import logging
from datetime import datetime
from app.database import db_session
from app.models import (
    User, AttendanceSession, Attendance, Location, SystemSetting,
    get_ist_now, get_ist_today
)
from app.utils.geo_utils import verify_student_location

logger = logging.getLogger(__name__)

class AttendanceService:
    @staticmethod
    def process_scan(usn: str, token: str, device_id: str,
                     lat: float = None, lon: float = None,
                     name: str = None, department: str = None,
                     division: str = None, semester: str = None,
                     custom_data: dict = None, session_id: int = None):
        """
        Core attendance processing engine:
        1. Multi-location geofence verification
        2. Hardware binding / Anti-proxy protection
        3. Dynamic user registration
        4. State machine: Single-scan vs Check-in / One-Time Checkout
        """
        usn = (usn or "").strip().upper()
        if not usn:
            return {"status": "error", "message": "USN / Roll Number is required."}

        if not device_id:
            return {"status": "error", "message": "Device identification failed. Please enable browser cookies and storage."}

        now = get_ist_now()
        today = get_ist_today()

        # 1. Resolve Target Session
        session = None
        if session_id:
            session = db_session.query(AttendanceSession).filter_by(id=session_id).first()
        if not session:
            active_setting = db_session.query(SystemSetting).filter_by(setting_key="active_session_id").first()
            if active_setting and active_setting.setting_value:
                try:
                    session = db_session.query(AttendanceSession).filter_by(id=int(active_setting.setting_value)).first()
                except (ValueError, TypeError):
                    session = None

        if not session:
            session = db_session.query(AttendanceSession).filter_by(is_active=True).order_by(AttendanceSession.id.desc()).first()

        if not session:
            return {"status": "error", "message": "No active attendance session found. Please contact the administrator."}

        # 2. Multi-Location Geofence Validation
        geofence_setting = db_session.query(SystemSetting).filter_by(setting_key="require_geofence").first()
        is_geofence_required = geofence_setting.setting_value.lower() == "true" if geofence_setting else True

        matched_loc_id = None
        matched_loc_name = None

        if is_geofence_required:
            if lat is None or lon is None:
                return {
                    "status": "error",
                    "message": "GPS coordinates not received. Please grant location permission to scan."
                }

            active_locations = db_session.query(Location).filter_by(is_active=True).all()
            is_inside, matched_loc, dist = verify_student_location(lat, lon, active_locations)

            if not is_inside:
                loc_hint = f" Closest location: '{matched_loc.name}' ({dist}m away, allowed radius: {matched_loc.radius_meters}m)" if matched_loc else ""
                return {
                    "status": "error",
                    "message": f"Outside permitted attendance perimeter.{loc_hint}"
                }
            if matched_loc:
                matched_loc_id = matched_loc.id
                matched_loc_name = matched_loc.name
        else:
            if lat is not None and lon is not None:
                active_locations = db_session.query(Location).filter_by(is_active=True).all()
                _, matched_loc, _ = verify_student_location(lat, lon, active_locations)
                if matched_loc:
                    matched_loc_id = matched_loc.id
                    matched_loc_name = matched_loc.name

        # 3. Anti-Proxy / Device Hardware Binding
        device_logs = db_session.query(Attendance).filter(
            Attendance.session_id == session.id,
            Attendance.date == today,
            Attendance.device_id == device_id
        ).all()

        other_students = {log.usn for log in device_logs if log.usn != usn}
        if other_students:
            proxy_usn = list(other_students)[0]
            return {
                "status": "error",
                "message": f"Security Alert: This device has already been bound to USN {proxy_usn} for this session today. Proxy attendance is strictly prohibited."
            }

        # 4. User Existence & Dynamic Registration Check
        user = db_session.query(User).filter_by(usn=usn).first()
        if not user:
            if not name or not department or not division or not semester:
                return {
                    "status": "new_user",
                    "message": "First time scanning? Please enter your registration details."
                }
            user = User(
                usn=usn,
                name=name.strip(),
                department=department.strip(),
                division=division.strip(),
                semester=semester.strip(),
                custom_data=custom_data or {}
            )
            db_session.add(user)
            db_session.flush()
        else:
            if name and name.strip():
                user.name = name.strip()
            if department:
                user.department = department.strip()
            if division:
                user.division = division.strip()
            if semester:
                user.semester = semester.strip()
            if custom_data:
                current_data = user.custom_data or {}
                current_data.update(custom_data)
                user.custom_data = current_data
            db_session.flush()

        # 5. Check Attendance State Machine for Session
        record = db_session.query(Attendance).filter_by(
            session_id=session.id,
            usn=usn,
            date=today
        ).first()

        # --- MODE 1: Single-scan (Count students present) ---
        if session.mode == "single_checkin":
            if record:
                checkin_str = record.checkin_time.strftime("%I:%M %p")
                return {
                    "status": "already_marked",
                    "action": "none",
                    "message": f"Attendance already recorded for {user.name} ({user.usn}) at {checkin_str}.",
                    "session_title": session.title,
                    "student_name": user.name
                }

            record = Attendance(
                session_id=session.id,
                usn=usn,
                date=today,
                checkin_time=now,
                checkout_time=now,
                status="Present",
                verified_location_id=matched_loc_id,
                location_name=matched_loc_name,
                device_id=device_id,
                latitude=lat,
                longitude=lon,
                remarks=f"Verified at {matched_loc_name or 'Authorized Area'}"
            )
            db_session.add(record)
            db_session.commit()

            total_present = db_session.query(Attendance).filter_by(session_id=session.id, date=today).count()
            return {
                "status": "success",
                "action": "checkin",
                "message": f"Welcome {user.name}! Attendance verified for '{session.title}'. (Total Present: {total_present})",
                "student_name": user.name,
                "session_title": session.title,
                "total_present": total_present
            }

        # --- MODE 2: Check-in & One-Time Check-out ---
        elif session.mode == "checkin_checkout":
            if not record:
                record = Attendance(
                    session_id=session.id,
                    usn=usn,
                    date=today,
                    checkin_time=now,
                    status="Checked In",
                    verified_location_id=matched_loc_id,
                    location_name=matched_loc_name,
                    device_id=device_id,
                    latitude=lat,
                    longitude=lon,
                    remarks="Checked In"
                )
                db_session.add(record)
                db_session.commit()
                return {
                    "status": "success",
                    "action": "checkin",
                    "message": f"Check-in successful at {now.strftime('%I:%M %p')}. Scan again when leaving to complete your one-time checkout.",
                    "student_name": user.name,
                    "session_title": session.title
                }

            if record.checkout_time is None:
                record.checkout_time = now
                record.status = "Present"
                t_now = now.replace(tzinfo=None) if getattr(now, 'tzinfo', None) else now
                t_checkin = record.checkin_time.replace(tzinfo=None) if getattr(record.checkin_time, 'tzinfo', None) else record.checkin_time
                diff = t_now - t_checkin
                hrs, rem = divmod(max(0, int(diff.total_seconds())), 3600)
                mins = rem // 60
                duration_str = f"{hrs}h {mins}m" if hrs > 0 else f"{mins}m"
                record.remarks = f"Completed ({duration_str})"
                db_session.commit()

                return {
                    "status": "success",
                    "action": "checkout",
                    "message": f"One-time checkout successful at {now.strftime('%I:%M %p')}! Total session time: {duration_str}.",
                    "student_name": user.name,
                    "session_title": session.title,
                    "duration": duration_str
                }
            else:
                return {
                    "status": "already_done",
                    "action": "none",
                    "message": f"You have already completed your one-time checkout today at {record.checkout_time.strftime('%I:%M %p')}. Multiple checkouts are not permitted.",
                    "student_name": user.name,
                    "session_title": session.title
                }

        return {"status": "error", "message": "Unknown session mode."}

import logging
from datetime import datetime
import pyotp
from flask import Blueprint, render_template, request, jsonify
from app.config import Config
from app.database import db_session
from app.models import (
    User, Department, Division, Semester, DynamicField,
    Location, AttendanceSession, Attendance, SystemSetting,
    get_ist_today
)
from app.services.attendance_service import AttendanceService

logger = logging.getLogger(__name__)
public_bp = Blueprint("public", __name__)

totp = pyotp.TOTP(Config.SHARED_SECRET, interval=Config.TOTP_INTERVAL)

@public_bp.route("/")
def index():
    """Live Dynamic QR Display screen for the active attendance session."""
    active_sessions = db_session.query(AttendanceSession).filter_by(is_active=True).order_by(AttendanceSession.id.desc()).all()
    active_setting = db_session.query(SystemSetting).filter_by(setting_key="active_session_id").first()
    selected_session = None

    if active_setting and active_setting.setting_value:
        try:
            selected_session = db_session.query(AttendanceSession).filter_by(id=int(active_setting.setting_value)).first()
        except (ValueError, TypeError):
            pass

    if not selected_session and active_sessions:
        selected_session = active_sessions[0]

    return render_template(
        "index.html",
        active_sessions=active_sessions,
        current_session=selected_session,
        totp_interval=Config.TOTP_INTERVAL
    )

@public_bp.route("/get_token")
def get_token():
    """API called periodically by the display screen to rotate the TOTP QR payload."""
    now_ts = int(datetime.now().timestamp())
    expires_in = Config.TOTP_INTERVAL - (now_ts % Config.TOTP_INTERVAL)

    session_id = request.args.get("session_id")
    target_session = None
    if session_id:
        try:
            target_session = db_session.query(AttendanceSession).filter_by(id=int(session_id)).first()
        except (ValueError, TypeError):
            pass

    if not target_session:
        active_setting = db_session.query(SystemSetting).filter_by(setting_key="active_session_id").first()
        if active_setting and active_setting.setting_value:
            try:
                target_session = db_session.query(AttendanceSession).filter_by(id=int(active_setting.setting_value)).first()
            except (ValueError, TypeError):
                pass

    if not target_session:
        target_session = db_session.query(AttendanceSession).filter_by(is_active=True).first()

    today = get_ist_today()
    count_today = 0
    if target_session:
        count_today = db_session.query(Attendance).filter_by(session_id=target_session.id, date=today).count()

    return jsonify({
        "token": totp.now(),
        "expires_in": expires_in,
        "session_id": target_session.id if target_session else None,
        "session_title": target_session.title if target_session else "General Attendance",
        "session_mode": target_session.mode if target_session else "single_checkin",
        "count_today": count_today
    })

@public_bp.route("/checkin")
def checkin():
    """Mobile check-in page with responsive touch layout and dynamic registration fields."""
    token = request.args.get("token", "")
    session_id = request.args.get("session_id")

    current_session = None
    if session_id:
        try:
            current_session = db_session.query(AttendanceSession).filter_by(id=int(session_id)).first()
        except (ValueError, TypeError):
            pass

    if not current_session:
        active_setting = db_session.query(SystemSetting).filter_by(setting_key="active_session_id").first()
        if active_setting and active_setting.setting_value:
            try:
                current_session = db_session.query(AttendanceSession).filter_by(id=int(active_setting.setting_value)).first()
            except (ValueError, TypeError):
                pass

    departments = db_session.query(Department).filter_by(is_active=True).order_by(Department.code).all()
    divisions = db_session.query(Division).filter_by(is_active=True).order_by(Division.name).all()
    semesters = db_session.query(Semester).filter_by(is_active=True).order_by(Semester.name).all()
    dynamic_fields = db_session.query(DynamicField).filter_by(is_active=True).order_by(DynamicField.display_order).all()
    active_locations = db_session.query(Location).filter_by(is_active=True).all()

    geofence_setting = db_session.query(SystemSetting).filter_by(setting_key="require_geofence").first()
    require_geofence = geofence_setting.setting_value.lower() == "true" if geofence_setting else True

    return render_template(
        "checkin.html",
        token=token,
        current_session=current_session,
        departments=departments,
        divisions=divisions,
        semesters=semesters,
        dynamic_fields=[df.to_dict() for df in dynamic_fields],
        active_locations=[loc.to_dict() for loc in active_locations],
        require_geofence=require_geofence
    )

@public_bp.route("/api/check_usn")
def api_check_usn():
    """Quick lookup to pre-fill known student registration data."""
    usn = request.args.get("usn", "").strip().upper()
    if not usn:
        return jsonify({"exists": False})

    user = db_session.query(User).filter_by(usn=usn).first()
    if user:
        return jsonify({
            "exists": True,
            "user": user.to_dict()
        })
    return jsonify({"exists": False})

@public_bp.route("/submit", methods=["POST"])
def submit_attendance():
    """Core attendance submission endpoint."""
    token = request.form.get("token")
    device_id = request.form.get("device_id")
    usn = request.form.get("usn", "").strip().upper()
    name = request.form.get("name", "").strip()
    department = request.form.get("department", "").strip()
    division = request.form.get("division", "").strip()
    semester = request.form.get("semester", "").strip()
    session_id_raw = request.form.get("session_id")

    session_id = None
    if session_id_raw:
        try:
            session_id = int(session_id_raw)
        except (ValueError, TypeError):
            pass

    if not token or not totp.verify(token, valid_window=1):
        return jsonify({
            "status": "error",
            "message": "QR Code has expired or is invalid. Please rescan the latest QR displayed on screen."
        })

    lat = None
    lon = None
    try:
        lat_raw = request.form.get("lat")
        lon_raw = request.form.get("lon")
        if lat_raw is not None and lon_raw is not None:
            lat = float(lat_raw)
            lon = float(lon_raw)
    except (ValueError, TypeError):
        lat = None
        lon = None

    custom_data = {}
    dynamic_fields = db_session.query(DynamicField).filter_by(is_active=True).all()
    for df in dynamic_fields:
        val = request.form.get(f"custom_{df.field_key}", "").strip()
        if val:
            custom_data[df.field_key] = val

    result = AttendanceService.process_scan(
        usn=usn,
        token=token,
        device_id=device_id,
        lat=lat,
        lon=lon,
        name=name,
        department=department,
        division=division,
        semester=semester,
        custom_data=custom_data,
        session_id=session_id
    )

    return jsonify(result)

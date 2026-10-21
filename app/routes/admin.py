import os
import logging
from datetime import datetime
from functools import wraps
import pandas as pd
from flask import (
    Blueprint, render_template, request, jsonify, session,
    redirect, url_for, make_response, send_file
)
from werkzeug.security import generate_password_hash, check_password_hash

from app.config import Config
from app.database import db_session, get_db_info
from app.models import (
    User, Department, Division, Semester, DynamicField,
    Location, AttendanceSession, Attendance, SystemSetting,
    get_ist_now, get_ist_today
)
from app.services.export_service import ExportService

logger = logging.getLogger(__name__)
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("admin.admin_login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# ----------------- AUTHENTICATION -----------------

@admin_bp.route("/login", methods=["GET", "POST"])
def admin_login():
    """Secure Admin Login Portal."""
    if session.get("logged_in"):
        return redirect(url_for("admin.admin_dashboard"))

    error = None
    if request.method == "POST":
        password = request.form.get("password", "")
        stored_hash = db_session.query(SystemSetting).filter_by(setting_key="admin_password_hash").first()
        is_valid = False
        if stored_hash and stored_hash.setting_value:
            is_valid = check_password_hash(stored_hash.setting_value, password)
        else:
            if password == Config.ADMIN_PASSWORD:
                is_valid = True
                new_hash = generate_password_hash(Config.ADMIN_PASSWORD)
                db_session.add(SystemSetting(setting_key="admin_password_hash", setting_value=new_hash))
                db_session.commit()

        if is_valid:
            session["logged_in"] = True
            session["admin_user"] = Config.ADMIN_USERNAME
            next_url = request.args.get("next") or url_for("admin.admin_dashboard")
            return redirect(next_url)
        else:
            error = "Invalid administrator password. Please try again."

    return render_template("login.html", error=error)

@admin_bp.route("/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin.admin_login"))

@admin_bp.route("/dashboard")
@login_required
def admin_dashboard():
    """Unified Admin Dashboard."""
    filter_date = request.args.get("date", get_ist_today().strftime("%Y-%m-%d"))
    filter_dept = request.args.get("department", "All")
    filter_div = request.args.get("division", "All")
    filter_sem = request.args.get("semester", "All")
    filter_session = request.args.get("session_id", "All")
    search = request.args.get("search", "").strip()

    total_users = db_session.query(User).count()
    today_records_count = db_session.query(Attendance).filter_by(date=get_ist_today()).count()
    active_locs_count = db_session.query(Location).filter_by(is_active=True).count()
    total_sessions_count = db_session.query(AttendanceSession).count()

    departments = db_session.query(Department).order_by(Department.code).all()
    divisions = db_session.query(Division).order_by(Division.name).all()
    semesters = db_session.query(Semester).order_by(Semester.name).all()
    locations = db_session.query(Location).order_by(Location.id.desc()).all()
    sessions = db_session.query(AttendanceSession).order_by(AttendanceSession.id.desc()).all()
    dynamic_fields = db_session.query(DynamicField).order_by(DynamicField.display_order).all()

    geofence_setting = db_session.query(SystemSetting).filter_by(setting_key="require_geofence").first()
    require_geofence = geofence_setting.setting_value.lower() == "true" if geofence_setting else True

    active_session_setting = db_session.query(SystemSetting).filter_by(setting_key="active_session_id").first()
    active_session_id = int(active_session_setting.setting_value) if (active_session_setting and active_session_setting.setting_value) else None

    records = ExportService.query_attendance(
        date_from=filter_date,
        date_to=filter_date,
        department=filter_dept,
        division=filter_div,
        semester=filter_sem,
        session_id=filter_session,
        search=search
    )

    db_info = get_db_info()

    return render_template(
        "admin_dashboard.html",
        records=records,
        total_users=total_users,
        today_records_count=today_records_count,
        active_locs_count=active_locs_count,
        total_sessions_count=total_sessions_count,
        departments=departments,
        divisions=divisions,
        semesters=semesters,
        locations=locations,
        sessions=sessions,
        dynamic_fields=dynamic_fields,
        require_geofence=require_geofence,
        active_session_id=active_session_id,
        current_date=filter_date,
        current_dept=filter_dept,
        current_div=filter_div,
        current_sem=filter_sem,
        current_session=filter_session,
        search=search,
        db_info=db_info
    )

# ----------------- SESSION MANAGEMENT -----------------

@admin_bp.route("/sessions/create", methods=["POST"])
@login_required
def admin_create_session():
    title = request.form.get("title", "").strip()
    session_code = request.form.get("session_code", "").strip().upper()
    mode = request.form.get("mode", "single_checkin")
    date_str = request.form.get("date")

    if not title:
        return redirect(url_for("admin.admin_dashboard", tab="sessions", error="Title is required"))

    if not session_code:
        session_code = f"SES-{int(datetime.now().timestamp()) % 100000}"

    try:
        session_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else get_ist_today()
    except ValueError:
        session_date = get_ist_today()

    new_session = AttendanceSession(
        title=title,
        session_code=session_code,
        mode=mode,
        is_active=True,
        date=session_date
    )
    db_session.add(new_session)
    db_session.commit()

    active_setting = db_session.query(SystemSetting).filter_by(setting_key="active_session_id").first()
    if active_setting:
        active_setting.setting_value = str(new_session.id)
    else:
        db_session.add(SystemSetting(setting_key="active_session_id", setting_value=str(new_session.id)))
    db_session.commit()

    return redirect(url_for("admin.admin_dashboard", tab="sessions", success="Session created successfully!"))

@admin_bp.route("/sessions/set_active", methods=["POST"])
@login_required
def admin_set_active_session():
    session_id = request.form.get("session_id")
    if session_id:
        active_setting = db_session.query(SystemSetting).filter_by(setting_key="active_session_id").first()
        if active_setting:
            active_setting.setting_value = str(session_id)
        else:
            db_session.add(SystemSetting(setting_key="active_session_id", setting_value=str(session_id)))
        db_session.commit()
    return redirect(url_for("admin.admin_dashboard", tab="sessions"))

@admin_bp.route("/sessions/toggle", methods=["POST"])
@login_required
def admin_toggle_session():
    data = request.json or {}
    session_id = data.get("session_id")
    sess = db_session.query(AttendanceSession).filter_by(id=session_id).first()
    if sess:
        sess.is_active = not sess.is_active
        db_session.commit()
        return jsonify({"status": "success", "is_active": sess.is_active})
    return jsonify({"status": "error", "message": "Session not found"}), 404

@admin_bp.route("/sessions/delete", methods=["POST"])
@login_required
def admin_delete_session():
    data = request.json or {}
    session_id = data.get("session_id")
    sess = db_session.query(AttendanceSession).filter_by(id=session_id).first()
    if sess:
        db_session.delete(sess)
        db_session.commit()
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Session not found"}), 404

# ----------------- LOCATION MANAGEMENT -----------------

@admin_bp.route("/locations/add", methods=["POST"])
@login_required
def admin_add_location():
    name = request.form.get("name", "").strip()
    try:
        lat = float(request.form.get("latitude"))
        lon = float(request.form.get("longitude"))
        rad = float(request.form.get("radius_meters", 100.0))
    except (TypeError, ValueError):
        return redirect(url_for("admin.admin_dashboard", tab="locations", error="Invalid latitude/longitude/radius"))

    if not name:
        return redirect(url_for("admin.admin_dashboard", tab="locations", error="Location name is required"))

    loc = Location(name=name, latitude=lat, longitude=lon, radius_meters=rad, is_active=True)
    db_session.add(loc)
    db_session.commit()
    return redirect(url_for("admin.admin_dashboard", tab="locations", success="Location added successfully!"))

@admin_bp.route("/locations/toggle", methods=["POST"])
@login_required
def admin_toggle_location():
    data = request.json or {}
    loc_id = data.get("location_id")
    loc = db_session.query(Location).filter_by(id=loc_id).first()
    if loc:
        loc.is_active = not loc.is_active
        db_session.commit()
        return jsonify({"status": "success", "is_active": loc.is_active})
    return jsonify({"status": "error", "message": "Location not found"}), 404

@admin_bp.route("/locations/delete", methods=["POST"])
@login_required
def admin_delete_location():
    data = request.json or {}
    loc_id = data.get("location_id")
    loc = db_session.query(Location).filter_by(id=loc_id).first()
    if loc:
        db_session.delete(loc)
        db_session.commit()
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Location not found"}), 404

@admin_bp.route("/toggle_geofence", methods=["POST"])
@login_required
def admin_toggle_geofence():
    data = request.json or {}
    val = "true" if data.get("require_geofence") else "false"
    setting = db_session.query(SystemSetting).filter_by(setting_key="require_geofence").first()
    if setting:
        setting.setting_value = val
    else:
        db_session.add(SystemSetting(setting_key="require_geofence", setting_value=val))
    db_session.commit()
    return jsonify({"status": "success", "require_geofence": val == "true"})

# ----------------- LOOKUPS & DYNAMIC FIELDS -----------------

@admin_bp.route("/lookup/manage", methods=["POST"])
@login_required
def admin_manage_lookup():
    data = request.json or {}
    l_type = data.get("type")
    action = data.get("action")
    name = (data.get("name") or "").strip()
    code = (data.get("code") or "").strip().upper()

    if not name:
        return jsonify({"status": "error", "message": "Name is required"}), 400

    if l_type == "department":
        if action == "add":
            if not code:
                code = name[:4].upper()
            existing = db_session.query(Department).filter((Department.code == code) | (Department.name == name)).first()
            if not existing:
                db_session.add(Department(code=code, name=name, is_active=True))
        elif action == "delete":
            item = db_session.query(Department).filter_by(id=data.get("id")).first()
            if item:
                db_session.delete(item)

    elif l_type == "division":
        if action == "add":
            existing = db_session.query(Division).filter_by(name=name).first()
            if not existing:
                db_session.add(Division(name=name, is_active=True))
        elif action == "delete":
            item = db_session.query(Division).filter_by(id=data.get("id")).first()
            if item:
                db_session.delete(item)

    elif l_type == "semester":
        if action == "add":
            existing = db_session.query(Semester).filter_by(name=name).first()
            if not existing:
                db_session.add(Semester(name=name, is_active=True))
        elif action == "delete":
            item = db_session.query(Semester).filter_by(id=data.get("id")).first()
            if item:
                db_session.delete(item)

    db_session.commit()
    return jsonify({"status": "success"})

@admin_bp.route("/dynamic_fields/add", methods=["POST"])
@login_required
def admin_add_dynamic_field():
    label = request.form.get("label", "").strip()
    field_key = request.form.get("field_key", "").strip().lower().replace(" ", "_")
    field_type = request.form.get("field_type", "text")
    options = request.form.get("options", "").strip()
    is_required = bool(request.form.get("is_required"))

    if not label or not field_key:
        return redirect(url_for("admin.admin_dashboard", tab="fields", error="Label and Key are required"))

    existing = db_session.query(DynamicField).filter_by(field_key=field_key).first()
    if existing:
        return redirect(url_for("admin.admin_dashboard", tab="fields", error=f"Field key '{field_key}' already exists"))

    order = db_session.query(DynamicField).count() + 1
    new_field = DynamicField(
        field_key=field_key,
        label=label,
        field_type=field_type,
        options=options if field_type == "select" else None,
        is_required=is_required,
        is_active=True,
        display_order=order
    )
    db_session.add(new_field)
    db_session.commit()
    return redirect(url_for("admin.admin_dashboard", tab="fields", success="Dynamic field created successfully!"))

@admin_bp.route("/dynamic_fields/delete", methods=["POST"])
@login_required
def admin_delete_dynamic_field():
    data = request.json or {}
    field_id = data.get("field_id")
    field = db_session.query(DynamicField).filter_by(id=field_id).first()
    if field:
        db_session.delete(field)
        db_session.commit()
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Field not found"}), 404

# ----------------- BULK CSV ROSTER IMPORT -----------------

@admin_bp.route("/upload_csv", methods=["POST"])
@login_required
def admin_upload_csv():
    if "file" not in request.files:
        return redirect(url_for("admin.admin_dashboard", tab="import", error="No file selected"))

    file = request.files["file"]
    if file.filename == "":
        return redirect(url_for("admin.admin_dashboard", tab="import", error="No file selected"))

    try:
        df = pd.read_csv(file).fillna("")
        df.columns = df.columns.str.lower().str.strip()

        if "usn" not in df.columns or "name" not in df.columns:
            return redirect(url_for("admin.admin_dashboard", tab="import", error="CSV must contain 'USN' and 'Name' columns."))

        df["usn"] = df["usn"].astype(str).str.strip().str.upper()
        df = df[df["usn"] != ""]
        df = df.drop_duplicates(subset=["usn"], keep="last")

        for _, row in df.iterrows():
            usn = row["usn"]
            name = str(row["name"]).strip()
            dept = str(row.get("department", row.get("domain", ""))).strip()
            div = str(row.get("division", row.get("div", ""))).strip()
            sem = str(row.get("semester", row.get("sem", row.get("batch", "")))).strip()

            if dept:
                existing_dept = db_session.query(Department).filter(
                    (Department.code == dept.upper()) | (Department.name == dept)
                ).first()
                if not existing_dept:
                    db_session.add(Department(code=dept[:6].upper(), name=dept, is_active=True))

            if div:
                existing_div = db_session.query(Division).filter_by(name=div).first()
                if not existing_div:
                    db_session.add(Division(name=div, is_active=True))

            if sem:
                existing_sem = db_session.query(Semester).filter_by(name=sem).first()
                if not existing_sem:
                    db_session.add(Semester(name=sem, is_active=True))

            user = db_session.query(User).filter_by(usn=usn).first()
            if not user:
                user = User(usn=usn, name=name, department=dept, division=div, semester=sem)
                db_session.add(user)
            else:
                user.name = name
                if dept: user.department = dept
                if div: user.division = div
                if sem: user.semester = sem

        db_session.commit()
        return redirect(url_for("admin.admin_dashboard", tab="import", success=f"Successfully ingested {len(df)} student records."))

    except Exception as e:
        logger.error(f"Error during bulk CSV import: {e}")
        return redirect(url_for("admin.admin_dashboard", tab="import", error=f"CSV processing failed: {str(e)}"))

# ----------------- EXPORT STUDIO (EXCEL & CSV) -----------------

@admin_bp.route("/export/excel")
@login_required
def admin_export_excel():
    date_from = request.args.get("date_from") or None
    date_to = request.args.get("date_to") or None
    dept = request.args.get("department", "All")
    div = request.args.get("division", "All")
    sem = request.args.get("semester", "All")
    sess_id = request.args.get("session_id", "All")

    records = ExportService.query_attendance(
        date_from=date_from,
        date_to=date_to,
        department=dept,
        division=div,
        semester=sem,
        session_id=sess_id
    )

    excel_buffer = ExportService.export_excel(records)
    timestamp = get_ist_now().strftime("%Y%m%d_%H%M%S")
    filename = f"Attendance_Export_{timestamp}.xlsx"

    return send_file(
        excel_buffer,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )

@admin_bp.route("/export/csv")
@login_required
def admin_export_csv():
    date_from = request.args.get("date_from") or None
    date_to = request.args.get("date_to") or None
    dept = request.args.get("department", "All")
    div = request.args.get("division", "All")
    sem = request.args.get("semester", "All")
    sess_id = request.args.get("session_id", "All")

    records = ExportService.query_attendance(
        date_from=date_from,
        date_to=date_to,
        department=dept,
        division=div,
        semester=sem,
        session_id=sess_id
    )

    csv_data = ExportService.export_csv(records)
    timestamp = get_ist_now().strftime("%Y%m%d_%H%M%S")
    filename = f"Attendance_Export_{timestamp}.csv"

    response = make_response(csv_data)
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    return response

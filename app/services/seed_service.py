import logging
from app.database import db_session
from app.models import Department, Division, Semester, DynamicField, Location, AttendanceSession, SystemSetting, get_ist_today

logger = logging.getLogger(__name__)

def seed_defaults():
    """Seed initial lookup values and settings if database is newly initialized."""
    # 1. Departments
    if db_session.query(Department).count() == 0:
        default_depts = [
            ("CSE", "Computer Science & Engineering"),
            ("ISE", "Information Science & Engineering"),
            ("AIML", "Artificial Intelligence & Machine Learning"),
            ("ECE", "Electronics & Communication Engineering"),
            ("MECH", "Mechanical Engineering"),
            ("CIVIL", "Civil Engineering")
        ]
        for code, name in default_depts:
            db_session.add(Department(code=code, name=name, is_active=True))
        logger.info("Default departments seeded.")

    # 2. Divisions
    if db_session.query(Division).count() == 0:
        default_divs = ["A", "B", "C", "D"]
        for div in default_divs:
            db_session.add(Division(name=div, is_active=True))
        logger.info("Default divisions seeded.")

    # 3. Semesters
    if db_session.query(Semester).count() == 0:
        default_sems = [f"Sem {i}" for i in range(1, 9)]
        for sem in default_sems:
            db_session.add(Semester(name=sem, is_active=True))
        logger.info("Default semesters seeded.")

    # 4. Dynamic Fields
    if db_session.query(DynamicField).count() == 0:
        db_session.add(DynamicField(
            field_key="phone",
            label="Mobile Number",
            field_type="number",
            is_required=False,
            is_active=True,
            display_order=1
        ))
        logger.info("Default dynamic fields seeded.")

    # 5. Default Locations
    if db_session.query(Location).count() == 0:
        default_locations = [
            ("Main Campus - CS Block", 15.778169, 74.460522, 150.0, True),
            ("Auditorium / Seminar Hall", 15.774238, 74.466045, 100.0, True),
            ("Central Library & Lab", 15.775500, 74.462500, 120.0, True)
        ]
        for name, lat, lon, rad, act in default_locations:
            db_session.add(Location(name=name, latitude=lat, longitude=lon, radius_meters=rad, is_active=act))
        logger.info("Default locations seeded.")

    # 6. Default Settings (No pre-created sessions or students)
    settings_map = {
        "require_geofence": "true",
        "active_session_id": "",
        "allow_registration": "true"
    }
    for key, val in settings_map.items():
        existing = db_session.query(SystemSetting).filter_by(setting_key=key).first()
        if not existing:
            db_session.add(SystemSetting(setting_key=key, setting_value=val))

    db_session.commit()

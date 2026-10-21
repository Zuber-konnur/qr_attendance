from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, Text, ForeignKey, UniqueConstraint, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from zoneinfo import ZoneInfo
from app.database import Base

def get_ist_now():
    return datetime.now(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None)

def get_ist_today():
    return get_ist_now().date()

class User(Base):
    __tablename__ = "users"

    usn = Column(String(64), primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    department = Column(String(64), nullable=True, index=True)
    division = Column(String(32), nullable=True, index=True)
    semester = Column(String(32), nullable=True, index=True)
    custom_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=get_ist_now)

    attendances = relationship("Attendance", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "usn": self.usn,
            "name": self.name,
            "department": self.department or "",
            "division": self.division or "",
            "semester": self.semester or "",
            "custom_data": self.custom_data or {},
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else ""
        }

class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(32), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    is_active = Column(Boolean, default=True)

    def to_dict(self):
        return {"id": self.id, "code": self.code, "name": self.name, "is_active": self.is_active}

class Division(Base):
    __tablename__ = "divisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(32), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "is_active": self.is_active}

class Semester(Base):
    __tablename__ = "semesters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(32), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "is_active": self.is_active}

class DynamicField(Base):
    __tablename__ = "dynamic_fields"

    id = Column(Integer, primary_key=True, autoincrement=True)
    field_key = Column(String(64), unique=True, nullable=False, index=True)
    label = Column(String(128), nullable=False)
    field_type = Column(String(32), default="text")
    options = Column(Text, nullable=True)
    is_required = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)

    def to_dict(self):
        opts = [o.strip() for o in self.options.split(",") if o.strip()] if self.options else []
        return {
            "id": self.id,
            "field_key": self.field_key,
            "label": self.label,
            "field_type": self.field_type,
            "options": opts,
            "raw_options": self.options or "",
            "is_required": self.is_required,
            "is_active": self.is_active,
            "display_order": self.display_order
        }

class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    radius_meters = Column(Float, default=100.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=get_ist_now)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "radius_meters": self.radius_meters,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else ""
        }

class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(128), nullable=False)
    session_code = Column(String(64), unique=True, nullable=False, index=True)
    mode = Column(String(32), default="single_checkin")
    is_active = Column(Boolean, default=True)
    date = Column(Date, default=get_ist_today, index=True)
    created_at = Column(DateTime, default=get_ist_now)

    attendances = relationship("Attendance", back_populates="session", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "session_code": self.session_code,
            "mode": self.mode,
            "mode_label": "One-Time Attendance (Count Attendees)" if self.mode == "single_checkin" else "Check-in & Check-out",
            "is_active": self.is_active,
            "date": self.date.strftime("%Y-%m-%d") if self.date else "",
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else ""
        }

class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('attendance_sessions.id', ondelete='CASCADE'), nullable=False, index=True)
    usn = Column(String(64), ForeignKey('users.usn', ondelete='CASCADE'), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    checkin_time = Column(DateTime, nullable=False)
    checkout_time = Column(DateTime, nullable=True)
    status = Column(String(32), default="Present")
    verified_location_id = Column(Integer, ForeignKey('locations.id', ondelete='SET NULL'), nullable=True)
    location_name = Column(String(128), nullable=True)
    device_id = Column(String(128), nullable=False, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    remarks = Column(String(256), nullable=True)

    __table_args__ = (
        UniqueConstraint('session_id', 'usn', 'date', name='uq_session_usn_date'),
    )

    user = relationship("User", back_populates="attendances")
    session = relationship("AttendanceSession", back_populates="attendances")
    location = relationship("Location")

    def duration_formatted(self):
        if not self.checkin_time or not self.checkout_time:
            return "--"
        t1 = self.checkin_time.replace(tzinfo=None) if self.checkin_time.tzinfo else self.checkin_time
        t2 = self.checkout_time.replace(tzinfo=None) if self.checkout_time.tzinfo else self.checkout_time
        diff = t2 - t1
        total_seconds = max(0, int(diff.total_seconds()))
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

class SystemSetting(Base):
    __tablename__ = "system_settings"

    setting_key = Column(String(64), primary_key=True)
    setting_value = Column(Text, nullable=False)

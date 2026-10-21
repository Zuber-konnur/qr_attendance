import unittest
import uuid
from app import create_app
from app.database import db_session, init_db
from app.models import AttendanceSession, Attendance, User, get_ist_today
from app.services.attendance_service import AttendanceService
from app.services.export_service import ExportService
from app.utils.geo_utils import haversine_distance
import pyotp
from app.config import Config

class TestQRAttendanceSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        init_db()

    def setUp(self):
        db_session.rollback()
        self.totp = pyotp.TOTP(Config.SHARED_SECRET, interval=Config.TOTP_INTERVAL)
        self.device_1 = f"dev-1-{uuid.uuid4().hex[:6]}"
        self.device_2 = f"dev-2-{uuid.uuid4().hex[:6]}"

    def tearDown(self):
        db_session.rollback()

    def test_haversine_distance(self):
        p1_lat, p1_lon = 15.778169, 74.460522
        p2_lat, p2_lon = 15.778169, 74.460622
        dist = haversine_distance(p1_lat, p1_lon, p2_lat, p2_lon)
        self.assertTrue(0 < dist < 50)

    def test_one_time_attendance_session(self):
        sess_code = f"TEST-AI-{uuid.uuid4().hex[:6]}"
        session = AttendanceSession(
            title="AI Workshop Lab",
            session_code=sess_code,
            mode="single_checkin",
            is_active=True,
            date=get_ist_today()
        )
        db_session.add(session)
        db_session.commit()

        usn = f"USN1_{uuid.uuid4().hex[:6]}"
        # Mark attendance 1st time
        res1 = AttendanceService.process_scan(
            usn=usn,
            token=self.totp.now(),
            device_id=self.device_1,
            lat=15.778169,
            lon=74.460522,
            name="Alice Smith",
            department="CSE",
            division="A",
            semester="Sem 5",
            session_id=session.id
        )
        self.assertEqual(res1["status"], "success")
        self.assertEqual(res1["action"], "checkin")

        # Attempt to mark attendance 2nd time in same session -> informs already marked
        res2 = AttendanceService.process_scan(
            usn=usn,
            token=self.totp.now(),
            device_id=self.device_1,
            lat=15.778169,
            lon=74.460522,
            session_id=session.id
        )
        self.assertEqual(res2["status"], "already_marked")

    def test_checkin_and_one_time_checkout(self):
        sess_code = f"TEST-DAY-{uuid.uuid4().hex[:6]}"
        session = AttendanceSession(
            title="Full Day College",
            session_code=sess_code,
            mode="checkin_checkout",
            is_active=True,
            date=get_ist_today()
        )
        db_session.add(session)
        db_session.commit()

        usn = f"USN2_{uuid.uuid4().hex[:6]}"
        # Step 1: Check-in
        res1 = AttendanceService.process_scan(
            usn=usn,
            token=self.totp.now(),
            device_id=self.device_2,
            lat=15.778169,
            lon=74.460522,
            name="Bob Jones",
            department="ISE",
            division="B",
            semester="Sem 3",
            session_id=session.id
        )
        self.assertEqual(res1["status"], "success")
        self.assertEqual(res1["action"], "checkin")

        # Step 2: One-time Checkout
        res2 = AttendanceService.process_scan(
            usn=usn,
            token=self.totp.now(),
            device_id=self.device_2,
            lat=15.778169,
            lon=74.460522,
            session_id=session.id
        )
        self.assertEqual(res2["status"], "success")
        self.assertEqual(res2["action"], "checkout")

        # Step 3: Attempt a second checkout -> should strictly reject!
        res3 = AttendanceService.process_scan(
            usn=usn,
            token=self.totp.now(),
            device_id=self.device_2,
            lat=15.778169,
            lon=74.460522,
            session_id=session.id
        )
        self.assertEqual(res3["status"], "already_done")

    def test_anti_proxy_device_binding(self):
        sess_code = f"TEST-EXAM-{uuid.uuid4().hex[:6]}"
        session = AttendanceSession(
            title="Exam Hall Attendance",
            session_code=sess_code,
            mode="single_checkin",
            is_active=True,
            date=get_ist_today()
        )
        db_session.add(session)
        db_session.commit()

        shared_phone_uuid = f"shared-phone-{uuid.uuid4().hex[:6]}"
        usn_a = f"USN_A_{uuid.uuid4().hex[:6]}"
        usn_b = f"USN_B_{uuid.uuid4().hex[:6]}"

        res1 = AttendanceService.process_scan(
            usn=usn_a,
            token=self.totp.now(),
            device_id=shared_phone_uuid,
            lat=15.778169,
            lon=74.460522,
            name="Student A",
            department="CSE",
            division="A",
            semester="Sem 7",
            session_id=session.id
        )
        self.assertEqual(res1["status"], "success")

        # Student 2 tries to mark attendance on the SAME device -> anti-proxy security alert!
        res2 = AttendanceService.process_scan(
            usn=usn_b,
            token=self.totp.now(),
            device_id=shared_phone_uuid,
            lat=15.778169,
            lon=74.460522,
            name="Student B",
            department="CSE",
            division="A",
            semester="Sem 7",
            session_id=session.id
        )
        self.assertEqual(res2["status"], "error")
        self.assertIn("Security Alert", res2["message"])

    def test_excel_and_csv_export(self):
        records = ExportService.query_attendance()
        self.assertIsNotNone(records)

        csv_content = ExportService.export_csv(records)
        self.assertIn("USN", csv_content)
        self.assertIn("Student Name", csv_content)

        excel_buffer = ExportService.export_excel(records)
        self.assertGreater(excel_buffer.getbuffer().nbytes, 100)

if __name__ == "__main__":
    unittest.main()

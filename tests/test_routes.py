import unittest
from app import create_app
from app.config import Config

class TestWebRoutes(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    def test_public_routes(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Smart QR Attendance", res.data)

        res = self.client.get("/get_token")
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()
        self.assertIn("token", json_data)
        self.assertIn("expires_in", json_data)

        res = self.client.get("/checkin")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Student Attendance", res.data)

    def test_admin_flow(self):
        res = self.client.get("/admin/dashboard")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/admin/login", res.headers["Location"])

        res = self.client.post("/admin/login", data={"password": Config.ADMIN_PASSWORD}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Attendance Stream", res.data)

        res = self.client.get("/admin/export/excel")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content_type, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        res = self.client.get("/admin/export/csv")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/csv", res.content_type)

if __name__ == "__main__":
    unittest.main()

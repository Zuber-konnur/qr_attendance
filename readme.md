# 📱 Enterprise Smart QR Attendance System

A production-grade, database-agnostic, and anti-spoofing attendance automation platform built with **Python (Flask)**, **SQLAlchemy 2.0**, and modern **Bootstrap 5.3**.

---

## 🌟 Key Features & Capabilities

### 1. Dual Attendance Modes
- **One-Time Session Attendance (Count Attendees)**: Designed for lectures, workshops, exams, or seminars where a single scan confirms presence and immediately computes the live attendee count.
- **Check-in & One-Time Check-out (Full Day / Lab Mode)**: Enforces an explicit check-in and strictly **one-time check-out** (preventing multiple check-outs or checking out before check-in), calculating total duration automatically.

### 2. Comprehensive Student Attributes & Dynamic Custom Fields
- Core student fields: **USN**, **Name**, **Department**, **Division**, and **Semester**.
- **Dynamic Custom Fields Builder**: Administrators can add custom registration fields (e.g. Mobile Number, Seat Number, Guardian Contact) with customizable input types (Text, Number, Dropdown) and validation rules.
- **Dynamic Lookups**: Administrators can dynamically add and manage Departments, Divisions, and Semesters from the Admin Console.

### 3. Multi-Location Geofencing with Radius Perimeter
- Multiple attendance zones can be created with precise center GPS coordinates (`latitude`, `longitude`) and a custom radius in meters (e.g., 50m, 100m, 200m).
- Each location can be dynamically **Enabled** or **Disabled** with a single click.
- Includes a **"🎯 Use My Current GPS Position"** one-click tool in the admin console.
- Global geofencing enforcement can be toggled On or Off.

### 4. Database-Agnostic Engine (SQLite, PostgreSQL, MySQL)
- Seamlessly transition between database engines simply by updating `DATABASE_URL` in `.env`:
  - **SQLite** (Default, zero-setup local storage for testing and edge deployments)
  - **PostgreSQL / Supabase** (Enterprise cloud or hosted database)
  - **MySQL** (Traditional institutional infrastructure)
- Automated schema creation and lookup data seeding on initial run.

### 5. Advanced Export Studio
- Export attendance records filtered by:
  - **Date Range** (From Date to To Date)
  - **Department** (e.g. CSE, ISE, AIML, ECE, MECH, CIVIL)
  - **Division** (e.g. Div A, Div B, Div C)
  - **Semester** (e.g. Sem 1 through Sem 8)
  - **Session** (Specific class or lecture)
- **Formats Available**:
  - 📊 **Styled Excel (.xlsx)**: Formatted table with dark headers, alternating row colors, auto-fit column widths, and duration metrics.
  - 📄 **Clean CSV (.csv)**: Clean comma-separated export suitable for ERP or data analysis.

### 6. Mobile-First Responsive Interface
- Optimized for mobile phone screens with touch-friendly input fields and floating status pills.
- Instant USN auto-fill: When a registered student types their USN, their name, department, division, and semester are instantly recognized.
- Live GPS radar indicator providing real-time perimeter distance feedback.

### 7. Anti-Proxy & Hardware Binding Protection
- **TOTP QR Code**: QR code rotates every 30 seconds using RFC 6238 time-based tokens, defeating static screenshots and shared links.
- **1-Device-1-User Daily Binding**: Devices are fingerprinted using combined browser cookies and `localStorage` UUIDs, preventing one smartphone from checking in multiple students.

---

## 🏗️ System Architecture

```text
[ Classroom Display Screen: / ]  <--->  Auto-refreshing 30s TOTP QR Payload
            |
       (Scan with Phone)
            v
[ Mobile Check-in App: /checkin ]
  ├── 🛰️ Browser GPS Geofence Check (Perimeter Radius)
  ├── 📱 Persistent Device ID Fingerprint
  └── 🆔 USN Auto-Lookup & Dynamic Registration
            |
            v
[ Flask Backend Engine: /submit ]
  ├── 🔐 PyOTP Token Window Verification
  ├── 🛡️ Anti-Proxy Hardware Collision Check
  ├── 📍 Multi-Location Haversine Distance Check
  └── ⚡ State Machine (One-Time Count vs Check-in / One-Time Checkout)
            |
            v
[ Multi-Database Layer (SQLAlchemy ORM) ]
  ├── SQLite (Default: sqlite:///attendance.db)
  ├── PostgreSQL / Supabase (postgresql://...)
  └── MySQL (mysql+pymysql://...)
```

---

## 📦 Installation & Setup (Using Virtual Environment)

### 1. Clone & Enter Directory
```bash
git clone <repository-url>
cd qr_attendance
```

### 2. Activate Virtual Environment
```bash
# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Windows (Command Prompt)
.\venv\Scripts\activate.bat

# Linux / macOS
source venv/bin/activate
```

*(If creating a new virtual environment: `python -m venv venv`)*

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## ⚙️ Database Configuration (`.env`)

Create or edit your `.env` file in the project root:

```env
# Choose your database by setting DATABASE_URL:

# Option A: Local SQLite (Zero setup, default)
DATABASE_URL=sqlite:///attendance.db

# Option B: PostgreSQL / Supabase
# DATABASE_URL=postgresql://postgres:your_password@localhost:5432/attendance_db

# Option C: MySQL
# DATABASE_URL=mysql+pymysql://root:your_password@localhost:3306/attendance_db

# Security & Admin Settings
SECRET_KEY=change_this_to_a_random_secure_key
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123

# TOTP & Geofence Defaults
SHARED_SECRET=JBSWY3DPEHPK3PXP
TOTP_INTERVAL=30
TIMEZONE=Asia/Kolkata
DEFAULT_GEOFENCE_RADIUS=100.0
```

---

## ▶️ Running the Application

Start the local server:
```bash
python app.py
```

Access the application in your browser:
- 📱 **Live Dynamic QR Display Screen**: [http://localhost:5000/](http://localhost:5000/)
- 📍 **Student Mobile Check-in Page**: [http://localhost:5000/checkin](http://localhost:5000/checkin)
- 🔐 **Admin Management Console**: [http://localhost:5000/admin/login](http://localhost:5000/admin/login)
  - Default Password: `admin123` *(configurable in `.env`)*

---

## 📊 Bulk Student Roster Import

To bulk-import students, navigate to **Admin Console -> Bulk Import** and upload a `.csv` file formatted as follows:

```csv
USN,Name,Department,Division,Semester,phone
4SF21CS001,Rahul Sharma,CSE,A,Sem 5,9876543210
4SF21CS002,Aisha Khan,ISE,B,Sem 5,9876543211
4SF21CS003,Imran Patel,AIML,A,Sem 3,9876543212
4SF21CS004,Sneha Rao,ECE,C,Sem 7,9876543213
4SF21CS005,Vikram Verma,MECH,A,Sem 1,9876543214
```

> **Note**: New departments, divisions, and semesters in the CSV will be automatically registered in the system during ingestion!

---

## 🧪 Running Automated Unit Tests

Execute the automated test suite to verify one-time attendance, check-in / check-out, anti-proxy binding, geofencing, and export generation:

```bash
# Run Core System Tests
python test_attendance_system.py

# Run Web Routes & API Tests
python test_web_routes.py
```

---

## 🛡️ Security Architecture Summary

1. **RFC 6238 TOTP Validation**: QR tokens rotate every 30 seconds with a strict 1-step window tolerance.
2. **Ray-Casting & Haversine Distance**: Exact distance calculations against active institutional perimeters.
3. **Hardware Anti-Proxy**: Cookies and LocalStorage persistent hardware UUIDs guarantee 1 device can only submit for 1 student per session.
4. **Password Hashing**: Secure PBKDF2/SHA256 password hashing replaces plain-text comparisons.
5. **Connection Management**: Scoped SQLAlchemy sessions automatically clean up and return connections to the pool on teardown.

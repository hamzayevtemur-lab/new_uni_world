# Uni World — Overseas Education Consulting & Student Portal Platform

Uni World is a comprehensive web platform for international educational consulting, student application tracking, lead management, and administrative CRM.

---

## 🌟 Key Features

### 🎓 Public Website (`/`)
- Interactive destination guides (UK, USA, Australia, Germany, Canada, South Korea, etc.)
- Program catalog & university search
- Educational consulting service overviews & consultation request form
- Student testimonials & news ticker announcements

### 👨‍🎓 Student Access & Verification (`/student`)
- **2-Step Email Verification (OTP)**: Students submit access requests with 6-digit email OTP verification before queuing for approval.
- **Admin-Controlled Credentials**: Access to the portal is invitation/approval-based. Credentials are provided to students upon admin review.
- **Personal Dossier Management**: Academic background, language scores, passport details.
- **Application Tracking Dashboard**: Real-time status updates on target university applications.
- **Document Vault**: Upload & manage passports, academic transcripts, diplomas, and language certificates.

### 📊 Admin CRM Dashboard (`/admin`)
- **Access Requests Management**: Review email-verified student access requests, approve student accounts, and dispatch login credentials automatically via email.
- **Student Leads & Dossier CRM**: Track student application pipelines, inspect uploaded student documents, and generate 1-click university portal auto-fill payloads.
- **Content Management System (CMS)**: Manage countries, partner universities, services, testimonials, and announcement tickers.

---

## 📁 Project Structure

```
uni-world/
├── backend/
│   ├── main.py                 # FastAPI core application & static asset mounts
│   ├── config.py               # Environment configuration & settings
│   ├── database.py             # PostgreSQL connection & auto-table schema migration
│   ├── auth.py                 # JWT token creation & auth dependencies
│   ├── schemas/                # Pydantic data schemas
│   └── routers/                # Modular APIRouters
│       ├── auth.py             # Admin login endpoint
│       ├── student.py          # Student auth, profile, applications & document endpoints
│       ├── crm.py              # Admin student & document CRM endpoints
│       ├── leads.py            # Public contact inquiries & lead tracking
│       ├── comments.py         # Testimonials & approval system
│       ├── news.py             # Announcement ticker management
│       ├── countries.py        # Study destination management
│       ├── services.py         # Consulting services management
│       └── universities.py     # Partner university catalog
├── frontend/
│   ├── index.html              # Main public landing page
│   ├── student.html            # Student Portal interface
│   ├── admin.html              # Administrative CRM dashboard
│   ├── homepage.js             # Frontend API integration & lead capture
│   └── homepage.css            # Responsive design styling
├── render.yaml                 # Deployment configuration for Render
└── Procfile                    # Web service process configuration
```

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.10+**
- **PostgreSQL** database (Local or hosted on [Neon.tech](https://neon.tech))

### Environment Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/hamzayevtemur-lab/new_uni_world.git
   cd new_uni_world
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install backend dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```

4. Configure environment variables in `.env`:
   ```env
   DATABASE_URL=postgresql://user:password@localhost:5432/uniworld
   JWT_SECRET=your_super_secret_key
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD_HASH=$2b$12$...
   PORT=4000
   ```

5. Run the application:
   ```bash
   python backend/main.py
   ```
   Access the app at `http://127.0.0.1:4000` (or configured `PORT`).

---

## 🌐 Deployment (Render + Neon PostgreSQL)

Refer to [`DEPLOY.md`](file:///Users/mac/Desktop/uni-world/DEPLOY.md) for detailed step-by-step instructions on deploying the FastAPI backend and static web pages on Render paired with a free PostgreSQL database on Neon.tech.

# Uni World — Clean Deployment Guide

## Final Project Structure
```
uni-world/                  ← your GitHub repo root
├── .gitignore              ← keeps venvs out of git
├── render.yaml             ← Render auto-config
├── Procfile                ← backup start command
├── backend/
│   ├── main.py             ← FastAPI app (PostgreSQL)
│   └── requirements.txt
└── frontend/
    ├── index.html
    ├── admin.html
    ├── homepage.js
    ├── homepage.css
    └── images/             ← copy your images folder here
```

---

## Step 1 — Clean your local project

Open a terminal in your project folder and run:

```bash
# Delete ALL old venv folders (safe — they can always be recreated)
rm -rf .venv venv myvenv myenv312

# Delete Python cache
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Optional: remove old backend folder if it exists
rm -rf uniworldbackend
```

Then copy the new files from this package into your project so it matches
the structure shown above.

---

## Step 2 — Create a FREE PostgreSQL database on Neon

1. Go to **https://neon.tech** and sign up (free — no credit card, no trial expiry)
2. Click **"New Project"** → give it a name like `uni-world`
3. Once created, click **"Connection Details"**
4. Copy the **Connection string** — it looks like:
   ```
   postgresql://user:password@ep-xxx.us-east-1.aws.neon.tech/neondb?sslmode=require
   ```
   Keep this — you'll paste it into Render next.

---

## Step 3 — Generate your admin password hash

Run this ONE TIME on your computer (requires Python + bcrypt installed):

```bash
pip install bcrypt
python -c "import bcrypt; print(bcrypt.hashpw(b'YOUR_PASSWORD_HERE', bcrypt.gensalt()).decode())"
```

Replace `YOUR_PASSWORD_HERE` with a strong password you'll remember.
Copy the output (starts with `$2b$12$...`).

---

## Step 4 — Push to GitHub

```bash
cd /path/to/uni-world

# If no git repo yet:
git init
git remote add origin https://github.com/YOUR_USERNAME/uni-world.git

# First commit:
git add .
git commit -m "Clean structure: PostgreSQL + JWT auth + news system"
git push -u origin main
```

The `.gitignore` will automatically exclude all venv folders.
**Verify** before pushing: `git status` should NOT show any venv/ folders.

---

## Step 5 — Deploy on Render

1. Go to **https://render.com** → your existing service (or create new Web Service)
2. Connect to your GitHub repo
3. Render will detect `render.yaml` automatically

Set these **Environment Variables** in Render dashboard:

| Key | Value |
|-----|-------|
| `DATABASE_URL` | The Neon connection string from Step 2 |
| `JWT_SECRET` | Any long random string (or let Render generate it) |
| `ADMIN_USERNAME` | Your chosen admin username |
| `ADMIN_PASSWORD_HASH` | The `$2b$12$...` hash from Step 3 |

Build command: `pip install -r backend/requirements.txt`
Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`

---

## Step 6 — Initialize the database

After Render finishes deploying, visit:
```
https://your-app.onrender.com/setup-db
```

You should see: `{"message": "Tables created successfully"}`

This creates the `comments` and `news` tables in Neon. You only need to do this once.

---

## Step 7 — Verify everything works

- [ ] Homepage loads: `https://your-app.onrender.com/`
- [ ] Admin login works: `https://your-app.onrender.com/admin`
- [ ] Credentials are checked server-side (not visible in browser DevTools)
- [ ] Create a test news announcement from admin panel
- [ ] Check it appears on homepage

---

## Notes

- **Neon free tier**: 0.5 GB storage, unlimited connections, no expiry ✅
- **Old Railway data**: If you had existing comments in Railway, you can export
  them with `pg_dump` and import into Neon with `psql` if needed.
- **Images**: Your `frontend/images/` folder is served as static files.
  Make sure to copy it into the new `frontend/` folder.

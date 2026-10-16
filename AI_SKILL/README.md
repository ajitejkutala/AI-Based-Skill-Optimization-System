# Workforce Skill Match 🚀

An AI-powered workforce intelligence and role matching web platform built with Flask, SQLAlchemy, and semantic similarity.

Optimized for instant, zero-config deployment on **Vercel**!

---

## 🚀 Deploying to Vercel (Step-by-Step)

This repository is pre-configured for Vercel Serverless Functions with:
- `vercel.json` (route rewrites to the Python function)
- `api/index.py` (WSGI serverless entrypoint)
- `requirements.txt` (lightweight dependencies under Vercel's 250 MB limit)
- Automatic fallback semantic matching (TF-IDF + NLP) that runs fast with zero memory bloat.

### 1. Push to GitHub
Commit and push your project to a GitHub repository:
```bash
git add .
git commit -m "Configure project for Vercel deployment"
git push origin main
```

### 2. Import into Vercel
1. Go to [vercel.com](https://vercel.com/) and sign in.
2. Click **Add New...** → **Project**.
3. Select your GitHub repository and click **Import**.
4. Leave **Framework Preset** as **Other**.
5. (Optional) Under **Environment Variables**, you can set:
   - `SECRET_KEY`: A secure random string for Flask sessions (e.g. `your-super-secret-key-123`).
   - `DATABASE_URL`: (Optional) A hosted PostgreSQL connection string (e.g. from [Neon.tech](https://neon.tech/) or [Supabase](https://supabase.com/)) if you want permanent database persistence across cold boots. If omitted, the app will use temporary SQLite in `/tmp`.
6. Click **Deploy**!

Vercel will install the dependencies, configure the serverless function, and give you a live production URL in under 60 seconds!

---

## 💻 Running Locally

```bash
# 1. Clone repository
git clone <your-repo-url>
cd AI_SKILL

# 2. Create virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start local Flask development server
python main.py
```

Open your browser at `http://127.0.0.1:5000`.

---

## 📁 Project Structure

```text
AI_SKILL/
├── api/
│   └── index.py            # Vercel serverless function entry point
├── instance/
│   └── workforce_...db     # Local SQLite database (git-ignored)
├── templates/
│   ├── base.html           # Main UI shell, theme toggle, styling
│   ├── dashboard.html      # Add employees & job descriptions
│   ├── employee_edit.html  # Edit existing employee details
│   ├── employee_login.html # Staff self-service login
│   ├── employee_portal.html# Staff career & skills dashboard
│   ├── role_match.html     # Semantic matching & gap recommendations
│   └── talent.html         # Talent directory & search
├── main.py                 # Flask application factory, routes & auth
├── models.py               # SQLAlchemy models (Employee, JobRole)
├── services.py             # NLP skill extraction & semantic fit engine
├── requirements.txt        # Production dependencies for Vercel
├── vercel.json             # Vercel routing configuration
└── README.md               # Documentation & deployment guide
```

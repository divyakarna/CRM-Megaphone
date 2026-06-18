# Podcaster CRM — AI Ko-Bato

A full-stack CRM for tracking YouTube podcaster outreach.  
**Stack:** Python Flask · PostgreSQL · Chart.js · Claude AI

---

## Project structure

```
podcaster_crm/
├── app.py              ← single entry point (Flask backend + all API routes)
├── requirements.txt
├── render.yaml         ← Render deployment config
└── templates/
    └── index.html      ← full frontend (HTML/CSS/JS, served by Flask)
```

---

## Run locally

### 1. Create a PostgreSQL database
```bash
createdb podcaster_crm
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set environment variables
```bash
export DATABASE_URL="postgresql://localhost/podcaster_crm"
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 4. Run
```bash
python app.py
```
Visit: http://localhost:5000

---

## Deploy to Render (free tier)

### Option A — Automatic (render.yaml)
1. Push this folder to a GitHub repo
2. Go to https://render.com → New → Blueprint
3. Connect your GitHub repo — Render reads `render.yaml` automatically
4. It will create both the web service AND the PostgreSQL database
5. Go to your web service → Environment → add `ANTHROPIC_API_KEY`
6. Deploy — done!

### Option B — Manual
1. Go to https://render.com
2. **Create PostgreSQL database:**
   - New → PostgreSQL
   - Name: `podcaster-crm-db`
   - Plan: Free
   - Copy the "Internal Database URL"

3. **Create Web Service:**
   - New → Web Service
   - Connect your GitHub repo
   - Runtime: Python 3
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 60`

4. **Environment variables** (in Render dashboard → Environment):
   ```
   DATABASE_URL = <paste the Internal Database URL from step 2>
   ANTHROPIC_API_KEY = sk-ant-...
   ```

5. Click **Deploy** — app goes live in ~2 minutes

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string (auto-set by render.yaml) |
| `ANTHROPIC_API_KEY` | Yes | Your Claude API key from console.anthropic.com |
| `PORT` | Auto | Set by Render automatically |

---

## API routes

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/` | Serves the frontend |
| GET | `/api/clients` | List all clients |
| POST | `/api/clients` | Add a client |
| PUT | `/api/clients/<id>` | Update a client |
| DELETE | `/api/clients/<id>` | Delete a client |
| GET | `/api/communications` | List all communications |
| POST | `/api/communications` | Log a communication |
| DELETE | `/api/communications/<id>` | Delete a communication |
| GET | `/api/stats` | Dashboard stats (charts data) |
| POST | `/api/ai` | Ask the AI assistant |

---

## Notes

- The database tables are created automatically on first run (`init_db()` in `app.py`)
- Sample data is seeded automatically if the database is empty
- The `postgres://` → `postgresql://` URL fix is handled automatically for Render

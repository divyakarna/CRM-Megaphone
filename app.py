import os
import json
from datetime import datetime, date
from flask import Flask, render_template, request, jsonify
import psycopg
from psycopg.rows import dict_row
import requests

app = Flask(__name__)

# ─── DATABASE ────────────────────────────────────────────────────────────────

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost/podcaster_crm")

# Render gives postgres:// but psycopg2 needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


def get_db():
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id          SERIAL PRIMARY KEY,
            channel     TEXT NOT NULL,
            host        TEXT,
            url         TEXT,
            email       TEXT,
            phone       TEXT,
            country     TEXT,
            theme       TEXT,
            subs        TEXT,
            status      TEXT DEFAULT 'To Reach Out',
            priority    TEXT DEFAULT 'Medium',
            followup    DATE,
            source      TEXT,
            description TEXT,
            notes       TEXT,
            added       DATE DEFAULT CURRENT_DATE,
            created_at  TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS communications (
            id          SERIAL PRIMARY KEY,
            client_id   INTEGER REFERENCES clients(id) ON DELETE CASCADE,
            type        TEXT,
            subject     TEXT,
            comm_date   DATE,
            status      TEXT,
            notes       TEXT,
            created_at  TIMESTAMP DEFAULT NOW()
        );
    """)
    # Seed sample data if empty
    cur.execute("SELECT COUNT(*) as cnt FROM clients")
    row = cur.fetchone()
    if row["cnt"] == 0:
        sample_clients = [
            ("The Knowledge Project", "Shane Parrish", "", "shane@fs.blog", "", "Canada",
             "Philosophy & Business", "450K", "Interested", "High", "2026-06-25",
             "YouTube search", "Deep dive interviews on decision making and mental models.",
             "Very aligned with AI education. Send demo deck."),
            ("Lex Fridman Podcast", "Lex Fridman", "", "", "", "USA",
             "Tech & AI", "4.2M", "To Reach Out", "High", "2026-06-20",
             "YouTube search", "Long-form conversations on AI, science and humanity.",
             "Try DM first. Massive reach."),
            ("Sanjiv Chaudhary Talks", "Sanjiv Chaudhary", "", "sanjiv@example.com",
             "+977 9800000001", "Nepal", "Entrepreneurship", "120K", "Onboarded",
             "Medium", None, "Referral", "Nepal-based business and startup conversations.",
             "First onboarded client! Great relationship."),
            ("Nepalaya Podcast", "Aashish Thapa", "", "nepalaya@gmail.com",
             "+977 9811111111", "Nepal", "Culture & Society", "85K", "In Talks",
             "High", "2026-06-22", "YouTube search",
             "Nepali language podcast about culture and society.",
             "Had a great call. Wants to see the AI Ko-Bato demo."),
            ("My First Million", "Sam Parr", "", "", "", "USA",
             "Business", "1.1M", "Contacted", "Medium", "2026-07-01",
             "Podcast directory", "Two entrepreneurs discussing business ideas.",
             "Sent intro email last week."),
            ("Startup Stories India", "Varun Agarwal", "", "varun@startup.in", "",
             "India", "Entrepreneurship", "320K", "Follow-up Needed", "High",
             "2026-06-19", "Referral", "Stories of Indian entrepreneurs.",
             "Warm intro — follow up ASAP."),
            ("Tech Burner", "Shlok Srivastava", "", "", "", "India",
             "Tech", "3.8M", "Not Interested", "Low", None,
             "YouTube", "Tech reviews and gadget unboxings.",
             "Said not a fit for now."),
        ]
        for c in sample_clients:
            cur.execute("""
                INSERT INTO clients
                  (channel,host,url,email,phone,country,theme,subs,status,priority,
                   followup,source,description,notes,added)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_DATE)
            """, c)

        cur.execute("SELECT id FROM clients ORDER BY id LIMIT 5")
        ids = [r["id"] for r in cur.fetchall()]
        if len(ids) >= 5:
            sample_comms = [
                (ids[2], "Email sent", "Partnership with AI Ko-Bato",
                 "2026-05-18", "Replied", "Sent initial proposal. Got positive response."),
                (ids[3], "Call", "Intro call about AI education collab",
                 "2026-06-10", "Replied", "Very positive. Wants to see the full deck."),
                (ids[4], "Email sent", "AI Ko-Bato intro email",
                 "2026-06-09", "No response", "Followed up once."),
            ]
            for cm in sample_comms:
                cur.execute("""
                    INSERT INTO communications (client_id,type,subject,comm_date,status,notes)
                    VALUES (%s,%s,%s,%s,%s,%s)
                """, cm)

    conn.commit()
    cur.close()
    conn.close()


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def serialize(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def rows_to_list(rows):
    return [dict(r) for r in rows]


# ─── API: CLIENTS ─────────────────────────────────────────────────────────────

@app.route("/api/clients", methods=["GET"])
def get_clients():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM clients ORDER BY created_at DESC")
    clients = rows_to_list(cur.fetchall())
    cur.close()
    conn.close()
    return jsonify(clients)


@app.route("/api/clients", methods=["POST"])
def create_client():
    data = request.json
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO clients
          (channel,host,url,email,phone,country,theme,subs,status,priority,
           followup,source,description,notes,added)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_DATE)
        RETURNING *
    """, (
        data.get("channel"), data.get("host"), data.get("url"),
        data.get("email"), data.get("phone"), data.get("country"),
        data.get("theme"), data.get("subs"), data.get("status", "To Reach Out"),
        data.get("priority", "Medium"),
        data.get("followup") or None,
        data.get("source"), data.get("description"), data.get("notes")
    ))
    client = dict(cur.fetchone())
    conn.commit()
    cur.close()
    conn.close()
    return jsonify(client), 201


@app.route("/api/clients/<int:client_id>", methods=["PUT"])
def update_client(client_id):
    data = request.json
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE clients SET
          channel=%s,host=%s,url=%s,email=%s,phone=%s,country=%s,theme=%s,
          subs=%s,status=%s,priority=%s,followup=%s,source=%s,description=%s,notes=%s
        WHERE id=%s RETURNING *
    """, (
        data.get("channel"), data.get("host"), data.get("url"),
        data.get("email"), data.get("phone"), data.get("country"),
        data.get("theme"), data.get("subs"), data.get("status"),
        data.get("priority"),
        data.get("followup") or None,
        data.get("source"), data.get("description"), data.get("notes"),
        client_id
    ))
    client = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if not client:
        return jsonify({"error": "Not found"}), 404
    return jsonify(dict(client))


@app.route("/api/clients/<int:client_id>", methods=["DELETE"])
def delete_client(client_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM clients WHERE id=%s", (client_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"ok": True})


# ─── API: COMMUNICATIONS ──────────────────────────────────────────────────────

@app.route("/api/communications", methods=["GET"])
def get_communications():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.*, cl.channel as client_channel
        FROM communications c
        LEFT JOIN clients cl ON c.client_id = cl.id
        ORDER BY c.created_at DESC
    """)
    comms = rows_to_list(cur.fetchall())
    cur.close()
    conn.close()
    return jsonify(comms)


@app.route("/api/communications", methods=["POST"])
def create_communication():
    data = request.json
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO communications (client_id,type,subject,comm_date,status,notes)
        VALUES (%s,%s,%s,%s,%s,%s) RETURNING *
    """, (
        data.get("client_id"), data.get("type"), data.get("subject"),
        data.get("comm_date") or None, data.get("status"), data.get("notes")
    ))
    comm = dict(cur.fetchone())
    conn.commit()
    cur.close()
    conn.close()
    return jsonify(comm), 201


@app.route("/api/communications/<int:comm_id>", methods=["DELETE"])
def delete_communication(comm_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM communications WHERE id=%s", (comm_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"ok": True})


# ─── API: STATS (for dashboard charts) ───────────────────────────────────────

@app.route("/api/stats", methods=["GET"])
def get_stats():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT status, COUNT(*) as count FROM clients GROUP BY status
    """)
    status_counts = {r["status"]: r["count"] for r in cur.fetchall()}

    cur.execute("""
        SELECT country, COUNT(*) as count FROM clients
        WHERE country IS NOT NULL AND country != ''
        GROUP BY country ORDER BY count DESC LIMIT 8
    """)
    country_counts = rows_to_list(cur.fetchall())

    cur.execute("""
        SELECT theme, COUNT(*) as count FROM clients
        WHERE theme IS NOT NULL AND theme != ''
        GROUP BY theme ORDER BY count DESC LIMIT 8
    """)
    theme_counts = rows_to_list(cur.fetchall())

    cur.execute("""
        SELECT TO_CHAR(DATE_TRUNC('month', added), 'Mon YY') as month,
               COUNT(*) as count
        FROM clients
        WHERE added >= CURRENT_DATE - INTERVAL '6 months'
        GROUP BY DATE_TRUNC('month', added)
        ORDER BY DATE_TRUNC('month', added)
    """)
    monthly = rows_to_list(cur.fetchall())

    cur.execute("SELECT COUNT(*) as total FROM clients")
    total = cur.fetchone()["total"]

    cur.execute("SELECT COUNT(*) as total FROM communications")
    total_comms = cur.fetchone()["total"]

    cur.close()
    conn.close()

    return jsonify({
        "status_counts": status_counts,
        "country_counts": country_counts,
        "theme_counts": theme_counts,
        "monthly": monthly,
        "total": total,
        "total_comms": total_comms,
    })


# ─── API: AI ASSISTANT ────────────────────────────────────────────────────────

@app.route("/api/ai", methods=["POST"])
def ai_assistant():
    data = request.json
    question = data.get("question", "")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM clients ORDER BY created_at DESC")
    clients = rows_to_list(cur.fetchall())
    cur.execute("""
        SELECT c.*, cl.channel as client_channel
        FROM communications c LEFT JOIN clients cl ON c.client_id = cl.id
        ORDER BY c.created_at DESC LIMIT 30
    """)
    comms = rows_to_list(cur.fetchall())
    cur.close()
    conn.close()

    def fmt_date(v):
        return v.isoformat() if isinstance(v, (datetime, date)) else str(v or "N/A")

    client_lines = "\n".join([
        f"- {c['channel']} | Host: {c['host'] or 'N/A'} | Country: {c['country'] or 'N/A'} "
        f"| Theme: {c['theme'] or 'N/A'} | Subs: {c['subs'] or 'N/A'} "
        f"| Status: {c['status']} | Priority: {c['priority']} "
        f"| Email: {c['email'] or 'N/A'} | Follow-up: {fmt_date(c['followup'])} "
        f"| Notes: {c['notes'] or 'None'}"
        for c in clients
    ])
    comm_lines = "\n".join([
        f"- {c['client_channel']}: {c['type']} on {fmt_date(c['comm_date'])} | "
        f"Subject: {c['subject']} | Status: {c['status']} | Notes: {c['notes'] or 'None'}"
        for c in comms
    ])

    system_prompt = f"""You are an AI assistant for a YouTube podcaster outreach CRM called "Podcaster CRM", built for AI Ko-Bato — an AI education venture in Nepal run by Divya through MindMine Pvt. Ltd. AI Ko-Bato teaches AI tools to Nepali school and college students (Grades 8–12).

The CRM tracks YouTube podcasters as potential collaboration and sponsorship partners.

CLIENTS ({len(clients)} total):
{client_lines}

RECENT COMMUNICATIONS ({len(comms)}):
{comm_lines}

Be concise, specific, and actionable. Use the real data above when answering. When drafting emails, make them warm and professional, referencing the specific podcaster's channel theme. Always respond in plain text (no markdown formatting like ** or ##)."""

    if not ANTHROPIC_API_KEY:
        return jsonify({"response": "AI assistant is not configured. Please set the ANTHROPIC_API_KEY environment variable on Render."}), 200

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 1000,
                "system": system_prompt,
                "messages": [{"role": "user", "content": question}],
            },
            timeout=30,
        )
        result = resp.json()
        answer = result["content"][0]["text"]
        return jsonify({"response": answer})
    except Exception as e:
        return jsonify({"response": f"AI error: {str(e)}"}), 500


# ─── FRONTEND ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ─── BOOT ─────────────────────────────────────────────────────────────────────

# Always init DB on startup (works with python app.py, flask run, and gunicorn)
with app.app_context():
    init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
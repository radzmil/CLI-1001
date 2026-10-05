"""Read-only LeeA client dashboard, scoped to the Architech Systems tenant."""
import hmac
import os
from datetime import datetime, timedelta, timezone
import re

import psycopg2
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from chat_ticket import issue

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=os.environ.get("LOCAL_HTTP") != "1")

TENANT = "architechsystems"
DEFAULT_PORTAL_PASSWORD = "defaultpass123"


@app.after_request
def security_headers(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


@app.before_request
def protect_posts():
    if request.method == "POST":
        origin = request.headers.get("Origin")
        if origin and origin != request.host_url.rstrip("/"):
            return jsonify(error="Asal permintaan tidak dibenarkan."), 403


def configured():
    return bool(app.secret_key)


@app.get("/")
def index():
    if not configured():
        return render_template("login.html", error="Konfigurasi keselamatan portal belum lengkap."), 503
    if not session.get("authenticated"):
        return render_template("login.html")
    return render_template("dashboard.html")


@app.post("/login")
def login():
    if not configured():
        return render_template("login.html", error="Konfigurasi keselamatan portal belum lengkap."), 503
    password = os.environ.get("PORTAL_PASSWORD") or DEFAULT_PORTAL_PASSWORD
    if not hmac.compare_digest(request.form.get("password", ""), password):
        return render_template("login.html", error="Kata laluan tidak tepat."), 401
    session.clear()
    session["authenticated"] = True
    return redirect(url_for("index"))


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


def tenant_id(cursor):
    cursor.execute("SELECT id FROM clients WHERE username = %s", (TENANT,))
    row = cursor.fetchone()
    return row[0] if row else None


@app.post("/api/contacts")
def save_contact():
    if not configured() or not session.get("authenticated"):
        return jsonify(error="Sila log masuk dahulu."), 401
    data = request.get_json(silent=True) or {}
    phone = str(data.get("phone", "")).strip()
    name = str(data.get("name", "")).strip()
    if not re.fullmatch(r"\+?[0-9]{5,50}", phone) or not name or len(name) > 150:
        return jsonify(error="Nombor atau nama tidak sah."), 400
    url = os.environ.get("DATABASE_URL")
    if not url:
        return jsonify(error="Pangkalan data belum dikonfigurasi."), 503
    try:
        with psycopg2.connect(url, connect_timeout=5) as conn:
            with conn.cursor() as cursor:
                client_id = tenant_id(cursor)
                if client_id is None:
                    return jsonify(error="Rekod LeeA belum tersedia."), 503
                cursor.execute("SELECT 1 FROM messages WHERE client_id = %s AND prospect_phone = %s LIMIT 1",
                               (client_id, phone))
                if cursor.fetchone() is None:
                    return jsonify(error="Prospek belum mempunyai perbualan."), 404
                cursor.execute("""INSERT INTO prospect_contacts (client_id, phone, name, source)
                    VALUES (%s, %s, %s, 'manual') ON CONFLICT (client_id, phone)
                    DO UPDATE SET name = EXCLUDED.name, source = 'manual', updated_at = NOW()""",
                    (client_id, phone, name))
        return jsonify(phone=phone, name=name, source="manual")
    except psycopg2.Error:
        app.logger.exception("Gagal menyimpan phone book")
        return jsonify(error="Phone book tidak tersedia. Semak migrasi database."), 503


@app.get("/api/analytics")
def analytics():
    """Read-only WhatsApp activity derived from this tenant's stored messages."""
    if not configured() or not session.get("authenticated"):
        return jsonify(error="Sila log masuk dahulu."), 401
    url = os.environ.get("DATABASE_URL")
    if not url:
        return jsonify(error="Pangkalan data belum dikonfigurasi."), 503
    try:
        with psycopg2.connect(url, connect_timeout=5) as conn:
            with conn.cursor() as cursor:
                client_id = tenant_id(cursor)
                if client_id is None:
                    return jsonify(error="Rekod LeeA belum tersedia."), 503
                cursor.execute(
                    "SELECT prospect_phone, sender, timestamp FROM messages "
                    "WHERE client_id = %s AND prospect_phone IS NOT NULL "
                    "AND prospect_phone <> '' ORDER BY id",
                    (client_id,),
                )
                rows = cursor.fetchall()
    except psycopg2.Error:
        app.logger.exception("Gagal membaca analisis WhatsApp")
        return jsonify(error="Analisis WhatsApp tidak tersedia."), 503

    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=6)
    days = { (start + timedelta(days=i)).isoformat(): 0 for i in range(7) }
    prospects = {}
    inbound = outbound = active = 0
    for phone, sender, timestamp in rows:
        item = prospects.setdefault(phone, {"phone": phone, "incoming": 0,
                                            "replies": 0, "last_activity": ""})
        if sender == phone:
            inbound += 1
            item["incoming"] += 1
        else:
            outbound += 1
            item["replies"] += 1
        if timestamp:
            moment = timestamp.replace(tzinfo=timezone.utc) if timestamp.tzinfo is None else timestamp
            date = moment.astimezone(timezone.utc).date().isoformat()
            if date in days:
                days[date] += 1
                active += 1
            value = moment.isoformat()
            if value > item["last_activity"]:
                item["last_activity"] = value
    top = sorted(prospects.values(), key=lambda item: (-item["incoming"], item["phone"]))[:10]
    return jsonify(prospects=len(prospects), incoming=inbound, replies=outbound,
                   messages_7d=active, daily=[{"date": day, "messages": count}
                                              for day, count in days.items()], top_leads=top,
                   as_of=datetime.now(timezone.utc).isoformat())


@app.get("/api/chat-ticket")
def chat_ticket():
    if not configured() or not session.get("authenticated"):
        return jsonify(error="Sila log masuk dahulu."), 401
    secret = os.environ.get("CHAT_SOCKET_SECRET", "")
    endpoint = os.environ.get("CHAT_SOCKET_URL", "")
    local_socket = (os.environ.get("LOCAL_HTTP") == "1" and
                    endpoint in ("ws://127.0.0.1:5000/ws/chat", "ws://localhost:5000/ws/chat"))
    if len(secret) < 32 or not (endpoint.startswith("wss://") or local_socket):
        return jsonify(error="Sambungan langsung belum dikonfigurasi."), 503
    return jsonify(url=endpoint, ticket=issue(secret, TENANT))


@app.get("/api/leads")
def leads():
    if not configured() or not session.get("authenticated"):
        return jsonify(error="Sila log masuk dahulu."), 401
    url = os.environ.get("DATABASE_URL")
    if not url:
        return jsonify(error="Pangkalan data belum dikonfigurasi."), 503
    try:
        with psycopg2.connect(url, connect_timeout=5) as conn:
            with conn.cursor() as cursor:
                client_id = tenant_id(cursor)
                if client_id is None:
                    return jsonify(error="Rekod LeeA belum tersedia."), 503
                cursor.execute(
                    "SELECT recent.prospect_phone, contact.name, contact.source FROM "
                    "(SELECT prospect_phone, MAX(id) AS last_id FROM messages "
                    "WHERE client_id = %s AND prospect_phone IS NOT NULL "
                    "GROUP BY prospect_phone ORDER BY last_id DESC LIMIT 200) recent "
                    "LEFT JOIN prospect_contacts contact ON contact.client_id = %s "
                    "AND contact.phone = recent.prospect_phone ORDER BY recent.last_id DESC",
                    (client_id, client_id),
                )
                return jsonify([{"phone": phone, "name": name or "", "source": source or ""}
                                for phone, name, source in cursor.fetchall()])
    except psycopg2.Error:
        app.logger.exception("Gagal membaca senarai prospek")
        return jsonify(error="Senarai prospek tidak tersedia."), 503


@app.get("/api/history")
def history():
    if not configured() or not session.get("authenticated"):
        return jsonify(error="Sila log masuk dahulu."), 401
    phone = request.args.get("phone", "")
    if not phone or len(phone) > 50 or not phone.lstrip("+").isdigit():
        return jsonify(error="Nombor prospek tidak sah."), 400
    url = os.environ.get("DATABASE_URL")
    if not url:
        return jsonify(error="Pangkalan data belum dikonfigurasi."), 503
    try:
        with psycopg2.connect(url, connect_timeout=5) as conn:
            with conn.cursor() as cursor:
                client_id = tenant_id(cursor)
                if client_id is None:
                    return jsonify(error="Rekod LeeA belum tersedia."), 503
                cursor.execute(
                    "SELECT sender, message, timestamp FROM "
                    "(SELECT id, sender, message, timestamp FROM messages "
                    "WHERE client_id = %s AND prospect_phone = %s "
                    "ORDER BY id DESC LIMIT 100) recent ORDER BY id ASC",
                    (client_id, phone),
                )
                return jsonify([{"sender": "customer" if sender == phone else "agent",
                                 "text": message,
                                 "time": timestamp.isoformat() if timestamp else ""}
                                for sender, message, timestamp in cursor.fetchall()])
    except psycopg2.Error:
        app.logger.exception("Gagal membaca sejarah perbualan")
        return jsonify(error="Sejarah perbualan tidak tersedia."), 503


if __name__ == "__main__":
    app.run(debug=False)
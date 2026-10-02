"""Read-only LeeA client dashboard, scoped to the Architech Systems tenant."""
import hmac
import os

import psycopg2
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from chat_ticket import issue

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=os.environ.get("LOCAL_HTTP") != "1")

TENANT = "architechsystems"


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
    return bool(app.secret_key and os.environ.get("PORTAL_PASSWORD"))


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
    if not hmac.compare_digest(request.form.get("password", ""), os.environ["PORTAL_PASSWORD"]):
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
                    "SELECT prospect_phone, MAX(id) FROM messages "
                    "WHERE client_id = %s AND prospect_phone IS NOT NULL "
                    "GROUP BY prospect_phone ORDER BY MAX(id) DESC LIMIT 200",
                    (client_id,),
                )
                return jsonify([{"phone": phone} for phone, _ in cursor.fetchall()])
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
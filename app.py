"""LeeA client dashboard, scoped to the configured tenant."""
import hmac
import os
from datetime import datetime, timedelta, timezone
import re

import psycopg2
from flask import Flask, jsonify, redirect, render_template, request, session, url_for, Response
from werkzeug.security import check_password_hash, generate_password_hash
from chat_ticket import issue

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=os.environ.get("LOCAL_HTTP") != "1")

TENANT = os.environ.get("CLIENT_USERNAME", "architechsystems").strip()


def client_context():
    """Deployment-specific identity; database primary keys are never business IDs."""
    return {"client_name": os.environ.get("CLIENT_NAME", "").strip() or TENANT,
            "client_code": os.environ.get("CLIENT_CODE", "CLI-1001").strip(),
            "client_logo": os.environ.get("CLIENT_LOGO_URL", "").strip() or "/static/logo.png"}


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
        return render_template("login.html", error="Konfigurasi keselamatan portal belum lengkap.", **client_context()), 503
    if not authenticated():
        return render_template("login.html", **client_context())
    return render_template("dashboard.html", **client_context())


@app.post("/login")
def login():
    session.clear()
    if not configured():
        return render_template("login.html", error="Konfigurasi keselamatan portal belum lengkap.", **client_context()), 503
    if request.form.get("username", "").strip() != TENANT:
        return render_template("login.html", error="Maklumat log masuk tidak tepat.", **client_context()), 401
    url = os.environ.get("DATABASE_URL")
    if not url:
        return render_template("login.html", error="Pangkalan data belum dikonfigurasi.", **client_context()), 503
    try:
        with psycopg2.connect(url, connect_timeout=5) as conn:
            with conn.cursor() as cursor:
                client_id = tenant_id(cursor)
                cursor.execute("SELECT portal_password_hash FROM clients WHERE id = %s AND username = %s",
                               (client_id, TENANT))
                row = cursor.fetchone()
    except psycopg2.Error:
        app.logger.exception("Gagal mengesahkan tenant portal")
        return render_template("login.html", error="Pangkalan data tidak tersedia.", **client_context()), 503
    if client_id is None:
        return render_template("login.html", error="Rekod klien tidak tersedia.", **client_context()), 503
    stored = row[0] if row else None
    supplied = request.form.get("password", "")
    valid = (check_password_hash(stored, supplied) if stored else
             bool(os.environ.get("PORTAL_PASSWORD")) and
             hmac.compare_digest(supplied, os.environ["PORTAL_PASSWORD"]))
    if not valid:
        return render_template("login.html", error="Maklumat log masuk tidak tepat.", **client_context()), 401
    session.clear()
    session["authenticated"] = True
    session["client_id"] = client_id
    session["username"] = TENANT
    return redirect(url_for("index"))


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


def tenant_id(cursor):
    cursor.execute("SELECT id FROM clients WHERE username = %s", (TENANT,))
    row = cursor.fetchone()
    return row[0] if row else None


def authenticated():
    return (configured() and session.get("authenticated") is True and
            session.get("username") == TENANT and isinstance(session.get("client_id"), int))


@app.route("/api/bot-profile", methods=["GET", "POST"])
def bot_profile():
    if not authenticated():
        return jsonify(error="Sila log masuk dahulu."), 401
    if request.method == "POST":
        data = request.get_json(silent=True)
        name = data.get("bot_name") if isinstance(data, dict) else None
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
            return jsonify(error="Nama bot mesti antara 1 hingga 100 aksara."), 400
    url = os.environ.get("DATABASE_URL")
    if not url:
        return jsonify(error="Pangkalan data belum dikonfigurasi."), 503
    try:
        with psycopg2.connect(url, connect_timeout=5) as conn:
            with conn.cursor() as cursor:
                if tenant_id(cursor) != session["client_id"]:
                    return jsonify(error="Rekod klien tidak tersedia."), 503
                if request.method == "POST":
                    cursor.execute("UPDATE clients SET bot_name = %s WHERE id = %s",
                                   (name.strip(), session["client_id"]))
                    return jsonify(success=True)
                cursor.execute("SELECT bot_name, bot_status, display_name FROM clients WHERE id = %s AND username = %s",
                               (session["client_id"], TENANT))
                row = cursor.fetchone()
                if row is None:
                    return jsonify(error="Rekod klien tidak tersedia."), 404
                return jsonify(bot_name=row[0], status=row[1], display_name=row[2],
                               phone_number=None, storage_used_mb=None, storage_max_mb=None)
    except psycopg2.Error:
        app.logger.exception("Gagal mengakses profil bot")
        return jsonify(error="Profil bot tidak tersedia. Semak migrasi pangkalan data."), 503


@app.get("/api/token-usage")
def token_usage():
    if not authenticated():
        return jsonify(error="Sila log masuk dahulu."), 401
    url = os.environ.get("DATABASE_URL")
    if not url:
        return jsonify(error="Pangkalan data belum dikonfigurasi."), 503
    try:
        with psycopg2.connect(url, connect_timeout=5) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT ai_token_balance, ai_token_quota, meta_token_balance, "
                               "meta_token_quota, subscription_end FROM clients "
                               "WHERE id = %s AND username = %s", (session["client_id"], TENANT))
                row = cursor.fetchone()
        if row is None:
            return jsonify(error="Rekod klien tidak tersedia."), 404
        def quota_info(balance, quota):
            used = max(0, quota - balance) if balance is not None and quota is not None else None
            percent = round(balance / quota * 100, 1) if balance is not None and quota and quota > 0 else None
            return dict(balance=balance, quota=quota, used=used, percent=percent)
        return jsonify(ai=quota_info(row[0], row[1]), meta=quota_info(row[2], row[3]),
                       renewal_date=row[4].isoformat() if row[4] else None)
    except psycopg2.Error:
        app.logger.exception("Gagal membaca penggunaan token")
        return jsonify(error="Penggunaan token tidak tersedia."), 503


@app.post("/api/profile/logo")
def upload_logo():
    if not authenticated():
        return jsonify(error="Sila log masuk dahulu."), 401
    image = request.files.get("logo")
    if not image or image.mimetype not in ("image/png", "image/jpeg", "image/webp", "image/gif"):
        return jsonify(error="Pilih imej PNG, JPEG, WebP atau GIF."), 400
    data = image.read(2 * 1024 * 1024 + 1)
    signatures = {"image/png": data.startswith(b"\x89PNG\r\n\x1a\n"),
                  "image/jpeg": data.startswith(b"\xff\xd8\xff"),
                  "image/webp": data.startswith(b"RIFF") and data[8:12] == b"WEBP",
                  "image/gif": data.startswith((b"GIF87a", b"GIF89a"))}
    if not data or len(data) > 2 * 1024 * 1024 or not signatures[image.mimetype]:
        return jsonify(error="Imej tidak sah atau melebihi 2 MB."), 400
    try:
        with psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=5) as conn:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE clients SET logo_data = %s, logo_mime = %s WHERE id = %s AND username = %s",
                               (psycopg2.Binary(data), image.mimetype, session["client_id"], TENANT))
                if cursor.rowcount != 1:
                    return jsonify(error="Rekod klien tidak tersedia."), 404
        return jsonify(success=True, logo_url="/api/profile/logo")
    except (psycopg2.Error, KeyError):
        app.logger.exception("Gagal menyimpan logo")
        return jsonify(error="Storan logo tidak tersedia."), 503


@app.get("/api/profile/logo")
def get_logo():
    if not authenticated():
        return jsonify(error="Sila log masuk dahulu."), 401
    try:
        with psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=5) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT logo_data, logo_mime FROM clients WHERE id = %s AND username = %s",
                               (session["client_id"], TENANT))
                row = cursor.fetchone()
        if not row or not row[0]:
            return jsonify(error="Logo belum tersedia."), 404
        return Response(bytes(row[0]), mimetype=row[1])
    except (psycopg2.Error, KeyError):
        return jsonify(error="Logo tidak tersedia."), 503


@app.get("/api/profile/company")
def company_profile():
    if not authenticated():
        return jsonify(error="Sila log masuk dahulu."), 401
    try:
        with psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=5) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT display_name, email, logo_data FROM clients WHERE id = %s AND username = %s",
                               (session["client_id"], TENANT))
                row = cursor.fetchone()
        if not row:
            return jsonify(error="Rekod klien tidak tersedia."), 404
        return jsonify(display_name=row[0] or client_context()["client_name"], email=row[1] or "",
                       logo_url="/api/profile/logo" if row[2] else client_context()["client_logo"])
    except (psycopg2.Error, KeyError):
        return jsonify(error="Profil syarikat tidak tersedia."), 503


@app.post("/api/profile/password")
def change_password():
    if not authenticated():
        return jsonify(error="Sila log masuk dahulu."), 401
    data = request.get_json(silent=True) or {}
    current, new = data.get("current_password"), data.get("new_password")
    if not isinstance(current, str) or not isinstance(new, str) or len(new) < 12 or len(new) > 256 or new != data.get("confirm_password"):
        return jsonify(error="Kata laluan baharu mesti 12–256 aksara dan pengesahan mesti sepadan."), 400
    try:
        with psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=5) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT portal_password_hash FROM clients WHERE id = %s AND username = %s FOR UPDATE",
                               (session["client_id"], TENANT))
                row = cursor.fetchone()
                if not row:
                    return jsonify(error="Rekod klien tidak tersedia."), 404
                valid = (check_password_hash(row[0], current) if row[0] else
                         bool(os.environ.get("PORTAL_PASSWORD")) and hmac.compare_digest(current, os.environ["PORTAL_PASSWORD"]))
                if not valid:
                    return jsonify(error="Kata laluan semasa tidak tepat."), 400
                cursor.execute("UPDATE clients SET portal_password_hash = %s WHERE id = %s AND username = %s",
                               (generate_password_hash(new), session["client_id"], TENANT))
        return jsonify(success=True)
    except (psycopg2.Error, KeyError):
        return jsonify(error="Kata laluan tidak dapat disimpan."), 503


@app.post("/api/profile/company")
def update_company():
    if not authenticated():
        return jsonify(error="Sila log masuk dahulu."), 401
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="JSON tidak sah."), 400
    name, email = data.get("display_name"), data.get("email")
    if (not isinstance(name, str) or not name.strip() or len(name.strip()) > 150 or
            not isinstance(email, str) or len(email) > 254 or
            not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email)):
        return jsonify(error="Nama syarikat atau e-mel tidak sah."), 400
    url = os.environ.get("DATABASE_URL")
    if not url:
        return jsonify(error="Pangkalan data belum dikonfigurasi."), 503
    try:
        with psycopg2.connect(url, connect_timeout=5) as conn:
            with conn.cursor() as cursor:
                if tenant_id(cursor) != session["client_id"]:
                    return jsonify(error="Rekod klien tidak tersedia."), 503
                cursor.execute("UPDATE clients SET display_name = %s, email = %s WHERE id = %s AND username = %s",
                               (name.strip(), email, session["client_id"], TENANT))
                return jsonify(success=True)
    except psycopg2.Error:
        app.logger.exception("Gagal mengemas kini profil syarikat")
        return jsonify(error="Profil syarikat tidak tersedia. Semak migrasi pangkalan data."), 503


@app.get("/api/subscription")
def subscription():
    if not authenticated():
        return jsonify(error="Sila log masuk dahulu."), 401
    url = os.environ.get("DATABASE_URL")
    if not url:
        return jsonify(error="Pangkalan data belum dikonfigurasi."), 503
    try:
        with psycopg2.connect(url, connect_timeout=5) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT plan, subscription_end, subscription_status, ai_token_quota "
                               "FROM clients WHERE id = %s AND username = %s",
                               (session["client_id"], TENANT))
                row = cursor.fetchone()
        if row is None:
            return jsonify(error="Rekod klien tidak tersedia."), 404
        return jsonify(plan=row[0], renewal_date=row[1].isoformat() if row[1] else None,
                       status=row[2], token_quota=row[3], price_rm=None, start_date=None)
    except psycopg2.Error:
        app.logger.exception("Gagal membaca langganan")
        return jsonify(error="Langganan tidak tersedia."), 503


@app.post("/api/contacts")
def save_contact():
    if not authenticated():
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
    if not authenticated():
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
    return jsonify(source="messages", prospects=len(prospects), incoming=inbound, replies=outbound,
                   messages_7d=active, daily=[{"date": day, "messages": count}
                                              for day, count in days.items()], top_leads=top,
                   as_of=datetime.now(timezone.utc).isoformat())


@app.get("/api/chat-ticket")
def chat_ticket():
    if not authenticated():
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
    if not authenticated():
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
    if not authenticated():
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


@app.route("/api/chat-mode", methods=["GET", "POST"])
def chat_mode():
    if not authenticated():
        return jsonify(error="Sila log masuk dahulu."), 401
    data = request.get_json(silent=True) if request.method == "POST" else request.args
    if not data or not isinstance(data.get("phone"), str):
        return jsonify(error="Nombor prospek tidak sah."), 400
    phone = data["phone"]
    if not re.fullmatch(r"\+?[0-9]{5,50}", phone):
        return jsonify(error="Nombor prospek tidak sah."), 400
    mode = data.get("mode")
    if request.method == "POST" and mode not in ("ai", "human"):
        return jsonify(error="Mod perbualan tidak sah."), 400
    url = os.environ.get("DATABASE_URL")
    if not url:
        return jsonify(error="Pangkalan data belum dikonfigurasi."), 503
    try:
        with psycopg2.connect(url, connect_timeout=5) as conn:
            with conn.cursor() as cursor:
                client_id = tenant_id(cursor)
                if client_id is None or client_id != session["client_id"]:
                    return jsonify(error="Rekod klien tidak tersedia."), 403
                cursor.execute("SELECT 1 FROM messages WHERE client_id = %s AND prospect_phone = %s LIMIT 1",
                               (client_id, phone))
                if cursor.fetchone() is None:
                    return jsonify(error="Prospek belum mempunyai perbualan."), 404
                if request.method == "POST":
                    cursor.execute("""INSERT INTO chat_modes (client_id, phone, mode)
                        VALUES (%s, %s, %s) ON CONFLICT (client_id, phone)
                        DO UPDATE SET mode = EXCLUDED.mode, updated_at = NOW()""",
                        (client_id, phone, mode))
                else:
                    cursor.execute("SELECT mode FROM chat_modes WHERE client_id = %s AND phone = %s",
                                   (client_id, phone))
                    row = cursor.fetchone()
                    mode = row[0] if row else "ai"
        return jsonify(phone=phone, mode=mode)
    except psycopg2.Error:
        app.logger.exception("Gagal membaca atau menyimpan mod perbualan")
        return jsonify(error="Mod perbualan tidak tersedia. Semak migrasi chat_modes."), 503


if __name__ == "__main__":
    app.run(debug=False)
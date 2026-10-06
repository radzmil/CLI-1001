import os
import unittest
from html.parser import HTMLParser
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import app as portal


class DashboardStructure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.panels = {}
        self.errors = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'section' and attrs.get('id', '').startswith('tab-'):
            if any(item[1] and item[1].startswith('tab-') for item in self.stack):
                self.errors.append('Nested dashboard panels')
            self.panels[attrs['id']] = attrs.get('hidden') is not None or 'hidden' in attrs
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
                       'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.stack.append((tag, attrs.get('id')))

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1][0] != tag:
            self.errors.append('Unexpected closing tag: ' + tag)
        else:
            self.stack.pop()


class PortalTest(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"PORTAL_PASSWORD": "test-only", "DATABASE_URL": "postgresql://example.invalid/db"})
        self.env.start()
        portal.app.secret_key = "test-secret-only"
        self.client = portal.app.test_client()

    def tearDown(self):
        self.env.stop()

    def login(self, password="test-only", username="architechsystems", client_id=42):
        cursor = MagicMock()
        cursor.fetchone.return_value = (client_id,) if client_id is not None else None
        connection = MagicMock()
        connection.__enter__.return_value.cursor.return_value.__enter__.return_value = cursor
        with patch.object(portal.psycopg2, "connect", return_value=connection):
            return self.client.post("/login", data={"username": username, "password": password})

    def test_login_required(self):
        self.assertEqual(self.client.get("/api/analytics").status_code, 401)
        self.assertEqual(self.client.get("/api/chat-ticket").status_code, 401)
        self.assertEqual(self.client.get("/api/leads").status_code, 401)
        self.assertEqual(self.client.get("/api/history?phone=60123456789").status_code, 401)
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertNotIn(b"/api/leads", self.client.get("/").data)

    def test_deployment_identity_is_rendered_without_changing_tenant_scope(self):
        with patch.dict(os.environ, {"CLIENT_NAME": "Syarikat Demo", "CLIENT_CODE": "CLI-1007",
                                  "CLIENT_LOGO_URL": "https://example.org/logo.png"}):
            page = self.client.get("/").data.decode("utf-8")
            self.assertIn("Syarikat Demo", page)
            self.assertIn("CLI-1007", page)
            self.assertIn("https://example.org/logo.png", page)
            self.login()
            dashboard = self.client.get("/").data.decode("utf-8")
            self.assertIn("Syarikat Demo", dashboard)
            self.assertIn("CLI-1007", dashboard)

    def test_dashboard_has_categorized_navigation_and_panels(self):
        self.login()
        html = self.client.get("/").data.decode("utf-8")
        for tab in ('control-center', 'phonebook', 'bot-profile', 'token-usage', 'settings'):
            self.assertIn('href="#' + tab + '"', html)
            self.assertIn('id="tab-' + tab + '"', html)
        for category in ('WORKSPACE', 'BOT &amp; AI', 'AKAUN'):
            self.assertIn(category, html)
        self.assertIn('id="contact-form"', html)
        for marker in ('phonebook-table', 'contact-prev', 'contact-next', 'contact-empty'):
            self.assertIn(marker, html)
        self.assertIn('id="analytics"', html)
        self.assertIn('id="whatsapp-leads"', html)
        self.assertIn('id="metric-prospects"', html)
        self.assertIn('id="top-leads"', html)
        self.assertIn('class="stats-grid"', html)
        self.assertIn('class="two-column"', html)
        self.assertIn('class="status-footer card"', html)
        self.assertIn('id="daily-activity"', html)
        self.assertIn('Data penggunaan token belum disambungkan', html)
        self.assertIn('id="user-dropdown" hidden', html)
        self.assertIn('id="mobile-nav-toggle"', html)
        self.assertIn('aria-controls="mobile-navigation"', html)
        self.assertIn('id="mobile-navigation"', html)
        self.assertIn('aria-controls="user-dropdown"', html)
        for target in ('company-profile', 'password-settings', 'subscription-settings'):
            self.assertIn('id="' + target + '"', html)
            self.assertIn('data-profile-target="' + target + '"', html)
        self.assertIn('method="post" action="/logout"', html)
        self.assertNotIn('href="/logout"', html)
        self.assertIn('id="bot-profile-form"', html)
        self.assertIn('name="bot_name"', html)
        self.assertIn('id="bot-phone"', html)
        self.assertIn('aria-valuetext="Data kapasiti belum tersedia"', html)
        self.assertIn('<button type="submit" disabled>Simpan Perubahan</button>', html)
        self.assertNotIn('Terhubung ke Meta API', html)
        self.assertIn('class="token-grid"', html)
        self.assertIn('id="token-message-summary"', html)
        self.assertIn('id="token-activity-status"', html)
        self.assertIn('bukan penggunaan token Gemini atau caj Meta', html)
        self.assertIn('Tiada kuota rasmi 1,000', html)
        self.assertIn('Tiada kuota token percuma bulanan standard', html)
        self.assertNotIn('id="usage-log"', html)
        for form in ('company-form', 'password-form'):
            self.assertIn('id="' + form + '"', html)
        for field in ('logo', 'display_name', 'email', 'current_password', 'new_password', 'confirm_password'):
            self.assertIn('name="' + field + '"', html)
        self.assertIn('class="logo-preview"', html)
        self.assertIn('Plan: Belum tersedia', html)
        self.assertIn('<button type="button" disabled>Upgrade Plan</button>', html)
        self.assertNotIn('RM 130 / bulan', html)

    def test_dashboard_panels_are_siblings_and_html_is_balanced(self):
        self.login()
        parser = DashboardStructure()
        parser.feed(self.client.get('/').data.decode('utf-8'))
        parser.close()
        self.assertEqual(parser.errors, [])
        self.assertEqual(parser.stack, [])
        self.assertEqual(parser.panels, {
            'tab-control-center': False, 'tab-phonebook': True,
            'tab-bot-profile': True, 'tab-token-usage': True, 'tab-settings': True,
        })

    def test_login_layout_toggle_and_support_have_no_contact_details(self):
        html = self.client.get('/').data.decode('utf-8')
        for marker in ('PORTAL KLIEN', 'design-system.css', 'client-login.css',
                       'id="toggle-password"', 'login.js', 'LIVE SUPPORT',
                       'Hubungi admin untuk bantuan'):
            self.assertIn(marker, html)
        for forbidden in ('login-intro', 'wa.link', '018-317-2114', '+60 18-317 2114'):
            self.assertNotIn(forbidden, html)
        response = self.client.get('/static/login.js')
        script = response.data.decode('utf-8')
        response.close()
        self.assertIn("passwordInput.type = visible ? 'text' : 'password'", script)
        self.assertIn("visible ? 'eye-off' : 'eye'", script)

    def test_password_must_be_configured(self):
        with patch.dict(os.environ, {"PORTAL_PASSWORD": ""}):
            self.assertEqual(self.login(password="defaultpass123").status_code, 503)

    def test_explicit_password_overrides_default(self):
        self.assertEqual(self.login(password="defaultpass123").status_code, 401)
        self.assertEqual(self.login(username="architechlaboratory").status_code, 401)
        self.assertEqual(self.login().status_code, 302)
        with self.client.session_transaction() as state:
            self.assertEqual(state["client_id"], 42)
            self.assertEqual(state["username"], "architechsystems")

    def test_missing_tenant_and_failed_relogin_do_not_grant_access(self):
        self.assertEqual(self.login(client_id=None).status_code, 503)
        self.assertEqual(self.client.get("/api/leads").status_code, 401)
        self.assertEqual(self.login().status_code, 302)
        self.assertEqual(self.login(password="wrong").status_code, 401)
        self.assertEqual(self.client.get("/api/leads").status_code, 401)

    def test_login_and_tenant_scoped_queries(self):
        self.assertEqual(self.login(password="bad").status_code, 401)
        self.assertEqual(self.login().status_code, 302)
        cursor = MagicMock()
        cursor.fetchone.return_value = (42,)
        cursor.fetchall.side_effect = [[("60123456789", "Ali", "manual")], [("60123456789", "Hai", None)]]
        cursor.fetchone.side_effect = [(42,), (42,)]
        connection = MagicMock()
        connection.__enter__.return_value.cursor.return_value.__enter__.return_value = cursor
        with patch.object(portal.psycopg2, "connect", return_value=connection):
            self.assertEqual(self.client.get("/api/leads").json, [{"phone": "60123456789", "name": "Ali", "source": "manual"}])
            self.assertEqual(self.client.get("/api/history?phone=60123456789").json[0]["text"], "Hai")
        self.assertEqual(cursor.execute.call_args_list[0].args[1], ("architechsystems",))
        self.assertEqual(cursor.execute.call_args_list[1].args[1], (42, 42))
        self.assertEqual(cursor.execute.call_args_list[3].args[1], (42, "60123456789"))
        self.assertEqual(self.client.get("/api/history?phone=bad").status_code, 400)
        self.client.post("/logout")
        self.assertEqual(self.client.get("/api/leads").status_code, 401)

    def test_whatsapp_bot_reply_visible_after_refresh(self):
        self.login()
        cursor = MagicMock()
        cursor.fetchone.return_value = (42,)
        cursor.fetchall.side_effect = [
            [("60123456789", "", "")],
            [("60123456789", "Hai", datetime(2026, 1, 1)),
             ("Zulfa Bot", "Salam!", datetime(2026, 1, 1))],
        ]
        connection = MagicMock()
        connection.__enter__.return_value.cursor.return_value.__enter__.return_value = cursor
        with patch.object(portal.psycopg2, "connect", return_value=connection):
            self.assertEqual(self.client.get("/api/leads").json, [{"phone": "60123456789", "name": "", "source": ""}])
            history = self.client.get("/api/history?phone=60123456789").json
        self.assertEqual([item["sender"] for item in history], ["customer", "agent"])
        self.assertEqual(history[1]["text"], "Salam!")

    def test_analytics_uses_tenant_messages_not_sample_data(self):
        self.login()
        now = datetime.now(timezone.utc)
        cursor = MagicMock()
        cursor.fetchone.return_value = (42,)
        cursor.fetchall.return_value = [
            ("60111", "60111", now), ("60111", "LeeA Bot", now),
            ("60222", "60222", now - timedelta(days=8)),
            ("60222", "60222", None),
        ]
        connection = MagicMock()
        connection.__enter__.return_value.cursor.return_value.__enter__.return_value = cursor
        with patch.object(portal.psycopg2, "connect", return_value=connection):
            response = self.client.get("/api/analytics")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["source"], "messages")
        self.assertEqual(response.json["prospects"], 2)
        self.assertEqual(response.json["incoming"], 3)
        self.assertEqual(response.json["replies"], 1)
        self.assertEqual(response.json["messages_7d"], 2)
        self.assertEqual(sum(day["messages"] for day in response.json["daily"]), 2)
        self.assertEqual(response.json["top_leads"][0]["phone"], "60222")
        self.assertEqual(cursor.execute.call_args_list[1].args[1], (42,))

    def test_analytics_missing_database(self):
        self.login()
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            self.assertEqual(self.client.get("/api/analytics").status_code, 503)

    def test_manual_phone_book_is_authenticated_and_tenant_scoped(self):
        payload = {"phone": "60123456789", "name": "Ali"}
        self.assertEqual(self.client.post("/api/contacts", json=payload).status_code, 401)
        self.login()
        self.assertEqual(self.client.post("/api/contacts", json={**payload, "name": " "}).status_code, 400)
        self.assertEqual(self.client.post("/api/contacts", json={**payload, "name": "x" * 151}).status_code, 400)
        cursor = MagicMock()
        cursor.fetchone.side_effect = [(42,), (1,)]
        connection = MagicMock()
        connection.__enter__.return_value.cursor.return_value.__enter__.return_value = cursor
        with patch.object(portal.psycopg2, "connect", return_value=connection):
            result = self.client.post("/api/contacts", json=payload)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["source"], "manual")
        self.assertEqual(cursor.execute.call_args_list[1].args[1], (42, "60123456789"))
        self.assertEqual(cursor.execute.call_args_list[2].args[1], (42, "60123456789", "Ali"))

    def test_ticket_requires_login_and_configuration(self):
        self.login()
        self.assertEqual(self.client.get("/api/chat-ticket").status_code, 503)
        with patch.dict(os.environ, {"CHAT_SOCKET_SECRET": "x" * 40,
                                  "CHAT_SOCKET_URL": "wss://bot.example/ws/chat"}):
            result = self.client.get("/api/chat-ticket")
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json["url"], "wss://bot.example/ws/chat")
            self.assertTrue(result.json["ticket"])

    def test_local_socket_requires_explicit_local_mode(self):
        self.login()
        settings = {"CHAT_SOCKET_SECRET": "x" * 40,
                    "CHAT_SOCKET_URL": "ws://127.0.0.1:5000/ws/chat"}
        with patch.dict(os.environ, settings):
            self.assertEqual(self.client.get("/api/chat-ticket").status_code, 503)
        with patch.dict(os.environ, {**settings, "LOCAL_HTTP": "1"}):
            self.assertEqual(self.client.get("/api/chat-ticket").status_code, 200)

    def test_new_profile_endpoints_require_login_and_do_not_invent_data(self):
        for path in ("/api/bot-profile", "/api/token-usage", "/api/subscription"):
            self.assertEqual(self.client.get(path).status_code, 401)
        for path in ("/api/bot-profile", "/api/profile/company", "/api/profile/logo"):
            self.assertEqual(self.client.post(path, json={}).status_code, 401)
        self.login()
        for path in ("/api/token-usage", "/api/subscription"):
            self.assertEqual(self.client.get(path).status_code, 503)
        self.assertEqual(self.client.post("/api/profile/logo").status_code, 503)
        self.assertEqual(self.client.post("/api/bot-profile", json={"bot_name": " "}).status_code, 400)
        self.assertEqual(self.client.post("/api/profile/company", json={"display_name": "X", "email": "bad"}).status_code, 400)

    def test_profile_writes_are_tenant_scoped(self):
        self.login()
        cursor = MagicMock()
        cursor.fetchone.side_effect = [(42,), ("LeeA",), (42,), (42,)]
        connection = MagicMock()
        connection.__enter__.return_value.cursor.return_value.__enter__.return_value = cursor
        with patch.object(portal.psycopg2, "connect", return_value=connection):
            result = self.client.get("/api/bot-profile")
            self.assertEqual(result.json["bot_name"], "LeeA")
            self.assertIsNone(result.json["capacity_used_mb"])
            self.assertTrue(self.client.post("/api/bot-profile", json={"bot_name": "Bot Baru"}).json["success"])
            self.assertTrue(self.client.post("/api/profile/company", json={"display_name": "Firma", "email": "a@example.com"}).json["success"])
        self.assertEqual(cursor.execute.call_args_list[3].args[1], ("Bot Baru", 42))
        self.assertEqual(cursor.execute.call_args_list[5].args[1], ("Firma", "a@example.com", 42))


if __name__ == "__main__":
    unittest.main()
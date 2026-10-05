import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import app as portal


class PortalTest(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"PORTAL_PASSWORD": "test-only", "DATABASE_URL": "postgresql://example.invalid/db"})
        self.env.start()
        portal.app.secret_key = "test-secret-only"
        self.client = portal.app.test_client()

    def tearDown(self):
        self.env.stop()

    def test_login_required(self):
        self.assertEqual(self.client.get("/api/analytics").status_code, 401)
        self.assertEqual(self.client.get("/api/chat-ticket").status_code, 401)
        self.assertEqual(self.client.get("/api/leads").status_code, 401)
        self.assertEqual(self.client.get("/api/history?phone=60123456789").status_code, 401)
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertNotIn(b"/api/leads", self.client.get("/").data)

    def test_dashboard_has_analytics_and_whatsapp_lead_navigation(self):
        self.client.post("/login", data={"password": "test-only"})
        html = self.client.get("/").data.decode("utf-8")
        self.assertIn('href="#analytics"', html)
        self.assertIn('href="#whatsapp-leads"', html)
        self.assertIn('id="analytics"', html)
        self.assertIn('id="whatsapp-leads"', html)
        self.assertIn('id="metric-prospects"', html)
        self.assertIn('id="top-leads"', html)

    def test_default_password_when_not_configured(self):
        with patch.dict(os.environ, {"PORTAL_PASSWORD": ""}):
            self.assertEqual(self.client.post("/login", data={"password": "wrong"}).status_code, 401)
            self.assertEqual(self.client.post("/login", data={"password": "defaultpass123"}).status_code, 302)
            self.assertIn(b"Dashboard LeeA", self.client.get("/").data)

    def test_explicit_password_overrides_default(self):
        self.assertEqual(self.client.post("/login", data={"password": "defaultpass123"}).status_code, 401)
        self.assertEqual(self.client.post("/login", data={"password": "test-only"}).status_code, 302)

    def test_login_and_tenant_scoped_queries(self):
        self.assertEqual(self.client.post("/login", data={"password": "bad"}).status_code, 401)
        self.assertEqual(self.client.post("/login", data={"password": "test-only"}).status_code, 302)
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
        self.client.post("/login", data={"password": "test-only"})
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
        self.client.post("/login", data={"password": "test-only"})
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
        self.assertEqual(response.json["prospects"], 2)
        self.assertEqual(response.json["incoming"], 3)
        self.assertEqual(response.json["replies"], 1)
        self.assertEqual(response.json["messages_7d"], 2)
        self.assertEqual(sum(day["messages"] for day in response.json["daily"]), 2)
        self.assertEqual(response.json["top_leads"][0]["phone"], "60222")
        self.assertEqual(cursor.execute.call_args_list[1].args[1], (42,))

    def test_analytics_missing_database(self):
        self.client.post("/login", data={"password": "test-only"})
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            self.assertEqual(self.client.get("/api/analytics").status_code, 503)

    def test_manual_phone_book_is_authenticated_and_tenant_scoped(self):
        payload = {"phone": "60123456789", "name": "Ali"}
        self.assertEqual(self.client.post("/api/contacts", json=payload).status_code, 401)
        self.client.post("/login", data={"password": "test-only"})
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
        self.client.post("/login", data={"password": "test-only"})
        self.assertEqual(self.client.get("/api/chat-ticket").status_code, 503)
        with patch.dict(os.environ, {"CHAT_SOCKET_SECRET": "x" * 40,
                                  "CHAT_SOCKET_URL": "wss://bot.example/ws/chat"}):
            result = self.client.get("/api/chat-ticket")
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json["url"], "wss://bot.example/ws/chat")
            self.assertTrue(result.json["ticket"])

    def test_local_socket_requires_explicit_local_mode(self):
        self.client.post("/login", data={"password": "test-only"})
        settings = {"CHAT_SOCKET_SECRET": "x" * 40,
                    "CHAT_SOCKET_URL": "ws://127.0.0.1:5000/ws/chat"}
        with patch.dict(os.environ, settings):
            self.assertEqual(self.client.get("/api/chat-ticket").status_code, 503)
        with patch.dict(os.environ, {**settings, "LOCAL_HTTP": "1"}):
            self.assertEqual(self.client.get("/api/chat-ticket").status_code, 200)


if __name__ == "__main__":
    unittest.main()
import os
import unittest
from datetime import datetime
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
        self.assertEqual(self.client.get("/api/chat-ticket").status_code, 401)
        self.assertEqual(self.client.get("/api/leads").status_code, 401)
        self.assertEqual(self.client.get("/api/history?phone=60123456789").status_code, 401)
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertNotIn(b"/api/leads", self.client.get("/").data)

    def test_login_and_tenant_scoped_queries(self):
        self.assertEqual(self.client.post("/login", data={"password": "bad"}).status_code, 401)
        self.assertEqual(self.client.post("/login", data={"password": "test-only"}).status_code, 302)
        cursor = MagicMock()
        cursor.fetchone.return_value = (42,)
        cursor.fetchall.side_effect = [[("60123456789", 3)], [("60123456789", "Hai", None)]]
        connection = MagicMock()
        connection.__enter__.return_value.cursor.return_value.__enter__.return_value = cursor
        with patch.object(portal.psycopg2, "connect", return_value=connection):
            self.assertEqual(self.client.get("/api/leads").json, [{"phone": "60123456789"}])
            self.assertEqual(self.client.get("/api/history?phone=60123456789").json[0]["text"], "Hai")
        self.assertEqual(cursor.execute.call_args_list[0].args[1], ("architechsystems",))
        self.assertEqual(cursor.execute.call_args_list[1].args[1], (42,))
        self.assertEqual(cursor.execute.call_args_list[3].args[1], (42, "60123456789"))
        self.assertEqual(self.client.get("/api/history?phone=bad").status_code, 400)
        self.client.post("/logout")
        self.assertEqual(self.client.get("/api/leads").status_code, 401)

    def test_whatsapp_bot_reply_visible_after_refresh(self):
        self.client.post("/login", data={"password": "test-only"})
        cursor = MagicMock()
        cursor.fetchone.return_value = (42,)
        cursor.fetchall.side_effect = [
            [("60123456789", 2)],
            [("60123456789", "Hai", datetime(2026, 1, 1)),
             ("Zulfa Bot", "Salam!", datetime(2026, 1, 1))],
        ]
        connection = MagicMock()
        connection.__enter__.return_value.cursor.return_value.__enter__.return_value = cursor
        with patch.object(portal.psycopg2, "connect", return_value=connection):
            self.assertEqual(self.client.get("/api/leads").json, [{"phone": "60123456789"}])
            history = self.client.get("/api/history?phone=60123456789").json
        self.assertEqual([item["sender"] for item in history], ["customer", "agent"])
        self.assertEqual(history[1]["text"], "Salam!")

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
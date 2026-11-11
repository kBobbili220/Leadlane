from datetime import datetime, timedelta, timezone
import os
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from sqlalchemy import func, select, update

from backend.app.cli.create_owner import create_owner
from backend.app.core.config import Settings, get_settings
from backend.app.core.security import password_hasher, token_digest
from backend.app.main import app
from backend.app.models import AuthRateLimit, AuthSession, Business, BusinessMembership, User
from database_helpers import TEST_PASSWORD
import test_services_api as services_tests

AUTH = "/api/v1/auth"


class AuthAPITests(unittest.TestCase):
    build_database = services_tests.ServiceAPITests.build_database
    setUp = services_tests.ServiceAPITests.setUp
    tearDown = services_tests.ServiceAPITests.tearDown

    def registration(self, **changes):
        return {"email": "new-owner@example.com", "password": TEST_PASSWORD,
                "full_name": "New owner", "business_name": "New Detailing", **changes}

    def test_registration_creates_new_business_and_hides_credentials(self):
        response = self.client.post(f"{AUTH}/register", json=self.registration())
        self.assertEqual(response.status_code, 201, response.text)
        data = response.json()
        self.assertNotEqual(data["business"]["id"], str(self.business_id))
        self.assertEqual(data["business"]["currency"], "USD")
        self.assertTrue(data["business"]["slug"].startswith("new-detailing-"))
        self.assertEqual(data["token_type"], "bearer")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertNotIn(TEST_PASSWORD, response.text)
        self.assertNotIn("password_hash", response.text)
        self.assertNotIn("token_digest", response.text)
        with self.sessions() as session:
            user = session.get(User, UUID(data["user"]["id"]))
            self.assertTrue(user.password_hash.startswith("$argon2id$"))
            self.assertTrue(password_hasher.verify(TEST_PASSWORD, user.password_hash))
            record = session.scalar(select(AuthSession).where(AuthSession.token_digest == token_digest(data["access_token"])))
            self.assertIsNotNone(record)
            self.assertNotEqual(record.token_digest, data["access_token"].encode())
        headers = {"Authorization": f"Bearer {data['access_token']}"}
        self.assertEqual(self.client.get("/api/v1/services", headers=headers).json(), [])

    def test_duplicate_email_is_case_insensitive_and_registration_is_atomic(self):
        first = self.client.post(f"{AUTH}/register", json=self.registration(email="NEW-OWNER@EXAMPLE.COM"))
        self.assertEqual(first.status_code, 201, first.text)
        with self.sessions() as session:
            before = session.scalar(select(func.count()).select_from(Business))
        duplicate = self.client.post(f"{AUTH}/register", json=self.registration())
        self.assertEqual(duplicate.status_code, 409)
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(Business)), before)
        self.assertEqual(first.json()["user"]["email"], "new-owner@example.com")

    def test_validation_never_echoes_password_and_cannot_claim_existing_business(self):
        for changes in ({"password": "secret"}, {"password": "s" * 129},
                        {"business_id": str(self.business_id)}, {"role": "admin"}, {"email": "bad email"}):
            with self.subTest(fields=list(changes)):
                payload = self.registration(**changes)
                response = self.client.post(f"{AUTH}/register", json=payload)
                self.assertEqual(response.status_code, 422)
                self.assertNotIn(payload["password"], response.text)
                self.assertNotIn('"input"', response.text)
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(Business)), 3)

    def test_login_normalization_identity_and_independent_sessions(self):
        response = self.client.post(f"{AUTH}/login", json={"email": "OWNER@EXAMPLE.COM", "password": TEST_PASSWORD})
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertNotEqual(data["access_token"], self.owner.access_token)
        headers = {"Authorization": f"Bearer {data['access_token']}"}
        me = self.client.get(f"{AUTH}/me", headers=headers)
        self.assertEqual(me.status_code, 200, me.text)
        self.assertEqual(me.json()["business"]["id"], str(self.business_id))
        self.assertNotIn("access_token", me.json())
        self.assertEqual(self.client.post(f"{AUTH}/logout", headers=headers).status_code, 204)
        self.assertEqual(self.client.post(f"{AUTH}/logout", headers=headers).status_code, 204)
        self.assertEqual(self.client.get(f"{AUTH}/me", headers=headers).status_code, 401)
        self.assertEqual(self.client.get(f"{AUTH}/me").status_code, 200)

    def test_invalid_credentials_are_generic_for_known_unknown_and_disabled_users(self):
        known = self.client.post(f"{AUTH}/login", json={"email": "owner@example.com", "password": "wrong"})
        unknown = self.client.post(f"{AUTH}/login", json={"email": "unknown@example.com", "password": "wrong"})
        self.assertEqual(known.status_code, 401)
        self.assertEqual(known.json(), unknown.json())
        with self.sessions() as session:
            session.execute(update(User).where(User.id == self.owner.user.id).values(is_active=False))
            session.commit()
        disabled = self.client.post(f"{AUTH}/login", json={"email": "owner@example.com", "password": TEST_PASSWORD})
        self.assertEqual(disabled.json(), known.json())
        self.assertEqual(self.client.get(f"{AUTH}/me").status_code, 401)

    def test_expired_invalid_and_missing_sessions_cannot_access_any_service_operation(self):
        self.client.headers.pop("Authorization")
        with patch.dict(os.environ, {"DEV_BUSINESS_ID": str(self.business_id)}):
            for method, path, body in (
                ("GET", "/api/v1/services", None), ("POST", "/api/v1/services", {"name": "Detail"}),
                ("GET", f"/api/v1/services/{uuid4()}", None),
                ("PATCH", f"/api/v1/services/{uuid4()}", {"name": "Changed"}),
                ("DELETE", f"/api/v1/services/{uuid4()}", None),
            ):
                self.assertEqual(self.client.request(method, path, json=body).status_code, 401)
        self.assertEqual(self.client.get(f"{AUTH}/me", headers={"Authorization": "Bearer invalid"}).status_code, 401)
        with self.sessions() as session:
            record = session.scalar(select(AuthSession).where(AuthSession.token_digest == token_digest(self.owner.access_token)))
            record.created_at = datetime.now(timezone.utc) - timedelta(days=3)
            record.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
            session.commit()
        self.assertEqual(self.client.get(f"{AUTH}/me", headers={"Authorization": f"Bearer {self.owner.access_token}"}).status_code, 401)

    def test_revoked_membership_and_inactive_business_are_forbidden(self):
        with self.sessions() as session:
            session.execute(update(BusinessMembership).where(BusinessMembership.user_id == self.owner.user.id).values(is_active=False))
            session.commit()
        self.assertEqual(self.client.get("/api/v1/services").status_code, 403)
        response = self.client.post(f"{AUTH}/login", json={"email": "owner@example.com", "password": TEST_PASSWORD})
        self.assertEqual(response.status_code, 403)

    def test_failed_logins_are_counted_and_rate_limit_resets_in_new_window(self):
        for _ in range(10):
            self.assertEqual(self.client.post(f"{AUTH}/login", json={"email": "owner@example.com", "password": "wrong"}).status_code, 401)
        blocked = self.client.post(f"{AUTH}/login", json={"email": "owner@example.com", "password": TEST_PASSWORD})
        self.assertEqual(blocked.status_code, 429)
        self.assertGreater(int(blocked.headers["retry-after"]), 0)
        with self.sessions() as session:
            counter = session.scalar(select(AuthRateLimit).where(AuthRateLimit.scope == "login_email"))
            self.assertEqual(counter.attempts, 11)
            self.assertEqual(counter.key_digest, token_digest("owner@example.com"))
            session.execute(update(AuthRateLimit).values(window_start=datetime.now(timezone.utc) - timedelta(hours=2)))
            session.commit()
        self.assertEqual(self.client.post(f"{AUTH}/login", json={"email": "owner@example.com", "password": TEST_PASSWORD}).status_code, 200)

    def test_ip_and_registration_rate_limits(self):
        with patch("backend.app.services.auth.verify_password", return_value=(False, None)):
            for i in range(60):
                self.assertEqual(self.client.post(f"{AUTH}/login", json={"email": f"unknown-{i}@example.com", "password": "wrong"}).status_code, 401)
            self.assertEqual(self.client.post(f"{AUTH}/login", json={"email": "another@example.com", "password": "wrong"}).status_code, 429)
        for i in range(5):
            response = self.client.post(f"{AUTH}/register", json=self.registration(email=f"signup-{i}@example.com"))
            self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(self.client.post(f"{AUTH}/register", json=self.registration()).status_code, 429)

    def test_session_duration_is_configurable_and_password_whitespace_preserved(self):
        app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, auth_session_ttl_days=1)
        password = f" {TEST_PASSWORD} "
        registered = self.client.post(f"{AUTH}/register", json=self.registration(password=password))
        self.assertEqual(registered.status_code, 201, registered.text)
        expires = datetime.fromisoformat(registered.json()["expires_at"].replace("Z", "+00:00"))
        self.assertAlmostEqual((expires - datetime.now(timezone.utc)).total_seconds(), 86400, delta=5)
        bad = self.client.post(f"{AUTH}/login", json={"email": "new-owner@example.com", "password": TEST_PASSWORD})
        self.assertEqual(bad.status_code, 401)

    def test_existing_business_owner_setup_preserves_history_and_prevents_takeover(self):
        with self.sessions() as session:
            self.assertTrue(create_owner(session, self.other_id, "bootstrap@example.com", "Existing owner", TEST_PASSWORD))
            self.assertFalse(create_owner(session, self.other_id, "bootstrap@example.com", "Existing owner", TEST_PASSWORD))
            with self.assertRaises(ValueError):
                create_owner(session, self.other_id, "takeover@example.com", "Another", TEST_PASSWORD)
            session.rollback()
        logged_in = self.client.post(f"{AUTH}/login", json={"email": "bootstrap@example.com", "password": TEST_PASSWORD})
        self.assertEqual(logged_in.status_code, 200, logged_in.text)
        rows = self.client.get("/api/v1/services", headers={"Authorization": f"Bearer {logged_in.json()['access_token']}"}).json()
        self.assertEqual(rows[0]["id"], str(self.other_service_id))


@unittest.skipUnless(os.environ.get("TEST_DATABASE_URL"), "Set TEST_DATABASE_URL for PostgreSQL auth tests")
class PostgreSQLAuthAPITests(AuthAPITests):
    build_database = services_tests.PostgreSQLServiceAPITests.build_database

    def tearDown(self):
        try:
            self.transaction.rollback()
            self.connection.close()
        finally:
            services_tests.ServiceAPITests.tearDown(self)

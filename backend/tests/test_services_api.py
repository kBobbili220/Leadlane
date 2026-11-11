"""HTTP/SQL tests on SQLite, plus the same suite on PostgreSQL when configured.

The SQLite fixture contains the actual Service mapping and a minimal business
table; UUID/time/string functions stand in for PostgreSQL defaults. PostgreSQL
runs use the migrated schema and real quote items to check historical references.
"""

from datetime import datetime, timezone
import os
import unittest
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.config import Settings, get_settings
from backend.app.db.session import get_session
from backend.app.main import app
from backend.app.models import Business, Contact, Inquiry, Quote, QuoteItem, Service

BASE = "/api/v1/services"


class ServiceAPITests(unittest.TestCase):
    def build_database(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )

        @event.listens_for(self.engine, "connect")
        def sqlite_functions(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.create_function("gen_random_uuid", 0, lambda: uuid4().hex)
            connection.create_function("now", 0, lambda: datetime.now(timezone.utc).isoformat())
            connection.create_function("btrim", 1, lambda value: value.strip(" ") if value is not None else None)

        with self.engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE businesses (id UUID PRIMARY KEY, is_active BOOLEAN NOT NULL)")
            for business_id, active in ((self.business_id, True), (self.other_id, True), (self.inactive_id, False)):
                connection.exec_driver_sql("INSERT INTO businesses VALUES (?, ?)", (business_id.hex, active))
            Service.__table__.create(connection)
            connection.exec_driver_sql(
                "CREATE TABLE historical_service_references (business_id UUID NOT NULL, service_id UUID NOT NULL, "
                "unit_price_minor BIGINT NOT NULL, FOREIGN KEY (business_id, service_id) "
                "REFERENCES services(business_id, id) ON DELETE RESTRICT)"
            )
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def setUp(self):
        self.business_id, self.other_id, self.inactive_id = uuid4(), uuid4(), uuid4()
        self.build_database()
        with self.sessions() as session:
            other_service = Service(business_id=self.other_id, name="Other tenant's service")
            session.add(other_service)
            session.commit()
            self.other_service_id = other_service.id

        def test_session():
            with self.sessions() as session:
                yield session

        self.previous_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[get_session] = test_session
        app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, dev_business_id=self.business_id)
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.previous_overrides)
        self.engine.dispose()

    def create(self, **changes):
        response = self.client.post(BASE, json={"name": "Full detail", "base_price_minor": 15000, **changes})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def add_historical_reference(self, service_id):
        with self.sessions() as session:
            session.execute(text(
                "INSERT INTO historical_service_references (business_id, service_id, unit_price_minor) "
                "VALUES (:business, :service, 15000)"
            ), {"business": self.business_id.hex, "service": UUID(service_id).hex})
            session.commit()

    def historical_price(self):
        with self.sessions() as session:
            return session.scalar(text("SELECT unit_price_minor FROM historical_service_references"))

    def test_create_read_and_nullable_price(self):
        service = self.create(description="Interior and exterior", base_price_minor=None)
        self.assertEqual(service["business_id"], str(self.business_id))
        self.assertIsNone(service["base_price_minor"])
        self.assertTrue(service["is_active"])
        self.assertEqual(service["unit_label"], "vehicle")
        self.assertIsNotNone(service["created_at"])
        response = self.client.get(f"{BASE}/{service['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), service)

    def test_list_filters_orders_and_paginates(self):
        first = self.create(name="First", sort_order=-1)
        last = self.create(name="Last", sort_order=10)
        archived = self.create(name="Archived", is_active=False, sort_order=20)
        response = self.client.get(BASE)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.json()], [first["id"], last["id"]])
        self.assertEqual(self.client.get(BASE, params={"limit": 1, "offset": 1}).json()[0]["id"], last["id"])
        all_rows = self.client.get(BASE, params={"include_archived": True}).json()
        self.assertEqual([row["id"] for row in all_rows], [first["id"], last["id"], archived["id"]])

    def test_patch_updates_only_supplied_fields_and_clears_nullable_fields(self):
        service = self.create(description="Original", estimated_duration_minutes=120)
        response = self.client.patch(f"{BASE}/{service['id']}", json={"base_price_minor": 17500, "description": None})
        self.assertEqual(response.status_code, 200, response.text)
        updated = response.json()
        self.assertEqual(updated["name"], service["name"])
        self.assertEqual(updated["estimated_duration_minutes"], 120)
        self.assertEqual(updated["base_price_minor"], 17500)
        self.assertIsNone(updated["description"])
        response = self.client.patch(f"{BASE}/{service['id']}", json={"base_price_minor": None, "estimated_duration_minutes": None})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(response.json()["base_price_minor"])
        self.assertIsNone(response.json()["estimated_duration_minutes"])

    def test_archive_preserves_history_is_idempotent_and_can_be_restored(self):
        service = self.create()
        self.add_historical_reference(service["id"])
        response = self.client.patch(f"{BASE}/{service['id']}", json={"base_price_minor": 17500})
        self.assertEqual(response.status_code, 200, response.text)
        for _ in range(2):
            response = self.client.delete(f"{BASE}/{service['id']}")
            self.assertEqual(response.status_code, 204, response.text)
            self.assertEqual(response.content, b"")
        with self.sessions() as session:
            persisted = session.get(Service, UUID(service["id"]))
            self.assertIsNotNone(persisted)
            self.assertFalse(persisted.is_active)
        self.assertEqual(self.historical_price(), 15000)
        self.assertEqual(self.client.get(BASE).json(), [])
        self.assertEqual(len(self.client.get(BASE, params={"include_archived": True}).json()), 1)
        self.assertFalse(self.client.get(f"{BASE}/{service['id']}").json()["is_active"])
        response = self.client.patch(f"{BASE}/{service['id']}", json={"is_active": True})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(self.client.get(BASE).json()), 1)

    def test_cross_tenant_and_unknown_ids_are_not_accessible(self):
        for service_id in (self.other_service_id, uuid4()):
            for method, body in (("GET", None), ("PATCH", {"name": "Attempted edit"}), ("DELETE", None)):
                with self.subTest(id=service_id, method=method):
                    response = self.client.request(method, f"{BASE}/{service_id}", json=body)
                    self.assertEqual(response.status_code, 404, response.text)
        response = self.client.get(BASE, headers={"X-Business-ID": str(self.other_id)})
        self.assertEqual(response.json(), [])
        with self.sessions() as session:
            self.assertTrue(session.get(Service, self.other_service_id).is_active)

    def test_invalid_requests_do_not_change_the_record(self):
        service = self.create()
        url = f"{BASE}/{service['id']}"
        for payload in (
            {}, {"name": None}, {"name": "   "}, {"unit_label": None}, {"is_active": None},
            {"sort_order": None}, {"base_price_minor": -1}, {"base_price_minor": 15.5},
            {"estimated_duration_minutes": 0}, {"business_id": str(self.other_id)},
            {"id": str(uuid4())}, {"unexpected": "value"},
        ):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.patch(url, json=payload).status_code, 422)
        for params in ({"limit": 0}, {"limit": 101}, {"offset": -1}):
            with self.subTest(params=params):
                self.assertEqual(self.client.get(BASE, params=params).status_code, 422)
        self.assertEqual(self.client.get(f"{BASE}/not-a-uuid").status_code, 422)
        self.assertEqual(self.client.post(BASE, json={"name": "Detail", "business_id": str(self.other_id)}).status_code, 422)
        self.assertEqual(self.client.get(url).json(), service)

    def test_missing_or_inactive_business_context(self):
        app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
        self.assertEqual(self.client.get(BASE).status_code, 503)
        for business_id in (uuid4(), self.inactive_id):
            with self.subTest(business=business_id):
                app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, dev_business_id=business_id)
                self.assertEqual(self.client.get(BASE).status_code, 404)

    def test_health_works_without_database_configuration(self):
        app.dependency_overrides.pop(get_session)
        app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get(BASE).status_code, 503)

    def test_mobile_onboarding_is_served_without_a_database_connection(self):
        app.dependency_overrides.pop(get_session)
        app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
        page = self.client.get("/onboarding/")
        self.assertEqual(page.status_code, 200)
        self.assertIn('id="service-form"', page.text)
        self.assertIn('type="module" src="./app.js"', page.text)
        for path in ("styles.css", "app.js", "service-client.mjs"):
            response = self.client.get(f"/onboarding/{path}")
            self.assertEqual(response.status_code, 200, path)
        self.assertEqual(self.client.get("/onboarding/.env").status_code, 404)


@unittest.skipUnless(os.environ.get("TEST_DATABASE_URL"), "Set TEST_DATABASE_URL to run the service API suite on PostgreSQL")
class PostgreSQLServiceAPITests(ServiceAPITests):
    def build_database(self):
        url = make_url(os.environ["TEST_DATABASE_URL"]).set(drivername="postgresql+psycopg")
        self.engine = create_engine(url)
        self.connection = self.engine.connect()
        self.transaction = self.connection.begin()
        self.sessions = sessionmaker(
            bind=self.connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        with self.sessions() as session:
            session.add_all([
                Business(id=self.business_id, slug=f"test-{self.business_id}", name="Detailer"),
                Business(id=self.other_id, slug=f"test-{self.other_id}", name="Other detailer"),
                Business(id=self.inactive_id, slug=f"test-{self.inactive_id}", name="Inactive", is_active=False),
            ])
            session.commit()

    def add_historical_reference(self, service_id):
        with self.sessions() as session:
            contact = Contact(business_id=self.business_id, name="Customer", email="test@example.com")
            inquiry = Inquiry(business_id=self.business_id, contact=contact)
            quote = Quote(business_id=self.business_id, inquiry=inquiry, currency="USD", recipient_name="Customer",
                          recipient_email="test@example.com", subtotal_minor=15000)
            item = QuoteItem(business_id=self.business_id, quote=quote, service_id=UUID(service_id), position=0,
                             name="Full detail", unit_price_minor=15000)
            session.add_all([contact, inquiry, quote, item])
            session.commit()
            self.historical_item_id = item.id

    def historical_price(self):
        with self.sessions() as session:
            return session.scalar(select(QuoteItem.unit_price_minor).where(QuoteItem.id == self.historical_item_id))

    def tearDown(self):
        try:
            self.transaction.rollback()
            self.connection.close()
        finally:
            super().tearDown()


if __name__ == "__main__":
    unittest.main()

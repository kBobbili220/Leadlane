from datetime import datetime, timedelta, timezone
import unittest
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from backend.app.models import Quote, QuoteItem
import backend.app.schemas as schemas
from backend.app.schemas.common import BIGINT_MAX


def item_data(**changes):
    return {"position": 0, "name": "Full detail", "quantity": 2, "unit_price_minor": 15000, **changes}


def quote_data(**changes):
    return {
        "currency": "USD", "recipient_name": "Customer", "recipient_email": "customer@example.com",
        "items": [item_data()], **changes,
    }


class SchemaTests(unittest.TestCase):
    def test_all_exported_schemas_generate_json_schema(self):
        for name in schemas.__all__:
            cls = getattr(schemas, name)
            if isinstance(cls, type) and issubclass(cls, BaseModel):
                with self.subTest(schema=name):
                    cls.model_json_schema()

    def test_public_inquiry_validates_contact_and_defaults(self):
        inquiry = schemas.PublicInquiryCreate.model_validate({
            "contact": {"name": " Customer ", "phone": "+15555550123", "preferred_channel": "sms"},
            "vehicle_details": {"pet_hair": True, "photos": ["front.jpg"]},
        })
        self.assertEqual(inquiry.contact.name, "Customer")
        self.assertEqual(inquiry.service_address, {})

    def test_public_input_rejects_internal_fields(self):
        payload = {"contact": {"name": "Customer", "email": "customer@example.com"}}
        for field, value in (("business_id", str(uuid4())), ("internal_notes", "private"), ("status", "won"), ("contact_id", str(uuid4()))):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                schemas.PublicInquiryCreate.model_validate({**payload, field: value})
        with self.assertRaises(ValidationError):
            schemas.PublicInquiryCreate.model_validate({"contact": {**payload["contact"], "notes": "private"}})

    def test_create_schemas_reject_tenant_and_database_generated_values(self):
        cases = (
            (schemas.BusinessCreate, {"slug": "detailer", "name": "Detailer"}),
            (schemas.ContactCreate, {"name": "Customer", "phone": "+15555550123"}),
            (schemas.ServiceCreate, {"name": "Detail"}),
            (schemas.InquiryCreate, {"contact_id": uuid4()}),
            (schemas.QuoteCreate, quote_data()),
            (schemas.QuoteItemCreate, item_data()),
        )
        for cls, payload in cases:
            for field in ("id", "business_id", "created_at", "updated_at"):
                with self.subTest(schema=cls.__name__, field=field), self.assertRaises(ValidationError):
                    cls.model_validate({**payload, field: str(uuid4())})
        for field in ("subtotal_minor", "total_minor", "public_token_hash", "status", "revision"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                schemas.QuoteCreate.model_validate(quote_data(**{field: 1}))
        with self.assertRaises(ValidationError):
            schemas.QuoteItemCreate.model_validate(item_data(line_total_minor=30000))

    def test_contact_reachability_and_channel_constraints(self):
        for payload in (
            {"name": "Customer"},
            {"name": "Customer", "email": "   "},
            {"name": "Customer", "email": "customer@example.com", "preferred_channel": "sms"},
            {"name": "Customer", "phone": "+15555550123", "preferred_channel": "email"},
        ):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                schemas.ContactCreate.model_validate(payload)

    def test_business_slug_currency_and_timezone(self):
        self.assertEqual(schemas.BusinessCreate(slug="detailer-1", name="Detailer", timezone="America/Chicago").currency, "USD")
        for changes in ({"slug": "Invalid Slug"}, {"currency": "usd"}, {"timezone": "Not/A_Timezone"}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                schemas.BusinessCreate.model_validate({"slug": "detailer", "name": "Detailer", **changes})

    def test_integer_ranges_and_money_do_not_coerce_floats_or_booleans(self):
        for amount in (-1, BIGINT_MAX + 1, 1.5, True, "15000"):
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                schemas.ServiceCreate(name="Detail", base_price_minor=amount)
        for quantity in (0, -1, 2**31, 1.5, True):
            with self.subTest(quantity=quantity), self.assertRaises(ValidationError):
                schemas.QuoteItemCreate.model_validate(item_data(quantity=quantity))
        with self.assertRaises(ValidationError):
            schemas.QuoteItemCreate.model_validate(item_data(unit_price_minor=BIGINT_MAX))

    def test_aware_datetimes_and_preferred_window(self):
        now = datetime.now(timezone.utc)
        valid = schemas.InquiryCreate(contact_id=uuid4(), preferred_start_at=now, preferred_end_at=now + timedelta(hours=1))
        self.assertEqual(valid.preferred_start_at, now)
        for changes in (
            {"preferred_start_at": datetime(2026, 11, 9)},
            {"preferred_end_at": now},
            {"preferred_start_at": now, "preferred_end_at": now},
            {"preferred_start_at": now, "preferred_end_at": now - timedelta(hours=1)},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                schemas.InquiryCreate.model_validate({"contact_id": uuid4(), **changes})

    def test_quote_items_and_amounts(self):
        self.assertEqual(schemas.QuoteCreate.model_validate(quote_data(discount_minor=1000)).discount_minor, 1000)
        for changes in (
            {"items": []},
            {"items": [item_data(), item_data()]},
            {"discount_minor": 30001},
            {"recipient_email": None},
            {"tax_minor": BIGINT_MAX},
            {"items": [item_data(quantity=1, unit_price_minor=BIGINT_MAX), item_data(position=1, quantity=1, unit_price_minor=1)]},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                schemas.QuoteCreate.model_validate(quote_data(**changes))

    def test_json_fields_require_objects_and_fresh_defaults(self):
        first = schemas.ServiceCreate(name="Detail")
        self.assertIsNone(first.base_price_minor)
        a = schemas.BusinessCreate(slug="a", name="A")
        b = schemas.BusinessCreate(slug="b", name="B")
        a.address["city"] = "Austin"
        self.assertEqual(b.address, {})
        for invalid in ([], "address", None, {"not_json": object()}):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                schemas.BusinessCreate(slug="detailer", name="Detailer", address=invalid)

    def test_owner_and_public_responses_serialize_orm_and_hide_secrets(self):
        now = datetime.now(timezone.utc)
        business_id, quote_id = uuid4(), uuid4()
        item = QuoteItem(
            id=uuid4(), business_id=business_id, quote_id=quote_id, service_id=uuid4(),
            position=0, name="Detail", quantity=2, unit_label="vehicle", unit_price_minor=15000,
            line_total_minor=30000, created_at=now, updated_at=now,
        )
        quote = Quote(
            id=quote_id, business_id=business_id, inquiry_id=uuid4(), revision=1, status="sent", currency="USD",
            recipient_name="Customer", recipient_email="customer@example.com", recipient_phone="+15555550123",
            vehicle_snapshot={"make": "Toyota"}, service_address_snapshot={},
            subtotal_minor=30000, discount_minor=1000, tax_minor=2320, total_minor=31320,
            public_token_hash=b"x" * 32, follow_up_count=0, sent_at=now, expires_at=now + timedelta(days=7),
            created_at=now, updated_at=now, items=[item],
        )
        owner = schemas.QuoteRead.model_validate(quote).model_dump(mode="json")
        public = schemas.PublicQuoteRead.model_validate(quote).model_dump(mode="json")
        self.assertEqual(owner["items"][0]["line_total_minor"], 30000)
        self.assertEqual(public["total_minor"], 31320)
        self.assertNotIn("public_token_hash", owner)
        for field in ("public_token_hash", "business_id", "inquiry_id", "recipient_email", "recipient_phone", "follow_up_count"):
            self.assertNotIn(field, public)
        for field in ("id", "business_id", "quote_id", "service_id"):
            self.assertNotIn(field, public["items"][0])


if __name__ == "__main__":
    unittest.main()

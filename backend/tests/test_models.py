"""Compare ORM DDL to the actual migration, independent of a running database."""

import os
from pathlib import Path
import unittest
import warnings
from uuid import uuid4

from pglast import ast, parse_sql
from pglast.stream import RawStream
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, SAWarning
from sqlalchemy.orm import Session, configure_mappers, selectinload
from sqlalchemy.schema import CreateIndex, CreateTable

from backend.app.models import Base, Business, Contact, Inquiry, Quote, QuoteItem, Service
from backend.app.schemas import QuoteRead

MIGRATIONS = Path(__file__).resolve().parents[1] / "app/db"
DIALECT = postgresql.dialect()


def render(node):
    return RawStream()(node) if node is not None else None


def names(nodes):
    return tuple(node.sval for node in nodes or ())


def table_signature(statement):
    """Normalize inline/table constraints and SQL type aliases, preserving semantics."""
    columns, constraints = {}, set()
    for element in statement.tableElts:
        if isinstance(element, ast.ColumnDef):
            columns[element.colname] = {
                "type": (names(element.typeName.names)[-1], tuple(render(n) for n in element.typeName.typmods or ())),
                "nullable": True,
                "default": None,
                "generated": None,
            }

    def add_constraint(constraint, column=None):
        kind = constraint.contype.name
        keys = names(constraint.keys) or ((column,) if column else ())
        if kind == "CONSTR_NOTNULL":
            columns[column]["nullable"] = False
        elif kind == "CONSTR_DEFAULT":
            columns[column]["default"] = render(constraint.raw_expr)
        elif kind == "CONSTR_GENERATED":
            columns[column]["generated"] = (constraint.generated_when, render(constraint.raw_expr))
        elif kind in ("CONSTR_PRIMARY", "CONSTR_UNIQUE"):
            constraints.add((kind, constraint.conname, keys))
            if kind == "CONSTR_PRIMARY":
                for key in keys:
                    columns[key]["nullable"] = False
        elif kind == "CONSTR_CHECK":
            constraints.add((kind, constraint.conname, render(constraint.raw_expr)))
        elif kind == "CONSTR_FOREIGN":
            constraints.add((
                kind, constraint.conname, names(constraint.fk_attrs) or (column,),
                constraint.pktable.relname, names(constraint.pk_attrs),
                constraint.fk_del_action, constraint.fk_upd_action,
                constraint.fk_matchtype, constraint.deferrable, constraint.initdeferred,
            ))
        else:
            raise AssertionError(f"Unhandled migration constraint: {kind}")

    for element in statement.tableElts:
        if isinstance(element, ast.ColumnDef):
            for constraint in element.constraints or ():
                add_constraint(constraint, element.colname)
        else:
            add_constraint(element)
    return columns, constraints


class ModelParityTests(unittest.TestCase):
    def test_all_columns_constraints_and_indexes_match_migration(self):
        expected_tables, expected_indexes = {}, {}
        sql = "\n".join(path.read_text() for path in sorted(MIGRATIONS.glob('*.sql')))
        for raw in parse_sql(sql):
            statement = raw.stmt
            if isinstance(statement, ast.CreateStmt):
                expected_tables[statement.relation.relname] = table_signature(statement)
            elif isinstance(statement, ast.IndexStmt):
                expected_indexes[statement.idxname] = render(statement)

        self.assertEqual(set(expected_tables), set(Base.metadata.tables))
        actual_indexes = {}
        for table in Base.metadata.sorted_tables:
            with self.subTest(table=table.name):
                ddl = str(CreateTable(table).compile(dialect=DIALECT))
                actual = table_signature(parse_sql(ddl)[0].stmt)
                self.assertEqual(expected_tables[table.name], actual)
            for index in table.indexes:
                ddl = str(CreateIndex(index).compile(dialect=DIALECT))
                actual_indexes[index.name] = render(parse_sql(ddl)[0].stmt)
        self.assertEqual(expected_indexes, actual_indexes)

    def test_relationship_configuration_has_no_overlap_warnings(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error", SAWarning)
            configure_mappers()

    def test_composite_relationships_do_not_overwrite_business_id(self):
        # A related object from another tenant must fail its FK, never retag a row.
        for cls, relationship_name, target in (
            (Inquiry, "contact", "contact_id"),
            (Inquiry, "requested_service", "requested_service_id"),
            (Quote, "inquiry", "inquiry_id"),
            (QuoteItem, "quote", "quote_id"),
            (QuoteItem, "service", "service_id"),
        ):
            with self.subTest(model=cls.__name__, relationship=relationship_name):
                relationship = inspect(cls).relationships[relationship_name]
                self.assertEqual([destination.name for _, destination in relationship.synchronize_pairs], [target])
                self.assertIn("business_id", str(relationship.primaryjoin))


@unittest.skipUnless(os.environ.get("TEST_DATABASE_URL"), "Set TEST_DATABASE_URL to run PostgreSQL round-trip checks")
class PostgreSQLRoundTripTests(unittest.TestCase):
    def test_defaults_totals_triggers_relationships_and_tenant_rejection(self):
        url = make_url(os.environ["TEST_DATABASE_URL"]).set(drivername="postgresql+psycopg")
        engine = create_engine(url)
        try:
            with engine.connect() as connection:
                transaction = connection.begin()
                try:
                    with Session(bind=connection) as session:
                        business = Business(slug=f"test-{uuid4()}", name="Detailer")
                        other = Business(slug=f"test-{uuid4()}", name="Other detailer")
                        customer = Contact(business=business, name="Customer", email="test@example.com")
                        other_customer = Contact(business=other, name="Other", phone="+15555550123")
                        service = Service(business=business, name="Detail", base_price_minor=15000)
                        inquiry = Inquiry(business=business, contact=customer, requested_service=service)
                        quote = Quote(
                            business=business, inquiry=inquiry, currency="USD", recipient_name="Customer",
                            recipient_email="test@example.com", subtotal_minor=30000, discount_minor=1000, tax_minor=2320,
                        )
                        item = QuoteItem(business=business, quote=quote, service=service, position=0, name="Detail", quantity=2, unit_price_minor=15000)
                        session.add_all([business, other, customer, other_customer, service, inquiry, quote, item])
                        session.flush()

                        self.assertIsNotNone(business.id)
                        self.assertEqual(business.timezone, "UTC")
                        self.assertEqual(business.address, {})
                        self.assertEqual(inquiry.status, "new")
                        self.assertEqual(quote.status, "draft")
                        self.assertEqual(quote.total_minor, 31320)
                        self.assertEqual(item.line_total_minor, 30000)
                        prior_update = service.updated_at
                        service.name = "Updated catalog name"
                        session.flush()
                        self.assertGreater(service.updated_at, prior_update)
                        self.assertEqual(item.name, "Detail")

                        with self.assertRaises(IntegrityError):
                            with session.begin_nested():
                                inquiry.contact = other_customer
                                session.flush()

                        loaded = session.scalars(
                            select(Quote).where(Quote.id == quote.id).options(selectinload(Quote.items))
                        ).one()
                        response = QuoteRead.model_validate(loaded)
                        self.assertEqual(response.items[0].line_total_minor, 30000)
                        self.assertNotIn("public_token_hash", response.model_dump())
                finally:
                    transaction.rollback()
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()

# Service endpoints

Start the API after applying the initial schema and `002_owner_auth.sql`.
See [owner authentication and existing-business setup](authentication.md).

## Development configuration

The root `.env` supplies `DATABASE_URL` and optional `AUTH_SESSION_TTL_DAYS`
(default 14). `DEV_BUSINESS_ID` is no longer used. Register a new owner/business in
the native app, or use the local owner setup command for an existing business.
Every service endpoint requires a bearer session and derives its business from
that owner's active membership; request headers/bodies cannot switch tenants.

Sign in using `/api/v1/auth/login` in Swagger UI, copy the returned access token,
and paste it into **Authorize**. For the curl examples below, set `OWNER_TOKEN`
without putting the token into shell history:

```bash
read -rsp "Owner access token: " OWNER_TOKEN
printf '\n'
```

Run the API from the repository root:

```bash
fastapi dev backend/app/main.py
```

Plain `postgresql://`, `postgres://`, and `postgresql+psycopg://` database URLs are
normalized to the psycopg driver. Settings changes require a server restart.

## Create and retrieve

```bash
curl -X POST http://127.0.0.1:8000/api/v1/services \
  -H "Authorization: Bearer $OWNER_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Full detail","description":"Interior and exterior","base_price_minor":15000,"estimated_duration_minutes":120,"sort_order":0}'

curl -H "Authorization: Bearer $OWNER_TOKEN" http://127.0.0.1:8000/api/v1/services
curl -H "Authorization: Bearer $OWNER_TOKEN" http://127.0.0.1:8000/api/v1/services/SERVICE_UUID
```

POST returns `201` with a `ServiceRead` object, including database-generated UUID
and timestamps. GET returns `200`. Nullable `base_price_minor` means the service
needs individualized pricing; zero means free. Prices are integer minor units in
the business's currency. Units default to `vehicle`, display order to `0`, and
`is_active` to `true`.

List responses are JSON arrays. Query parameters are `include_archived` (default
false), `limit` (default 50, maximum 100) and `offset` (default 0). Ordering is
`sort_order ASC, id ASC`. Individual GET requests can retrieve archived services.

## Partial update

```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/services/SERVICE_UUID \
  -H "Authorization: Bearer $OWNER_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"base_price_minor":17500,"description":null}'
```

PATCH returns `200` with the updated service. Only supplied fields are changed.
Explicit null clears `description`, `base_price_minor` or
`estimated_duration_minutes`. Null is invalid for `name`, `unit_label`,
`is_active` and `sort_order`. Empty patches and unknown fields return `422`.
Business IDs, service IDs and timestamps are never writable through these schemas.

## Archive and restore

```bash
curl -X DELETE -H "Authorization: Bearer $OWNER_TOKEN" http://127.0.0.1:8000/api/v1/services/SERVICE_UUID
curl -H "Authorization: Bearer $OWNER_TOKEN" 'http://127.0.0.1:8000/api/v1/services?include_archived=true'

curl -X PATCH http://127.0.0.1:8000/api/v1/services/SERVICE_UUID \
  -H "Authorization: Bearer $OWNER_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"is_active":true}'
```

DELETE sets `is_active=false` and returns `204` with an empty body. It never
physically deletes a service. Repeating DELETE on an archived service also returns
`204`. Existing inquiry and quote item references remain valid, and snapshot
prices/descriptions in quote items are unchanged. PATCH can restore or edit an
archived service.

## Errors and transactions

Missing/invalid sessions return `401`; inactive business access returns `403`.
Unknown services and services from another business return `404`. Invalid UUIDs,
request fields or pagination values return `422`. An unconfigured or unavailable
database returns `503` without connection details.

Each request owns a database session. Mutations flush and validate their response
before committing. Failed requests close their session and roll back outstanding
changes. PATCH and DELETE acquire a row lock after filtering by business and
service ID. All service queries include the business boundary.

## Tests

```bash
python -m pip install -e '.[test]'
python -m unittest discover -s backend/tests -p 'test_*.py' -v
```

The default API suite uses the actual service mapping on SQLite, with functions
standing in for PostgreSQL UUID/timestamp/string defaults and a minimal business
table. It exercises HTTP routing, persistence, pagination, partial updates,
archival, validation and business boundaries. PostgreSQL-specific timestamp
triggers, row locks and real quote item references require the PostgreSQL suite.
Set `TEST_DATABASE_URL` to an authenticated URL for a migrated development
PostgreSQL database to run that suite as well; its fixtures are rolled back.

## Diagnose a database connection

If `psql` connects but the API returns `Database is unavailable`, run this in the
same terminal/virtual environment used to launch FastAPI:

```bash
python -m backend.app.db.check_connection
```

It checks the exact application settings, database driver, required tables and
configured business. Database passwords are redacted from errors. Environment
variables override `.env`, so an old exported `DATABASE_URL` can select a different
connection. URL-reserved password characters must be percent-encoded in the URL.

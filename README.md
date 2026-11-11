# Service Business API

FastAPI backend requiring Python 3.10 or newer.

The six-table PostgreSQL schema and its workflow contracts are documented in
[docs/database.md](docs/database.md). Apply [the initial schema](backend/app/db/001_initial.sql)
to an empty PostgreSQL 14+ database; it is not applied automatically by the API.

SQLAlchemy mappings live in [`backend/app/models`](backend/app/models); Pydantic request
and response schemas live in [`backend/app/schemas`](backend/app/schemas).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env
```

Edit `.env` with your PostgreSQL connection URL. Apply `001_initial.sql` and then
`002_owner_auth.sql`. Settings are
loaded from `.env` at the repository root, with environment variables taking
precedence. Restart the API after changing configuration.

Owners register and sign in using email/password. Sessions are stored securely
on the device and expire after 14 days by default. All service endpoints require
a bearer session; `DEV_BUSINESS_ID` is no longer used. To link an owner to an
existing development business without losing services, follow
[the authentication upgrade guide](docs/authentication.md).

## Run

```bash
fastapi dev backend/app/main.py
```

The API runs at http://127.0.0.1:8000. Interactive API documentation is
available at http://127.0.0.1:8000/docs (Swagger UI) and
http://127.0.0.1:8000/redoc (ReDoc).

- `GET /` returns the API name.
- `GET /health` returns `{"status": "ok"}`.

For production, run `fastapi run backend/app/main.py`.

## Services API

For the native iPhone/Android app, run FastAPI with `--host 0.0.0.0`, configure
`mobile/.env` with your computer's API address, then run `npm install` and
`npm start` in `mobile/`. Open the project in a compatible Expo Go build or a
development build on your phone. Create a service, then use **My services** to see
records saved in PostgreSQL. See [`mobile/README.md`](mobile/README.md) for the
complete device setup. The browser page at `/onboarding/` is now a read-only design preview.

| Method | Endpoint | Behavior |
| --- | --- | --- |
| POST | `/api/v1/services` | Create a service; returns `201`. |
| GET | `/api/v1/services` | List active services; returns `200`. |
| GET | `/api/v1/services/{id}` | Get an active or archived service; returns `200`. |
| PATCH | `/api/v1/services/{id}` | Update supplied fields; returns `200`. |
| DELETE | `/api/v1/services/{id}` | Set `is_active=false`; returns `204` with no body. |

All operations require login and are scoped to the owner's business. Missing services and
services belonging to a different business return `404`. Archival preserves
inquiry/quote references and historical quote item prices. Repeating DELETE is
safe. PATCH with `{"is_active": true}` restores an archived service.

List parameters: `include_archived=false`, `limit=50` (1–100), `offset=0` (nonnegative).
The response is an array ordered by `sort_order`, then `id`.

Create an example service:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/services \
  -H "Authorization: Bearer $OWNER_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Full detail","base_price_minor":15000,"estimated_duration_minutes":120}'
```

Prices use integer minor units (`15000` means USD 150.00); null means individualized
pricing. PATCH leaves omitted fields unchanged. `description`, `base_price_minor`
and `estimated_duration_minutes` can be cleared with null. Other fields cannot be
set to null. Empty patches, unknown fields and invalid values return `422`.
See [the API guide](docs/services-api.md) for configuration and additional examples.
Obtain `OWNER_TOKEN` by signing in through Swagger UI as described in the
[authentication guide](docs/authentication.md#api-contract).

## Test

```bash
python -m pip install -e '.[test]'
python -m unittest discover -s backend/tests -p 'test_*.py' -v
```

The tests compare ORM definitions with the SQL migration, validate API schemas,
and exercise the service HTTP endpoints with a SQLite service-table fixture.
To also run PostgreSQL round-trip checks, set `TEST_DATABASE_URL` to an authenticated
connection URL for a development database with the migration already applied.
This also runs the service API suite against PostgreSQL with real quote references.
PostgreSQL test fixtures are rolled back.

See the [FastAPI CLI documentation](https://fastapi.tiangolo.com/fastapi-cli/).

# Owner authentication

Owners sign up and sign in with email/password through the native mobile app.
Each account manages one business. Service endpoints require an authenticated
owner; `DEV_BUSINESS_ID` no longer grants access.

## Upgrade your existing development setup

Run these commands from `/root/projects/Leadlane` in Ubuntu/WSL. Stop the current
`dev.sh` session with Ctrl+C first. Keep PostgreSQL running.

### 1. Install dependencies

```bash
source .venv/bin/activate
python -m pip install -e '.[test]'
cd mobile
npm install
cd ..
```

The backend adds `pwdlib[argon2]`; the app adds `expo-secure-store`. Expo Go
includes the native SecureStore module. If you use a custom development build,
rebuild it after adding a native dependency.

Run `npm install` before restarting the app; it installs SecureStore and updates
the mobile dependency lockfile. The WSL launcher reports this missing dependency
directly instead of opening an app that cannot bundle.

### 2. Apply the authentication migration

The original six-table migration must already be applied. Run the new migration
once, using your configured database role and name:

```bash
psql -h localhost -p 5432 -U service_app -d service_business_dev \
  -v ON_ERROR_STOP=1 -f backend/app/db/002_owner_auth.sql
```

Enter the database password when prompted. This adds four authentication tables
and preserves existing businesses, services, contacts, inquiries and quotes.
For a fresh database, apply `001_initial.sql` first, then `002_owner_auth.sql`.

Check connectivity/schema without printing credentials:

```bash
python -m backend.app.db.check_connection
```

### 3. Create an owner for your existing business

Find the business UUID using the [database login instructions](database.md#connect-from-the-command-line):

```sql
SELECT id, name, slug FROM businesses WHERE is_active = true;
```

Then run the local setup command, replacing the example values:

```bash
python -m backend.app.cli.create_owner \
  --business-id YOUR_BUSINESS_UUID \
  --email you@example.com \
  --name "Your Name"
```

It prompts for a password twice without displaying it. Use 12–128 characters.
Passwords are never accepted as command-line arguments. This command links the
owner to the existing business; it does not move or recreate services. Repeating
it for the same owner/business does not change the password. It refuses business
takeovers or reuse of an email already attached to another account.

Public **Create an account** always creates a new business. To see the existing
development catalog, use **Sign in** with the owner created by this command.

### 4. Restart and test

```bash
bash dev.sh
```

Leave the Android Emulator open. Sign in, create a service, close/reopen the app
and check **My services**. Tap the sign-out icon in the workspace header to log out.
The root `.env` needs `DATABASE_URL`; `AUTH_SESSION_TTL_DAYS` defaults to 14.
The old `DEV_BUSINESS_ID` setting can be removed. The mobile `.env` still contains
only the API address. Never place passwords or session tokens in `EXPO_PUBLIC_`
variables.

## API contract

| Method | Endpoint | Result |
| --- | --- | --- |
| POST | `/api/v1/auth/register` | `201`: create owner + business + membership + session. |
| POST | `/api/v1/auth/login` | `200`: create a new session. |
| GET | `/api/v1/auth/me` | `200`: current owner, business, role and session expiry. |
| POST | `/api/v1/auth/logout` | `204`: revoke supplied session; repeated calls remain safe. |

Registration JSON contains `full_name`, `email`, `password` and `business_name`.
Login JSON contains `email` and `password`. Passwords are never trimmed; email
addresses are validated and normalized to lowercase. A business slug is generated
from its name with a random suffix. New businesses default to USD and UTC.

Registration/login return `access_token`, `token_type: "bearer"`, `expires_at`,
`user` (`id`, `full_name`, `email`), `business` (`id`, `name`, `slug`, `currency`,
`timezone`) and `role: "owner"`. `/me` returns the same safe identity without the
token. Responses containing identity/session data use `Cache-Control: no-store`.

All service requests and `/me` require:

```http
Authorization: Bearer YOUR_ACCESS_TOKEN
```

Missing, invalid, expired or revoked sessions return `401` with a Bearer challenge.
Disabled users cannot sign in or use sessions. Inactive memberships/businesses
return `403`. Other businesses' services return `404`. Invalid login credentials
have a generic error for known and unknown addresses. Duplicate registrations
return `409` and roll back the entire account/business creation. Validation errors
return `422` without echoing password input. Logout revokes only the supplied
session, so other devices remain signed in.

In [Swagger UI](http://127.0.0.1:8000/docs), call `/auth/login`, copy the returned
`access_token`, click **Authorize**, paste the token, then try service endpoints.

## Storage and limits

`users` stores Argon2id password hashes. `business_memberships` enforces one owner
per business and one business per owner. `auth_sessions` stores only SHA-256
digests of random 256-bit bearer tokens, plus expiry and revocation timestamps.
Sessions have a configurable absolute lifetime; there is no refresh-token flow.

The native app keeps the token in Expo SecureStore, never AsyncStorage or browser
storage. On launch it validates a remembered token with `/me`. Network failures
preserve the stored token and offer retry. A `401` removes the session and opens
sign-in. If secure persistence fails, the app explicitly reports that the current
session is memory-only and offers a retry. Logout clears local storage even if
the API is offline, and reports when remote revocation could not be confirmed.
If local secure storage itself cannot be cleared, logout reports failure and can
be retried rather than claiming the credential was removed.

Rate counters are stored in `auth_rate_limits`, shared across API workers. Both
failed and successful attempts count: login allows 10/email and 60/IP per fixed
15-minute window, while registration allows five/IP/hour. Limited requests return
`429` with `Retry-After`. Counters are committed before authentication so failed
requests cannot roll them back. Email/IP keys are hashed; windows older than one
day are pruned during authentication requests. Deployments behind a proxy must
configure trusted proxies correctly so the client IP cannot be spoofed.

The browser `/onboarding/` remains a read-only design reference; it does not offer
owner login or anonymous service creation. The API enforces authentication
independently of disabled preview controls.

## Verification and limitations

```bash
python -m unittest discover -s backend/tests -p 'test_*.py' -v
cd mobile
npm run typecheck
npm test
```

Backend tests cover registration, password hashing, uniqueness/rollback, throttling,
sessions, logout, tenant isolation and the existing-business setup command. Set
`TEST_DATABASE_URL` to a migrated development PostgreSQL database to run the
PostgreSQL suites; their fixtures are rolled back. Default HTTP tests use SQLite
fixtures, and DDL parity tests compare both migrations with ORM metadata.

Client tests cover auth transport, remembered-session restoration, expired-token
cleanup, network failures, storage errors and bearer headers on service requests.
Device testing should confirm secure persistence across app restarts and logout.

Email verification, emailed password recovery, staff accounts and business
switching are deferred. Email ownership is not verified in this version. A
deployed authentication service must use HTTPS; local emulator HTTP remains
supported, and the development app's broad HTTP transport exceptions must be
removed before release. Passwords, raw bearer tokens and token digests must not
be added to application/request logs.

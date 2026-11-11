-- Apply after 001_initial.sql. Existing business/customer/quote data is preserved.
BEGIN;

CREATE TABLE users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email varchar(254) NOT NULL UNIQUE,
    full_name varchar(200) NOT NULL CHECK (btrim(full_name) <> ''),
    password_hash text NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT users_email_normalized CHECK (email = lower(btrim(email)) AND email <> '')
);

CREATE TABLE business_memberships (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL UNIQUE REFERENCES users(id) ON DELETE RESTRICT,
    business_id uuid NOT NULL UNIQUE REFERENCES businesses(id) ON DELETE RESTRICT,
    role varchar(20) NOT NULL DEFAULT 'owner' CHECK (role = 'owner'),
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE auth_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    membership_id uuid NOT NULL REFERENCES business_memberships(id) ON DELETE CASCADE,
    token_digest bytea NOT NULL UNIQUE CHECK (octet_length(token_digest) = 32),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT auth_sessions_expiry CHECK (expires_at > created_at)
);
CREATE INDEX auth_sessions_membership_idx ON auth_sessions (membership_id);
CREATE INDEX auth_sessions_expiry_idx ON auth_sessions (expires_at);

-- Fixed-window counters are shared across API workers. Keys are SHA-256 digests,
-- never raw email addresses/IPs. Old windows are pruned during auth requests.
CREATE TABLE auth_rate_limits (
    scope varchar(20) NOT NULL,
    key_digest bytea NOT NULL CHECK (octet_length(key_digest) = 32),
    window_start timestamptz NOT NULL,
    attempts integer NOT NULL CHECK (attempts > 0),
    PRIMARY KEY (scope, key_digest, window_start)
);
CREATE INDEX auth_rate_limits_window_idx ON auth_rate_limits (window_start);

CREATE TRIGGER users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER business_memberships_updated_at BEFORE UPDATE ON business_memberships
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER auth_sessions_updated_at BEFORE UPDATE ON auth_sessions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;

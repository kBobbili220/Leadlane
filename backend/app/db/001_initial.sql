-- PostgreSQL 14+. Apply once to an empty application database.
-- psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/app/db/001_initial.sql
BEGIN;

CREATE TABLE businesses (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug varchar(100) NOT NULL UNIQUE,
    name varchar(200) NOT NULL CHECK (btrim(name) <> ''),
    email varchar(254),
    phone varchar(32),
    timezone varchar(100) NOT NULL DEFAULT 'UTC',
    currency varchar(3) NOT NULL DEFAULT 'USD' CHECK (currency ~ '^[A-Z]{3}$'),
    address jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(address) = 'object'),
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT businesses_slug_format CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$')
);

CREATE TABLE contacts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id uuid NOT NULL REFERENCES businesses(id) ON DELETE RESTRICT,
    name varchar(200) NOT NULL CHECK (btrim(name) <> ''),
    email varchar(254) CHECK (email IS NULL OR btrim(email) <> ''),
    phone varchar(32) CHECK (phone IS NULL OR btrim(phone) <> ''),
    preferred_channel varchar(10) CHECK (preferred_channel IN ('email', 'sms', 'phone')),
    notes text,
    archived_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT contacts_reachable CHECK (email IS NOT NULL OR phone IS NOT NULL),
    CONSTRAINT contacts_channel_available CHECK (
        (preferred_channel <> 'email' OR email IS NOT NULL)
        AND (preferred_channel NOT IN ('sms', 'phone') OR phone IS NOT NULL)
    ),
    CONSTRAINT contacts_tenant_id UNIQUE (business_id, id)
);

-- Deliberately nonunique: shared email addresses/phone numbers are possible.
CREATE INDEX contacts_email_idx ON contacts (business_id, lower(email)) WHERE email IS NOT NULL;
CREATE INDEX contacts_phone_idx ON contacts (business_id, phone) WHERE phone IS NOT NULL;

CREATE TABLE services (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id uuid NOT NULL REFERENCES businesses(id) ON DELETE RESTRICT,
    name varchar(200) NOT NULL CHECK (btrim(name) <> ''),
    description text,
    -- NULL means this service requires an individualized price.
    base_price_minor bigint CHECK (base_price_minor >= 0),
    estimated_duration_minutes integer CHECK (estimated_duration_minutes > 0),
    unit_label varchar(50) NOT NULL DEFAULT 'vehicle' CHECK (btrim(unit_label) <> ''),
    is_active boolean NOT NULL DEFAULT true,
    sort_order integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT services_tenant_id UNIQUE (business_id, id)
);

CREATE INDEX services_catalog_idx ON services (business_id, is_active, sort_order, id);

CREATE TABLE inquiries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id uuid NOT NULL REFERENCES businesses(id) ON DELETE RESTRICT,
    contact_id uuid NOT NULL,
    requested_service_id uuid,
    status varchar(20) NOT NULL DEFAULT 'new'
        CHECK (status IN ('new', 'reviewing', 'quoted', 'won', 'lost', 'cancelled')),
    source varchar(50) NOT NULL DEFAULT 'public_form',
    message text,
    vehicle_year smallint CHECK (vehicle_year BETWEEN 1886 AND 2200),
    vehicle_make varchar(100),
    vehicle_model varchar(100),
    vehicle_size varchar(50),
    -- Flexible condition details: pet hair, stains, paint condition, etc.
    vehicle_details jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(vehicle_details) = 'object'),
    service_address jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(service_address) = 'object'),
    preferred_start_at timestamptz,
    preferred_end_at timestamptz,
    internal_notes text,
    lost_reason text,
    closed_at timestamptz,
    -- Client-supplied retry key, scoped to one business; NULL permits normal submissions.
    submission_key varchar(128),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT inquiries_tenant_id UNIQUE (business_id, id),
    CONSTRAINT inquiries_submission_key UNIQUE (business_id, submission_key),
    CONSTRAINT inquiries_contact_fk FOREIGN KEY (business_id, contact_id)
        REFERENCES contacts(business_id, id) ON DELETE RESTRICT,
    CONSTRAINT inquiries_service_fk FOREIGN KEY (business_id, requested_service_id)
        REFERENCES services(business_id, id) ON DELETE RESTRICT,
    CONSTRAINT inquiries_preferred_window CHECK (
        preferred_end_at IS NULL OR (preferred_start_at IS NOT NULL AND preferred_end_at > preferred_start_at)
    ),
    CONSTRAINT inquiries_closed_state CHECK (
        (status IN ('won', 'lost', 'cancelled')) = (closed_at IS NOT NULL)
    )
);

CREATE INDEX inquiries_inbox_idx ON inquiries (business_id, created_at DESC, id DESC);
CREATE INDEX inquiries_status_idx ON inquiries (business_id, status, created_at DESC, id DESC);
CREATE INDEX inquiries_contact_idx ON inquiries (business_id, contact_id, created_at DESC);
CREATE INDEX inquiries_service_idx ON inquiries (business_id, requested_service_id)
    WHERE requested_service_id IS NOT NULL;

CREATE TABLE quotes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id uuid NOT NULL REFERENCES businesses(id) ON DELETE RESTRICT,
    inquiry_id uuid NOT NULL,
    revision integer NOT NULL DEFAULT 1 CHECK (revision > 0),
    status varchar(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'sent', 'accepted', 'declined', 'expired', 'superseded', 'cancelled')),
    currency varchar(3) NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    -- Snapshot the recipient; later contact edits must not change a sent quote.
    recipient_name varchar(200) NOT NULL CHECK (btrim(recipient_name) <> ''),
    recipient_email varchar(254) CHECK (recipient_email IS NULL OR btrim(recipient_email) <> ''),
    recipient_phone varchar(32) CHECK (recipient_phone IS NULL OR btrim(recipient_phone) <> ''),
    vehicle_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(vehicle_snapshot) = 'object'),
    service_address_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(service_address_snapshot) = 'object'),
    customer_notes text,
    terms text,
    -- All amounts are integer minor units: 12999 = USD 129.99.
    -- subtotal_minor must equal SUM(quote_items.line_total_minor) at send time.
    subtotal_minor bigint NOT NULL DEFAULT 0 CHECK (subtotal_minor >= 0),
    discount_minor bigint NOT NULL DEFAULT 0 CHECK (discount_minor >= 0),
    tax_minor bigint NOT NULL DEFAULT 0 CHECK (tax_minor >= 0),
    total_minor bigint GENERATED ALWAYS AS (subtotal_minor - discount_minor + tax_minor) STORED,
    -- SHA-256 digest of an application-generated cryptographically random token.
    public_token_hash bytea UNIQUE CHECK (octet_length(public_token_hash) = 32),
    sent_at timestamptz,
    expires_at timestamptz,
    viewed_at timestamptz,
    accepted_at timestamptz,
    declined_at timestamptz,
    decline_reason text,
    next_follow_up_at timestamptz,
    last_follow_up_at timestamptz,
    follow_up_count integer NOT NULL DEFAULT 0 CHECK (follow_up_count >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT quotes_tenant_id UNIQUE (business_id, id),
    CONSTRAINT quotes_revision UNIQUE (business_id, inquiry_id, revision),
    CONSTRAINT quotes_inquiry_fk FOREIGN KEY (business_id, inquiry_id)
        REFERENCES inquiries(business_id, id) ON DELETE RESTRICT,
    CONSTRAINT quotes_recipient_reachable CHECK (recipient_email IS NOT NULL OR recipient_phone IS NOT NULL),
    CONSTRAINT quotes_discount_limit CHECK (discount_minor <= subtotal_minor),
    CONSTRAINT quotes_sent_link CHECK (
        status NOT IN ('sent', 'accepted', 'declined', 'expired')
        OR (sent_at IS NOT NULL AND public_token_hash IS NOT NULL AND expires_at IS NOT NULL)
    ),
    CONSTRAINT quotes_draft_unsent CHECK (status <> 'draft' OR sent_at IS NULL),
    CONSTRAINT quotes_expiry_order CHECK (expires_at > sent_at),
    CONSTRAINT quotes_acceptance_state CHECK ((status = 'accepted') = (accepted_at IS NOT NULL)),
    CONSTRAINT quotes_decline_state CHECK ((status = 'declined') = (declined_at IS NOT NULL)),
    CONSTRAINT quotes_response_order CHECK (
        (accepted_at IS NULL OR (accepted_at >= sent_at AND accepted_at < expires_at))
        AND (declined_at IS NULL OR (declined_at >= sent_at AND declined_at < expires_at))
    ),
    CONSTRAINT quotes_follow_up_state CHECK (next_follow_up_at IS NULL OR status = 'sent')
);

CREATE INDEX quotes_inquiry_idx ON quotes (business_id, inquiry_id, created_at DESC, id DESC);
CREATE UNIQUE INDEX quotes_one_accepted_per_inquiry ON quotes (business_id, inquiry_id)
    WHERE status = 'accepted';
-- Global due-time ordering supports a worker scanning across all businesses.
CREATE INDEX quotes_follow_up_due_idx ON quotes (next_follow_up_at, id)
    WHERE status = 'sent' AND next_follow_up_at IS NOT NULL;
CREATE INDEX quotes_expiry_due_idx ON quotes (expires_at, id) WHERE status = 'sent';

CREATE TABLE quote_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id uuid NOT NULL REFERENCES businesses(id) ON DELETE RESTRICT,
    quote_id uuid NOT NULL,
    -- Nullable to allow custom work outside the catalog. Archive services rather than deleting them.
    service_id uuid,
    position integer NOT NULL CHECK (position >= 0),
    name varchar(200) NOT NULL CHECK (btrim(name) <> ''),
    description text,
    unit_label varchar(50) NOT NULL DEFAULT 'vehicle' CHECK (btrim(unit_label) <> ''),
    quantity integer NOT NULL DEFAULT 1 CHECK (quantity > 0),
    unit_price_minor bigint NOT NULL CHECK (unit_price_minor >= 0),
    line_total_minor bigint GENERATED ALWAYS AS (quantity::bigint * unit_price_minor) STORED,
    estimated_duration_minutes integer CHECK (estimated_duration_minutes > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT quote_items_position UNIQUE (business_id, quote_id, position),
    CONSTRAINT quote_items_quote_fk FOREIGN KEY (business_id, quote_id)
        REFERENCES quotes(business_id, id) ON DELETE CASCADE,
    CONSTRAINT quote_items_service_fk FOREIGN KEY (business_id, service_id)
        REFERENCES services(business_id, id) ON DELETE RESTRICT
);

CREATE INDEX quote_items_service_idx ON quote_items (business_id, service_id) WHERE service_id IS NOT NULL;

CREATE FUNCTION set_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = clock_timestamp();
    RETURN NEW;
END;
$$;

CREATE TRIGGER businesses_updated_at BEFORE UPDATE ON businesses
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER contacts_updated_at BEFORE UPDATE ON contacts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER services_updated_at BEFORE UPDATE ON services
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER inquiries_updated_at BEFORE UPDATE ON inquiries
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER quotes_updated_at BEFORE UPDATE ON quotes
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER quote_items_updated_at BEFORE UPDATE ON quote_items
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;

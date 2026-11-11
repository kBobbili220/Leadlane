-- Apply backend/app/db/001_initial.sql first, then run with psql -v ON_ERROR_STOP=1.
-- All fixture data is rolled back, including on success.
BEGIN;
DO $$
DECLARE
    a uuid := gen_random_uuid();
    b uuid := gen_random_uuid();
    customer uuid := gen_random_uuid();
    service uuid := gen_random_uuid();
    other_service uuid := gen_random_uuid();
    lead uuid := gen_random_uuid();
    quote uuid := gen_random_uuid();
    second_quote uuid := gen_random_uuid();
    item uuid := gen_random_uuid();
    amount bigint;
BEGIN
    INSERT INTO businesses (id, slug, name) VALUES
        (a, 'test-' || a::text, 'Detailer A'), (b, 'test-' || b::text, 'Detailer B');
    INSERT INTO contacts (id, business_id, name, email)
        VALUES (customer, a, 'Customer', 'customer@example.com');
    INSERT INTO services (id, business_id, name, base_price_minor) VALUES
        (service, a, 'Full detail', 15000), (other_service, b, 'Other business service', 20000);
    INSERT INTO inquiries (id, business_id, contact_id, requested_service_id, submission_key)
        VALUES (lead, a, customer, service, 'submission-1');

    BEGIN
        INSERT INTO inquiries (business_id, contact_id) VALUES (b, customer);
        RAISE EXCEPTION 'Cross-business contact reference was allowed';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
    BEGIN
        UPDATE inquiries SET requested_service_id = other_service WHERE id = lead;
        RAISE EXCEPTION 'Cross-business inquiry service was allowed';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO inquiries (business_id, contact_id, submission_key) VALUES (a, customer, 'submission-1');
        RAISE EXCEPTION 'Duplicate inquiry retry key was allowed';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;

    INSERT INTO quotes (id, business_id, inquiry_id, currency, recipient_name, recipient_email,
                        subtotal_minor, discount_minor, tax_minor)
        VALUES (quote, a, lead, 'USD', 'Customer', 'customer@example.com', 30000, 1000, 2320);
    INSERT INTO quote_items (id, business_id, quote_id, service_id, position, name, quantity, unit_price_minor)
        VALUES (item, a, quote, service, 0, 'Full detail', 2, 15000);
    SELECT line_total_minor INTO amount FROM quote_items WHERE id = item;
    IF amount <> 30000 THEN RAISE EXCEPTION 'Incorrect line total: %', amount; END IF;
    SELECT total_minor INTO amount FROM quotes WHERE id = quote;
    IF amount <> 31320 THEN RAISE EXCEPTION 'Incorrect quote total: %', amount; END IF;

    BEGIN
        UPDATE quotes SET business_id = b WHERE id = quote;
        RAISE EXCEPTION 'Cross-business quote inquiry was allowed';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
    BEGIN
        UPDATE quote_items SET service_id = other_service WHERE id = item;
        RAISE EXCEPTION 'Cross-business quote item service was allowed';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
    BEGIN
        UPDATE quote_items SET business_id = b, service_id = NULL WHERE id = item;
        RAISE EXCEPTION 'Cross-business quote item quote was allowed';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
    BEGIN
        UPDATE quote_items SET quantity = 0 WHERE id = item;
        RAISE EXCEPTION 'Zero quantity was allowed';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        UPDATE quotes SET discount_minor = 30001 WHERE id = quote;
        RAISE EXCEPTION 'Discount exceeding subtotal was allowed';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        UPDATE quotes SET status = 'sent' WHERE id = quote;
        RAISE EXCEPTION 'Sending without a token and expiry was allowed';
    EXCEPTION WHEN check_violation THEN NULL;
    END;

    UPDATE services SET name = 'New catalog name', base_price_minor = 17000 WHERE id = service;
    SELECT unit_price_minor INTO amount FROM quote_items WHERE id = item;
    IF amount <> 15000 THEN RAISE EXCEPTION 'Catalog changes altered quote price'; END IF;

    INSERT INTO quotes (id, business_id, inquiry_id, revision, currency, recipient_name, recipient_email)
        VALUES (second_quote, a, lead, 2, 'USD', 'Customer', 'customer@example.com');
    UPDATE quotes SET status = 'sent', sent_at = now(), expires_at = now() + interval '7 days',
        public_token_hash = decode(repeat('ab', 32), 'hex') WHERE id = quote;
    UPDATE quotes SET status = 'accepted', accepted_at = now() WHERE id = quote;
    BEGIN
        UPDATE quotes SET status = 'accepted', accepted_at = now(), sent_at = now(),
            expires_at = now() + interval '7 days', public_token_hash = decode(repeat('cd', 32), 'hex')
            WHERE id = second_quote;
        RAISE EXCEPTION 'Multiple accepted quotes were allowed for one inquiry';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    BEGIN
        DELETE FROM services WHERE id = service;
        RAISE EXCEPTION 'Deletion of a referenced service was allowed';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
    UPDATE inquiries SET status = 'won', closed_at = now() WHERE id = lead;
    RAISE NOTICE 'Schema smoke checks passed';
END;
$$;
ROLLBACK;

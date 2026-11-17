-- Run through migrate.py, after registering the initial user.
-- Locks prevent registration or chat writes from racing the owner selection.
LOCK TABLE users IN SHARE MODE;
LOCK TABLE conversations IN ACCESS EXCLUSIVE MODE;

DO $$
DECLARE
    selected_owner BIGINT := NULLIF(current_setting('app.migration_owner_id', true), '')::BIGINT;
    user_count BIGINT;
BEGIN
    IF selected_owner IS NOT NULL THEN
        IF NOT EXISTS (SELECT 1 FROM users WHERE id = selected_owner) THEN
            RAISE EXCEPTION 'Selected owner does not exist.';
        END IF;
    ELSE
        SELECT COUNT(*), MIN(id) INTO user_count, selected_owner FROM users;
        IF user_count = 0 THEN
            RAISE EXCEPTION 'No registered users. Register first, then rerun ownership migration.';
        ELSIF user_count > 1 THEN
            RAISE EXCEPTION 'More than one registered user. Rerun with --owner-id ID to explicitly select the existing-history owner.';
        END IF;
    END IF;

    ALTER TABLE conversations ADD COLUMN user_id BIGINT;
    UPDATE conversations SET user_id = selected_owner;
    ALTER TABLE conversations ADD CONSTRAINT conversations_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES users(id);
    ALTER TABLE conversations ALTER COLUMN user_id SET NOT NULL;
END;
$$;

CREATE INDEX conversations_user_updated_idx ON conversations (user_id, updated_at DESC);
INSERT INTO schema_migrations (version) VALUES (2);

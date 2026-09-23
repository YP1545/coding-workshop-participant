-- GENERATED FILE — do not edit by hand.
--
-- Produced by deploy/generate-schema.sh from the Alembic migrations in
-- backend/_shared/alembic/versions. Re-run that script after adding a
-- migration; editing this file directly makes it disagree with models.py.
--
-- What it contains: every table, enum type, index, constraint and the
-- seeded incident_categories rows, wrapped in one transaction, plus the
-- alembic_version stamp so Alembic can still take over later.
--
-- Generated: 2026-09-23T19:18:59Z
-- Head revision: b1d47e93c6a2 (head)

BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 2607896d33fb

CREATE TABLE buildings (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    name TEXT NOT NULL, 
    address TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_buildings PRIMARY KEY (id)
);

CREATE TYPE user_role AS ENUM ('employee', 'facility_admin', 'engineer');

CREATE TABLE users (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    email TEXT NOT NULL, 
    password_hash TEXT NOT NULL, 
    full_name TEXT NOT NULL, 
    role user_role DEFAULT 'employee' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_users PRIMARY KEY (id), 
    CONSTRAINT ck_users_email_domain CHECK (email ~* '^[A-Za-z0-9._%+-]+@acme\.inc$'), 
    CONSTRAINT uq_users_email UNIQUE (email)
);

CREATE UNIQUE INDEX uq_users_email_lower ON users (lower(email));

CREATE TYPE availability_status AS ENUM ('available', 'busy', 'off');

CREATE TABLE engineer_profiles (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    user_id UUID NOT NULL, 
    specialty TEXT, 
    availability availability_status DEFAULT 'available' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_engineer_profiles PRIMARY KEY (id), 
    CONSTRAINT fk_engineer_profiles_user_id FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_engineer_profiles_user_id UNIQUE (user_id)
);

CREATE INDEX idx_engineer_profiles_availability ON engineer_profiles (availability);

CREATE TABLE floors (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    building_id UUID NOT NULL, 
    name TEXT NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_floors PRIMARY KEY (id), 
    CONSTRAINT fk_floors_building_id FOREIGN KEY(building_id) REFERENCES buildings (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_floors_building_id_name UNIQUE (building_id, name)
);

CREATE INDEX idx_floors_building_id ON floors (building_id);

CREATE TABLE seats (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    floor_id UUID NOT NULL, 
    label TEXT NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_seats PRIMARY KEY (id), 
    CONSTRAINT fk_seats_floor_id FOREIGN KEY(floor_id) REFERENCES floors (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_seats_floor_id_label UNIQUE (floor_id, label)
);

CREATE INDEX idx_seats_floor_id ON seats (floor_id);

CREATE TYPE incident_category AS ENUM ('hvac', 'electrical', 'plumbing', 'furniture', 'network', 'hardware', 'software', 'access_security', 'other');

CREATE TYPE incident_status AS ENUM ('open', 'in_progress', 'blocked', 'resolved', 'closed');

CREATE TYPE incident_priority AS ENUM ('low', 'medium', 'high', 'urgent');

CREATE TABLE incidents (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    title TEXT NOT NULL, 
    description TEXT NOT NULL, 
    category incident_category DEFAULT 'other' NOT NULL, 
    status incident_status DEFAULT 'open' NOT NULL, 
    priority incident_priority DEFAULT 'medium' NOT NULL, 
    building_id UUID, 
    floor_id UUID, 
    seat_id UUID, 
    reporter_id UUID NOT NULL, 
    assignee_id UUID, 
    escalation_requested BOOLEAN DEFAULT false NOT NULL, 
    escalated BOOLEAN DEFAULT false NOT NULL, 
    escalation_reason TEXT, 
    blocked_reason TEXT, 
    acknowledged_at TIMESTAMP WITH TIME ZONE, 
    assigned_at TIMESTAMP WITH TIME ZONE, 
    resolved_at TIMESTAMP WITH TIME ZONE, 
    closed_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_incidents PRIMARY KEY (id), 
    CONSTRAINT fk_incidents_assignee_id FOREIGN KEY(assignee_id) REFERENCES engineer_profiles (id) ON DELETE SET NULL, 
    CONSTRAINT fk_incidents_building_id FOREIGN KEY(building_id) REFERENCES buildings (id) ON DELETE SET NULL, 
    CONSTRAINT fk_incidents_floor_id FOREIGN KEY(floor_id) REFERENCES floors (id) ON DELETE SET NULL, 
    CONSTRAINT fk_incidents_reporter_id FOREIGN KEY(reporter_id) REFERENCES users (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_incidents_seat_id FOREIGN KEY(seat_id) REFERENCES seats (id) ON DELETE SET NULL
);

CREATE INDEX idx_incidents_assignee_id ON incidents (assignee_id);

CREATE INDEX idx_incidents_building_id ON incidents (building_id);

CREATE INDEX idx_incidents_category ON incidents (category);

CREATE INDEX idx_incidents_floor_id ON incidents (floor_id);

CREATE INDEX idx_incidents_priority ON incidents (priority);

CREATE INDEX idx_incidents_reporter_id ON incidents (reporter_id);

CREATE INDEX idx_incidents_seat_id ON incidents (seat_id);

CREATE INDEX idx_incidents_status ON incidents (status);

CREATE TYPE assignment_request_status AS ENUM ('pending', 'approved', 'denied');

CREATE TABLE incident_assignment_requests (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    incident_id UUID NOT NULL, 
    engineer_id UUID NOT NULL, 
    status assignment_request_status DEFAULT 'pending' NOT NULL, 
    requested_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    decided_at TIMESTAMP WITH TIME ZONE, 
    decided_by UUID, 
    CONSTRAINT pk_incident_assignment_requests PRIMARY KEY (id), 
    CONSTRAINT fk_incident_assignment_requests_decided_by FOREIGN KEY(decided_by) REFERENCES users (id) ON DELETE SET NULL, 
    CONSTRAINT fk_incident_assignment_requests_engineer_id FOREIGN KEY(engineer_id) REFERENCES engineer_profiles (id) ON DELETE CASCADE, 
    CONSTRAINT fk_incident_assignment_requests_incident_id FOREIGN KEY(incident_id) REFERENCES incidents (id) ON DELETE CASCADE, 
    CONSTRAINT uq_assignment_requests_incident_engineer UNIQUE (incident_id, engineer_id)
);

CREATE INDEX idx_assignment_requests_engineer_id ON incident_assignment_requests (engineer_id);

CREATE INDEX idx_assignment_requests_incident_id ON incident_assignment_requests (incident_id);

CREATE INDEX idx_assignment_requests_status ON incident_assignment_requests (status);

CREATE TABLE incident_notes (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    incident_id UUID NOT NULL, 
    author_id UUID NOT NULL, 
    body TEXT NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_incident_notes PRIMARY KEY (id), 
    CONSTRAINT fk_incident_notes_author_id FOREIGN KEY(author_id) REFERENCES users (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_incident_notes_incident_id FOREIGN KEY(incident_id) REFERENCES incidents (id) ON DELETE CASCADE
);

CREATE INDEX idx_incident_notes_incident_id ON incident_notes (incident_id);

CREATE TABLE incident_status_history (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    incident_id UUID NOT NULL, 
    from_status incident_status, 
    to_status incident_status NOT NULL, 
    changed_by UUID NOT NULL, 
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_incident_status_history PRIMARY KEY (id), 
    CONSTRAINT fk_incident_status_history_changed_by FOREIGN KEY(changed_by) REFERENCES users (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_incident_status_history_incident_id FOREIGN KEY(incident_id) REFERENCES incidents (id) ON DELETE CASCADE
);

CREATE INDEX idx_incident_status_history_incident_id ON incident_status_history (incident_id);

INSERT INTO alembic_version (version_num) VALUES ('2607896d33fb') RETURNING alembic_version.version_num;

-- Running upgrade 2607896d33fb -> 8f3c21a4d5e7

CREATE SEQUENCE incident_reference_seq START 1;

ALTER TABLE incidents ADD COLUMN reference TEXT;

UPDATE incidents AS target
        SET reference = 'INC-' || lpad(ordered.position::text, 4, '0')
        FROM (
            SELECT id, row_number() OVER (ORDER BY created_at, id) AS position
            FROM incidents
        ) AS ordered
        WHERE target.id = ordered.id;

SELECT setval('incident_reference_seq', GREATEST((SELECT count(*) FROM incidents), 1));

ALTER TABLE incidents ALTER COLUMN reference SET NOT NULL;

ALTER TABLE incidents ALTER COLUMN reference SET DEFAULT 'INC-' || lpad(nextval('incident_reference_seq')::text, 4, '0');

CREATE UNIQUE INDEX uq_incidents_reference ON incidents (reference);

UPDATE alembic_version SET version_num='8f3c21a4d5e7' WHERE alembic_version.version_num = '2607896d33fb';

-- Running upgrade 8f3c21a4d5e7 -> b1d47e93c6a2

CREATE TABLE incident_categories (
    slug TEXT NOT NULL, 
    name TEXT NOT NULL, 
    sort_order INTEGER DEFAULT 100 NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_incident_categories PRIMARY KEY (slug)
);

INSERT INTO incident_categories (slug, name, sort_order) VALUES ('hvac', 'Heating, ventilation and air conditioning', 10);

INSERT INTO incident_categories (slug, name, sort_order) VALUES ('electrical', 'Electrical', 20);

INSERT INTO incident_categories (slug, name, sort_order) VALUES ('plumbing', 'Plumbing', 30);

INSERT INTO incident_categories (slug, name, sort_order) VALUES ('furniture', 'Furniture', 40);

INSERT INTO incident_categories (slug, name, sort_order) VALUES ('network', 'Network', 50);

INSERT INTO incident_categories (slug, name, sort_order) VALUES ('hardware', 'Hardware', 60);

INSERT INTO incident_categories (slug, name, sort_order) VALUES ('software', 'Software', 70);

INSERT INTO incident_categories (slug, name, sort_order) VALUES ('access_security', 'Access and security', 80);

INSERT INTO incident_categories (slug, name, sort_order) VALUES ('other', 'Other', 90);

ALTER TABLE incidents ALTER COLUMN category DROP DEFAULT;

ALTER TABLE incidents ALTER COLUMN category TYPE TEXT USING category::text;

ALTER TABLE incidents ALTER COLUMN category SET DEFAULT 'other';

ALTER TABLE incidents ADD CONSTRAINT fk_incidents_category FOREIGN KEY(category) REFERENCES incident_categories (slug) ON DELETE RESTRICT;

DROP TYPE IF EXISTS incident_category;

UPDATE alembic_version SET version_num='b1d47e93c6a2' WHERE alembic_version.version_num = '8f3c21a4d5e7';

COMMIT;


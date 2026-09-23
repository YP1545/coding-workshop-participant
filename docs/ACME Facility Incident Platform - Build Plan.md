# ACME Facility Incident Platform — Build Plan

2026-09-22

## Step 1 — Requirements

Twenty-five requirements come out of the brief and the workshop's Full Stack Guide, split into what's graded as core scope, what's expected but flexible, and what's cut for the MVP.

### Must

1. Employees register only with an `@acme.inc` email address.
2. Employees can create incidents, view their own incidents, and add notes to open incidents.
3. Employees can request a priority change or escalation on their own incidents.
4. Facility Admins can create, edit, and remove buildings, floors, and seats.
5. Facility Admins can create engineer profiles and assign incidents to engineers.
6. Facility Admins can view and manage the full incident lifecycle across all incidents.
7. Engineers can view their assigned incidents, update status, and add notes.
8. Incident workflow enforces five statuses: Open, In Progress, Blocked, Resolved, Closed.
9. The UI shows the workflow visually (a status stepper or board), not just a status label.
10. Each persona has a dashboard with ticket counts by status, priority, and assignee.
11. Users can search and filter incidents by status, priority, category, building/floor/seat, and assignee.
12. The UI is responsive across mobile and desktop (React Responsive + MUI breakpoints).
13. Authentication is token-based (JWT), with password hashing and role-based access control.
14. CRUD is fully implemented for incidents, facilities, engineer profiles, and incident notes.
15. The stack is fixed: React + Vite + MUI frontend, Python backend, PostgreSQL storage — no substitutions.
16. Deployment targets AWS Serverless (S3 + CloudFront, Lambda, RDS) via Terraform and shell scripts.
17. No external system integrations are in scope for the MVP.
18. Backend and frontend test coverage meet the guide's stated thresholds (see Step 6).

### Should

19. Dashboards answer the seven business questions from the brief: open-incident status, recurring-issue hotspots by location, time-to-acknowledge/assign/resolve, engineer workload and availability, issue-category breakdown, escalated/blocked incidents with reasons, and employees' visibility into ticket progress.
20. An incident status history is recorded (who changed what, when) — it's what makes the acknowledge/assign/resolve timing metrics real instead of guessed.
21. Engineers set their own availability (available / busy / off) so admins see real workload data.
22. Blocked and escalated incidents carry a required reason, since the brief calls out "why" specifically.

### Won't (MVP cut)

23. No email/Slack notifications — "how effectively are employees informed" is answered with in-app status visibility and the notes thread, since no integration is in scope.
24. No admin-managed category taxonomy — issue categories ship as a fixed enum for v1 (flagged in Decisions to confirm).
25. No SLA-breach alerting — timing metrics are reported, not enforced.

The brief is explicit that PostgreSQL is the required database (not MongoDB/DocumentDB, which the guide only lists as an optional path for other cohorts), so the plan below has no Mongo fallback.

## Step 2 — Data model (PostgreSQL)

Eight tables model the three personas, the building/floor/seat hierarchy, and the incident lifecycle, with ownership (`reporter_id`) and assignment (`assignee_id`) as explicit foreign keys so authorization is a query filter, not an afterthought.

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto; -- gen_random_uuid()

CREATE TYPE user_role AS ENUM ('employee', 'facility_admin', 'engineer');
CREATE TYPE availability_status AS ENUM ('available', 'busy', 'off');
CREATE TYPE incident_status AS ENUM ('open', 'in_progress', 'blocked', 'resolved', 'closed');
CREATE TYPE incident_priority AS ENUM ('low', 'medium', 'high', 'urgent');
CREATE TYPE incident_category AS ENUM ('hvac', 'electrical', 'plumbing', 'furniture', 'network', 'hardware', 'software', 'access_security', 'other');
CREATE TYPE assignment_request_status AS ENUM ('pending', 'approved', 'denied');

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL UNIQUE CHECK (email ~* '^[A-Za-z0-9._%+-]+@acme\.inc$'),
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role user_role NOT NULL DEFAULT 'employee',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE engineer_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    specialty TEXT,
    availability availability_status NOT NULL DEFAULT 'available',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_engineer_profiles_availability ON engineer_profiles(availability);

CREATE TABLE buildings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    address TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE floors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    building_id UUID NOT NULL REFERENCES buildings(id) ON DELETE RESTRICT,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (building_id, name)
);
CREATE INDEX idx_floors_building_id ON floors(building_id);

CREATE TABLE seats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    floor_id UUID NOT NULL REFERENCES floors(id) ON DELETE RESTRICT,
    label TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (floor_id, label)
);
CREATE INDEX idx_seats_floor_id ON seats(floor_id);

CREATE TABLE incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category incident_category NOT NULL DEFAULT 'other',
    status incident_status NOT NULL DEFAULT 'open',
    priority incident_priority NOT NULL DEFAULT 'medium',
    building_id UUID REFERENCES buildings(id) ON DELETE SET NULL,
    floor_id UUID REFERENCES floors(id) ON DELETE SET NULL,
    seat_id UUID REFERENCES seats(id) ON DELETE SET NULL,
    reporter_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    assignee_id UUID REFERENCES engineer_profiles(id) ON DELETE SET NULL,
    escalation_requested BOOLEAN NOT NULL DEFAULT false,
    escalated BOOLEAN NOT NULL DEFAULT false,
    escalation_reason TEXT,
    blocked_reason TEXT,
    acknowledged_at TIMESTAMPTZ,
    assigned_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_incidents_reporter_id ON incidents(reporter_id);
CREATE INDEX idx_incidents_assignee_id ON incidents(assignee_id);
CREATE INDEX idx_incidents_status ON incidents(status);
CREATE INDEX idx_incidents_priority ON incidents(priority);
CREATE INDEX idx_incidents_building_id ON incidents(building_id);
CREATE INDEX idx_incidents_floor_id ON incidents(floor_id);
CREATE INDEX idx_incidents_seat_id ON incidents(seat_id);
CREATE INDEX idx_incidents_category ON incidents(category);

CREATE TABLE incident_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    author_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_incident_notes_incident_id ON incident_notes(incident_id);

CREATE TABLE incident_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    from_status incident_status,
    to_status incident_status NOT NULL,
    changed_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_incident_status_history_incident_id ON incident_status_history(incident_id);

CREATE TABLE incident_assignment_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    engineer_id UUID NOT NULL REFERENCES engineer_profiles(id) ON DELETE CASCADE,
    status assignment_request_status NOT NULL DEFAULT 'pending',
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_at TIMESTAMPTZ,
    decided_by UUID REFERENCES users(id) ON DELETE SET NULL,
    UNIQUE (incident_id, engineer_id)
);
CREATE INDEX idx_assignment_requests_incident_id ON incident_assignment_requests(incident_id);
CREATE INDEX idx_assignment_requests_engineer_id ON incident_assignment_requests(engineer_id);
CREATE INDEX idx_assignment_requests_status ON incident_assignment_requests(status);
```

Key decisions: `engineer_profiles` is a 1:1 extension of `users` (role = `engineer`) rather than a separate identity, so an engineer logs in with the same account an admin provisions. `building_id`/`floor_id`/`seat_id` on `incidents` are nullable and independently set (not a strict chain) because a technology issue may only have a seat, or only a building. Schema changes after the first migration go through Alembic, not hand edits.

`incident_assignment_requests` backs the new engineer self-assign flow: an engineer requests an unassigned incident, a Facility Admin approves or denies it, and approving writes `incidents.assignee_id`/`assigned_at` and auto-denies that incident's other pending requests. Admins keep the existing direct `PATCH /incidents/{id}/assign` too, so they're never blocked waiting on a request.

## Step 3 — API contract

The contract is RESTful, one level of nesting deep, ids are UUID strings throughout, and errors always return `{"detail": "..."}` with 400 (validation), 401 (unauthenticated), 403 (forbidden), 404 (not found), or 409 (conflict). This is what the frontend, tests, and Postman collection are built against — it should not change after this plan is approved.

### Auth

| Method | Path | Auth | Request → Response |
| --- | --- | --- | --- |
| POST | `/auth/register` | none | `{email, password, full_name}` → 201 `{user}` (rejects non-`@acme.inc` emails, 400) |
| POST | `/auth/login` | none | `{email, password}` → 200 `{access_token, token_type, user}` |
| GET | `/auth/me` | any | — → 200 `{user}` |

### Users (admin)

| Method | Path | Auth | Request → Response |
| --- | --- | --- | --- |
| GET | `/users` | facility\_admin | `?role=` → 200 `[user]` |
| PATCH | `/users/{id}/role` | facility\_admin | `{role}` → 200 `{user}` |

### Facilities

| Method | Path | Auth | Request → Response |
| --- | --- | --- | --- |
| POST | `/buildings` | facility\_admin | `{name, address?}` → 201 `{building}` |
| GET | `/buildings` | any | → 200 `[building]` |
| GET | `/buildings/{id}` | any | → 200 `{building}` |
| PUT | `/buildings/{id}` | facility\_admin | `{name, address?}` → 200 `{building}` |
| DELETE | `/buildings/{id}` | facility\_admin | → 204 (409 if floors reference it) |
| POST | `/buildings/{building_id}/floors` | facility\_admin | `{name}` → 201 `{floor}` |
| GET | `/buildings/{building_id}/floors` | any | → 200 `[floor]` |
| PUT | `/floors/{id}` | facility\_admin | `{name}` → 200 `{floor}` |
| DELETE | `/floors/{id}` | facility\_admin | → 204 (409 if seats reference it) |
| POST | `/floors/{floor_id}/seats` | facility\_admin | `{label}` → 201 `{seat}` |
| GET | `/floors/{floor_id}/seats` | any | → 200 `[seat]` |
| PUT | `/seats/{id}` | facility\_admin | `{label}` → 200 `{seat}` |
| DELETE | `/seats/{id}` | facility\_admin | → 204 |

### Engineers

| Method | Path | Auth | Request → Response |
| --- | --- | --- | --- |
| POST | `/engineers` | facility\_admin | `{user_id}` or `{email, full_name}` → 201 `{engineer_profile}` |
| GET | `/engineers` | any | `?availability=` → 200 `[engineer_profile]` |
| GET | `/engineers/{id}` | any | → 200 `{engineer_profile}` |
| PUT | `/engineers/{id}` | facility\_admin, or engineer (self, `availability` only) | → 200 `{engineer_profile}` |
| DELETE | `/engineers/{id}` | facility\_admin | → 204 |

### Incidents

| Method | Path | Auth | Request → Response |
| --- | --- | --- | --- |
| POST | `/incidents` | employee | `{title, description, category, building_id?, floor_id?, seat_id?}` → 201 `{incident}` (`reporter_id` = self, `status` = open) |
| GET | `/incidents` | any, scoped by role | `?status=&priority=&category=&building_id=&assignee_id=&escalated=` → 200 `[incident]` (employee: own only; engineer: assigned incidents plus unassigned open incidents, so they can browse and request them; admin: all) |
| GET | `/incidents/{id}` | owner, assignee, or admin | → 200 `{incident}` |
| PUT | `/incidents/{id}` | role-scoped field set (see below) | → 200 `{incident}` |
| PATCH | `/incidents/{id}/status` | engineer (assignee) or facility\_admin | `{status}` → 200 `{incident}` (400 on an invalid transition) |
| PATCH | `/incidents/{id}/assign` | facility\_admin | `{assignee_id}` → 200 `{incident}` (direct assignment; bypasses the request/approve flow below) |
| PATCH | `/incidents/{id}/escalate` | employee (request) or facility\_admin (set) | `{escalation_requested?, escalated?, escalation_reason?}` → 200 `{incident}` |
| DELETE | `/incidents/{id}` | facility\_admin | → 204 |

### Assignment requests

Engineers browse unassigned incidents and ask to take them, rather than every ticket being pushed by an admin; a Facility Admin still approves or denies each request.

| Method | Path | Auth | Request → Response |
| --- | --- | --- | --- |
| POST | `/incidents/{incident_id}/assignment-requests` | engineer | — → 201 `{assignment_request}` (409 if that engineer already has a pending request on this incident) |
| GET | `/incidents/{incident_id}/assignment-requests` | facility\_admin, or the requesting engineer (own request only) | → 200 `[assignment_request]` |
| GET | `/assignment-requests` | facility\_admin | `?status=` → 200 `[assignment_request]` (queue across all incidents) |
| GET | `/engineers/me/assignment-requests` | engineer | `?status=` → 200 `[assignment_request]` (their own requests, any incident) |
| PATCH | `/assignment-requests/{id}` | facility\_admin | `{status: "approved" \| "denied"}` → 200 `{assignment_request}` (approving sets `incidents.assignee_id`/`assigned_at` and auto-denies the incident's other pending requests) |

### Notes

| Method | Path | Auth | Request → Response |
| --- | --- | --- | --- |
| POST | `/incidents/{incident_id}/notes` | reporter, assignee, or admin | `{body}` → 201 `{note}` |
| GET | `/incidents/{incident_id}/notes` | reporter, assignee, or admin | → 200 `[note]` |

### Dashboard and health

| Method | Path | Auth | Request → Response |
| --- | --- | --- | --- |
| GET | `/dashboard/summary` | any, scoped by role | → 200 `{counts_by_status, counts_by_priority, counts_by_assignee, avg_time_to_acknowledge, avg_time_to_resolve, top_locations, category_breakdown, escalated_blocked}` |
| GET | `/health` | none | → 200 `{status: "ok"}` |

## Step 4 — Frontend map

An `AuthContext`/`useAuth` hook holds the JWT (in memory + `localStorage`) and exposes `login`/`logout`/`user`/`role`; a `ProtectedRoute` wrapper checks the token and, where needed, the role, redirecting to `/login` otherwise. An `api/` layer (`authApi`, `incidentsApi`, `facilitiesApi`, `engineersApi`, `dashboardApi`) owns the base URL and attaches the `Authorization: Bearer` header.

| Page (route) | Who | Components | API calls |
| --- | --- | --- | --- |
| `/login`, `/register` | public | `LoginForm`, `RegisterForm` | `POST /auth/login`, `POST /auth/register` |
| `/dashboard` | all (content varies by role) | `DashboardStats`, `StatCard`, `WorkflowChart` | `GET /dashboard/summary` |
| `/incidents` | all (scoped by role) | `SearchFilterBar`, `IncidentList`, `IncidentCard` (adds a "Request assignment" quick action for engineers on unassigned incidents) | `GET /incidents`, `POST /incidents/:id/assignment-requests` |
| `/incidents/new` | employee | `IncidentForm` | `POST /incidents`, `GET /buildings`/`floors`/`seats` |
| `/incidents/:id` | owner, assignee, or admin | `IncidentDetail`, `WorkflowVisualization`, `NotesThread`, status/assign/escalate action panels, `AssignmentRequestPanel` (engineer: request button; admin: approve/deny pending requests) — all rendered per role | `GET /incidents/:id`, `PUT`/`PATCH` variants, `GET`/`POST /incidents/:id/notes`, `POST`/`GET /incidents/:id/assignment-requests`, `PATCH /assignment-requests/:id` |
| `/assignment-requests` | facility\_admin | `AssignmentRequestQueue`, `AssignmentRequestCard` | `GET /assignment-requests`, `PATCH /assignment-requests/:id` |
| `/facilities` | facility\_admin | `FacilityTree` (buildings › floors › seats), inline create/edit/delete forms | full `/buildings`, `/floors`, `/seats` CRUD |
| `/engineers` | facility\_admin (manage), engineer (self) | `EngineerTable`, `EngineerAvailabilityToggle`, `EngineerForm` | full `/engineers` CRUD |
| `/profile` | all | `ProfileCard`, availability toggle (engineer only) | `GET /auth/me`, `PUT /engineers/:id` (engineer) |

`WorkflowVisualization` renders the five-status pipeline (Open → In Progress → Blocked → Resolved → Closed) as a stepper or small board on the incident detail page — this is the "visual representation of the ticket workflow" MVP requirement, not just a status chip. The component tree stays shallow: pages own data fetching and pass props down; no component both fetches and owns unrelated UI state. Responsive layout uses MUI's `Grid`/`Stack` breakpoints plus `react-responsive` for the few places (the facility tree, the incident board) that need a genuinely different layout on mobile rather than just reflow.

## Step 5 — Infrastructure topology

The workshop's own scaffold already gives per-service Lambdas behind API Gateway, S3 + CloudFront for the frontend, and Aurora RDS PostgreSQL — matching the brief's "AWS Serverless" target exactly, and matching the architecture diagram in the Full Stack Guide (the diagram's DocumentDB path is unused since this brief mandates Postgres). The client hits CloudFront for the UI and API Gateway/Lambda directly for the API; Lambda reads/writes Aurora Postgres inside the VPC.

### Backend services (one Lambda each, via the scaffold)

Using the guide's `cp -R ../backend/_examples/python-service ../backend/{{service-name}}` pattern:

- `users-service` — auth (register/login/me), user role management
- `facilities-service` — buildings, floors, seats
- `engineers-service` — engineer profiles
- `incidents-service` — incidents, notes, status transitions, and the dashboard aggregation endpoint (kept in this service since it queries the same tables)

Each is created and wired into `../bin/start-dev.sh` for local development, then deployed independently by the workshop's `../bin/deploy-backend.sh`.

### Environment variables (injected automatically per the guide)

| Variable | Local | Cloud |
| --- | --- | --- |
| `IS_LOCAL` | `true` | `false` |
| `POSTGRES_HOST` | `localhost` | Aurora endpoint |
| `POSTGRES_PORT` | `5432` | `5432` |
| `POSTGRES_NAME`/`USER`/`PASS` | set locally | Aurora values |

Connection logic branches on `IS_LOCAL`: no SSL locally, `sslmode=require` appended to the connection string when `IS_LOCAL` is `false`. No `MONGO_*` variables are needed since this build is Postgres-only.

### Terraform layout

The workshop scaffold is expected to already provide the base Terraform (network, Aurora instance, S3/CloudFront, API Gateway wiring) — see Decisions to confirm. What this plan adds per service: a `lambda.tf` entry (or module call) per backend service, IAM scoped to that service's needs only (least-privilege, not a shared admin role), and `outputs.tf` values the frontend build needs (API base URL(s), CloudFront distribution id, S3 bucket name).

### Deploy flow

1. `../bin/deploy-backend.sh` — packages and deploys each Lambda service, applies Terraform for backend resources.
2. Frontend build (`npm run build`) picks up the deployed API URL(s) via a build-time env var, then syncs to S3 and invalidates CloudFront.
3. Post-deploy smoke test: `GET /health` on each service through the public API URL, then a full register → login → create incident → assign → resolve round trip against the deployed stack.

Cost/teardown: `terraform destroy` tears down Lambda, API Gateway, and Aurora; CloudFront/S3 teardown follows the workshop's own scaffold conventions since this brief states no resource-naming or tagging scheme of its own (see Decisions to confirm).

## Step 6 — Phase plan

Nine branches, each ending with something runnable. Time estimates assume a \~3-day workshop (roughly 24 working hours); confirm the actual timebox (Decisions to confirm) and rescale.

| Phase (branch) | Goal | Verify | Est. time |
| --- | --- | --- | --- |
| `phase/scaffold` | Four backend service stubs + Vite/React/MUI frontend shell | `../bin/start-dev.sh` starts; each service's `/health` returns 200; frontend renders | 2h |
| `phase/database` | SQLAlchemy models + Alembic migration for all 8 tables | Migration applies locally; tables/indexes exist | 2h |
| `phase/api-core` | CRUD (no auth/workflow rules yet) across all four services | Postman round trip: create/list/get/update/delete per resource, correct status codes | 3h |
| `phase/auth-rbac` | JWT register/login/me, `@acme.inc` check, bcrypt hashing, RBAC middleware, ownership filtering on incidents | 401 with no token, 403 for wrong role, 200 for correct role, token-expiry test | 3h |
| `phase/workflow` | Status state machine, escalation + blocked-reason fields, status history logging, `/dashboard/summary` aggregation | Invalid transition rejected 400; dashboard numbers match seeded data | 3h |
| `phase/frontend` | All pages/components from Step 4, role-gated actions, workflow visualization, responsive layout | Full flow in browser, per persona, against local API | 5h |
| `phase/testing` | Backend unit + integration tests (disposable test DB), frontend Jest/RTL + mocked-API tests, Cypress/Selenium E2E for the report → assign → resolve journey | Coverage meets the guide's thresholds (80%+ backend/frontend, 90%+ API and error handling, 100% critical E2E); runs with one command | 4h |
| `phase/infra-deploy` | Per-service Terraform/Lambda, S3 + CloudFront, Aurora, least-privilege IAM, `sslmode=require` when not local | `terraform apply` clean, outputs present, public-URL health checks, full flow against deployed app | 3h |
| `phase/polish` | README (architecture, setup, trade-offs), diagram, demo script covering all 3 personas and the 7 business questions, a quick Artillery/JMeter pass on `GET /incidents` | Fresh clone runs from the README alone; demo script covers each rubric category | 2h |

Unlike a from-scratch AWS build, this workshop's local scaffold (per its own guide) already emulates the cloud stack from `phase/scaffold` onward, so the usual advice to front-load the riskiest phase applies less here — `phase/infra-deploy` mainly exercises Terraform the scaffold already provides, and can stay near the end without leaving too little recovery time. If that assumption is wrong for this cohort's repo, move `phase/infra-deploy` earlier, right after `phase/database`.

For each phase, hand the user a one-line prompt they can give an AI to generate it, e.g. for `phase/workflow`: "Implement the incident status state machine (open→in\_progress→blocked→resolved→closed) with validated transitions, escalation/blocked-reason fields, a status-history table write on every transition, and a `/dashboard/summary` endpoint scoped by the caller's role, per the approved API contract."

## Decisions to confirm

1. **Backend service split.** Assumed four Lambda services (`users`, `facilities`, `engineers`, `incidents` — the last also serving notes and the dashboard) via the workshop's `cp -R` scaffold pattern. Confirm this grouping, or consolidate further if the workshop expects fewer services.
2. **Engineer account provisioning.** The brief has employees self-register but says Facility Admins "create engineer profiles." Assumed: an admin can either promote an existing registered employee to the `engineer` role, or create a new user + engineer profile directly (no email invite, since no integrations are in scope). Confirm which path(s) the MVP needs.
3. **Priority/escalation model.** "Request or manage incident priority/escalation based on the product design" is open-ended in the brief. Assumed: employees can *request* a priority change or escalation (flag + reason); only Facility Admins can *set* the actual priority or confirm an escalation. Confirm or adjust.
4. **Category taxonomy.** Assumed a fixed enum (HVAC, Electrical, Plumbing, Furniture, Network, Hardware, Software, Access/Security, Other) rather than an admin-managed table, to keep MVP CRUD scope smaller. Confirm, or promote categories to a full CRUD entity if the workshop expects that.
5. **Base infrastructure and timebox.** This plan assumes the workshop repo already supplies base Terraform (network, Aurora, S3/CloudFront, API Gateway) per its own guide, and assumes a \~3-day/24-hour timebox for the phase estimates in Step 6, since neither the base Terraform's actual contents nor a stated duration were included in what was pasted here. Confirm both so `phase/infra-deploy` and the time estimates can be adjusted.

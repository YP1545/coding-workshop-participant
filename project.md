# ACME Facility Incident Platform — Project Plan

Source: [docs/ACME Facility Incident Platform - Build Plan.md](docs/ACME%20Facility%20Incident%20Platform%20-%20Build%20Plan.md) · Plan date: 2026-09-22

## 1. Overview

A facility incident-management platform for three personas — **Employee**, **Facility Admin**, and **Engineer** — covering the full ticket lifecycle from report through assignment to resolution, plus dashboards that answer the brief's business questions.

**Fixed stack (no substitutions):** React + Vite + MUI frontend · Python backend · PostgreSQL storage · AWS Serverless deployment (S3 + CloudFront, Lambda behind API Gateway, Aurora RDS) provisioned with Terraform and the workshop's shell scripts.

## 2. Requirements

### Must have

1. Registration restricted to `@acme.inc` email addresses.
2. Employees create incidents, view their own, and add notes to open incidents.
3. Employees can request a priority change or escalation on their own incidents.
4. Facility Admins CRUD buildings, floors, and seats.
5. Facility Admins create engineer profiles and assign incidents to engineers.
6. Facility Admins view and manage the full incident lifecycle across all incidents.
7. Engineers view assigned incidents, update status, and add notes.
8. Five-status workflow enforced: Open → In Progress → Blocked → Resolved → Closed.
9. The UI shows the workflow visually (stepper or board), not just a status label.
10. Per-persona dashboard with ticket counts by status, priority, and assignee.
11. Search and filter incidents by status, priority, category, building/floor/seat, assignee.
12. Responsive across mobile and desktop (MUI breakpoints + React Responsive).
13. Token-based auth (JWT), password hashing, role-based access control.
14. Full CRUD for incidents, facilities, engineer profiles, and incident notes.
15. Stack as fixed above.
16. AWS Serverless deployment via Terraform + shell scripts.
17. No external system integrations in MVP scope.
18. Test coverage meets the guide's thresholds (see Phase plan).

### Should have

19. Dashboards answer the seven business questions: open-incident status, recurring-issue hotspots by location, time-to-acknowledge/assign/resolve, engineer workload and availability, category breakdown, escalated/blocked incidents with reasons, and employee visibility into progress.
20. Incident status history (who changed what, when) — makes timing metrics real rather than guessed.
21. Engineers set their own availability (available / busy / off).
22. Blocked and escalated incidents carry a required reason.

### Won't have (MVP cut)

23. No email/Slack notifications — in-app status visibility and the notes thread cover "how are employees informed", since no integration is in scope.
24. No admin-managed category taxonomy — categories ship as a fixed enum for v1.
25. No SLA-breach alerting — timing metrics are reported, not enforced.

PostgreSQL is mandated by the brief, so there is no MongoDB/DocumentDB fallback anywhere in this plan.

## 3. Data model (PostgreSQL)

Nine tables. (The source build plan's prose says "eight" but its own DDL defines nine — `incident_assignment_requests` was added with the self-assign flow and the count was never updated.) Full DDL lives in Step 2 of the source build plan; this is the shape:

| Table | Purpose | Key relationships |
| --- | --- | --- |
| `users` | Accounts + role (`employee` / `facility_admin` / `engineer`); `@acme.inc` CHECK on email | — |
| `engineer_profiles` | 1:1 extension of a `users` row; specialty + availability | `user_id` → `users` (UNIQUE, CASCADE) |
| `buildings` | Top of the facility hierarchy | — |
| `floors` | Floors within a building | `building_id` → `buildings` (RESTRICT), UNIQUE per building |
| `seats` | Seats on a floor | `floor_id` → `floors` (RESTRICT), UNIQUE per floor |
| `incidents` | Core ticket: status, priority, category, location, escalation/blocked reasons, lifecycle timestamps | `reporter_id` → `users`, `assignee_id` → `engineer_profiles`, nullable `building_id`/`floor_id`/`seat_id` |
| `incident_notes` | Threaded notes on an incident | `incident_id` (CASCADE), `author_id` → `users` |
| `incident_status_history` | One row per transition: from/to status, who, when | `incident_id` (CASCADE), `changed_by` → `users` |
| `incident_assignment_requests` | Engineer-initiated assignment requests awaiting admin decision | `incident_id`, `engineer_id`, UNIQUE together |

Enums: `user_role`, `availability_status`, `incident_status`, `incident_priority`, `incident_category`, `assignment_request_status`.

**Key decisions**

- `engineer_profiles` extends `users` rather than being a separate identity, so an engineer logs in with the account an admin provisions.
- Location columns on `incidents` are nullable and set independently (not a strict chain) — an issue may have only a seat, or only a building.
- Ownership (`reporter_id`) and assignment (`assignee_id`) are explicit FKs, so authorization is a query filter, not an afterthought.
- Schema changes after the first migration go through Alembic, never hand edits.
- `incident_assignment_requests` backs the engineer self-assign flow: an engineer requests an unassigned incident, an admin approves or denies, approval writes `assignee_id`/`assigned_at` and auto-denies that incident's other pending requests. Admins keep direct assignment too.

## 4. API contract

RESTful, one level of nesting deep, UUID string ids, errors always `{"detail": "..."}` with 400 / 401 / 403 / 404 / 409. Frontend, tests, and the Postman collection are built against this; it should not change after the plan is approved.

### Auth
| Method | Path | Auth | Request → Response |
| --- | --- | --- | --- |
| POST | `/auth/register` | none | `{email, password, full_name}` → 201 `{user}` (400 on non-`@acme.inc`) |
| POST | `/auth/login` | none | `{email, password}` → 200 `{access_token, token_type, user}` |
| GET | `/auth/me` | any | → 200 `{user}` |

### Users (admin)
| Method | Path | Auth | Request → Response |
| --- | --- | --- | --- |
| GET | `/users` | facility_admin | `?role=` → 200 `[user]` |
| PATCH | `/users/{id}/role` | facility_admin | `{role}` → 200 `{user}` |

### Facilities
| Method | Path | Auth | Request → Response |
| --- | --- | --- | --- |
| POST | `/buildings` | facility_admin | `{name, address?}` → 201 `{building}` |
| GET | `/buildings` | any | → 200 `[building]` |
| GET | `/buildings/{id}` | any | → 200 `{building}` |
| PUT | `/buildings/{id}` | facility_admin | `{name, address?}` → 200 `{building}` |
| DELETE | `/buildings/{id}` | facility_admin | → 204 (409 if floors reference it) |
| POST | `/buildings/{building_id}/floors` | facility_admin | `{name}` → 201 `{floor}` |
| GET | `/buildings/{building_id}/floors` | any | → 200 `[floor]` |
| PUT | `/floors/{id}` | facility_admin | `{name}` → 200 `{floor}` |
| DELETE | `/floors/{id}` | facility_admin | → 204 (409 if seats reference it) |
| POST | `/floors/{floor_id}/seats` | facility_admin | `{label}` → 201 `{seat}` |
| GET | `/floors/{floor_id}/seats` | any | → 200 `[seat]` |
| PUT | `/seats/{id}` | facility_admin | `{label}` → 200 `{seat}` |
| DELETE | `/seats/{id}` | facility_admin | → 204 |

### Engineers
| Method | Path | Auth | Request → Response |
| --- | --- | --- | --- |
| POST | `/engineers` | facility_admin | `{user_id}` or `{email, full_name}` → 201 `{engineer_profile}` |
| GET | `/engineers` | any | `?availability=` → 200 `[engineer_profile]` |
| GET | `/engineers/{id}` | any | → 200 `{engineer_profile}` |
| PUT | `/engineers/{id}` | facility_admin, or engineer (self, `availability` only) | → 200 `{engineer_profile}` |
| DELETE | `/engineers/{id}` | facility_admin | → 204 |

### Incidents
| Method | Path | Auth | Request → Response |
| --- | --- | --- | --- |
| POST | `/incidents` | employee | `{title, description, category, building_id?, floor_id?, seat_id?}` → 201 `{incident}` (`reporter_id` = self, status = open) |
| GET | `/incidents` | any, scoped by role | `?status=&priority=&category=&building_id=&assignee_id=&escalated=` → 200 `[incident]` (employee: own; engineer: assigned + unassigned open; admin: all) |
| GET | `/incidents/{id}` | owner, assignee, or admin | → 200 `{incident}` |
| PUT | `/incidents/{id}` | role-scoped field set | → 200 `{incident}` |
| PATCH | `/incidents/{id}/status` | engineer (assignee) or facility_admin | `{status}` → 200 `{incident}` (400 on invalid transition) |
| PATCH | `/incidents/{id}/assign` | facility_admin | `{assignee_id}` → 200 `{incident}` (direct; bypasses the request flow) |
| PATCH | `/incidents/{id}/escalate` | employee (request) or facility_admin (set) | `{escalation_requested?, escalated?, escalation_reason?}` → 200 `{incident}` |
| DELETE | `/incidents/{id}` | facility_admin | → 204 |

### Assignment requests
| Method | Path | Auth | Request → Response |
| --- | --- | --- | --- |
| POST | `/incidents/{incident_id}/assignment-requests` | engineer | → 201 `{assignment_request}` (409 if already pending) |
| GET | `/incidents/{incident_id}/assignment-requests` | facility_admin, or requesting engineer (own only) | → 200 `[assignment_request]` |
| GET | `/assignment-requests` | facility_admin | `?status=` → 200 `[assignment_request]` (queue across incidents) |
| GET | `/engineers/me/assignment-requests` | engineer | `?status=` → 200 `[assignment_request]` |
| PATCH | `/assignment-requests/{id}` | facility_admin | `{status: "approved" \| "denied"}` → 200 `{assignment_request}` (approval assigns and auto-denies the rest) |

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

## 5. Frontend map

`AuthContext` / `useAuth` holds the JWT (memory + `localStorage`) and exposes `login` / `logout` / `user` / `role`. `ProtectedRoute` checks token and role, redirecting to `/login`. An `api/` layer (`authApi`, `incidentsApi`, `facilitiesApi`, `engineersApi`, `dashboardApi`) owns the base URL and the `Authorization: Bearer` header.

| Route | Who | Components | API calls |
| --- | --- | --- | --- |
| `/login`, `/register` | public | `LoginForm`, `RegisterForm` | `POST /auth/login`, `POST /auth/register` |
| `/dashboard` | all (varies by role) | `DashboardStats`, `StatCard`, `WorkflowChart` | `GET /dashboard/summary` |
| `/incidents` | all (role-scoped) | `SearchFilterBar`, `IncidentList`, `IncidentCard` (engineer quick action: request assignment) | `GET /incidents`, `POST /incidents/:id/assignment-requests` |
| `/incidents/new` | employee | `IncidentForm` | `POST /incidents`, `GET /buildings`/`floors`/`seats` |
| `/incidents/:id` | owner, assignee, admin | `IncidentDetail`, `WorkflowVisualization`, `NotesThread`, status/assign/escalate panels, `AssignmentRequestPanel` | `GET /incidents/:id`, `PUT`/`PATCH` variants, notes endpoints, assignment-request endpoints |
| `/assignment-requests` | facility_admin | `AssignmentRequestQueue`, `AssignmentRequestCard` | `GET /assignment-requests`, `PATCH /assignment-requests/:id` |
| `/facilities` | facility_admin | `FacilityTree` (buildings › floors › seats) + inline CRUD forms | full `/buildings`, `/floors`, `/seats` CRUD |
| `/engineers` | facility_admin (manage), engineer (self) | `EngineerTable`, `EngineerAvailabilityToggle`, `EngineerForm` | full `/engineers` CRUD |
| `/profile` | all | `ProfileCard`, availability toggle (engineer) | `GET /auth/me`, `PUT /engineers/:id` |

`WorkflowVisualization` renders the five-status pipeline as a stepper or small board on incident detail — this is the "visual representation of the ticket workflow" requirement, not a status chip. Component tree stays shallow: pages fetch and pass props down; no component both fetches and owns unrelated UI state. Responsive layout uses MUI `Grid`/`Stack` breakpoints, with `react-responsive` only where a genuinely different mobile layout is needed (facility tree, incident board).

### Framework

The backend runs on **FastAPI**, adapted to Lambda with **Mangum**. `app.py`'s
`create_app()` gives every service the same three pieces of wiring — the
`/api/{service}` prefix CloudFront adds, the `{"detail": "..."}` error shape,
and the Mangum adapter — so a service file contains nothing but its routes.

What the move bought:

* **Pydantic models are the contract.** `schemas.py` validates requests, shapes
  responses and generates the documentation, so those three can no longer
  disagree. Request models set `extra="forbid"`, which is what makes sending
  `reporter_id` or `status` a 400 rather than a silently ignored field.
  Response models are allow-lists, so `password_hash` cannot leak.
* **Roles are declared in the signature.** `user: User = Depends(require_roles(ADMIN_ONLY))`
  is visible in the route definition, and a route with no such dependency is
  visibly public.
* **Generated API documentation** at `/api/{service}/docs`, local only — it is a
  complete map of every path and field and needs no token, which is useful while
  building and is reconnaissance once deployed.
* Backend test coverage rose from 80% to **90%**, because hand-written
  validation was replaced by declarations.

What it cost: **13 MB per Lambda package** (37 MB → 50 MB), four times over,
and two behaviour changes noted in Step 3 below. The business rules —
`workflow.py`, `access.py`, `dashboard.py`, `crud.py` — still raise a plain
`ApiError` and import no web framework, so they stay readable and testable as
ordinary Python.

## 6. Infrastructure topology

Client hits CloudFront for both the UI and the API: `infra/cloudfront.tf` adds an ordered cache behavior per service (`/api/{service-name}*`) pointing at that service's Lambda Function URL. There is no API Gateway. Lambda reads and writes Aurora PostgreSQL inside the VPC. Locally, `bin/proxy-server.js` on port 3001 plays CloudFront's role, mapping `/api/{service}` onto the LocalStack Function URL.

### Backend services (one Lambda each)

Each is a directory under `backend/` holding `function.py` (handler `function.handler`), `router.py`, and `requirements.txt`. Terraform discovers them by glob, so adding a service needs no infra edit:

- `users-service` — auth (register / login / me), user role management
- `facilities-service` — buildings, floors, seats
- `engineers-service` — engineer profiles
- `incidents-service` — incidents, notes, status transitions, dashboard aggregation (same tables, so kept together)

Each is wired into `../bin/start-dev.sh` for local dev, then deployed by `../bin/deploy-backend.sh`.

### Environment variables

| Variable | Local | Cloud |
| --- | --- | --- |
| `IS_LOCAL` | `true` | `false` |
| `POSTGRES_HOST` | `localhost` | Aurora endpoint |
| `POSTGRES_PORT` | `5432` | `5432` |
| `POSTGRES_NAME` / `USER` / `PASS` | set locally | Aurora values |

Connection logic branches on `IS_LOCAL`: no SSL locally, `sslmode=require` when `IS_LOCAL` is false. No `MONGO_*` variables — this build is Postgres-only.

### Terraform

Confirmed: the scaffold's Terraform already covers everything this build needs — per-service Lambda + Function URL + DLQ (`infra/lambda.tf`), CloudFront behaviors, Aurora, S3, and the `api_endpoints` / `lambda_urls` / `s3_bucket_name` outputs the frontend build consumes. **No Terraform changes are planned.** Two consequences to note: all services share one IAM role (`local.lambda_role_arn`), so per-service least privilege would mean editing given infra; and env vars are injected from `infra/locals.tf`, so the app reads config only from the names listed below.

### Deploy flow

1. `../bin/deploy-backend.sh` — package and deploy each Lambda, apply backend Terraform.
2. `npm run build` with the deployed API URL as a build-time env var → sync to S3 → invalidate CloudFront.
3. Smoke test: `GET /health` per service through the public URL, then register → login → create incident → assign → resolve against the deployed stack.

Teardown: `terraform destroy` removes Lambda, API Gateway, and Aurora; S3/CloudFront teardown follows the scaffold's own conventions.

## 7. Phase plan

Nine steps, each ending with something runnable. All work happens on a single branch — the steps are sequencing, not separate branches. Estimates assume a ~3-day / ~24-hour workshop — rescale once the timebox is confirmed.

| Step | Goal | Verify | Est. |
| --- | --- | --- | --- |
| **Step 1 — Scaffold** | Four backend service stubs + Vite/React/MUI shell | `start-dev.sh` runs; each `/health` 200; frontend renders | 2h |
| **Step 2 — Database** | SQLAlchemy models + Alembic migration for all 8 tables | Migration applies; tables and indexes exist | 2h |
| **Step 3 — API core** | CRUD across all four services (no auth/workflow rules yet) | Postman round trip per resource, correct status codes | 3h |
| **Step 4 — Auth & RBAC** | JWT register/login/me, `@acme.inc` check, bcrypt, RBAC middleware, ownership filtering | 401 without token, 403 wrong role, 200 correct role, expiry test | 3h |
| **Step 5 — Workflow** | Status state machine, escalation + blocked reasons, status history, `/dashboard/summary` | Invalid transition → 400; dashboard matches seeded data | 3h |
| **Step 6 — Frontend** | All pages/components, role-gated actions, workflow visualization, responsive layout | Full per-persona flow in browser against local API | 5h |
| **Step 7 — Testing** | Backend unit + integration (disposable test DB), Jest/RTL + mocked API, Cypress/Selenium E2E for report → assign → resolve | 80%+ backend/frontend, 90%+ API and error handling, 100% critical E2E; one command | 4h |
| **Step 8 — Infra & deploy** | Per-service Terraform/Lambda, S3 + CloudFront, Aurora, least-privilege IAM, `sslmode=require` | Clean `terraform apply`, outputs present, public health checks, full flow deployed | 3h |
| **Step 9 — Polish** | README (architecture, setup, trade-offs), diagram, 3-persona demo script covering the 7 business questions, Artillery/JMeter pass on `GET /incidents` | Fresh clone runs from README alone; demo covers each rubric category | 2h |

Because the local scaffold already emulates the cloud stack from Step 1 onward, the usual advice to front-load the riskiest phase applies less here — **Step 8 — Infra & deploy** mostly exercises Terraform the scaffold provides. If that assumption is wrong for this repo, move Step 8 right after Step 2.

Each step ships with a one-line prompt to hand an AI, e.g. for Step 5: "Implement the incident status state machine (open→in_progress→blocked→resolved→closed) with validated transitions, escalation/blocked-reason fields, a status-history write on every transition, and a `/dashboard/summary` endpoint scoped by the caller's role, per the approved API contract."

## 8. Decisions to confirm

1. **Backend service split** — assumed four Lambda services (`users`, `facilities`, `engineers`, `incidents` + notes + dashboard). Confirm the grouping, or consolidate.
2. **Engineer account provisioning** — assumed an admin can promote a registered employee to `engineer`, or create user + profile directly (no email invite, no integrations). Confirm which paths the MVP needs.
3. **Priority / escalation model** — assumed employees *request* a priority change or escalation (flag + reason) and only admins *set* priority or confirm escalation.
4. **Category taxonomy** — assumed a fixed enum (HVAC, Electrical, Plumbing, Furniture, Network, Hardware, Software, Access/Security, Other) rather than an admin-managed CRUD entity.
5. **Base infrastructure** — **answered.** The repo supplies all base Terraform and discovers services by directory glob, so Step 8 is deploy-and-verify only. There is no API Gateway: CloudFront routes `/api/{service}*` straight to each Lambda Function URL. **Timebox still open** — the estimates assume ~3 days / 24 hours.
6. ~~**Who may add notes**~~ — **answered.** Reading and writing are now separate: an engineer can read an unassigned incident to decide whether to ask for it, but only the reporter, the assigned engineer and admins can add notes (`access.can_comment_on`). The UI hides the note box rather than letting the server refuse it.
7. **Notes on a closed incident.** Requirement 2 says employees may "add notes to open incidents". Today notes are allowed at any status, including closed. Blocking them would match the wording; allowing them keeps the thread usable as a record. Currently allowed — confirm which you want.
8. **Approving two requests at the same moment.** Approval checks the incident is unassigned and then assigns it — two steps rather than one atomic one. A test firing two approvals simultaneously returned 200 and 409 with exactly one approval recorded, but that is one observation, not a guarantee: under real concurrent Lambda invocations a double assignment remains possible. The fix is a row lock on the incident read, left out to keep the code simple. Confirm whether to add it.

## 9. Task breakdown

Every step from Section 7, split into tasks sized at roughly 15–45 minutes each. Work stays on one branch; tasks within a step are ordered; `[ ]` items at the same indent with no dependency between them can be done in any order or split across people.

### Step 1 — Scaffold (2h)

- [x] Create `backend/users-service` from the Python example (Postgres only — no Mongo).
- [x] Repeat for `facilities-service`, `engineers-service`, `incidents-service`.
- [x] Add `router.py` per service: path patterns with `{param}` capture, JSON bodies, `{"detail": ...}` errors, and 404/405 handling.
- [x] Add a `GET /health` returning `{"status": "ok", "service": ...}` to each of the four services.
- [x] ~~Register the services in `bin/start-dev.sh`~~ — not needed. Terraform globs `backend/*/requirements.txt` (`infra/locals.tf:24`) and `start-dev.sh` counts service dirs, so a new directory is picked up automatically.
- [x] Install MUI, `react-router-dom`, and `react-responsive` in the frontend.
- [x] Add the app shell — theme provider, top nav that collapses on mobile, router outlet, placeholder `/login` route.
- [x] Create `frontend/src/api/client.js` targeting `${VITE_API_URL}/api/{service}` so the local proxy and CloudFront paths are identical.
- [x] **Verify (partial):** every route returns the right status when the handler is invoked directly with sample Function URL events; `npm run lint` and `npm run build` pass; the shell renders at desktop and 375px.
- [ ] **Verify (full):** run `./bin/start-dev.sh` (needs `sudo` to rebind Postgres to `0.0.0.0` and start LocalStack), then `curl` each deployed `/health` through the proxy.

### Step 2 — Database (2h)

- [x] Add SQLAlchemy + Alembic tooling in `backend/_shared/requirements-dev.txt` (deliberately not `requirements.txt`, which `start-dev.sh` would pip-install into a directory that ships no Lambda).
- [x] Create the shared layer in `backend/_shared/` — `db.py` (engine, session factory, `session_scope`), `models.py`, `router.py` — plus `sync.sh`, which copies them into each service. A Lambda is packaged from its own directory and cannot import across services, so the modules are physically copied from one canonical source rather than shared by import.
- [x] Add the `IS_LOCAL` branch in the connection string: `sslmode=require` whenever not local.
- [x] Define the six enum types, with `values_callable` so PostgreSQL stores `facility_admin` rather than the Python member name `FACILITY_ADMIN`.
- [x] Model `users` (with the `@acme.inc` CHECK) and `engineer_profiles`.
- [x] Add a unique index on `lower(email)` — plain `UNIQUE (email)` is case-sensitive, so `Bob@ACME.inc` would be a second account for `bob@acme.inc`. Not in the source DDL.
- [x] Model `buildings`, `floors`, `seats` with their RESTRICT FKs and UNIQUE constraints.
- [x] Model `incidents` with all FKs, escalation/blocked fields, and lifecycle timestamps.
- [x] Model `incident_notes`, `incident_status_history`, `incident_assignment_requests`.
- [x] Add every index listed in the DDL (31 indexes including primary keys).
- [x] Generate the initial Alembic migration and apply it to local Postgres. Hand-adjusted twice: `downgrade()` drops the six enum types (autogenerate leaves them orphaned, breaking the next upgrade), and no `CREATE EXTENSION pgcrypto` since `gen_random_uuid()` is core from PostgreSQL 13 and Aurora here is 17.7.
- [x] Write `seed.py` — 5 users across 3 personas, 2 buildings, 3 floors, 4 seats, 6 incidents spanning all five statuses, notes, 14 status-history rows, 1 pending assignment request. Refuses to run unless `IS_LOCAL=true`, since all seeded accounts share one password.
- [x] **Verify:** migration applies clean on an empty DB; upgrade → downgrade → upgrade is repeatable; `alembic check` reports no drift from `models.py`; the `@acme.inc` CHECK, the case-insensitive email index, the enum constraint and `ON DELETE RESTRICT` were each confirmed to reject a bad write.
- [x] **Parity-checked against the reference `schema.sql`.** Both were applied to separate databases and compared on 119 structural facts (columns, types, nullability, defaults, foreign keys with delete rules, indexes, enum members, check constraints), ignoring constraint names. Identical except for the one intended addition, the unique index on `lower(email)`. The check also caught a defect in the migration: Alembic's autogenerate had rendered the CHECK regex's literal `%` doubled as `%%`, which stored a redundant duplicate inside the character class — corrected and re-verified.
- [x] Fixed ORM/database delete semantics: `passive_deletes="all"` where the database says RESTRICT (so the ORM does not pre-null children and mask the error) and `passive_deletes=True` where it says CASCADE (so deleting an incident with fifty notes is one statement, not fifty-one).

### Step 3 — API core (3h)

- [x] Request validation and response shaping — `validation.py` (required fields, length caps, UUID/enum/bool parsing, unknown-field rejection, paginated `limit`/`offset` with a 200 cap) and `serializers.py` (explicit allow-list per entity, so `password_hash` cannot leak). Not Pydantic: there is no FastAPI here, the services are bare Lambda handlers.
- [x] Shared error handling — `crud.py` maps PostgreSQL SQLSTATEs onto HTTP codes in one place; every failure returns `{"detail": "..."}`.
- [x] `users-service`: `GET /users` (`?role=`), `GET /users/{id}`, `PATCH /users/{id}/role`.
- [x] `facilities-service`: buildings CRUD.
- [x] `facilities-service`: floors — nested create/list under a building, plus `PUT`/`DELETE /floors/{id}`.
- [x] `facilities-service`: seats — nested create/list under a floor, plus `PUT`/`DELETE /seats/{id}`.
- [x] Return 409 on delete when child rows still reference a building or floor. Two real bugs found here: SQLAlchemy was nulling children's foreign keys before the delete (masking the database's `RESTRICT` as a 400), and `ON DELETE RESTRICT` raises SQLSTATE **23001**, not 23503 — handling only the latter turned the conflict into a 500.
- [x] `engineers-service`: profile CRUD with `?availability=`, both provisioning paths from Decision 2, and a single joined query for the list so names do not cost one query per row.
- [x] `incidents-service`: incidents CRUD, unscoped for now, with every documented filter applied in SQL so the Step 2 indexes are used.
- [x] `incidents-service`: notes create/list under an incident.
- [x] Build the Postman collection covering every endpoint — `postman/acme-incidents.postman_collection.json`, 47 requests in 5 folders, each with a test asserting the documented status code and the `{detail}` error shape.
- [x] **Verify:** the pytest suite in `backend/_shared/tests/` covers the CRUD contract; `roundtrip_check.py` and its siblings were retired once their assertions lived there.
- [x] **Two behaviour changes from the FastAPI move**, both deliberate: `?limit=999999` is now a **400** rather than being silently clamped to 200 — a client should be told its request was wrong; and `?escalated=0` is now accepted as False, because FastAPI parses the usual boolean spellings without guessing.

### Step 4 — Auth & RBAC (3h)

- [x] Add bcrypt password hashing helpers (hash + verify) — `_shared/auth.py`, the only module that touches hashes or the signing key.
- [x] `POST /auth/register` — `@acme.inc` domain check, duplicate → 409, 201 on success. The `role` field is rejected outright, so nobody can register as an admin.
- [x] `POST /auth/login` — issues a JWT with `sub`, `role`, `iat`, `exp` (24h). Unknown email and wrong password return the same message after the same work, so the endpoint cannot be used to enumerate accounts.
- [x] `GET /auth/me` — returns the caller as loaded from the database this request.
- [x] Shared token handling in `_shared/auth.py` + `_shared/api.py`: 401 on missing, malformed, expired, wrongly-signed and `alg=none` tokens. `algorithms` is pinned to a single value, so the algorithm-confusion attacks do not apply.
- [x] **`JWT_SECRET` now fails closed.** `auth.jwt_secret()` uses the env var if set, a documented local-only default when `IS_LOCAL=true`, and otherwise **raises** — so a deployed Lambda that was never given a secret returns 500 on the first request instead of silently signing tokens with a string published in this repository. Supplying the real value in a deployment is still an open decision (Secrets Manager via the Lambda role, or an exception to the no-infra-edits rule).
- [ ] ~~**Decide where `JWT_SECRET` comes from.**~~ `infra/locals.tf` injects only `APP_*`, `IS_LOCAL`, `POSTGRES_*` and `MONGO_*`, so a deployed Lambda receives no signing secret. Falling back to a default in code means tokens are signed with a string anyone can read from the repo and use to forge a `facility_admin`. Needs a runtime fetch (Secrets Manager via the Lambda role) or an explicit exception to the no-infra-edits rule.
- [x] ~~**Stop `reporter_id` / `author_id` being client input.**~~ Done — both come from the token and are rejected as request fields. Step 3 reads them from the request body; until they come from the token, any caller can file a ticket or post a note in someone else's name.
- [ ] Add a way to set a password on an admin-provisioned engineer account. `engineers-service` stores `LOCKED_PASSWORD_HASH` (`"!"`), which no bcrypt check can match, so those accounts can be assigned work but cannot sign in.
- [x] Routed the browser past `bin/proxy-server.js` via a `server.proxy` block in `frontend/vite.config.js`, built from `VITE_API_ENDPOINTS`. The API client sends the bearer token and targets the dev server's own origin in development. **Not yet verified end to end** — that needs `start-dev.sh` and LocalStack running. Was: `bin/proxy-server.js` strips the `Authorization` header (it forwards only accept, content-type, user-agent, host). A `server.proxy` block in `frontend/vite.config.js` is app config, so this needs no change to `bin/`. CloudFront is unaffected — it uses the AllViewerExceptHostHeader policy.
- [x] Roles are declared per route rather than checked inside handlers — `@route("POST", "/buildings", ADMIN_ONLY)`. A route either names its roles or is explicitly `PUBLIC`, so shipping an endpoint with no check is not something you can do by forgetting. The wrapper also gives each request exactly one transaction.
- [x] The role is read from the database on every request, never from the token's claim: a validly-signed token carrying `role: facility_admin` for an employee account gets 403.
- [x] Scope `GET /incidents` by role, as a WHERE clause — an employee's query never fetches another employee's rows, and a query-string filter can only narrow the scope, never widen it.
- [x] Object-level access on `GET/PUT /incidents/{id}` and both notes endpoints. A record the caller may not see returns **404, not 403**: 403 would confirm that an incident with that id exists.
- [x] `reporter_id` and `author_id` are no longer request fields — both come from the token, and sending them is a 400.
- [x] An engineer may `PUT /engineers/{id}` on their own profile, `availability` only. Specialty stays admin-only: what someone is qualified for is a management decision.
- [x] An admin cannot change their own role, so the last admin cannot demote themselves and lock everyone out of facility management.
- [x] **Verify:** `backend/_shared/auth_check.py` — **64 assertions**, every rule with an explicit negative test (wrong role refused, another user's record invisible, expired/forged/`alg=none` tokens rejected, scope not wideable). `roundtrip_check.py` re-run authenticated: 64 more.

### Step 5 — Workflow (3h)

- [x] Transition map in `incidents-service/workflow.py` — a plain dict of status → allowed next statuses. `closed` maps to an empty list: it is the end of the line, since reopening would blur the resolution times the dashboard reports.
- [x] `PATCH /incidents/{id}/status` — validates the move, restricted to the assigned engineer or an admin. The reporter can read and comment but not move it.
- [x] `blocked_reason` required when blocking, and cleared automatically when work restarts so a stale reason cannot linger.
- [x] Timestamps stamped at the right moves. `acknowledged_at` is set only the first time work starts — overwriting it on every restart would make time-to-acknowledge drift later and later.
- [x] A history row on every transition, including the opening `None → open` row written at creation, so the timeline starts at the beginning.
- [x] `PATCH /incidents/{id}/escalate` — the reporter requests with a required reason, only an admin confirms. Split by role per Decision 3.
- [x] `PATCH /incidents/{id}/assign` — admin direct assignment; sending null unassigns. Assigning also denies any pending requests, since the work is no longer available.
- [x] `POST /incidents/{id}/assignment-requests` — engineer asks for unassigned work; the database's unique constraint makes a repeat ask a 409.
- [x] `GET /assignment-requests` (admin queue, `?status=`) and `GET /engineers/me/assignment-requests`. On a single incident an engineer sees only their own request; the admin sees all of them.
- [x] `PATCH /assignment-requests/{id}` — approving records the decision, assigns the incident and auto-denies everyone else who asked, in one request rather than three round trips.
- [x] `GET /dashboard/summary` in `incidents-service/dashboard.py` — counts by status, priority, assignee and category, all role-scoped through the same `access.py` rules the list endpoint uses.
- [x] Average hours to acknowledge, assign and resolve. Only incidents that reached the milestone are counted: treating unresolved ones as zero would make the team look faster the more work they left undone.
- [x] `top_locations` (recurring-problem hotspots) and `escalated_blocked` with the reason text, since the brief asks specifically *why*.
- [x] **Verify:** `backend/_shared/workflow_check.py` — **63 assertions**, most of them negative: open → resolved refused, blocking without a reason refused, the reporter and unassigned engineers refused, a closed incident cannot be reopened, a decided request cannot be decided twice. Dashboard output was compared against raw SQL and matches.

### Step 6 — Frontend (5h)

- [x] `AuthProvider` + `useAuth`, with the token in `localStorage` so a refresh does not sign you out. Split across three files (`authContext.js`, `AuthContext.jsx`, `useAuth.js`) because Vite's fast refresh only works when a file exports components alone.
- [x] The API client attaches `Authorization: Bearer` and, in development, targets the dev server's own origin so the Vite proxy can forward the header.
- [x] `ProtectedRoute` with an optional role list. Documented in the file as a convenience, not a security boundary — the API enforces the same rules again.
- [x] API layer split into `authApi`, `incidentsApi`, `facilitiesApi`, `engineersApi`. The dashboard call lives in `incidentsApi` because that is the service serving it.
- [x] `/login` and `/register`, with the `@acme.inc` rule stated up front and registration signing you straight in.
- [x] `/` — **three dashboards, not one with things hidden.** The server sends a different shape per persona and the page picks the component from the `role` in the response, so a heading can never appear for figures the response does not contain:
  - **Employee** — their counts by status and priority, and *Waiting on you*: their incidents where the last note came from somebody else. With no email or Slack integration, that list is this product's answer to "how effectively are employees informed" — not a notification that can be missed, but a dashboard that is correct whenever they look.
  - **Engineer** — assigned counts by status and priority, the assigned incidents themselves, their own pending requests, how much unassigned open work they could ask for, and their own average resolution time. Unassigned work they can browse is counted separately so it never inflates their own queue.
  - **Facility Admin** — everything: counts by status, priority and category, workload per engineer *by name*, unassigned still needing an owner, time to acknowledge/assign/resolve, recurring-problem locations, engineer availability, pending assignment requests, and escalated/blocked with reasons. This is where most of the seven business questions get answered.
- [x] `/incidents` — search box plus filters (status, priority, category, building), all sent to the API as query parameters rather than filtered in the browser, and **10 per page** with page controls. `GET /incidents` returns `{items, total, limit, offset}`: the total is what lets the page say "page 2 of 3", and it travels in the body because the Function URLs set `expose_headers = []`, so a browser could not read a custom header. Search matches title or description, case-insensitively, with `%` and `_` escaped so a wildcard typed into the box is treated as text. Changing a filter or searching returns to page 1.
- [x] Responsive checked at 320, 375, 768, 1024 and 1280 px on every page, measuring `scrollWidth` against the viewport. One real break found and fixed: past the old 700px breakpoint an admin's seven nav links rendered inline and overflowed a tablet by 67px. The bar now collapses based on **how many links the role has**, not a fixed width, and the title truncates rather than wrapping.
- [x] `/incidents/new` — cascading building → floor → seat, all optional.
- [x] `/incidents/:id` — details, timestamps, and `NotesThread`.
- [x] `WorkflowStepper` — the five-status pipeline as a stepper. Blocked is shown as a red marker at the in-progress step with its reason, rather than a fifth step, because an incident is blocked *while* in progress.
- [x] Role-gated panels on the detail page: update status (assignee or admin), assign (admin), request escalation (reporter), confirm escalation (admin), request assignment (engineer), approve/deny (admin), delete (admin).
- [x] `/assignment-requests` — the admin queue, filterable by decision.
- [x] `/facilities` — buildings as accordions; floors and seats load only when a building is opened.
- [x] `/engineers` — a table that becomes cards below 700px, with the availability dropdown inline.
- [x] `/profile` — account details, and for engineers an availability picker. Specialty is shown but not editable: that is a management decision.
- [x] Loading spinners and a shared `ErrorMessage` that prints the server's own `detail` text on every page that fetches.
- [x] Engineers see their own assigned work at the top of the incident list — they open that page to find out what to do today (`access.order_for`).
- [x] Managing the engineer roster is admin-only. Engineers get `/my-requests` instead, showing what they have asked for and how it was decided.
- [x] Assignment requests carry the engineer's name and email and a summary of the incident (title, description, status, priority, category). An admin choosing between two requests needs to see who is asking and what the job is — an id tells them neither. Two extra queries for the whole list, not one per row.
- [x] Fixed: an engineer could not see the status panel or the note box on their **own assigned** incident. The page only loaded the engineer roster for admins, so an engineer had no way to learn their own profile id, and every "is this mine?" check silently answered no.
- [x] `/people` (admin): everyone who registered, with a role dropdown as the single control. Choosing Engineer creates their engineer profile too, so they appear on the rota and can be assigned work; choosing anything else takes them off it.
- [x] **Demotion hides rather than deletes.** `incidents.assignee_id` is `ON DELETE SET NULL`, so deleting the profile would erase the record of who resolved every incident that person ever closed — a routine admin action quietly destroying history. The profile is kept, the roster filters on the current role, and re-promoting restores the same profile with its specialty intact. Assigning work to a demoted profile is refused with 409.
- [x] **Verify:** walked in the browser against the live API. Admin sees 6 incidents and every nav link; employee sees 3, only Dashboard/Incidents/Profile, and typing `/facilities` directly redirects to the dashboard. Workflow stepper renders the blocked state with its reason. Lint and build clean.

### Step 7 — Testing (4h)

- [x] pytest against a **disposable database**: created per run, migrated with the real Alembic migration (not `create_all`, or it would not prove the migration works), dropped in a `finally` so a failing run still cleans up.
- [x] Fixtures in `tests/conftest.py`: a client per persona, a facility tree, and an incident — so each test reads as the request it is making.
- [x] **92 backend tests** across database guarantees, auth, RBAC, facilities, incidents, workflow and the three dashboards.
- [x] **43 frontend tests** (Vitest + React Testing Library): the API client, the route guard, the workflow stepper, the note thread, login, the incident list, the incident detail panels per role, and the three dashboards.
- [x] `./test.sh` runs both; `./test.sh --coverage` adds coverage.
- [ ] Raise frontend coverage from 50% to the guide's 80%: the pages with no tests yet are Facilities, Engineers, People, New Incident, My Requests, Assignment Requests, Register and Profile.
- [ ] End-to-end browser test (Cypress or Playwright) for the report → assign → resolve journey. The journey has been walked by hand in the browser for all three personas, but nothing runs it automatically.
- [ ] Port `backend/_shared/auth_check.py` (64 assertions), `roundtrip_check.py` (65) and `workflow_check.py` (63) to pytest against a disposable database. They already cover the RBAC matrix and the CRUD contract; what they lack is isolation — they run against the development database and clean up after themselves rather than starting from a known empty one.
- [ ] Test the Step 2 database guarantees directly: the `@acme.inc` CHECK rejects a foreign domain, `lower(email)` uniqueness rejects a case-variant duplicate, an invalid enum value is refused, and deleting a building that has floors raises instead of cascading. These are currently only verified by hand.
- [ ] Cypress (or Selenium) E2E: report → assign → resolve across all three personas.
- [ ] **Verify:** 80%+ backend and frontend, 90%+ API and error handling, 100% of the critical E2E journey.

### Step 8 — Infra & deploy (3h)

- [x] Read the scaffold's Terraform and confirm what the base provides — done in Step 1: services are discovered by glob, each gets a Lambda + Function URL + DLQ, CloudFront routes `/api/{service}*`, and the needed outputs already exist. No Terraform edits are planned.
- [ ] Confirm the Lambdas land in subnets that can reach Aurora (the scaffold places them in public subnets with the workspace security groups).
- [ ] **Decide how migrations reach Aurora.** `alembic upgrade head` currently runs from a developer machine against local Postgres; the Aurora cluster sits inside the VPC, so the same command will not reach it. Options: a one-off migration Lambda in the VPC, running Alembic from an in-VPC host, or temporarily allowing the developer's IP. This is the most likely Step 8 blocker and has no code written for it yet.
- [ ] Confirm `POSTGRES_*` and `IS_LOCAL` arrive from `infra/locals.tf` in the deployed Lambda, and that the app reads no env var the scaffold does not inject.
- [ ] Run the Alembic migration against Aurora.
- [ ] Deploy with `bin/deploy-backend.sh` and fix whatever breaks.
- [ ] Build the frontend with the deployed API URL, sync to S3, invalidate CloudFront.
- [ ] Smoke test: `GET /health` per service through the public URL.
- [ ] Smoke test: register → login → create incident → assign → resolve against the deployed stack.
- [ ] Document the teardown path and confirm `terraform destroy` plans clean.

### Step 9 — Polish (2h)

- [ ] README: architecture overview, local setup, deploy steps, trade-offs and cut scope.
- [ ] Architecture diagram (client → CloudFront/API Gateway → Lambda → Aurora).
- [ ] Demo script covering all three personas and the seven business questions.
- [ ] Artillery/JMeter pass on `GET /incidents`; record the numbers in the README.
- [ ] Fresh-clone test: follow the README only and confirm the app runs.
- [ ] Final sweep for leftover TODOs, debug logging, and committed secrets.

### Cross-cutting, before Step 3 starts

- [ ] Get answers to the five items in Section 8 — the service split and the escalation model change the API surface, so confirm them before writing endpoints.

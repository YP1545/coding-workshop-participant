# ACME Facility Incident Platform

An incident reporting and workflow system for a corporate facility. Employees
report problems, engineers fix them, facility admins run the site.

**Live:** https://d2wweylet0bbeg.cloudfront.net

Built on the [Citi coding workshop scaffold](https://github.com/citi/coding-workshop-participant).
The scaffold's Terraform and shell scripts (`infra/`, `bin/`) are **unchanged** —
this application was written to fit them. The original workshop material is in
[`docs/README.md`](./docs/README.md).

| | |
|---|---|
| 41 REST endpoints | across four services |
| 10 tables | PostgreSQL, Alembic migrations |
| 200 tests | 139 backend (90% coverage) + 61 frontend |
| 5 Lambda functions | four services plus a migration runner |

---

## What it does

Three roles, and they want genuinely different things — so `GET /dashboard/summary`
returns three different response shapes.

| Role | Sees |
|---|---|
| **Employee** | Their own incidents, the notes thread, what is waiting on them |
| **Engineer** | Assigned work first, their request queue, their own availability |
| **Facility admin** | Every incident, workload per engineer, timing metrics, the whole site |

An employee never *receives* site-wide figures. The filtering happens in SQL, so
there is nothing extra in the payload to inspect — not a UI that shows less.

### The incident workflow

```
open ──────▶ in_progress ──────▶ resolved ──────▶ closed
  │               │                   │              ▲
  │               ▼                   │              │
  └────────▶  blocked  ───────────────┴──────────────┘
```

Defined once, in [`workflow.py`](./backend/incidents-service/workflow.py). Rules
that come with it:

- **Blocking requires a reason.** Unblocking clears the old one.
- **Closed is terminal.** Reopening would blur the resolution times the
  dashboard reports, so a new problem gets a new incident.
- **Every transition writes a history row.** That is what makes the timing
  metrics measured rather than estimated.
- **Reopening a resolved incident clears its resolution date** — otherwise the
  admin's average-hours-to-resolve counts work that was undone.

---

## Architecture

```
Browser
   │
   ▼
CloudFront ──── /             ──▶  S3 (the built React app)
           └─── /api/{service}/* ──▶  Lambda Function URL, one per service
                                         │
                                      Mangum  (Lambda event ──▶ ASGI)
                                         │
                                      FastAPI
                                         │
                                   Aurora Serverless v2 (PostgreSQL 17.7)
```

**Stack:** React 19 · MUI 9 · Vite 7 · FastAPI 0.141 · SQLAlchemy 2.0 ·
psycopg 3 · Python 3.13 · Terraform

### Why four services

Not a design decision — [`infra/locals.tf`](./infra/locals.tf) discovers services
by globbing for `backend/*/requirements.txt`, and every match becomes its own
Lambda packaged from that directory alone:

```hcl
for file in fileset("../backend", "*/requirements.txt") :
  dirname(file) if !startswith(dirname(file), "_")
```

Because a Lambda packages one directory, services cannot share code by importing
it. So [`backend/_shared/`](./backend/_shared/) holds one canonical copy of the
eight shared modules and [`sync.sh`](./backend/_shared/sync.sh) copies them out.
The leading underscore keeps that folder invisible to the glob.

The duplication is *generated*, not written: four copies typed by hand would be
four opinions, four copies a script produced from one file are one opinion
stored redundantly because the deployment model requires it. A Lambda layer
would be tidier and needs Terraform that could not be edited.

### Layout

```
backend/
  _shared/          canonical shared modules, migrations, tests, seed, dev server
  users-service/    auth and accounts          (6 endpoints)
  incidents-service/  incidents, workflow, dashboard  (17)
  facilities-service/ buildings, floors, seats        (13)
  engineers-service/  engineer profiles               (5)
  migrate-service/  runs migrations from inside the VPC — never an HTTP endpoint
frontend/src/
  api/              one HTTP client, four service modules — the only fetch() call
  auth/             context, provider and hook (split for Vite fast refresh)
  components/       layout, route guard, shared UI, dashboard pieces
  pages/            12 routed pages
deploy/             schema.sql and the post-deploy scripts
```

---

## Running it locally

**You need:** Python 3.13, Node 20+, PostgreSQL 16+ running locally.

```bash
python3 -m venv .venv && .venv/bin/pip install -r backend/_shared/requirements-dev.txt
cd frontend && npm install && cd ..
```

Create the schema and some demo data:

```bash
cd backend/_shared
IS_LOCAL=true POSTGRES_NAME=postgres ../../.venv/bin/alembic upgrade head
IS_LOCAL=true POSTGRES_NAME=postgres ../../.venv/bin/python seed.py
```

Then start both halves with one command:

```bash
./dev.sh
```

Backend on `:8000`, frontend on `:3000`, Ctrl+C stops both. Seeded accounts all
share the password printed by `seed.py`:

```
dana.admin@acme.inc       facility_admin
sam.employee@acme.inc     employee
alex.engineer@acme.inc    engineer
```

**`IS_LOCAL=true` is not optional.** Without it the server starts and `/health`
answers, but signing in returns 500 — see *The signing secret*, below. The
five-second check:

```bash
curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/api/users-service/docs
```

`200` means configured for local. `404` means `IS_LOCAL` is unset.

Interactive API documentation, local only:
`http://localhost:8000/api/incidents-service/docs`

---

## Testing

```bash
./test.sh              # backend then frontend
./test.sh --coverage
```

The backend suite **creates a disposable database and drops it afterwards**, so
it never touches development data and can run in any order. Requests go through
the application's own test client, so routing, validation and the dependency
guards are all exercised — not handlers called directly with hand-made
arguments.

One test worth naming: [`test_lambda_entry.py`](./backend/_shared/tests/test_lambda_entry.py)
covers Mangum and the CloudFront path prefix — the one seam the test client
skips, and exactly where a deployed request would 404 while every local test
passed.

---

## Deploying

Full runbook: [`deploy/README.md`](./deploy/README.md).

```bash
export EVENT_ID=… PARTICIPANT_ID=… PARTICIPANT_CODE=… AWS_REGION=us-east-2
./bin/setup-participant.sh          # short-lived credentials
./bin/deploy-backend.sh aws         # Terraform: Lambdas, CloudFront, S3, Aurora
./deploy/after-deploy.sh            # re-apply what Terraform reverts
./bin/deploy-frontend.sh
```

Then create the schema, once:

```bash
aws lambda invoke --function-name coding-workshop-migrate-service-<id> \
  --cli-binary-format raw-in-base64-out --payload '{}' /dev/stdout
```

### Why `after-deploy.sh` exists

Three settings this application needs are not in `infra/`, which is the
scaffold and is not modified. They are applied out of band — and Terraform owns
all three resources, so every deploy silently removes them again:

| | Without it |
|---|---|
| `JWT_SECRET` on each Lambda | Sign-in returns 500 |
| `s3:ListBucket` for CloudFront | Every deep link returns S3's `AccessDenied` XML |
| Lambda memory at 1024 MB | Sign-in takes 4.2s instead of 0.6s |

Each failure appears only when somebody tries to use the app, by which point
the deploy looks finished. One command after every deploy is the cheapest way
not to be caught by that.

### Migrations run from inside the VPC

Aurora is created without `publicly_accessible`, so it has no public endpoint
and `alembic upgrade head` cannot reach it from a developer machine.
[`migrate-service`](./backend/migrate-service/) exists to do nothing but that.

Terraform gives every discovered service a public Function URL, so that one is
on the internet too — the handler **refuses anything shaped like an HTTP
request**. A Function URL event carries `requestContext`; a direct invoke does
not. The only way to run it is AWS credentials that already have
`lambda:InvokeFunction`.

[`deploy/schema.sql`](./deploy/schema.sql) is the same schema as plain SQL,
generated offline from the migrations, for the case where you would rather run
`psql` from a CloudShell VPC environment than deploy a migration runner.

---

## Design decisions

**The role is read from the database, never from the token.** The JWT carries a
role claim so the frontend can draw the right navigation without waiting for a
round trip. The backend ignores it and reloads the user every request — the
token was issued up to 24 hours ago, so reloading means a demotion takes effect
on the next call rather than at expiry.

**Responses are allow-lists.** Registration returns the whole ORM object,
password hash included, and the response model filters it to six declared
fields. The hash cannot leak by accident because the field does not exist in the
response model.

**The signing secret fails closed.** `infra/locals.tf` injects database
credentials but no JWT secret. Falling back to the committed development default
would sign production tokens with a string anyone can read from this repository,
so [`auth.py`](./backend/_shared/auth.py) raises instead. A loud 500 beats a
silent compromise.

**`ON DELETE` is chosen per relationship**, because each one is a product rule:

| Foreign key | Behaviour | Why |
|---|---|---|
| `incidents.reporter_id → users` | RESTRICT | Cannot delete someone who reported things |
| `incidents.assignee_id → engineer_profiles` | SET NULL | The profile can go; the incident survives |
| `incidents.building_id → buildings` | SET NULL | Removing a seat must not erase what went wrong there |
| `incident_notes.incident_id → incidents` | CASCADE | A note has no life without its incident |

**The route guard is not the security boundary.**
[`ProtectedRoute`](./frontend/src/components/ProtectedRoute.jsx) stops an honest
person taking a wrong turn. Every rule it expresses is enforced again by the API,
because anyone can open DevTools and call it directly.

**Demotion hides an engineer, it does not delete them.** The roster joins to
`users` and filters on the current role, so a demoted person disappears from
assignment dropdowns while their profile survives. Deleting it would blank the
assignee on every incident they ever closed.

---

## Three bugs that only existed once deployed

Worth recording, because none of them can happen on localhost.

**API 404s arrived as 200 with HTML.** CloudFront rewrites every 404 to
`index.html` so deep links into the single-page app work — but that rule is
distribution-wide, so it caught the API too. The client saw success, failed to
parse HTML as JSON, and returned an empty object. Recognised in
[`client.js`](./frontend/src/api/client.js) by content type.

**Every deep link returned raw `AccessDenied` XML.** S3 answers 403 rather than
404 for a missing key unless `ListBucket` is granted — it will not reveal
whether the object exists — and only 404 was mapped. Fixed by
[`fix-spa-routing.sh`](./deploy/fix-spa-routing.sh).

**Seeding reported a password it had not used.** Lambda reuses a warm container,
so a module-level read of the password happened once, on the first invocation. It
did not error — it returned success and a password that would never work. Every
local run is a fresh process, so this could not happen on a developer machine.

---

## What is not done

- **Frontend test coverage is 61% of lines, against an 80% target.** Function
  coverage is lower still at 33% — several pages have no tests at all. The API
  client and the core journeys are covered.
- **No browser end-to-end test.** The full journey has been walked by hand on
  the deployed stack, which is not the same thing.
- **Three post-deploy steps are manual**, scripted but not enforced.
- **The four services share one database**, so they are independently deployed
  rather than independent. Real separation means each owning its own schema —
  cost without benefit at this size.
- **No SLA alerting, no notifications, no admin screen for categories** —
  deliberate MVP cuts, recorded in [`project.md`](./project.md).

---

## Repository

`infra/` and `bin/` are the workshop scaffold, byte-identical to upstream.
Everything under `backend/`, `frontend/src/`, `deploy/` and `postman/` is this
project, along with `project.md`, `dev.sh` and `test.sh`.

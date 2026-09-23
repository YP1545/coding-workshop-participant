# Deploying to AWS

The order below matters. Each step says what it needs, what it does, and how to
tell it worked.

Nothing here modifies `infra/` or `bin/` — those are the workshop scaffold and
this project is built to fit them.

---

## What gets created

`./bin/deploy-backend.sh` runs Terraform, which builds:

| Resource | Notes |
|---|---|
| 4 Lambda functions | one per `backend/*/requirements.txt`, auto-discovered |
| 4 Function URLs | one per function, fronted by CloudFront |
| CloudFront distribution | `/` to S3, `/api/{service}/*` to the matching Lambda |
| S3 bucket | the built React app |
| Aurora Serverless v2 | PostgreSQL 17.7, max 4 ACU |

Terraform skips CloudFront, Aurora, DocumentDB and EKS when the account is
LocalStack's `000000000000`, so the local stack builds only Lambda and S3.

---

## Step 1 — Refresh AWS credentials

The workshop issues short-lived session tokens. They expire during a long
deploy, and every step below fails with `ExpiredToken` when they do.

```bash
export EVENT_ID='...' PARTICIPANT_ID='...' PARTICIPANT_CODE='...' AWS_REGION='us-east-2'
./bin/setup-participant.sh
```

The three values come from the organizer's email. The script rewrites
`ENVIRONMENT.config`, which is gitignored and holds live credentials — never
commit it.

**Check it worked:**

```bash
set -a; . ./ENVIRONMENT.config; set +a; aws sts get-caller-identity
```

An account id means you are in. `ExpiredToken` means run it again.

---

## Step 2 — Deploy the infrastructure

```bash
./bin/deploy-backend.sh aws
```

First run takes several minutes; Aurora is the slow part.

**Check it worked:**

```bash
cd infra && terraform output
```

`api_base_url`, `website_url` and `lambda_urls` should all have values.

---

## Step 3 — Create the schema

Aurora has no public endpoint — `aws_rds_cluster_instance` does not set
`publicly_accessible`, which defaults to `false`. Confirmed: port 5432 is not
reachable from a developer machine. So the migrations have to run from inside
the VPC, which is what `backend/migrate-service` is for.

It is deployed by Step 2 like any other service, then invoked directly:

```bash
aws lambda invoke --function-name coding-workshop-migrate-service-<app-id> \
  --cli-binary-format raw-in-base64-out --payload '{}' /dev/stdout
```

**Check it worked** — the response names the revision before and after:

```json
{"before": null, "after": "b1d47e93c6a2", "changed": true}
```

`"changed": false` means the database was already up to date, which is the
normal answer on every run after the first.

### Why it is safe to have deployed

Terraform gives every discovered service a public Function URL, so this one is
on the internet too. The handler refuses anything shaped like an HTTP request —
a Function URL event carries `requestContext`, a direct invoke does not — so the
only way to run it is with AWS credentials that already have
`lambda:InvokeFunction`. Verified against the live URL:

```
GET  https://<function-url>/   ->  404 {"detail":"Not found"}
POST https://<function-url>/   ->  404 {"detail":"Not found"}
```

To remove it entirely, delete `backend/migrate-service/` and re-apply —
`infra/locals.tf` discovers services by globbing for `requirements.txt`, so the
function disappears with the directory.

### The offline alternative

`deploy/schema.sql` is the same schema as plain SQL, generated from the
migrations without connecting to anything. It exists for the case where you
would rather not deploy a migration runner: run it with `psql` from anywhere
inside the VPC, such as an AWS CloudShell VPC environment.

```bash
psql "host=<aurora-endpoint> port=5432 dbname=codingworkshop user=superadmin sslmode=require" \
     -v ON_ERROR_STOP=1 -f schema.sql
```

The database is **`codingworkshop`** and the user is **`superadmin`** — not
`postgres`. Terraform creates the cluster with its own names and passes them to
the Lambdas; connecting to `postgres` instead succeeds and creates the tables in
the wrong database, which shows up later as `relation does not exist`. Read the
real values from the deployed function rather than assuming:

```bash
aws lambda get-function-configuration \
  --function-name coding-workshop-users-service-<app-id> \
  --query 'Environment.Variables' --output json
```

Regenerate the file after adding a migration, or it will quietly disagree with
`models.py`:

```bash
./deploy/generate-schema.sh
```

---

## Step 3b — Seed the demo data (optional)

A freshly deployed database is empty, and there is no way to create the first
admin through the API: registration always produces an employee, and promoting
one requires an admin to call it. The migration runner can do both, because it
runs with AWS credentials rather than a user token.

```bash
aws lambda invoke --function-name coding-workshop-migrate-service-<app-id> \
  --cli-binary-format raw-in-base64-out \
  --payload '{"action":"seed"}' /dev/stdout
```

Five accounts, two buildings, six incidents with history and notes. The
response carries the password — **it is shown once and stored nowhere**:

```json
{"action":"seed","counts":{"users":5,"incidents":6,...},"password":"sZog6ahU7qhZriYA"}
```

**The password is generated, not `seed.py`'s default.** That default is
committed in this repository and this database sits behind a public URL —
seeding with it would publish five working logins, one of them a facility
admin, to anyone who reads the repo.

Seeding deletes every existing row first, so it refuses to run against a
database that already has users unless you say so explicitly:

```bash
--payload '{"action":"seed","reset":true}'
```

If you would rather not have demo data, register an account through the UI and
promote it instead:

```bash
aws lambda invoke --function-name coding-workshop-migrate-service-<app-id> \
  --cli-binary-format raw-in-base64-out \
  --payload '{"action":"promote","email":"you@acme.inc"}' /dev/stdout
```

That is the narrowest bootstrap available: it promotes an account that already
exists, cannot create one, and cannot set a password.

---

## Step 4 — Set the signing secret

`infra/locals.tf` injects `APP_*`, `IS_LOCAL`, `POSTGRES_*` and `MONGO_*` — no
`JWT_SECRET`. Without one, `auth.jwt_secret()` raises rather than falling back
to the development default committed in this repository, so **sign-in returns
500 until this runs**.

That failure is deliberate. A default anyone can read from git would let them
mint a `facility_admin` token for any account, and a loud 500 is better than
that working silently.

```bash
./deploy/set-jwt-secret.sh
```

It generates a secret, sets it on all four functions, and prints the value —
save it. Every service must sign with the same key.

**This has to run after every deploy.** Terraform owns `environment_variables`,
so the next `apply` removes it. Re-apply the same secret rather than generating
a new one, or every token in circulation stops working:

```bash
JWT_SECRET='<the saved value>' ./deploy/set-jwt-secret.sh
```

**Check it worked:** sign in through the deployed API and get a token back.

---

## Step 5 — Deploy the frontend

```bash
./bin/deploy-frontend.sh
```

Builds the React app with the CloudFront URL baked in, syncs to S3 and
invalidates the distribution.

Then make deep links work:

```bash
./deploy/fix-spa-routing.sh
```

Without it, opening `/incidents` directly returns S3's raw `AccessDenied` XML
instead of the app — only `/` works, and a refresh or a shared link breaks.

Two given settings combine to cause it, neither wrong alone:
`infra/cloudfront.tf` maps a **404** to `/index.html`, which is what makes
client-side routes work — but the bucket policy grants only `s3:GetObject`, and
without `s3:ListBucket` S3 answers **403** for a missing key rather than 404,
because it will not reveal whether the object exists. CloudFront has no 403
mapping, so the XML is served as-is.

The script grants `s3:ListBucket` to the same CloudFront principal, reusing the
existing statement's condition so access cannot widen. Like the signing secret,
**Terraform owns the bucket policy and reverts this on the next apply.**

Allow a minute, or invalidate:

```bash
aws cloudfront create-invalidation --distribution-id $(cd infra && terraform output -raw cloudfront_distribution_id) --paths '/*'
```

---

## Step 6 — Smoke test

Health, which needs no token:

```bash
API=$(cd infra && terraform output -raw api_base_url)
for s in users incidents facilities engineers; do
  curl -s -o /dev/null -w "$s-service %{http_code}\n" "$API/api/$s-service/health"
done
```

Four 200s.

Then the path that exercises auth, the database and the signing secret together:

```bash
curl -s -X POST "$API/api/users-service/auth/register" \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@acme.inc","password":"ChangeMe!2026","full_name":"Your Name"}'

curl -s -X POST "$API/api/users-service/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@acme.inc","password":"ChangeMe!2026"}'
```

A `access_token` in the response means Lambda, Aurora, the schema and the secret
are all working.

Confirm the docs are **not** public — they are gated on `IS_LOCAL`:

```bash
curl -s -o /dev/null -w "docs %{http_code}\n" "$API/api/users-service/docs"   # 404
```

---

## When something breaks

| Symptom | Cause |
|---|---|
| `AccessDenied` XML on any route but `/` | Step 5's routing fix not applied, or a deploy reverted it |
| An API 404 arrives as 200 with HTML | Expected — CloudFront rewrites it; `api/client.js` recognises it |
| `ExpiredToken` on any command | Credentials lapsed — Step 1 again |
| 500 on sign-in, health fine | `JWT_SECRET` missing — Step 4, or a deploy wiped it |
| 500 on anything touching data | Schema not created — Step 3 |
| Lambda times out | Cannot reach Aurora; check both are on the same subnets and security groups |
| `relation does not exist` | Schema applied to the wrong database |
| `docs` returns 200 | `IS_LOCAL` is `true` in a deployed function — it should be `false` |

Lambda logs are in CloudWatch under `/aws/lambda/<function-name>`. Read the
traceback there rather than guessing from the browser.

---

## Teardown

```bash
./bin/cleanup-environment.sh
```

The S3 bucket must be empty before Terraform can remove it.

---

## What is not solved

**Two post-deploy steps are manual and get reverted.** Terraform owns both the
Lambda environment and the bucket policy, so `set-jwt-secret.sh` and
`fix-spa-routing.sh` must be re-run after every `apply`. Both are one command
and safe to repeat, but neither is enforced — forgetting the first breaks
sign-in, forgetting the second breaks every deep link. A wrapper script that
runs deploy-then-both would remove the footgun.

**The signing secret lives in an environment variable**, applied out of band and
wiped by every `apply`. Secrets Manager would be the better home —
`infra/policy.tftpl` already grants `secretsmanager:*` on app-prefixed secrets —
but the Lambda *execution* role is created outside Terraform and its permissions
are unknown, so that path is unverified.

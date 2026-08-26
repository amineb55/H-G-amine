# HSE Inspection Analysis Service

FastAPI service for AI-assisted analysis of HSE inspection media. Media is
uploaded, analyzed in the background, and deleted as soon as the analysis
ends — only the result is retained.

## Requirements

- Python 3.10+

## Project structure

```
app/
  main.py                       FastAPI app and endpoints
  config.py                     settings loaded from .env
  models/schemas.py             Finding / InspectionResult schemas
  services/analysis_engine.py   analysis engine interface
  services/providers/           provider implementation behind that interface
  services/inspection_prompt.py rule catalogs and system prompt assembly
  services/assignment.py        assignment, deadlines and review summary
  services/notification.py      grouping findings into per-recipient emails
  services/evidence.py          evidence frames and capture time
  services/report.py            the French PDF report
  services/notifiers/           email provider implementation
  services/storage.py           media storage (local filesystem)
  services/inspection_store.py  inspection state (in-memory)
  services/job_queue.py         job dispatch interface
  services/inspection_job.py    the background analysis job
rules/                          rule catalogs and assignment catalog (YAML)
prompts/inspection.txt          system prompt template
templates/review.html           the review screen
requirements.txt
.env.example
```

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Liveness probe. |
| `POST` | `/inspections` | Upload media and queue an analysis. Returns `202`. |
| `GET` | `/inspections/{id}` | Current status and result. |
| `GET` | `/inspections/{id}/review` | Enriched result plus review counts. |
| `POST` | `/inspections/{id}/findings/{index}/approve` | Approve one finding. |
| `POST` | `/inspections/{id}/findings/{index}/reject` | Reject one finding. |
| `POST` | `/inspections/{id}/dispatch` | Email the approved findings to their owners. |
| `PATCH` | `/inspections/{id}/findings/{index}` | Correct a finding. |
| `POST` | `/inspections/{id}/findings` | Add a finding the analysis missed. |
| `GET` | `/inspections/{id}/evidence/{filename}` | One retained evidence image. |
| `GET` | `/inspections/{id}/report.pdf` | The PDF report. |
| `GET` | `/review/{id}` | The review screen. |

`POST /inspections` takes a multipart body with a `referentiel` field
(`bureaux` or `btp`) and a `files` field holding **either one video or up to
ten images**. Accepted types are `video/mp4`, `video/quicktime`, `image/jpeg`
and `image/png`, each capped at 200 MB.

| Status | Meaning |
| --- | --- |
| `202` | Accepted and queued. |
| `400` | Bad combination of files (video and images mixed, too many). |
| `413` | A file exceeds the size limit. |
| `415` | Unsupported media type. |
| `422` | Missing or invalid `referentiel`. |

`GET /inspections/{id}` returns `status` (`processing`, `done` or `failed`),
`result` (the `InspectionResult` once done, otherwise `null`) and `error`
(the reason when the analysis failed, otherwise `null`). Unknown ids give
`404`.

## Assignment and deadlines

Once the analysis returns, every finding is enriched by
`app/services/assignment.py` before it is stored.

**Who is accountable** comes from `app/rules/responsables.yaml`: a table of
roles, a rule-to-role assignment per rule id, and an escalation rule. It is
validated on load — an assignment pointing at an unknown role, an escalation
target that does not exist or a malformed address all fail loudly rather than
silently dropping a recipient. A rule with no entry in the catalog leaves the
finding unassigned and is logged.

**Deadlines** are computed from the severity actually observed, not the rule
default:

| Observed severity | Deadline |
| --- | --- |
| `arret_immediat` | today, `immediate: true` |
| `critique` | +1 day |
| `majeur` | +7 days |
| `mineur` | +30 days |

The rule's own `deadline_days` is the fallback if a severity outside that grid
ever reaches the enrichment.

**Who is notified** is the assigned role, plus the escalation role when the
severity is `arret_immediat`. Addresses are de-duplicated, so roles sharing a
mailbox are notified once.

Findings whose analysis status is `a_verifier` are enriched like any other and
carry `requires_review: true`. That flag is shown in the review screen so the
auditor knows the finding is low-confidence, but it does not block dispatch:
approving is the human act that resolves the doubt.

## Auditor corrections

Approving or rejecting is not the only thing an auditor can do: the analysis
can be corrected outright.

`PATCH /inspections/{id}/findings/{index}` accepts `observed_severity`,
`observation`, `rule_id` and `assigned_role`. Everything derived from those
values is recomputed — the rule title, the accountable role, the deadline, the
recipients and the escalation. An `assigned_role` set by hand overrides the
catalog.

What the analysis originally reported is preserved: the first override stores
`original_severity` and `original_observation`, and the finding is flagged
`edited_by_human`. The correction is therefore always auditable, in the review
screen and in the PDF alike.

`POST /inspections/{id}/findings` adds a finding the analysis missed, from
`rule_id`, `observation` and `observed_severity`. Manual findings carry
`source: "human"` — everything else carries `source: "ai"` — and are assigned
and scheduled by the same rules.

## PDF report

`GET /inspections/{id}/report.pdf` renders the French report with reportlab:
header (referential, capture time, edition date, counts by severity, stop-work
banner when one applies), then one section per finding with its evidence image
embedded, the rule title, observation, severity, justification, ISO clause,
assignee, deadline, and whether it was detected by the analysis, corrected by
the auditor, or added by them. The footer carries *Analyse assistée par IA,
validée par un auditeur.*

The same PDF is attached to every dispatch email.

## Human validation

Every finding carries `validation_status`, `pending` until a human decides.
`POST .../approve` and `POST .../reject` record that decision; rejecting a
finding that was already queued removes it from the queue.

`POST /inspections/{id}/dispatch` emails the approved findings to the people
accountable for them. Only findings left `pending` or `rejected` are excluded —
an approved finding is sent whatever its confidence, and the ones flagged for
review are listed in `approved_from_review` so the decision stays visible.

## Notifications

Emails are grouped **by recipient, not by finding**: one person receives one
message listing everything they own, rather than eight separate emails.

Findings that require work to stop immediately are pulled into their own
message, sent before the digests, with the subject prefix `[ARRET IMMEDIAT]` —
an imminent danger is never buried in a summary. A recipient therefore receives
at most two emails per dispatch.

Each finding carries its own outcome: `dispatch_status` is `not_queued`, `sent`
or `failed`, with `message_id` on success and `dispatch_error` on failure. The
response reports one `EmailOutcome` per email attempted.

- **Partial failure never rolls back a success.** Each email is independent; a
  failed one marks only its own findings `failed` and leaves delivered ones
  alone.
- **Nothing is ever sent twice.** A finding already `sent` is skipped on any
  later dispatch and listed in `already_sent`, so calling dispatch again after
  a partial failure retries only what failed.
- Approved findings with no recipient are reported in `unassigned` rather than
  silently dropped.

Each email opens with a short paragraph addressed to the recipient's role,
stating what they must do and by when. Urgency is settled in the first two
lines — an immediate-stop email says the work must stop now and that no delay
applies; a digest states the soonest deadline in plain words ("aujourd'hui",
"demain", "sous 7 jours") and says explicitly that nothing requires stopping
work. The evidence image is embedded in the body, and the PDF report is
attached.

`POST /inspections/{id}/dispatch` accepts an optional body `{"cc": [...]}`.
Those addresses are copied on every email of that dispatch; the format is
validated server-side and in the review screen, and a recipient is never copied
on their own message.

Everything the model wrote is HTML-escaped before it reaches an email body.

### Diagnosing a delivery failure

A transport failure is logged at `ERROR` before it is wrapped, with the
category, the host, the recipient, the exception type and its root cause. The
API key is never logged, nor is the payload that carries it:

```
ERROR Email transport failure [dns] host=api.example.com recipient=... :
      ConnectError: [Errno -2] Name or service not known (root cause gaierror: ...)
```

The wrapped message names the cause rather than saying the service could not
be reached: `dns`, `connection_refused`, `tls`, `tls_verification`, `proxy`,
`network_unreachable`, `connection_reset`, `timeout`, or an HTTP status.

`GET /debug/notifier` runs the same path step by step and reports where it
stops — configuration presence, DNS resolution, TCP and TLS, then a read-only
API call that sends no mail. It returns **no secret**: only whether a key and
a sender are configured, the host being contacted, and each step's outcome.

```json
{
  "endpoint_host": "api.example.com", "endpoint_scheme": "https",
  "dns": {"ok": true, "addresses": ["..."]},
  "tcp_tls": {"ok": true, "tls_version": "TLSv1.3", "certificate_issuer": "..."},
  "api_call": {"ok": false, "status_code": 401, "message": "..."},
  "outcome": "failed at api_call"
}
```

Any text derived from an exception — the wrapped message, the log line, the
traceback, and every field of the diagnostic response — is scrubbed of the
configured secret values first. A library that rejects a malformed request
quotes the offending input back at you, credentials included, so redaction is
applied at the formatter as well as at each call site: a value shorter than
six characters is left alone rather than mangling unrelated text.

Secrets are also stripped of surrounding whitespace when read. A value
injected from a secret store often carries a trailing newline, which makes an
HTTP header illegal and produces exactly the kind of error that leaks the
value. Startup names any variable that had to be stripped, never its value:

```
WARNING Surrounding whitespace was stripped from: NOTIFIER_API_KEY.
```

This endpoint is **temporary diagnostic tooling**. It is unauthenticated like
the rest of the service, so it does disclose the provider host and whether
credentials are set — remove it once the problem is understood.

### Email provider

`app/services/notifiers/email_notifier.py` is the only module aware of which
email provider is used — its endpoint, payload and status codes stop there. It
exposes one function:

```python
async def send(to: str, subject: str, html: str) -> str  # returns the message id
```

It calls the provider's transactional HTTP API with `httpx`; no provider SDK is
installed. Failures surface as readable messages — bad credentials, rate
limiting, unavailability, timeout and unreachable host each get their own.

### Review screen

`GET /review/{id}` serves `templates/review.html`: plain HTML and vanilla JS,
no framework and no build step. It loads its data from the review endpoint and
shows, per finding, the timestamp, rule title, observation, observed severity
in colour, the severity justification, confidence, ISO 45001 clause, the
accountable person and the deadline. Findings are ordered most serious first,
`arret_immediat` ones carry an explicit stop-work banner, and the header counts
findings by severity and by review state. Low-confidence findings are badged
and their confidence highlighted, so an auditor approving one sees what they
are approving.

The screen is in French; the API responses and this README are in English.

## Persistence

Inspections are stored in a document database, one document per inspection in
the `inspections` collection, keyed by `inspection_id`. An inspection —
including its findings, their enrichment, and their validation and dispatch
state — survives a restart or a redeploy.

The client is synchronous, so every call runs in a worker thread and the event
loop is never blocked. **The store functions are therefore `async`**: same
names, same arguments, same return values as before, but callers `await` them.
A synchronous function cannot offload work to a thread without blocking the
caller, so keeping them synchronous would have defeated the purpose.

Credentials come from the ambient environment (application default
credentials) — there is no key file in the repository. The project id is read
from `GOOGLE_CLOUD_PROJECT`, falling back to whatever the credentials name.

Records are written through a normaliser that turns enums and dates into plain
scalars, and read back through the pydantic models, so datetimes round-trip
exactly.

### When the store is unreachable

The client is built on first use, never at import, and the application starts
regardless. A startup probe reports the outcome in the logs:

```
INFO:     app.main - Inspection store: persistent, collection 'inspections'.
ERROR:    app.main - Inspection store UNREACHABLE: ... The application is
                     running, but every inspection request will fail until
                     this is fixed.
```

Every store call is bounded by `STORE_TIMEOUT_SECONDS` and fails with a
readable message rather than hanging — the client library retries internally
and can outlive its own timeout, so the deadline is enforced at the call
boundary. A worker thread cannot be interrupted, so a call that overruns is
left to finish on its own; with an unreachable store those stragglers can
delay process shutdown.

### Local work without credentials

Set `STORE_BACKEND=memory` to use the in-process dictionary instead. Startup
says so explicitly:

```
WARNING:  app.main - Inspection store: IN MEMORY. Inspections are lost when
                     this process stops.
```

### Evidence storage

Evidence images go to object storage, selected by `STORAGE_BACKEND`:

- `gcs` (default) — objects at `evidence/{inspection_id}/{filename}` in the
  bucket named by `EVIDENCE_BUCKET`. Survives an instance being replaced.
- `local` — a directory under `EVIDENCE_DIR`, for development without cloud
  credentials.

Callers never learn which backend is in use: the evidence endpoint, the PDF
generator and the email builder all read through `app/services/storage.py`,
none of them assumes a filesystem path. Inspection ids and file names are
validated against a strict pattern before they reach either backend, so
nothing can be read outside an inspection's own space.

Uploaded media is the exception and stays on local disk: the analysis and the
frame extraction need real files, and it is deleted as soon as the job ends.
On Cloud Run that disk is in-memory and counts against the instance's memory,
so a 200 MB upload is 200 MB of the 1 GiB allowance.

## Deployment

The service runs on Cloud Run from the `Dockerfile`: `python:3.11-slim`,
multi-stage, a single uvicorn worker, listening on the `PORT` the platform
provides (8080 when run without one) as a non-root user. `ffmpeg` comes from
the `imageio-ffmpeg` wheel as a statically linked binary — verified with
`ldd`, it has no dynamic dependencies — so the slim image needs no apt
package and downloads nothing at run time.

Deploy with `./deploy.sh` (bash) or `.\deploy.ps1` (PowerShell). Both run the
same `gcloud run deploy` against `europe-west1` with 1 GiB and a 300 s
timeout, and both take the project from `PROJECT_ID` or your gcloud default.

### Secrets

Secrets are injected as environment variables from Secret Manager; the
application never calls Secret Manager itself and no key file exists in this
repository.

| Secret | Environment variable |
| --- | --- |
| `analysis-engine-api-key` | `ANALYSIS_ENGINE_API_KEY` |
| `notifier-api-key` | `NOTIFIER_API_KEY` |
| `notifier-sender-email` | `NOTIFIER_SENDER_EMAIL` |

A missing secret does not stop the service from starting; it is reported at
startup **by name only**, and the feature that needs it fails with a readable
message:

```
ERROR: Missing configuration: NOTIFIER_API_KEY. The application is running,
       but the features that need them will fail until they are provided.
```

### IAM

Grant the Cloud Run service account three roles. By default that account is
`PROJECT_NUMBER-compute@developer.gserviceaccount.com`; find it with:

```bash
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
```

| Role | Why |
| --- | --- |
| `roles/datastore.user` | read and write the inspection documents |
| `roles/storage.objectAdmin` | write, read and delete evidence objects |
| `roles/secretmanager.secretAccessor` | read the three secrets at start-up |

```bash
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA}" --role="roles/datastore.user"

gcloud storage buckets add-iam-policy-binding gs://hse-audit-agent-evidence \
  --member="serviceAccount:${SA}" --role="roles/storage.objectAdmin"

gcloud secrets add-iam-policy-binding analysis-engine-api-key \
  --member="serviceAccount:${SA}" --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding notifier-api-key \
  --member="serviceAccount:${SA}" --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding notifier-sender-email \
  --member="serviceAccount:${SA}" --role="roles/secretmanager.secretAccessor"
```

`roles/storage.objectAdmin` is granted on the bucket rather than the whole
project, so the service can only touch its own evidence.

### Health and startup

`GET /health` touches nothing downstream and answers `200` even when the
store and the bucket are both unreachable — the platform must never restart a
healthy container because of a downstream outage. Requests that do need a
backend return `503` with the reason:

```json
{"detail": "The inspection store did not answer in time; could not read this inspection."}
```

Startup logs which backends are active, and never logs a secret value:

```
INFO:  Configuration: all required secrets are present.
INFO:  Inspection store: persistent, collection 'inspections'.
INFO:  Evidence storage: object storage, bucket 'hse-audit-agent-evidence'.
```

## Processing model

Uploads are analyzed outside the request cycle, so the client gets its
`inspection_id` immediately and polls for the result.

- Jobs are dispatched through `app/services/job_queue.py`, which currently
  runs them in-process via FastAPI `BackgroundTasks`. Swapping in a real
  broker means replacing that module, not the endpoints.
- Inspection state lives in `app/services/inspection_store.py`, behind
  `get` / `set` / `update`. See **Persistence** below.
- A failing job records `status: failed` and the error message. It never
  propagates, so a bad analysis cannot take the server down.

### Media retention and evidence

Uploaded media is written under `data/uploads/{inspection_id}/` and deleted by
`storage.delete_media()` in the job's `finally` block — so it is removed
whether the analysis succeeds or fails. Client filenames are never reused on
disk: each file is stored under a generated name with a suffix derived from its
validated media type.

What survives is the **evidence**, under `data/evidence/{inspection_id}/`:

- **Video**: one still is extracted at each finding's `timestamp_sec`, and the
  video is deleted. Two findings at the same second share one frame.
- **Images**: the image a finding came from is kept, downscaled. The model
  reports which image it observed as the 0-based index in `timestamp_sec`; an
  index outside the batch falls back to the first image.

Each finding carries `evidence_image`, served by
`GET /inspections/{id}/evidence/{filename}`. File names are validated against a
strict pattern and resolved inside the inspection's own directory, so nothing
outside it can be reached.

`captured_at` is the moment the media was shot, read from EXIF
`DateTimeOriginal` on images and the container creation time on video — the
earliest one found. **It is never inferred**: media without that metadata
leaves it `null`, and the review screen and report say so rather than
substituting a plausible date.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Then:

- Health check: http://127.0.0.1:8000/health -> `{"status":"ok"}`
- API docs: http://127.0.0.1:8000/docs

## Testing the endpoints

```bash
# One video
curl -i -X POST http://127.0.0.1:8000/inspections \
  -F "referentiel=btp" \
  -F "files=@/path/to/clip.mp4;type=video/mp4"

# Up to ten images
curl -i -X POST http://127.0.0.1:8000/inspections \
  -F "referentiel=bureaux" \
  -F "files=@/path/to/one.jpg;type=image/jpeg" \
  -F "files=@/path/to/two.png;type=image/png"

# Poll the result
curl http://127.0.0.1:8000/inspections/<inspection_id>
```

## Configuration

Settings are read from the environment and from `.env` (see `.env.example`).
`.env` is git-ignored and must never be committed.

| Variable | Default | Purpose |
| --- | --- | --- |
| `UPLOAD_DIR` | `data/uploads` | Where media is held during analysis. |
| `MAX_UPLOAD_BYTES` | `209715200` | Per-file size limit (200 MB). |
| `MAX_IMAGES` | `10` | Images accepted per inspection. |
| `EVIDENCE_DIR` | `data/evidence` | Where retained evidence images live. |
| `EVIDENCE_MAX_PIXELS` | `1280` | Longest edge of a stored evidence image. |
| `STORE_BACKEND` | `firestore` | `firestore` to persist, `memory` for local work. |
| `STORE_COLLECTION` | `inspections` | Collection holding the inspections. |
| `GOOGLE_CLOUD_PROJECT` | *(empty)* | Project id. Empty uses the credentials' own. |
| `STORE_TIMEOUT_SECONDS` | `15` | Deadline on each store call. |
| `STORE_PROBE_SECONDS` | `5` | Deadline on the startup probe. |
| `LOG_LEVEL` | `INFO` | Application log level. |
| `STORAGE_BACKEND` | `gcs` | `gcs` for object storage, `local` for a directory. |
| `EVIDENCE_BUCKET` | *(empty)* | Bucket holding the evidence. Required in `gcs` mode. |
| `PORT` | `8080` | Port the container listens on. Supplied by the platform. |
| `ANALYSIS_ENGINE_API_KEY` | *(empty)* | Provider credentials. Required to analyze. |
| `ANALYSIS_ENGINE_MODEL` | *(empty)* | Model identifier. Empty uses the provider default. |
| `ANALYSIS_ENGINE_TIMEOUT_SECONDS` | `120` | Per-request timeout. |
| `ANALYSIS_ENGINE_VIDEO_FPS` | `1.0` | Frames sampled per second of video. |
| `BREVO_API_KEY` | *(empty)* | Email provider credentials. Required to send. |
| `BREVO_SENDER_EMAIL` | *(empty)* | Address emails are sent from. |
| `NOTIFIER_SENDER_NAME` | `Inspection HSE` | Display name on outgoing email. |
| `NOTIFIER_TIMEOUT_SECONDS` | `30` | Per-request timeout when sending. |
| `NOTIFIER_API_URL` | *(empty)* | Override the provider endpoint. Empty uses the default. |

## Analysis engine

`app/services/analysis_engine.py` exposes a single vendor-neutral entry point:

```python
async def analyze(media_path: str, referentiel: str) -> dict
```

`media_path` is the directory holding one inspection's media — one video or a
batch of images. The engine delegates to the provider in
`app/services/providers/`, which is the **only** module allowed to import the
provider SDK: the model identifier, the SDK types and its error classes all
stop there. The import is lazy, so the rest of the application starts and runs
without the SDK installed.

Swapping providers means writing a new module in `providers/` and changing the
delegation in `analysis_engine.py`. Nothing else in the codebase refers to a
provider.

Failures never surface as stack traces. Each cause gets its own message,
stored on the inspection and returned by `GET /inspections/{id}`:

| Cause | Message stored |
| --- | --- |
| No API key configured | The analysis engine is not configured: no API key is set. |
| Rate limited | The analysis engine is rate limited. Retry this inspection later. |
| Bad credentials | The analysis engine rejected the configured credentials. |
| Timeout | The analysis engine did not respond in time. |
| Provider unavailable | The analysis engine is temporarily unavailable. Retry this inspection later. |
| Unusable response, twice | The analysis engine returned a result in an unexpected format, twice in a row. |

Token usage is logged at INFO on every call, so cost can be tracked:

```
Analysis call: model=... attempt=1 prompt_tokens=1200 output_tokens=300 thoughts_tokens=50 total_tokens=1550
```

### Rule catalogs

`app/rules/<referentiel>.yaml` holds the rules audited for each referential —
`bureaux.yaml` and `btp.yaml`. Each rule carries `id`, `title`,
`default_severity`, `deadline_days` and `iso_45001_clause`. The files ship with
two example rules each; replace their contents with the real catalogs. The
structure is validated on load, and an unknown referential, a malformed file or
a duplicate rule id fails the inspection with a readable message.

### System prompt

`app/prompts/inspection.txt` is the prompt template, editable without touching
code. Two placeholders are substituted at run time: `{{REFERENTIEL}}` and
`{{RULES}}`, the latter being the loaded catalog. The prompt instructs the model
to audit only against that catalog, to check the scene matches the referential
(otherwise `scene_valid: false` and no findings), to report only what is
visibly observable, to mark anything below 0.7 confidence as `a_verifier`, to
refer to people by role and location and never identify them, and to justify
any severity it raises or lowers relative to the rule default.

### Response handling

Structured JSON output is requested from the model and validated with pydantic.
An unparseable or non-conforming response triggers **one** retry carrying the
validation error as a corrective instruction; a second failure fails the
inspection. Unvalidated data is never returned. Video is sampled at one frame
per second (`ANALYSIS_ENGINE_VIDEO_FPS`) to bound the cost of a long clip, and
the provider deletes its own copy of the media once the call is over.

## Schema

`Finding`

| Field | Type | Notes |
| --- | --- | --- |
| `timestamp_sec` | `int` | offset in the media, seconds |
| `rule_id` | `str` | referential rule identifier |
| `observation` | `str` | what was observed |
| `default_severity` | `str` | severity defined by the rule |
| `observed_severity` | `str` | severity retained for this observation |
| `severity_reason` | `str` | justification |
| `iso_45001_clause` | `str` | related ISO 45001 clause |
| `confidence` | `float` | between 0.0 and 1.0 |
| `status` | `str` | review status |

`InspectionResult`: `inspection_id: str`, `referentiel: str`,
`scene_valid: bool`, `scene_detected: str`, `findings: list[Finding]`.

Severity values: `arret_immediat`, `critique`, `majeur`, `mineur`.
Status values: `nc`, `a_verifier`.

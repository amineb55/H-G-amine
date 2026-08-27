# HSE Audit Agent

An autonomous agent that turns a workplace safety walkthrough into dispatched
corrective actions — without a human writing the report.

An inspector uploads a short video or a few photos from a site walkthrough. The
agent identifies the work environment, detects safety non-conformities against
the matching rule catalogue, maps each one to the relevant ISO 45001 clause,
decides its real severity from what is actually visible, assigns it to the
responsible role with a risk-based deadline, and — after a single human
approval — emails each recipient a personalised action notice with the evidence
photo and a PDF report attached.

**Live service:** https://hse-audit-agent-2161166844.europe-west1.run.app

**Hackathon:** All Things Agentic — track: The Taskmaster

---

## Why this is an agent, not a chatbot

The value is not the analysis. It is everything the system does *after* the
upload, on its own:

| Decision | Made by the agent |
|---|---|
| Which sector this is | Yes — detected from the media, no user input |
| Which rule was breached | Yes — against the matching catalogue |
| How severe it *actually* is | Yes — escalated or lowered from the rule default, with a written justification |
| Whether work must stop now | Yes — `arret_immediat` triggers a separate, priority alert |
| Who is responsible | Yes — from the assignment catalogue |
| By when | Yes — computed from the observed severity |
| Whether to escalate to management | Yes — imminent danger also notifies the site director |
| Whether it is confident enough to assert it | Yes — below 0.7 confidence a finding is flagged `a_verifier`, never asserted |
| Whether to audit at all | Yes — an unrecognised sector produces no findings, not guesses |

The human does one thing: approve, correct, or reject. Nothing leaves the system
without that approval.

---

## Scope of this demo

Two referentials are implemented and field-tested:

- **`bureaux`** — offices and administrative premises (12 rules)
- **`btp`** — construction sites (12 rules)

The rule catalogues live in `app/rules/*.yaml`, not in code. Adding a sector is
a new YAML file — no code change. Four more sectors (industry, healthcare,
logistics, hospitality, transport) are drafted but deliberately out of scope: a
safety rule catalogue that has not been validated in the field has no business
being shipped. We would rather present two sectors that work than six that look
impressive in a diagram.

---

## Design decisions worth reading

**The agent detects the sector; it does not guess it.** Detection runs as a
first pass on the media. If confidence is below 0.7, or if the scene matches no
available catalogue, the agent produces no findings and says so — it never picks
a sector just to have something to audit. The auditor can then choose manually.

**Nothing is asserted that a human did not approve.** Rejected and pending
findings are excluded from the PDF report and from every email. The report
states how many findings were rejected or left pending, so the auditor's
decision stays traceable without its content being asserted.

**The auditor can correct the model, not just veto it.** Severity, observation
text, rule and assignee are editable. Original AI values are retained
(`original_severity`, `original_observation`) so every correction is auditable.
The auditor can also add a finding the model missed.

**No individual is ever identified.** The prompt forbids describing or
characterising people; findings refer to role and location only ("an operator
near the east wall"). This is deliberate: the tool detects dangerous situations,
not individual fault. That single constraint is what makes it deployable in
front of a works council instead of being blocked as workplace surveillance.

**Source media is destroyed once its audit is done.** Only the evidence frames
for actual findings are retained. For video, one still frame is extracted per
finding timestamp and the video is deleted — locally and at the provider.

The one narrow exception: when detection cannot determine the sector, no audit
has run, so the media is held briefly with a short TTL so the auditor can pick a
sector without re-uploading. It is deleted the moment any audit runs against it,
whether that audit succeeds or fails, and expires automatically otherwise. The
retention rule was never "retain nothing" — it is "retain only what documents a
finding, once the audit is done". Media whose audit has not yet happened has not
completed its lifecycle. The UI states this explicitly rather than making a
silent exception.

**Every external dependency sits behind a neutral interface.** The analysis
provider, the object storage, the inspection store and the email notifier each
have exactly one implementation file. No other module imports a vendor SDK or
names a vendor. Swapping any of them is a one-file change.

---

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the diagram and the reasoning behind
each boundary.

| Layer | Technology |
|---|---|
| API & UI | FastAPI, server-rendered templates, vanilla JS (no build step) |
| Analysis | Gemini 3.5 Flash via the Gemini API, structured JSON output |
| Async execution | Background jobs behind a swappable queue interface |
| State | Firestore (native mode, `europe-west1`) |
| Evidence | Cloud Storage |
| Reports | ReportLab |
| Notifications | Transactional email API |
| Runtime | Cloud Run, `europe-west1` |
| Secrets | Secret Manager, injected as environment variables |

---

## Running locally

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then fill in the values below
uvicorn app.main:app --reload --port 8000
```

Open http://127.0.0.1:8000 — the landing page. `/health` returns
`{"status":"ok"}` without touching any backend.

### Environment

| Variable | Purpose |
|---|---|
| `ANALYSIS_ENGINE_API_KEY` | Gemini API key |
| `ANALYSIS_ENGINE_MODEL` | Optional model override |
| `NOTIFIER_API_KEY` | Transactional email API key |
| `NOTIFIER_SENDER_EMAIL` | Verified sender address |
| `GOOGLE_CLOUD_PROJECT` | GCP project id |
| `STORE_BACKEND` | `firestore` (default) or `memory` |
| `STORAGE_BACKEND` | `gcs` (default) or `local` |
| `EVIDENCE_BUCKET` | Cloud Storage bucket for evidence |

`STORE_BACKEND=memory STORAGE_BACKEND=local` runs the whole flow with no cloud
credentials — useful for a first look.

### Trying it

Open the landing page, drop a photo or video, and press **Lancer l'analyse**.
There is also a one-click example on the page for anyone without a site photo
to hand.

Via the API, the sector is optional — omit it and the agent detects it:

```bash
curl -X POST http://127.0.0.1:8000/inspections \
  -F "files=@walkthrough.jpg;type=image/jpeg"
```

---

## Deploying

```bash
./deploy.sh          # Windows: .\deploy.ps1
```

The service account needs `roles/datastore.user`,
`roles/storage.objectAdmin` and `roles/secretmanager.secretAccessor`.
Exact grant commands are in `deploy.sh`.

---

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Landing page |
| `GET` | `/health` | Liveness — never touches a backend |
| `GET` | `/referentiels` | Available catalogues, from YAML |
| `POST` | `/inspections` | Upload media, returns `202` and an id. `referentiel` optional |
| `GET` | `/inspections/{id}` | Job status, current stage, and result |
| `GET` | `/inspections/{id}/review` | Enriched result for the review screen |
| `PATCH` | `/inspections/{id}/findings/{i}` | Correct a finding |
| `POST` | `/inspections/{id}/findings` | Add a finding the model missed |
| `POST` | `/inspections/{id}/findings/{i}/approve` | Approve |
| `POST` | `/inspections/{id}/findings/{i}/reject` | Reject |
| `POST` | `/inspections/{id}/dispatch` | Send approved findings |
| `GET` | `/inspections/{id}/evidence/{filename}` | Evidence frame |
| `GET` | `/inspections/{id}/report.pdf` | PDF report |
| `GET` | `/review/{id}` | Review UI |

---

## Known limits

Stated plainly, because an audit tool that hides its limits is worse than none:

- **Detection is partial.** On a dense construction scene the model finds the
  prominent hazards and misses secondary ones. It assists an auditor; it does
  not replace one.
- **The upstream model API returns `503` under load.** The agent handles this
  cleanly — the inspection is marked failed with a readable message and a retry
  action, the container stays healthy, and no partial state is written. But a
  retry may be needed.
- **Inline evidence images use data URIs**, which Gmail's web client blocks. The
  attached PDF carries the same images reliably.
- **Correcting an already-sent finding does not re-send it.** An email cannot be
  unsent; in real audit practice a correction is issued, history is not
  rewritten.
- **Sender reputation.** The demo sends from a freemail address without DKIM, so
  messages may land in spam.
- **This produces a self-assessment, not a certification.** Only an accredited
  body certifies conformity to ISO 45001.

---

## Interface language

The operator interface, reports and emails are in French, the working language
of the target users. API responses, code and documentation are in English.

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
  services/storage.py           media storage (local filesystem)
  services/inspection_store.py  inspection state (in-memory)
  services/job_queue.py         job dispatch interface
  services/inspection_job.py    the background analysis job
rules/                          one rule catalog per referential (YAML)
prompts/inspection.txt          system prompt template
templates/                      reserved for later
requirements.txt
.env.example
```

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Liveness probe. |
| `POST` | `/inspections` | Upload media and queue an analysis. Returns `202`. |
| `GET` | `/inspections/{id}` | Current status and result. |

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

## Processing model

Uploads are analyzed outside the request cycle, so the client gets its
`inspection_id` immediately and polls for the result.

- Jobs are dispatched through `app/services/job_queue.py`, which currently
  runs them in-process via FastAPI `BackgroundTasks`. Swapping in a real
  broker means replacing that module, not the endpoints.
- Inspection state lives in `app/services/inspection_store.py`, an in-memory
  dict behind `get` / `set` / `update`. It is lost on restart until a
  database replaces it.
- A failing job records `status: failed` and the error message. It never
  propagates, so a bad analysis cannot take the server down.

### Media retention

Uploaded media is written under `data/uploads/{inspection_id}/` and deleted
by `storage.delete_media()` in the job's `finally` block — so it is removed
whether the analysis succeeds or fails. Only the result is kept. Client
filenames are never reused on disk: each file is stored under a generated
name with a suffix derived from its validated media type.

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
| `ANALYSIS_ENGINE_API_KEY` | *(empty)* | Provider credentials. Required to analyze. |
| `ANALYSIS_ENGINE_MODEL` | *(empty)* | Model identifier. Empty uses the provider default. |
| `ANALYSIS_ENGINE_TIMEOUT_SECONDS` | `120` | Per-request timeout. |
| `ANALYSIS_ENGINE_VIDEO_FPS` | `1.0` | Frames sampled per second of video. |

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

# HSE Inspection Analysis Service

FastAPI service skeleton for AI-assisted analysis of HSE inspection media.
This is a skeleton only: the analysis engine returns an empty result and no
upload logic is wired yet.

## Requirements

- Python 3.10+

## Project structure

```
app/
  main.py                      FastAPI app, /health endpoint
  config.py                    settings loaded from .env
  models/schemas.py            Finding / InspectionResult schemas
  services/analysis_engine.py  analysis engine interface (stub)
templates/                     reserved for later
requirements.txt
.env.example
```

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

## Configuration

Settings are read from the environment and from `.env` (see `.env.example`).
`.env` is git-ignored and must never be committed.

## Analysis engine

`app/services/analysis_engine.py` exposes a single vendor-neutral entry point:

```python
async def analyze(media_path: str, referentiel: str) -> dict
```

It currently returns a hardcoded empty result. The provider implementation is
injected behind this interface later, so nothing outside this module needs to
change when it lands.

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

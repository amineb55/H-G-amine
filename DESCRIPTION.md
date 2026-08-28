# Devpost submission text

---

## Full version

### The problem

Every industrial site, construction project and office building is legally
required to run safety inspections. In practice the same thing happens
everywhere: an inspector walks the site, takes notes and photos, then spends two
to four hours back at a desk writing them up. By the time the report reaches the
person who can actually fix the hazard, days have passed. Some findings never
reach anyone at all — they die in a document nobody opens.

The bottleneck was never the walking. It was everything after it.

### What HSE Audit Agent does

An inspector films a 90-second walkthrough or takes a few photos on their phone,
uploads them, and closes the tab. They do not fill in a form. They do not even
tell the system what kind of site it is.

In the background, the agent:

1. **Recognises the work environment** and selects the matching rule catalogue
2. **Detects** safety non-conformities against it
3. **Judges severity from what is actually visible** — not from a lookup table.
   A cable on the floor is a minor housekeeping issue; a cable with exposed live
   wire in a wet area is critical. The agent escalates or lowers the rule's
   default severity and writes down why.
4. **Stops work when it must.** A worker at height with no fall protection does
   not get a 24-hour deadline. It triggers an immediate-stop alert, sent
   separately and first, and escalated to the site director.
5. **Maps each finding to the ISO 45001 clause** it breaches
6. **Assigns an owner and a deadline** from the site's own responsibility matrix
7. **Extracts the evidence frame** at the exact second of the finding, then
   destroys the source footage
8. **Emails each recipient one personalised notice** — not one email per
   finding — stating plainly what they must do and by when, with the evidence
   image inline and a full PDF report attached

A human does exactly one thing: approve, correct, or reject. Nothing is ever
asserted, sent or written into a report without that approval.

### What makes it different

**It knows when it does not know — twice over.** If it cannot recognise the
environment with enough confidence, it audits nothing and asks the auditor
rather than guessing a sector to have something to report. And every individual
finding carries a confidence score: below 0.7 it is flagged "to verify on site"
rather than asserted as a non-conformity. An audit tool that produces confident
false findings destroys its own credibility in a week.

**The auditor can correct it, not just veto it.** Severity, wording, rule and
assignee are all editable, and the original AI values are retained so every
correction is auditable. The auditor can also add a finding the model missed —
because it will miss some.

**It never identifies a person.** Findings refer to role and location only. This
is deliberate: it detects dangerous situations, not individual fault. That single
constraint is what makes the tool deployable in front of a works council instead
of being blocked as workplace surveillance.

**It destroys the footage.** Only the frames documenting an actual finding are
kept. Nothing else survives the audit.

### Scope of this submission

Two rule sets are implemented and field-tested: **offices** and
**construction sites**, 12 rules each, written by a QSE professional with eight
years of practice and ISO 9001 / 14001 / 45001 certification.

Four more sectors — industry, healthcare, logistics, hospitality — are drafted
but deliberately not claimed as working. The catalogues are YAML configuration
files, so adding a sector requires no code change. But a safety rule catalogue
that has not been validated in the field has no business being shipped, and we
would rather present two sectors that work than six that look impressive in a
diagram.

### Why it matters

Workplace injuries are not a data problem waiting for a smarter model. They are a
latency problem: the time between someone seeing a hazard and someone with
authority acting on it. Every hour of that gap is exposure.

This agent compresses that gap from days to minutes — and it does so without
asking anyone to trust an AI's judgement unsupervised.

### Built with

Gemini 3.5 Flash (native multimodal video and image analysis, structured JSON
output) · Cloud Run · Firestore · Cloud Storage · Secret Manager · FastAPI ·
Python 3.11 · ReportLab

---

## Short version (~200 words)

Every site is legally required to run safety inspections. The bottleneck is
never the walkthrough — it is the two to four hours of report writing
afterwards, and the days before a finding reaches someone who can fix it.

HSE Audit Agent removes that gap. An inspector uploads a 90-second walkthrough
and closes the tab — no form, not even a site type to select. In the background
the agent recognises the environment, detects safety non-conformities, judges
each one's real severity from what is actually visible rather than from a lookup
table, maps it to the relevant ISO 45001 clause, assigns an owner and a
risk-based deadline, and — after one human approval — emails each recipient a
personalised action notice with the evidence photo and a PDF report attached. A
worker at height with no fall protection does not get a 24-hour deadline: it
triggers an immediate-stop alert, escalated to the site director.

It knows when it does not know: an unrecognised environment is audited against
nothing, and low-confidence findings are flagged "to verify" rather than
asserted. The auditor can correct any finding, and every correction is
auditable. No individual is ever identified, and the source footage is destroyed
once evidence frames are extracted.

Two rule sets are implemented and tested: offices and construction sites.

---

## Suggested tagline

*Film the walkthrough. The report writes, assigns and sends itself.*

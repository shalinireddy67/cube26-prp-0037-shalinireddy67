# Prep Manager Architecture

This document describes the current architecture and technical implementation of the Prep Manager codebase.

---

## 1. Overview

Prep Manager is a visual inspection and compliance pipeline designed for Amazon FBA product preparation. Its purpose is to verify packaging prep requirements (such as polybagging, suffocation warnings, label placements, barcode masking, expiration dates, and handling marks) from product photographs.

The system follows a strict, unidirectional processing flow:

```
Photo of Prepared Product
         │
         ▼
   Vision Layer (Groq / Gemini / Anthropic / mock)
         │  Observable evidence & categorical strings
         ▼
 Structured Schema (parse_vision_result -> VisionObservationResult)
         │
         ▼
    Rules Layer (build_prep_result + work-order gating)
         │  Deterministic PASS / FAIL / UNCERTAIN
         ▼
    PrepResult (overall_status, checks, requires_manual_review)
         │
         ▼
User Interface (Web Server /docs/landing/ or Streamlit UI) & SQLite Storage
```

1. **Photo Input**: A photograph of a prepared packaging unit is provided.
2. **Vision Layer**: An LLM-based vision provider analyzes the image and extracts visual observations without deciding pass/fail compliance.
3. **Structured Schema**: The raw vision output is parsed and strictly validated against allowable categorical observation sets.
4. **Deterministic Rules Layer**: Business and marketplace rules evaluate the parsed observations against work-order applicability flags to determine compliance verdicts.
5. **PrepResult Output**: A structured object containing individual check verdicts, explanations, observable evidence, overall status, and manual review indicators.
6. **User-Facing Interfaces & Storage**: Results are presented via the web interface or Streamlit app, with optional persistence to an organization-scoped SQLite database.

---

## 2. Vision Layer

The vision layer lives in [`src/vision_agent.py`](file:///c:/Users/reddy/cube26-prp-0037-shalinireddy67/src/vision_agent.py) and is invoked through `analyze_unit_photo(image_path)`.

### Provider Configuration
The active vision provider is configured dynamically through the `VISION_PROVIDER` environment variable (defaults to `gemini` if unset; currently configured to `groq` in `.env`).

The codebase implements four distinct provider paths:
* **Groq** (`_call_groq`): Calls Groq's Chat Completions API with vision-capable models (e.g., `qwen/qwen3.6-27b`, configurable via `GROQ_VISION_MODEL`). Requires `GROQ_API_KEY`.
* **Gemini** (`_call_gemini`): Calls Google's GenAI API (defaults to `gemini-2.5-flash`, configurable via `GEMINI_VISION_MODEL`). Requires `GEMINI_API_KEY`.
* **Anthropic** (`_call_anthropic`): Calls Anthropic's Messages API (defaults to `claude-haiku-4-5-20251001`, configurable via `VISION_MODEL`). Requires `ANTHROPIC_API_KEY`.
* **Mock** (`_call_mock`): Returns hard-coded synthetic JSON observations for offline local testing and development without requiring network calls or API credentials.

> **Note**: While four provider implementations exist in code, only the provider specified by `VISION_PROVIDER` is active at runtime.

### Separation of Observation and Decision
The vision prompt (`VISION_PROMPT`) explicitly instructs the vision model **not** to make compliance or pass/fail determinations. Instead, the model is restricted to reporting:
* An **observation** matching a predefined categorical set per check.
* A concise **evidence** string describing exactly what is physically visible in the image.
* When visual evidence is incomplete or obscured, the model is required to return `uncertain` rather than speculating.

If the vision model fails to return valid JSON, omits required keys, or returns invalid observation categories, `analyze_unit_photo` fails open by returning `{"status": "PENDING", "reason": "..."}` rather than crashing the pipeline.

---

## 3. Structured Schema

The schema layer is defined in [`src/schemas.py`](file:///c:/Users/reddy/cube26-prp-0037-shalinireddy67/src/schemas.py). It enforces strict typing and validation across the pipeline:

* **`VisionCheckObservation`**: Encapsulates a single check's `observation` and `evidence` strings.
* **`VisionObservationResult`**: Represents the complete vision response for a `unit_id` and `image_path`, including a status (`OK` or `PENDING`) and a dictionary of checks.
* **`parse_vision_result(raw, unit_id, image_path)`**: Validates and transforms raw dictionaries into typed `VisionObservationResult` instances.
* **`ComplianceCheck`**: Represents an evaluated compliance check, including `name`, `verdict` (`PASS`, `FAIL`, `UNCERTAIN`, `PENDING`), `explanation`, and `evidence`.
* **`PrepResult`**: The final pipeline output containing `unit_id`, `checks` (list of `ComplianceCheck`), `overall_status`, `evidence`, and `requires_manual_review` (boolean flag).

---

## 4. Rules Layer

Compliance evaluation is implemented in [`src/rules.py`](file:///c:/Users/reddy/cube26-prp-0037-shalinireddy67/src/rules.py). Compliance verdicts are deterministic and gated by work-order requirements (`wo_*`).

### Check Categorization

The system categorizes the six checks into two groups:

#### 1. Decidable Checks (`DECIDABLE_CHECKS`)
* `polybag_present_sealed`
* `suffocation_warning`
* `expiry_date`
* `handling_marks`

For these four checks:
* If the check is **not required** by the work order (e.g., `wo_polybag=False`), it immediately evaluates to `PASS` with the explanation `"Not required per work order."`.
* If **required**, the observation determines the verdict:
  * Positive observation (e.g., `yes`, `legible`, `all_present`) $\rightarrow$ `PASS`.
  * Defective observation (e.g., `not_sealed`, `missing`, `obscured_by_fold`, `illegible_after_wrap`, `some_missing`) $\rightarrow$ `FAIL`.
  * Incomplete visual evidence (`uncertain`) $\rightarrow$ `UNCERTAIN`.

`overall_status` is computed exclusively from these decidable checks using strict priority: `FAIL` > `UNCERTAIN` > `PASS`.

#### 2. Advisory Checks (`ADVISORY_CHECKS`)
* `fnsku_label_placement`
* `original_barcode_covered`

**Important Design Decision**:
The vision layer actively observes label placement (`flat`, `on_seam`, `on_curve`, `on_edge`, `missing`, `uncertain`) and barcode masking (`yes`, `no`, `uncertain`). However, because the project specification does not define an authoritative automated rule for these two checks, their compliance verdict remains **`UNCERTAIN` by design**.

To avoid forcing every unit's `overall_status` to `UNCERTAIN`, these checks do not affect `overall_status`. Instead, whenever an advisory check produces an `UNCERTAIN` verdict, the system sets `requires_manual_review = True` on the final `PrepResult`.

---

## 5. Suffocation Warning Rule

The suffocation warning compliance rule is documented in [`src/rules.py`](file:///c:/Users/reddy/cube26-prp-0037-shalinireddy67/src/rules.py) and references the published Amazon Seller Central requirement:

* **Source**: Amazon Seller Central Packaging and Prep Requirements
* **URL**: [https://sellercentral.amazon.com/gp/help/external/200141500](https://sellercentral.amazon.com/gp/help/external/200141500)
* **Rule**: Amazon mandates a suffocation warning on polybags with an opening of 5 inches or larger (measured flat).
* **Application in Prep Manager**: The vision model cannot accurately measure bag opening dimensions in inches from a 2D photograph. Therefore, the applicability of this rule is determined by the work-order flag `wo_suffocation_warning`. If the work order marks the warning as required, the rule enforces that the warning must be present and legible (`PASS`); if missing or obscured by a fold, it evaluates to `FAIL`.

---

## 6. Backend and Web Flow

The repository supports two user interfaces, both interacting with the underlying pipeline without modifying core logic:

### Web Server (`server.py`)
A lightweight, multi-threaded HTTP server implemented using Python's standard `http.server.ThreadingHTTPServer`. It serves:
* **Static Assets**: Serves the repository's static files, including the marketing landing page ([`docs/landing/index.html`](file:///c:/Users/reddy/cube26-prp-0037-shalinireddy67/docs/landing/index.html)) and the interactive package compliance checker ([`docs/landing/checker.html`](file:///c:/Users/reddy/cube26-prp-0037-shalinireddy67/docs/landing/checker.html)).
* **Health Endpoint**: `GET /api/health` returning service availability.
* **Checker API**: `POST /api/check`, which receives `{unit_id, work_order, image_path, image_base64}`, processes the unit photo through `src.app.process_unit()`, and returns the serialized `PrepResult` JSON.

### Web Interface Pages
* **Landing Page (`docs/landing/index.html`)**: Product introduction and navigation hub linking to the compliance checker and feature overviews.
* **Checker Page (`docs/landing/checker.html`)**: Interactive testing interface for running packaging compliance checks against sample images or uploaded photos.

### Streamlit Application (`streamlit_app.py`)
An alternative UI built with Streamlit providing:
* Work order configuration sidebar with explicit `org_id` input.
* Image upload preview and analysis trigger.
* Detailed compliance card views with color-coded badges.
* Historical records table displaying past results saved for the organization.

### Authentication Status
There is currently no implemented user authentication, session tracking, or seller login layer in the active codebase. Multi-tenancy and data scoping are handled via an explicit `org_id` parameter passed to storage routines and operator interfaces.

---

## 7. Storage and Multi-Tenancy

Data persistence is implemented in [`src/storage.py`](file:///c:/Users/reddy/cube26-prp-0037-shalinireddy67/src/storage.py) using an embedded SQLite database (`data/prep_manager.db`) and local filesystem storage (`data/images/`).

* **Tenant Isolation**: All database tables (`results`, `overrides`) include an `org_id` column indexed for fast lookups (`idx_results_org_id`, `idx_overrides_org_id`).
* **Parameterized Queries**: All SQL operations use parameter substitution (e.g., `WHERE id = ? AND org_id = ?`) to avoid query injection and prevent cross-organization data access.
* **Path Sanitization**: The helper `_sanitize_id()` cleans identifiers by rejecting directory traversal sequences (`..`, `/`, `\`) and empty strings.
* **Image Organization**: Uploaded images are stored in organization-specific directories (`data/images/{org_id}/`).
* **Operator Overrides**: The `overrides` table supports audit tracking when an operator modifies an automated verdict, storing `original_verdict`, `new_verdict`, `reason`, `operator_id`, and a UTC ISO timestamp.

---

## 8. Evaluation Setup and Metrics

The evaluation framework lives in [`eval/run_eval.py`](file:///c:/Users/reddy/cube26-prp-0037-shalinireddy67/eval/run_eval.py) and scores the vision agent against hand-labeled ground truth in [`data/eval_labels.csv`](file:///c:/Users/reddy/cube26-prp-0037-shalinireddy67/data/eval_labels.csv).

### Current Development Evaluation
The current evaluation dataset contains 5 real product packaging images staged in `fixtures/prep/` (`a.jpg` through `e.jpg`).

* **Total Images Evaluated**: 5
* **Total Labeled Checks Scored**: 30
* **Model Failures (`PENDING`)**: 0
* **Total Matches**: 22 / 30
* **Overall Match Rate**: 73.3%

#### Per-Check Results
| Check Name | Labeled | Matches | Match Rate | Cautious Miss | Overconfident Miss | Wrong Observation |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `polybag_present_sealed` | 5 | 4 | 80.0% | 1 | 0 | 0 |
| `suffocation_warning` | 5 | 2 | 40.0% | 3 | 0 | 0 |
| `fnsku_label_placement` | 5 | 3 | 60.0% | 0 | 0 | 2 |
| `original_barcode_covered` | 5 | 3 | 60.0% | 1 | 1 | 0 |
| `expiry_date` | 5 | 5 | 100.0% | 0 | 0 | 0 |
| `handling_marks` | 5 | 5 | 100.0% | 0 | 0 | 0 |

> **Evaluation Scope**: This evaluation represents a small development test set scored against hand-written labels created by the project author. It serves as an internal benchmark for tracking changes, not an independent statistical validation or representative benchmark.

---

## 9. Known Limitations

* **Evaluation Sample Size**: The current evaluation is based on 5 staged test images. Percentages are directional indicators rather than statistically significant benchmarks.
* **Advisory Checks**: Automated compliance rules for `fnsku_label_placement` and `original_barcode_covered` are not defined in the project specification and remain flagged for manual review (`UNCERTAIN`).
* **2D Visual Perspective**: A single photograph captures only visible exterior faces. Physical attributes on unphotographed sides or internal bag contents cannot be verified and naturally result in `uncertain` observations.
* **Physical Measurement**: The vision agent cannot measure physical bag opening dimensions to verify the Amazon 5-inch suffocation warning threshold directly; it relies on work-order applicability flags.

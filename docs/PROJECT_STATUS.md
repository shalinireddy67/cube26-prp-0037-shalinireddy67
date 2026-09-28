# Project Status & Repository Audit: Prep Manager

## Current Branch
- **Current active branch:** `shalinireddy67`
- **Branch safety check:** PASSED. The repository is checked out on participant branch `shalinireddy67`, NOT `main`.
- **Git status:** Up to date with `origin/shalinireddy67` (remote `https://github.com/shalinireddy67/cube26-prp-0037-shalinireddy67.git`).
- **Untracked files initially present:** `fixtures/prep/test.jpg`, `src/rules.py`, `src/schemas.py`.

---

## RULES.md Summary
`RULES.md` defines two distinct sets of rules for the buildathon:

1. **Repository Rules (R1–R8):**
   - Round 2 is an individual build that must be carried out exclusively in the participant's own GitHub fork.
   - All commits forming the submission must occur within the authorized build phase (September 25, 2026, 9:00 AM IST to October 1, 2026, 6:00 PM IST; submissions open September 27). No changes permitted after the deadline.
   - Strict ban on secrets (API keys, tokens, passwords, `.env` files).
   - No tampering with the organizer repository or others' submissions.
   - Once submitted via the official form, the submission is final with no reopening or resubmission.

2. **Engineering Rules (Non-Negotiable):**
   - **Tenancy isolation before any feature:** Row-level security must be enabled and enforced per organization (using sample tenants `org_demo_alpha` and `org_demo_bravo`). A foreign org must see 0 rows and cannot access image assets via guessable keys.
   - **Batch model calls:** Exactly one model call per unit carrying all compliance checks (never one call per individual check) to maintain operating margin.
   - **Fail open:** Model errors or timeouts must still persist the capture and produce a record flagged as `pending`, ensuring warehouse lines are never blocked.
   - **Uncertain is a valid verdict:** `UNCERTAIN` and `PENDING_REVIEW` are first-class verdicts and not low-confidence passes.
   - **Look authoritative rules up:** Retrieve channel requirements directly from official published channel specifications; do not infer from sample CSVs or recall from memory.

3. **Honesty Rules (Assessed):**
   - Truth in advertising (e.g., distinguish between content hashing and immutable/anchored ledgers).
   - Operator overrides must be preserved as structured data (original verdict, new verdict, reason).
   - Accuracy must be reported empirically per check with separate false-positive and false-negative metrics; contradictions in source materials must be logged as findings.

---

## ARCHITECTURE.md Summary
`ARCHITECTURE.md` exists in the repository root but is currently empty (0 bytes, 1 blank line). It was cleared in commit `bc7c9e2 ("Init project structure")`.

---

## Existing src/ Files
The `src/` directory contains 2 untracked Python source files:
- **`src/rules.py` (327 bytes):** Defines rule versioning (`RULE_VERSION = "0.1"`) and a set of standard verdict strings `VERDICTS = {"PASS", "FAIL", "UNCERTAIN", "PENDING"}`. Its module docstring reminds developers that compliance rules must originate from authoritative published documentation, `prep_sample.csv` must not be treated as ground truth, and `UNCERTAIN` must remain a valid outcome.
- **`src/schemas.py` (882 bytes):** Defines Python dataclass models for compliance data: `ComplianceCheck` (name, verdict, explanation, and evidence list) and `PrepResult` (unit_id, checks list, overall_status, and evidence dict). Both models validate in `__post_init__` that verdicts and statuses belong strictly to `VALID_VERDICTS = {"PASS", "FAIL", "UNCERTAIN", "PENDING"}`, raising a `ValueError` otherwise.

---

## Existing tests/ Files
Not found (the `tests/` directory exists in the repository root, but contains no files or test cases).

---

## data/prep_sample.csv Structure
- **Dataset Overview:** Synthetic reference dataset containing 62 records (64 lines: 1 header row, 62 data rows, 1 trailing empty newline). Documented in `data/README.md` as explicitly dummy data that must not be used for compliance ground truth or model training.
- **Total Columns:** 22 columns.
- **Comparison to Expected Column Set:**
  - *Expected fields:* `record_id`, `unit_id`, `org_id`, `photo_refs`, `operator_id`, `captured_at`, `work_order_id`, `fba_shipment_id`, `sku`, `asin`, `fnsku`, `prep_price_usd`, `wo_*` fields, `polybag_present_sealed`, `suffocation_warning`, `fnsku_label_placement`, `original_barcode_covered`, `expiry_date`, `handling_marks`.
  - *Actual columns present:*
    1. `record_id`
    2. `unit_id`
    3. `org_id`
    4. `work_order_id`
    5. `fba_shipment_id`
    6. `sku`
    7. `asin`
    8. `fnsku`
    9. `prep_price_usd`
    10. `wo_polybag`
    11. `wo_suffocation_warning`
    12. `wo_expiry_date`
    13. `wo_handling_marks`
    14. `polybag_present_sealed`
    15. `suffocation_warning`
    16. `fnsku_label_placement`
    17. `original_barcode_covered`
    18. `expiry_date`
    19. `handling_marks`
    20. `photo_refs`
    21. `operator_id`
    22. `captured_at`
  - *Differences & Deviations Flagged:*
    - **Column Ordering Difference:** All 22 expected fields are present, but their physical order in the CSV differs from the expected enumeration. In `data/prep_sample.csv`, `photo_refs`, `operator_id`, and `captured_at` appear as the final 3 columns (columns 20, 21, and 22), whereas the expected list placed them immediately after `org_id` (positions 4, 5, and 6).
    - **Specific `wo_*` Columns:** The `wo_*` wildcard consists of exactly four columns: `wo_polybag`, `wo_suffocation_warning`, `wo_expiry_date`, and `wo_handling_marks`.
    - **Row Count Note:** `data/README.md` specifies "62 rows", which matches the 62 data records (lines 2–63); line 64 is a trailing blank line.

---

## fixtures/prep/ Contents
The `fixtures/prep/` directory contains exactly 1 file:
- **`test.jpg` (28,655 bytes):** A sample JPEG image (currently untracked by git).
- *Note:* While `data/prep_sample.csv` references placeholder fixture paths like `fixtures/prep/UNIT-0002_front.jpg`, `fixtures/prep/UNIT-0002_back.jpg`, and `fixtures/prep/UNIT-0002_label.jpg`, none of those referenced image files exist in `fixtures/prep/`.

---

## Risks Found
1. **Empty root `.gitignore`:** The root `.gitignore` file is completely empty (0 bytes). In commit `bc7c9e2`, the initial gitignore rules (ignoring `.env`, `.env.*`, `venv/`, `node_modules/`, `__pycache__/`, `*.pyc`) were deleted. Consequently, any newly created `.env` file containing secret keys or environment variables will be untracked and vulnerable to accidental staging and commit via `git add .`, which would violate rule R6.
2. **Virtual Environment tracking risk:** While `venv/` contains an auto-generated internal `.gitignore` (`*`), root `.gitignore` does not exclude `venv/` or `.venv/`. Any files created outside that directory or tools bypassing nested ignores could unintentionally track environment dependencies.
3. **Empty configuration and dependency files:** `requirements.txt`, `.env.example`, `README.md`, and `ARCHITECTURE.md` are all 0 bytes (cleared in commit `bc7c9e2`). There is currently no locked dependency manifest, setup documentation, or architecture blueprint.
4. **No test suite:** `tests/` is completely empty. Engineering Rule 1 requires tenancy isolation testing prior to feature development, but no test framework or test fixtures are currently implemented.
5. **Missing image assets for sample data:** The 62 sample records in `prep_sample.csv` reference multi-perspective image paths (front, back, label) that do not exist in `fixtures/prep/` (only `test.jpg` exists). Testing the full pipeline against sample records will require providing or generating valid images.
6. **Hardcoded Secrets Verification:** A comprehensive regex search across all files and git history (`api_key`, `secret`, `token`, `password`, `AIza`, `sk-`, `ghp_`, etc.) found **no hard-coded API keys, tokens, or credentials** in the repository. Mentions of secrets occur exclusively in guidelines and rules.

---

## Open Questions
1. **Project Directory Convention:** Should Phase 2 code and documentation be developed directly in root `src/` and root `docs/` (as illustrated in `GITHUB-GUIDE.md`), or under `submissions/<username>/` (as outlined in `submissions/_TEMPLATE/README.md` and `.github/scripts/submission-guard.sh`)?
2. **Dependency Specification:** Which framework, vision model SDK (e.g., `google-genai` / Gemini API), image processing libraries (e.g., Pillow), and testing tools (e.g., `pytest`) should be populated in `requirements.txt`?
3. **Gitignore Restoration:** Should the standard `.gitignore` patterns (blocking `.env`, `venv/`, `__pycache__`) and `.env.example` template variables be restored immediately before Phase 2 code and configuration are introduced?
4. **Evaluation Fixture Acquisition:** Will official multi-angle evaluation fixtures (front, back, label) for the mandatory 50-unit evaluation set be provided by organizers, or is the participant expected to capture and label their own fixture set?

---

## Gitignore Fix & Submission Structure (Task 1B)

### 1. Updated `.gitignore` Content
The root `.gitignore` file has been restored to prevent accidental commits of secrets and environment bloat. It now contains:
```gitignore
.env
.env.*
!.env.example
venv/
.venv/
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
.DS_Store
```

### 2. Restored `.env.example` Content
`.env.example` has been populated with clear usage instructions and commented placeholder variables (with no real secrets):
```env
# ==============================================================================
# Environment Configuration Template for Prep Manager
# ==============================================================================
# INSTRUCTIONS:
# Copy this file to `.env` in the project root:
#   cp .env.example .env   (or copy in your editor)
# Fill in your actual credentials and local configurations in `.env`.
# NEVER commit the `.env` file to version control (it is excluded by .gitignore).
# ==============================================================================

# LLM / Vision Model API Keys (populate the key for your chosen provider)
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
OPENAI_API_KEY=

# Application / Tenancy Settings (optional)
# TENANT_ORG_ID=org_demo_alpha
```

### 3. Submission Structure Analysis
A plain evaluation of whether the project requires files under `submissions/<username>/` versus root-level `src/` and `docs/`:

#### A. What `.github/scripts/submission-guard.sh` Specifies
Lines 1–4:
```bash
#!/usr/bin/env bash
# Fails a PR unless (a) the branch is named after the PR author and
# (b) every changed file is inside submissions/<author>/.
# Inputs (env): AUTHOR, HEAD_REF, BASE_SHA, HEAD_SHA, ADMIN
```
Lines 17–20:
```bash
if [ "$(lower "$HEAD_REF")" != "$(lower "$AUTHOR")" ]; then
  echo "::error::Branch name '$HEAD_REF' does not match your GitHub username '$AUTHOR'."
  echo "Rename it:  git branch -m $AUTHOR && git push -u origin $AUTHOR   (then open a new PR from it)"
```
Lines 27–42:
```bash
prefix="submissions/$(lower "$AUTHOR")/"
outside=""
while IFS= read -r f; do
  [ -z "$f" ] && continue
  case "$(lower "$f")" in
    "$prefix"*) ;;
    *) outside="$outside$f"$'\n' ;;
  esac
done <<< "$CHANGED_FILES"

if [ -n "$outside" ]; then
  echo "::error::This PR changes files outside submissions/$AUTHOR/. Only your own folder may be changed:"
  printf '%s' "$outside" | sed 's/^/  /'
  echo "Undo them with:  git checkout origin/main -- <file>   then commit and push."
  fail=1
fi
```

#### B. What `submissions/_TEMPLATE/README.md` Specifies
Lines 1–3:
```markdown
# <your-github-username> · Prep Manager

Copy this file to `submissions/<your-github-username>/README.md` and keep it as your index.
```
Lines 7–19:
```text
submissions/<your-github-username>/
├── README.md            ← this file: who you are, links to everything below
├── 01-customer-letter.md
├── 02-prfaq.md          ← include the questions you'd rather not answer
├── 03-one-pager.md      ← metrics table + at least one kill condition
├── CLAUDE.md            ← durable constraints, hard rules, forbidden language
├── build-brief.md
├── build-log.md         ← keep it current; organisers read it
├── eval-report.md       ← method, two-labeller agreement, per-check FP / FN, failure modes
├── contract/            ← your evidence-record shape, as agreed with the other pods
└── agent/               ← your code (headless first)
```

#### C. What `GITHUB-GUIDE.md` and `RULES.md` Specify
`GITHUB-GUIDE.md` (updated in commit `512753e` to supersede the old monorepo PR workflow) explicitly states:
- Lines 79–81:
  > "You do **not** need to create a participant branch or participant folder in the organiser repository. Build your solution inside your own fork."
- Lines 113–137:
  > "You are free to choose your own project structure.  
  > For example:  
  > ```text
  > cube-02-prep-manager/
  > ├── data/
  > ├── src/
  > ├── tests/
  > ├── README.md
  > ├── RULES.md
  > ├── GITHUB-GUIDE.md
  > ├── ARCHITECTURE.md
  > └── ...
  > ```  
  > This is only an example. Your final repository should be clear and easy to run.  
  > You do not need to create:  
  > `submissions/<your-github-username>/`  
  > in the organiser repository."
- `RULES.md` (Rules R2, R3):
  > "R2: Each participant must work in their **own GitHub fork** of this repository."  
  > "R3: Your fork is your Round 2 development and final submission repository."

#### Plain Conclusion
- **Root-level `src/` and `docs/` is completely acceptable** for your build and final submission repository. Per `GITHUB-GUIDE.md` and `RULES.md`, participants build in their own GitHub fork and submit via the official submission form, without needing a `submissions/<username>/` folder.
- **The only scenario where `submissions/<username>/` is enforced** is if an author opens an actual GitHub Pull Request targeting the upstream organizer repo (`main` branch), which triggers `.github/workflows/submission-guard.yml` and `.github/scripts/submission-guard.sh`.

### 4. Verification that `.env` is Ignored
- `git check-ignore .env` exits with code 0 and outputs `.env`.
- `git check-ignore .env.local` exits with code 0 and outputs `.env.local`.
- `git check-ignore venv/` exits with code 0 and outputs `venv/`.
- `git check-ignore .env.example` exits with code 1 (unignored, correctly tracked as a template).
- `git status` verifies no untracked `.env` file is staged or exposed.


# Prep Manager

Prep Manager is an automated visual packaging compliance tool for Amazon FBA preparation. It inspects product photographs using a vision language model to extract physical evidence (such as polybag presence, suffocation warnings, barcode masking, label placement, expiration dates, and handling marks), and then applies deterministic, work-order-gated rules to determine whether a unit passes, fails, or requires manual review.

For complete technical documentation and pipeline diagrams, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Local Setup

### 1. Prerequisites
* Python 3.10+ (tested on Python 3.11/3.12)
* Git

### 2. Virtual Environment & Dependencies

Create and activate a virtual environment, then install dependencies:

```bash
# Create virtual environment
python -m venv .venv

# Activate on Windows (PowerShell)
.venv\Scripts\Activate.ps1
# Or on Linux / macOS:
# source .venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 3. Environment Configuration

Copy the example environment template and configure your API credentials:

```bash
cp .env.example .env
```

Open `.env` and specify your vision provider and API key:

```env
# Choose provider: groq, gemini, anthropic, or mock
VISION_PROVIDER=groq

# Provider API keys (populate the key matching your chosen provider)
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Optional model overrides
GROQ_VISION_MODEL=qwen/qwen3.8-27b
GEMINI_VISION_MODEL=gemini-2.5-flash
```

For offline development without API keys, set `VISION_PROVIDER=mock`.

---

## Running the Application

Prep Manager provides two user interfaces:

### Option A: Web Server & Checker (Recommended)

Start the built-in HTTP server:

```bash
python server.py
```

Once running, navigate to:
* **Landing Page**: [http://localhost:8000/docs/landing/index.html](http://localhost:8000/docs/landing/index.html)
* **Compliance Checker**: [http://localhost:8000/docs/landing/checker.html](http://localhost:8000/docs/landing/checker.html)
* **Health API**: [http://localhost:8000/api/health](http://localhost:8000/api/health)

The web checker allows you to select sample images from `fixtures/prep/` or upload a package photo, configure work-order toggles, and view per-check compliance breakdowns and evidence in real time.

### Option B: Streamlit Dashboard

Alternatively, launch the Streamlit interface:

```bash
streamlit run streamlit_app.py
```

The Streamlit app provides interactive work-order configuration, image upload previews, compliance status badges, and an organization-scoped history log backed by local SQLite storage.

---

## Evaluation

An evaluation runner is included to benchmark the vision model's observations against ground-truth labels:

```bash
python eval/run_eval.py
```

The runner evaluates the test images listed in `data/eval_labels.csv` against `fixtures/prep/` and writes a detailed markdown report to [docs/eval-report.md](docs/eval-report.md).

### Current Development Benchmark
On the current 5-image development dataset (`fixtures/prep/a.jpg` through `e.jpg`):
* **Images Evaluated**: 5
* **Total Labeled Checks Scored**: 30
* **Model Failures (`PENDING`)**: 0
* **Matches**: 22 / 30
* **Overall Match Rate**: 73.3%

> **Status Notice**: The 73.3% match rate reflects a small, 5-image development set with hand-labeled ground truth used for local testing. It does not represent an independent validation benchmark.

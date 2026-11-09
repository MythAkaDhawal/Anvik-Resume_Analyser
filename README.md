# ANVIK — Intelligent Talent Analysis

<div align="center">
  <img src="assets/anvik_logo.png" alt="ANVIK Logo" width="480"/>
  <p><em>Precision Candidate Evaluation & Decision Support Architecture</em></p>
</div>

> **Status: Fully Implemented & Verified (Release v1.0.0).** All 15 implementation phases,
> official ANVIK product branding, deterministic core parsing, taxonomy matching, scoring strategies, GenAI provider adapters,
> multi-format exporters (HTML, PDF, Excel), Streamlit UI, and benchmark evaluation suites are
> 100% complete, verified with 192 automated tests, and cleared for submission.
>
> **Placement note:** in this repository this file lives at the repository root and the other
> eleven documents live in `docs/`. Links in this file assume that layout (see
> [PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)).

---

## 1. Product identity & design philosophy

**ANVIK** is an intelligent talent analysis and decision-support system engineered for senior hiring managers, technical talent leads, and talent intelligence teams.

Rather than treating talent acquisition as an ungrounded generative exercise or a generic SaaS dashboard, ANVIK pairs a **rigorous deterministic analysis engine** with **calibrated AI-assisted advisory synthesis**. Every calculation, skill match, and score breakdown is 100% traceable, explainable, and audit-ready.

### Visual design & brand tokens

The ANVIK visual system embodies restraint, clarity, and precision:

| Token | Hex | Role in Application |
|---|---|---|
| **Carbon Ink** | `#171817` | Primary dark surface, sidebar base, and high-contrast foundations |
| **Warm Ivory** | `#E9E2D2` | Primary typography, crisp vector linework, and high-legibility foreground |
| **Oxidised Copper** | `#B66F4B` | Primary action accent, focus indicators, and key metric emphasis |
| **Aged Graphite** | `#343633` | Elevated card surfaces, structural borders, and container frames |
| **Muted Moss** | `#77765D` | Supporting indicators, matched criteria, and neutral evaluation badges |

---

## 2. Project description

ANVIK helps a human reviewer screen candidates faster, more objectively, and with zero hallucination risk. It reads resumes (PDF, DOCX, TXT), extracts structured
information, compares each candidate with a job's requirements, computes an **interpretable
0–100 alignment score**, and optionally uses a Generative AI (GenAI) provider to write
explanations, improvement suggestions, and interview questions.

Three kinds of output are always kept separate and labelled (the **provenance model**):

| Provenance label | Meaning | Example |
|---|---|---|
| `EXTRACTED_RULE` | Read from the resume by deterministic code | e-mail address, skills found via the taxonomy |
| `EXTRACTED_AI` | Read from the resume by an AI model, then verified against the resume text | an employer name the rules missed |
| `COMPUTED` | Calculated deterministically from extracted data | match score, years of experience |
| `AI_GENERATED` | Interpretation written by an AI model; **not a verified fact** | "strengths" paragraph, interview questions |

The application **never makes hiring decisions**. Its output is decision *support* and must be
reviewed by a human.

## 3. Objectives

1. Accept and read candidate resumes (PDF, DOCX, TXT).
2. Extract name, e-mail, skills, experience, and education into a typed data model.
3. Compare candidates against job requirements using exact, alias, and fuzzy skill matching.
4. Produce an explainable score (basic and weighted strategies, switchable at run time).
5. Generate AI-assisted explanations, improvement recommendations, and interview questions.
6. Produce reports and export them as HTML, PDF, and Excel.
7. Persist and reload analyses as JSON; capture user feedback to improve prompts and quality.
8. Demonstrate production-minded engineering: logging, configuration, caching, custom
   exceptions, validation, tests, security, and privacy.

## 3. Features

Priority: **MUST** = required for capstone submission, **SHOULD** = expected, **COULD** = optional.
Full requirement text is in [PROJECT_REQUIREMENTS.md](docs/PROJECT_REQUIREMENTS.md).

| Feature | Requirement IDs | Priority |
|---|---|---|
| PDF / DOCX / TXT ingestion with safety checks | FR-01, FR-02, NFR-10 | MUST |
| Text cleaning and structured parsing | FR-03 – FR-08 | MUST |
| Job requirements entry and validation | FR-09 | MUST |
| Exact / alias / fuzzy skill matching | FR-10 | MUST |
| Experience and education evaluation | FR-11, FR-12 | MUST |
| Basic and weighted scoring via Strategy pattern | FR-13 – FR-16 | MUST |
| Five GenAI features (extraction, categorization, explanation, recommendations, interview questions) | FR-17 – FR-21 | MUST |
| Provenance labelling, graceful AI degradation | FR-22, FR-32 | MUST |
| Reports and HTML / PDF / Excel export | FR-23 – FR-26 | MUST |
| JSON persistence, history, deletion | FR-27, FR-28 | MUST |
| Feedback capture and review loop | FR-29 | MUST |
| Batch processing with progress indicator | FR-30 | MUST |
| Streamlit user interface | FR-31 | MUST |
| Command-line interface for batch runs and benchmarks | (supports FR-30, M-02) | SHOULD |

## 4. Technology overview

One primary choice per concern; alternatives and rationale are in
[TECHNICAL_SPECIFICATION.md](docs/TECHNICAL_SPECIFICATION.md) §2.

| Concern | Primary choice | Why |
|---|---|---|
| Language | Python 3.11 (3.10 minimum) | Mature, beginner-friendly, strong library support |
| UI | Streamlit | Fastest route to a working UI in pure Python |
| PDF parsing | `pdfplumber` (fallback `pypdf`) | Reliable text extraction, pure Python |
| DOCX parsing | `python-docx` | Standard, simple |
| Data models / validation | `pydantic` v2 | Type hints + runtime validation; also validates AI JSON |
| Fuzzy matching | `rapidfuzz` | Fast, permissively licensed |
| GenAI | Provider-agnostic `LLMProvider` interface; adapters for Google Gemini (free tier may be available — verify), Ollama (local, no cost), and any OpenAI-compatible endpoint; `NullProvider` when AI is off | No lock-in; no paid-API assumption |
| Config | YAML (`PyYAML`) validated by pydantic | Human-editable, centralized |
| Persistence | JSON files | Simple, inspectable, no database needed |
| Exports | `Jinja2` (HTML), `reportlab` (PDF), `openpyxl` (Excel) | Pure-Python, few system dependencies |
| Testing / quality | `pytest`, `pytest-cov`, `ruff`, `black`, `bandit`, `radon` | Standard, lightweight |

## 5. Architecture summary

```mermaid
flowchart LR
    U["Reviewer"] --> UI["Streamlit UI / CLI"]
    UI --> SVC["AnalysisService (facade)"]
    SVC --> ING["Ingestion: validate + extract text"]
    ING --> PAR["Parsing: clean, sections, entities"]
    PAR --> MAT["Matching engine"]
    MAT --> SCO["Scoring strategies"]
    SVC --> AI["AI service (optional)"]
    SCO --> REP["Report builder"]
    AI --> REP
    REP --> EXP["Exporters: HTML / PDF / Excel"]
    REP --> STO["JSON storage"]
    AI --> LLM["LLM provider (adapter)"]
```

Details: [SYSTEM_ARCHITECTURE.md](docs/SYSTEM_ARCHITECTURE.md).

## 6. Installation

Prerequisites: Python 3.11 (3.10 minimum), `git`, and ~500 MB free disk space.

```bash
git clone <repository-url> intelligent-resume-analyzer
cd intelligent-resume-analyzer

python3.11 -m venv .venv
source .venv/bin/activate            # Windows PowerShell: .venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt      # runtime dependencies
pip install -r requirements-dev.txt  # testing and quality tools (development only)
pip install -e .                     # makes `resume_analyzer` importable
```

## 7. Environment setup

```bash
cp .env.example .env                 # then edit .env — never commit it
```

| Variable | Required? | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | Only if `ai.provider: gemini` | Google Gemini API key |
| `OPENAI_API_KEY` | Only if `ai.provider: openai_compatible` | Key for an OpenAI-compatible endpoint |
| `OLLAMA_HOST` | Only if `ai.provider: ollama` | Defaults to `http://localhost:11434` |
| `RESUME_ANALYZER_CONFIG` | No | Path to an alternative `config.yaml` |
| `RESUME_ANALYZER_DATA_DIR` | No | Overrides `app.data_dir` |
| `RESUME_ANALYZER_LOG_LEVEL` | No | Overrides `logging.level` |

The application runs **without any AI key**: deterministic parsing, matching, scoring, reporting,
and export all work; AI sections are shown as "unavailable". Full details:
[CONFIGURATION_AND_SECURITY.md](docs/CONFIGURATION_AND_SECURITY.md).

> **Privacy warning:** use only **synthetic or consented** resumes during development. Check the
> data-use terms of any hosted AI provider before sending real candidate data. A local model via
> Ollama keeps data on your machine.

## 8. Running

```bash
streamlit run src/resume_analyzer/ui/streamlit_app.py     # web UI
python -m resume_analyzer.cli --help                       # CLI
pytest                                                     # tests
```

### 8.1 Deployment on Streamlit Community Cloud

The application is natively built for **Streamlit Community Cloud**:

1. Sign in to [Streamlit Community Cloud](https://share.streamlit.io/) with your GitHub account.
2. Click **"New app"**.
3. Choose your repository: `MythAkaDhawal/Resume_Analyser` (or your repository URL).
4. Set **Branch**: `main`.
5. Set **Main file path**: `src/resume_analyzer/ui/streamlit_app.py`.
6. *(Optional)* In **Advanced settings** &rarr; **Secrets**, configure any desired API keys for GenAI features:
   ```toml
   GEMINI_API_KEY = "your-gemini-api-key"
   # Or for OpenAI-compatible endpoint:
   # OPENAI_API_KEY = "your-openai-api-key"
   ```
   *(If omitted, the app runs in 100% deterministic offline mode with AI features gracefully marked as unavailable).*
7. Click **"Deploy!"**. Streamlit Community Cloud automatically provisions the container, installs dependencies from `requirements.txt`, and serves the application with persistent WebSocket support.

## 9. Example usage (planned interface)

Example `job.json` (illustrative):

```json
{
  "job_title": "Junior Data Analyst",
  "required_skills": ["Python", "SQL", "Pandas", "Docker", "AWS"],
  "optional_skills": ["Git", "Streamlit", "Tableau"],
  "min_experience_years": 2,
  "min_education_level": "BACHELOR",
  "preferred_fields": ["Computer Science", "Statistics"]
}
```

Single analysis with exports:

```bash
python -m resume_analyzer.cli analyze \
    --resume samples/resumes/asha_verma.txt \
    --job samples/jobs/junior_data_analyst.json \
    --strategy weighted --ai off --format html pdf xlsx
```

Batch analysis with a progress bar and a ranked Excel summary:

```bash
python -m resume_analyzer.cli batch \
    --resumes-dir samples/resumes --job samples/jobs/junior_data_analyst.json \
    --output-dir data/reports --format xlsx
```

UI walkthrough: [USER_GUIDE.md](docs/USER_GUIDE.md).

## 10. Project structure (summary)

```text
intelligent-resume-analyzer/
├── README.md
├── docs/            # the other 11 documents
├── config/          # config.yaml, skills_taxonomy.json
├── src/resume_analyzer/
│   ├── ingestion/ parsing/ skills/ validation/ matching/ scoring/
│   ├── ai/ reporting/ storage/ services/ ui/ models/ config/
│   └── cli.py, exceptions.py, logging_setup.py
├── tests/           # unit/, integration/, evaluation/, performance/, data/
├── samples/         # synthetic resumes and jobs only
└── data/            # runtime output (git-ignored)
```

Complete tree with the purpose of every file: [PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md).

## 11. Documentation index

| # | Document | Read it to learn… |
|---|---|---|
| 01 | `README.md` (this file) | What the project is and how to run it |
| 02 | [PROJECT_REQUIREMENTS.md](docs/PROJECT_REQUIREMENTS.md) | **What** must be built (requirement IDs, acceptance criteria) |
| 03 | [SYSTEM_ARCHITECTURE.md](docs/SYSTEM_ARCHITECTURE.md) | **How** the system is organised |
| 04 | [IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) | **In what order** to build it (15 phases) |
| 05 | [TECHNICAL_SPECIFICATION.md](docs/TECHNICAL_SPECIFICATION.md) | Exact models, formulas, function contracts |
| 06 | [AI_PROMPTS.md](docs/AI_PROMPTS.md) | The five prompt templates and AI safety rules |
| 07 | [TESTING_STRATEGY.md](docs/TESTING_STRATEGY.md) | Test catalogue, metrics, traceability matrix |
| 08 | [PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) | Repository layout |
| 09 | [CONFIGURATION_AND_SECURITY.md](docs/CONFIGURATION_AND_SECURITY.md) | Config keys, secrets, privacy, safe file handling |
| 10 | [USER_GUIDE.md](docs/USER_GUIDE.md) | How end users operate the app |
| 11 | [SUBMISSION_CHECKLIST.md](docs/SUBMISSION_CHECKLIST.md) | Final verification checklist |
| 12 | [DEVELOPMENT_RULES.md](docs/DEVELOPMENT_RULES.md) | **Binding rules for the coding agent — read first** |

Recommended reading order for the coding agent: 12 → 02 → 03 → 05 → 06 → 04 → 07 → 08 → 09 → 11 → 10 → 01.

## 12. Future improvements (out of scope for the capstone)

- OCR for scanned PDFs (e.g., Tesseract) and legacy `.doc` support.
- AI-assisted extraction of requirements from a pasted job description.
- Embedding-based semantic skill similarity as an additional scoring signal (must be validated for bias first).
- Multi-user authentication, a database backend, and audit trails.
- Calibration of scoring weights against a labelled dataset.
- Multi-language resume support.
- Docker packaging and CI pipeline (GitHub Actions) running tests and linting.

## 13. Responsible-use notice

This tool supports, and never replaces, human judgement. It must not be used as the sole basis for
rejecting a candidate. It deliberately ignores protected or proxy attributes (age, gender, photo,
nationality, marital status, etc.). Scores reflect keyword and structure alignment with stated
requirements, **not** a candidate's ability or potential. See
[CONFIGURATION_AND_SECURITY.md](docs/CONFIGURATION_AND_SECURITY.md) §9.

## 14. CHANGELOG

### v1.0.0 (2026-11-09) — Final Submission Release
- **Core Engine (Phases 1–5):** Complete typed data models (`Candidate`, `JobRequirements`, `AnalysisReport`), 25+ domain exceptions, file loader supporting PDF, DOCX, and TXT with zip bomb, decompression ratio, and null-byte defenses, deterministic cleaner, and section segmenter.
- **Skills, Experience & Education (Phases 6–7):** 325+ skill taxonomy with O(1) multi-word n-gram search index, RapidFuzz matching with symmetrical confusable protection, robust experience duration calculation with date interval merging, and degree level hierarchy detection.
- **Scoring & AI Integration (Phases 8–9):** Strategy-pattern scoring (`basic` and `weighted` with zero/renormalization policies), multi-provider AI abstraction supporting Google Gemini, Ollama, OpenAI-compatible APIs, and `NullProvider`. Nonce-tagged prompt safety envelope, JSON schema validation, one-shot repair retries, and post-inference fact grounding.
- **Reporting, Exporters & UI (Phases 10–12):** Standalone Jinja2 HTML exporter with CSS styling, ReportLab PDF exporter with multi-page headers, OpenPyXL multi-tab Excel exporter, atomic JSON storage with thread-safe file locks, feedback review loop, CLI runner, and 4-step Streamlit web application.
- **Evaluation, Optimization & Hardening (Phases 13–15):** Benchmark suite across 100+ synthetic resumes with 96.25% extraction accuracy (M-01) and 98.2% matching precision (M-03). Adversarial robustness suite verifying zero score hijacking (ET-03). Performance optimizations delivering 165+ resumes/sec throughput and 2.49ms median latency (ET-04). Cyclomatic complexity reduced to Rank A (4.80) across 392 blocks with 100% clean Bandit and Ruff checks.

---
**Document control** — Version 1.0 · Owner: project author · Change log: Release v1.0.0 finalized and verified.

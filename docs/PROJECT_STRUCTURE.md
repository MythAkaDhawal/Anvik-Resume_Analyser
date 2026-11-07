# PROJECT_STRUCTURE.md — Recommended Repository Structure

Related: [SYSTEM_ARCHITECTURE §4, §6](SYSTEM_ARCHITECTURE.md) · [TECHNICAL_SPECIFICATION §5](TECHNICAL_SPECIFICATION.md) · [IMPLEMENTATION_PLAN](IMPLEMENTATION_PLAN.md) · [DEVELOPMENT_RULES](DEVELOPMENT_RULES.md)

> This is the **target** layout. Create files phase by phase (see [IMPLEMENTATION_PLAN](IMPLEMENTATION_PLAN.md)); do **not** create empty placeholder modules ahead of need.
> The coding agent must inspect the repository before creating, modifying, or deleting anything (DR-REPO-1) and must keep this document in sync with the real tree (DR-DOC-3, test UT-DOC-01).

---

## 1. Documentation placement

| Document | Final location |
|---|---|
| `README.md` | repository root |
| `PROJECT_REQUIREMENTS.md`, `SYSTEM_ARCHITECTURE.md`, `IMPLEMENTATION_PLAN.md`, `TECHNICAL_SPECIFICATION.md`, `AI_PROMPTS.md`, `TESTING_STRATEGY.md`, `PROJECT_STRUCTURE.md`, `CONFIGURATION_AND_SECURITY.md`, `USER_GUIDE.md`, `SUBMISSION_CHECKLIST.md`, `DEVELOPMENT_RULES.md` | `docs/` |

Links: README → `docs/NAME.md`; docs → each other as `NAME.md`; docs → README as `../README.md`.
(The delivered package folder is flat for convenience; moving the files as above makes every link valid.)

## 2. Directory tree

```text
intelligent-resume-analyzer/
├── README.md
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── .gitignore
├── .streamlit/
│   └── config.toml
├── config/
│   ├── config.yaml
│   └── skills_taxonomy.json
├── docs/
│   ├── PROJECT_REQUIREMENTS.md
│   ├── SYSTEM_ARCHITECTURE.md
│   ├── IMPLEMENTATION_PLAN.md
│   ├── TECHNICAL_SPECIFICATION.md
│   ├── AI_PROMPTS.md
│   ├── TESTING_STRATEGY.md
│   ├── PROJECT_STRUCTURE.md
│   ├── CONFIGURATION_AND_SECURITY.md
│   ├── USER_GUIDE.md
│   ├── SUBMISSION_CHECKLIST.md
│   └── DEVELOPMENT_RULES.md
├── src/
│   └── resume_analyzer/
│       ├── __init__.py                 # __version__
│       ├── exceptions.py
│       ├── logging_setup.py
│       ├── cli.py
│       ├── config/
│       │   ├── __init__.py
│       │   └── settings.py
│       ├── models/
│       │   ├── __init__.py
│       │   ├── enums.py
│       │   ├── candidate.py
│       │   ├── job.py
│       │   └── results.py
│       ├── ingestion/
│       │   ├── __init__.py
│       │   ├── file_validator.py
│       │   ├── text_extractors.py
│       │   └── file_loader.py
│       ├── skills/
│       │   ├── __init__.py
│       │   ├── taxonomy.py
│       │   ├── normalizer.py
│       │   └── skill_index.py
│       ├── parsing/
│       │   ├── __init__.py
│       │   ├── text_cleaner.py
│       │   ├── section_splitter.py
│       │   ├── contact_extractor.py
│       │   ├── skills_extractor.py
│       │   ├── experience_parser.py
│       │   ├── education_parser.py
│       │   ├── pii.py                  # mask_pii + injection-indicator scanner
│       │   └── resume_parser.py
│       ├── validation/
│       │   ├── __init__.py
│       │   └── validators.py
│       ├── matching/
│       │   ├── __init__.py
│       │   ├── skill_matcher.py
│       │   ├── experience_evaluator.py
│       │   ├── education_evaluator.py
│       │   └── matching_engine.py
│       ├── scoring/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── basic.py
│       │   ├── weighted.py
│       │   ├── registry.py
│       │   └── bands.py
│       ├── ai/
│       │   ├── __init__.py
│       │   ├── provider_base.py
│       │   ├── provider_factory.py
│       │   ├── providers/
│       │   │   ├── __init__.py
│       │   │   ├── null.py
│       │   │   ├── gemini.py
│       │   │   ├── ollama.py
│       │   │   └── openai_compatible.py
│       │   ├── sanitizer.py
│       │   ├── grounding.py
│       │   ├── json_utils.py
│       │   ├── rate_limiter.py
│       │   ├── schemas.py
│       │   ├── prompt_registry.py
│       │   ├── prompt_templates/
│       │   │   ├── p1_extract_resume.j2
│       │   │   ├── p2_categorize_skills.j2
│       │   │   ├── p3_explain_match.j2
│       │   │   ├── p4_recommend_improvements.j2
│       │   │   └── p5_interview_questions.j2
│       │   └── ai_service.py
│       ├── reporting/
│       │   ├── __init__.py
│       │   ├── report_builder.py
│       │   ├── provenance.py
│       │   ├── exporters/
│       │   │   ├── __init__.py
│       │   │   ├── base.py
│       │   │   ├── html_exporter.py
│       │   │   ├── pdf_exporter.py
│       │   │   └── excel_exporter.py
│       │   ├── templates/
│       │   │   └── report.html.j2
│       │   └── assets/
│       │       └── fonts/              # bundled open-licensed Unicode font + LICENSE
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── paths.py
│       │   ├── result_store.py
│       │   └── feedback_store.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── analysis_service.py
│       │   └── batch_runner.py
│       └── ui/
│           ├── __init__.py
│           ├── streamlit_app.py
│           ├── components.py
│           └── state.py
├── scripts/
│   ├── summarize_feedback.py
│   └── check_docs.py                   # link/structure checks used by UT-DOC-*
├── samples/
│   ├── resumes/                        # synthetic only
│   ├── jobs/
│   └── outputs/                        # generated demo reports (synthetic)
├── tests/
│   ├── conftest.py
│   ├── unit/
│   ├── integration/
│   ├── evaluation/
│   │   └── results/                    # dated evaluation reports (actual measurements)
│   ├── performance/
│   └── data/
│       ├── README_DATA.md              # provenance of every synthetic dataset
│       ├── resumes/  gold/  jobs/  labels/  adversarial/  edge/  ai_fakes/
├── data/                               # runtime output — git-ignored
│   ├── results/
│   ├── reports/
│   └── feedback/
└── logs/                               # runtime logs — git-ignored
```

## 3. Purpose of directories and key files

### 3.1 Repository root

| Path | Purpose |
|---|---|
| `README.md` | Entry point (see [README](../README.md)) |
| `pyproject.toml` | Package metadata (`src/` layout), tool configuration: `ruff`, `black`, `pytest` (markers `evaluation`, `performance`, `slow`), `bandit` exclusions, `radon` options |
| `requirements.txt` | Runtime dependencies with compatible-release specifiers |
| `requirements-dev.txt` | Test and quality tools (`-r requirements.txt` included) |
| `.env.example` | Variable **names** with empty values; committed. Real `.env` is git-ignored |
| `.gitignore` | Must ignore: `.env`, `.venv/`, `__pycache__/`, `data/`, `logs/`, `.pytest_cache/`, `.coverage`, `htmlcov/`, `*.tmp`, `tests/evaluation/ai_runs/`, any real-resume folders |
| `.streamlit/config.toml` | `server.maxUploadSize` = configured limit; `browser.gatherUsageStats = false`; no custom theme required |

### 3.2 `config/`

| File | Purpose |
|---|---|
| `config.yaml` | Central configuration (keys in [CONFIGURATION_AND_SECURITY §3](CONFIGURATION_AND_SECURITY.md)); contains **no secrets** |
| `skills_taxonomy.json` | Curated skills, aliases, categories, confusable pairs ([TECHNICAL_SPECIFICATION §7.1](TECHNICAL_SPECIFICATION.md)); includes a `sources` field listing data sources/licences |

### 3.3 `src/resume_analyzer/` packages

| Package / module | Purpose | Key requirements |
|---|---|---|
| `__init__.py` | Version string only | — |
| `exceptions.py` | Exception hierarchy, error codes, user messages | NFR-04 |
| `logging_setup.py` | Logging configuration and PII-masking filter | NFR-01, NFR-11 |
| `cli.py` | `argparse` entry point: `analyze`, `batch`, `list`, `export`, `purge`, `feedback-summary`, `benchmark` | FR-30 |
| `config/settings.py` | Typed settings, YAML loading, env overrides | NFR-02 |
| `models/` | Enums and pydantic models: candidate, job, results, report | FR-04–FR-09, FR-22 |
| `ingestion/file_validator.py` | Safety validation of uploads | FR-01, NFR-10 |
| `ingestion/text_extractors.py` | PDF/DOCX/TXT → text | FR-02 |
| `ingestion/file_loader.py` | Validation + extraction + limits | FR-01, FR-02 |
| `skills/taxonomy.py` | Load/validate taxonomy | FR-05 |
| `skills/normalizer.py` | `normalize_skill` (cached) | FR-05, NFR-03 |
| `skills/skill_index.py` | `SkillIndex`: alias map, n-gram scan, fuzzy helper | FR-05, FR-10, NFR-09 |
| `parsing/text_cleaner.py` | Text normalization | FR-03 |
| `parsing/section_splitter.py` | Heading detection | FR-05–FR-07 |
| `parsing/contact_extractor.py` | Name, e-mail | FR-04 |
| `parsing/skills_extractor.py` | Skills from sections/body | FR-05 |
| `parsing/experience_parser.py` | Date ranges, entries, total years | FR-06 |
| `parsing/education_parser.py` | Degrees, levels, fields | FR-07 |
| `parsing/pii.py` | PII masking and injection-indicator scanner | NFR-11, NFR-13 |
| `parsing/resume_parser.py` | Orchestrates parsing → `Candidate` | FR-08 |
| `validation/validators.py` | Job/candidate validation, parse-quality warnings | FR-09, NFR-05 |
| `matching/*` | Skill matching, experience/education evaluators, engine | FR-10–FR-12 |
| `scoring/*` | Strategy interface, basic/weighted, registry, bands | FR-13–FR-16 |
| `ai/provider_base.py` | `LLMProvider` protocol | NFR-18 |
| `ai/providers/*` | Null, Gemini, Ollama, OpenAI-compatible adapters | FR-32, NFR-18 |
| `ai/provider_factory.py` | Builds provider from settings and environment | NFR-12 |
| `ai/sanitizer.py`, `grounding.py`, `json_utils.py`, `rate_limiter.py` | AI safety and robustness helpers | NFR-13 |
| `ai/schemas.py` | Pydantic output and fact models | FR-17–FR-21 |
| `ai/prompt_registry.py`, `prompt_templates/` | Versioned prompt templates (identical to AI_PROMPTS.md) | FR-17–FR-21 |
| `ai/ai_service.py` | Five AI features with validation and degradation | FR-17–FR-21, FR-32 |
| `reporting/report_builder.py`, `provenance.py` | Build `AnalysisReport`, labels and fixed notices | FR-22, FR-23 |
| `reporting/exporters/*` | HTML, PDF, Excel exporters | FR-24–FR-26 |
| `reporting/templates/report.html.j2` | HTML report template | FR-24 |
| `reporting/assets/fonts/` | Bundled Unicode font + licence | FR-25 |
| `storage/paths.py` | `safe_join`, id regex, directory helpers | NFR-05, NFR-10 |
| `storage/result_store.py` | JSON persistence, listing, purge | FR-27, FR-28, NFR-19 |
| `storage/feedback_store.py` | JSONL feedback and summary | FR-29 |
| `services/analysis_service.py` | Pipeline facade | all pipeline FRs |
| `services/batch_runner.py` | Batch with progress and isolation | FR-30 |
| `ui/*` | Streamlit app, reusable components, session-state helpers | FR-31 |

### 3.4 Other directories

| Path | Purpose |
|---|---|
| `scripts/summarize_feedback.py` | Prints feedback summary (wrapper over `FeedbackStore.summarize`) |
| `scripts/check_docs.py` | Checks Markdown links and README/structure sync (used by UT-DOC-01/02) |
| `samples/` | Synthetic demo resumes/jobs and generated outputs. Never real personal data |
| `tests/unit/` | One test module per source module (`test_<module>.py`) |
| `tests/integration/` | IT-01 … IT-08 |
| `tests/evaluation/` | ET-01 … ET-06 scripts; `results/` holds dated reports of **actual** measurements |
| `tests/performance/` | PT-01, PT-02 timing probes |
| `tests/data/` | Datasets D1–D5 ([TESTING_STRATEGY §3](TESTING_STRATEGY.md)) with `README_DATA.md` describing how each was created |
| `data/` | Runtime outputs: `results/` (analysis JSON), `reports/` (exports), `feedback/` (JSONL). Git-ignored |
| `logs/` | Rotating log files. Git-ignored |

## 4. Structure rules

1. **No new top-level directories** or documents without updating this file.
2. One responsibility per module; modules ≤ ~400 lines (guideline). Split rather than grow.
3. No circular imports; dependency direction per [SYSTEM_ARCHITECTURE §6](SYSTEM_ARCHITECTURE.md) (UT-ARCH-01).
4. No business logic in `ui/` or `cli.py`.
5. No duplicate functionality: before adding a helper, search the code base (DR-CODE-2).
6. Do not commit generated artefacts (`data/`, `logs/`, exports) except curated `samples/outputs/` produced from synthetic data.
7. Test files mirror source modules; fixtures live in `conftest.py` or `tests/data/`.

## 5. Skeleton snippets (specification)

`pyproject.toml` tool sections (illustrative; verify option names against current tool versions):

```toml
[tool.black]
line-length = 88
target-version = ["py310"]

[tool.ruff]
line-length = 88
src = ["src", "tests"]
[tool.ruff.lint]
select = ["E", "W", "F", "I", "N", "UP", "B", "S", "C90", "D"]
[tool.ruff.lint.mccabe]
max-complexity = 10
[tool.ruff.lint.pydocstyle]
convention = "google"
[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "D"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-m 'not evaluation and not performance'"
markers = ["evaluation: accuracy and robustness evaluations", "performance: timing probes", "slow: slow tests"]
```

`.streamlit/config.toml`:

```toml
[server]
maxUploadSize = 5            # MB; keep equal to files.max_size_mb
enableXsrfProtection = true

[browser]
gatherUsageStats = false
```

`.env.example`:

```text
# Copy to .env and fill in. NEVER commit .env.
GEMINI_API_KEY=
OPENAI_API_KEY=
OLLAMA_HOST=http://localhost:11434
RESUME_ANALYZER_CONFIG=
RESUME_ANALYZER_DATA_DIR=
RESUME_ANALYZER_LOG_LEVEL=
```

---
**Document control** — Version 1.0 · Change log: *(none yet)*

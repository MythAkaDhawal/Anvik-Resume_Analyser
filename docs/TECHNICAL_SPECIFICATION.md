# TECHNICAL_SPECIFICATION.md — Implementation Specification

Related: [PROJECT_REQUIREMENTS](PROJECT_REQUIREMENTS.md) · [SYSTEM_ARCHITECTURE](SYSTEM_ARCHITECTURE.md) · [AI_PROMPTS](AI_PROMPTS.md) · [CONFIGURATION_AND_SECURITY](CONFIGURATION_AND_SECURITY.md) · [TESTING_STRATEGY](TESTING_STRATEGY.md)

> **Specification, not implementation.** Code blocks below define contracts (signatures, models, formulas). They are
> illustrative specifications that the coding agent must implement and verify; none of it exists yet.
> Labels: **[REQUIRED]** = needed for submission (MUST/SHOULD requirements) · **[OPTIONAL]** = enhancement (COULD).

---

## 1. Python version and environment

| Item | Specification |
|---|---|
| Recommended Python | **3.11** (tested target). Minimum supported: **3.10**. Do not use features newer than 3.11. |
| Packaging | `pyproject.toml` (setuptools, `src/` layout); `pip install -e .` |
| Virtual environment | `python -m venv .venv` |
| Code style | PEP 8; `black` (line length 88) + `ruff` (rules: `E,W,F,I,N,UP,B,S,C90,D` with Google docstring convention, `max-complexity = 10`) |
| Typing | Type hints on all function signatures; `from __future__ import annotations`; `mypy` is **[OPTIONAL]** |
| Docstrings | Google style on all public modules, classes, functions |
| Time handling | Timezone-aware UTC (`datetime.now(timezone.utc)`); functions needing "today" accept `reference_date: date` for deterministic tests |

## 2. Technology selection (primary choice + brief alternatives)

| Concern | **Primary** | Alternatives (why not primary) |
|---|---|---|
| UI | **Streamlit** | Gradio (less layout control), Flask/FastAPI + templates (more code), Tkinter (dated UX) |
| PDF text extraction | **pdfplumber** (fallback **pypdf**) | PyMuPDF (AGPL licence concerns), pdfminer.six (lower-level) |
| DOCX parsing | **python-docx** | docx2txt (loses tables/structure), mammoth (HTML-oriented) |
| Fuzzy matching | **rapidfuzz** | thefuzz (slower), difflib (slower, weaker scoring) |
| Data models / validation | **pydantic v2** | dataclasses + manual validation, attrs |
| GenAI access | **`LLMProvider` protocol** with adapters: **Gemini** (`google-genai` SDK; free tier may exist — verify), **Ollama** (local HTTP API via `requests`), **OpenAI-compatible** (HTTP via `requests`), **Null** | Direct vendor SDK calls everywhere (lock-in); LangChain (heavy abstraction for 5 simple calls) |
| Config | **PyYAML** + pydantic | JSON, TOML (Python 3.11 has `tomllib` but read-only; YAML allows comments and is common) |
| Persistence | **JSON files** | SQLite (documented upgrade path) |
| HTML export | **Jinja2** (autoescape on) | f-strings (escaping risk) |
| PDF export | **reportlab** | WeasyPrint (needs system libraries), pdfkit/wkhtmltopdf (external binary) |
| Excel export | **openpyxl** | XlsxWriter (write-only, also fine), pandas `to_excel` (adds large dependency) |
| Progress (CLI) | **tqdm** | rich |
| Testing | **pytest**, `pytest-cov` | unittest (more boilerplate) |
| Security/quality tools | **bandit**, **ruff**, **black**, **radon** | flake8/pylint |

## 3. Dependencies

Versions: determine the current stable release at install time and record **compatible-release** specifiers in
`requirements.txt` (e.g., `rapidfuzz>=3,<4`). Do not copy version numbers from this document; the minimum majors
below are lower bounds believed valid at authoring time and must be verified.

### 3.1 Runtime (`requirements.txt`)

| Package | Min major | Purpose | Class |
|---|---|---|---|
| `pydantic` | 2 | Models and validation | REQUIRED |
| `PyYAML` | 6 | Read `config.yaml` | REQUIRED |
| `python-dotenv` | 1 | Load `.env` in development | REQUIRED |
| `pdfplumber` | 0.11 | PDF text | REQUIRED |
| `pypdf` | 4 | PDF fallback + encryption check | REQUIRED |
| `python-docx` | 1 | DOCX text | REQUIRED |
| `rapidfuzz` | 3 | Fuzzy matching | REQUIRED |
| `Jinja2` | 3.1 | HTML report and prompt templates | REQUIRED |
| `reportlab` | 4 | PDF report | REQUIRED |
| `openpyxl` | 3.1 | Excel report | REQUIRED |
| `streamlit` | 1.3x (verify current) | UI | REQUIRED |
| `tqdm` | 4 | CLI progress | REQUIRED |
| `requests` | 2 | Ollama / OpenAI-compatible adapters | REQUIRED |
| `google-genai` | 1 | Gemini adapter (import lazily; only needed when provider = gemini) | OPTIONAL |

### 3.2 Development (`requirements-dev.txt`)

`pytest`, `pytest-cov`, `ruff`, `black`, `bandit`, `radon`, `types-PyYAML`, `types-requests`, `mypy` (optional).
`reportlab`/`openpyxl`/`pypdf` are also used by tests to **read back** generated exports (UT-XPT).

## 4. Enumerations and data models

All models: pydantic v2 `BaseModel` with `model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)`.
The shapes below are the **contract**; field names are final.

### 4.1 Enumerations (`models/enums.py`)

```python
class Provenance(str, Enum):
    EXTRACTED_RULE = "extracted_rule"
    EXTRACTED_AI = "extracted_ai"
    COMPUTED = "computed"
    AI_GENERATED = "ai_generated"

class EducationLevel(IntEnum):
    UNSPECIFIED = 0
    HIGH_SCHOOL = 1
    DIPLOMA = 2          # diploma / associate / polytechnic
    BACHELOR = 3
    MASTER = 4
    DOCTORATE = 5

class MatchType(str, Enum):
    EXACT = "exact"; ALIAS = "alias"; FUZZY = "fuzzy"; NONE = "none"

class FitBand(str, Enum):
    STRONG = "strong"; MODERATE = "moderate"; LIMITED = "limited"; LOW = "low"

class FeatureStatus(str, Enum):
    OK = "ok"; PARTIAL = "partial"; UNAVAILABLE = "unavailable"
    DISABLED = "disabled"; BLOCKED = "blocked"

class ComponentStatus(str, Enum):
    EVALUATED = "evaluated"; NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"; NOT_USED = "not_used"
```

### 4.2 Candidate models (`models/candidate.py`)

```python
class ParseWarning(BaseModel):
    code: str                      # see §6.8
    message: str                   # no resume content / PII
    field: str | None = None

class Skill(BaseModel):
    name: str                              # as found (cleaned), 1-60 chars
    canonical_name: str | None = None      # taxonomy canonical, None if unrecognized
    category: str | None = None
    category_provenance: Provenance | None = None
    provenance: Provenance = Provenance.EXTRACTED_RULE
    mentions: int = Field(default=1, ge=1)

class ExperienceEntry(BaseModel):
    job_title: str | None = None
    company: str | None = None
    start: date | None = None              # first day of month
    end: date | None = None                # first day of month; None if current/unknown
    is_current: bool = False
    duration_months: int | None = Field(default=None, ge=0)   # computed from dates only
    provenance: Provenance = Provenance.EXTRACTED_RULE

class EducationEntry(BaseModel):
    degree: str | None = None              # raw degree text
    level: EducationLevel = EducationLevel.UNSPECIFIED       # computed from degree text
    field_of_study: str | None = None
    institution: str | None = None
    provenance: Provenance = Provenance.EXTRACTED_RULE

class Candidate(BaseModel):
    candidate_id: str                      # first 12 hex chars of SHA-256(file bytes)
    name: str | None = None
    email: str | None = None
    skills: list[Skill] = []
    experience: list[ExperienceEntry] = []
    education: list[EducationEntry] = []
    total_experience_years: float | None = None   # merged-interval total; None = unknown
    highest_education_level: EducationLevel = EducationLevel.UNSPECIFIED
    source_format: Literal["pdf", "docx", "txt"]
    parse_warnings: list[ParseWarning] = []
    injection_indicators: list[str] = []          # codes from heuristic scanner (see AI_PROMPTS §2.4)
    parser_version: str
```

**Fields deliberately absent (fairness/privacy, NFR-14):** date of birth, age, gender, marital status, nationality,
religion, photo, street address, phone number, graduation year, social-media handles. Parsers must not extract or
store them; phone numbers and addresses are masked before any AI call (§6.7).

### 4.3 Job model (`models/job.py`)

```python
class JobRequirements(BaseModel):
    job_id: str                                  # slug/uuid assigned at creation
    job_title: str                               # 1-100 chars
    description: str | None = None               # <= 5000 chars; context only
    required_skills: list[str]                   # 1-50, each 1-60 chars
    optional_skills: list[str] = []              # 0-50
    min_experience_years: float = Field(default=0, ge=0, le=50)
    min_education_level: EducationLevel = EducationLevel.UNSPECIFIED
    preferred_fields: list[str] = []             # 0-10
```

Validators: strip; drop empty strings; de-duplicate case-insensitively preserving first spelling; a skill may not
appear in both required and optional lists (moved/rejected with message); collect **all** problems before raising
`DataValidationError`.

### 4.4 Result models (`models/results.py`)

```python
class SkillMatch(BaseModel):
    target: str                      # skill as entered in the job
    target_canonical: str | None
    is_required: bool
    matched_candidate_skill: str | None
    match_type: MatchType
    similarity: float = Field(ge=0, le=100)     # 100 for exact/alias, ratio for fuzzy, 0 for none
    credit: float = Field(ge=0, le=1)           # 1.0 exact/alias; similarity/100 fuzzy; 0 none
    provenance: Provenance = Provenance.COMPUTED

class ExperienceAnalysis(BaseModel):
    required_years: float
    candidate_years: float | None
    status: Literal["met", "partial", "unmet", "unknown", "not_required"]
    subscore: float | None           # 0..1 or None
    gap_years: float | None
    provenance: Provenance = Provenance.COMPUTED

class EducationAnalysis(BaseModel):
    required_level: EducationLevel
    candidate_level: EducationLevel
    status: Literal["met", "below", "unknown", "not_required"]
    field_match: bool | None         # None = not evaluated / unknown
    subscore: float | None
    provenance: Provenance = Provenance.COMPUTED

class MatchResult(BaseModel):
    skill_matches: list[SkillMatch]
    required_credit: float           # mean credit over required skills, 0..1
    optional_credit: float | None    # None when job has no optional skills
    experience: ExperienceAnalysis
    education: EducationAnalysis

class ScoreComponent(BaseModel):
    name: Literal["required_skills", "experience", "education", "optional_skills"]
    status: ComponentStatus
    weight: float                    # configured weight (0 for NOT_USED in basic)
    subscore: float | None           # 0..1
    points: float | None             # contribution on the 0..100 scale after renormalization
    explanation: str                 # plain-language formula instance

class ScoreResult(BaseModel):
    strategy_name: str
    total_score: float = Field(ge=0, le=100)     # rounded to 1 decimal
    components: list[ScoreComponent]
    coverage: float = Field(ge=0, le=1)          # share of intended weight that was evaluable
    fit_band: FitBand
    flags: list[str] = []                        # e.g. "INCOMPLETE_DATA", "MISSING_REQUIRED_SKILLS"
    provenance: Provenance = Provenance.COMPUTED
```

### 4.5 AI and report models

```python
class FeatureResult(BaseModel, Generic[T]):
    feature: Literal["extraction", "categorization", "explanation",
                     "recommendations", "interview_questions"]
    status: FeatureStatus
    data: T | None = None
    error_code: str | None = None
    prompt_id: str | None = None
    prompt_version: str | None = None
    model: str | None = None
    provenance: Provenance = Provenance.AI_GENERATED
    dropped_items: int = 0              # unverified items removed by grounding/validation

class AIInsights(BaseModel):
    categorization: FeatureResult[list[SkillCategory]] | None = None
    explanation: FeatureResult[MatchExplanation] | None = None
    recommendations: FeatureResult[list[Recommendation]] | None = None
    interview_questions: FeatureResult[list[InterviewQuestion]] | None = None
    # extraction (P1) augments Candidate and is recorded here only as status metadata:
    extraction_status: FeatureResult[None] | None = None

class ReportFlag(BaseModel):
    code: str                  # "INJECTION_INDICATORS", "INCOMPLETE_DATA", "AI_UNAVAILABLE", ...
    message: str

class AnalysisReport(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    report_id: str             # r"^\d{8}T\d{6}Z_[0-9a-f]{8}_[0-9a-f]{4}$"
    created_at: datetime       # UTC
    app_version: str
    config_snapshot: dict      # strategy, weights, thresholds, fuzzy settings, ai provider/model names (no secrets)
    candidate: Candidate
    job: JobRequirements
    match: MatchResult
    score: ScoreResult
    ai: AIInsights
    flags: list[ReportFlag] = []
    human_review_notice: str   # fixed text, see §11.1
```

`SkillCategory`, `MatchExplanation`, `Recommendation`, `InterviewQuestion` are defined in
[AI_PROMPTS §4–§8](AI_PROMPTS.md) and implemented in `ai/schemas.py`.

## 5. Module and function specifications

Conventions: *Raises* lists only project exceptions (§13). All functions have type hints and docstrings.
Public = importable by other packages.

### 5.1 `config`

| Function / class | Signature | Behaviour |
|---|---|---|
| `Settings` (pydantic) | nested models mirroring `config.yaml` | Validates ranges (weights sum to 1.0 ± 1e-6, thresholds `strong_min > moderate_min > limited_min`, positive limits) |
| `load_settings` | `(path: Path \| None = None) -> Settings` | `@lru_cache`-wrapped via `get_settings`; precedence: defaults < YAML < env overrides. Raises `ConfigurationError` |
| `get_settings` | `() -> Settings` | Cached singleton for UI/CLI entry points only; library code receives `Settings` by argument |

### 5.2 `ingestion`

| Function | Signature | Behaviour | Raises |
|---|---|---|---|
| `validate_upload` | `(filename: str, data: bytes, settings: FileSettings) -> ValidatedFile` | Checks: non-empty; size ≤ `max_size_mb`; extension allow-list (case-insensitive, **last** suffix only); magic bytes (`%PDF-` within first 1024 bytes; DOCX = ZIP signature `PK\x03\x04` **and** contains `word/document.xml`; TXT = no NUL bytes in first 8 KB and decodable); DOCX archive safety: member count ≤ 2 000, total uncompressed ≤ `max_docx_uncompressed_mb`, per-member compression ratio ≤ 100; macro-enabled files (`vbaProject.bin`) rejected; PDF: not encrypted (`pypdf.PdfReader.is_encrypted`), pages ≤ `max_pdf_pages`. Returns `ValidatedFile(format, sha256, size_bytes, safe_display_name)` where `safe_display_name` = `candidate-<sha12>.<ext>` (original name is **never** logged or stored) | `UnsupportedFileTypeError`, `FileTooLargeError`, `EmptyFileError`, `FileTypeMismatchError`, `UnsafeArchiveError`, `EncryptedFileError`, `UnreadableFileError` |
| `extract_text` | `(file: ValidatedFile, data: bytes) -> str` | Dispatches to format extractor; wraps library errors | `UnreadableFileError`, `EmptyResumeError` |
| `extract_pdf_text` | `(data: bytes, max_pages: int) -> str` | `pdfplumber` page by page; on exception for a page, try `pypdf` for that document once; joins pages with `\n\n` | `UnreadableFileError` |
| `extract_docx_text` | `(data: bytes) -> str` | Paragraph text in body order, then table cell text (row-wise, tab-separated) | `UnreadableFileError` |
| `extract_txt_text` | `(data: bytes) -> str` | Try `utf-8-sig`, `utf-8`, `cp1252`, `latin-1` in order (latin-1 never fails) | — |
| `load_resume` | `(filename: str, data: bytes, settings: FileSettings) -> LoadedResume` | `validate_upload` → `extract_text`; enforces `min_text_chars` ≤ len ≤ `max_text_chars` (longer → truncated with warning `TEXT_TRUNCATED`); never writes to disk | as above |

### 5.3 `parsing`

| Function | Signature | Behaviour |
|---|---|---|
| `clean_text` | `(text: str) -> str` | §6.1; idempotent |
| `split_sections` | `(text: str) -> dict[str, str]` | §6.2; keys: `header`, `summary`, `skills`, `experience`, `education`, `projects`, `certifications`, `other` |
| `extract_email` | `(text: str) -> tuple[str \| None, list[ParseWarning]]` | §6.3 |
| `extract_name` | `(header_text: str, email: str \| None) -> str \| None` | §6.3 |
| `extract_skills` | `(sections: dict[str, str], index: SkillIndex) -> list[Skill]` | §6.4 |
| `parse_experience` | `(experience_text: str, reference_date: date) -> tuple[list[ExperienceEntry], list[ParseWarning]]` | §6.5 |
| `total_experience_years` | `(entries: list[ExperienceEntry], reference_date: date) -> float \| None` | Merge overlapping intervals; `None` if no entry has a start date |
| `parse_education` | `(education_text: str) -> tuple[list[EducationEntry], list[ParseWarning]]` | §6.6 |
| `mask_pii` | `(text: str) -> str` | §6.7 |
| `scan_injection_indicators` | `(text: str) -> list[str]` | [AI_PROMPTS §2.4](AI_PROMPTS.md) |
| `ResumeParser.parse` | `(self, loaded: LoadedResume, reference_date: date \| None = None) -> Candidate` | Orchestrates the above; never raises for partial data; sets `parser_version`; computes `candidate_id` |

### 5.4 `skills`

| Item | Signature | Behaviour |
|---|---|---|
| `SkillTaxonomy` | `.from_file(path) -> SkillTaxonomy` (`@lru_cache` on the loader) | Validates schema: unique canonicals, no alias collisions across canonicals, categories declared |
| `normalize_skill` | `(text: str) -> str` (`@lru_cache(maxsize=8192)`) | NFKC, lowercase, remove parenthetical text, collapse whitespace, normalize dashes, strip leading/trailing punctuation except meaningful `+`, `#`, `.` inside tokens (`c++`, `c#`, `.net`, `node.js`) |
| `SkillIndex` | `__init__(taxonomy, fuzzy_enabled, fuzzy_threshold, fuzzy_min_length)` | Builds `alias_to_canonical: dict[str, str]`, `canonical_set`, `max_ngram` (≤ 4) |
| `SkillIndex.canonical` | `(norm: str) -> str \| None` | O(1) lookup |
| `SkillIndex.category` | `(canonical: str) -> str \| None` | O(1) |
| `SkillIndex.find_mentions` | `(text: str) -> Counter[str]` | n-gram scan (§6.4) returning canonical → mention count |
| `SkillIndex.is_confusable` | `(a: str, b: str) -> bool` | Symmetric lookup in taxonomy `confusable_pairs` |
| `fuzzy_similarity` | `(a: str, b: str) -> float` (`@lru_cache(maxsize=65536)`) | `rapidfuzz.fuzz.ratio` on normalized strings, 0–100 |

### 5.5 `validation`

| Function | Signature | Behaviour | Raises |
|---|---|---|---|
| `validate_job` | `(job: JobRequirements) -> JobRequirements` | Beyond pydantic: at least one required skill; lengths; duplicates; collects all problems | `DataValidationError` (E-DATA-001) |
| `validate_candidate` | `(candidate: Candidate) -> list[ParseWarning]` | Sanity checks: end ≥ start, no future start > 1 year, skills count ≤ 300, name length ≤ 100, e-mail regex | `DataValidationError` (E-DATA-002) only for structurally impossible data |
| `assess_parse_quality` | `(candidate: Candidate) -> list[ParseWarning]` | Adds warnings: `NO_SKILLS`, `NO_EXPERIENCE_DATES`, `NO_EDUCATION`, `NO_EMAIL`, `NO_NAME` |

### 5.6 `matching`

| Function | Signature | Behaviour |
|---|---|---|
| `match_skills` | `(candidate: Candidate, job: JobRequirements, index: SkillIndex, settings: MatchingSettings) -> list[SkillMatch]` | §7.2. Output has **exactly one** `SkillMatch` per job skill (required + optional) |
| `evaluate_experience` | `(candidate_years: float \| None, required_years: float) -> ExperienceAnalysis` | §7.3 |
| `evaluate_education` | `(candidate: Candidate, job: JobRequirements) -> EducationAnalysis` | §7.4 |
| `MatchingEngine.match` | `(candidate, job) -> MatchResult` | Calls the three functions; computes `required_credit`, `optional_credit` |

### 5.7 `scoring`

| Item | Signature | Behaviour |
|---|---|---|
| `ScoringStrategy` (ABC) | `name: ClassVar[str]`; `score(self, match: MatchResult, job: JobRequirements) -> ScoreResult` | Pure function of inputs + config |
| `BasicScoringStrategy` | name `"basic"` | §7.5 |
| `WeightedScoringStrategy` | name `"weighted"`; `__init__(weights: ScoreWeights, unknown_policy: Literal["exclude","zero"], bands: BandThresholds)` | §7.5 |
| `STRATEGY_REGISTRY` / `get_strategy` | `(name: str, settings: ScoringSettings) -> ScoringStrategy` | Raises `UnknownStrategyError` listing valid names |
| `fit_band_for` | `(score: float, bands: BandThresholds) -> FitBand` | §7.6 |

### 5.8 `ai`

| Item | Signature | Behaviour |
|---|---|---|
| `LLMProvider` (Protocol) | `name: str`; `model: str`; `generate_json(system: str, user: str, *, temperature: float, max_output_tokens: int, timeout_s: float) -> str` | Returns raw model text; raises `AIProviderError` (network, 5xx, 429 after retries), `AIBlockedError` (provider safety block), `AIConfigurationError` |
| `create_provider` | `(ai_settings: AISettings) -> LLMProvider` | Reads API key from env; if `enabled` false → `NullProvider`; if key missing → logs WARNING and returns `NullProvider` flagged `reason="missing_key"` |
| `NullProvider.generate_json` | raises `AIConfigurationError` | Allows uniform handling; `AIService` converts to `FeatureStatus.DISABLED` / `UNAVAILABLE` |
| `AIService` | `__init__(provider, settings, skill_index, rate_limiter)` | Methods in §9 |
| `sanitize_untrusted` | `(text: str, max_chars: int) -> SanitizedText` | [AI_PROMPTS §2.2](AI_PROMPTS.md) |
| `ground_items` | `(items: list[str], source_text: str, threshold: int = 90) -> tuple[list[str], int]` | Returns verified items and dropped count |
| `parse_json_response` | `(raw: str) -> dict` | Strips code fences, extracts the outermost JSON object, `json.loads` (no `eval`) |

### 5.9 `reporting`

| Item | Signature | Behaviour |
|---|---|---|
| `ReportBuilder.build` | `(candidate, job, match, score, ai: AIInsights, settings) -> AnalysisReport` | Generates `report_id`; builds flags (`INJECTION_INDICATORS`, `INCOMPLETE_DATA`, `AI_UNAVAILABLE`, `MISSING_REQUIRED_SKILLS`, `LOW_PARSE_QUALITY`); embeds `config_snapshot` |
| `Exporter` (ABC) | `format: ClassVar[str]`; `export(self, report: AnalysisReport, out_path: Path) -> Path` | Writes atomically; raises `ExportError` |
| `get_exporter` | `(fmt: Literal["html","pdf","xlsx"]) -> Exporter` | Raises `UnsupportedExportFormatError` |
| `export_batch_workbook` | `(reports: list[AnalysisReport], out_path: Path) -> Path` | Ranking workbook (§11.3) |

### 5.10 `storage`

| Function | Signature | Behaviour |
|---|---|---|
| `ResultStore.save` | `(report: AnalysisReport) -> Path` | `model_dump_json(indent=2)` → temp file in same dir → `os.replace`; file mode 0600 where supported |
| `ResultStore.load` | `(report_id: str) -> AnalysisReport` | Validates id against regex first; validates schema; `CorruptResultError` on failure |
| `ResultStore.list` | `() -> list[ReportSummary]` | Newest first; unreadable files listed with `readable=False` |
| `ResultStore.delete` | `(report_id: str) -> None` | |
| `ResultStore.purge_older_than` | `(days: int) -> int` | Deletes by `created_at`; returns count |
| `FeedbackStore.append` | `(record: FeedbackRecord) -> None` | JSON line append with file lock-free single-writer assumption |
| `FeedbackStore.summarize` | `() -> FeedbackSummary` | Counts, mean rating, thumbs ratios, most-corrected skills |
| `safe_join` | `(base: Path, name: str) -> Path` | Rejects separators, `..`, absolute paths; resolved path must stay under `base` |

### 5.11 `services`

| Item | Signature | Behaviour |
|---|---|---|
| `AnalysisService.analyze` | `(filename: str, data: bytes, job: JobRequirements, options: AnalysisOptions, reference_date: date \| None = None) -> AnalysisReport` | Pipeline of [SYSTEM_ARCHITECTURE §5](SYSTEM_ARCHITECTURE.md) |
| `AnalysisOptions` | `strategy: str`, `ai_features: set[str]`, `persist: bool` | |
| `BatchRunner.run` | `(files: Sequence[tuple[str, bytes]], job, options, progress: ProgressCallback \| None) -> BatchResult` | Per-file `try/except ResumeAnalyzerError`; `BatchResult(reports, failures: list[FileFailure(display_name, error_code, user_message)])`; sorted by score desc, tie-break by `required_credit` desc then `candidate_id` |
| `ProgressCallback` | `Callable[[int, int, str], None]` — `(done, total, display_name)` | `display_name` is the safe name |

## 6. Parsing logic (rule-based)

### 6.1 Text cleaning (`clean_text`)

Apply in order:

1. Unicode NFKC normalization.
2. Remove control characters except `\n` and `\t`; remove zero-width characters (`\u200b-\u200f`, `\ufeff`).
3. Normalize line endings to `\n`.
4. Replace bullet glyphs (`•●▪■◦‣·`, leading `-`/`*`) with `- `.
5. Re-join hyphenated line breaks: `(\w)-\n(\w)` → `\1\2` **only when** the next fragment starts lowercase.
6. Collapse runs of spaces/tabs to a single space; strip trailing spaces.
7. Collapse 3+ blank lines to 2.
8. Strip leading/trailing blank lines.

Idempotent: `clean_text(clean_text(x)) == clean_text(x)` (UT-CLEAN-05).

### 6.2 Section detection (`split_sections`)

A line is a **heading** if, after stripping punctuation/colons, it is ≤ 40 characters, has ≤ 5 words, and its lowercase form
equals or starts with a known heading synonym. Matching is case-insensitive; lines in ALL CAPS or Title Case are preferred
but not required.

| Section key | Synonyms (extend as needed) |
|---|---|
| `summary` | summary, professional summary, profile, objective, about me |
| `skills` | skills, technical skills, core competencies, key skills, technologies, tools |
| `experience` | experience, work experience, professional experience, employment history, internships, work history |
| `education` | education, academic background, qualifications, academics |
| `projects` | projects, personal projects, academic projects |
| `certifications` | certifications, certificates, licenses, courses |

Text before the first heading is `header` (used for name/e-mail). Unrecognized headings start `other`. If **no** headings are
found, the whole text is treated as `other` **and** scanned for skills (body scan) with warning `NO_SECTIONS_DETECTED`.

### 6.3 Contact extraction

- **E-mail:** regex `[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}` over the header, then the whole text. First valid match wins;
  additional distinct e-mails add warning `MULTIPLE_EMAILS`. Candidate strings are validated (length ≤ 254, one `@`, domain contains `.`).
  None found → `email=None`, warning `NO_EMAIL`. **AI never supplies e-mail.**
- **Name (heuristic, conservative):** first non-empty header line that (a) has 2–4 tokens, (b) each token alphabetic (allowing `.`, `'`, `-`),
  (c) is not a heading synonym, (d) contains no digits, `@`, or URL. If not satisfied → `None` + warning `NO_NAME`. A name may later be
  filled by P1 if and only if it passes grounding.

### 6.4 Skill extraction

1. **Skills section:** split on newlines, commas, semicolons, pipes, bullets, and `:` (category labels such as `Languages: Python, Java`
   drop the label). Do **not** split on `/` when the whole token is in the taxonomy (`CI/CD`); otherwise split on `/`.
   Each fragment is normalized; fragments longer than 40 characters or 5 words are discarded (they are sentences).
   - Taxonomy hit → `Skill(name=cleaned, canonical_name=canonical, category=taxonomy category, provenance=EXTRACTED_RULE)`.
   - No hit → `Skill(canonical_name=None, category=None)` (unrecognized; may be categorized by P2).
2. **Body scan:** tokenise `experience`, `projects`, `summary`, `certifications`, and `other` sections with regex
   `\.?[a-z0-9][a-z0-9+#.\-]*` (strip trailing `.`/`-`), generate 1–`max_ngram` (4) token n-grams, and look each up in `alias_to_canonical`.
   Body scan finds **taxonomy skills only**.
3. Merge by canonical name (or normalized string if unrecognized): `mentions` = total occurrences (skills-section hit counts as 1).
4. Cap: if more than 300 distinct skills are found, keep the first 300 by position and add warning `SKILL_LIST_TRUNCATED` (stuffing defence).
5. Never emit a skill whose normalized form is not present in the text (UT-SKILL-06).

### 6.5 Experience extraction

**Date-range grammar (case-insensitive):**

```
range   := start sep end
sep     := "-" | "–" | "—" | "to" | "until" | "till"
start   := month_year | numeric_month_year | year
end     := start | present
present := "present" | "current" | "now" | "ongoing" | "till date" | "to date"
month_year         := (Jan|January|Feb|...|Dec|December) [.,]? \s* YYYY
numeric_month_year := (0?[1-9]|1[0-2]) [/.\-] YYYY
year               := YYYY            (1970 <= YYYY <= current_year + 1)
```

Resolution rules:

| Situation | Resolution |
|---|---|
| Month + year | first day of that month |
| Year only | **July 1** of that year (unbiased midpoint; documented limitation) |
| `present`-type end | `reference_date` (first day of its month); `is_current=True`, `end=None` |
| End before start | entry kept; `duration_months=None`; warning `INVALID_DATE_RANGE` |
| Start more than 12 months after `reference_date` | warning `FUTURE_DATE`; entry excluded from totals |
| Duration | `(end.year-start.year)*12 + end.month-start.month`, minimum 0 |

**Entry assembly:** each date range in the `experience` section starts an entry. The entry text is the lines from the previous
entry's end (or section start) through the line containing the range, plus following bullet lines until the next range.
`job_title`/`company` come from the line containing the range (after removing the range) or the line directly above it, split on
` at `, ` @ `, ` | `, ` - `, `, `; the first fragment matching a title lexicon (engineer, developer, analyst, intern, manager, scientist,
consultant, designer, lead, architect, administrator, associate, trainee, …) is the title; the remaining non-empty fragment is the
company. If ambiguous, leave `None` (never guess).

**Total years:** union of `[start, end]` intervals (merge overlaps and touching intervals), sum months, divide by 12, round to 1 decimal.
`count_internships: false` excludes entries whose title contains "intern". No entry with valid start → `None` (**unknown**, never 0).

### 6.6 Education extraction

Entry boundaries: a line containing a degree keyword begins an entry; subsequent lines until the next degree line belong to it.

Degree-level table (**short abbreviations ≤ 3 letters are matched case-sensitively and only inside the `education` section**):

| Level | Keywords |
|---|---|
| `DOCTORATE` | `ph.d`, `phd`, `doctorate`, `doctor of philosophy`, `d.phil` |
| `MASTER` | `master`, `m.sc`, `msc`, `m.s.`, `MS`, `m.tech`, `mtech`, `m.e.`, `ME`, `mba`, `m.a.`, `MA`, `mca`, `m.eng`, `meng` |
| `BACHELOR` | `bachelor`, `b.sc`, `bsc`, `b.s.`, `BS`, `b.tech`, `btech`, `b.e.`, `BE`, `b.a.`, `BA`, `bca`, `b.com`, `bcom`, `b.eng`, `beng`, `undergraduate degree` |
| `DIPLOMA` | `diploma`, `associate degree`, `associate of`, `polytechnic`, `a.s.`, `a.a.` |
| `HIGH_SCHOOL` | `high school`, `secondary school`, `hsc`, `ssc`, `12th`, `10th`, `a-levels`, `gcse` |

Field of study: text following `in` / `of` / `,` after the degree keyword, up to 60 characters, stopping at `|`, `(`, a year, or line end
(e.g., "Bachelor of Technology in Computer Science" → `Computer Science`). Institution: a remaining line containing `university`, `college`,
`institute`, `school`, or `academy`. **Graduation year is not extracted.** `highest_education_level` = max level over entries; no entry →
`UNSPECIFIED` + warning `NO_EDUCATION`.

### 6.7 PII masking (`mask_pii`)

Before any AI call, replace: e-mail → `[EMAIL]`; phone numbers (regex for 7+ digit sequences with common separators) → `[PHONE]`; URLs
(`https?://\S+`, `www\.\S+`, and `linkedin.com/...`, `github.com/...` patterns) → `[URL]`; lines that look like street addresses (number + street word, or postal-code patterns) → `[ADDRESS]`.
Names are *not* masked in P1 (needed to extract the name) but are **never** sent in P2–P5 (candidate is referred to as "the candidate").

### 6.8 Parse warning codes

`NO_NAME`, `NO_EMAIL`, `MULTIPLE_EMAILS`, `NO_SKILLS`, `NO_SECTIONS_DETECTED`, `SKILL_LIST_TRUNCATED`, `NO_EXPERIENCE_DATES`,
`INVALID_DATE_RANGE`, `FUTURE_DATE`, `NO_EDUCATION`, `UNKNOWN_DEGREE`, `TEXT_TRUNCATED`, `LOW_TEXT_QUALITY` (many non-alphanumeric symbols
or very short average line length), `INJECTION_INDICATORS` (also surfaced as a report flag).

## 7. Matching and scoring

### 7.1 Skill taxonomy file (`config/skills_taxonomy.json`)

```json
{
  "schema_version": "1.0",
  "categories": ["Programming Languages", "Frameworks & Libraries", "Databases",
                 "Cloud & DevOps", "Data Science & ML", "Tools & Platforms",
                 "Soft Skills", "Domain Knowledge", "Other"],
  "skills": [
    {"canonical": "Python", "category": "Programming Languages", "aliases": ["python3", "py"]},
    {"canonical": "AWS", "category": "Cloud & DevOps", "aliases": ["amazon web services"]},
    {"canonical": "Pandas", "category": "Data Science & ML", "aliases": ["pandas library"]}
  ],
  "confusable_pairs": [["java", "javascript"], ["c", "c++"], ["c", "c#"], ["sql", "nosql"],
                       ["react", "react native"], ["angular", "angularjs"]]
}
```

Seed size: **at least 300 curated skills** across the categories (candidate sources for curation: O\*NET and ESCO skill listings — verify their
licences and cite them; do not bulk-copy without checking). Aliases must be unique across the taxonomy (validated at load).

### 7.2 Skill matching algorithm

For each job skill `t` (required and optional):

1. `t_norm = normalize_skill(t)`; `t_can = index.canonical(t_norm)` (may be `None`).
2. Candidate skills are pre-indexed: `cand_norms` (set of normalized names) and `cand_by_canonical` (canonical → Skill).
3. **EXACT:** `t_norm ∈ cand_norms` → `similarity=100`, `credit=1.0`.
4. **ALIAS:** `t_can` is not `None` and `t_can ∈ cand_by_canonical` → `similarity=100`, `credit=1.0`.
5. **FUZZY** (only if `matching.fuzzy_enabled`): consider candidate skills `c` such that **`t_can is None or c.canonical_name is None`**
   (*if both sides are known taxonomy skills they are different skills by definition, so no fuzzy match*). For each, compute
   `s = fuzzy_similarity(t_norm, normalize_skill(c.name))`. Accept the best `c` if **all** hold:
   `s ≥ fuzzy_threshold` (default 85); `min(len(t_norm), len(c_norm)) ≥ fuzzy_min_length` (default 4); first characters equal;
   `not index.is_confusable(t_norm, c_norm)`. Then `match_type=FUZZY`, `similarity=s`, `credit=s/100`.
6. Otherwise `NONE`, `credit=0`.

Properties (tested): each job skill yields exactly one `SkillMatch`; a candidate skill may satisfy several job skills (no exclusivity);
results are order-independent; deterministic.

`required_credit = mean(credit over required)`; `optional_credit = mean(credit over optional)` or `None` when the job has no optional skills.

### 7.3 Experience evaluation

| Case | `status` | `subscore` |
|---|---|---|
| `required_years == 0` | `not_required` | `None` |
| `candidate_years is None` | `unknown` | `None` |
| `candidate_years ≥ required_years` | `met` | `1.0` |
| otherwise | `partial` if `candidate_years > 0` else `unmet` | `candidate_years / required_years` |

`gap_years = max(0, required − candidate)` (or `None` when unknown).

### 7.4 Education evaluation

Let `req = job.min_education_level`, `cand = candidate.highest_education_level` (integer levels).

| Case | `status` | base subscore |
|---|---|---|
| `req == UNSPECIFIED` | `not_required` | `None` |
| `cand == UNSPECIFIED` | `unknown` | `None` |
| `cand ≥ req` | `met` | `1.0` |
| `cand == req − 1` | `below` | `0.5` |
| `cand < req − 1` | `below` | `0.0` |

Field-of-study adjustment: if `job.preferred_fields` is non-empty **and** `status == met` **and** the candidate has at least one education
entry with a field: `field_match = any(rapidfuzz.fuzz.token_set_ratio(pref, field) ≥ 85)`; if `field_match is False` the subscore is
capped at `0.75`. If the candidate has no field text, `field_match=None` and no cap applies.

### 7.5 Scoring strategies

**Basic (`"basic"`)** — required-skill coverage only:

```
score_basic = 100 × required_credit
```

Components: `required_skills` EVALUATED (weight 1.0); all others `NOT_USED`. `coverage = 1.0`.

**Weighted (`"weighted"`, default)** — default weights (configurable, must sum to 1.0):

| Dimension | Default weight | Applicability |
|---|---|---|
| `required_skills` | 0.50 | always evaluated (job has ≥ 1 required skill) |
| `experience` | 0.20 | `NOT_APPLICABLE` if min years = 0; `UNKNOWN` if candidate years unknown |
| `education` | 0.15 | `NOT_APPLICABLE` if requirement unspecified; `UNKNOWN` if candidate level unknown |
| `optional_skills` | 0.15 | `NOT_APPLICABLE` if job lists no optional skills |

```
E  = dimensions with status EVALUATED
score_weighted = 100 × ( Σ_{d∈E} w_d · s_d ) / ( Σ_{d∈E} w_d )

coverage = Σ_{d∈E} w_d / ( Σ_{d∈E} w_d + Σ_{d∈UNKNOWN} w_d )
```

`unknown_policy` (config `scoring.unknown_policy`): `"exclude"` (default) removes UNKNOWN dimensions from `E`; `"zero"` treats them as evaluated with `s_d = 0`
(then `coverage = 1.0` but flag `UNKNOWN_TREATED_AS_ZERO` is added). With `"exclude"`, if `coverage < 1` flag `INCOMPLETE_DATA` is added and the UI shows
"Score based on partial data".

Each `ScoreComponent.points = 100 × w_d·s_d / Σ_{E} w` so that component points sum to the total (± rounding). `total_score` is rounded to one decimal.

**Worked example (reproduced by UT-SCORE-02).** Job requires `Python, SQL, Docker, AWS, Pandas`; optional `Git, Streamlit, Tableau`; min experience 2 years;
min education BACHELOR. Candidate skills include `Python`, `SQL`, `Amazon Web Services`, `Panda`, `Git`, `Streamlit`; candidate has 1.5 years and a bachelor's degree.

| Job skill | Result | Credit |
|---|---|---|
| Python | EXACT | 1.000 |
| SQL | EXACT | 1.000 |
| Docker | NONE | 0.000 |
| AWS | ALIAS (`amazon web services`) | 1.000 |
| Pandas | FUZZY with `Panda` (ratio = 100·(1 − 1/11) ≈ 90.9) | 0.909 |

`required_credit = 3.909/5 = 0.7818`; optional: Git ✓, Streamlit ✓, Tableau ✗ → `0.6667`; experience `1.5/2 = 0.75`; education `1.0`.

| Strategy | Calculation | Score | Band |
|---|---|---|---|
| basic | `100 × 0.7818` | **78.2** | MODERATE |
| weighted | `100 × (0.50×0.7818 + 0.20×0.75 + 0.15×1.0 + 0.15×0.6667)` = `100 × 0.7909` | **79.1** | MODERATE |

### 7.6 Fit bands

Defaults (config `scoring.bands`): `STRONG ≥ 80`, `MODERATE ≥ 60`, `LIMITED ≥ 40`, else `LOW`. Applied to the **rounded** total score.
Display names: "Strong alignment", "Moderate alignment", "Limited alignment", "Low alignment". Bands describe *alignment with the stated requirements*;
they are not a recommendation to hire or reject. Every band is shown with the human-review notice (§11.1).

Additional flags: `MISSING_REQUIRED_SKILLS` (≥ 1 required skill with `NONE`) is raised regardless of band, so a high overall score cannot hide a missing must-have.

### 7.7 Limitations of the scoring (must be shown in the UI help and the report appendix)

1. Weights and thresholds are **design defaults, not empirically derived**; they must be calibrated on labelled data before any real-world use (see M-03/M-04).
2. Skill coverage measures *mention* of a skill, not proficiency or recency.
3. Fuzzy matches can be false positives (e.g., `scala`/`scalar` when `scalar` is not in the taxonomy); they are labelled FUZZY and receive partial credit.
4. Experience counts elapsed time, not relevance; year-only dates are approximated.
5. Education is ordinal and ignores institution quality (intentionally, to avoid prestige bias).
6. Unrecognized skills outside the taxonomy are matched by string only.
7. The score is not a measure of potential, culture fit, or job performance.

## 8. Scoring strategy interface

```python
class ScoringStrategy(ABC):
    name: ClassVar[str]

    @abstractmethod
    def score(self, match: MatchResult, job: JobRequirements) -> ScoreResult:
        """Return a ScoreResult; must be deterministic and free of I/O."""
```

Adding a strategy = new class in `scoring/` + one registry entry + tests; no other module changes (FR-15). `get_strategy(name)` raises
`UnknownStrategyError` (E-MATCH-001) with the list of valid names.

## 9. AI service contract

| Method | Feature | Inputs (all sanitized/masked) | Returns |
|---|---|---|---|
| `extract_resume(text: str, known_candidate: Candidate) -> FeatureResult[ExtractionResult]` | P1 `extraction` | masked resume text | grounded additions merged by `AnalysisService` (merge rules below) |
| `categorize_skills(skills: list[str]) -> FeatureResult[list[SkillCategory]]` | P2 `categorization` | skill names lacking category | categories (`AI_GENERATED`) |
| `explain_match(facts: MatchFacts) -> FeatureResult[MatchExplanation]` | P3 `explanation` | deterministic facts with IDs | explanation |
| `recommend_improvements(facts: GapFacts) -> FeatureResult[list[Recommendation]]` | P4 `recommendations` | gaps | recommendations |
| `generate_interview_questions(facts: InterviewFacts) -> FeatureResult[list[InterviewQuestion]]` | P5 `interview_questions` | job + strengths + gaps | questions |

Common behaviour: render template → sanitize/mask → rate-limit → provider call with retries → `parse_json_response` → pydantic validation → feature-specific
validation/grounding → `FeatureResult`. **No method raises `AIError` to its caller**; errors become `FeatureResult(status=UNAVAILABLE|BLOCKED|DISABLED, error_code=...)`
(FR-32). Full prompts and rules: [AI_PROMPTS](AI_PROMPTS.md).

**P1 merge rules (`AnalysisService`)** — rule-based values always win:

| Field | Rule |
|---|---|
| `email` | rule-based only |
| `name` | AI name used only if rule-based is `None` and grounded |
| `skills` | union; AI-only skills are `EXTRACTED_AI`; de-duplicated by canonical/normalized name |
| `experience` | AI entries are added only when rule-based found **zero** entries; `duration_months` always recomputed from validated dates |
| `education` | AI entries added only if rule-based found none; `level` always recomputed deterministically from degree text |

Feature toggles are controlled by `ai.features` (config) and UI checkboxes.

## 10. Persistence specification

- Directory layout and retention: [CONFIGURATION_AND_SECURITY §7](CONFIGURATION_AND_SECURITY.md).
- Result file: `data/results/<report_id>.json`, UTF-8, `indent=2`, pydantic JSON mode (dates ISO-8601, enums as values).
- `report_id` format: `YYYYMMDDTHHMMSSZ_<candidate_id[:8]>_<4 random hex>`, validated by regex `^\d{8}T\d{6}Z_[0-9a-f]{8}_[0-9a-f]{4}$` before **any** filesystem access.
- `schema_version`: `"1.0"`. Loading an unknown major version raises `CorruptResultError` with a clear message; loading a minor-compatible version is allowed.
- Raw resume text and uploaded files are **not** persisted unless `storage.store_raw_text` / `files.store_uploaded_files` are explicitly enabled (default `false`).
- Writes: write to `<name>.tmp` in the same directory, `flush` + `os.fsync`, then `os.replace`.

Abbreviated example (illustrative):

```json
{
  "schema_version": "1.0",
  "report_id": "20261107T101500Z_3fa91c0b_a1c4",
  "created_at": "2026-11-07T10:15:00Z",
  "app_version": "0.1.0",
  "config_snapshot": {"strategy": "weighted", "weights": {"required_skills": 0.5, "experience": 0.2,
                      "education": 0.15, "optional_skills": 0.15}, "fuzzy_threshold": 85, "ai": {"provider": "none"}},
  "candidate": {"candidate_id": "3fa91c0b77de", "name": "Asha Verma", "email": "asha@example.com",
                "skills": [{"name": "Python", "canonical_name": "Python", "provenance": "extracted_rule", "mentions": 4}],
                "total_experience_years": 1.5, "highest_education_level": 3, "source_format": "txt",
                "parse_warnings": [], "parser_version": "0.1.0"},
  "job": {"job_id": "junior-data-analyst", "job_title": "Junior Data Analyst", "required_skills": ["Python", "SQL"]},
  "match": {"required_credit": 0.7818, "skill_matches": [ "…" ]},
  "score": {"strategy_name": "weighted", "total_score": 79.1, "coverage": 1.0, "fit_band": "moderate", "components": ["…"]},
  "ai": {"explanation": {"feature": "explanation", "status": "disabled"}},
  "flags": [{"code": "MISSING_REQUIRED_SKILLS", "message": "1 required skill not found."}],
  "human_review_notice": "…"
}
```

## 11. Reporting and export specification

### 11.1 Report content (all exporters render the same sections, in this order)

| # | Section | Contents | Provenance badge |
|---|---|---|---|
| 0 | Header | Report ID, date, app version, **human-review notice** | — |
| 1 | Candidate information | Name, e-mail, source format, parse warnings | EXTRACTED_* |
| 2 | Job information | Title, requirements, strategy used | — |
| 3 | Overall match score | Score, fit band, coverage, flags | COMPUTED |
| 4 | Score breakdown | Component table: weight, subscore, points, explanation | COMPUTED |
| 5 | Matched skills | Job skill → candidate skill, match type, similarity | COMPUTED |
| 6 | Missing skills | Required first, then optional | COMPUTED |
| 7 | Experience analysis | Required vs candidate years, status, entries table | COMPUTED / EXTRACTED_* |
| 8 | Education analysis | Required vs candidate level, field match, entries | COMPUTED / EXTRACTED_* |
| 9 | Recommendations | 9a *Reviewer notes* (P3 explanation); 9b *Candidate development suggestions* (P4) | AI_GENERATED |
| 10 | Hiring-suitability assessment | Fit band text + caveats (missing must-haves, incomplete data, injection indicators) + disclaimer | COMPUTED |
| 11 | Suggested interview questions | P5 output | AI_GENERATED |
| 12 | Appendix | Scoring limitations (§7.7), prompt versions, model name | — |

**Human-review notice (fixed text):** "This report supports, and does not replace, human judgement. Scores reflect alignment between stated
requirements and information extracted from the resume. AI-generated sections are interpretations that have not been verified. Do not use this report as the sole basis for any employment decision."

If an AI section's status is not `OK`/`PARTIAL`, render "AI-generated content unavailable (<status>)" instead of omitting the section.

### 11.2 HTML

Jinja2 environment with `autoescape=True`; single self-contained file (inline CSS, no external requests, no JavaScript required);
`<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:">`; badges via CSS classes.

### 11.3 PDF and Excel

- **PDF (reportlab platypus):** A4, title, tables, badges as coloured text labels; all dynamic strings pass through `xml.sax.saxutils.escape` before `Paragraph`;
  register a bundled open-licensed Unicode TTF (e.g., DejaVu Sans; ship its licence file) for non-Latin names; page footer with report id and page number.
- **Excel (openpyxl):** single-report workbook sheets `Summary`, `Skills`, `Experience-Education`, `AI-Insights`. Batch workbook adds first sheet `Ranking`
  (columns: Rank, Candidate ID, Name, Score, Fit band, Coverage, Missing required skills, Flags, Strategy). All text cells are written with explicit string type; any
  string beginning with `=`, `+`, `-`, `@`, tab, or carriage return is prefixed with `'` (formula-injection defence). Column widths set; header row frozen.

## 12. Logging specification

| Level | Use | Examples (no PII) |
|---|---|---|
| `INFO` | Lifecycle and outcomes | `analysis started cid=3fa91c0b strategy=weighted`; `analysis finished score=79.1 band=moderate duration_ms=412`; `export written fmt=pdf` |
| `WARNING` | Recoverable problems | `ai feature=explanation status=unavailable code=E-AI-002`; `parse warning NO_EXPERIENCE_DATES cid=…`; `missing GEMINI_API_KEY, using NullProvider` |
| `ERROR` | Failures needing attention | `file rejected code=E-FILE-005`; `storage write failed code=E-STORE-001`; unexpected exception with traceback (traceback text must not contain resume text) |
| `DEBUG` (optional) | Developer detail | timings, counts; still **no** resume text, prompts, or responses |

Format: `%(asctime)s | %(levelname)s | %(name)s | %(message)s` (UTC). Rotating file handler (`logging.max_bytes`, `logging.backup_count`) plus console.
A `PIIMaskingFilter` redacts e-mail and phone patterns in every record as defence in depth. Loggers are module-level `logging.getLogger(__name__)`.

## 13. Exceptions and error codes

Base class: `ResumeAnalyzerError(message: str, *, error_code: str, user_message: str | None = None, details: dict | None = None)`. `details` must not contain resume text.

| Class | Code | Typical `user_message` |
|---|---|---|
| `ConfigurationError` | E-CFG-001 | "The application configuration is invalid: <key>." |
| `UnsupportedFileTypeError` | E-FILE-001 | "Only PDF, DOCX and TXT files are supported." |
| `FileTooLargeError` | E-FILE-002 | "The file exceeds the size limit of N MB." |
| `EmptyFileError` | E-FILE-003 | "The file is empty." |
| `UnreadableFileError` | E-FILE-004 | "The file could not be read; it may be corrupted." |
| `EncryptedFileError` | E-FILE-005 | "Password-protected files are not supported." |
| `FileTypeMismatchError` | E-FILE-006 | "The file content does not match its extension." |
| `UnsafeArchiveError` | E-FILE-007 | "The file structure is unsafe or exceeds limits." |
| `EmptyResumeError` | E-PARSE-001 | "No readable text found. Scanned documents are not supported (no OCR)." |
| `ParsingError` | E-PARSE-002 | "The resume could not be parsed." |
| `DataValidationError` (job) | E-DATA-001 | "Job requirements are invalid: <list>." |
| `DataValidationError` (candidate) | E-DATA-002 | "Parsed data failed validation." |
| `UnknownStrategyError` | E-MATCH-001 | "Unknown scoring strategy. Available: basic, weighted." |
| `MatchingError` | E-MATCH-002 | "Matching failed unexpectedly." |
| `AIConfigurationError` | E-AI-001 | "AI is not configured (missing key or provider)." |
| `AIProviderError` | E-AI-002 | "The AI service is unavailable or timed out." |
| `AIResponseError` | E-AI-003 | "The AI returned an unusable response." |
| `AIBlockedError` | E-AI-004 | "The AI provider blocked this request." |
| `StorageError` | E-STORE-001 | "Could not write the result." |
| `ResultNotFoundError` | E-STORE-002 | "Saved analysis not found." |
| `CorruptResultError` | E-STORE-003 | "The saved analysis is unreadable." |
| `InvalidIdentifierError` | E-STORE-004 | "Invalid analysis identifier." |
| `ExportError` | E-EXPORT-001 | "The report could not be exported." |
| `UnsupportedExportFormatError` | E-EXPORT-002 | "Unsupported export format." |

Rules: catch the narrowest class; never `except:` or silent `except Exception: pass`; unexpected exceptions are logged with `logger.exception` and re-raised as `ResumeAnalyzerError(error_code="E-UNEXPECTED")` at the service boundary.

## 14. Caching policy (`functools.lru_cache`)

| Function | `maxsize` | Reason |
|---|---|---|
| `load_settings` / `get_settings` | 1 | Config read once |
| `SkillTaxonomy.from_file` (module-level loader) | 4 | Taxonomy parsed once per path |
| `normalize_skill` | 8192 | Pure, hot path |
| `fuzzy_similarity` | 65536 | Pure; repeated pairs across a batch |
| compiled regex helpers | default | Avoid recompilation |

**Never cached:** resume text, parsed candidates, AI prompts/responses (privacy and non-determinism). Tests must call `cache_clear()` in fixtures.

## 15. Command-line interface [REQUIRED for batch/benchmark support]

`python -m resume_analyzer.cli <command> [options]` (`argparse`).

| Command | Options | Behaviour |
|---|---|---|
| `analyze` | `--resume PATH` `--job PATH` `--strategy {basic,weighted}` `--ai {on,off}` `--format html pdf xlsx` `--output-dir DIR` `--no-save` | Single analysis; prints a short summary |
| `batch` | `--resumes-dir DIR` `--job PATH` `--strategy` `--ai` `--output-dir DIR` `--format xlsx html pdf` `--workers N` | tqdm progress; failures table; ranked summary |
| `list` | | List saved analyses |
| `export` | `--id REPORT_ID` `--format ...` | Re-export a saved analysis |
| `purge` | `--days N` `--yes` | Delete analyses older than N days |
| `feedback-summary` | | Print aggregated feedback |
| `benchmark` | `--resumes-dir DIR` `--runs N` | Deterministic-pipeline throughput (M-02) |

Exit codes: `0` success; `1` one or more files failed (batch) ; `2` invalid arguments/configuration; `3` unexpected error.

## 16. Streamlit UI contract (summary; user-facing labels in [USER_GUIDE](USER_GUIDE.md))

Sidebar navigation: **1 Job · 2 Resumes · 3 Results · 4 Reports · 5 History**. State in `st.session_state` keys: `job`, `files`, `reports`, `failures`, `options`.
Upload widget accepts multiple files with `type=["pdf","docx","txt"]`; `.streamlit/config.toml` sets `server.maxUploadSize` to the configured limit and disables usage stats.
UI code contains no business logic; it calls `AnalysisService`, `BatchRunner`, `get_exporter`, `ResultStore`, `FeedbackStore`.

## 17. Required vs optional functionality

| Capability | Class |
|---|---|
| FR-01 – FR-16, FR-22 – FR-28, FR-30 – FR-32, all MUST NFRs | **REQUIRED** |
| FR-17, FR-18, FR-19, FR-21 (AI features) — implemented and tested with a fake provider; exercised once with a real or local provider | **REQUIRED** |
| FR-20 (P4 recommendations), CLI `benchmark`, `mypy`, process-pool batch parsing | **REQUIRED/OPTIONAL as marked in requirements** (FR-20 SHOULD; others OPTIONAL) |
| Additional providers beyond one cloud + one local adapter | OPTIONAL |
| Embedding-based similarity, OCR, DB backend, authentication | OUT OF SCOPE |

---
**Document control** — Version 1.0 · Change log: *(none yet)*

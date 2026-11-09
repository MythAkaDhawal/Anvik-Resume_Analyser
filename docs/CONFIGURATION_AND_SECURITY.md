# CONFIGURATION_AND_SECURITY.md — Configuration & Security Specification

Related: [PROJECT_REQUIREMENTS](PROJECT_REQUIREMENTS.md) · [SYSTEM_ARCHITECTURE](SYSTEM_ARCHITECTURE.md) · [TECHNICAL_SPECIFICATION](TECHNICAL_SPECIFICATION.md) · [DEVELOPMENT_RULES](DEVELOPMENT_RULES.md)

---

## 1. Overview

The Intelligent Resume Analyzer is designed with a **secure-by-default, zero-trust mindset** toward untrusted candidate files and external inputs.

Key principles enforced:
1. **Deterministic Core:** Deterministic matching and scoring algorithms run locally with zero external network connectivity.
2. **AI Optionality:** The application runs fully with AI disabled (`ai.enabled: false`). When enabled, sensitive API keys are read strictly from environment variables, never committed or echoed in reports.
3. **Defense in Depth:** Every uploaded document is subjected to layered security checks (file extension, magic bytes, decompression ratio, zip bomb detection, null byte scans, and line length checks).

---

## 2. Configuration System

Configuration is managed via Pydantic v2 schemas in [`src/resume_analyzer/config/settings.py`](../src/resume_analyzer/config/settings.py) and loaded from [`config/config.yaml`](../config/config.yaml) with optional environment variable overrides.

### 2.1 Configuration Keys (`config.yaml`)

```yaml
app:
  data_dir: "data"
  reports_dir: "data/reports"
  feedback_dir: "data/feedback"

matching:
  strategy: "weighted"           # 'basic' or 'weighted'
  fuzzy_threshold: 85.0          # 0-100 similarity cutoff
  unknown_policy: "renormalize"  # 'renormalize' or 'zero'
  weights:
    required_skills: 0.50
    experience: 0.30
    education: 0.15
    optional_skills: 0.05

files:
  max_file_size_mb: 10
  allowed_extensions: [".pdf", ".docx", ".txt"]
  max_decompression_ratio: 100.0

ai:
  enabled: false
  provider: "gemini"             # 'gemini', 'ollama', 'openai_compatible', 'null'
  model: "gemini-1.5-flash"
  timeout_seconds: 30
  rate_limit:
    requests_per_minute: 15
  features:
    extraction: true
    categorization: true
    explanation: true
    recommendations: false
    interview_questions: false

logging:
  level: "INFO"
  format: "json"
  pii_masking: true
```

### 2.2 Environment Variables

| Variable | Description | Default |
|---|---|---|
| `GEMINI_API_KEY` | API Key for Google Gemini LLM API | None |
| `OPENAI_API_KEY` | API Key for OpenAI-compatible LLM endpoints | None |
| `OLLAMA_HOST` | Endpoint address for local Ollama instance | `http://localhost:11434` |
| `RESUME_ANALYZER_CONFIG` | Custom path to alternative YAML config file | `config/config.yaml` |
| `RESUME_ANALYZER_DATA_DIR` | Custom directory for reports and storage | `data/` |
| `RESUME_ANALYZER_LOG_LEVEL` | Log level override (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |

---

## 3. Security Controls & Protections

### 3.1 Ingestion Security
- **Archive Safety (`_check_docx_infolist_safety`):** Rejects zip archives with decompression ratios $> 100\times$, uncompressed size $> 50$ MB, or $> 1,000$ internal entries.
- **Null Byte and Binary Content Scans:** Plaintext uploads containing null bytes (`\x00`) or non-UTF-8 binary noise are immediately rejected with typed `UnreadableFileError`.
- **Magic Byte Validation:** PDF files must begin with `%PDF-` signature; DOCX files must start with `PK\x03\x04`. Extension mismatches raise `FileTypeMismatchError`.

### 3.2 AI Safety & Prompt Isolation (S-1 to S-5)
- **Zero-Tool Execution:** Model receives no tool execution, shell, browser, or code execution capabilities.
- **Nonce Delimiters:** Every prompt call wraps untrusted resume text inside dynamic, cryptographically generated boundaries (`<<<RESUME_{nonce}_BEGIN>>> ... <<<RESUME_{nonce}_END>>>`).
- **PII Masking:** Email addresses, phone numbers, and URLs are sanitized and masked in prompt context and logs (`[EMAIL_MASKED]`, `[PHONE_MASKED]`).
- **Post-Inference Grounding:** AI extractions and explanations are rigorously checked against actual resume text and verified match facts. Any hallucinated facts or hiring recommendations ("hire", "reject", "do not hire") are filtered out automatically.

### 3.3 Storage Security
- **Path Traversal Protection:** All report ID access is validated against regular expression `^[a-zA-Z0-9_-]{1,64}$` and resolved relative to storage roots via `safe_join()`.
- **Atomic File Writes:** Result reports and feedback records are written to `.tmp` files and atomically swapped using `os.replace` to prevent corrupted records during abrupt shutdowns or concurrent writes.

---

## 4. Responsible AI & Fair Review

This software serves exclusively as **decision support for human recruiters**. It adheres to the European Union AI Act and NYC Local Law 144 guidance:
- Scores reflect explicit requirement alignment and do not evaluate demographic, socio-economic, or proxy characteristics.
- Every report includes a prominent **Human Review Notice**.
- AI outputs are labelled with provenance tag `AI_GENERATED` and never modify deterministic candidate scores.

# DEVELOPMENT_RULES.md — Binding Engineering Principles

Related: [PROJECT_REQUIREMENTS](PROJECT_REQUIREMENTS.md) · [SYSTEM_ARCHITECTURE](SYSTEM_ARCHITECTURE.md) · [TECHNICAL_SPECIFICATION](TECHNICAL_SPECIFICATION.md) · [SUBMISSION_CHECKLIST](SUBMISSION_CHECKLIST.md)

---

## 1. Core Directives

1. **Deterministic Core Isolation (DR-DET-1):**
   Deterministic matching, scoring, and parsing pipelines must never depend on external network requests or AI availability. The application must achieve 100% test pass rates and functionality with `ai.enabled: false`.

2. **Data Provenance Enforcement (DR-PROV-1):**
   Every reported piece of data carries explicit provenance tags:
   - `EXTRACTED_RULE`: Extracted by deterministic regular expressions or taxonomy scanning.
   - `EXTRACTED_AI`: Extracted by LLM and confirmed via resume text substring grounding.
   - `COMPUTED`: Derived deterministically by business logic algorithms.
   - `AI_GENERATED`: Generated as an interpretation by LLM (never alters scores).

3. **Human Decision Making (DR-HUMAN-1):**
   The software provides decision support and never automated rejection. Scores and fit bands reflect keyword and qualification alignment with the submitted job specification, not candidate quality or employability.

4. **Layered Architectural Integrity (DR-ARCH-1):**
   Strict unidirectional dependencies are maintained across packages:
   `exceptions` $\leftarrow$ `config` $\leftarrow$ `models` $\leftarrow$ `skills` $\leftarrow$ `parsing` $\leftarrow$ `matching` $\leftarrow$ `scoring` $\leftarrow$ `ai` $\leftarrow$ `storage` $\leftarrow$ `reporting` $\leftarrow$ `services` $\leftarrow$ `ui`.
   Lower layers must never import higher layers.

5. **Security & Untrusted Input Sanitization (DR-SEC-1):**
   - Untrusted documents are sanitized and validated against decompression bomb limits and binary hazards before parsing.
   - Nonce boundaries isolate untrusted text in AI prompts.
   - Sensitive credentials and keys must never be logged or echoed in reports.

6. **Quality & Release Gates (DR-GATE-1):**
   - Zero `TODO`/`FIXME` markers allowed in production code.
   - All modules must maintain Average Cyclomatic Complexity $\le 5.0$ (Rank A).
   - Core packages must maintain $\ge 80\%$ test coverage.
   - Bandit and Ruff lint checks must pass with zero unresolved issues.

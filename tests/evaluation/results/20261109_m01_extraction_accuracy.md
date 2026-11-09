# M-01 Extraction Accuracy Evaluation Report (ET-01)

**Evaluation Date:** 2026-11-09  
**Specification:** [TESTING_STRATEGY §8.1](file:///d:/STARTUP/Resume%20Analyser/docs/TESTING_STRATEGY.md)  
**Dataset:** D1 (`tests/data/resumes/` and `tests/data/gold/`)  
**Sample Count:** 30 synthetic resumes (20 TXT, 5 DOCX, 5 PDF)  

---

## 1. Executive Summary

| Metric | Target | Actual Measured | Status |
|---|---|---|---|
| **Skills Extraction Accuracy (Micro Recall)** | $\ge 80.0\%$ | **98.24%** (167 / 170) | **EXCEEDED** |
| **Skills Precision** | $\ge 70.0\%$ | **86.98%** (167 / 192) | **EXCEEDED** |
| **Skills Micro F1 Score** | $\ge 75.0\%$ | **92.27%** | **EXCEEDED** |
| **Candidate Email Exact-Match Rate** | $\ge 85.0\%$ | **100.0%** (30 / 30) | **EXCEEDED** |
| **Candidate Name Exact-Match Rate** | $\ge 80.0\%$ | **100.0%** (30 / 30) | **EXCEEDED** |
| **Highest Education Exact-Match Rate** | $\ge 85.0\%$ | **96.67%** (29 / 30) | **EXCEEDED** |
| **Total Experience Years Match ($\pm 0.5$ yr)** | $\ge 75.0\%$ | **90.00%** (27 / 30) | **EXCEEDED** |

---

## 2. Format Distribution & Performance

- **TXT (20 resumes):** 100% extraction precision & recall on standardized headers.
- **DOCX (5 resumes):** 100% text recovery via WordprocessingML XML parser (`word/document.xml`).
- **PDF (5 resumes):** 96.4% recall on minimal/multi-line PDF streams.

---

## 3. Top Discrepancies & Taxonomy Findings

1. **False Positives (25 total):**
   - Natural language overlaps (e.g., words like `C`, `R` appearing in generic contexts).
   - Acronyms in project titles recognized as skills.
2. **False Negatives (3 total):**
   - Niche/compound domain terms absent from the core 325-skill seed taxonomy.
   - Mitigated via P1 AI extraction fallback and feedback ingestion loop (FR-29).

---

## 4. Caveats & Hardware

- **Hardware:** Intel x86_64, Windows 11, Python 3.14.0.
- **Scope:** Synthetic dataset covering realistic developer, data, QA, and cloud resumes.


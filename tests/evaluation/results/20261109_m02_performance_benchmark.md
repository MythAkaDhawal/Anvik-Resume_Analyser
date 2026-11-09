# M-02 Throughput & Latency Performance Benchmark Report (ET-04 / PT-01 / PT-02)

**Evaluation Date:** 2026-11-09  
**Specification:** [TESTING_STRATEGY §7.4](file:///d:/STARTUP/Resume%20Analyser/docs/TESTING_STRATEGY.md)  
**Corpus Size:** 100 resumes (replicated from D1 across TXT, DOCX, PDF)  
**Measured Iterations:** 1 warm-up pass + 5 measured passes (500 total analyses)  

---

## 1. System Environment

- **Operating System:** Windows 11 (AMD64)
- **CPU:** Intel64 Family 6 Model 142 Stepping 12 GenuineIntel
- **Python Version:** 3.14.0
- **AI Mode:** `ai.enabled = false` (100% deterministic pipeline)

---

## 2. Benchmark Results

| Metric | Target | Actual Measured | Status |
|---|---|---|---|
| **Deterministic Pipeline Throughput** | $\ge 20.0$ resumes/sec | **57.56 resumes/sec** (peak 74.29) | **EXCEEDED** |
| **Median Per-Resume Latency** | $\le 50.0$ ms | **5.66 ms** | **EXCEEDED** |
| **95th Percentile (p95) Latency** | $\le 100.0$ ms | **64.98 ms** | **EXCEEDED** |
| **SkillIndex Initialization Time (PT-01)** | $\le 0.50$ s | **0.0446 s** (44.6 ms) | **EXCEEDED** |
| **HTML Export Speed** | $\ge 100$ exports/sec | **1,140.54 exports/sec** | **EXCEEDED** |
| **PDF Export Speed** | $\ge 5$ exports/sec | **6.58 exports/sec** | **EXCEEDED** |
| **Excel Export Speed** | $\ge 5$ exports/sec | **5.75 exports/sec** | **EXCEEDED** |

---

## 3. Measured Throughput Across 5 Passes

1. **Pass 1:** 25.31 resumes/sec (initial disk cache population)
2. **Pass 2:** 60.31 resumes/sec
3. **Pass 3:** 62.32 resumes/sec
4. **Pass 4:** 74.29 resumes/sec
5. **Pass 5:** 65.56 resumes/sec
- **Overall Mean:** **57.56 resumes/second**

---

## 4. Observations

- Pre-compiled regex tokenizers and trie-indexed taxonomy matching in `SkillIndex` allow single-digit millisecond parse times (median 5.66 ms).
- Heavy formats (multi-stream PDFs and zipped DOCX archives) accounted for the p95 latency tail (64.98 ms).


# M-03 & M-04 Matching Precision, Recall & Ablation Report (ET-02)

**Evaluation Date:** 2026-11-09  
**Specification:** [TESTING_STRATEGY §8.2](file:///d:/STARTUP/Resume%20Analyser/docs/TESTING_STRATEGY.md)  
**Dataset:** D3 (`tests/data/labels/pairs.csv`)  
**Total Pairs Evaluated:** 180 (30 candidates $\times$ 6 jobs)  
**Split:** 60% Dev Split (108 pairs) / 40% Test Split (72 pairs, stratified by job)  

---

## 1. Inter-Annotator Agreement

- **Annotators:** 2 independent simulated annotators + adjudication
- **Cohen's Kappa ($\kappa$):** **1.00** (High alignment on requirements criteria)

---

## 2. Dev Split Threshold Sweep ($T \in [30..90]$, step 5)

| Threshold $T$ | TP | FP | FN | TN | Precision | Recall | F1 Score |
|---|---|---|---|---|---|---|---|
| 30.0 | 32 | 61 | 0 | 15 | 0.3441 | 1.0000 | 0.5120 |
| 40.0 | 32 | 29 | 0 | 47 | 0.5246 | 1.0000 | 0.6882 |
| 45.0 | 29 | 18 | 3 | 58 | 0.6170 | 0.9062 | 0.7342 |
| **50.0 (Frozen Best $T$)** | **28** | **9** | **4** | **67** | **0.7568** | **0.8750** | **0.8116** |
| 60.0 | 21 | 4 | 11 | 72 | 0.8400 | 0.6562 | 0.7368 |
| 70.0 | 16 | 2 | 16 | 74 | 0.8889 | 0.5000 | 0.6400 |
| 80.0 | 10 | 0 | 22 | 76 | 1.0000 | 0.3125 | 0.4762 |

- **Optimal Classification Threshold Selected on Dev:** $T = 50.0$

---

## 3. Test Set Evaluation ($N = 72$, at Frozen $T = 50.0$)

| Metric | Target | Actual Measured | 95% Bootstrap CI | Status |
|---|---|---|---|---|
| **Precision (M-03)** | $\ge 70.0\%$ | **94.74%** | $[83.33\%, 100.0\%]$ | **EXCEEDED** |
| **Recall (M-04)** | $\ge 70.0\%$ | **78.26%** | $[60.87\%, 92.59\%]$ | **EXCEEDED** |
| **F1 Score** | $\ge 70.0\%$ | **85.71%** | $[73.33\%, 95.24\%]$ | **EXCEEDED** |

### Test Confusion Matrix
- **True Positives (TP):** 18
- **False Positives (FP):** 1
- **False Negatives (FN):** 5
- **True Negatives (TN):** 48

---

## 4. Strategy Ablation: Weighted vs Basic

| Strategy | Precision | Recall | F1 Score | Outperforms? |
|---|---|---|---|---|
| **Weighted Scoring (`weighted`)** | **94.74%** | **78.26%** | **85.71%** | **YES (+13.49% F1)** |
| Basic Scoring (`basic`) | 100.0% | 56.52% | 72.22% | Baseline |

- **Conclusion:** The multi-component weighted strategy (`required_skills`, `experience`, `education`, `optional_skills`) significantly outperforms the unweighted baseline, reducing false negatives and achieving an F1 of 85.71%.


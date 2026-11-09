"""Evaluation test ET-02: Precision and Recall of Matching (M-03, M-04).

Evaluates deterministic matching engine against adjudicated human labels in tests/data/labels/pairs.csv (D3).
Performs:
1. Dev/test split (60% dev / 40% test stratified by job).
2. Threshold sweep on dev split (T in [30..90] step 5) to freeze optimal classification threshold T.
3. Test-set evaluation reporting Precision, Recall, F1, Confusion Matrix, and 95% bootstrap confidence intervals.
4. Strategy ablation comparing 'weighted' vs 'basic'.
5. Annotator agreement computation (Cohen's Kappa).
Saves results to tests/evaluation/results/et02_matching.json.
"""

from __future__ import annotations

import csv
import json
import math
import random
from datetime import date
from pathlib import Path

from resume_analyzer.config.settings import get_settings
from resume_analyzer.models.job import JobRequirements
from resume_analyzer.services.analysis_service import AnalysisOptions, AnalysisService

PAIRS_CSV = Path("tests/data/labels/pairs.csv")
JOBS_DIR = Path("tests/data/jobs")
GOLD_DIR = Path("tests/data/gold")
RESUMES_DIR = Path("tests/data/resumes")
RESULTS_DIR = Path("tests/evaluation/results")
REF_DATE = date(2024, 6, 1)


def cohen_kappa(ann1: list[str], ann2: list[str]) -> float:
    """Compute Cohen's Kappa inter-annotator agreement."""
    assert len(ann1) == len(ann2)
    n = len(ann1)
    if n == 0:
        return 0.0

    categories = sorted(list(set(ann1) | set(ann2)))
    # Observed agreement
    p_o = sum(1 for a, b in zip(ann1, ann2) if a == b) / n

    # Expected chance agreement
    p_e = 0.0
    for cat in categories:
        p1 = sum(1 for a in ann1 if a == cat) / n
        p2 = sum(1 for b in ann2 if b == cat) / n
        p_e += p1 * p2

    if math.isclose(p_e, 1.0):
        return 1.0
    return (p_o - p_e) / (1.0 - p_e)


def compute_metrics(actual: list[bool], pred: list[bool]) -> dict[str, float]:
    """Compute TP, FP, TN, FN, Precision, Recall, F1."""
    tp = sum(1 for a, p in zip(actual, pred) if a and p)
    fp = sum(1 for a, p in zip(actual, pred) if not a and p)
    fn = sum(1 for a, p in zip(actual, pred) if a and not p)
    tn = sum(1 for a, p in zip(actual, pred) if not a and not p)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def bootstrap_ci(
    actual: list[bool],
    pred: list[bool],
    n_resamples: int = 1000,
    seed: int = 42,
) -> dict[str, tuple[float, float]]:
    """Compute 95% bootstrap confidence intervals for precision, recall, and F1."""
    rng = random.Random(seed)
    n = len(actual)
    p_samples, r_samples, f1_samples = [], [], []

    for _ in range(n_resamples):
        indices = [rng.randint(0, n - 1) for _ in range(n)]
        b_act = [actual[i] for i in indices]
        b_pred = [pred[i] for i in indices]
        m = compute_metrics(b_act, b_pred)
        p_samples.append(m["precision"])
        r_samples.append(m["recall"])
        f1_samples.append(m["f1"])

    p_samples.sort()
    r_samples.sort()
    f1_samples.sort()

    lower_idx = int(0.025 * n_resamples)
    upper_idx = int(0.975 * n_resamples)

    return {
        "precision_ci95": (
            round(p_samples[lower_idx], 4),
            round(p_samples[upper_idx], 4),
        ),
        "recall_ci95": (round(r_samples[lower_idx], 4), round(r_samples[upper_idx], 4)),
        "f1_ci95": (round(f1_samples[lower_idx], 4), round(f1_samples[upper_idx], 4)),
    }


def test_et_02_matching_precision_recall_and_ablation() -> None:
    """ET-02: Run matching precision/recall evaluation against labelled benchmark pairs."""
    assert PAIRS_CSV.is_file(), f"Pairs dataset missing at {PAIRS_CSV}"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    service = AnalysisService()

    # Load all jobs
    jobs: dict[str, JobRequirements] = {}
    for jf in JOBS_DIR.glob("*.json"):
        raw = json.loads(jf.read_text(encoding="utf-8"))
        jobs[raw["job_id"]] = JobRequirements.model_validate(raw)

    # Load all candidate raw bytes and filenames
    resumes_cache: dict[str, tuple[str, bytes]] = {}
    for gf in GOLD_DIR.glob("cand_*.json"):
        gdata = json.loads(gf.read_text(encoding="utf-8"))
        cid = gdata["id"]
        fname = gdata["resume_filename"]
        rpath = RESUMES_DIR / fname
        resumes_cache[cid] = (fname, rpath.read_bytes())

    # Read pairs CSV
    rows = []
    with PAIRS_CSV.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    assert len(rows) >= 120, f"Expected at least 120 pairs, found {len(rows)}"

    # 1. Annotator agreement (Cohen's Kappa)
    ann1 = [r["annotator_1"] for r in rows]
    ann2 = [r["annotator_2"] for r in rows]
    kappa = cohen_kappa(ann1, ann2)

    # 2. Score all pairs with both 'weighted' and 'basic' strategies
    scored_pairs = []
    for row in rows:
        cid = row["resume_id"]
        jid = row["job_id"]
        adjudicated = row["adjudicated"] == "suitable"

        fname, rbytes = resumes_cache[cid]
        job = jobs[jid]

        # Analyze with weighted strategy
        rep_weighted = service.analyze(
            filename=fname,
            data=rbytes,
            job=job,
            options=AnalysisOptions(strategy="weighted", ai_enabled=False),
            reference_date=REF_DATE,
        )

        # Analyze with basic strategy
        rep_basic = service.analyze(
            filename=fname,
            data=rbytes,
            job=job,
            options=AnalysisOptions(strategy="basic", ai_enabled=False),
            reference_date=REF_DATE,
        )

        scored_pairs.append(
            {
                "candidate_id": cid,
                "job_id": jid,
                "actual_suitable": adjudicated,
                "score_weighted": rep_weighted.score.total_score,
                "score_basic": rep_basic.score.total_score,
            }
        )

    # 3. Stratified 60% Dev / 40% Test split by job_id
    rng = random.Random(42)
    by_job: dict[str, list[dict]] = {}
    for sp in scored_pairs:
        by_job.setdefault(sp["job_id"], []).append(sp)

    dev_pairs = []
    test_pairs = []
    for jid, plist in by_job.items():
        rng.shuffle(plist)
        n_dev = int(len(plist) * 0.60)
        dev_pairs.extend(plist[:n_dev])
        test_pairs.extend(plist[n_dev:])

    assert len(dev_pairs) > 0 and len(test_pairs) > 0

    # 4. Threshold sweep on Dev Split (T from 30 to 90, step 5) for 'weighted'
    sweep_results = []
    best_t = 60.0
    best_f1 = -1.0

    dev_actual = [p["actual_suitable"] for p in dev_pairs]
    for t in range(30, 95, 5):
        t_float = float(t)
        dev_pred = [p["score_weighted"] >= t_float for p in dev_pairs]
        m = compute_metrics(dev_actual, dev_pred)
        sweep_results.append({"threshold": t_float, **m})
        if m["f1"] > best_f1:
            best_f1 = m["f1"]
            best_t = t_float

    # 5. Evaluate on Test Split with Frozen Threshold best_t
    test_actual = [p["actual_suitable"] for p in test_pairs]
    test_pred_weighted = [p["score_weighted"] >= best_t for p in test_pairs]
    test_metrics_weighted = compute_metrics(test_actual, test_pred_weighted)
    ci95 = bootstrap_ci(test_actual, test_pred_weighted)

    # 6. Ablation: evaluate 'basic' strategy on Test Split at same best_t
    test_pred_basic = [p["score_basic"] >= best_t for p in test_pairs]
    test_metrics_basic = compute_metrics(test_actual, test_pred_basic)

    # Compile benchmark summary
    summary = {
        "evaluation_name": "ET-02 Matching Precision & Recall",
        "dataset_size": len(scored_pairs),
        "dev_split_size": len(dev_pairs),
        "test_split_size": len(test_pairs),
        "annotator_agreement_kappa": round(kappa, 4),
        "frozen_threshold": best_t,
        "dev_threshold_sweep": sweep_results,
        "test_evaluation_weighted": {
            **test_metrics_weighted,
            **ci95,
        },
        "test_evaluation_basic_ablation": test_metrics_basic,
        "comparison_weighted_vs_basic": {
            "weighted_f1": test_metrics_weighted["f1"],
            "basic_f1": test_metrics_basic["f1"],
            "weighted_beats_basic": test_metrics_weighted["f1"]
            >= test_metrics_basic["f1"],
        },
    }

    out_file = RESULTS_DIR / "et02_matching.json"
    out_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Assertions
    assert kappa >= 0.70, f"Annotator agreement Kappa ({kappa:.2f}) below 0.70"
    assert test_metrics_weighted["precision"] >= 0.65, (
        f"Precision ({test_metrics_weighted['precision']}) below 0.65"
    )
    assert test_metrics_weighted["recall"] >= 0.60, (
        f"Recall ({test_metrics_weighted['recall']}) below 0.60"
    )
    assert test_metrics_weighted["f1"] >= 0.65, (
        f"F1 score ({test_metrics_weighted['f1']}) below 0.65"
    )

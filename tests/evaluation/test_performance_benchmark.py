"""Evaluation test ET-04 / PT-01 / PT-02: Performance Benchmarking Procedure (TESTING_STRATEGY §7.4).

Measures:
1. PT-01: SkillIndex construction latency and taxonomy loading time.
2. PT-02 / ET-04: Full deterministic pipeline throughput (warmup + 5 measured passes over replicated 100+ file corpus).
   Calculates resumes/second, median latency, and p95 latency.
3. Export generation throughput per format (HTML, PDF, Excel).
Saves results to tests/evaluation/results/et04_benchmark.json.
"""

from __future__ import annotations

import json
import platform
import statistics
import sys
import time
from datetime import date
from pathlib import Path

from resume_analyzer.models.job import JobRequirements
from resume_analyzer.reporting.exporters.excel_exporter import ExcelExporter
from resume_analyzer.reporting.exporters.html_exporter import HTMLExporter
from resume_analyzer.reporting.exporters.pdf_exporter import PDFExporter
from resume_analyzer.services.analysis_service import AnalysisOptions, AnalysisService
from resume_analyzer.skills.skill_index import SkillIndex
from resume_analyzer.skills.taxonomy import SkillTaxonomy

RESUMES_DIR = Path("tests/data/resumes")
GOLD_DIR = Path("tests/data/gold")
RESULTS_DIR = Path("tests/evaluation/results")
TAXONOMY_PATH = Path("config/skills_taxonomy.json")


def test_et_04_performance_benchmark(tmp_path: Path) -> None:
    """ET-04: Execute deterministic throughput and latency benchmark."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Environment capture
    env_info = {
        "os": f"{platform.system()} {platform.release()}",
        "architecture": platform.machine(),
        "python_version": sys.version.split()[0],
        "processor": platform.processor(),
    }

    # 2. PT-01: SkillIndex build latency
    t0 = time.perf_counter()
    taxonomy = SkillTaxonomy.from_file(TAXONOMY_PATH)
    t_taxonomy_load = time.perf_counter() - t0

    t1 = time.perf_counter()
    skill_index = SkillIndex(taxonomy)
    t_index_build = time.perf_counter() - t1

    pt01_results = {
        "taxonomy_load_seconds": round(t_taxonomy_load, 4),
        "index_build_seconds": round(t_index_build, 4),
        "total_init_seconds": round(t_taxonomy_load + t_index_build, 4),
        "total_canonical_skills": len(taxonomy.skills),
    }

    # 3. Assemble replicated corpus (>= 100 files)
    sample_files = []
    for gf in GOLD_DIR.glob("cand_*.json"):
        data = json.loads(gf.read_text(encoding="utf-8"))
        fname = data["resume_filename"]
        fpath = RESUMES_DIR / fname
        if fpath.is_file():
            sample_files.append((fname, fpath.read_bytes()))

    assert len(sample_files) >= 15, "Insufficient base resume samples"

    # Replicate to at least 100 files
    corpus = []
    multiplier = (100 // len(sample_files)) + 1
    for i in range(multiplier):
        for orig_name, raw in sample_files:
            corpus.append((f"rep_{i}_{orig_name}", raw))
    corpus = corpus[:100]
    assert len(corpus) == 100

    # 4. Deterministic analysis setup
    service = AnalysisService(skill_index=skill_index)
    job = JobRequirements(
        job_title="Software Engineer",
        required_skills=["Python", "SQL", "Git"],
        optional_skills=["Docker", "AWS"],
        min_experience_years=2.0,
    )
    opts = AnalysisOptions(strategy="weighted", ai_enabled=False)
    ref_date = date(2024, 6, 1)

    # Warm-up pass (unmeasured)
    for name, data in corpus[:5]:
        service.analyze(name, data, job, options=opts, reference_date=ref_date)

    # 5 measured passes
    pass_durations = []
    pass_throughputs = []
    single_latencies = []
    sample_reports = []

    for pass_num in range(5):
        t_start = time.perf_counter()
        for name, data in corpus:
            t_single_start = time.perf_counter()
            rep = service.analyze(
                name, data, job, options=opts, reference_date=ref_date
            )
            single_latencies.append(time.perf_counter() - t_single_start)
            if pass_num == 0:
                sample_reports.append(rep)
        elapsed = time.perf_counter() - t_start
        pass_durations.append(elapsed)
        throughput = len(corpus) / elapsed if elapsed > 0 else 0
        pass_throughputs.append(throughput)

    avg_throughput = statistics.mean(pass_throughputs)
    median_latency_ms = statistics.median(single_latencies) * 1000.0
    sorted_latencies = sorted(single_latencies)
    p95_idx = int(0.95 * len(sorted_latencies))
    p95_latency_ms = sorted_latencies[p95_idx] * 1000.0

    # 5. Measure Export Speeds (HTML, PDF, Excel) across 20 reports
    html_exp = HTMLExporter()
    pdf_exp = PDFExporter()
    xlsx_exp = ExcelExporter()

    test_reps = sample_reports[:20]

    t_html_start = time.perf_counter()
    for r in test_reps:
        html_exp.export_bytes(r)
    html_duration = time.perf_counter() - t_html_start
    html_per_sec = len(test_reps) / html_duration if html_duration > 0 else 0

    t_pdf_start = time.perf_counter()
    for r in test_reps:
        pdf_exp.export_bytes(r)
    pdf_duration = time.perf_counter() - t_pdf_start
    pdf_per_sec = len(test_reps) / pdf_duration if pdf_duration > 0 else 0

    t_xlsx_start = time.perf_counter()
    for r in test_reps:
        xlsx_exp.export_bytes(r)
    xlsx_duration = time.perf_counter() - t_xlsx_start
    xlsx_per_sec = len(test_reps) / xlsx_duration if xlsx_duration > 0 else 0

    benchmark_summary = {
        "evaluation_name": "ET-04 / PT-01 / PT-02 Performance Benchmark",
        "environment": env_info,
        "corpus_size": len(corpus),
        "measured_passes": len(pass_throughputs),
        "pt01_skill_index_latency": pt01_results,
        "throughput_resumes_per_second": {
            "mean": round(avg_throughput, 2),
            "passes": [round(p, 2) for p in pass_throughputs],
        },
        "latency_milliseconds": {
            "median_ms": round(median_latency_ms, 2),
            "p95_ms": round(p95_latency_ms, 2),
        },
        "export_throughput_per_second": {
            "html": round(html_per_sec, 2),
            "pdf": round(pdf_per_sec, 2),
            "xlsx": round(xlsx_per_sec, 2),
        },
    }

    out_file = RESULTS_DIR / "et04_benchmark.json"
    out_file.write_text(json.dumps(benchmark_summary, indent=2), encoding="utf-8")

    # Assertions for performance targets
    assert avg_throughput >= 10.0, (
        f"Average throughput ({avg_throughput:.1f} res/s) below minimum 10 res/s"
    )
    assert median_latency_ms <= 100.0, (
        f"Median latency ({median_latency_ms:.1f}ms) above 100ms ceiling"
    )

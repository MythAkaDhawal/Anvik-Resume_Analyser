"""Command-line interface for the Intelligent Resume Analyzer (TECHNICAL_SPECIFICATION §15).

Implements single-resume analysis, isolated batch processing, throughput benchmarking,
and storage administration with standardized exit codes:
  0 = success
  1 = one or more files failed (batch)
  2 = invalid arguments / configuration
  3 = unexpected error
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections.abc import Sequence
from pathlib import Path

import yaml

from resume_analyzer.exceptions import (
    CorruptResultError,
    DataValidationError,
    InvalidIdentifierError,
    ResultNotFoundError,
    ResumeAnalyzerError,
)
from resume_analyzer.models.job import JobRequirements
from resume_analyzer.reporting.exporters.base import export_batch_workbook, get_exporter
from resume_analyzer.services.analysis_service import AnalysisOptions, AnalysisService
from resume_analyzer.services.batch_runner import BatchRunner
from resume_analyzer.storage.feedback_store import FeedbackStore
from resume_analyzer.storage.result_store import ResultStore

logger = logging.getLogger(__name__)


def load_job_file(path: Path | str) -> JobRequirements:
    """Load and validate JobRequirements from a JSON or YAML file."""
    p = Path(path)
    if not p.is_file():
        raise DataValidationError(f"Job file not found: '{p}'")

    raw = p.read_text(encoding="utf-8")
    try:
        # Try JSON first
        data = json.loads(raw)
    except Exception:
        try:
            data = yaml.safe_load(raw)
        except Exception as ye:
            raise DataValidationError(
                f"Job file '{p}' is not valid JSON or YAML: {ye}"
            ) from ye

    if not isinstance(data, dict):
        raise DataValidationError(f"Job file '{p}' must contain a key-value mapping.")

    try:
        return JobRequirements.model_validate(data)
    except Exception as e:
        raise DataValidationError(f"Invalid job requirements in '{p}': {e}") from e


def cmd_analyze(args: argparse.Namespace) -> int:
    """Execute single resume analysis command."""
    resume_path = Path(args.resume)
    if not resume_path.is_file():
        sys.stderr.write(f"Error: Resume file not found at '{resume_path}'\n")
        return 2

    try:
        job = load_job_file(args.job)
    except Exception as e:
        sys.stderr.write(f"Error loading job: {e}\n")
        return 2

    ai_enabled = args.ai.lower() == "on"
    opts = AnalysisOptions(
        strategy=args.strategy,
        ai_enabled=ai_enabled,
        ai_extract_candidate=ai_enabled,
        ai_categorize_skills=ai_enabled,
        ai_explain_match=ai_enabled,
        ai_recommendations=ai_enabled,
        ai_interview_questions=ai_enabled,
    )

    try:
        service = AnalysisService()
        resume_bytes = resume_path.read_bytes()
        report = service.analyze(
            filename=resume_path.name,
            data=resume_bytes,
            job=job,
            options=opts,
        )
    except ResumeAnalyzerError as e:
        sys.stderr.write(f"Analysis error [{e.error_code}]: {e.user_message or e}\n")
        return 2
    except Exception as e:
        logger.exception("Unexpected error analyzing %s", resume_path)
        sys.stderr.write(f"Unexpected error: {e}\n")
        return 3

    # Persist unless disabled
    if not args.no_save:
        try:
            store = ResultStore()
            store.save(report)
        except Exception as se:
            logger.warning("Failed to save report to storage: %s", se)

    # Output summary
    cand_name = report.candidate.name or "Anonymous"
    print("\n--- RESUME ANALYSIS SUMMARY ---")
    print(f"Candidate:       {cand_name}")
    print(f"Overall Score:   {report.score.total_score:.1f} / 100")
    print(f"Fit Band:        {report.score.fit_band.value}")
    print(f"Strategy:        {report.strategy_used}")
    print(
        f"Matched Skills:  {len(report.match.matched_skills)} / {len(job.required_skills)} required"
    )
    print(f"Missing Req:     {', '.join(report.match.missing_required) or 'None'}")
    exp_yrs = report.candidate.total_experience_years or 0.0
    print(f"Experience:      {exp_yrs:.1f} yrs ({report.match.experience_eval.status})")
    print(
        f"Education:       {report.candidate.highest_education_level.name} ({report.match.education_eval.status})"
    )
    print(f"Report ID:       {report.report_id}")
    print("--------------------------------\n")

    # Export if requested
    if args.format and args.output_dir:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for fmt in args.format:
            try:
                exporter = get_exporter(fmt)
                target_path = (
                    out_dir / f"report_{report.candidate.candidate_id}.{fmt.lower()}"
                )
                exporter.export_to_file(report, target_path)
                print(f"Exported {fmt.upper()} report to: {target_path}")
            except Exception as e:
                sys.stderr.write(f"Warning: Failed to export {fmt} report: {e}\n")

    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    """Execute batch analysis across a directory of resumes."""
    resumes_dir = Path(args.resumes_dir)
    if not resumes_dir.is_dir():
        sys.stderr.write(f"Error: Resumes directory not found at '{resumes_dir}'\n")
        return 2

    try:
        job = load_job_file(args.job)
    except Exception as e:
        sys.stderr.write(f"Error loading job: {e}\n")
        return 2

    # Discover candidate files
    valid_exts = {".pdf", ".docx", ".txt"}
    files_to_process = [
        p
        for p in resumes_dir.iterdir()
        if p.is_file() and p.suffix.lower() in valid_exts
    ]

    if not files_to_process:
        sys.stderr.write(
            f"Error: No resume files (.pdf, .docx, .txt) found in '{resumes_dir}'\n"
        )
        return 2

    ai_enabled = args.ai.lower() == "on"
    opts = AnalysisOptions(
        strategy=args.strategy,
        ai_enabled=ai_enabled,
        ai_extract_candidate=ai_enabled,
        ai_categorize_skills=ai_enabled,
        ai_explain_match=ai_enabled,
        ai_recommendations=ai_enabled,
        ai_interview_questions=ai_enabled,
    )

    # Progress bar setup using tqdm
    try:
        from tqdm import tqdm

        pbar = tqdm(total=len(files_to_process), desc="Screening resumes", unit="file")

        def progress_cb(done: int, total: int, current_file: str) -> None:
            pbar.update(1)
            pbar.set_postfix_str(current_file[:20])
    except ImportError:
        pbar = None

        def progress_cb(done: int, total: int, current_file: str) -> None:
            print(f"[{done}/{total}] Analyzed {current_file}")

    service = AnalysisService()
    runner = BatchRunner(analysis_service=service)

    result = runner.run_paths(
        files_to_process, job=job, options=opts, progress=progress_cb
    )

    if pbar is not None:
        pbar.close()

    # Print failures table if any
    if result.failures:
        print("\n--- BATCH FAILURES ---")
        print(f"{'Filename':<30} {'Error Code':<15} {'Reason'}")
        print("-" * 75)
        for f in result.failures:
            print(f"{f.display_name:<30} {f.error_code:<15} {f.user_message}")
        print("-" * 75)

    # Print ranked summary
    print("\n--- CANDIDATE RANKINGS ---")
    print(
        f"{'Rank':<5} {'Candidate Name':<25} {'Score':<8} {'Fit Band':<12} {'Matched Skills'}"
    )
    print("-" * 70)
    for idx, r in enumerate(result.reports, start=1):
        cname = r.candidate.name or "Anonymous"
        matched_cnt = f"{len(r.match.matched_skills)}/{len(job.required_skills)}"
        print(
            f"{idx:<5} {cname:<25} {r.score.total_score:<8.1f} {r.score.fit_band.value:<12} {matched_cnt}"
        )
    print("-" * 70)

    # Persist batch reports unless disabled
    if not getattr(args, "no_save", False):
        try:
            store = ResultStore()
            for r in result.reports:
                store.save(r)
        except Exception as se:
            logger.warning("Failed to save batch reports to storage: %s", se)

    # Export if requested
    if args.output_dir and result.reports:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        formats = args.format or ["xlsx"]
        if "xlsx" in formats:
            batch_xlsx_path = out_dir / "batch_ranking_summary.xlsx"
            batch_bytes = export_batch_workbook(result.reports)
            batch_xlsx_path.write_bytes(batch_bytes)
            print(f"Exported batch ranking workbook to: {batch_xlsx_path}")

        for fmt in formats:
            if fmt == "xlsx":
                continue
            try:
                exporter = get_exporter(fmt)
                for r in result.reports:
                    target = (
                        out_dir / f"report_{r.candidate.candidate_id}.{fmt.lower()}"
                    )
                    exporter.export_to_file(r, target)
            except Exception as e:
                sys.stderr.write(
                    f"Warning: Failed to export individual {fmt} reports: {e}\n"
                )

    # Exit code: 0 if no failures; 1 if one or more files failed
    return 1 if result.failures else 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    """Execute throughput benchmark on the deterministic parsing and matching pipeline (M-02)."""
    resumes_dir = Path(args.resumes_dir)
    if not resumes_dir.is_dir():
        sys.stderr.write(
            f"Error: Benchmark resumes directory not found: '{resumes_dir}'\n"
        )
        return 2

    valid_exts = {".pdf", ".docx", ".txt"}
    files = [
        p
        for p in resumes_dir.iterdir()
        if p.is_file() and p.suffix.lower() in valid_exts
    ]
    if not files:
        sys.stderr.write(f"Error: No resume files found in '{resumes_dir}'\n")
        return 2

    # Benchmark job
    bench_job = JobRequirements(
        title="Benchmark Software Engineer",
        required_skills=["Python", "SQL", "Git"],
        optional_skills=["Docker", "AWS"],
        min_experience_years=2.0,
    )

    runs = max(1, args.runs)
    service = AnalysisService()
    runner = BatchRunner(analysis_service=service)
    opts = AnalysisOptions(strategy="weighted", ai_enabled=False)

    print(
        f"\nRunning deterministic throughput benchmark ({runs} run(s) over {len(files)} resume(s))..."
    )
    latencies: list[float] = []

    for run_idx in range(1, runs + 1):
        start_t = time.perf_counter()
        res = runner.run_paths(files, job=bench_job, options=opts)
        elapsed = time.perf_counter() - start_t
        latencies.append(elapsed)
        throughput = len(files) / elapsed if elapsed > 0 else 0
        print(
            f"  Run {run_idx}: {elapsed:.3f}s ({throughput:.1f} resumes/sec, {len(res.reports)} parsed, {len(res.failures)} failures)"
        )

    avg_elapsed = sum(latencies) / len(latencies)
    avg_throughput = len(files) / avg_elapsed if avg_elapsed > 0 else 0
    print("\n--- BENCHMARK RESULTS ---")
    print(f"Total files:      {len(files)}")
    print(f"Average latency:  {avg_elapsed:.3f}s")
    print(f"Throughput:       {avg_throughput:.1f} resumes/second")
    print("-------------------------\n")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List saved analyses in storage."""
    store = ResultStore()
    summaries = store.list()
    if not summaries:
        print("No saved analyses found in data/results/.")
        return 0

    print(f"\nFound {len(summaries)} saved analyses in data/results/:")
    print(
        f"{'Report ID':<35} {'Candidate':<25} {'Score':<8} {'Fit Band':<10} {'Status'}"
    )
    print("-" * 90)
    for s in summaries:
        cand = s.candidate_name or "Anonymous"
        sc = f"{s.total_score:.1f}" if s.total_score is not None else "—"
        band = s.fit_band or "—"
        status = "OK" if s.readable else "UNREADABLE"
        print(f"{s.report_id:<35} {cand:<25} {sc:<8} {band:<10} {status}")
    print("-" * 90 + "\n")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Re-export a saved analysis report by ID."""
    report_id = args.id
    store = ResultStore()
    try:
        report = store.load(report_id)
    except (ResultNotFoundError, InvalidIdentifierError) as e:
        sys.stderr.write(f"Error: {e}\n")
        return 2
    except CorruptResultError as e:
        sys.stderr.write(f"Error: Saved report is corrupt: {e}\n")
        return 3

    try:
        out_dir = Path(args.output_dir or ".")
        out_dir.mkdir(parents=True, exist_ok=True)
        exporter = get_exporter(args.format)
        out_path = out_dir / f"report_{report_id}.{args.format.lower()}"
        exporter.export_to_file(report, out_path)
        print(f"Exported report to: {out_path}")
        return 0
    except Exception as e:
        sys.stderr.write(f"Export failed: {e}\n")
        return 3


def cmd_purge(args: argparse.Namespace) -> int:
    """Delete analyses older than specified days."""
    days = args.days
    store = ResultStore()
    if not args.yes:
        confirm = input(
            f"Are you sure you want to purge analyses older than {days} days? [y/N]: "
        )
        if confirm.strip().lower() != "y":
            print("Purge cancelled.")
            return 0

    deleted = store.purge_older_than(days)
    print(f"Successfully purged {deleted} analysis record(s) older than {days} day(s).")
    return 0


def cmd_feedback_summary(args: argparse.Namespace) -> int:
    """Print aggregated feedback metrics."""
    store = FeedbackStore()
    summary = store.summarize()
    if summary.total_submissions == 0:
        print("No user feedback records recorded yet (data/feedback.jsonl).")
        return 0

    print("\n--- FEEDBACK SUMMARY ---")
    print(f"Total Feedback Submissions: {summary.total_submissions}")
    print(f"Average Star Rating:        {summary.average_rating:.2f} / 5.00")
    if summary.section_positive_ratios:
        print("\nSection Positive Ratios:")
        for sec, ratio in summary.section_positive_ratios.items():
            print(f"  • {sec:<20} {ratio * 100:.1f}%")
    if summary.top_corrected_skills:
        print("\nTop Corrected Skills:")
        for sk, count in summary.top_corrected_skills:
            print(f"  • {sk:<20} ({count} times)")
    print("------------------------\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="resume-analyzer",
        description="Intelligent Resume Analyzer CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # analyze
    p_analyze = subparsers.add_parser(
        "analyze", help="Analyze a single resume against a job"
    )
    p_analyze.add_argument(
        "--resume", required=True, help="Path to resume file (.pdf, .docx, .txt)"
    )
    p_analyze.add_argument(
        "--job", required=True, help="Path to job requirements JSON/YAML file"
    )
    p_analyze.add_argument(
        "--strategy",
        choices=["weighted", "basic"],
        default="weighted",
        help="Scoring strategy",
    )
    p_analyze.add_argument(
        "--ai", choices=["on", "off"], default="off", help="Enable AI features"
    )
    p_analyze.add_argument(
        "--format",
        nargs="+",
        choices=["html", "pdf", "xlsx"],
        help="Report export format(s)",
    )
    p_analyze.add_argument("--output-dir", help="Directory to save exported reports")
    p_analyze.add_argument(
        "--no-save", action="store_true", help="Do not persist result to disk"
    )

    # batch
    p_batch = subparsers.add_parser(
        "batch", help="Batch analyze resumes in a directory"
    )
    p_batch.add_argument(
        "--resumes-dir", required=True, help="Directory containing resumes"
    )
    p_batch.add_argument(
        "--job", required=True, help="Path to job requirements JSON/YAML file"
    )
    p_batch.add_argument(
        "--strategy",
        choices=["weighted", "basic"],
        default="weighted",
        help="Scoring strategy",
    )
    p_batch.add_argument(
        "--ai", choices=["on", "off"], default="off", help="Enable AI features"
    )
    p_batch.add_argument("--output-dir", help="Directory to save exported reports")
    p_batch.add_argument(
        "--format",
        nargs="+",
        choices=["xlsx", "html", "pdf"],
        default=["xlsx"],
        help="Export formats",
    )
    p_batch.add_argument("--workers", type=int, default=1, help="Worker count")
    p_batch.add_argument(
        "--no-save", action="store_true", help="Do not persist results to disk"
    )

    # benchmark
    p_bench = subparsers.add_parser(
        "benchmark", help="Measure deterministic throughput (M-02)"
    )
    p_bench.add_argument(
        "--resumes-dir", required=True, help="Directory containing resumes"
    )
    p_bench.add_argument("--runs", type=int, default=3, help="Number of benchmark runs")

    # list
    subparsers.add_parser("list", help="List saved analyses")

    # export
    p_exp = subparsers.add_parser("export", help="Re-export saved analysis")
    p_exp.add_argument("--id", required=True, help="Report ID to export")
    p_exp.add_argument(
        "--format",
        choices=["html", "pdf", "xlsx"],
        default="html",
        help="Export format",
    )
    p_exp.add_argument("--output-dir", default=".", help="Output directory")

    # purge
    p_purge = subparsers.add_parser("purge", help="Delete analyses older than N days")
    p_purge.add_argument("--days", type=int, default=30, help="Age in days to purge")
    p_purge.add_argument("--yes", action="store_true", help="Skip confirmation prompt")

    # feedback-summary
    subparsers.add_parser("feedback-summary", help="Print aggregated user feedback")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI main execution dispatcher."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as se:
        return 2 if se.code != 0 else 0

    commands = {
        "analyze": cmd_analyze,
        "batch": cmd_batch,
        "benchmark": cmd_benchmark,
        "list": cmd_list,
        "export": cmd_export,
        "purge": cmd_purge,
        "feedback-summary": cmd_feedback_summary,
    }

    handler = commands.get(args.command)
    if not handler:
        sys.stderr.write(f"Unknown command '{args.command}'\n")
        return 2

    try:
        return handler(args)
    except Exception as e:
        logger.exception("CLI execution failed: %s", e)
        sys.stderr.write(f"Unexpected error: {e}\n")
        return 3


if __name__ == "__main__":
    sys.exit(main())

"""Evaluation test ET-01: Baseline Extraction Accuracy against synthetic gold dataset.

Evaluates ResumeParser extraction against gold annotations in tests/data/gold/.
Computes micro-averaged precision, recall (extraction accuracy), and F1 for skills,
as well as exact-match rates for candidate name, email, education level, and experience years.
Saves honest baseline evaluation measurements to tests/evaluation/results/et01_baseline.json.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from resume_analyzer.config.settings import get_settings
from resume_analyzer.ingestion.file_loader import load_resume
from resume_analyzer.parsing.resume_parser import ResumeParser
from resume_analyzer.skills.skill_index import SkillIndex
from resume_analyzer.skills.taxonomy import SkillTaxonomy

GOLD_DIR = Path("tests/data/gold")
RESUMES_DIR = Path("tests/data/resumes")
RESULTS_DIR = Path("tests/evaluation/results")
REF_DATE = date(2024, 6, 1)


@pytest.fixture(scope="module")
def parser() -> ResumeParser:
    tax = SkillTaxonomy.from_file("config/skills_taxonomy.json")
    index = SkillIndex(tax)
    return ResumeParser(index)


def test_et_01_baseline_extraction_accuracy(parser: ResumeParser):
    """ET-01: Run extraction benchmark against gold dataset and persist results."""
    gold_files = sorted(GOLD_DIR.glob("*.json"))
    assert len(gold_files) >= 15, (
        f"Expected at least 15 gold files, found {len(gold_files)}"
    )

    settings = get_settings()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    total_tp = 0
    total_fp = 0
    total_fn = 0

    email_matches = 0
    name_matches = 0
    edu_matches = 0
    exp_matches = 0

    detailed_results = []
    format_counts: dict[str, int] = {}

    for gf in gold_files:
        gold = json.loads(gf.read_text(encoding="utf-8"))
        res_file = RESUMES_DIR / gold["resume_filename"]
        assert res_file.exists(), (
            f"Resume file {res_file} missing for gold annotation {gf}"
        )

        ext = res_file.suffix.lower().lstrip(".")
        format_counts[ext] = format_counts.get(ext, 0) + 1

        content = res_file.read_bytes()
        loaded = load_resume(gold["resume_filename"], content, settings=settings.files)
        cand = parser.parse(loaded, reference_date=REF_DATE)

        # 1. Skills evaluation
        extracted_skills = {
            s.canonical_name.lower() if s.canonical_name else s.name.lower()
            for s in cand.skills
        }
        gold_skills = {s.lower() for s in gold.get("skills", [])}

        tp = len(extracted_skills & gold_skills)
        fp = len(extracted_skills - gold_skills)
        fn = len(gold_skills - extracted_skills)

        total_tp += tp
        total_fp += fp
        total_fn += fn

        # 2. Email evaluation
        gold_email = gold.get("email")
        extracted_email = cand.email
        email_match = False
        if gold_email is None and extracted_email is None:
            email_match = True
        elif (
            gold_email
            and extracted_email
            and gold_email.lower() == extracted_email.lower()
        ):
            email_match = True
        if email_match:
            email_matches += 1

        # 3. Name evaluation
        gold_name = gold.get("name")
        extracted_name = cand.name
        name_match = False
        if gold_name is None and extracted_name is None:
            name_match = True
        elif (
            gold_name and extracted_name and gold_name.lower() == extracted_name.lower()
        ):
            name_match = True
        if name_match:
            name_matches += 1

        # 4. Highest Education level evaluation
        gold_edu = gold.get("highest_education_level")
        extracted_edu = cand.highest_education_level.name
        edu_match = gold_edu == extracted_edu
        if edu_match:
            edu_matches += 1

        # 5. Experience years evaluation (+/- 0.5 year tolerance)
        gold_exp = gold.get("total_experience_years")
        extracted_exp = cand.total_experience_years
        exp_match = False
        if gold_exp is None and extracted_exp is None:
            exp_match = True
        elif gold_exp is not None and extracted_exp is not None:
            if abs(gold_exp - extracted_exp) <= 0.5:
                exp_match = True
        if exp_match:
            exp_matches += 1

        detailed_results.append(
            {
                "id": gold["id"],
                "filename": gold["resume_filename"],
                "format": ext,
                "skills": {
                    "gold_count": len(gold_skills),
                    "extracted_count": len(extracted_skills),
                    "tp": tp,
                    "fp": fp,
                    "fn": fn,
                },
                "email_match": email_match,
                "name_match": name_match,
                "education_match": edu_match,
                "experience_match": exp_match,
                "extracted_exp": extracted_exp,
                "gold_exp": gold_exp,
            }
        )

    n_samples = len(gold_files)
    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    benchmark_summary = {
        "evaluation_name": "ET-01 Baseline Extraction Accuracy",
        "sample_count": n_samples,
        "format_distribution": format_counts,
        "skills_micro_metrics": {
            "tp": total_tp,
            "fp": total_fp,
            "fn": total_fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        },
        "exact_match_rates": {
            "email_accuracy": round(email_matches / n_samples, 4),
            "name_accuracy": round(name_matches / n_samples, 4),
            "education_accuracy": round(edu_matches / n_samples, 4),
            "experience_accuracy": round(exp_matches / n_samples, 4),
        },
        "detailed": detailed_results,
    }

    out_path = RESULTS_DIR / "et01_baseline.json"
    out_path.write_text(json.dumps(benchmark_summary, indent=2), encoding="utf-8")

    # Assertions for baseline accuracy criteria
    assert recall >= 0.75, (
        f"Extraction recall ({recall:.3f}) below 0.75 baseline target"
    )
    assert precision >= 0.70, (
        f"Extraction precision ({precision:.3f}) below 0.70 baseline target"
    )
    assert email_matches / n_samples >= 0.85, "Email extraction accuracy below 85%"
    assert edu_matches / n_samples >= 0.85, "Education extraction accuracy below 85%"

# USER_GUIDE.md — User Operation & Application Guide

Related: [PROJECT_REQUIREMENTS](PROJECT_REQUIREMENTS.md) · [SYSTEM_ARCHITECTURE](SYSTEM_ARCHITECTURE.md) · [TECHNICAL_SPECIFICATION](TECHNICAL_SPECIFICATION.md) · [CONFIGURATION_AND_SECURITY](CONFIGURATION_AND_SECURITY.md)

---

## 1. Introduction

The Intelligent Resume Analyzer is an AI-powered smart hiring assistant designed to assist hiring managers and recruiters in evaluating candidate resumes against open job specifications.

The application offers two interfaces:
1. **Streamlit Web Application:** Interactive 4-step wizard for screening, ranking, deep-dive analysis, and downloading reports.
2. **Command-Line Interface (CLI):** Scriptable utility for headless batch evaluations, benchmark runs, storage purges, and automated exports.

---

## 2. Streamlit Web Application

To launch the web user interface:

```bash
streamlit run src/resume_analyzer/ui/streamlit_app.py
```

The browser opens at `http://localhost:8501`.

### Step 1: Job Specification
1. Enter the **Job Title** (e.g. `Senior Python Developer`).
2. Specify mandatory **Required Skills** (comma-separated or list).
3. Specify optional **Nice-to-Have Skills** and **Preferred Academic Fields**.
4. Set minimum requirements for **Years of Experience** and **Education Level**.
5. Alternatively, click **Load Sample Job** to populate presets (`Junior Data Analyst`, `ML Engineer`, `Senior Python Developer`).

### Step 2: Upload Resumes
1. Drag and drop candidate resumes (`.pdf`, `.docx`, `.txt`).
2. Adjust analysis settings (e.g., enable/disable AI insights, choose scoring strategy).
3. Click **Run Analysis**. A progress bar tracks document ingestion and parsing.

### Step 3: Screening Results & Candidate Ranking
1. View candidates ranked by overall compatibility score (0–100) and fit band:
   - **Strong Match** (85.0 – 100.0)
   - **Moderate Match** (65.0 – 84.9)
   - **Potential Match** (45.0 – 64.9)
   - **Limited Match** (0.0 – 44.9)
2. Select a candidate to inspect the breakdown:
   - **Skills Alignment:** Matched required/optional skills, match types (EXACT, ALIAS, FUZZY), missing skills.
   - **Experience & Education:** Chronological timeline, detected total tenure, highest degree level.
   - **AI Insights:** Grounded explanation of strengths and gaps, interview questions, and improvement suggestions.
   - **Feedback Widget:** Submit thumbs-up/down ratings and corrections to refine taxonomy matching.

### Step 4: Export Reports
Download evaluation artifacts:
- **Individual HTML Report:** Standalone web report with styled breakdown and badges.
- **Individual PDF Report:** Multi-page printable dossier formatted with ReportLab.
- **Batch Excel Workbook:** Multi-tab `.xlsx` file summarizing all candidate scores, skills matrices, and AI evaluations.

---

## 3. Command-Line Interface (CLI)

The CLI is available via `resume-analyzer` or `python -m resume_analyzer.cli`.

### 3.1 Single Resume Analysis
```bash
python -m resume_analyzer.cli analyze \
    --resume samples/resumes/cand_01_asha_verma.txt \
    --job samples/jobs/senior_python_developer.json \
    --strategy weighted \
    --no-ai \
    --output samples/outputs/asha_verma.json
```

### 3.2 Batch Processing
```bash
python -m resume_analyzer.cli batch \
    --resumes-dir tests/data/resumes \
    --job samples/jobs/senior_python_developer.json \
    --output-dir data/reports \
    --format html pdf xlsx
```

### 3.3 Running Benchmarks
```bash
python -m resume_analyzer.cli benchmark \
    --dataset tests/data/benchmark_corpus \
    --passes 5
```

### 3.4 History & Persistence Management
```bash
# List saved screening records
python -m resume_analyzer.cli list

# Export saved report by ID
python -m resume_analyzer.cli export --report-id 0123456789ab --format pdf

# Review recruiter feedback
python -m resume_analyzer.cli feedback-summary

# Purge reports older than 30 days
python -m resume_analyzer.cli purge --older-than-days 30
```

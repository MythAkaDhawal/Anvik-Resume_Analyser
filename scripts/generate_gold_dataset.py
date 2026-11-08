"""Generate >= 15 synthetic resumes and gold annotations for parsing verification (ET-01)."""

from __future__ import annotations

import json
from pathlib import Path

resumes_dir = Path("tests/data/resumes")
gold_dir = Path("tests/data/gold")
resumes_dir.mkdir(parents=True, exist_ok=True)
gold_dir.mkdir(parents=True, exist_ok=True)

PROFILES = [
    {
        "id": "cand_01_asha_verma",
        "filename": "cand_01_asha_verma.txt",
        "name": "Asha Verma",
        "email": "asha.verma@example.com",
        "skills": ["Python", "SQL", "Pandas", "Tableau", "Docker", "AWS"],
        "total_experience_years": 2.2,
        "highest_education_level": "BACHELOR",
        "text": """Asha Verma
Email: asha.verma@example.com
Phone: (555) 234-5678
San Francisco, CA

SUMMARY
Enthusiastic Junior Data Analyst with 2 years of experience in Python, SQL, and data reporting.

SKILLS
Programming: Python, SQL, Pandas, Tableau, Docker, AWS

EXPERIENCE
Data Analyst Intern at DataCorp Inc
June 2023 - Present
- Created analytics dashboards using Tableau and SQL.
- Containerized workflows using Docker and AWS.

Junior Analyst | Alpha Solutions
January 2022 - May 2023
- Analyzed business performance using Python and Pandas.

EDUCATION
Bachelor of Science in Computer Science
State University, 2022
""",
    },
    {
        "id": "cand_02_marcus_chen",
        "filename": "cand_02_marcus_chen.txt",
        "name": "Marcus Chen",
        "email": "marcus.chen@example.org",
        "skills": ["Go", "Docker", "Kubernetes", "PostgreSQL", "Redis", "gRPC"],
        "total_experience_years": 4.5,
        "highest_education_level": "MASTER",
        "text": """Marcus Chen
marcus.chen@example.org
Seattle, WA

PROFESSIONAL SUMMARY
Senior Backend Engineer with 4+ years architecting microservices with Go and Kubernetes.

TECHNICAL SKILLS
Go, Docker, Kubernetes, PostgreSQL, Redis, gRPC, Linux

WORK EXPERIENCE
Senior Backend Engineer @ CloudScale Technologies
March 2021 - Present
- Architected Go microservices processing 10k req/sec.
- Managed PostgreSQL and Redis persistence tiers.

Software Engineer at MicroSys
September 2019 - February 2021
- Deployed distributed container clusters using Docker and Kubernetes.

EDUCATION
Master of Science in Software Engineering
University of Washington
""",
    },
    {
        "id": "cand_03_sarah_connor",
        "filename": "cand_03_sarah_connor.txt",
        "name": "Sarah Connor",
        "email": "sconnor@cyberdyne.net",
        "skills": ["AWS", "Terraform", "Ansible", "Linux", "Python", "CI/CD"],
        "total_experience_years": 5.0,
        "highest_education_level": "BACHELOR",
        "text": """Sarah Connor
sconnor@cyberdyne.net | Austin, TX

SUMMARY
Cloud Architect and Infrastructure Lead specializing in AWS and Terraform automation.

CORE COMPETENCIES
AWS, Terraform, Ansible, Linux, Python, CI/CD, Git

PROFESSIONAL EXPERIENCE
Lead Cloud Architect | Cyberdyne Systems
January 2021 - Present
- Built multi-region AWS cloud infrastructure using Terraform.
- Automated system configurations via Ansible and Linux shell scripts.

DevOps Engineer at SkyNet Global
January 2019 - December 2020
- Built automated CI/CD deployment pipelines using Python and Git.

ACADEMIC BACKGROUND
Bachelor of Technology in Information Technology
Austin Institute of Technology
""",
    },
    {
        "id": "cand_04_elena_rostova",
        "filename": "cand_04_elena_rostova.txt",
        "name": "Elena Rostova",
        "email": "elena.rostova@ai-lab.io",
        "skills": ["Python", "PyTorch", "TensorFlow", "Scikit-Learn", "Machine Learning", "Deep Learning"],
        "total_experience_years": 3.0,
        "highest_education_level": "DOCTORATE",
        "text": """Elena Rostova
elena.rostova@ai-lab.io
New York, NY

OBJECTIVE
Machine Learning Researcher specializing in deep learning, neural networks, and computer vision.

SKILLS
Python, PyTorch, TensorFlow, Scikit-Learn, Machine Learning, Deep Learning

EXPERIENCE
Machine Learning Scientist at VisionAI Labs
June 2021 - Present
- Developed deep learning models with PyTorch and TensorFlow for computer vision.

Research Assistant at NYU AI Center
June 2020 - May 2021
- Applied machine learning algorithms using Scikit-Learn and Python.

EDUCATION
PhD in Computer Science
New York University
""",
    },
    {
        "id": "cand_05_david_kim",
        "filename": "cand_05_david_kim.txt",
        "name": "David Kim",
        "email": "david.kim@webdev.com",
        "skills": ["JavaScript", "TypeScript", "React", "Node.js", "MongoDB", "Express.js"],
        "total_experience_years": 3.5,
        "highest_education_level": "BACHELOR",
        "text": """David Kim
david.kim@webdev.com
San Jose, CA

PROFILE
Full Stack Developer proficient in React, Node.js, and TypeScript.

TECHNICAL SKILLS
Languages: JavaScript, TypeScript
Web: React, Node.js, Express.js, MongoDB, HTML, CSS

EXPERIENCE
Full Stack Developer | Nexa Web Studio
October 2021 - Present
- Developed scalable React and Node.js applications with MongoDB.

Frontend Developer at PixelWorks
May 2020 - September 2021
- Created dynamic user interfaces using TypeScript and React.

EDUCATION
Bachelor of Science in Computer Science
San Jose State University
""",
    },
    {
        "id": "cand_06_fatima_mansoor",
        "filename": "cand_06_fatima_mansoor.txt",
        "name": "Fatima Mansoor",
        "email": "fatima.mansoor@devops.org",
        "skills": ["Kubernetes", "Docker", "Jenkins", "Ansible", "Linux", "Git"],
        "total_experience_years": 4.0,
        "highest_education_level": "BACHELOR",
        "text": """Fatima Mansoor
fatima.mansoor@devops.org
Chicago, IL

SUMMARY
DevOps Engineer experienced in continuous delivery, Kubernetes cluster administration, and automated configuration.

SKILLS
Kubernetes, Docker, Jenkins, Ansible, Linux, Git, Bash

WORK HISTORY
DevOps Engineer at Midwest Logistics
January 2022 - Present
- Maintained production Kubernetes clusters and Docker containers.
- Orchestrated automated Jenkins builds.

Systems Administrator at Chicago Data Corp
January 2020 - December 2021
- Automated server provisioning with Ansible and Linux shell scripts.

EDUCATION
Bachelor of Engineering in Computer Engineering
University of Illinois
""",
    },
    {
        "id": "cand_07_alex_morgan",
        "filename": "cand_07_alex_morgan.txt",
        "name": "Alex Morgan",
        "email": "alex.morgan@dataflow.io",
        "skills": ["Python", "SQL", "Apache Spark", "Apache Kafka", "Snowflake", "Apache Airflow"],
        "total_experience_years": 3.7,
        "highest_education_level": "MASTER",
        "text": """Alex Morgan
alex.morgan@dataflow.io
Denver, CO

PROFESSIONAL SUMMARY
Data Engineer skilled in large-scale batch and streaming pipeline architectures.

KEY SKILLS
Python, SQL, Apache Spark, Apache Kafka, Snowflake, Apache Airflow

EXPERIENCE
Senior Data Engineer | DataFlow Systems
August 2022 - Present
- Engineered high-throughput streaming pipelines using Apache Kafka and Apache Spark.
- Automated daily orchestrations using Apache Airflow into Snowflake data warehouse.

Data Engineer at Apex Analytics
May 2020 - July 2022
- Maintained dimensional data models in Snowflake using Python and SQL.

EDUCATION
Master of Science in Data Science
University of Colorado
""",
    },
    {
        "id": "cand_08_rajesh_sharma",
        "filename": "cand_08_rajesh_sharma.txt",
        "name": "Rajesh Sharma",
        "email": "rajesh.sharma@mobileapps.in",
        "skills": ["Kotlin", "Java", "Swift", "RESTful APIs", "Git"],
        "total_experience_years": 4.2,
        "highest_education_level": "BACHELOR",
        "text": """Rajesh Sharma
rajesh.sharma@mobileapps.in
Bangalore, India

SUMMARY
Mobile Application Developer experienced in building native Android and iOS applications.

TECHNICAL PROFICIENCIES
Kotlin, Java, Swift, RESTful APIs, Git

EXPERIENCE
Lead Android Developer at AppVantage Technologies
July 2021 - Present
- Designed native mobile apps using Kotlin and Java.
- Integrated backend services through RESTful APIs.

Mobile Developer at InnoApps India
January 2020 - June 2021
- Maintained Swift and Java mobile codebases.

EDUCATION
Bachelor of Technology in Computer Science
Visvesvaraya Technological University
""",
    },
    {
        "id": "cand_09_clara_schmidt",
        "filename": "cand_09_clara_schmidt.txt",
        "name": "Clara Schmidt",
        "email": "clara.schmidt@frontend.de",
        "skills": ["Vue.js", "JavaScript", "HTML", "CSS", "Tailwind CSS", "Figma"],
        "total_experience_years": 2.5,
        "highest_education_level": "BACHELOR",
        "text": """Clara Schmidt
clara.schmidt@frontend.de
Berlin, Germany

CAREER SUMMARY
Frontend Engineer passionate about design systems, accessible UI, and Vue.js architecture.

SKILLS
Vue.js, JavaScript, HTML, CSS, Tailwind CSS, Figma

WORK EXPERIENCE
Frontend Engineer @ DesignCraft Digital
January 2023 - Present
- Implemented responsive web components using Vue.js and Tailwind CSS.
- Translated UI mockups from Figma into pixel-perfect web interfaces.

Junior Web Developer at Studio Berlin
June 2021 - December 2022
- Built interactive websites using HTML, CSS, and JavaScript.

EDUCATION
Bachelor of Science in Digital Media
Technical University of Berlin
""",
    },
    {
        "id": "cand_10_james_wilson",
        "filename": "cand_10_james_wilson.txt",
        "name": "James Wilson",
        "email": "jwilson@dbadmin.com",
        "skills": ["PostgreSQL", "MySQL", "Oracle Database", "Redis", "SQL"],
        "total_experience_years": 5.0,
        "highest_education_level": "BACHELOR",
        "text": """James Wilson
jwilson@dbadmin.com
Dallas, TX

SUMMARY
Database Administrator with extensive background in high availability, query optimization, and disaster recovery.

SKILLS
PostgreSQL, MySQL, Oracle Database, Redis, SQL, Linux

EXPERIENCE
Database Administrator at Enterprise Data Corp
January 2021 - Present
- Administered high-concurrency PostgreSQL and MySQL database clusters.
- Configured in-memory caching with Redis.

Database Analyst at First Financial
January 2019 - December 2020
- Tuned complex SQL queries on Oracle Database systems.

EDUCATION
Bachelor of Science in Information Systems
University of Texas at Dallas
""",
    },
    {
        "id": "cand_11_priya_patel",
        "filename": "cand_11_priya_patel.txt",
        "name": "Priya Patel",
        "email": "priya.patel@qatech.com",
        "skills": ["Selenium", "Pytest", "Python", "Git", "Jira"],
        "total_experience_years": 2.8,
        "highest_education_level": "BACHELOR",
        "text": """Priya Patel
priya.patel@qatech.com
Atlanta, GA

SUMMARY
Quality Assurance Engineer skilled in building automated test suites with Python and Selenium.

SKILLS
Selenium, Pytest, Python, Git, Jira

WORK EXPERIENCE
Software QA Engineer | QualiTech Solutions
August 2022 - Present
- Developed end-to-end regression test suites with Selenium and Pytest.
- Managed bug tracking workflows in Jira.

QA Analyst at Alpha Software
January 2021 - July 2022
- Executed automated and exploratory test scripts using Python.

EDUCATION
Bachelor of Science in Computer Science
Georgia Institute of Technology
""",
    },
    {
        "id": "cand_12_lucas_silva",
        "filename": "cand_12_lucas_silva.txt",
        "name": "Lucas Silva",
        "email": "lucas.silva@security.io",
        "skills": ["Cybersecurity", "Linux", "Python", "Network Security"],
        "total_experience_years": 3.0,
        "highest_education_level": "DIPLOMA",
        "text": """Lucas Silva
lucas.silva@security.io
Miami, FL

SUMMARY
Information Security Analyst skilled in threat detection, vulnerability analysis, and network hardening.

KEY SKILLS
Cybersecurity, Linux, Python, Network Security, Bash

EXPERIENCE
Security Analyst at Shield Security Systems
May 2022 - Present
- Monitored network security telemetry and responded to security incidents.
- Developed threat hunting scripts in Python and Bash.

IT Support Specialist at Miami Tech
May 2020 - April 2022
- Administered Linux servers and enforced network security policies.

EDUCATION
Associate Degree in Cyber Security
Miami Dade College
""",
    },
    {
        "id": "cand_13_ananya_iyer",
        "filename": "cand_13_ananya_iyer.txt",
        "name": "Ananya Iyer",
        "email": "ananya.iyer@analytics.com",
        "skills": ["Power BI", "SQL", "Excel", "Tableau", "Business Intelligence"],
        "total_experience_years": 3.5,
        "highest_education_level": "MASTER",
        "text": """Ananya Iyer
ananya.iyer@analytics.com
Boston, MA

PROFESSIONAL SUMMARY
Business Intelligence Analyst specializing in executive dashboards, SQL modeling, and KPI tracking.

SKILLS
Power BI, SQL, Excel, Tableau, Business Intelligence

WORK EXPERIENCE
BI Analyst at Global Insights Consulting
March 2022 - Present
- Designed executive dashboards in Power BI and Tableau.
- Crafted complex SQL queries to model financial metrics.

Junior Analyst at Boston Analytics
October 2019 - February 2022
- Conducted variance analysis in Excel and SQL.

EDUCATION
Master of Science in Business Analytics
Boston University
""",
    },
    {
        "id": "cand_14_minimal_candidate",
        "filename": "cand_14_minimal_candidate.txt",
        "name": "Jean-Luc O'Neil",
        "email": "jl.oneil@freelance.org",
        "skills": ["Python", "FastAPI", "PostgreSQL"],
        "total_experience_years": None,
        "highest_education_level": "UNSPECIFIED",
        "text": """Jean-Luc O'Neil
jl.oneil@freelance.org

SKILLS
Python, FastAPI, PostgreSQL
""",
    },
    {
        "id": "cand_15_sparse_candidate",
        "filename": "cand_15_sparse_candidate.txt",
        "name": None,
        "email": None,
        "skills": ["Python", "Docker", "Machine Learning"],
        "total_experience_years": None,
        "highest_education_level": "UNSPECIFIED",
        "text": """Software developer passionate about cloud engineering.
Over the past years I have worked extensively with Python, Docker, and Machine Learning.
Interested in remote opportunities and consulting engagements.
""",
    },
]

for p in PROFILES:
    # Write resume text
    txt_file = resumes_dir / p["filename"]
    txt_file.write_text(p["text"].strip(), encoding="utf-8")

    # Write gold annotation JSON
    gold_data = {
        "id": p["id"],
        "resume_filename": p["filename"],
        "name": p["name"],
        "email": p["email"],
        "skills": p["skills"],
        "total_experience_years": p["total_experience_years"],
        "highest_education_level": p["highest_education_level"],
    }
    gold_file = gold_dir / f"{p['id']}.json"
    gold_file.write_text(json.dumps(gold_data, indent=2), encoding="utf-8")

print(f"Generated {len(PROFILES)} resumes in {resumes_dir} and gold annotations in {gold_dir}")


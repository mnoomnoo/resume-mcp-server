from __future__ import annotations

import pytest
from resume_mcp_server.parser import (
    _extract_contact,
    _find_sections,
    _parse_skills,
    _parse_work_modern,
    _split_company_title,
    parse_resume,
)


# ── _find_sections ────────────────────────────────────────────────────────────

def test_find_sections_basic():
    lines = [
        "Summary",
        "Experienced engineer.",
        "Experience",
        "Acme Corp",
        "Skills",
        "Python, Rust",
        "Education",
        "BS Computer Science",
    ]
    sections = _find_sections(lines)
    assert sections["summary"] == ["Experienced engineer."]
    assert sections["experience"] == ["Acme Corp"]
    assert sections["skills"] == ["Python, Rust"]
    assert sections["education"] == ["BS Computer Science"]


def test_find_sections_unknown_heading_ignored():
    lines = ["References", "John Smith", "Skills", "Python"]
    sections = _find_sections(lines)
    assert "references" not in sections
    assert sections["skills"] == ["Python"]


def test_find_sections_content_before_first_heading_discarded():
    lines = ["Jane Doe", "jane@example.com", "Skills", "Python"]
    sections = _find_sections(lines)
    assert "skills" in sections
    assert len(sections) == 1


def test_find_sections_last_section_captured():
    lines = ["Education", "BS Computer Science", "Minor in Mathematics"]
    sections = _find_sections(lines)
    assert sections["education"] == ["BS Computer Science", "Minor in Mathematics"]


def test_find_sections_alternate_headings():
    lines = ["Work History", "Acme Corp", "Technical Skills", "Python"]
    sections = _find_sections(lines)
    assert "experience" in sections
    assert "skills" in sections


# ── _extract_contact ──────────────────────────────────────────────────────────

def test_extract_contact_full():
    lines = [
        "Jane Doe",
        "Portland, OR",
        "jane@example.com",
        "503-555-1234",
    ]
    first, last, email, phone, address = _extract_contact(lines)
    assert first == "Jane"
    assert last == "Doe"
    assert email == "jane@example.com"
    assert "503-555-1234" in phone
    assert "Portland" in address


def test_extract_contact_name_with_job_title_skipped():
    lines = [
        "Software Engineer",
        "jane@example.com",
        "503-555-1234",
    ]
    first, last, email, phone, address = _extract_contact(lines)
    # "Software Engineer" should not be picked up as name
    assert first == "" or first.lower() not in ("software",)


def test_extract_contact_email_only():
    lines = ["jane@example.com"]
    first, last, email, phone, address = _extract_contact(lines)
    assert email == "jane@example.com"
    assert phone == ""


def test_extract_contact_no_email_or_phone():
    lines = ["Jane Doe", "Some Company"]
    first, last, email, phone, address = _extract_contact(lines)
    assert email == ""
    assert phone == ""


# ── _split_company_title ──────────────────────────────────────────────────────

def test_split_pipe_separator():
    assert _split_company_title("Acme Corp | Software Engineer") == (
        "Acme Corp",
        "Software Engineer",
    )


def test_split_middle_dot_reversed_order():
    # "Title · Company" → (company, title)
    company, title = _split_company_title("Software Engineer · Acme Corp")
    assert company == "Acme Corp"
    assert title == "Software Engineer"


def test_split_comma_title_word():
    company, title = _split_company_title("Acme Corp, Senior Developer")
    assert company == "Acme Corp"
    assert title == "Senior Developer"


def test_split_no_separator():
    company, title = _split_company_title("Acme Corp")
    assert company == "Acme Corp"
    assert title == ""


# ── _parse_skills ─────────────────────────────────────────────────────────────

def test_parse_skills_basic():
    skills = _parse_skills(["Python, Rust, Go"])
    titles = [s.title for s in skills]
    assert "Python" in titles
    assert "Rust" in titles
    assert "Go" in titles


def test_parse_skills_category_prefix_stripped():
    skills = _parse_skills(["Languages: Python, Rust"])
    titles = [s.title for s in skills]
    assert "Languages" not in titles
    assert "Python" in titles
    assert "Rust" in titles


def test_parse_skills_deduplication():
    skills = _parse_skills(["Python, python, PYTHON"])
    assert len(skills) == 1
    assert skills[0].title == "Python"


def test_parse_skills_bullet_prefix_stripped():
    skills = _parse_skills(["• Docker"])
    assert skills[0].title == "Docker"


def test_parse_skills_short_tokens_filtered():
    skills = _parse_skills(["C, Go, Rust"])
    titles = [s.title for s in skills]
    assert "C" not in titles  # length 1, filtered out
    assert "Go" in titles
    assert "Rust" in titles


def test_parse_skills_semicolon_separator():
    skills = _parse_skills(["Python; Rust; Go"])
    assert len(skills) == 3


# ── _parse_work_modern ────────────────────────────────────────────────────────

def test_parse_work_modern_single_entry():
    lines = [
        "Acme Corp | Software Engineer  March 2022 – December 2025",
        "• Built a distributed system that handles 10k requests/second",
        "• Reduced latency by 40% through caching improvements",
    ]
    entries = _parse_work_modern(lines)
    assert len(entries) == 1
    assert entries[0].company_name == "Acme Corp"
    assert entries[0].position_title == "Software Engineer"
    assert entries[0].start_date == "March 2022"
    assert entries[0].end_date == "December 2025"
    assert len(entries[0].achievements) == 2


def test_parse_work_modern_two_entries_boundary():
    lines = [
        "Acme Corp | Software Engineer  March 2022 – December 2025",
        "• Built distributed system handling large traffic volumes",
        "Globex | Senior Engineer  January 2020 – February 2022",
        "• Led rewrite of core authentication service used across org",
    ]
    entries = _parse_work_modern(lines)
    assert len(entries) == 2
    assert entries[0].company_name == "Acme Corp"
    assert len(entries[0].achievements) == 1
    assert entries[1].company_name == "Globex"
    assert len(entries[1].achievements) == 1


def test_parse_work_modern_short_lines_filtered():
    lines = [
        "Acme Corp | Software Engineer  March 2022 – Present",
        "• Short",  # < 16 chars after stripping bullet → filtered
        "• Built a scalable microservice architecture for payments",
    ]
    entries = _parse_work_modern(lines)
    assert len(entries[0].achievements) == 1
    assert "microservice" in entries[0].achievements[0].desc


# ── parse_resume integration ──────────────────────────────────────────────────

_SAMPLE_RESUME = """\
Jane Doe
Portland, OR
jane@example.com
503-555-1234

Summary
Experienced software engineer with 5+ years building distributed systems.

Experience
Acme Corp | Software Engineer  March 2022 – Present
• Built a distributed system that handles large traffic volumes efficiently
• Reduced latency by 40% through targeted caching improvements

Globex | Junior Engineer  January 2020 – February 2022
• Developed RESTful APIs consumed by mobile and web clients daily
• Wrote comprehensive unit and integration tests using pytest framework

Skills
Languages: Python, Go, Rust
Tools: Docker, Kubernetes, PostgreSQL

Education
BS Computer Science, University of Oregon, 2019
"""


def test_parse_resume_happy_path():
    result = parse_resume(_SAMPLE_RESUME, "jane_resume.docx")
    assert result is not None
    assert result.first_name == "Jane"
    assert result.last_name == "Doe"
    assert result.email == "jane@example.com"
    assert len(result.work_experiences) == 2
    assert result.work_experiences[0].company_name == "Acme Corp"
    assert len(result.badge_skills) >= 3
    assert result.professional_statement != ""
    assert result.education != ""


def test_parse_resume_empty_returns_none():
    assert parse_resume("", "resume.docx") is None


def test_parse_resume_whitespace_only_returns_none():
    assert parse_resume("   \n\n  \n", "resume.docx") is None


def test_parse_resume_no_name_falls_back_to_filename():
    text = """\
someone@example.com
503-555-1234

Experience
Acme Corp | Engineer  Jan 2020 – Present
• Built systems and infrastructure improvements across the organization

Skills
Python
"""
    result = parse_resume(text, "john_smith_resume.docx")
    assert result is not None
    assert result.first_name.lower() == "john"


def test_parse_resume_no_experience_section():
    text = """\
Jane Doe
jane@example.com

Skills
Python, Go
"""
    result = parse_resume(text, "jane.docx")
    assert result is not None
    assert result.work_experiences == []
    assert len(result.badge_skills) >= 1


def test_parse_resume_professional_statement_from_summary():
    text = """\
Jane Doe
jane@example.com

Summary
Experienced engineer building scalable distributed systems.

Skills
Python
"""
    result = parse_resume(text, "jane.docx")
    assert result is not None
    assert "Experienced engineer" in result.professional_statement

from __future__ import annotations

import unittest

from resume_mcp_server.parser import (
    _extract_contact,
    _find_sections,
    _parse_projects,
    _parse_education,
    _parse_skills,
    _parse_work_modern,
    _split_company_title,
    parse_resume,
)


# ── _find_sections ────────────────────────────────────────────────────────────

class TestFindSections(unittest.TestCase):
    def test_basic(self):
        lines = [
            "Summary", "Experienced engineer.",
            "Experience", "Acme Corp",
            "Skills", "Python, Rust",
            "Education", "BS Computer Science",
        ]
        sections = _find_sections(lines)
        self.assertEqual(sections["summary"], ["Experienced engineer."])
        self.assertEqual(sections["experience"], ["Acme Corp"])
        self.assertEqual(sections["skills"], ["Python, Rust"])
        self.assertEqual(sections["education"], ["BS Computer Science"])

    def test_unknown_heading_ignored(self):
        lines = ["References", "John Smith", "Skills", "Python"]
        sections = _find_sections(lines)
        self.assertNotIn("references", sections)
        self.assertEqual(sections["skills"], ["Python"])

    def test_content_before_first_heading_discarded(self):
        lines = ["Jane Doe", "jane@example.com", "Skills", "Python"]
        sections = _find_sections(lines)
        self.assertIn("skills", sections)
        self.assertEqual(len(sections), 1)

    def test_last_section_captured(self):
        lines = ["Education", "BS Computer Science", "Minor in Mathematics"]
        sections = _find_sections(lines)
        self.assertEqual(sections["education"], ["BS Computer Science", "Minor in Mathematics"])

    def test_alternate_headings(self):
        lines = ["Work History", "Acme Corp", "Technical Skills", "Python"]
        sections = _find_sections(lines)
        self.assertIn("experience", sections)
        self.assertIn("skills", sections)


# ── _extract_contact ──────────────────────────────────────────────────────────

class TestExtractContact(unittest.TestCase):
    def test_full(self):
        lines = ["Jane Doe", "Portland, OR", "jane@example.com", "503-555-1234"]
        first, last, email, phone, address = _extract_contact(lines)
        self.assertEqual(first, "Jane")
        self.assertEqual(last, "Doe")
        self.assertEqual(email, "jane@example.com")
        self.assertIn("503-555-1234", phone)
        self.assertIn("Portland", address)

    def test_job_title_line_not_picked_up_as_name(self):
        lines = ["Software Engineer", "jane@example.com", "503-555-1234"]
        first, last, email, phone, address = _extract_contact(lines)
        self.assertTrue(first == "" or first.lower() not in ("software",))

    def test_email_only(self):
        lines = ["jane@example.com"]
        first, last, email, phone, address = _extract_contact(lines)
        self.assertEqual(email, "jane@example.com")
        self.assertEqual(phone, "")

    def test_no_email_or_phone(self):
        lines = ["Jane Doe", "Some Company"]
        first, last, email, phone, address = _extract_contact(lines)
        self.assertEqual(email, "")
        self.assertEqual(phone, "")


# ── _split_company_title ──────────────────────────────────────────────────────

class TestSplitCompanyTitle(unittest.TestCase):
    def test_pipe_separator(self):
        self.assertEqual(
            _split_company_title("Acme Corp | Software Engineer"),
            ("Acme Corp", "Software Engineer"),
        )

    def test_middle_dot_reversed_order(self):
        company, title = _split_company_title("Software Engineer · Acme Corp")
        self.assertEqual(company, "Acme Corp")
        self.assertEqual(title, "Software Engineer")

    def test_comma_title_word(self):
        company, title = _split_company_title("Acme Corp, Senior Developer")
        self.assertEqual(company, "Acme Corp")
        self.assertEqual(title, "Senior Developer")

    def test_no_separator(self):
        company, title = _split_company_title("Acme Corp")
        self.assertEqual(company, "Acme Corp")
        self.assertEqual(title, "")


# ── _parse_skills ─────────────────────────────────────────────────────────────

class TestParseSkills(unittest.TestCase):
    def test_basic(self):
        skills = _parse_skills(["Python, Rust, Go"])
        titles = [s.title for s in skills]
        self.assertIn("Python", titles)
        self.assertIn("Rust", titles)
        self.assertIn("Go", titles)

    def test_category_prefix_stripped(self):
        skills = _parse_skills(["Languages: Python, Rust"])
        titles = [s.title for s in skills]
        self.assertNotIn("Languages", titles)
        self.assertIn("Python", titles)
        self.assertIn("Rust", titles)

    def test_deduplication(self):
        skills = _parse_skills(["Python, python, PYTHON"])
        self.assertEqual(len(skills), 1)
        self.assertEqual(skills[0].title, "Python")

    def test_bullet_prefix_stripped(self):
        skills = _parse_skills(["• Docker"])
        self.assertEqual(skills[0].title, "Docker")

    def test_short_tokens_filtered(self):
        skills = _parse_skills(["C, Go, Rust"])
        titles = [s.title for s in skills]
        self.assertNotIn("C", titles)
        self.assertIn("Go", titles)
        self.assertIn("Rust", titles)

    def test_semicolon_separator(self):
        skills = _parse_skills(["Python; Rust; Go"])
        self.assertEqual(len(skills), 3)


# ── _parse_work_modern ────────────────────────────────────────────────────────

class TestParseWorkModern(unittest.TestCase):
    def test_single_entry(self):
        lines = [
            "Acme Corp | Software Engineer  March 2022 – December 2025",
            "• Built a distributed system that handles 10k requests/second",
            "• Reduced latency by 40% through caching improvements",
        ]
        entries = _parse_work_modern(lines)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].company_name, "Acme Corp")
        self.assertEqual(entries[0].position_title, "Software Engineer")
        self.assertEqual(entries[0].start_date, "March 2022")
        self.assertEqual(entries[0].end_date, "December 2025")
        self.assertEqual(len(entries[0].achievements), 2)

    def test_two_entries_boundary(self):
        lines = [
            "Acme Corp | Software Engineer  March 2022 – December 2025",
            "• Built distributed system handling large traffic volumes",
            "Globex | Senior Engineer  January 2020 – February 2022",
            "• Led rewrite of core authentication service used across org",
        ]
        entries = _parse_work_modern(lines)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].company_name, "Acme Corp")
        self.assertEqual(len(entries[0].achievements), 1)
        self.assertEqual(entries[1].company_name, "Globex")
        self.assertEqual(len(entries[1].achievements), 1)

    def test_short_lines_filtered(self):
        lines = [
            "Acme Corp | Software Engineer  March 2022 – Present",
            "• Short",
            "• Built a scalable microservice architecture for payments",
        ]
        entries = _parse_work_modern(lines)
        self.assertEqual(len(entries[0].achievements), 1)
        self.assertIn("microservice", entries[0].achievements[0].desc)


# ── _parse_projects ───────────────────────────────────────────────────────────

class TestParseProjects(unittest.TestCase):
    def test_pipe_separated_header_with_technologies(self):
        lines = [
            "Resume Bot | Python, FastMCP, Docker",
            "A tool that serves resume data over MCP.",
        ]
        projects = _parse_projects(lines)
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0].name, "Resume Bot")
        self.assertEqual(
            [t.title for t in projects[0].technologies], ["Python", "FastMCP", "Docker"]
        )
        self.assertIn("serves resume data", projects[0].description)

    def test_header_without_separator_has_no_technologies(self):
        lines = ["Personal Website", "A portfolio site built with static HTML."]
        projects = _parse_projects(lines)
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0].name, "Personal Website")
        self.assertEqual(projects[0].technologies, [])

    def test_multi_line_description_is_joined(self):
        lines = [
            "Resume Bot | Python",
            "First line of the description.",
            "• Second line with a bullet.",
        ]
        projects = _parse_projects(lines)
        self.assertEqual(len(projects), 1)
        self.assertIn("First line of the description.", projects[0].description)
        self.assertIn("Second line with a bullet.", projects[0].description)

    def test_multiple_projects_separated_by_blank_lines(self):
        lines = [
            "Resume Bot | Python, FastMCP",
            "Serves resume data over MCP.",
            "",
            "Game Engine | C++, OpenGL",
            "A small 3D rendering engine.",
        ]
        projects = _parse_projects(lines)
        self.assertEqual(len(projects), 2)
        self.assertEqual(projects[0].name, "Resume Bot")
        self.assertEqual(projects[1].name, "Game Engine")
        self.assertEqual([t.title for t in projects[1].technologies], ["C++", "OpenGL"])

    def test_empty_input_returns_no_projects(self):
        self.assertEqual(_parse_projects([]), [])


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

Projects
Resume Bot | Python, FastMCP
A tool that serves resume data over MCP.

Education
BS Computer Science, University of Oregon, 2019
"""


class TestParseResume(unittest.TestCase):
    def test_happy_path(self):
        result = parse_resume(_SAMPLE_RESUME, "jane_resume.docx")
        self.assertIsNotNone(result)
        self.assertEqual(result.first_name, "Jane")
        self.assertEqual(result.last_name, "Doe")
        self.assertEqual(result.email, "jane@example.com")
        self.assertEqual(len(result.work_experiences), 2)
        self.assertEqual(result.work_experiences[0].company_name, "Acme Corp")
        self.assertGreaterEqual(len(result.badge_skills), 3)
        self.assertNotEqual(result.professional_statement, "")
        self.assertNotEqual(result.education, "")
        self.assertEqual(len(result.side_projects), 1)
        self.assertEqual(result.side_projects[0].name, "Resume Bot")
        self.assertEqual(
            [t.title for t in result.side_projects[0].technologies], ["Python", "FastMCP"]
        )

    def test_empty_returns_none(self):
        self.assertIsNone(parse_resume("", "resume.docx"))

    def test_whitespace_only_returns_none(self):
        self.assertIsNone(parse_resume("   \n\n  \n", "resume.docx"))

    def test_no_name_falls_back_to_filename(self):
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
        self.assertIsNotNone(result)
        self.assertEqual(result.first_name.lower(), "john")

    def test_no_experience_section(self):
        text = """\
Jane Doe
jane@example.com

Skills
Python, Go
"""
        result = parse_resume(text, "jane.docx")
        self.assertIsNotNone(result)
        self.assertEqual(result.work_experiences, [])
        self.assertGreaterEqual(len(result.badge_skills), 1)

    def test_professional_statement_from_summary(self):
        text = """\
Jane Doe
jane@example.com

Summary
Experienced engineer building scalable distributed systems.

Skills
Python
"""
        result = parse_resume(text, "jane.docx")
        self.assertIsNotNone(result)
        self.assertIn("Experienced engineer", result.professional_statement)


# ── _parse_education ─────────────────────────────────────────────────────────

class TestParseEducation(unittest.TestCase):
    def test_single_entry(self):
        lines = ["BS Computer Science, University of Oregon, 2016"]
        entries = _parse_education(lines)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].degree, "BS Computer Science")
        self.assertEqual(entries[0].institution, "University of Oregon")
        self.assertEqual(entries[0].year, "2016")
        self.assertEqual(entries[0].competencies, [])

    def test_entry_with_coursework(self):
        lines = [
            "BS Computer Science, University of Oregon, 2016",
            "Relevant Coursework: Algorithms, Operating Systems, Databases",
        ]
        entries = _parse_education(lines)
        self.assertEqual(len(entries), 1)
        self.assertEqual(
            [c.title for c in entries[0].competencies],
            ["Algorithms", "Operating Systems", "Databases"],
        )

    def test_multiple_entries(self):
        lines = [
            "MS Computer Science, Portland State University, 2020",
            "Coursework: Machine Learning, Distributed Systems",
            "BS Computer Science, University of Oregon, 2016",
        ]
        entries = _parse_education(lines)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].institution, "Portland State University")
        self.assertEqual([c.title for c in entries[0].competencies], ["Machine Learning", "Distributed Systems"])
        self.assertEqual(entries[1].institution, "University of Oregon")
        self.assertEqual(entries[1].competencies, [])

    def test_no_year(self):
        lines = ["BS Computer Science, University of Oregon"]
        entries = _parse_education(lines)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].year, "")
        self.assertEqual(entries[0].institution, "University of Oregon")

    def test_no_comma_lines_ignored(self):
        lines = ["BS Computer Science, University of Oregon, 2016", "Minor in Mathematics"]
        entries = _parse_education(lines)
        self.assertEqual(len(entries), 1)

    def test_empty_section(self):
        self.assertEqual(_parse_education([]), [])

    def test_parse_resume_includes_education_entries(self):
        text = """\
Jane Doe
jane@example.com

Education
BS Computer Science, University of Oregon, 2016
Relevant Coursework: Algorithms, Operating Systems
"""
        result = parse_resume(text, "jane.docx")
        self.assertIsNotNone(result)
        self.assertEqual(len(result.education_entries), 1)
        self.assertEqual(result.education_entries[0].institution, "University of Oregon")
        self.assertEqual(
            [c.title for c in result.education_entries[0].competencies],
            ["Algorithms", "Operating Systems"],
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import re
from pathlib import Path

from .models import (
    AchievementCreate, BadgeSkillCreate, ResumeCreate, WorkExperienceCreate,
)

# ── Regexes ───────────────────────────────────────────────────────────────────

_MONTHS = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
    r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
_DATE_TOKEN = rf"(?:{_MONTHS}\.?\s*\d{{4}}|\d{{4}})"
DATE_RANGE_RE = re.compile(
    rf"({_DATE_TOKEN})\s*[-–—]\s*({_DATE_TOKEN}|Present|Current|Now)",
    re.IGNORECASE,
)

EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w{2,}")
PHONE_RE = re.compile(r"(?:\+1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")

_SECTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "summary": re.compile(
        r"^(?:professional\s+)?(?:summary|objective|profile):?$", re.IGNORECASE
    ),
    "experience": re.compile(
        r"^(?:work\s+)?(?:experience|employment(?:\s+history)?|work\s+history):?$",
        re.IGNORECASE,
    ),
    "skills": re.compile(
        r"^(?:technical\s+)?(?:skills?|competencies|expertise|technologies):?$",
        re.IGNORECASE,
    ),
    "education": re.compile(
        r"^education(?:al\s+background)?:?$|^academic(?:\s+background)?:?$",
        re.IGNORECASE,
    ),
}

NAME_RE = re.compile(r"^[A-Z][a-zA-Z\'\-]+(?: [A-Z][a-zA-Z\'\-\.]+){1,3}$")
_JOB_TITLE_WORDS = {
    "engineer", "developer", "manager", "director", "associate", "analyst",
    "designer", "architect", "consultant", "specialist", "coordinator", "lead",
    "senior", "junior", "principal", "staff", "intern", "contractor",
}

# Bullet characters used in em-dash and other resume bullets
_BULLETS = "•·▪▸◦✓—–"


# ── Section splitting ─────────────────────────────────────────────────────────

def _find_sections(lines: list[str]) -> dict[str, list[str]]:
    """Return {section_name: [content lines]} from stripped lines."""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    buf: list[str] = []

    for line in lines:
        matched: str | None = None
        for name, pat in _SECTION_PATTERNS.items():
            if pat.match(line):
                matched = name
                break
        if matched:
            if current is not None:
                sections[current] = buf
            current = matched
            buf = []
        elif current is not None:
            buf.append(line)

    if current is not None:
        sections[current] = buf

    return sections


# ── Contact extraction ────────────────────────────────────────────────────────

def _extract_contact(
    lines: list[str],
) -> tuple[str, str, str, str, str]:
    """Return (first_name, last_name, email, phone_num, address)."""
    email = phone_num = address = first_name = last_name = ""
    email_idx = phone_idx = None

    for i, line in enumerate(lines):
        if not email:
            m = EMAIL_RE.search(line)
            if m:
                email = m.group(0)
                email_idx = i
        if not phone_num:
            m = PHONE_RE.search(line)
            if m:
                phone_num = m.group(0)
                phone_idx = i

    # Find name near the contact block
    ref_idx = next(
        (x for x in [email_idx, phone_idx] if x is not None),
        0,
    )
    for j in range(max(0, ref_idx - 5), min(len(lines), ref_idx + 5)):
        candidate = lines[j]
        words_lower = set(candidate.lower().split())
        if (
            NAME_RE.match(candidate)
            and not any(p.match(candidate) for p in _SECTION_PATTERNS.values())
            and not DATE_RANGE_RE.search(candidate)
            and not EMAIL_RE.search(candidate)
            and not PHONE_RE.search(candidate)
            and not words_lower & _JOB_TITLE_WORDS
        ):
            parts = candidate.split()
            first_name = parts[0]
            last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
            break

    # Address: line near contact with city/state pattern
    for j in range(max(0, ref_idx - 3), min(len(lines), ref_idx + 3)):
        line = lines[j]
        if re.search(r"\w[\w\s]+,\s+[A-Z]{2}\b", line) and not EMAIL_RE.search(line):
            # Strip away email/phone tokens to leave the address
            addr = EMAIL_RE.sub("", PHONE_RE.sub("", line)).strip(" ,·•|")
            if addr:
                address = addr
            break

    return first_name, last_name, email, phone_num, address


# ── Work experience parsing ───────────────────────────────────────────────────

def _split_company_title(text: str) -> tuple[str, str]:
    """
    Split 'Company | Title', 'Title · Company', or 'Company, Title' into
    (company_name, position_title). Returns (text, '') if no clear separator.
    """
    text = text.strip()

    # "Title · Company" (middle dot — reversed order in these resumes)
    m = re.match(r"^(.+?)\s+[·•]\s+(.+)$", text)
    if m:
        return m.group(2).strip(), m.group(1).strip()

    # "Company | Title"
    m = re.match(r"^(.+?)\s*\|\s*(.+)$", text)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # "Company, Title" — only split if the second part looks like a job title
    m = re.match(
        r"^(.+?),\s+((?:Senior|Junior|Lead|Staff|Principal|Software|Hardware|Data|"
        r"Systems|Product|Project|Engineering|Technical|Full.?Stack|Embedded|"
        r"Machine|Research|Sales).+)$",
        text,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip(), m.group(2).strip()

    return text, ""


def _strip_bullet(line: str) -> str:
    """Remove leading bullet character and surrounding whitespace."""
    stripped = line.strip()
    if stripped and stripped[0] in _BULLETS + "-*":
        stripped = stripped[1:].strip()
    return stripped


def _parse_work_modern(
    lines: list[str],
) -> list[WorkExperienceCreate]:
    """
    Modern format: each job entry is a single line containing both
    company/title info and a date range, e.g.:
        'Skayl  |  Software Engineer    March 2022 – December 2025'
        'Software Engineer  ·  Skayl    March 2022 – December 2025'
    Achievements follow until the next entry line.
    """
    # Find all entry-line positions
    entry_positions: list[tuple[int, re.Match[str]]] = []
    for i, line in enumerate(lines):
        m = DATE_RANGE_RE.search(line)
        if m and line[:m.start()].strip():  # something before the date
            entry_positions.append((i, m))

    entries: list[WorkExperienceCreate] = []
    for k, (pos, m) in enumerate(entry_positions):
        line = lines[pos]
        before_date = line[: m.start()].strip().rstrip("\t ,")
        company_name, position_title = _split_company_title(before_date)
        start_date = m.group(1).strip()
        end_date = m.group(2).strip()

        next_pos = entry_positions[k + 1][0] if k + 1 < len(entry_positions) else len(lines)
        achievements = [
            AchievementCreate(desc=_strip_bullet(l))
            for l in lines[pos + 1 : next_pos]
            if l.strip() and len(_strip_bullet(l)) > 15
        ]

        if company_name:
            entries.append(
                WorkExperienceCreate(
                    company_name=company_name,
                    position_title=position_title,
                    start_date=start_date,
                    end_date=end_date,
                    achievements=achievements,
                )
            )
    return entries


def _parse_work_legacy(
    we_lines: list[str],
    all_lines: list[str],
) -> list[WorkExperienceCreate]:
    """
    Legacy format: achievements are grouped inside the WE section (separated by
    blank lines) while company/date lines appear elsewhere in the document.
    Groups are matched to company lines by order.
    """
    # Find company/date lines anywhere in the document (outside of WE section)
    we_set = set(we_lines)
    company_entries: list[tuple[str, str, str, str]] = []  # (company, title, start, end)
    for line in all_lines:
        if line in we_set:
            continue
        m = DATE_RANGE_RE.search(line)
        if not m:
            continue
        before = line[: m.start()].strip().rstrip("\t ,")
        if not before:
            continue
        company, title = _split_company_title(before)
        if company:
            company_entries.append(
                (company, title, m.group(1).strip(), m.group(2).strip())
            )

    if not company_entries:
        return []

    # Split WE lines into paragraph groups (separated by blank lines)
    groups: list[list[str]] = []
    current_group: list[str] = []
    for line in we_lines:
        if line.strip():
            current_group.append(line.strip())
        else:
            if current_group:
                groups.append(current_group)
                current_group = []
    if current_group:
        groups.append(current_group)

    if not groups:
        return []

    entries: list[WorkExperienceCreate] = []
    for idx, (company, title, start, end) in enumerate(company_entries):
        group_lines = groups[idx] if idx < len(groups) else []
        achievements = [
            AchievementCreate(desc=_strip_bullet(l))
            for l in group_lines
            if len(_strip_bullet(l)) > 15
        ]
        entries.append(
            WorkExperienceCreate(
                company_name=company,
                position_title=title,
                start_date=start,
                end_date=end,
                achievements=achievements,
            )
        )
    return entries


# ── Skills parsing ────────────────────────────────────────────────────────────

def _parse_skills(lines: list[str]) -> list[BadgeSkillCreate]:
    seen: set[str] = set()
    skills: list[BadgeSkillCreate] = []
    for line in lines:
        # "Category: skill1, skill2, ..." → use only the skill part
        skill_part = line.partition(":")[2] if ":" in line else line
        # Split on comma/semicolon; avoid splitting on "/" within version numbers (e.g. C++11/14/17)
        tokens = re.split(r"[,;]|(?<!\w)/(?!\w)", skill_part)
        for token in tokens:
            skill = re.sub(r"\s+", " ", token).strip().strip(_BULLETS + "-*()").strip()
            if skill and 1 < len(skill) < 80:
                lower = skill.lower()
                if lower not in seen:
                    seen.add(lower)
                    skills.append(BadgeSkillCreate(title=skill))
    return skills


# ── Main entry point ──────────────────────────────────────────────────────────

def parse_resume(text: str, filename: str) -> ResumeCreate | None:
    """
    Parse extracted resume text into a ResumeCreate.
    Returns None if the text doesn't look like a parseable resume.
    """
    # Work with both raw (for paragraph-group detection) and stripped lines
    raw_lines = text.split("\n")
    lines = [re.sub(r'^#+\s*', '', l.strip()) for l in raw_lines]

    if not any(lines):
        return None

    # Contact info
    first_name, last_name, email, phone_num, address = _extract_contact(lines)

    # Fall back to filename stem if no name found
    if not first_name:
        stem = Path(filename).stem
        parts = re.split(r"[_\s-]+", stem)
        first_name = parts[0].capitalize() if parts else stem

    # Section detection
    sections = _find_sections(lines)

    professional_statement = "\n".join(sections.get("summary", []))
    education = "\n".join(sections.get("education", []))

    # Work experience
    we_lines = sections.get("experience", [])
    work_experiences = _parse_work_modern(we_lines)
    if not work_experiences:
        work_experiences = _parse_work_legacy(we_lines, lines)

    # Skills
    badge_skills = _parse_skills(sections.get("skills", []))

    return ResumeCreate(
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone_num=phone_num,
        address=address,
        professional_statement=professional_statement,
        education=education,
        work_experiences=work_experiences,
        badge_skills=badge_skills,
    )

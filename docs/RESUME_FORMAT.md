# Resume Formatting Guide

`resume-mcp-server` parses each document into structured data using pattern-matching heuristics, not an LLM — so extraction quality depends on how closely your document follows the conventions below. A resume that doesn't match will still be searchable via `search_resumes` and `get_resume`, but structured fields (work experiences, skills, education, side projects) may come back empty or partial.

`sample_resumes/jane_doe_resume.md` follows every convention in this guide and is a good reference to copy from.

---

## Section headers

Each section must start with a line containing **only** the header text (a leading Markdown `#`/`##` is fine and stripped automatically; a trailing colon is fine too). Recognized headers, case-insensitive:

| Section | Recognized headers |
|---|---|
| Summary | `Summary`, `Professional Summary`, `Objective`, `Profile` |
| Experience | `Experience`, `Work Experience`, `Employment`, `Employment History`, `Work History` |
| Skills | `Skills`, `Technical Skills`, `Competencies`, `Expertise`, `Technologies` |
| Education | `Education`, `Educational Background`, `Academic Background` |
| Projects | `Projects`, `Side Projects`, `Personal Projects`, `Technical Projects` |

Anything outside a recognized section (or before the first one) isn't attributed to that section's structured data — it's still included in full-text search, just not parsed into fields.

---

## Contact info

Put your name, email, phone, and location together near the top of the document, each on **its own line** where possible.

- **Email/phone** are matched anywhere by regex, so these are the most reliable fields.
- **Name** is detected as a capitalized 2-4 word line near the email/phone line that isn't a section header, date range, email/phone itself, or a line containing job-title words (engineer, manager, director, etc.). If no name is found this way, the first word of the *filename* is used as a fallback first name.
- **Address** is detected as a `City, ST` pattern near the email/phone — **but only on a line that doesn't also contain the email or phone number.** Putting `email | phone | City, ST` all on one line (a common resume header style) will cause the address to be dropped. Put location on its own line if you want it captured.

```
Jane Doe
jane.doe@email.com | (555) 123-4567
San Francisco, CA
```

---

## Work experience

One format is reliable; a second exists for a narrower legacy layout.

### Recommended: one line per job

Put company, title, and date range **on a single line**, followed by bullet-point achievements:

```
Experience

Acme Corp | Staff Software Engineer    Jan 2021 – Present
- Architected a distributed job scheduling system processing 2M tasks/day
- Led a team of 6 engineers to rewrite the core ingestion pipeline

Widgets Inc | Senior Software Engineer    Mar 2018 – Dec 2020
- Designed a multi-tenant API gateway handling 50k requests/second
```

Rules that apply to this format:

- **Company/title separator**: `Company | Title`, `Title · Company` (middle dot, reversed order), or `Company, <Title>` where `<Title>` starts with a recognizable title word (Senior, Lead, Staff, Principal, Engineering, Software, Data, Product, etc.).
- **Don't put a second `|` directly before the date.** Separate the date range with whitespace, not another pipe — `Company | Title    Jan 2021 – Present` is correct; `Company | Title | Jan 2021 – Present` will leave a stray trailing `|` stuck on the parsed title.
- **Date range**: month name (full or 3-letter abbreviation, e.g. `Jan` or `January`) + 4-digit year, or a bare year; separated by `-`, `–`, or `—`; the end may be `Present`, `Current`, or `Now`. Examples: `Jan 2021 – Present`, `March 2022 - December 2025`, `2018 - 2020`.
- **Achievement bullets** may start with `•`, `·`, `▪`, `▸`, `◦`, `✓`, `—`, `–`, `-`, or `*`. Bullets are collected until the next line matching the pattern above. Bullets under ~15 characters (after stripping the bullet character) are discarded as noise, so keep achievement lines substantive.

### Legacy: achievements grouped separately from company/date lines

If your achievement paragraphs live inside the Experience section but the company/title/date lines live in a *different* section (e.g. a "Companies" summary block elsewhere in the document), entries are matched to company lines **by order**, with achievement paragraphs separated by blank lines:

```
Companies
Acme Corp | Senior Engineer  2018 - 2020
Globex | Junior Engineer  2015 - 2017

Experience
Built a distributed system that handles large traffic efficiently
Reduced latency significantly through caching improvements

Managed a team of five engineers across two major products
Developed RESTful APIs consumed by clients on a daily basis
```

This only works when the company/date lines are **outside** the Experience section — a company/date line placed inside the Experience section is ignored by this fallback. When in doubt, use the single-line recommended format instead; it's the one that reliably captures both format styles worth using.

---

## Skills

List skills comma- or semicolon-separated, one or more per line. An optional `Category: ` prefix is stripped, keeping only the values after the colon:

```
Skills

Languages: Python, Go, Rust
Cloud: AWS, GCP, Azure
```

Slashes inside version-like tokens (e.g. `C++11/14/17`) are preserved rather than split. Duplicate skill titles (case-insensitive) are deduplicated automatically.

---

## Side projects

Each project is a blank-line-separated paragraph. The first line is the project name, optionally followed by `| Tech1, Tech2, ...`; remaining lines become the description:

```
Projects

Resume Parser | Python, regex
A tool that parses resumes into structured data for search.

Home Automation
Built a home automation system using Raspberry Pi and MQTT.
```

---

## Education

One entry per line, comma-separated as `Degree, Institution, Year` (year is optional — it's only recognized if it's a bare 4-digit year or the word "Present"). An immediately following `Relevant Coursework: X, Y, Z` (or `Coursework: ...`) line attaches those as competencies to the entry above it:

```
Education

BS Computer Science, University of Oregon, 2016
Relevant Coursework: Algorithms, Operating Systems, Databases
MS Computer Science, Portland State University, 2020
```

---

## Supported file types

| Extension | Extraction method | Notes |
|---|---|---|
| `.docx` | Paragraph text + table cell text (`python-docx`) | Tables are flattened into rows of tab-separated cell text |
| `.pdf` | Page text extraction (`pdfplumber`) | Scanned/image-only PDFs have no extractable text and won't parse — use a text-based PDF or convert to `.docx`/`.md` |
| `.md` / `.txt` | Raw file read | Leading `#`/`##` Markdown headers are stripped before section matching, so `## Experience` and `Experience` are equivalent |

---

## Troubleshooting

- **A field is empty in `get_resume_full` but the text is clearly in the document** — the raw text is always searchable via `search_resumes`/`get_resume` regardless of structured parsing; check that section headers and line formats above match exactly. A missing/unrecognized section simply parses as empty, not an error.
- **`work_experiences` is empty** — the most common cause is a date range that isn't on the same line as the company/title (see [Work experience](#work-experience) above).
- **Address missing** — check whether it's on the same line as your email or phone; move it to its own line.
- **A job title has a stray trailing `|`** — you likely have `Company | Title | Date` on one line; drop the second `|` and separate the date with whitespace instead.

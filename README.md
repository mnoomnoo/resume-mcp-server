# resume-mcp-server

[![CI](https://github.com/mnoomnoo/resume-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/mnoomnoo/resume-mcp-server/actions/workflows/ci.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-compatible-brightgreen)](https://modelcontextprotocol.io)
[![PyPI](https://img.shields.io/pypi/v/resume-mcp-server)](https://pypi.org/project/resume-mcp-server/)
[![resume-mcp-server MCP server](https://glama.ai/mcp/servers/mnoomnoo/resume-mcp-server/badges/score.svg)](https://glama.ai/mcp/servers/mnoomnoo/resume-mcp-server)

An MCP server that gives Claude (or any MCP client) structured, searchable access to your resume collection — resumes, cover letters, and application materials in `.docx`, `.pdf`, `.md`, or `.txt` format.

Job seekers accumulate document sprawl fast: multiple resume versions tailored to different roles, cover letter drafts, reference sheets. Manually digging through them to draft a new application is tedious. Point this server at your resume folder and Claude can answer questions like *"which of my resumes highlights Kubernetes experience?"*, *"what achievements have I listed across my backend roles?"*, or *"draft a cover letter drawing from my work at Acme Corp"* — without you pasting anything.

The server parses each document into structured data (contact info, work history, education, skills, side projects) and exposes 19 tools covering full-text search, skill lookup, company and role queries, achievement mining, education search, collection analytics, and more. Files are watched and re-indexed automatically, so edits to your documents are reflected immediately.

---

## Features

- **Multi-format parsing** — `.docx`, `.pdf`, `.md`, and `.txt` documents are parsed into structured data: contact info, work history, education, skills, and side projects.
- **Automatic hot-reload** — a filesystem watcher re-indexes your documents as soon as they change, no server restart needed.
- **Document type inference** — files are automatically classified as `resume`, `cover_letter`, `application_material`, or `other` based on filename patterns, which can be overridden per category via environment variables.
- **Full-text and structured search** — search whole documents with `search_resumes`, or filter any entity type (skills, work experience, achievements, side projects, education) with a scoped `query`, `technology`, or `competency` parameter.
- **Three search modes** — `and`, `or`, and `regex` matching, available consistently on every tool that accepts a query-like parameter.
- **Uniform pagination** — every list-style tool returns the same `total_count` / `items` / `has_more` / `next_offset` / `message` envelope, with validated `limit`/`offset` and a 200-item cap.
- **Unified error shape** — every failure returns `{"error": "..."}`, so callers only need to check for one shape regardless of which tool they called.
- **Collection analytics** — `get_collection_stats` and `get_skill_frequency` surface aggregate counts and cross-resume skill popularity.
- **Read-only and safe by construction** — every tool is annotated `readOnlyHint` / `idempotentHint` / `openWorldHint: false`; nothing mutates your files or reaches outside the local document collection.
- **Flexible deployment** — run over stdio or HTTP, standalone or via Docker/Docker Compose with CORS support, configured through environment variables or a `.env` file.

See [MCP Tools](#mcp-tools) below for the full list of tools this exposes.

---

## Quick Start

Give Claude structured access to your resume collection. The server parses your documents on startup and exposes 19 tools for searching by name, company, skill, education, side project, or full text, plus analytics tools for skill frequency and collection statistics — with automatic hot-reload when files change.

**Try it immediately with the included sample resumes:**

```bash
pip install resume-mcp-server
RESUME_DIR=./sample_resumes resume-mcp-server
```

Then connect Claude Code:

```bash
claude mcp add resume-mcp-server resume-mcp-server -e RESUME_DIR=$(pwd)/sample_resumes
```

For a persistent setup with Docker or your own documents, see [Docker Deploy](#docker-deploy) or [Dev Environment](#dev-environment).

---

## Docker Deploy

The recommended way to run the server. Docker Compose exposes the server over HTTP so any AI client can connect to it.

### 1. Set your resume directory

Copy the example env file and set your documents path:

```bash
cp .env.example .env
# then edit RESUME_DIR_HOST in .env
```

### 2. Sync the image version (optional)

Stamp the image with the current `pyproject.toml` version:

```bash
python scripts/sync_version.py
```

### 3. Build and start

```bash
docker compose build resume-mcp
docker compose up -d
```

The server is now available at `http://localhost:8001/mcp`.

### 4. Connect your AI client

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "resume-mcp-server": {
      "type": "http",
      "url": "http://localhost:8001/mcp"
    }
  }
}
```

**VS Code** (`.vscode/mcp.json`):

```json
{
  "servers": {
    "resume-mcp-server": {
      "type": "http",
      "url": "http://localhost:8001/mcp"
    }
  }
}
```

**Claude Code**:

```bash
claude mcp add resume-mcp-server --transport http http://localhost:8001/mcp
```

To add it globally across all projects, add the following to `~/.claude.json` instead:

```json
{
  "mcpServers": {
    "resume-mcp-server": {
      "type": "http",
      "url": "http://localhost:8001/mcp"
    }
  }
}
```

### Stopping

```bash
docker compose down
```

### Docker (stdio)

Run the image directly — no Compose needed — for MCP clients that use stdio transport (including Glama.ai and Claude Desktop):

```bash
docker run -i --rm -v /path/to/your/resumes:/resumes resume-mcp-server
```

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "resume-mcp-server": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "-v", "/path/to/your/resumes:/resumes", "resume-mcp-server"]
    }
  }
}
```

---

## Dev Environment

For local development or running the server without Docker.

### Prerequisites

Python 3.12+

### Install

```bash
pip install .
# include test dependencies:
pip install ".[dev]"
```

### Run

```bash
resume-mcp-server
# with a custom directory:
RESUME_DIR=/path/to/docs resume-mcp-server
```

Or create a `.env` file in the directory you run the server from:

```bash
# .env
RESUME_DIR=/path/to/docs
FASTMCP_PORT=8001
```

Then just run `resume-mcp-server` — the `.env` is loaded automatically. Variables already set in your shell or by the MCP client always take precedence over `.env` values.

### Connect your AI client (stdio)

**Claude Desktop**:

```json
{
  "mcpServers": {
    "resume-mcp-server": {
      "command": "resume-mcp-server",
      "env": {
        "RESUME_DIR": "/path/to/your/resumes"
      }
    }
  }
}
```

If `resume-mcp-server` is not on your `PATH`, use the full path (e.g. `~/.venv/bin/resume-mcp-server`).

**Claude Code**:

```bash
claude mcp add resume-mcp-server resume-mcp-server -e RESUME_DIR=/path/to/your/resumes
```

**uvx:**

```json
{
  "mcpServers": {
    "resume-mcp-server": {
      "command": "uvx",
      "args": ["resume-mcp-server"],
      "env": {
        "RESUME_DIR": "/path/to/your/resumes"
      }
    }
  }
}
```

---

## Configuration

**Docker Compose** (`.env`):

| Variable | Description |
|---|---|
| `RESUME_DIR_HOST` | Path on your machine to the documents directory — mounted to `/resumes` inside the container |
| `FASTMCP_PORT` | Port the HTTP server listens on (default `8001`) |
| `LOG_LEVEL` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` (default `INFO`) |

**Local run** (environment variables or `.env`):

| Variable | Default | Description |
|---|---|---|
| `RESUME_DIR` | `~/resumes` | Directory scanned for documents |
| `FASTMCP_TRANSPORT` | `http` (local) / `stdio` (Docker image) | Transport protocol (`http` or `stdio`) |
| `FASTMCP_HOST` | `0.0.0.0` | Bind address |
| `FASTMCP_PORT` | `8001` | Port the HTTP server listens on |
| `DOC_TYPE_PATTERN_RESUME` | `resume` | Regex used to classify a filename as `resume` |
| `DOC_TYPE_PATTERN_COVER_LETTER` | `cover.?letter\|_cl\.\|_cl_\|coverletter` | Regex used to classify a filename as `cover_letter` |
| `DOC_TYPE_PATTERN_APPLICATION_MATERIAL` | `interview\|study.?guide\|why_\|application.?question\|job.?desc` | Regex used to classify a filename as `application_material` |

A `.env` file in the working directory is loaded automatically on startup if present. Shell environment variables and values set by the MCP client always take precedence over `.env` values.

Each `DOC_TYPE_PATTERN_*` variable replaces the default regex for that category (filenames are matched in order: resume, then cover letter, then application material, then everything else falls back to `other`). Leave a variable unset to keep its default; an invalid regex is ignored and the default is used instead.

The server scans `RESUME_DIR` recursively on startup and reloads automatically when files change.

### Document type inference

Types are inferred from filenames:

| Type | Filename patterns |
|---|---|
| `resume` | contains `resume` |
| `cover_letter` | `cover letter`, `_cl.`, `coverletter` |
| `application_material` | `interview`, `study guide`, `why_`, `application question`, `job desc` |
| `other` | everything else |

Each of the three regexes can be overridden with `DOC_TYPE_PATTERN_RESUME`, `DOC_TYPE_PATTERN_COVER_LETTER`, and `DOC_TYPE_PATTERN_APPLICATION_MATERIAL` — see [Configuration](#configuration).

---

## Search behavior

Most tools that accept a `query` (or `technology`/`competency`) parameter split it on whitespace and support three match modes via the optional `mode` parameter:

| `mode` | Behavior |
|---|---|
| `"and"` *(default)* | All tokens must appear within the same field. `"latency throughput"` only matches a description that contains both words. |
| `"or"` | Any token is sufficient. `"latency throughput"` matches a description that contains either word. |
| `"regex"` | The query is compiled as-is (not tokenized or escaped) into a case-insensitive regular expression and matched against the field. Use this for grep-style power — alternation, wildcards, anchors, etc., e.g. `"eng(ineer)?"` or `"aws|gcp|azure"`. An invalid pattern returns `{"error": "..."}` instead of raising. |

**Multi-field note:** For tools that search several fields (company name, position title, achievement text, etc.), AND mode requires all tokens to co-occur in the *same* field, not spread across fields. Use OR mode when you want a looser cross-field match. Regex mode also matches per-field.

**Single-word queries** behave identically in `and`/`or` mode.

Every tool that accepts a query-like parameter — including `search_resumes`, the whole-document keyword search — shares this same `"and"`/`"or"`/`"regex"` vocabulary.

`search_resumes_by_skill` accepts either a single skill string or a list of skills. For a list, `mode` does double duty: it also controls whether a resume must match EACH skill in the list (`"and"`) or ANY skill (`"or"`); `"regex"` mode combines multiple skills with OR semantics.

An empty query or an empty skill list returns `{"error": "..."}` rather than an empty result — this distinguishes a caller mistake from a legitimate zero-match search.

---

## Pagination

All `list_*` tools (and `search_resumes`/`search_resumes_by_skill`) accept `limit` and `offset` parameters and return a consistent envelope:

```json
{
  "total_count": 247,
  "items": [...],
  "has_more": true,
  "next_offset": 100,
  "message": "100 of 247 results shown. Call again with offset=100 to see more."
}
```

`total_count` is the full match count before slicing. `has_more` and `next_offset` tell you directly whether to page further — no need to compute `offset + len(items) < total_count` yourself — and `message` restates that in plain language, ready to act on. When there's nothing left, `has_more` is `false`, `next_offset` is `null`, and `message` reads `"All N results shown."`.

`limit` must be greater than 0 and `offset` must be 0 or greater — otherwise the tool returns `{"error": "..."}`. An `offset` beyond the total result count is not an error; it's a valid "past the end" page (`items: []`, `has_more: false`).

**Cap and defaults.** `limit` is silently capped at `200` regardless of what's requested — if you ask for more, the response still comes back (not an error), but `message` is prefixed with `"Requested limit N capped to 200."` so you know it happened. Default `limit` varies by tool, generally lower for heavier, deeply-nested responses:

| Tool | Default `limit` |
|---|---|
| `list_resumes` | 10 (each item is a fully nested resume) |
| `list_work_experiences`, `list_side_projects`, `list_education` | 25 |
| `list_achievements` | 50 |
| `list_resume_summaries`, `list_skills`, `search_resumes`, `search_resumes_by_skill` | 100 |
| `get_skill_frequency` | 20 (not part of the pagination envelope, but shares the same 200 cap) |

---

## Error handling

Every tool returns a dict. On failure, the dict is exactly `{"error": "<message>"}` — this is the only failure shape in the API, so a caller can check for the `"error"` key regardless of which tool it called. This covers: not-found IDs, a `resume_id` filter that doesn't match any resume, invalid regex patterns, and invalid `limit`/`offset` values. A `resume_id` filter that *does* match a resume but simply has zero matching child records (e.g. `list_work_experiences(resume_id=<valid>)` for someone with no work history) is not an error — it returns an empty `items` list.

`get_resume`'s success shape is `{"text": "..."}` so that success and failure are both dicts, distinguishable by key.

---

## MCP Tools

19 tools are exposed, covering full-text search, skill lookup, company and role queries, achievement mining, education search, collection analytics, and more. Every tool is read-only (`readOnlyHint: true`) — none mutate state or reach outside the local document collection (`openWorldHint: false`).

| Tool | Description |
|---|---|
| `list_resume_summaries` | Lightweight identity records (id, name, email, phone) for orienting before fetching details; optional `query` filters by name |
| `get_resume_profile` | A resume's top-level fields (contact info, statement, education) without nested lists |
| `get_resume_full` | A resume's complete nested structure (work experiences, skills, side projects, education) in one call |
| `list_resumes` | List all documents, optionally filtered by type |
| `get_resume` | Full extracted text of a document, keyed by path (not resume_id) |
| `search_resumes` | Full-text search across all documents, sorted by match count |
| `list_skills` | List badge skills, optionally scoped to a resume and/or filtered by title |
| `get_badge_skill` | A single badge skill by ID |
| `search_resumes_by_skill` | Find which resumes list one or more given badge skills (accepts a string or a list) |
| `get_skill_frequency` | Badge skills ranked by how many resumes list them |
| `list_work_experiences` | List work experiences, optionally scoped to a resume, current-only, and/or a keyword query |
| `get_work_experience` | A single work experience entry with its achievement bullets |
| `list_achievements` | List achievement bullets, optionally scoped to a resume and/or a keyword query |
| `get_achievement` | A single achievement bullet by ID |
| `list_side_projects` | List side projects, optionally scoped to a resume and/or matched by keyword or technology |
| `get_side_project` | A single side project by ID, including demonstrated technologies |
| `list_education` | List education entries, optionally scoped to a resume and/or matched by keyword or competency |
| `get_education` | A single education entry by ID, including its competencies |
| `get_collection_stats` | Aggregate counts and averages across the entire loaded collection |

See [docs/TOOLS.md](docs/TOOLS.md) for full parameter tables and return shapes for every tool.


# resume-mcp-server

[![CI](https://github.com/mnoomnoo/resume-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/mnoomnoo/resume-mcp-server/actions/workflows/ci.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-compatible-brightgreen)](https://modelcontextprotocol.io)
[![PyPI](https://img.shields.io/pypi/v/resume-mcp-server)](https://pypi.org/project/resume-mcp-server/)
[![resume-mcp-server MCP server](https://glama.ai/mcp/servers/mnoomnoo/resume-mcp-server/badges/score.svg)](https://glama.ai/mcp/servers/mnoomnoo/resume-mcp-server)

An MCP server that gives Claude (or any MCP client) structured, searchable access to your resume collection — resumes, cover letters, and application materials in `.docx`, `.pdf`, `.md`, or `.txt` format.

Job seekers accumulate document sprawl fast: multiple resume versions tailored to different roles, cover letter drafts, reference sheets. Manually digging through them to draft a new application is tedious. Point this server at your resume folder and Claude can answer questions like *"which of my resumes highlights Kubernetes experience?"*, *"what achievements have I listed across my backend roles?"*, or *"draft a cover letter drawing from my work at Acme Corp"* — without you pasting anything.

The server parses each document into structured data (contact info, work history, education, skills, side projects) and exposes 27 tools covering full-text search, skill lookup, company and role queries, achievement mining, education search, collection analytics, and more. Files are watched and re-indexed automatically, so edits to your documents are reflected immediately.

---

## Quick Start

Give Claude structured access to your resume collection. The server parses your documents on startup and exposes 27 tools for searching by name, company, skill, education, side project, or full text, plus analytics tools for skill frequency and collection statistics — with automatic hot-reload when files change.

**Try it immediately with the included sample resumes:**

```bash
pip install resume-mcp-server
RESUME_DIR=./sample_resumes resume-mcp-server
```

Then connect Claude Code:

```bash
claude mcp add resume-collection resume-mcp-server -e RESUME_DIR=$(pwd)/sample_resumes
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
    "resume-collection": {
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
    "resume-collection": {
      "type": "http",
      "url": "http://localhost:8001/mcp"
    }
  }
}
```

**Claude Code**:

```bash
claude mcp add resume-collection --transport http http://localhost:8001/mcp
```

To add it globally across all projects, add the following to `~/.claude.json` instead:

```json
{
  "mcpServers": {
    "resume-collection": {
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
    "resume-collection": {
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
    "resume-collection": {
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
claude mcp add resume-collection resume-mcp-server -e RESUME_DIR=/path/to/your/resumes
```

**uvx:**

```json
{
  "mcpServers": {
    "resume-collection": {
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

A `.env` file in the working directory is loaded automatically on startup if present. Shell environment variables and values set by the MCP client always take precedence over `.env` values.

The server scans `RESUME_DIR` recursively on startup and reloads automatically when files change.

### Document type inference

Types are inferred from filenames:

| Type | Filename patterns |
|---|---|
| `resume` | contains `resume` |
| `cover_letter` | `cover letter`, `_cl.`, `coverletter` |
| `application_material` | `interview`, `study guide`, `why_`, `application question`, `job desc` |
| `other` | everything else |

---

## Search behavior

Most `search_*` tools split the query on whitespace and support three match modes via the optional `mode` parameter:

| `mode` | Behavior |
|---|---|
| `"and"` *(default)* | All tokens must appear within the same field. `"latency throughput"` only matches a description that contains both words. |
| `"or"` | Any token is sufficient. `"latency throughput"` matches a description that contains either word. |
| `"regex"` | The query is compiled as-is (not tokenized or escaped) into a case-insensitive regular expression and matched against the field. Use this for grep-style power — alternation, wildcards, anchors, etc., e.g. `"eng(ineer)?"` or `"aws|gcp|azure"`. An invalid pattern returns `{"error": "..."}` instead of raising. |

**Multi-field note:** For tools that search several fields (company name, position title, achievement text, etc.), AND mode requires all tokens to co-occur in the *same* field, not spread across fields. Use OR mode when you want a looser cross-field match. Regex mode also matches per-field.

**Single-word queries** behave identically in `and`/`or` mode.

`search_resumes` isn't tokenized (it's a whole-document keyword search), so its `mode` only accepts `"literal"` *(default)* or `"regex"`.

`search_resumes_by_skills` does not support `"regex"` — its `mode` already means something different (AND/OR *across* the list of skill queries, not within one query's tokens).

---

## Pagination

All `list_*` and `search_*` tools accept `limit` (default `100`) and `offset` (default `0`) parameters and return a consistent envelope:

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

---

## MCP Tools

27 tools are exposed, covering full-text search, skill lookup, company and role queries, achievement mining, education search, collection analytics, and more.

| Tool | Description |
|---|---|
| `list_resume_summaries` | Lightweight identity records (id, name, email, phone) for orienting before fetching details |
| `list_resumes` | List all documents, optionally filtered by type |
| `get_resume` | Full extracted text of a document |
| `get_resume_profile` | A resume's top-level fields (contact info, statement, education) without nested lists |
| `search_resumes` | Full-text search across all documents, sorted by match count |
| `search_resumes_by_name` | Find resumes by person name |
| `search_resumes_by_skill` | Find which resumes list a given badge skill |
| `search_resumes_by_skills` | Find resumes matching a list of skills with AND/OR logic across the list |
| `search_skills` | Search badge skills (technologies, tools, languages) by title |
| `search_work_experiences` | Search by company name, position title, or achievement bullets |
| `list_work_experiences` | List work experience entries, optionally scoped to a resume or current roles only |
| `get_work_experience` | A single work experience entry with its achievement bullets |
| `list_achievements` | List all achievement bullets, optionally scoped to a resume |
| `get_achievement` | A single achievement bullet by ID |
| `search_achievements` | Search achievement descriptions directly, returning minimal parent context |
| `list_badge_skills` | List all badge skills, optionally scoped to a resume |
| `get_badge_skill` | A single badge skill by ID |
| `list_side_projects` | List side projects, optionally scoped to a resume |
| `get_side_project` | A single side project by ID, including demonstrated technologies |
| `search_side_projects` | Search side projects by name, description, or technology |
| `search_side_projects_by_technology` | Find side projects demonstrating a given technology |
| `list_education` | List education entries, optionally scoped to a resume |
| `get_education` | A single education entry by ID, including its competencies |
| `search_education` | Search education entries by institution, degree, or competency |
| `search_education_by_competency` | Find education entries demonstrating a given competency |
| `get_collection_stats` | Aggregate counts and averages across the entire loaded collection |
| `get_skill_frequency` | Badge skills ranked by how many resumes list them |

See [docs/TOOLS.md](docs/TOOLS.md) for full parameter tables and return shapes for every tool.

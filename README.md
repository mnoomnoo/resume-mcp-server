# resume-mcp-server

An MCP server for browsing and searching job application documents — resumes, cover letters, and related materials.

Supports `.docx`, `.pdf`, `.md`, and `.txt` files, including nested subdirectories.

---

## Docker Deploy

The recommended way to run the server. Docker Compose exposes the server over HTTP so any AI client can connect to it.

### 1. Set your resume directory

Copy the example env file and set your documents path:

```bash
cp .env.example .env
# then edit RESUME_DIR_HOST in .env
```

### 2. Build and start

```bash
docker compose build resume-mcp
docker compose up -d
```

The server is now available at `http://localhost:8001/mcp`.

### 3. Connect your AI client

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

---

## Configuration

**Docker Compose** (`.env`):

| Variable | Description |
|---|---|
| `RESUME_DIR_HOST` | Path on your machine to the documents directory — mounted to `/resumes` inside the container |
| `FASTMCP_PORT` | Port the HTTP server listens on (default `8001`) |
| `LOG_LEVEL` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` (default `INFO`) |

**Local run** (environment variables):

| Variable | Default | Description |
|---|---|---|
| `RESUME_DIR` | `~/resumes` | Directory scanned for documents |

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

## MCP Tools

### `list_resumes`

List all documents, optionally filtered by type.

| Parameter | Type | Description |
|---|---|---|
| `doc_type` | string (optional) | `resume`, `cover_letter`, `application_material`, or `other` |

---

### `get_resume`

Return the full extracted text of a document.

| Parameter | Type | Description |
|---|---|---|
| `path` | string | Relative path as returned by `list_resumes` |

---

### `search_resumes`

Full-text search across all documents (case-insensitive), sorted by match count.

| Parameter | Type | Description |
|---|---|---|
| `query` | string | Text to search for |
| `doc_type` | string (optional) | Filter by type (same values as `list_resumes`) |

---

### `search_skills`

Search badge skills (technologies, tools, languages) by title.

| Parameter | Type | Description |
|---|---|---|
| `query` | string | Text to search for in skill titles (case-insensitive) |

---

### `search_work_experiences`

Search work experiences by company name, position title, or achievement description bullets.
Each result includes a `resume_id` field identifying which resume the entry belongs to.

| Parameter | Type | Description |
|---|---|---|
| `query` | string | Text to search for (case-insensitive) |

---

### `list_work_experiences`

List work experience entries, optionally scoped to a single resume.

| Parameter | Type | Description |
|---|---|---|
| `resume_id` | string (optional) | Resume ID from `list_resumes` |

---

### `get_work_experience`

Get a single work experience entry with its achievement bullets.

| Parameter | Type | Description |
|---|---|---|
| `id` | string | Work experience ID from `list_work_experiences` |

---

### `list_achievements`

List all achievement bullets, optionally scoped to a single resume.

| Parameter | Type | Description |
|---|---|---|
| `resume_id` | string (optional) | Resume ID from `list_resumes` |

---

### `get_achievement`

Get a single achievement bullet by ID.

| Parameter | Type | Description |
|---|---|---|
| `id` | string | Achievement ID from `list_achievements` |

---

### `list_badge_skills`

List all badge skills, optionally scoped to a single resume.

| Parameter | Type | Description |
|---|---|---|
| `resume_id` | string (optional) | Resume ID from `list_resumes` |

---

### `get_badge_skill`

Get a single badge skill by ID.

| Parameter | Type | Description |
|---|---|---|
| `id` | string | Badge skill ID from `list_badge_skills` |

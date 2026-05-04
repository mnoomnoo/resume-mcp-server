# resume-mcp-server

An MCP (Model Context Protocol) server for browsing and searching job application documents — resumes, cover letters, and related materials.

## Features

- **List** all documents in your collection, optionally filtered by type
- **Read** the full text of any document
- **Search** across all documents by keyword or phrase

Supports `.docx`, `.pdf`, `.md`, and `.txt` files, including nested subdirectories.

## Prerequisites

**Option A — Docker (recommended):** Docker installed, no Python required.

**Option B — Local:** Python 3.12+ and `pip`.

## Installation

### Docker

```bash
git clone <repo-url>
cd resume-mcp-server
docker build -t resume-mcp-server .
```

### Local

```bash
git clone <repo-url>
cd resume-mcp-server
pip install .
```

## Configuration

| Environment variable | Default | Description |
|---|---|---|
| `RESUME_DIR` | `~/resumes` | Path to your documents directory |

The server recursively scans `RESUME_DIR` on startup and indexes all supported files.

### Document type inference

Types are inferred from filenames automatically:

| Type | Filename patterns |
|---|---|
| `resume` | `resume`, `resume_` |
| `cover_letter` | `cover letter`, `_cl.`, `coverletter` |
| `application_material` | `interview`, `study guide`, `why_`, `application question`, `job desc` |
| `other` | everything else |

## Running the server

### Docker

```bash
docker run -i -v /path/to/your/resumes:/resumes resume-mcp-server
```

The `-i` flag is required — MCP communicates over stdin/stdout. The `/resumes` mount path maps to `RESUME_DIR` inside the container (default `/resumes`).

To use a different internal path:

```bash
docker run -i \
  -v /path/to/your/resumes:/docs \
  -e RESUME_DIR=/docs \
  resume-mcp-server
```

### Local

Requires `pip install .` first (adds `resume-mcp-server` to your PATH).

```bash
resume-mcp-server
# with a custom directory:
RESUME_DIR=/path/to/docs resume-mcp-server
```

## Docker Compose

Run the resume server exposed over HTTP so any AI client can connect to it.

### Prerequisites

Set `RESUME_DIR_HOST` to the path of your documents directory on the host machine. The easiest way is a `.env` file in the project root:

```bash
echo 'RESUME_DIR_HOST=/path/to/your/resumes' > .env
```

### Starting

```bash
docker compose build resume-mcp   # build resume server image
docker compose up -d              # start the server in the background
```

- Resume server: `http://localhost:8001/mcp`

### Stopping

```bash
docker compose down
```

### AI client integration

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "resume-mcp-docker": {
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
    "resume-mcp-docker": {
      "type": "http",
      "url": "http://localhost:8001/mcp"
    }
  }
}
```

**Claude Code**:

```bash
claude mcp add resume-mcp-docker --transport http http://localhost:8001/mcp
```

This writes to `~/.claude.json`. Do **not** add it to `~/.claude/settings.json` — that file is for permissions and preferences only, not MCP servers.

---

## Claude Desktop integration

### Docker

```json
{
  "mcpServers": {
    "resume-collection": {
      "command": "docker",
      "args": ["run", "-i", "-v", "/path/to/your/resumes:/resumes", "resume-mcp-server"]
    }
  }
}
```

### Local

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

If `resume-mcp-server` is not on your `PATH`, use the full path to the installed script (e.g. `~/.venv/bin/resume-mcp-server`).

## Claude Code integration

### Docker

```bash
claude mcp add resume-collection -- docker run -i -v /path/to/your/resumes:/resumes resume-mcp-server
```

### Local

```bash
claude mcp add resume-collection resume-mcp-server -e RESUME_DIR=/path/to/your/resumes
```

If `resume-mcp-server` is not on your `PATH`, use the full path (e.g. `~/.venv/bin/resume-mcp-server`).

Both commands write to `~/.claude.json`. Do **not** add MCP servers to `~/.claude/settings.json` — that file is for permissions and preferences only.

## MCP Tools

### `list_resumes`

List all documents in the collection.

| Parameter | Type | Description |
|---|---|---|
| `doc_type` | `string` (optional) | Filter by type: `resume`, `cover_letter`, `application_material`, or `other` |

Returns a list of objects:

```json
[
  {
    "path": "Acme/MyResume.docx",
    "filename": "MyResume.docx",
    "doc_type": "resume",
    "modified": "2024-11-01T10:30:00",
    "size_bytes": 42000
  }
]
```

---

### `get_resume`

Return the full extracted text of a document.

| Parameter | Type | Description |
|---|---|---|
| `path` | `string` | Relative path as returned by `list_resumes` |

Returns a string with the document's text content.

---

### `search_resumes`

Search across all documents for a keyword or phrase (case-insensitive).

| Parameter | Type | Description |
|---|---|---|
| `query` | `string` | Text to search for |
| `doc_type` | `string` (optional) | Filter by type (same values as `list_resumes`) |

Returns results sorted by match count descending:

```json
[
  {
    "path": "MyResume_v2.docx",
    "filename": "MyResume_v2.docx",
    "doc_type": "resume",
    "match_count": 5,
    "snippet": "...context around the first match..."
  }
]
```

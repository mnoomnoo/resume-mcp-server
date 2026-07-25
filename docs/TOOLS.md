# MCP Tools Reference

Full parameter and return-shape reference for all 19 tools exposed by `resume-mcp-server`. All tools that accept a `mode` parameter share the same match-mode conventions: see [Search behavior](../README.md#search-behavior) in the main README. All `list_*` tools share the same pagination envelope and validation — see [Pagination](../README.md#pagination). Every tool's failure shape is `{"error": "..."}` — see [Error handling](../README.md#error-handling). Every tool is read-only (annotated `readOnlyHint: true`, `idempotentHint: true`, `openWorldHint: false`) — safe to call freely, no confirmation needed.

### `list_resume_summaries`

List resumes as lightweight identity records. Use this first to orient and pick a `resume_id` before fetching details — much more token-efficient than `list_resumes`. Pass `query` to filter by first or last name.

| Parameter | Type | Description |
|---|---|---|
| `query` | string (optional) | Name fragment to filter by first or last name (case-insensitive) |
| `mode` | string (optional) | `"and"` *(default)*, `"or"`, or `"regex"` — see [Search behavior](../README.md#search-behavior) |
| `limit` | integer (optional) | Maximum number of results (default `100`) |
| `offset` | integer (optional) | Number of results to skip (default `0`) |

Returns: paginated envelope — `total_count` + `items`, where each item has `id`, `first_name`, `last_name`, `email`, `phone_num`.

---

### `get_resume_profile`

Get a resume's top-level fields (contact info, professional statement, education) without the nested work experience or badge skill lists. Prefer this over `get_resume_full` when you don't need the whole nested structure.

| Parameter | Type | Description |
|---|---|---|
| `resume_id` | string | Resume ID from `list_resume_summaries` |

Returns: the profile dict on success, `{"error": "..."}` if `resume_id` is not found.

---

### `get_resume_full`

Get a resume's complete nested structure in a single call: profile fields plus all work experiences (with achievements), badge skills, side projects (with technologies), and education entries (with competencies). Prefer `get_resume_profile` plus the scoped `list_*` tools when you only need part of this — it's more token-efficient; use `get_resume_full` when you need the whole picture at once and want to avoid multiple round trips.

| Parameter | Type | Description |
|---|---|---|
| `resume_id` | string | Resume ID from `list_resume_summaries` |

Returns: the full nested resume dict on success, `{"error": "..."}` if `resume_id` is not found.

---

### `list_resumes`

List all documents, optionally filtered by type. When `doc_type` is `resume` (or omitted), structured resume data is returned if available; otherwise flat file metadata is returned.

| Parameter | Type | Description |
|---|---|---|
| `doc_type` | string (optional) | `resume`, `cover_letter`, `application_material`, or `other` |
| `limit` | integer (optional) | Maximum number of results (default `10` — each item is a fully nested resume) |
| `offset` | integer (optional) | Number of results to skip (default `0`) |

Returns: paginated envelope — `total_count` + `items`.

---

### `get_resume`

Return the full extracted text of a document. Takes a file **path**, not a `resume_id` — use `get_resume_profile` or `get_resume_full` to fetch structured data by `resume_id` instead.

| Parameter | Type | Description |
|---|---|---|
| `path` | string | Relative path as returned by `list_resumes` |

Returns: `{"text": "..."}` on success, `{"error": "..."}` if `path` is not found.

---

### `search_resumes`

Full-text search across all documents (case-insensitive), sorted by match count.

| Parameter | Type | Description |
|---|---|---|
| `query` | string | Text to search for |
| `doc_type` | string (optional) | Filter by type (same values as `list_resumes`) |
| `mode` | string (optional) | `"and"` *(default)*, `"or"`, or `"regex"` — see [Search behavior](../README.md#search-behavior) |
| `limit` | integer (optional) | Maximum number of results (default `100`) |
| `offset` | integer (optional) | Number of results to skip (default `0`) |

Returns: paginated envelope — `total_count` + `items`, where each item has `path`, `filename`, `doc_type`, `match_count`, `snippet`.

---

### `list_skills`

List badge skills (technologies, tools, languages), optionally scoped to a single resume and/or filtered by a keyword query matched against the skill title.

Note: badge skills are deduplicated and shared across resumes by title, so — unlike work experiences, side projects, and education — items here do not carry a `resume_id`.

| Parameter | Type | Description |
|---|---|---|
| `resume_id` | string (optional) | Resume ID from `list_resume_summaries` |
| `query` | string (optional) | Text to search for in skill titles (case-insensitive) |
| `mode` | string (optional) | `"and"` *(default)*, `"or"`, or `"regex"` — see [Search behavior](../README.md#search-behavior) |
| `limit` | integer (optional) | Maximum number of results (default `100`) |
| `offset` | integer (optional) | Number of results to skip (default `0`) |

Returns: paginated envelope — `total_count` + `items`. `{"error": "..."}` if `resume_id` is given but not found.

---

### `get_badge_skill`

Get a single badge skill by ID.

| Parameter | Type | Description |
|---|---|---|
| `id` | string | Badge skill ID from `list_skills` |

Returns: the skill dict on success, `{"error": "..."}` if `id` is not found.

---

### `search_resumes_by_skill`

Find which resumes list one or more given badge skills. Returns resume identity and matched skill names — more token-efficient than `list_resumes` when filtering by skill. Accepts either a single skill string or a list of skills to filter by multiple at once.

| Parameter | Type | Description |
|---|---|---|
| `skill` | string or list of strings | Skill title fragment(s) to search for (case-insensitive, partial match) |
| `mode` | string (optional) | For a single skill: `"and"` *(default)*, `"or"`, or `"regex"` — see [Search behavior](../README.md#search-behavior). For a list of skills, `mode` also controls whether a resume must match EACH skill (`"and"`) or ANY skill (`"or"`); `"regex"` combines multiple skills with OR semantics. |
| `limit` | integer (optional) | Maximum number of results (default `100`) |
| `offset` | integer (optional) | Number of results to skip (default `0`) |

Returns: paginated envelope — `total_count` + `items`, where each item has `id`, `first_name`, `last_name`, `matched_skills`. An empty list, or a list of only blank strings, returns `{"error": "..."}`.

---

### `get_skill_frequency`

Return badge skills ranked by how many resumes list them, in descending order. Useful for identifying the most common technologies across all candidates.

| Parameter | Type | Description |
|---|---|---|
| `limit` | integer (optional) | Maximum number of skills to return (default `20`) |

Returns: list of `{ skill_id, skill_title, resume_count }`.

---

### `list_work_experiences`

List work experience entries, optionally scoped to a single resume, only current roles, and/or a keyword query matched against company name, position title, or achievement descriptions. Every item always includes `resume_id`, whether or not the call was scoped.

| Parameter | Type | Description |
|---|---|---|
| `resume_id` | string (optional) | Resume ID from `list_resume_summaries` |
| `query` | string (optional) | Text to match against company name, position title, or achievement descriptions (case-insensitive) |
| `current_only` | boolean (optional) | If `true`, return only roles where `end_date` is `"Present"` |
| `mode` | string (optional) | `"and"` *(default)*, `"or"`, or `"regex"` — see [Search behavior](../README.md#search-behavior) |
| `limit` | integer (optional) | Maximum number of results (default `25`) |
| `offset` | integer (optional) | Number of results to skip (default `0`) |

Returns: paginated envelope — `total_count` + `items`. `{"error": "..."}` if `resume_id` is given but not found.

---

### `get_work_experience`

Get a single work experience entry with its achievement bullets.

| Parameter | Type | Description |
|---|---|---|
| `id` | string | Work experience ID from `list_work_experiences` |

Returns: the entry dict on success, `{"error": "..."}` if `id` is not found.

---

### `list_achievements`

List achievement bullets, optionally scoped to a single resume and/or filtered by a keyword query matched against the achievement text.

Response shape depends on the arguments given, to keep the common case cheap:
- `resume_id` given, `query` omitted: bare `{id, desc}` per item (cheapest — you already know which resume these belong to).
- `query` given, and/or `resume_id` omitted: each item also includes `company_name`, `position_title`, `work_experience_id`, and `resume_id`, since that context would otherwise be unrecoverable from the achievement alone.

| Parameter | Type | Description |
|---|---|---|
| `resume_id` | string (optional) | Resume ID from `list_resume_summaries` |
| `query` | string (optional) | Text to search for in achievement descriptions (case-insensitive) |
| `mode` | string (optional) | `"and"` *(default)*, `"or"`, or `"regex"` — see [Search behavior](../README.md#search-behavior) |
| `limit` | integer (optional) | Maximum number of results (default `50`) |
| `offset` | integer (optional) | Number of results to skip (default `0`) |

Returns: paginated envelope — `total_count` + `items`. `{"error": "..."}` if `resume_id` is given but not found.

---

### `get_achievement`

Get a single achievement bullet by ID.

| Parameter | Type | Description |
|---|---|---|
| `id` | string | Achievement ID from `list_achievements` |

Returns: the achievement dict on success, `{"error": "..."}` if `id` is not found.

---

### `list_side_projects`

List side projects (personal/portfolio projects, distinct from work experience), optionally scoped to a single resume and/or matched by keyword or technology.

- If `technology` is given, projects are matched against technology names only, and each result uses a lighter shape: `id`, `name`, `description`, `matched_technologies`, `resume_id`.
- Else if `query` is given, projects are matched against name, description, or technology names, and each result includes the full nested structure plus `resume_id`.
- If both are given, `technology` takes precedence and `query` is ignored.
- If neither is given, results are the plain, unfiltered listing.

| Parameter | Type | Description |
|---|---|---|
| `resume_id` | string (optional) | Resume ID from `list_resume_summaries` |
| `query` | string (optional) | Text to match against name, description, or technology (case-insensitive) |
| `technology` | string (optional) | Technology/skill name fragment to match (case-insensitive, partial match); takes precedence over `query` |
| `mode` | string (optional) | `"and"` *(default)*, `"or"`, or `"regex"` — see [Search behavior](../README.md#search-behavior) |
| `limit` | integer (optional) | Maximum number of results (default `25`) |
| `offset` | integer (optional) | Number of results to skip (default `0`) |

Returns: paginated envelope — `total_count` + `items`. `{"error": "..."}` if `resume_id` is given but not found.

---

### `get_side_project`

Get a single side project by ID, including the technologies it demonstrates.

| Parameter | Type | Description |
|---|---|---|
| `id` | string | Side project ID from `list_side_projects` |

Returns: the project dict on success, `{"error": "..."}` if `id` is not found.

---

### `list_education`

List education entries (degree, institution, year, and relevant coursework/competencies), optionally scoped to a single resume and/or matched by keyword or competency.

- If `competency` is given, entries are matched against competency names only, and each result uses a lighter shape: `id`, `institution`, `degree`, `year`, `matched_competencies`, `resume_id`.
- Else if `query` is given, entries are matched against institution, degree, or competency names, and each result includes the full nested structure plus `resume_id`.
- If both are given, `competency` takes precedence and `query` is ignored.
- If neither is given, results are the plain, unfiltered listing.

| Parameter | Type | Description |
|---|---|---|
| `resume_id` | string (optional) | Resume ID from `list_resume_summaries` |
| `query` | string (optional) | Text to match against institution, degree, or competency (case-insensitive) |
| `competency` | string (optional) | Skill/competency name fragment to match (case-insensitive, partial match); takes precedence over `query` |
| `mode` | string (optional) | `"and"` *(default)*, `"or"`, or `"regex"` — see [Search behavior](../README.md#search-behavior) |
| `limit` | integer (optional) | Maximum number of results (default `25`) |
| `offset` | integer (optional) | Number of results to skip (default `0`) |

Returns: paginated envelope — `total_count` + `items`. `{"error": "..."}` if `resume_id` is given but not found.

---

### `get_education`

Get a single education entry by ID, including its competencies.

| Parameter | Type | Description |
|---|---|---|
| `id` | string | Education entry ID from `list_education` |

Returns: the entry dict on success, `{"error": "..."}` if `id` is not found.

---

### `get_collection_stats`

Return aggregate counts and averages across the entire loaded resume collection. Useful for a quick overview before diving into individual records.

No parameters.

Returns: `total_resumes`, `total_work_experiences`, `total_unique_skills`, `total_side_projects`, `total_education_entries`, `total_achievements`, `avg_skills_per_resume`, `avg_work_experiences_per_resume`.

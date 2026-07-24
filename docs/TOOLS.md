# MCP Tools Reference

Full parameter and return-shape reference for all 26 tools exposed by `resume-mcp-server`. All `search_*` tools — including `search_resumes` — share the same match-mode conventions: see [Search behavior](../README.md#search-behavior) in the main README. All `list_*` and `search_*` tools share the same pagination envelope and validation — see [Pagination](../README.md#pagination). Every tool's failure shape is `{"error": "..."}` — see [Error handling](../README.md#error-handling).

### `list_resume_summaries`

List all resumes as lightweight identity records. Use this first to orient and pick a `resume_id` before fetching details — much more token-efficient than `list_resumes`.

| Parameter | Type | Description |
|---|---|---|
| `limit` | integer (optional) | Maximum number of results (default `100`) |
| `offset` | integer (optional) | Number of results to skip (default `0`) |

Returns: paginated envelope — `total_count` + `items`, where each item has `id`, `first_name`, `last_name`, `email`, `phone_num`.

---

### `list_resumes`

List all documents, optionally filtered by type.

| Parameter | Type | Description |
|---|---|---|
| `doc_type` | string (optional) | `resume`, `cover_letter`, `application_material`, or `other` |
| `limit` | integer (optional) | Maximum number of results (default `100`) |
| `offset` | integer (optional) | Number of results to skip (default `0`) |

Returns: paginated envelope — `total_count` + `items`.

---

### `get_resume`

Return the full extracted text of a document. Takes a file **path**, not a `resume_id` — use `get_resume_profile` or `list_resumes` to fetch structured data by `resume_id` instead.

| Parameter | Type | Description |
|---|---|---|
| `path` | string | Relative path as returned by `list_resumes` |

Returns: `{"text": "..."}` on success, `{"error": "..."}` if `path` is not found.

---

### `get_resume_profile`

Get a resume's top-level fields (contact info, professional statement, education) without the nested work experience or badge skill lists. Prefer this over `get_resume` when you need structured contact data rather than raw text.

| Parameter | Type | Description |
|---|---|---|
| `resume_id` | string | Resume ID from `list_resume_summaries` |

Returns: the profile dict on success, `{"error": "..."}` if `resume_id` is not found.

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

### `search_resumes_by_name`

Find resumes by person name (first or last name). Returns minimal identity fields — use the returned `id` with other tools to fetch full details.

| Parameter | Type | Description |
|---|---|---|
| `query` | string | Name fragment to search for (case-insensitive, partial match) |
| `mode` | string (optional) | `"and"` *(default)*, `"or"`, or `"regex"` — see [Search behavior](../README.md#search-behavior) |
| `limit` | integer (optional) | Maximum number of results (default `100`) |
| `offset` | integer (optional) | Number of results to skip (default `0`) |

Returns: paginated envelope — `total_count` + `items`, where each item has `id`, `first_name`, `last_name`, `email`, `phone_num`.

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

### `search_skills`

Search badge skills (technologies, tools, languages) by title.

| Parameter | Type | Description |
|---|---|---|
| `query` | string | Text to search for in skill titles (case-insensitive) |
| `mode` | string (optional) | `"and"` *(default)*, `"or"`, or `"regex"` — see [Search behavior](../README.md#search-behavior) |
| `limit` | integer (optional) | Maximum number of results (default `100`) |
| `offset` | integer (optional) | Number of results to skip (default `0`) |

Returns: paginated envelope — `total_count` + `items`.

---

### `search_work_experiences`

Search work experiences by company name, position title, or achievement description bullets.
Each result includes a `resume_id` field identifying which resume the entry belongs to.

| Parameter | Type | Description |
|---|---|---|
| `query` | string | Text to search for (case-insensitive) |
| `mode` | string (optional) | `"and"` *(default)*, `"or"`, or `"regex"` — see [Search behavior](../README.md#search-behavior) |
| `limit` | integer (optional) | Maximum number of results (default `100`) |
| `offset` | integer (optional) | Number of results to skip (default `0`) |

Returns: paginated envelope — `total_count` + `items`.

---

### `list_work_experiences`

List work experience entries, optionally scoped to a single resume and/or only current roles.

| Parameter | Type | Description |
|---|---|---|
| `resume_id` | string (optional) | Resume ID from `list_resume_summaries` |
| `current_only` | boolean (optional) | If `true`, return only roles where `end_date` is `"Present"` |
| `limit` | integer (optional) | Maximum number of results (default `100`) |
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

List all achievement bullets, optionally scoped to a single resume.

| Parameter | Type | Description |
|---|---|---|
| `resume_id` | string (optional) | Resume ID from `list_resume_summaries` |
| `limit` | integer (optional) | Maximum number of results (default `100`) |
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

### `search_achievements`

Search achievement descriptions directly, returning only matching bullets with minimal parent context. More token-efficient than `search_work_experiences` when you only need matching bullets.

| Parameter | Type | Description |
|---|---|---|
| `query` | string | Text to search for in achievement descriptions (case-insensitive) |
| `resume_id` | string (optional) | Resume ID from `list_resume_summaries` to scope the search to one resume |
| `mode` | string (optional) | `"and"` *(default)*, `"or"`, or `"regex"` — see [Search behavior](../README.md#search-behavior) |
| `limit` | integer (optional) | Maximum number of results (default `100`) |
| `offset` | integer (optional) | Number of results to skip (default `0`) |

Returns: paginated envelope — `total_count` + `items`, where each item has `id`, `desc`, `company_name`, `position_title`, `work_experience_id`, `resume_id`. `{"error": "..."}` if `resume_id` is given but not found.

---

### `list_badge_skills`

List all badge skills, optionally scoped to a single resume.

| Parameter | Type | Description |
|---|---|---|
| `resume_id` | string (optional) | Resume ID from `list_resume_summaries` |
| `limit` | integer (optional) | Maximum number of results (default `100`) |
| `offset` | integer (optional) | Number of results to skip (default `0`) |

Returns: paginated envelope — `total_count` + `items`. `{"error": "..."}` if `resume_id` is given but not found.

---

### `get_badge_skill`

Get a single badge skill by ID.

| Parameter | Type | Description |
|---|---|---|
| `id` | string | Badge skill ID from `list_badge_skills` |

Returns: the skill dict on success, `{"error": "..."}` if `id` is not found.

---

### `list_side_projects`

List side projects (personal/portfolio projects, distinct from work experience) that demonstrate competency with specific technologies, optionally scoped to a single resume.

| Parameter | Type | Description |
|---|---|---|
| `resume_id` | string (optional) | Resume ID from `list_resume_summaries` |
| `limit` | integer (optional) | Maximum number of results (default `100`) |
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

### `search_side_projects`

Search side projects by name, description, or associated technology. See also `search_side_projects_by_technology` for technology-only matching with a lighter-weight response shape.
Each result includes a `resume_id` field identifying which resume the project belongs to.

| Parameter | Type | Description |
|---|---|---|
| `query` | string | Text to search for (case-insensitive) |
| `resume_id` | string (optional) | Resume ID from `list_resume_summaries` to scope the search to one resume |
| `mode` | string (optional) | `"and"` *(default)*, `"or"`, or `"regex"` — see [Search behavior](../README.md#search-behavior) |
| `limit` | integer (optional) | Maximum number of results (default `100`) |
| `offset` | integer (optional) | Number of results to skip (default `0`) |

Returns: paginated envelope — `total_count` + `items`. `{"error": "..."}` if `resume_id` is given but not found.

---

### `search_side_projects_by_technology`

Find side projects that demonstrate competency with a given technology. See also `search_side_projects` for broader name/description matching.

| Parameter | Type | Description |
|---|---|---|
| `technology` | string | Technology/skill name fragment to search for (case-insensitive, partial match) |
| `mode` | string (optional) | `"and"` *(default)*, `"or"`, or `"regex"` — see [Search behavior](../README.md#search-behavior) |
| `limit` | integer (optional) | Maximum number of results (default `100`) |
| `offset` | integer (optional) | Number of results to skip (default `0`) |

Returns: paginated envelope — `total_count` + `items`, where each item has `id`, `name`, `description`, `matched_technologies`, `resume_id`.

---

### `list_education`

List education entries (degree, institution, year, and relevant coursework/competencies), optionally scoped to a single resume.

| Parameter | Type | Description |
|---|---|---|
| `resume_id` | string (optional) | Resume ID from `list_resume_summaries` |
| `limit` | integer (optional) | Maximum number of results (default `100`) |
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

### `search_education`

Search education entries by institution, degree, or competency. See also `search_education_by_competency` for competency-only matching with a lighter-weight response shape. Each result includes a `resume_id` field identifying which resume the entry belongs to.

| Parameter | Type | Description |
|---|---|---|
| `query` | string | Text to search for (case-insensitive) |
| `resume_id` | string (optional) | Resume ID from `list_resume_summaries` to scope the search to one resume |
| `mode` | string (optional) | `"and"` *(default)*, `"or"`, or `"regex"` — see [Search behavior](../README.md#search-behavior) |
| `limit` | integer (optional) | Maximum number of results (default `100`) |
| `offset` | integer (optional) | Number of results to skip (default `0`) |

Returns: paginated envelope — `total_count` + `items`. `{"error": "..."}` if `resume_id` is given but not found.

---

### `search_education_by_competency`

Find education entries that demonstrate competency with a given skill — useful for matching a candidate's coursework/training to a specific position's requirements. See also `search_education` for broader institution/degree matching.

| Parameter | Type | Description |
|---|---|---|
| `competency` | string | Skill/competency name fragment to search for (case-insensitive, partial match) |
| `mode` | string (optional) | `"and"` *(default)*, `"or"`, or `"regex"` — see [Search behavior](../README.md#search-behavior) |
| `limit` | integer (optional) | Maximum number of results (default `100`) |
| `offset` | integer (optional) | Number of results to skip (default `0`) |

Returns: paginated envelope — `total_count` + `items`, where each item has `id`, `institution`, `degree`, `year`, `matched_competencies`, `resume_id`.

---

### `get_collection_stats`

Return aggregate counts and averages across the entire loaded resume collection. Useful for a quick overview before diving into individual records.

No parameters.

Returns: `total_resumes`, `total_work_experiences`, `total_unique_skills`, `total_side_projects`, `total_education_entries`, `total_achievements`, `avg_skills_per_resume`, `avg_work_experiences_per_resume`.

---

### `get_skill_frequency`

Return badge skills ranked by how many resumes list them, in descending order. Useful for identifying the most common technologies across all candidates.

| Parameter | Type | Description |
|---|---|---|
| `limit` | integer (optional) | Maximum number of skills to return (default `20`) |

Returns: list of `{ skill_id, skill_title, resume_count }`.

# MCP Server Registry & Tool Catalog
## Multi-Agent AI Orchestration System

**Version:** 1.0.0  
**Related:** `PRD.md`, `ARCHITECTURE.md`, `SETUP.md`

---

## 1. MCP Server Inventory

### 1.1 project_fs — Filesystem Access

| Attribute | Value |
|---|---|
| **Name** | `project_fs` |
| **Package** | `@modelcontextprotocol/server-filesystem` |
| **Transport** | stdio (via `npx`) |
| **Scope** | `/home/user/projects` (read-write) |
| **Parallel Safe** | Read: Yes / Write: No |
| **Health Check** | `list_directory` on root |

**Purpose:** Provide secure, scoped filesystem access for all agents.

**Tools:**
| Tool | Description | Parallel Safe | Risk Level |
|---|---|---|---|
| `read_file` | Read contents of a file | ✅ Yes | None |
| `write_file` | Write or overwrite a file | ❌ No (path-scoped) | High |
| `list_directory` | List files in a directory | ✅ Yes | None |
| `search_files` | Grep/search across files | ✅ Yes | None |

**Configuration:**
```yaml
mcp_servers:
  project_fs:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/home/user/projects"]
    tools:
      include: ["read_file", "write_file", "list_directory", "search_files"]
```

**Security Notes:**
- Scoped to `/home/user/projects` — cannot access `/etc`, `/root`, etc.
- `write_file` is path-scoped: parallel writes to different files are safe; same file is serialized.
- All write operations are logged to `~/.hermes/mcp_logs/project_fs.log`.

---

### 1.2 github — GitHub Integration

| Attribute | Value |
|---|---|
| **Name** | `github` |
| **Package** | `@modelcontextprotocol/server-github` |
| **Transport** | stdio (via `npx`) |
| **Auth** | `GITHUB_PERSONAL_ACCESS_TOKEN` env var |
| **Parallel Safe** | No |
| **Rate Limit** | 5,000 requests/hour (GitHub API) |

**Purpose:** Enable agents to interact with GitHub repositories, issues, and pull requests.

**Tools:**
| Tool | Description | Parallel Safe | Risk Level |
|---|---|---|---|
| `create_issue` | Create a new issue | ❌ No | Medium |
| `update_issue` | Update an existing issue | ❌ No | Medium |
| `search_issues` | Search issues and PRs | ✅ Yes | None |
| `create_pull_request` | Open a new PR | ❌ No | High |
| `get_pull_request` | Fetch PR details | ✅ Yes | None |
| `list_commits` | List commits in a branch | ✅ Yes | None |
| `create_branch` | Create a new branch | ❌ No | High |
| `search_code` | Search code across repos | ✅ Yes | None |
| `get_file_contents` | Read file from repo | ✅ Yes | None |
| `push_files` | Push multiple files | ❌ No | High |

**Configuration:**
```yaml
mcp_servers:
  github:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
    tools:
      include: ["search_issues", "get_pull_request", "list_commits", "search_code", "get_file_contents"]
      # Exclude high-risk tools by default:
      # exclude: ["create_pull_request", "push_files", "create_branch"]
```

**Security Notes:**
- Token should have minimal scopes: `repo:read`, `issues:read`.
- Write operations (`create_issue`, `create_pull_request`) require explicit user approval.
- Rate limit shared across all subagents — use caching for repeated queries.

---

### 1.3 browser — Browser Automation

| Attribute | Value |
|---|---|
| **Name** | `browser` |
| **Package** | `@modelcontextprotocol/server-puppeteer` |
| **Transport** | stdio (via `npx`) |
| **Parallel Safe** | No (single browser instance) |
| **Timeout** | 30s per navigation |

**Purpose:** Enable agents to navigate websites, take screenshots, and extract dynamic content.

**Tools:**
| Tool | Description | Parallel Safe | Risk Level |
|---|---|---|---|
| `browser_navigate` | Navigate to URL | ❌ No | Low |
| `browser_screenshot` | Take screenshot | ❌ No | Low |
| `browser_click` | Click an element | ❌ No | Low |
| `browser_evaluate` | Run JavaScript in page | ❌ No | Medium |
| `browser_get_text` | Extract visible text | ❌ No | Low |

**Configuration:**
```yaml
mcp_servers:
  browser:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-puppeteer"]
    tools:
      include: ["browser_navigate", "browser_screenshot", "browser_get_text"]
      exclude: ["browser_evaluate"]  # Security: disable arbitrary JS execution
```

**Security Notes:**
- Browser runs in sandboxed context (no local file access).
- `browser_evaluate` is disabled by default — arbitrary JS is a security risk.
- Screenshots are saved to `~/.hermes/browser_screenshots/`.
- Single instance: all browser operations are sequentialized by Hermes.

---

### 1.4 postgres — Database Access

| Attribute | Value |
|---|---|
| **Name** | `postgres` |
| **Package** | `@modelcontextprotocol/server-postgres` |
| **Transport** | stdio (via `npx`) |
| **Connection** | `postgresql://localhost:5432/mydb` |
| **Parallel Safe** | Read: Yes / Write: No |
| **Timeout** | 10s per query |

**Purpose:** Enable agents to query databases for schema inspection, data validation, and migration planning.

**Tools:**
| Tool | Description | Parallel Safe | Risk Level |
|---|---|---|---|
| `query` | Execute SELECT query | ✅ Yes | None |
| `execute` | Execute INSERT/UPDATE/DELETE | ❌ No | High |
| `get_schema` | Get table schema | ✅ Yes | None |

**Configuration:**
```yaml
mcp_servers:
  postgres:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-postgres", "postgresql://localhost:5432/mydb"]
    tools:
      include: ["query", "get_schema"]
      exclude: ["execute"]  # Disable writes by default
```

**Security Notes:**
- Use a read-only database user for agents: `GRANT SELECT ON ALL TABLES IN SCHEMA public TO agent_user;`
- `execute` tool is excluded by default — enable only for migration tasks with user approval.
- Query results are limited to 1,000 rows to prevent context overflow.
- Connection pooling: max 5 concurrent connections.

---

### 1.5 internal_api — Custom REST API

| Attribute | Value |
|---|---|
| **Name** | `internal_api` |
| **Package** | Custom (in-house MCP server) |
| **Transport** | HTTP SSE (Server-Sent Events) |
| **Endpoint** | `https://api.company.com/mcp` |
| **Auth** | Bearer token in `Authorization` header |
| **Parallel Safe** | Configurable (`supports_parallel_tool_calls: true`) |

**Purpose:** Connect agents to internal company APIs (e.g., microservices, CRM, analytics).

**Tools:**
| Tool | Description | Parallel Safe | Risk Level |
|---|---|---|---|
| `api_get` | GET request to internal endpoint | ✅ Yes | Low |
| `api_post` | POST request | ❌ No | Medium |
| `api_put` | PUT request | ❌ No | Medium |
| `api_delete` | DELETE request | ❌ No | High |
| `api_list_resources` | Discover available endpoints | ✅ Yes | None |

**Configuration:**
```yaml
mcp_servers:
  internal_api:
    url: "https://api.company.com/mcp"
    headers:
      Authorization: "Bearer ${INTERNAL_API_KEY}"
      Content-Type: "application/json"
    supports_parallel_tool_calls: true  # Enable parallel GET requests
    tools:
      include: ["api_get", "api_list_resources"]
      exclude: ["api_post", "api_put", "api_delete"]
```

**Security Notes:**
- API key stored in environment variable, never in config file.
- Write methods (`POST`, `PUT`, `DELETE`) excluded by default.
- All requests logged to `~/.hermes/mcp_logs/internal_api.log`.
- Rate limiting: respect `X-RateLimit-Remaining` header.

---

## 2. Parallel Safety Classification

### 2.1 Safety Matrix

| Server | Tool | Safe for Parallel | Overlap Detection | Notes |
|---|---|---|---|---|
| `project_fs` | `read_file` | ✅ Yes | N/A | Stateless |
| `project_fs` | `write_file` | ❌ No | Path-scoped | Same path = sequential |
| `project_fs` | `list_directory` | ✅ Yes | N/A | Stateless |
| `project_fs` | `search_files` | ✅ Yes | N/A | Stateless |
| `github` | `search_issues` | ✅ Yes | N/A | Read-only |
| `github` | `get_file_contents` | ✅ Yes | N/A | Read-only |
| `github` | `create_issue` | ❌ No | N/A | Write operation |
| `github` | `create_pull_request` | ❌ No | N/A | Write operation |
| `browser` | All tools | ❌ No | N/A | Single instance |
| `postgres` | `query` | ✅ Yes | N/A | Read-only |
| `postgres` | `execute` | ❌ No | N/A | Write operation |
| `postgres` | `get_schema` | ✅ Yes | N/A | Read-only |
| `internal_api` | `api_get` | ✅ Yes | N/A | Configurable |
| `internal_api` | `api_post` | ❌ No | N/A | Write operation |

### 2.2 Hermes Parallelization Logic

```python
# Pseudocode for Hermes Tool Parallelizer

def classify_tool_call(tool_call, server_name):
    tool_name = tool_call.name

    # 1. Check server-level parallel support
    server = get_mcp_server(server_name)
    if not server.supports_parallel_tool_calls:
        return SEQUENTIAL

    # 2. Check tool-level safety
    if tool_name in PARALLEL_SAFE_TOOLS:
        return PARALLEL

    # 3. Check path overlap for file tools
    if tool_name in PATH_SCOPED_TOOLS:
        path = extract_path(tool_call.arguments)
        if path_is_locked(path):
            return SEQUENTIAL
        else:
            lock_path(path)
            return PARALLEL

    # 4. Default to sequential for safety
    return SEQUENTIAL
```

---

## 3. Tool Catalog

### 3.1 Complete Tool Index

| # | Tool Name | Server | Description | Agent Roles |
|---|---|---|---|---|
| 1 | `read_file` | `project_fs` | Read file contents | All |
| 2 | `write_file` | `project_fs` | Write/overwrite file | Builder |
| 3 | `list_directory` | `project_fs` | List directory contents | All |
| 4 | `search_files` | `project_fs` | Search files with grep | All |
| 5 | `search_issues` | `github` | Search GitHub issues | Researcher |
| 6 | `get_pull_request` | `github` | Fetch PR details | Researcher |
| 7 | `list_commits` | `github` | List branch commits | Researcher |
| 8 | `search_code` | `github` | Search code across repos | Researcher |
| 9 | `get_file_contents` | `github` | Read file from GitHub | Researcher |
| 10 | `browser_navigate` | `browser` | Navigate to URL | Researcher |
| 11 | `browser_screenshot` | `browser` | Take screenshot | Researcher |
| 12 | `browser_get_text` | `browser` | Extract page text | Researcher |
| 13 | `query` | `postgres` | Execute SELECT query | Researcher, Executor |
| 14 | `get_schema` | `postgres` | Get table schema | Researcher |
| 15 | `api_get` | `internal_api` | GET internal API | Researcher |
| 16 | `api_list_resources` | `internal_api` | Discover endpoints | Researcher |

### 3.2 Tool Availability by Agent Role

| Tool | Orchestrator | Planner | Researcher | Builder | Executor |
|---|---|---|---|---|---|
| `read_file` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `write_file` | ❌ | ❌ | ❌ | ✅ | ❌ |
| `list_directory` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `search_files` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `search_issues` | ❌ | ✅ | ✅ | ❌ | ❌ |
| `get_pull_request` | ❌ | ✅ | ✅ | ❌ | ❌ |
| `list_commits` | ❌ | ✅ | ✅ | ❌ | ❌ |
| `search_code` | ❌ | ✅ | ✅ | ❌ | ❌ |
| `get_file_contents` | ❌ | ✅ | ✅ | ❌ | ❌ |
| `browser_navigate` | ❌ | ✅ | ✅ | ❌ | ❌ |
| `browser_screenshot` | ❌ | ✅ | ✅ | ❌ | ❌ |
| `browser_get_text` | ❌ | ✅ | ✅ | ❌ | ❌ |
| `query` | ❌ | ✅ | ✅ | ❌ | ✅ |
| `get_schema` | ❌ | ✅ | ✅ | ❌ | ❌ |
| `api_get` | ❌ | ✅ | ✅ | ❌ | ❌ |
| `api_list_resources` | ❌ | ✅ | ✅ | ❌ | ❌ |

---

## 4. Health Checks & Monitoring

### 4.1 Health Check Commands

```bash
# Check all MCP servers
hermes mcp test

# Check specific server
hermes mcp test --server project_fs

# Expected output:
# project_fs    ✅ Healthy  (12ms)
# github        ✅ Healthy  (45ms)
# browser       ⚠️ Slow     (2.3s)
# postgres      ✅ Healthy  (8ms)
# internal_api  ❌ Unhealthy (Connection timeout)
```

### 4.2 Automatic Recovery

| State | Detection | Action |
|---|---|---|
| **Healthy** | Response < 1s, no errors | Normal operation |
| **Slow** | Response 1-5s | Log warning, continue with reduced parallelism |
| **Unhealthy** | Response > 5s or error | Exclude server tools, retry connection every 30s |
| **Crashed** | Process exited | Restart server process, log incident |

### 4.3 Log Locations

| Log | Path | Rotation |
|---|---|---|
| MCP server stdout | `~/.hermes/mcp_logs/<server>.log` | 10MB × 5 files |
| MCP server stderr | `~/.hermes/mcp_logs/<server>.err` | 10MB × 5 files |
| Tool call audit | `~/.hermes/audit/tool_calls.jsonl` | 100MB × 10 files |
| Health check results | `~/.hermes/audit/health.jsonl` | 50MB × 5 files |

---

## 5. Environment Variables

| Variable | Required | Used By | Description |
|---|---|---|---|
| `GITHUB_TOKEN` | Yes (if github enabled) | `github` MCP | GitHub Personal Access Token |
| `INTERNAL_API_KEY` | Yes (if internal_api enabled) | `internal_api` MCP | API key for internal services |
| `POSTGRES_URL` | No | `postgres` MCP | Override connection string |
| `PROJECT_ROOT` | No | `project_fs` MCP | Override filesystem scope |
| `MCP_LOG_LEVEL` | No | All MCP | `debug`, `info`, `warn`, `error` |

---

## 6. Change Log

| Version | Date | Changes |
|---|---|---|
| 1.0.0 | 2026-07-31 | Initial MCP registry with 5 servers and 16 tools |

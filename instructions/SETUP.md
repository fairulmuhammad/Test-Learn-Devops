# Setup Guide
## Multi-Agent AI Orchestration System

**Version:** 1.0.0  
**Related:** `PRD.md`, `ARCHITECTURE.md`, `MCP.md`

---

## 1. Prerequisites

### 1.1 System Requirements

| Component | Minimum | Recommended |
|---|---|---|
| **OS** | Linux (Ubuntu 22.04+) | Linux (Ubuntu 24.04 LTS) |
| **CPU** | 4 cores | 8+ cores |
| **RAM** | 8 GB | 16+ GB |
| **Disk** | 20 GB SSD | 50+ GB SSD |
| **Network** | Stable internet | Low-latency (< 50ms to AI providers) |

### 1.2 Software Dependencies

```bash
# Node.js (for MCP servers)
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs

# Verify
node --version  # v22.x.x
npm --version   # 10.x.x

# Git (for worktree isolation)
sudo apt-get install -y git

# Docker (optional, for containerized subagents)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Python (for Hermes Agent)
sudo apt-get install -y python3 python3-pip python3-venv
```

### 1.3 API Keys & Credentials

| Service | Key Name | Where to Get |
|---|---|---|
| OpenRouter | `OPENROUTER_API_KEY` | https://openrouter.ai/keys |
| Anthropic | `ANTHROPIC_API_KEY` | https://console.anthropic.com/ |
| GitHub | `GITHUB_TOKEN` | https://github.com/settings/tokens |
| Internal API | `INTERNAL_API_KEY` | Your internal admin |

Store all keys in `~/.env`:
```bash
OPENROUTER_API_KEY=sk-or-v1-...
ANTHROPIC_API_KEY=sk-ant-...
GITHUB_TOKEN=ghp_...
INTERNAL_API_KEY=...
```

---

## 2. 9router Setup

### 2.1 Installation

```bash
# Clone 9router repository
git clone https://github.com/your-org/9router.git /opt/9router
cd /opt/9router

# Install dependencies
npm install

# Build
npm run build

# Create config directory
sudo mkdir -p /etc/9router
sudo chown $USER:$USER /etc/9router
```

### 2.2 Configuration (Combos)

**9router config lives in `~/.9router/db/data.sqlite`** (combos/providers tables), managed via the 9router UI or its local API (`/api/combos` with CLI token auth). There is NO `/etc/9router/config.json` in this install.

**Combo naming:** names may only contain `letters, numbers, -, _ and .` — `plan` style names are REJECTED (400). Use plain names: `plan`, `research`, `code`, `cheap`. The model id exposed in `/v1/models` = combo name.

**Combos created for this system (2026-07-31):**

```json
{
  "plan":     { "models": ["oc/big-pickle", "cf/@cf/deepseek-ai/deepseek-r1-distill-qwen-32b", "oc/nemotron-3-ultra-free"] },
  "research": { "models": ["oc/deepseek-v4-flash-free", "cf/@cf/mistralai/mistral-small-3.1-24b-instruct"] },
  "code":     { "models": ["cf/@cf/qwen/qwen2.5-coder-32b-instruct", "oc/big-pickle", "oc/deepseek-v4-flash-free"] },
  "cheap":    { "models": ["cf/@cf/meta/llama-3.3-70b-instruct-fp8-fast", "oc/nemotron-3-ultra-free"] }
}
```

**Model availability note:** the doc example models (`claude-opus-4-7`, `claude-sonnet-4-5`, `haiku-4`, `gpt-4.1`) are NOT reachable from this server — `ds/*` returns 402 (no credit), `kr/*`/`cl/*` fail auth, `nara/*` + `openrouter/*:free` are 429 rate-limited, `ca-prod/*` 401. Working providers verified live: `oc/*` (openclaw pool), `cf/*` (Cloudflare free tier). Re-map combos only to models that return 200 in `curl /v1/chat/completions`.

### 2.3 Systemd Service

Create `/etc/systemd/system/9router.service`:

```ini
[Unit]
Description=9router AI Model Router
After=network.target

[Service]
Type=simple
User=ai-user
WorkingDirectory=/opt/9router
EnvironmentFile=/home/ai-user/.env
ExecStart=/usr/bin/node /opt/9router/dist/index.js
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable 9router
sudo systemctl start 9router
sudo systemctl status 9router

# Verify endpoint
curl http://localhost:20128/v1/models
```

---

## 3. Hermes Agent Setup

### 3.1 Installation

```bash
# Install Hermes Agent
pip install hermes-agent

# Or install from source
git clone https://github.com/your-org/hermes-agent.git
cd hermes-agent
pip install -e .

# Verify
hermes --version
```

### 3.2 Directory Structure

```bash
mkdir -p ~/.hermes/{sessions,memory,mcp_logs,skills,errors}
touch ~/.hermes/config.yaml
touch ~/.hermes/SOUL.md
```

### 3.3 Configuration

Create `~/.hermes/config.yaml`:

```yaml
# ═══════════════════════════════════════════════════════════════════════════════
# HERMES AGENT — MULTI-AGENT ORCHESTRATION CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

# ─── Core Provider (Orchestrator) ─────────────────────────────────────────────
# The Orchestrator uses the user's main model (custom:wannadev → 9router combo 'premium-reques').
provider: "custom:wannadev"
model: "premium-reques"
base_url: "http://127.0.0.1:20128/v1"

# ─── Delegation Engine ────────────────────────────────────────────────────────
# All subagents route through 9router (inherit parent provider). Applied 2026-07-31.
delegation:
  # Default subagent model. NOTE: single value only — Hermes has NO per-role
  # model routing. Every child gets this combo regardless of role.
  model: "research"

  # Parallelism controls
  max_concurrent_children: 5        # Max parallel subagents per batch
  max_async_children: 3             # Max background subagents (non-blocking)
  max_spawn_depth: 2                # 2 = orchestrator → leaf chains
  orchestrator_enabled: true        # role="orchestrator" allowed
  max_iterations: 50                # Max tool turns per subagent
  child_timeout_seconds: 600        # 10 min wall-clock cap per child (0 = no cap)

  # false = subagents AUTO-DENY dangerous commands + audit log. Subagent threads
  # cannot prompt the user (parent TUI owns stdin). true = auto-approve.
  subagent_auto_approve: false

  # Inherit parent's MCP toolsets to children (default true)
  inherit_mcp_toolsets: true

# ─── Toolsets ─────────────────────────────────────────────────────────────────
# Enable ALL native Hermes tools. The 'delegate' toolset is REQUIRED for multi-agent.
toolsets:
  - core          # Basic agent operations
  - terminal      # Shell command execution
  - file          # File read/write/search
  - web           # Web search and extraction
  - browser       # Browser automation
  - code_execution # Sandbox code execution
  - delegate      # REQUIRED: Subagent spawning
  - todo          # Task tracking
  - memory        # Long-term memory
  - skills        # Reusable skill modules

# ─── MCP Servers ──────────────────────────────────────────────────────────────
# External tool servers accessible to all agents (when inherit_mcp_toolsets: true)
mcp_servers:
  # 1. Filesystem Access — Scoped to project directory
  project_fs:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/home/user/projects"]
    tools:
      include: ["read_file", "write_file", "list_directory", "search_files"]

  # 2. GitHub Integration — Read-only by default
  github:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
    tools:
      include: ["search_issues", "get_pull_request", "list_commits", "search_code", "get_file_contents"]
      exclude: ["create_pull_request", "push_files", "create_branch"]  # Enable manually for write ops

  # 3. Browser Automation — Single instance, sequential only
  browser:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-puppeteer"]
    tools:
      include: ["browser_navigate", "browser_screenshot", "browser_get_text"]
      exclude: ["browser_evaluate"]  # Security: disable arbitrary JS

  # 4. PostgreSQL — Read-only by default
  postgres:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-postgres", "postgresql://localhost:5432/mydb"]
    tools:
      include: ["query", "get_schema"]
      exclude: ["execute"]  # Enable manually for migrations

  # 5. Internal API — Custom REST endpoints with parallel support
  internal_api:
    url: "https://api.company.com/mcp"
    headers:
      Authorization: "Bearer ${INTERNAL_API_KEY}"
      Content-Type: "application/json"
    supports_parallel_tool_calls: true  # Enable parallel GET requests
    tools:
      include: ["api_get", "api_list_resources"]
      exclude: ["api_post", "api_put", "api_delete"]

# ─── Loop Guardrails ──────────────────────────────────────────────────────────
# Prevent runaway loops and excessive costs.
loop_caps:
  max_web_searches: 10
  max_subagents: 10
  max_terminal_commands: 20
  max_file_writes: 50

# ─── Memory & Persistence ─────────────────────────────────────────────────────
memory:
  enabled: true
  backend: "vector"  # or "sqlite", "redis"
  path: "~/.hermes/memory"
  max_entries: 10000

# ─── Logging ──────────────────────────────────────────────────────────────────
logging:
  level: "info"
  file: "~/.hermes/sessions/session.log"
  mcp_logs: "~/.hermes/mcp_logs"
  audit_tools: true
```

### 3.4 Global Orchestrator Identity

Create `~/.hermes/SOUL.md`:

```markdown
# IDENTITY
You are an AI orchestrator managing a team of specialized subagents.
Your primary tool is `delegate_task` for parallel delegation.

# CORE BEHAVIOR
When given a complex task:
1. FIRST, plan the work by delegating to a Planner subagent
2. THEN, fan out independent subtasks to Researcher subagents in parallel
3. NEXT, fan out implementation to Builder subagents in parallel
4. FINALLY, verify with an Executor subagent
5. SYNTHESIZE all results into a coherent final answer

# RULES
- Always use parallel delegation when subtasks are independent.
- Never do sequential work that could be parallel.
- Never write code or run commands directly — always delegate to the appropriate role.
- Always synthesize results before presenting to the user.
- Always update `todo` and `memory` after task completion.
- Always ask for user approval before destructive operations (delete, overwrite, deploy).

# MODEL ROUTING
- Orchestrator (you): plan
- Planner: plan
- Researcher: research
- Builder: code
- Executor: code

# OUTPUT FORMAT
For complex tasks, present:
1. What was done (high-level summary)
2. Which agents were involved
3. What files were changed
4. Test/verification results
5. Next steps or follow-up tasks

# PROJECT DOCUMENTATION
Refer to these files for architecture and workflow guidance:
- PRD.md — Product requirements
- ARCHITECTURE.md — System architecture
- AGENTS.md — Agent roles and delegation protocol
- MCP.md — MCP server registry
- WORKFLOWS.md — Common workflow patterns
- PROMPTS.md — Prompt templates and anti-patterns
```

---

## 4. Project Setup

### 4.1 Per-Project Configuration

In each project directory, create:

```bash
# Project-specific agent definitions
touch AGENTS.md

# Project context for all subagents
touch PROJECT_CONTEXT.md
```

### 4.2 AGENTS.md (Project Root)

See `AGENTS.md` in the documentation suite for the full template.

Quick start version:

```markdown
# Agent Definitions for [Project Name]

## Available Roles
- **Planner:** Architecture and task decomposition (plan)
- **Researcher:** Information gathering (research)
- **Builder:** Code implementation (code)
- **Executor:** Testing and verification (code)

## Delegation Protocol
1. Orchestrator receives request
2. Spawns Planner for complex tasks
3. Fans out Researchers in parallel
4. Fans out Builders in parallel (after research)
5. Spawns Executor for verification
6. Orchestrator synthesizes and delivers

## Parallel Rules
- Independent file edits → Parallel
- Same file edits → Sequential
- Terminal commands → Sequential
- Read-only operations → Parallel
```

### 4.3 PROJECT_CONTEXT.md (Project Root)

```markdown
# Project Context

## Overview
[Project name and one-line description]

## Tech Stack
- Language: [e.g., TypeScript]
- Framework: [e.g., Express.js]
- Database: [e.g., PostgreSQL]
- Testing: [e.g., Jest]
- Package Manager: [e.g., npm]

## Directory Structure
```
src/
  auth/      — Authentication logic
  routes/    — API endpoints
  db/        — Database queries
  middleware/ — Express middleware
tests/       — Test suites
docs/        — Documentation
```

## Conventions
- Use async/await, never callbacks
- Validate inputs with Zod
- Use AppError for all errors
- JSDoc on public functions
- Tests for every endpoint

## Key Dependencies
- express, jose, bcrypt, zod, pg

## Environment Variables
- DATABASE_URL
- JWT_SECRET
- PORT
```

---

## 5. MCP Server Installation

### 5.1 Install MCP Packages

```bash
# Filesystem server
npm install -g @modelcontextprotocol/server-filesystem

# GitHub server
npm install -g @modelcontextprotocol/server-github

# Browser server
npm install -g @modelcontextprotocol/server-puppeteer

# PostgreSQL server
npm install -g @modelcontextprotocol/server-postgres

# Verify installations
npx -y @modelcontextprotocol/server-filesystem --help
```

### 5.2 PostgreSQL Setup (Optional)

```bash
# Create read-only user for agents
sudo -u postgres psql -c "CREATE USER agent_user WITH PASSWORD 'secure_password';"
sudo -u postgres psql -c "GRANT CONNECT ON DATABASE mydb TO agent_user;"
sudo -u postgres psql -c "GRANT USAGE ON SCHEMA public TO agent_user;"
sudo -u postgres psql -c "GRANT SELECT ON ALL TABLES IN SCHEMA public TO agent_user;"
sudo -u postgres psql -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO agent_user;"
```

### 5.3 Browser Server Dependencies

```bash
# Puppeteer requires Chrome/Chromium
sudo apt-get install -y chromium-browser

# Set environment variable
export PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser
```

---

## 6. Validation & Testing

### 6.1 9router Validation

```bash
# Check 9router is running
curl http://localhost:20128/v1/models | jq

# Test each combo
curl http://localhost:20128/v1/chat/completions   -H "Authorization: Bearer $9ROUTER_API_KEY"   -H "Content-Type: application/json"   -d '{
    "model": "cheap",
    "messages": [{"role": "user", "content": "Say hello"}]
  }' | jq
```

### 6.2 Hermes Validation

```bash
# Check config + missing/outdated options
hermes config check

# List active toolsets
hermes tools --list

# List MCP servers
hermes mcp list

# Test a specific MCP server connection
hermes mcp test <server_name>
```

### 6.3 Single-Agent Test

```bash
# Test direct query (no delegation)
hermes chat -q "What is the capital of France?"

# Expected: Direct answer without subagent spawn
```

### 6.4 Multi-Agent Test

```bash
# Test parallel delegation
hermes chat -q "Research these 3 topics in parallel: 1) Best Node.js frameworks 2) PostgreSQL indexing strategies 3) Docker security best practices. Synthesize the results."

# Expected behavior:
# 1. Orchestrator recognizes parallel nature
# 2. Spawns 3 Researcher subagents concurrently
# 3. Shows real-time progress for each
# 4. Synthesizes results into one report
```

### 6.5 Build Pipeline Test

```bash
# Test nested orchestration
hermes chat -q "Create a simple Express middleware that logs request duration. Use Planner for design, Builder for implementation, and Executor for testing."

# Expected behavior:
# 1. Orchestrator spawns Planner
# 2. Planner returns design
# 3. Orchestrator spawns Builder
# 4. Builder writes middleware.ts
# 5. Orchestrator spawns Executor
# 6. Executor runs tests
# 7. Orchestrator presents final report
```

---

## 7. Troubleshooting

### 7.1 9router Issues

| Symptom | Cause | Fix |
|---|---|---|
| `Connection refused` | 9router not running | `sudo systemctl start 9router` |
| `Invalid model` | Combo not defined | Check `/etc/9router/config.json` combos |
| `Rate limited` | Too many requests | Increase `rateLimiting.requestsPerMinute` |
| `Timeout` | Model provider slow | Increase `providers[].timeout` or enable fallback |

### 7.2 Hermes Issues

| Symptom | Cause | Fix |
|---|---|---|
| `delegate_task not found` | `delegate` toolset not enabled | Add `- delegate` to `toolsets` in config |
| `MCP server unhealthy` | Server process crashed | Check `~/.hermes/mcp_logs/<server>.err` |
| `Subagent timeout` | Task too complex | Increase `child_timeout_seconds` or split task |
| `Context overflow` | Too many parallel results | Reduce `max_concurrent_children` or summarize earlier |
| `File write conflict` | Two Builders editing same file | Hermes auto-queues; check `AGENTS.md` path rules |

### 7.3 MCP Issues

| Symptom | Cause | Fix |
|---|---|---|
| `npx command not found` | Node.js not installed | Reinstall Node.js 22+ |
| `GITHUB_PERSONAL_ACCESS_TOKEN missing` | Env var not set | Add to `~/.env` and reload |
| `browser_navigate timeout` | Chromium not installed | `sudo apt-get install chromium-browser` |
| `postgres connection refused` | DB not running | `sudo systemctl start postgresql` |
| `internal_api 401` | API key invalid | Verify `INTERNAL_API_KEY` in `~/.env` |

---

## 8. Upgrade Path

### 8.1 From Single-Agent to Multi-Agent

If you have an existing Hermes single-agent setup:

```bash
# 1. Backup existing config
cp ~/.hermes/config.yaml ~/.hermes/config.yaml.backup

# 2. Add delegation block (see Section 3.3)
# 3. Add `delegate` to toolsets list
# 4. Add MCP servers (see Section 3.3)
# 5. Create SOUL.md (see Section 3.4)
# 6. Validate: hermes config check
# 7. Test: hermes chat -q "Research X and Y in parallel"
```

### 8.2 Adding New MCP Servers

```bash
# 1. Install the package
npm install -g @modelcontextprotocol/server-<name>

# 2. Add to ~/.hermes/config.yaml under mcp_servers:
#    <name>:
#      command: "npx"
#      args: ["-y", "@modelcontextprotocol/server-<name>"]
#      tools:
#        include: ["tool1", "tool2"]

# 3. Validate
hermes mcp test --server <name>
```

---

## 9. Quick Reference

### 9.1 File Locations

| File | Path | Purpose |
|---|---|---|
| 9router config | `/etc/9router/config.json` | Model combos and providers |
| Hermes config | `~/.hermes/config.yaml` | Agent orchestration settings |
| Orchestrator identity | `~/.hermes/SOUL.md` | Global system prompt |
| Project agents | `./AGENTS.md` | Per-project agent definitions |
| Project context | `./PROJECT_CONTEXT.md` | Per-project tech stack and conventions |
| Session logs | `~/.hermes/sessions/` | Conversation history |
| MCP logs | `~/.hermes/mcp_logs/` | Server stdout/stderr |
| Memory | `~/.hermes/memory/` | Vector database entries |

### 9.2 Key Commands

```bash
# 9router
sudo systemctl {start|stop|restart|status} 9router
journalctl -u 9router -f

# Hermes
hermes config check
hermes tools --list
hermes mcp list
hermes mcp test <server_name>
hermes chat -q "<prompt>"
hermes chat --interactive

# Debug
hermes logs --tail 100
hermes sessions --list
hermes sessions --show <session_id>
```

### 9.3 Environment Variables

```bash
# Required
export OPENROUTER_API_KEY="sk-or-v1-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GITHUB_TOKEN="ghp_..."

# Optional
export INTERNAL_API_KEY="..."
export MCP_LOG_LEVEL="info"
export HERMES_CONFIG_PATH="~/.hermes/config.yaml"
```

---

## 10. Change Log

| Version | Date | Changes |
|---|---|---|
| 1.0.0 | 2026-07-31 | Initial setup guide for 9router + Hermes multi-agent orchestration |

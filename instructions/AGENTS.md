# Agent Registry & Delegation Protocol
## Multi-Agent AI Orchestration System

**Version:** 1.0.0  
**Related:** `PRD.md`, `ARCHITECTURE.md`, `PROMPTS.md`

---

## 1. Agent Registry

### 1.1 Orchestrator (Master Agent)

| Attribute | Value |
|---|---|
| **Name** | `orchestrator` |
| **Model** | `premium-reques` |
| **Role Type** | `master` (cannot be spawned by other agents) |
| **Max Depth** | 0 (root only) |
| **Identity File** | `~/.hermes/SOUL.md` |
| **Context Window** | 200K tokens (claude-opus-4-7) |

**Responsibilities:**
1. Receive and parse all user requests.
2. Classify task complexity (simple vs. complex vs. architectural).
3. Decide execution strategy: direct handling, single delegation, or multi-agent fan-out.
4. Spawn Planner subagent for tasks requiring architecture or decomposition.
5. Fan out Researcher subagents for information gathering.
6. Fan out Builder subagents for implementation.
7. Spawn Executor subagent for verification and testing.
8. Synthesize results from all children into a coherent final response.
9. Handle failures, retries, and partial results.
10. Maintain session state and cross-task memory.

**Decision Tree:**
```
User Request
    │
    ├──→ Simple query ("What is the capital of France?")
    │      └──→ Handle directly (no delegation)
    │
    ├──→ Research task ("Find the best auth libraries")
    │      └──→ Fan out 1-3 Researcher subagents in parallel
    │
    ├──→ Build task ("Create a login form")
    │      └──→ Spawn Planner → Fan out Builders → Spawn Executor
    │
    └──→ Complex project ("Build a full auth module")
           └──→ Spawn Planner → Nested orchestration tree
```

**Allowed Tools:**
- `delegate_task` — Spawn subagents (PRIMARY TOOL)
- `read_file` — Inspect files for context
- `search_files` — Grep codebase
- `todo` — Track task progress
- `memory` — Read/write cross-session knowledge
- `skills` — Load reusable skill modules

**Forbidden Actions:**
- Never write code directly (always delegate to Builder).
- Never run terminal commands directly (always delegate to Executor).
- Never do sequential work that could be parallel.

---

### 1.2 Planner (Subagent)

| Attribute | Value |
|---|---|
| **Name** | `planner` |
| **Model** | `plan` |
| **Role Type** | `orchestrator` (CAN spawn further subagents) |
| **Max Depth** | 1 (can spawn leaf agents) |
| **Spawned By** | Orchestrator only |
| **Timeout** | 300s |

**Responsibilities:**
1. Analyze the task requirements thoroughly.
2. Decompose the task into atomic, independently executable subtasks.
3. Define dependencies between subtasks (Directed Acyclic Graph).
4. Assign the correct agent role to each subtask.
5. Estimate token budgets and iteration counts per subtask.
6. Identify risks and propose mitigation strategies.
7. Return a structured plan that the Orchestrator can execute.

**Output Format (MANDATORY):**
```markdown
# Plan: <Task Name>

## Overview
<Brief description of what needs to be built>

## Subtasks

### Task 1: <Name>
- **ID:** T1
- **Role:** researcher
- **Model:** research
- **Description:** <What to do>
- **Dependencies:** None
- **Estimated Tokens:** 3K
- **Files to Read:** ["src/config.ts", "docs/auth.md"]

### Task 2: <Name>
- **ID:** T2
- **Role:** builder
- **Model:** code
- **Description:** <What to build>
- **Dependencies:** [T1]
- **Estimated Tokens:** 5K
- **Files to Write:** ["src/auth/jwt.ts"]

## Dependency Graph
```
T1 (research) ──→ T2 (build) ──→ T4 (test)
T3 (research) ──→ T2 (build)
```

## Risks
- <Risk 1> → <Mitigation 1>
- <Risk 2> → <Mitigation 2>
```

**Allowed Tools:**
- `read_file` — Inspect existing codebase
- `search_files` — Find patterns and references
- `web_search` — Research external libraries
- `delegate_task` — Spawn leaf Researcher agents for deep investigation
- `todo` — Track planning progress

**Constraints:**
- Maximum 10 subtasks per plan.
- Maximum 3 levels of dependency depth.
- Must specify `files_to_read` for every Builder task.
- Must flag tasks requiring user approval (destructive operations).

---

### 1.3 Researcher (Subagent)

| Attribute | Value |
|---|---|
| **Name** | `researcher` |
| **Model** | `research` |
| **Role Type** | `leaf` (NO further delegation) |
| **Max Depth** | Terminal node |
| **Spawned By** | Orchestrator, Planner |
| **Timeout** | 180s |

**Responsibilities:**
1. Gather comprehensive information on the assigned topic.
2. Search the local codebase for relevant patterns.
3. Search the web for documentation, best practices, and examples.
4. Use browser tools if deep page inspection is needed.
5. Summarize findings with clear citations.
6. Return structured research notes, not raw dumps.

**Output Format (MANDATORY):**
```markdown
# Research: <Topic>

## Summary
<2-3 sentence executive summary>

## Findings

### 1. <Finding Title>
**Source:** <file_path> or <url>
**Relevance:** High / Medium / Low
**Details:** <What was found>
**Code Example:**
```typescript
// relevant code snippet
```

## Recommendations
1. <Recommendation with justification>
2. <Recommendation with justification>

## Sources
- [Source 1](url_or_path)
- [Source 2](url_or_path)
```

**Allowed Tools:**
- `read_file` — Read local files
- `search_files` — Grep codebase
- `web_search` — Search the internet
- `web_extract` — Extract content from URLs
- `browser_tool` — Navigate and inspect web pages
- `memory` — Store findings for future reference

**Constraints:**
- Maximum 5 web searches per task.
- Maximum 10 file reads per task.
- Must cite ALL sources.
- Must not write files.
- Must not execute terminal commands.

---

### 1.4 Builder (Subagent)

| Attribute | Value |
|---|---|
| **Name** | `builder` |
| **Model** | `code` |
| **Role Type** | `leaf` (NO further delegation) |
| **Max Depth** | Terminal node |
| **Spawned By** | Orchestrator, Planner |
| **Timeout** | 300s |

**Responsibilities:**
1. Implement features according to specification.
2. Write clean, documented, and tested code.
3. Create new files and directories as needed.
4. Modify existing files with minimal diff footprint.
5. Follow project coding standards and conventions.
6. Return a complete list of all files modified or created.

**Output Format (MANDATORY):**
```markdown
# Build Report: <Feature Name>

## Files Created
- `src/auth/jwt.ts` — JWT token generation and validation
- `src/auth/bcrypt.ts` — Password hashing utilities

## Files Modified
- `src/index.ts` — Added auth middleware import

## Code Quality
- **Linting:** Pass (npm run lint)
- **Type Check:** Pass (npx tsc --noEmit)
- **Test Coverage:** N/A (tests delegated to Executor)

## Diff Summary
```diff
+ src/auth/jwt.ts (45 lines)
+ src/auth/bcrypt.ts (28 lines)
~ src/index.ts (+3 lines)
```

## Notes
- <Any important decisions or trade-offs>
```

**Allowed Tools:**
- `read_file` — Read existing code for context
- `write_file` — Create new files
- `patch` — Modify existing files
- `terminal_tool` — Run linting, type checks
- `code_execution` — Run quick validation scripts

**Constraints:**
- Must run `npm run lint` or equivalent after writing code.
- Must not delete files without explicit user approval.
- Must not modify files outside the assigned scope.
- Must handle errors gracefully (no partial writes).

---

### 1.5 Executor (Subagent)

| Attribute | Value |
|---|---|
| **Name** | `executor` |
| **Model** | `code` |
| **Role Type** | `leaf` (NO further delegation) |
| **Max Depth** | Terminal node |
| **Spawned By** | Orchestrator only |
| **Timeout** | 600s |

**Responsibilities:**
1. Run test suites and report results.
2. Execute build commands and check for errors.
3. Run deployment scripts if configured.
4. Verify that the system works end-to-end.
5. Capture logs, screenshots, and metrics.
6. Report pass/fail status with detailed output.

**Output Format (MANDATORY):**
```markdown
# Execution Report: <Task Name>

## Commands Run
1. `npm test` — Exit code: 0
2. `npm run build` — Exit code: 0

## Test Results
- **Total:** 24 tests
- **Passed:** 24
- **Failed:** 0
- **Skipped:** 0
- **Duration:** 3.2s

## Build Results
- **Status:** ✅ Success
- **Output:** `dist/` (142 KB)
- **Warnings:** 0

## Logs
```
<relevant log output>
```

## Verification
- [x] Unit tests pass
- [x] Build succeeds
- [x] No TypeScript errors
- [ ] Integration tests (not configured)

## Conclusion
✅ All checks passed. Ready for deployment.
```

**Allowed Tools:**
- `terminal_tool` — Run shell commands
- `code_execution` — Run scripts in sandbox
- `process_registry` — Manage long-running processes
- `read_file` — Read logs and config files

**Constraints:**
- Must not write code (only run existing code).
- Must not modify files.
- Must timeout commands after 300s.
- Must report exit codes for every command.
- Must flag security-sensitive commands for approval.

---

## 2. Delegation Protocol

### 2.1 The 7-Step Orchestration Workflow

This is the canonical workflow for ALL complex tasks. The Orchestrator MUST follow this sequence.

```
Step 1: RECEIVE
├─ User submits request
├─ Orchestrator parses intent and complexity
└─ Decision: Direct handle OR Delegate

Step 2: PLAN (if complex)
├─ Orchestrator spawns Planner subagent
├─ Planner analyzes codebase and requirements
├─ Planner returns structured task DAG
└─ Orchestrator validates plan completeness

Step 3: RESEARCH (parallel)
├─ Orchestrator identifies information gaps
├─ Orchestrator fans out Researcher subagents (1-N)
├─ Researchers work in parallel (max 5 concurrent)
├─ Researchers return findings with citations
└─ Orchestrator collects and deduplicates results

Step 4: BUILD (parallel, after research)
├─ Orchestrator fans out Builder subagents (1-N)
├─ Builders receive specifications + research results
├─ Builders work in parallel on independent files
├─ Hermes path-overlap detection prevents conflicts
├─ Builders return file lists and diffs
└─ Orchestrator verifies no merge conflicts

Step 5: EXECUTE (sequential, after build)
├─ Orchestrator spawns Executor subagent
├─ Executor runs tests, builds, linting
├─ Executor returns pass/fail report
└─ Orchestrator assesses build health

Step 6: SYNTHESIZE
├─ Orchestrator merges all subagent outputs
├─ Orchestrator resolves contradictions
├─ Orchestrator formats final response
└─ Orchestrator updates `todo` and `memory`

Step 7: DELIVER
├─ Orchestrator presents final result to user
├─ Include: What was done, what files changed, test results
├─ Offer: Next steps, rollback instructions, or follow-up tasks
└─ Archive session to `~/.hermes/sessions/`
```

### 2.2 Parallel Execution Rules

| Rule | Condition | Action |
|---|---|---|
| **R1** | Tasks are independent (no shared files, no dependencies) | **PARALLEL** — Fan out immediately |
| **R2** | Tasks read the same files but write to different files | **PARALLEL** — Safe, read-only overlap |
| **R3** | Tasks write to the same file or overlapping paths | **SEQUENTIAL** — Queue second task after first completes |
| **R4** | Tasks have explicit dependencies (T2 needs T1 output) | **SEQUENTIAL** — Wait for dependency completion |
| **R5** | Tasks use terminal commands that modify shared state | **SEQUENTIAL** — Terminal is stateful |
| **R6** | Tasks use browser automation | **SEQUENTIAL** — Browser is single-session |
| **R7** | Tasks use MCP servers with `supports_parallel_tool_calls: true` | **PARALLEL** — Server handles concurrency |

### 2.3 Communication Protocol

**Parent → Child (Task Assignment):**
```json
{
  "task_id": "research_auth_001",
  "role": "researcher",
  "model": "research",
  "instruction": "Research the best JWT libraries for Node.js in 2026. Focus on: security audits, bundle size, TypeScript support. Return a ranked list with pros/cons.",
  "context": {
    "project_type": "Node.js/Express",
    "existing_deps": ["express", "typescript"],
    "constraints": ["must support ES modules", "< 100KB bundle size"]
  },
  "tools": ["web_search", "web_extract", "read_file"],
  "timeout_seconds": 180,
  "max_iterations": 20
}
```

**Child → Parent (Result Return):**
```json
{
  "task_id": "research_auth_001",
  "status": "completed",
  "result": "# Research: JWT Libraries...",
  "files_read": ["package.json"],
  "files_written": [],
  "commands_run": [],
  "token_usage": {"input": 1200, "output": 3400},
  "duration_seconds": 45
}
```

**Parent → User (Final Synthesis):**
```markdown
## Task Complete: Auth Module Research

I delegated research to 3 parallel Researcher agents. Here are the synthesized findings:

### Top Recommendation: `jose`
- **Security:** Passed all 2026 audits
- **Size:** 42KB (meets < 100KB constraint)
- **ESM:** Native support
- **Source:** [npm](https://npm.im/jose), [audit report](...)

### Alternatives
1. `jsonwebtoken` — Larger (89KB), more mature, fewer audits recently
2. `paseto` — Newer standard, smaller ecosystem

### Next Step
Shall I proceed to build the auth module using `jose`?
```

---

## 3. Handoff Procedures

### 3.1 Orchestrator → Planner Handoff

**Trigger:** Task complexity > threshold (requires architecture or >3 files modified).

**Procedure:**
1. Orchestrator creates task description with:
   - User's original request
   - Project context (tech stack, conventions)
   - Constraints and non-goals
2. Orchestrator calls `delegate_task(role="planner", ...)`.
3. Planner receives task and begins analysis.
4. Planner returns structured plan.
5. Orchestrator validates plan (checks for missing dependencies, impossible constraints).
6. If valid, Orchestrator proceeds to Step 3 (Research).
7. If invalid, Orchestrator sends feedback to Planner for revision (max 2 revisions).

### 3.2 Orchestrator → Researcher Handoff

**Trigger:** Information gaps identified in plan or user request.

**Procedure:**
1. Orchestrator creates batch of research tasks.
2. Orchestrator calls `delegate_task(tasks=[...])` with all research tasks.
3. Hermes Delegation Manager fans out tasks to ThreadPoolExecutor.
4. Researchers execute in parallel (up to 5 concurrent).
5. As each Researcher completes, result is streamed back to Orchestrator.
6. Orchestrator waits for ALL researchers to complete before proceeding.
7. Orchestrator deduplicates and synthesizes findings.

### 3.3 Orchestrator → Builder Handoff

**Trigger:** Plan is ready and research is complete.

**Procedure:**
1. Orchestrator creates batch of build tasks with:
   - File paths to create/modify
   - Specification from Planner
   - Research results for context
2. Orchestrator calls `delegate_task(tasks=[...])`.
3. Hermes checks path overlaps:
   - No overlap → Parallel execution
   - Overlap → Sequential queue
4. Builders execute and return file lists + diffs.
5. Orchestrator verifies no conflicts (file hashes, git status).

### 3.4 Orchestrator → Executor Handoff

**Trigger:** Build phase is complete.

**Procedure:**
1. Orchestrator creates execution task with:
   - Commands to run (tests, build, lint)
   - Expected outcomes
   - Timeout (default 600s)
2. Orchestrator calls `delegate_task(role="executor", ...)`.
3. Executor runs commands and captures output.
4. Executor returns structured report.
5. Orchestrator assesses:
   - All pass → Deliver success to user
   - Some fail → Decide: retry, fix, or escalate to user

---

## 4. Agent Lifecycle State Machine

```
┌─────────┐    spawn     ┌──────────┐
│  IDLE   │─────────────→│ RUNNING  │
└─────────┘              └────┬─────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
        ┌─────────┐    ┌─────────┐    ┌─────────┐
        │COMPLETED│    │  FAILED │    │ TIMEOUT │
        │(success)│    │(error)  │    │(retry?) │
        └────┬────┘    └────┬────┘    └────┬────┘
             │              │              │
             ▼              ▼              ▼
        ┌─────────┐    ┌─────────┐    ┌─────────┐
        │RESULT   │    │RETRY    │    │RETRY    │
        │RETURNED │    │(x1)     │    │(x1)     │
        └─────────┘    └────┬────┘    └────┬────┘
                            │              │
                            ▼              ▼
                      ┌─────────┐    ┌─────────┐
                      │COMPLETED│    │  FAILED │
                      │(retry)  │    │(final)  │
                      └─────────┘    └────┬────┘
                                          │
                                          ▼
                                    ┌─────────┐
                                    │ESCALATE │
                                    │TO USER  │
                                    └─────────┘
```

---

## 5. Anti-Patterns

### ❌ DO NOT

1. **Never spawn a Builder to do research.** Builders write code; Researchers gather info. Role confusion wastes tokens.
2. **Never run 5 Builders on the same file.** Path-overlap detection will serialize them anyway, but the spawn overhead is wasted.
3. **Never skip the Planner for complex tasks.** Direct fan-out without a plan leads to inconsistent architecture.
4. **Never let a leaf agent delegate.** Leaf agents (Researcher, Builder, Executor) must NOT call `delegate_task`. If they need help, they should return a partial result and let the parent re-delegate.
5. **Never synthesize before all children complete.** Partial synthesis leads to incomplete or contradictory responses.
6. **Never ignore tool errors.** Every tool error must be logged, retried, or escalated.
7. **Never hardcode model names.** Always use combo aliases (`research`, not a raw provider model id).

### ✅ DO

1. **Always plan first, execute second.**
2. **Always fan out independent tasks in parallel.**
3. **Always cite sources in Researcher outputs.**
4. **Always run lint/type-check after Builder writes code.**
5. **Always report exit codes in Executor outputs.**
6. **Always update `todo` and `memory` after task completion.**
7. **Always ask user approval for destructive operations.**

---

## 6. Change Log

| Version | Date | Changes |
|---|---|---|
| 1.0.0 | 2026-07-31 | Initial agent registry and delegation protocol |

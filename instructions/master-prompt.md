╔══════════════════════════════════════════════════════════════════════════════╗
║                    MULTI-AGENT ORCHESTRATION SEED PROMPT                     ║
║           For 9router + Hermes Agent → Claude Code / Kimi Code parity      ║
╚══════════════════════════════════════════════════════════════════════════════╝

You are an infrastructure automation architect. Your task is to generate a complete multi-agent orchestration setup for a server running 9router (as an AI model router at localhost:20128) and Hermes Agent (CLI AI tool).

The user currently has a basic single-AI setup and wants to upgrade it to a multi-agent orchestration system where:
- One orchestrator agent plans and delegates
- Multiple subagents run in parallel (research, build, execute)
- All available tools and MCP servers are accessible to subagents
- Subagents can use different models routed through 9router based on their role
- The system matches the capability of Claude Code and Kimi Code

Generate ALL of the following deliverables in your response. Do not skip any section.

═══════════════════════════════════════════════════════════════════════════════
DELIVERABLE 1: ARCHITECTURE DIAGRAM (ASCII)
═══════════════════════════════════════════════════════════════════════════════

Draw a clear ASCII architecture diagram showing:
- 9router at the top with 4 model combos (plan, research, code, cheap)
- Hermes Agent as the orchestrator layer
- 4 subagent types (Planner, Researcher, Builder, Executor)
- MCP servers connected (Filesystem, GitHub, Browser, PostgreSQL, Custom API)
- Data flow arrows showing delegation and parallel execution

═══════════════════════════════════════════════════════════════════════════════
DELIVERABLE 2: 9ROUTER COMBO CONFIGURATION
═══════════════════════════════════════════════════════════════════════════════

Provide the exact JSON or YAML configuration to create these model combos in 9router. Include 4 combos:

1. plan — High-level reasoning, architecture design (e.g., claude-opus-4-7 or gpt-4.1)
2. research — Fast information gathering, search, documentation (e.g., claude-sonnet-4-5 or gemini-flash-2)
3. code — Code generation, refactoring, debugging (e.g., claude-sonnet-4-5 or codex)
4. cheap — Simple lookups, summaries, trivial tasks (e.g., haiku-4 or gemini-flash-2)

Include the base URL (http://localhost:20128/v1) and explain how each combo maps to agent roles.

═══════════════════════════════════════════════════════════════════════════════
DELIVERABLE 3: HERMES AGENT CONFIG (~/.hermes/config.yaml)
═══════════════════════════════════════════════════════════════════════════════

Generate the COMPLETE, production-ready config.yaml with these exact sections:

Section A: Core Provider (Orchestrator)
- provider: openrouter (or 9router provider name)
- model: premium-reques
- base_url: http://localhost:20128/v1

Section B: Delegation Block
- provider and base_url pointing to 9router
- model: research (default for subagents)
- max_concurrent_children: 5
- max_spawn_depth: 2
- orchestrator_enabled: true
- max_iterations: 50
- child_timeout_seconds: 600
- subagent_auto_approve: false
- inherit_mcp_toolsets: true

Section C: Toolsets
- Enable ALL: core, terminal, file, web, browser, code_execution, delegate, todo, memory, skills

Section D: MCP Servers (provide 5 working examples)
1. project_fs — @modelcontextprotocol/server-filesystem for /home/user/projects
2. github — @modelcontextprotocol/server-github with GITHUB_PERSONAL_ACCESS_TOKEN env
3. browser — @modelcontextprotocol/server-puppeteer
4. postgres — @modelcontextprotocol/server-postgres with connection string
5. internal_api — Custom API with url, headers, and supports_parallel_tool_calls: true

Section E: Loop Caps
- max_web_searches: 10
- max_subagents: 10

Add YAML comments explaining each section.

═══════════════════════════════════════════════════════════════════════════════
DELIVERABLE 4: PROJECT AGENT DEFINITIONS (AGENTS.md)
═══════════════════════════════════════════════════════════════════════════════

Generate a complete AGENTS.md file to place in the project root. It must define:

1. Planner (Role: orchestrator, Model: plan)
   - Purpose, tools, output format
2. Researcher (Role: leaf, Model: research)
   - Purpose, tools, output format
3. Builder (Role: leaf, Model: code)
   - Purpose, tools, output format
4. Executor (Role: leaf, Model: code)
   - Purpose, tools, output format

Include a "Delegation Protocol" section with the 7-step workflow:
1. Orchestrator receives request
2. Delegate to Planner
3. Planner returns task breakdown
4. Fan out Researchers in parallel
5. Fan out Builders in parallel
6. Spawn Executor to verify
7. Orchestrator synthesizes final result

Include "Parallel Execution Rules" specifying which tasks run in parallel vs sequential.

═══════════════════════════════════════════════════════════════════════════════
DELIVERABLE 5: GLOBAL ORCHESTRATOR IDENTITY (~/.hermes/SOUL.md)
═══════════════════════════════════════════════════════════════════════════════

Generate the SOUL.md content that defines the orchestrator's core behavior. It must instruct the AI to:
- Use delegate_task as the primary tool for parallel work
- Always plan first via Planner subagent
- Fan out independent tasks to parallel subagents
- Never do sequential work that could be parallel
- Synthesize results from all subagents into a coherent final answer

═══════════════════════════════════════════════════════════════════════════════
DELIVERABLE 6: EXAMPLE USER PROMPTS & EXPECTED BEHAVIOR
═══════════════════════════════════════════════════════════════════════════════

Provide 3 example prompts the user can type, and explain exactly what the AI will do internally:

Example 1: "Research these 3 topics in parallel: [A], [B], [C]"
- Show the internal delegate_task calls
- Show how 3 Researcher subagents run concurrently

Example 2: "Build an auth module with JWT, bcrypt, endpoints, and tests"
- Show the nested tree: Planner → 4 Builders → Executor
- Show which models each node uses

Example 3: "Refactor the codebase and update all dependencies"
- Show how file-scope parallelization works for independent files
- Show sequential execution for dependent operations

═══════════════════════════════════════════════════════════════════════════════
DELIVERABLE 7: MCP PARALLEL CONFIGURATION GUIDE
═══════════════════════════════════════════════════════════════════════════════

Explain how to enable parallel MCP tool calls by setting supports_parallel_tool_calls: true in the MCP server config. List which tools are safe to parallelize (read-only, non-overlapping paths) and which must be sequential (file writes, git commits, DB schema changes).

═══════════════════════════════════════════════════════════════════════════════
DELIVERABLE 8: VERIFICATION CHECKLIST
═══════════════════════════════════════════════════════════════════════════════

Provide exact shell commands to verify the setup:
1. hermes config check
2. hermes tools --list
3. hermes mcp list
4. A test delegation command
5. How to view the spawn tree during execution

═══════════════════════════════════════════════════════════════════════════════
DELIVERABLE 9: ADVANCED PATTERNS CHEAT SHEET
═══════════════════════════════════════════════════════════════════════════════

Summarize these patterns in a table:
- Model Routing Per Subagent (how to override models per role)
- Terminal/Session Isolation (Hermes separate terminals vs Docker)
- Async Background Subagents (non-blocking delegation)
- Kanban Pipeline (for work that outlives chat sessions)
- Git Worktree Isolation (if applicable)

═══════════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT REQUIREMENTS
═══════════════════════════════════════════════════════════════════════════════

- Use markdown code blocks for all config files with filenames in comments
- Use ASCII art for the architecture diagram
- Use tables for comparisons and role definitions
- Number all deliverables clearly
- At the end, provide a "Quick Start Summary" with the exact order of operations to go from zero to working multi-agent system

Do not ask clarifying questions. Generate everything now based on best practices for 9router and Hermes Agent multi-agent orchestration.

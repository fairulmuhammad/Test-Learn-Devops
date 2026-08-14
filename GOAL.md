# GOAL — Learn DevOps with Multi-Agent Orchestration

**Created:** 2026-08-04
**Methodology:** Multi-agent AI orchestration system (docs in `instructions/`)
**Workspace:** /home/wannacry/devops-project/Test-Learn-Devops/

## What we are doing
Learn DevOps hands-on, using the agent orchestration system as the learning engine:
- Orchestrator (this session) plans and delegates
- Researcher agents gather knowledge (parallel fan-out)
- Builder agents write learning modules, configs, and labs
- Executor agents verify by running commands/tests
- Every file gets indexed → memory, so context survives across sessions

## Source instructions (from Obsidian vault `/agent`)
| File | Role in learning |
|---|---|
| PRD.md | Product goal of the agent system — the "why" behind our workflow |
| ARCHITECTURE.md | How the orchestration engine works internally |
| AGENTS.md | Agent roles: orchestrator/planner/researcher/builder/executor |
| WORKFLOWS.md | Reusable patterns: fan-out research, build pipeline, debug |
| PROMPTS.md | System prompts per role + user prompt templates |
| MCP.md | MCP server registry & tool catalog |
| SETUP.md | 9router + Hermes config reference |
| master-prompt.md | Seed prompt that generated the whole system |

## Devops learning path (draft)
1. Linux fundamentals (filesystem, processes, users, permissions)
2. Shell scripting (bash)
3. Systemd services (user already runs several)
4. Networking (ports, DNS, firewalls, reverse proxy)
5. Docker & containers (compose, networking, volumes)
6. CI/CD pipelines (GitHub Actions)
7. Monitoring & logging (uptime-kuma, netdata already installed)
8. Security hardening (ssh, fail2ban, secrets)

## Progress log
- 2026-08-04: Instructions copied to `instructions/`, index created. Research fan-out started.

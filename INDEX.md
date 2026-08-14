# INDEX — Test-Learn-Devops

**Workspace:** /home/wannacry/devops-project/Test-Learn-Devops/
**Purpose:** Learn DevOps via multi-agent orchestration. Instructions sourced from Obsidian vault `/agent` (2026-08-04).

## Instructions (copied from ~/Obsidian-Vault/agent/)
| File | Size | Purpose |
|---|---|---|
| instructions/PRD.md | 12.3K | Product requirements: multi-agent orchestration goals, roles, non-goals |
| instructions/ARCHITECTURE.md | 24.8K | Internal architecture: delegation engine, tool parallelizer, MCP client, data flows |
| instructions/AGENTS.md | 18.0K | Agent registry: orchestrator/planner/researcher/builder/executor roles & protocols |
| instructions/WORKFLOWS.md | 12.6K | Workflow patterns: parallel research, build pipeline, refactor, debug, docs |
| instructions/PROMPTS.md | 14.8K | System prompts per role + user prompt templates |
| instructions/MCP.md | 13.2K | MCP server registry: project_fs, github, browser, postgres, internal_api |
| instructions/SETUP.md | 20.3K | Setup guide: 9router combos, Hermes config.yaml, systemd services |
| instructions/master-prompt.md | 11.8K | Seed prompt that generated the orchestration system |

## Learning modules (created by agents 2026-08-04)
| Module | Lines | Status | Content |
|---|---|---|---|
| modules/linux-fundamentals.md | 258 | ✅ done | FHS, processes, users/perms, pipes/redirection, 30+ cmd cheat-sheet, 3 exercises |
| modules/systemd.md | 223 | ✅ done | Unit anatomy (real 9router.service), targets, journalctl, timers, 18 ops, 3 exercises |
| modules/docker.md | 285 | ✅ done | Images vs containers, multi-stage Dockerfile, compose, networks/volumes, ops, 3 exercises |
| modules/networking.md | 273 | ✅ done | IP/CIDR, ports, DNS, ufw/iptables, reverse proxy, TLS, Tailscale, 3 exercises |
| modules/shell-scripting.md | 459 | ✅ done | Script anatomy (real start_run.sh), syntax, set -euo pipefail, template, 3 exercises |
| modules/ci-cd.md | 444 | ✅ done | GitHub Actions anatomy (real magang-rbtv ci.yml/tests.yml), secrets, matrix, 3 exercises |
| modules/monitoring.md | 271 | ✅ done | 4 pillars, netdata/uptime-kuma (exited!), journald, logrotate, alerts, 3 exercises |
| modules/security.md | 470 | ✅ done | SSH hardening audit (real findings), ufw+Docker bypass, secrets, backup, checklist |

## Labs (hands-on exercises) — created 2026-08-04, README.md at labs/
| Lab | Lines | Content | Sudo |
|---|---|---|---|
| labs/01-linux-fundamentals.md | 219 | fs explore, processes/pipes, perms/symlink/tar | partial |
| labs/02-shell-scripting.md | 275 | backup.sh, getopts parse.sh, log rotator + cron | no |
| labs/03-systemd.md | 226 | hello service, kill-9 restart loop, backup timer | yes |
| labs/04-networking.md | 123 | port inventory, DNS experiments, http.server + ufw | partial |
| labs/05-docker.md | 199 | build/run/kill, multi-stage size, compose volume | yes |
| labs/06-ci-cd.md | 166 | hello.yml, matrix ci.yml, cd.yml env gate | no |
| labs/07-monitoring.md | 150 | journald audit, netdata restart [OPT], logrotate | partial |
| labs/08-security.md | 114 | SSH audit, exposure audit, secrets sweep (all read-only) | partial |

## Memory index
- Memory entry: "devops learning project" (2026-08-04) — points here.

## Progress log
- 2026-08-04: Instructions copied to `instructions/`, index created. Research fan-out started.
- 2026-08-14: Lab 01 (linux fundamentals) done — all exercises verified, no sudo needed (status readable unprivileged).
- 2026-08-14: Lab 02 (shell scripting) done — backup.sh/parse.sh/rotator.sh all verified, cron line installed+removed.
- 2026-08-14: Lab 03 (systemd) done — hello service restart loop (always + on-failure), backup timer fired at 02:30 schedule, all units cleaned up. Lab doc patched for systemd 255 (systemd-analyze calendar takes expr not unit).
- 2026-08-14: Lab 04 (networking) done — port inventory (0.0.0.0 vs 127.0.0.1 vs Tailscale binds), DNS experiments, hosts override, http.server + ufw allow/delete roundtrip. Note: 9router (20128) + netdata (9090) bound 0.0.0.0 = LAN-exposed.
- 2026-08-14: Lab 05 (docker) done — pingpong build/run/kill, multi-stage fat 539MB vs slim 165MB, compose volume survived down+up, down -v cleanup. INCIDENT: magang-db died (SIGKILL by dockerd 18:51 WIB) — mysqld unresponsive under memory pressure (1.7GB RAM box, node builds + 2 mysql instances); restarted, healthy, no data loss.
- 2026-08-14: Lab 06 (ci-cd) done — hello.yml + matrix ci.yml + cd.yml with environment gate, all YAML-validated, 3 commits in scratch repo, nothing pushed.
- 2026-08-14: Lab 07 (monitoring) done — journald audit (networkd-wait-online timeout), netdata restarted+verified+stopped (port 19999; 9090=Cockpit), logrotate proven with su directive + chmod/chown gotchas.
- 2026-08-14: Lab 08 (security) done — SSH audit (key-only in practice, password auth ON), exposure map (3306 public-facing, ufw inactive, docker bypass), secrets sweep (env perms 755→need 600; GitHub PAT leaked in git remote URL — needs rotation). AUDIT ONLY, nothing changed.
- 2026-08-14: Capstone scaffolded — hello-app (Flask, :8090) in apps/hello-app/, CI (validate+build+health) + CD (self-hosted deploy) workflows, systemd unit deployed + verified (restart OK). Repo committed. Pending user PAT: push to GitHub + register self-hosted runner (see GITHUB_SETUP.md).

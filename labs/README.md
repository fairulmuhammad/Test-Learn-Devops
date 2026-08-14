# LABS — Test-Learn-Devops

**Workspace:** /home/wannacry/devops-project/Test-Learn-Devops/
**Status:** Scaffolded 2026-08-04

## How to use
1. Read module first (../modules/<topic>.md) — labs assume module knowledge
2. Do exercises IN ORDER — each builds on the previous
3. Tick checkboxes when done. Every exercise has a **Verify** step — run it, don't skip
4. No sudo? Exercises marked [ROOT] need sudo — ask orchestrator, type password when prompted
5. Never run destructive commands on real data — labs use scratch dirs: ~/scratch/, /tmp/

## Progression
| Order | Lab | Module | Sudo needed |
|---|---|---|---|
| 1 | 01-linux-fundamentals.md | linux-fundamentals.md | partial |
| 2 | 02-shell-scripting.md | shell-scripting.md | no |
| 3 | 03-systemd.md | systemd.md | yes (create service) |
| 4 | 04-networking.md | networking.md | partial |
| 5 | 05-docker.md | docker.md | yes (docker group) |
| 6 | 06-ci-cd.md | ci-cd.md | no |
| 7 | 07-monitoring.md | monitoring.md | partial |
| 8 | 08-security.md | security.md | read-only mostly |

## Rules
- Scratch work: /home/wannacry/scratch/ or /tmp/ — never production dirs
- Clean up containers/images you create: docker rm/rmi after lab
- [ROOT] = ask orchestrator for sudo password
- After each lab, update INDEX.md progress column

## Progress tracker
| Lab | Status |
|---|---|
| 01 linux | ✅ done 2026-08-14 |
| 02 shell | ✅ done 2026-08-14 |
| 03 systemd | ✅ done 2026-08-14 |
| 04 networking | ✅ done 2026-08-14 |
| 05 docker | ✅ done 2026-08-14 |
| 06 ci-cd | ✅ done 2026-08-14 |
| 07 monitoring | ✅ done 2026-08-14 |
| 08 security | ✅ done 2026-08-14 |

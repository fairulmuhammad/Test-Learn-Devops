# Lab 08: Security Hardening (Audit)

## Setup

**Prereqs:** Ubuntu 24.04 box (`wannacry`), docker CLI, repo at `~/project/magang-rbtv`. Module: `modules/security.md`.

**Note:** `sudo` needed for two read-only commands (`sshd -T`, `ufw status`) — marked `[ROOT]`. **AUDIT ONLY — every command in this lab is read-only.** No config changes, no `fail2ban` install, no `ufw` changes, no file edits. `sshd -T` only *prints* the effective config; `ufw status` only *reports*. Nothing is started, stopped, or modified.

Ground truth up front: this box publishes **MySQL to the whole internet** (`0.0.0.0:3306`), SSH is key-only in practice (0 failed logins in auth.log), `fail2ban` not installed. The lab is about *finding* these, not fixing them.

---

## Exercise 1 — SSH audit walkthrough (read-only)

**Goal:** Determine the effective SSH configuration and whether the box is actually locked down.

**Steps:**

1. Print the effective (post-drop-in) sshd config `[ROOT]`:
   ```console
   $ sudo sshd -T | grep -E '^(permitrootlogin|passwordauthentication|pubkeyauthentication|maxauthtries)'
   ```
2. Check key file permissions:
   ```console
   $ stat -c '%a %n' ~/.ssh ~/.ssh/authorized_keys
   ```
3. Check the raw config file — note which directives are commented out:
   ```console
   $ grep -E 'PermitRootLogin|PasswordAuthentication' /etc/ssh/sshd_config
   ```
4. Count failed login attempts in the last 7 days:
   ```console
   $ journalctl -u ssh --since '7 days ago' | grep -icE 'failed password|invalid user'
   ```
5. Answer in writing: which directives are commented vs. effective? Is root login possible? How many failed attempts? What *should* a locked-down config say — diff it mentally against `sshd -T` output. **No changes made.**

**Expected output:** `sshd -T` prints effective values (`permitrootlogin prohibit-password`, `passwordauthentication yes` unless overridden); `~/.ssh` = `700`, `authorized_keys` = `600`; `sshd_config` shows both directives commented out; failed-attempt count = `0`.

**Verify:**
```console
$ sudo sshd -T | grep -cE '^(permitrootlogin|passwordauthentication|pubkeyauthentication)'   # expect 3 lines
```

- [x] Effective SSH state documented, config vs. reality compared, nothing changed

---

## Exercise 2 — Network exposure audit (read-only)

**Goal:** Map every listening socket and published container port, and classify each as public-internet vs. localhost/Tailscale/tunnel-only.

**Steps:**

1. List every listening socket:
   ```console
   $ ss -tlnp
   ```
2. List every published container port:
   ```console
   $ docker ps --format '{{.Names}}\t{{.Ports}}'
   ```
3. Check what the firewall *claims* `[ROOT]`:
   ```console
   $ sudo ufw status verbose
   ```
4. Map PIDs from `ss -tlnp` to processes:
   ```console
   $ ps aux | grep -E 'docker-proxy|cloudflared|next-server|mysqld'
   ```
5. For each listening port answer: what service? does it *need* to be reachable from the public internet? what would a bot do with it?

**Expected output:** `ss -tlnp` shows `0.0.0.0:3306` owned by `docker-proxy` (MySQL published to the internet), plus sshd:22, cockpit:9090, next-server:20128, apache:80. `docker ps` confirms `0.0.0.0:3306->3306/tcp` on `magang-db`. `ufw status verbose` shows the firewall profile — and note it would NOT block the Docker-published port (Docker writes its own iptables rules, bypassing UFW).

**Verify:**
```console
$ ss -tlnp | grep -c ':3306'    # expect 1 — the internet-facing MySQL
```

- [x] Every listening port classified, UFW-vs-Docker bypass understood

---

## Exercise 3 — Secrets sweep (read-only)

**Goal:** Find secret-shaped files and known token patterns, judge each hit, change nothing.

**Steps:**

1. List tracked files that look like secrets:
   ```console
   $ git -C ~/project/magang-rbtv ls-files | grep -iE '\.env|secret|credential|\.pem|\.key$'
   ```
2. Check whether `.env` ever entered git history:
   ```console
   $ git -C ~/project/magang-rbtv log --oneline -- .env
   ```
3. Check permissions of every env file on the box:
   ```console
   $ find ~ -maxdepth 3 -name '*.env*' -exec stat -c '%a %n' {} \; 2>/dev/null
   ```
4. Grep for known token patterns:
   ```console
   $ grep -rn 'ghp_\|sk-\|AKIA' ~/project 2>/dev/null | head
   ```
5. For each hit record in a table: real secret or dummy? in `.gitignore`? would `chmod 600` be needed? **Change nothing.**

**Expected output:** `git ls-files` shows no tracked `.env` (only `.env.example` if any); `git log -- .env` may be empty — but note the module's finding: a GitHub PAT lives in the repo's *remote URL* (`git remote -v` shows `https://fairulmuhammad:ghp_***@github.com/...`). `find` shows `.env` files with `600` (good) or `644` (needs 600). Token grep may return hits or nothing.

**Verify:**
```console
$ git -C ~/project/magang-rbtv ls-files | grep -c '\.env$'    # expect 0
```

- [x] Secrets sweep table filled in, no changes made

## Audit findings (2026-08-14)

### Exercise 1 — SSH
- Effective (sshd -T): `permitrootlogin without-password`, `passwordauthentication yes`, `pubkeyauthentication yes`, `maxauthtries 6`
- Both directives are COMMENTED in sshd_config → Ubuntu defaults apply (root=key-only, password auth ON)
- Key perms: `~/.ssh` 700, `authorized_keys` 600 ✅
- Failed logins (7d): 0 — key-only in practice, but `passwordauthentication yes` is a live risk if box is ever internet-reachable. Fix when ready: set `PasswordAuthentication no` in a drop-in.

### Exercise 2 — Exposure
| Port | Service | Bind | Verdict |
|---|---|---|---|
| 22 | sshd | 0.0.0.0 | LAN-wide; needs ufw or bind change |
| 3306 | MySQL (magang-db via docker-proxy) | 0.0.0.0 | **public-facing DB** — highest risk; bots would brute-force root |
| 20128 | 9router (next-server) | 0.0.0.0 | LAN-exposed; no auth on /v1/models |
| 80 | apache | * | web |
| 9090 | Cockpit | * | LAN-exposed admin UI |
| 443 | Tailscale funnel | tailscale IP only | safe (TS-only) |
- `ufw status`: inactive — and even if enabled, Docker-published ports bypass it (Docker writes its own iptables rules).

### Exercise 3 — Secrets
| Hit | Real? | In .gitignore? | Needs chmod? |
|---|---|---|---|
| `magang-rbtv/.env` | real | yes (untracked, not in history) | **755 → 600** (world-readable) |
| `magang-rbtv/.env.octane` / `.env.testing` | real | untracked | 664 → 600 |
| `magang_backup/.env.bak.1762852066` | real (backup) | n/a | 755 → 600 |
| `server/.env` | real | n/a | 600 ✅ |
| GitHub PAT in remote URL (`git remote -v`: `https://fairulmuhammad:ghp_***@github.com/...`) | **real leaked token** | n/a | **rotate the PAT + strip from remote URL** |
- Tracked: only `.env.example`; `git log -- .env` empty — no .env ever committed ✅

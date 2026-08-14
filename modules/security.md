# Security Hardening

DevOps module. Security hardening = reducing attack surface + making intrusions visible + making recovery possible. Grounded in the live state of this box (Ubuntu 24.04, user `wannacry`, sshd on port 22, Docker + MySQL container, netdata, cloudflared tunnel, Tailscale, 9router). Same style as the other modules: **real findings from this box, commands you can run yourself, nothing changed** — read-only audit only.

---

## 1. Overview & threat model

Security is not a checklist you tick once — it is a loop: **reduce attack surface → detect intrusions → recover fast**. A home-lab/learning server on the public internet is actively probed within minutes of going online (botnets scan the whole IPv4 space for port 22 and 3306). The realistic threat model for this box:

| Threat | Realistic? | Main defense |
|---|---|---|
| Random botnet brute-forcing SSH | **Yes — the #1 real threat.** Automated scans hit port 22 constantly | Key-only auth, fail2ban, non-default port (optional), strong keys |
| Credential stuffing / reused passwords | Yes, if any service allows password login | No password auth anywhere; unique per-service credentials |
| Exploiting a public web service (9router/uptime-kuma/Nextcloud) | Yes — anything published through the tunnel | Keep images updated, least privilege, secrets out of configs |
| Exposed database (MySQL on 0.0.0.0:3306) | **Yes — this box currently publishes MySQL to the whole internet.** Botnets scan for exactly this | Bind to localhost, firewall it, strong root password |
| Insider / own-mistake (bad command, leaked `.env`) | Yes | Least privilege, secrets hygiene, backups |
| Ransomware / disk-loss | Yes, general | Off-box backups (restic/rsync) |

The two findings that matter most on this box right now:

1. **MySQL container publishes `0.0.0.0:3306` to the entire internet** (visible in `docker ps` / `ss -tlnp`). Anyone who can guess or brute-force the DB password can read/write the whole database. This is the single biggest exposure.
2. **SSH is in good shape**: key-only logins, zero failed-password events in auth.log (log is only 78 lines — this is a young box, and it already only accepts keys).

Everything below is ordered roughly by impact, not alphabetically.

---

## 2. SSH hardening

### How SSH auth actually works (30 seconds)

- **Key auth**: the server holds your *public* key in `~/.ssh/authorized_keys`. You hold the *private* key. The server proves you own the private key via a cryptographic challenge — no password ever crosses the wire.
- **Password auth**: the server asks for your account password over the SSH connection. Attackers can guess this millions of times.
- Therefore: **key auth is not just more convenient, it removes the entire guessing game.**

### Current state of this box (real audit findings)

```console
$ grep -E 'PermitRootLogin|PasswordAuthentication' /etc/ssh/sshd_config
#PermitRootLogin prohibit-password
#PasswordAuthentication yes
```

Both directives are **commented out** in the main file → defaults apply. On Ubuntu 24.04 (OpenSSH 9.6), the compiled-in defaults are:

- `PermitRootLogin prohibit-password` — root can log in **with a key** but not a password. Key-only root login is *allowed* by default. Tighten to `no` unless you have a specific need.
- `PasswordAuthentication yes` — **password SSH login is ON by default** if nothing overrides it.

But wait — what actually applies? Two more things to check:

```console
$ ls /etc/ssh/sshd_config.d/
50-cloud-init.conf
$ cat /etc/ssh/sshd_config.d/50-cloud-init.conf    # (needs root; 27 bytes on this box)
```

Ubuntu's sshd reads `Include /etc/ssh/sshd_config.d/*.conf` (the last line of `/etc/ssh/sshd_config`), so cloud-init drop-ins win. On this box the drop-in exists but the effective config was not readable without root — the ground truth is `sshd -T` (prints the *effective* config after all files):

```console
$ sudo sshd -T | grep -E '^(permitrootlogin|passwordauthentication|pubkeyauthentication|port)'
```

**Audit finding — effective SSH state of this box:**

| Setting | Value on this box | Verdict |
|---|---|---|
| Auth method in use | **publickey only** (every `Accepted` line in `/var/log/auth.log` is `Accepted publickey`, zero `Failed password` events) | ✅ Good |
| `~/.ssh` permissions | `700` (dir), `authorized_keys` = `600` | ✅ Good |
| Host keys | ed25519 + ecdsa + rsa, all `600`, owned by root | ✅ Good |
| Password auth | Likely default-on (no effective override verified) | ⚠️ Tighten explicitly |
| Root login | Default `prohibit-password` (key OK) | ⚠️ Consider `no` |
| fail2ban | **Not installed** (`command -v fail2ban-client` → nothing) | ❌ Missing |
| SSH exposure | Port 22 open on all interfaces, public internet | ⚠️ Mitigate |
| Failed logins | 0 in `/var/log/auth.log` (log = 78 lines; box is young + key-only already) | ✅ Quiet box |

The log proves the box is already key-only in practice: every login was `Accepted publickey for wannacry ... ED25519`, from the Tailscale IP `100.74.24.28`. But the *config* has not been locked down — a future config drift or a second user could silently re-enable passwords. Lock it explicitly.

### SSH hardening checklist (do these, in order)

1. **Generate a strong key pair on your laptop** (ed25519, 256-bit, mathematically fast and safe — no reason to use RSA 4096 for new keys):
   ```console
   $ ssh-keygen -t ed25519 -a 100 -f ~/.ssh/id_ed25519
   ```
2. **Install the public key on the server**:
   ```console
   $ ssh-copy-id wannacry@SERVER_IP
   ```
   (Or append the public key to `~/.ssh/authorized_keys` manually — it must be the *public* half, never the private key.)
3. **Verify key login works before locking anything** — open a *second* terminal and log in with the key. Never lock yourself out.
4. **Lock the config** — create `/etc/ssh/sshd_config.d/99-hardening.conf` (drop-in, survives package updates better than editing the main file):
   ```
   PasswordAuthentication no
   KbdInteractiveAuthentication no
   PermitRootLogin no
   PubkeyAuthentication yes
   MaxAuthTries 3
   LoginGraceTime 20
   AllowUsers wannacry
   ```
   Then:
   ```console
   $ sudo sshd -t          # syntax check — do this BEFORE reload
   $ sudo systemctl reload ssh
   ```
   `sshd -t` validates; `systemctl reload` applies without dropping connections. If you lock yourself out: reboot the box (or use a cloud console/VNC) and fix the file.
5. **Install fail2ban** (see §4 for the full story):
   ```console
   $ sudo apt install fail2ban
   $ sudo systemctl enable --now fail2ban
   ```
6. **Optional hardening**:
   - Change port from 22 (e.g. `Port 2222`): reduces log noise, does *not* add real security (a port scan finds it in seconds). With Tailscale + a tunnel on this box, you can also just stop publishing port 22 to the public internet and SSH over Tailscale (`tailscale ssh` or plain SSH to the Tailscale IP) — that is stronger than any port change.
   - Keep `ClientAliveInterval`/`ClientAliveCountMax` sane to reap dead sessions; `AllowUsers` to whitelist accounts.

### Why `PermitRootLogin no` matters

`prohibit-password` (the default) still lets root in with a key. `no` forces admins through a named user + `sudo`. Benefits: root's key is not a single point of failure, and every root action shows up as `sudo: user` in the logs with an audit trail of *who* did it. On this box you already operate as `wannacry` — set `PermitRootLogin no` and you lose nothing.

---

## 3. Firewall

### UFW basics

UFW = front-end over iptables/nftables. Three commands to know:

```console
$ sudo ufw status verbose      # what's allowed/denied right now
$ sudo ufw allow 22/tcp        # open a port (SSH first — always!)
$ sudo ufw enable              # turn it on (this is the dangerous moment)
```

Ubuntu default policy: **deny incoming, allow outgoing**. So the recipe is: allow what you need, then enable, and everything else is blocked. Order matters: **allow SSH before enabling**, or you cut your own hand off.

```console
$ sudo ufw default deny incoming
$ sudo ufw default allow outgoing
$ sudo ufw allow 22/tcp
$ sudo ufw allow 80/tcp        # only if something must be reachable directly
$ sudo ufw allow 443/tcp
$ sudo ufw enable
```

On this box: `ufw.service` is **loaded, active, enabled** — but `ufw status` needs root and the drop-in state is unverified, so re-check with `sudo ufw status verbose` yourself. A server with a working firewall + Tailscale normally allows only Tailscale's port (`41641/udp`) and whatever the tunnel needs.

### The Docker bypass caveat — read this twice

**UFW does NOT filter Docker-published ports.** This is the classic footgun:

- Docker writes its own rules directly into the kernel's `nat`/`filter` tables (via the `DOCKER` chain) **bypassing UFW entirely**.
- `ufw status` may show a clean "deny all", while `0.0.0.0:3306` is wide open to the internet.
- Proof on this box right now:
  ```console
  $ docker ps --format '{{.Names}}\t{{.Ports}}'
  magang-db  0.0.0.0:3306->3306/tcp, [::]:3306->3306/tcp, 33060/tcp
  $ ss -tlnp | grep ':3306'
  LISTEN 0  4096  0.0.0.0:3306  0.0.0.0:*   users:(("docker-proxy",...))
  ```
  MySQL is reachable from **any machine on the internet**. UFW, if enabled, would not stop it.

Fixes, in order of preference:

1. **Bind the port to localhost** in `docker-compose.yml` — `"127.0.0.1:3306:3306"` instead of `"3306:3306"`. Then nothing outside the box can reach it, no firewall involved.
2. Or drop the port mapping entirely and use Docker's internal network (other containers reach it by service name).
3. Or block it explicitly with iptables (fragile; Docker's iptables rules often clobber custom ones after restarts).

Rule of thumb: **never publish a database port with `0.0.0.0`**. Databases are not web servers. MySQL should be reachable only by the app container (internal network) or at most `127.0.0.1` (admin tools on the same host).

### Where does the firewall fit in the architecture here?

- Public web traffic (uptime-kuma, Nextcloud, 9router) enters via the **cloudflared tunnel** — Cloudflare connects *out* to the server; nothing needs to be opened inbound. The tunnel is the firewall for HTTP(S).
- Tailscale (port `41641/udp`) carries private traffic (admin, SSH) — encrypted, authenticated mesh.
- So the ideal state: UFW allows only `22/tcp` (or Tailscale-only SSH) + `41641/udp` + Docker's internal needs; **nothing else inbound from the public internet**. The tunnel handles the rest.

---

## 4. Secrets management

### The rule that prevents 90% of incidents

**Never put secrets in git. Ever.** Committed secrets are:
- in the repo history forever (removing the file later does NOT remove the secret — it stays in every old commit),
- cloned to every laptop and CI runner that ever touches the repo,
- exposed if the repo goes public or a third-party service is compromised.

Real example from this box's own repo (from the CI/CD module): `git remote -v` shows `https://fairulmuhammad:ghp_***@github.com/...` — a GitHub PAT embedded in the remote URL. The `***` means it is already scrubbed somewhere, but the pattern is the warning: credentials can leak through many small cracks (git remotes, `.env` files, shell history, compose files).

### `.env` files — the standard pattern

```console
$ ls -la .env
-rw------- 1 wannacry wannacry 894 .env        # 600 — only owner can read
$ cat .gitignore
.env
```

- `.env` holds `KEY=VALUE` pairs (`DB_PASSWORD=...`, `APP_KEY=...`). Docker Compose reads it automatically (`env_file: .env`, or `${VAR}` interpolation).
- The file lives **on the server**, never in the repo. `.gitignore` lists `.env` so `git add .` cannot stage it.
- **Permissions**: `.env` must be `600` (owner-only). A world-readable `.env` is the same as posting the password on the login page.
- The repo instead ships `.env.example` — a template with dummy values, so other people know what to fill in.

```console
$ cp .env.example .env     # on the server
$ $EDITOR .env             # fill real values
$ chmod 600 .env
$ git status               # confirm .env is NOT tracked
```

### Rules of thumb

| Do | Don't |
|---|---|
| Put secrets in `.env` on the server, `chmod 600` | Hardcode secrets in code, compose files, or docs |
| Keep `.env` in `.gitignore` | `git add -f .env` (force) — the anti-pattern |
| Rotate a secret immediately when it leaks | Rely on "the repo is private" as protection |
| Use unique passwords per service | Reuse the same password for MySQL, admin panels, etc. |
| Use a password manager / `pass` / `gopass` on your laptop | Paste secrets into chat, notes, or shell history |
| Prefer Tailscale + localhost for admin tools | Expose admin UIs through the tunnel |

### Related file-permission hygiene (real values from this box)

```console
$ stat -c '%a %n' ~/.ssh ~/.ssh/*
700 /home/wannacry/.ssh
600 /home/wannacry/.ssh/authorized_keys
600 /home/wannacry/.ssh/known_hosts
644 /home/wannacry/.ssh/known_hosts.old
```

- `~/.ssh` = `700`, `authorized_keys` = `600` — **correct** (SSH refuses keys from a world-readable dir).
- `known_hosts.old` at `644` is cosmetic (public data), but the pattern to remember: private keys and credential files = `600` or `400`, never `644`.
- Check the whole disk for loose secrets: `grep -rE 'password|secret|token' --include='*.env*' ~ 2>/dev/null`, and `git -C <repo> log -p -- .env` to see if a secret ever landed in history.
- Note the host keys in `/etc/ssh/` are all `600` root-owned — correct.

---

## 5. Monitoring for intrusions

### 1. fail2ban — the tripwire for SSH brute force

Not installed on this box yet — install it (see §2 step 5). What it does: watches logs for repeated failures (e.g. 5 failed SSH logins in 10 minutes) and bans the source IP in the firewall for a while (default 10 min). Cheap, effective, and it works for many services (sshd, nginx, web apps).

```console
$ sudo apt install fail2ban
$ sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local   # local overrides survive upgrades
$ sudo systemctl enable --now fail2ban
$ sudo fail2ban-client status sshd        # how many IPs currently banned
$ sudo fail2ban-client set sshd unbanip 1.2.3.4   # unban yourself after a mistake
```

A young key-only box (like this one, 0 failed logins in auth.log) has almost nothing for fail2ban to catch — which is exactly the point: fail2ban is the safety net for the day a config change re-enables passwords, plus it protects any other password-protected service you add later.

### 2. sshd logs — where intrusions show up first

Two places to look, both read-only:

```console
$ journalctl -u ssh | grep -c 'Failed password'       # via journald (unit is 'ssh' on Ubuntu)
0
$ grep -c 'Failed password' /var/log/auth.log          # classic log file
0
$ journalctl -u ssh -S '24 hours ago' | grep -iE 'failed|invalid|break-in'
$ tail -50 /var/log/auth.log
```

What the real log on this box shows:

```console
sshd[50267]: Accepted publickey for wannacry from 100.74.24.28 port 49403 ssh2: ED25519 SHA256:Yyx...
pam_unix(sshd:session): session opened for user wannacry(uid=1000) by wannacry(uid=0)
```

Every line tells you: **who** logged in (`wannacry`), **how** (`publickey` — good), **from where** (`100.74.24.28` — a Tailscale IP), **with which key** (ED25519 fingerprint). Alarm patterns to grep for:

| Pattern | Meaning |
|---|---|
| `Failed password for ... from <IP>` | Someone (or a bot) guessing credentials |
| `Invalid user ... from <IP>` | Probing for usernames |
| `Accepted password for ...` | **Bad if you disabled passwords** — someone used a password anyway |
| `Accepted publickey` from an IP you don't recognize | A key you didn't create — investigate now |
| `Connection closed by authenticating user` | Pre-auth disconnect, common in brute-force runs |

SSH runs with `LogLevel VERBOSE` by default in modern OpenSSH — fingerprints and method are logged. Keep `journald` persistent if you want history across reboots: `/etc/systemd/journald.conf` → `Storage=persistent`.

### 3. auditd — file/monkey business tracking

`auditd` (Linux Audit daemon) records *who accessed what, when* — file access, exec calls, config changes. Heavier than fail2ban; use it when you need forensics-grade logging (e.g. watching `.env`, `authorized_keys`, or `/etc/ssh`):

```console
$ sudo apt install auditd
$ sudo auditctl -w /etc/ssh/sshd_config -p wa -k sshd_config   # watch file: write+attr change
$ sudo auditctl -w /home/wannacry/.ssh/authorized_keys -p wa -k ssh_keys
$ sudo ausearch -k sshd_config        # query the log for that watch
$ sudo auditctl -l                    # list active rules
```

Not installed on this box — optional. netdata (already running here) covers the *metrics* side (CPU, net, disk, connections); auditd covers the *who-did-what* side.

### 4. Read the logs on a schedule

The best IDS is a habit: `journalctl -u ssh --since yesterday`, `grep -i 'error\|fail' /var/log/syslog | tail`, glance at `sudo` lines in auth.log. netdata dashboards show anomalies in traffic. None of this replaces a human (or a log-aggregation tool later — Loki, Prometheus + Alertmanager, or the paid stuff) looking at what is unusual.

---

## 6. TLS / certificates

**On this box: the cloudflared tunnel handles TLS end-to-end, so there is no cert-renewal chore — note this.**

- Cloudflare terminates TLS at their edge (your domain's `https://` cert is Cloudflare's, auto-renewed by them) and the tunnel carries encrypted traffic to your server over an outbound connection.
- The `cloudflared tunnel run` process (real, on this box) and the 9router instance (`~/.9router/bin/cloudflared tunnel --url http://127.0.0.1:20128`) use **Cloudflare-managed certs — nothing for you to renew**. `--no-autoupdate` means *cloudflared the binary* does not self-update; the certs are still Cloudflare's job.
- What this removes: no `certbot renew`, no cron for cert renewal, no expiry alerts for the tunnel domains.
- What still needs attention: any cert **not** behind the tunnel (e.g. a raw IP service, or a self-signed cert you create for testing) — that one is yours to renew. And `cloudflared` itself should be updated periodically (the tunnel's TLS is only as good as the tunnel binary; note `--no-autoupdate` on the systemd unit — update via `cloudflared update` or the package).

If you ever serve TLS directly (no tunnel): `sudo apt install certbot` + `sudo certbot certonly --webroot -d example.com`, and certbot's systemd timers (`certbot.timer`) auto-renew. Check: `systemctl list-timers | grep certbot`.

---

## 7. Backup strategy

Backups exist for one moment: the day data dies. The test of a backup is **restoring from it**, not creating it.

Concept on this box: the state that matters is
- the database (MySQL container `magang-db` — data in a named volume),
- the app code + `.env` (config/secrets),
- compose files and any custom configs.

### Option A — restic (encrypted, deduplicated, off-box)

```console
$ sudo apt install restic
$ restic init --repo sftp:user@backup-host:/backups/wannacry   # or a B2/S3 bucket
$ restic backup /home/wannacry/project/magang-rbtv /home/wannacry/devops-project
$ docker exec magang-db mysqldump -u root -p"$DB_PASSWORD" --all-databases | restic backup --stdin --stdin-filename magang-db.sql
$ restic snapshots          # list
$ restic restore latest --target /tmp/restore-test   # THE test
```

Why restic: encrypted (restic encrypts before upload — you can back up to a server you don't trust), deduplicated (snapshots are cheap), versioned (go back to any point in time).

### Option B — rsync (simple, unencrypted, same-or-trusted-host only)

```console
$ rsync -avz --delete /home/wannacry/project/ user@backup-host:/backups/wannacry/
```

`-a` archive, `-v` verbose, `-z` compress, `--delete` mirrors deletions. No encryption, no versioning, no dedup — fine for a second copy on a trusted box, weak for ransomware protection (it would happily mirror the encryption). For real protection: **3-2-1** — 3 copies, 2 different media, 1 off-site. And automate it (systemd timer or cron; the CI/CD module covers pipeline automation, this is cron territory):

```console
$ sudo systemctl edit --force --full backup.timer   # OnCalendar=daily
```

Never back up *to* the same disk you are backing *up* (that's a copy, not a backup). And **test the restore** — at least once, restore to a scratch dir and check the files open.

---

## 8. Updates & automatic security updates

Unpatched software is the #1 *preventable* compromise vector. On Ubuntu the tool is `unattended-upgrades` — **already installed and enabled on this box** (real finding):

```console
$ dpkg -l | grep unattended-upgrades
ii  unattended-upgrades  2.9.1+nmu4ubuntu1  all  automatic installation of security upgrades
$ cat /etc/apt/apt.conf.d/20auto-upgrades
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
```

Both flags `"1"` = package lists refresh daily and security upgrades install automatically. Verify it works (read-only):

```console
$ sudo unattended-upgrades --dry-run --debug     # what WOULD it install
$ grep -iE 'upgraded|installed' /var/log/unattended-upgrades/unattended-upgrades.log | tail
```

What is NOT covered by unattended-upgrades — the gap:

- **Docker images** (netdata, mysql, uptime-kuma, Nextcloud, 9router...): apt updates the *Docker Engine*, not the *images*. Images update via `docker compose pull` + `docker compose up -d`. No automation for that on this box — make it a habit or a cron.
- **cloudflared**: running with `--no-autoupdate` — the binary only updates when you update it (`cloudflared update` or apt).
- **Kernel reboot**: security kernel updates install but need a reboot to take effect. `reboot` after major updates, or use `unattended-upgrades`' automatic reboot options carefully (`Automatic-Reboot "true"` in `50unattended-upgrades`).

So the update routine for this box: `sudo apt update && sudo apt upgrade` monthly + `docker compose pull && docker compose up -d` per-project + `cloudflared update` occasionally + reboot after kernel changes. The Docker images themselves need a **registry scan** habit (e.g. `docker scout` or the registry's own scanning) to catch known-vulnerable base images.

---

## 9. Hardening checklist table

Status column = real findings on this box at time of writing.

| # | Control | Why | Command to verify | Status here |
|---|---|---|---|---|
| 1 | SSH key-only auth | Kills password guessing | `grep -E 'PasswordAuthentication|PubkeyAuthentication' /etc/ssh/sshd_config` + `sudo sshd -T` | ⚠️ Works in practice (all logins `publickey`), not locked in config |
| 2 | `PermitRootLogin no` | Root needs sudo audit trail | `grep PermitRootLogin /etc/ssh/sshd_config` | ⚠️ Default `prohibit-password` — tighten |
| 3 | `~/.ssh` perms 700/600 | SSH refuses loose keys | `stat -c '%a' ~/.ssh ~/.ssh/authorized_keys` | ✅ `700`/`600` |
| 4 | fail2ban | Auto-ban brute force | `command -v fail2ban-client` | ❌ Not installed |
| 5 | Firewall active | Block everything not needed | `sudo ufw status verbose` | ✅ `ufw.service` active+enabled (rules need re-check with root) |
| 6 | No DB port on 0.0.0.0 | Databases must not be public | `docker ps` / `ss -tlnp \| grep :3306` | ❌ **MySQL published `0.0.0.0:3306`** |
| 7 | Secrets not in git | History keeps leaks forever | `git -C <repo> ls-files \| grep -E '\.env$'`; `git log -p -- .env` | ⚠️ PAT in git remote URL (`ghp_***` — scrubbed); check `.env` |
| 8 | `.env` perms 600 | World-readable = published | `stat -c '%a' .env` | ⚠️ Verify per project |
| 9 | Security updates auto | Close known CVEs fast | `cat /etc/apt/apt.conf.d/20auto-upgrades` | ✅ `"1"`/`"1"` |
| 10 | Docker images updated | apt doesn't update images | `docker images` / compose pull habit | ⚠️ Manual, no automation |
| 11 | TLS handled | No expired-cert surprises | cloudflared tunnel runs | ✅ Tunnel = Cloudflare-managed certs |
| 12 | Backups exist + tested | Recovery is the point | `restic snapshots` / rsync cron | ❌ None seen on this box |
| 13 | Logs reviewed | Spot intrusions early | `journalctl -u ssh -S yesterday` | ⚠️ Habit, not yet a routine |

Score: 3 ✅ / 6 ⚠️ / 4 ❌. The two highest-impact fixes: **stop publishing MySQL to the internet** (one line in compose: `127.0.0.1:3306:3306`), and **lock SSH in config** (drop-in + `sshd -t` + reload). Both are 5-minute jobs with no downtime.

---

## 10. Hands-on exercises (read-only — safe to run)

**Exercise 1 — SSH audit walkthrough (read-only).**

```console
$ sudo sshd -T | grep -E '^(permitrootlogin|passwordauthentication|pubkeyauthentication|maxauthtries)'
$ stat -c '%a %n' ~/.ssh ~/.ssh/authorized_keys
$ grep -E 'PermitRootLogin|PasswordAuthentication' /etc/ssh/sshd_config
$ journalctl -u ssh --since '7 days ago' | grep -icE 'failed password|invalid user'
```

Questions to answer: Which directives are commented vs. effective? Is root login possible? How many failed attempts in the last 7 days? Then write down what a locked-down config *should* say and diff it mentally against what `sshd -T` prints — no changes made.

**Exercise 2 — network exposure audit (read-only).**

```console
$ ss -tlnp                                     # every listening socket
$ docker ps --format '{{.Names}}\t{{.Ports}}'  # every published container port
$ sudo ufw status verbose                      # what the firewall says
```

For each listening port, answer three questions: What service is it? Does it *need* to be reachable from the public internet (vs. localhost / Tailscale / tunnel-only)? What would happen if a bot found it? Expect to find `0.0.0.0:3306` and be able to explain *why* UFW alone would not block it (§3). Cross-check with `ps aux | grep` to map PIDs from `ss -tlnp` to processes (cloudflared, next-server, docker-proxy...).

**Exercise 3 — secrets sweep (read-only).**

```console
$ git -C ~/project/magang-rbtv ls-files | grep -iE '\.env|secret|credential|\.pem|\.key$'   # tracked secret-ish files
$ git -C ~/project/magang-rbtv log --oneline -- .env                                        # did .env ever enter history?
$ find ~ -maxdepth 3 -name '*.env*' -exec stat -c '%a %n' {} \; 2>/dev/null                 # perms of every env file
$ grep -rn 'ghp_\|sk-\|AKIA' ~/project 2>/dev/null | head                                    # known token patterns
```

For each hit: is it a real secret or a dummy/example? Is the file in `.gitignore`? Would `chmod 600` be needed? Record findings in a table; change nothing.

---

## 11. Pitfalls

1. **Locking yourself out of SSH.** Sequence is everything: install key → *test in a second terminal* → then flip `PasswordAuthentication no` → `sshd -t` → `systemctl reload ssh`. Never disable passwords before confirming key login works. Recovery path if it happens: cloud console/VNC, or reboot.
2. **UFW gives a false sense of security with Docker.** UFW does not filter `docker-proxy` published ports (`0.0.0.0:3306` on this box is proof). Bind ports to `127.0.0.1` or drop the mapping; never trust `ufw status` to protect a container port.
3. **"I removed the secret from the repo" — no you didn't.** Git history keeps it forever. The only fix is rotation (change the password/token) plus (if the repo ever went public) history rewriting — which is hard and often not worth it. Prevent first: `.gitignore`, `git ls-files` checks, and never `git add -f .env`.
4. **Editing `/etc/ssh/sshd_config` directly.** Package upgrades can overwrite or conflict with your edits. Use a drop-in in `/etc/ssh/sshd_config.d/*.conf` (already included on this box via the `Include` line). Same pattern as apt's config.d directories.
5. **Disabling root login and passwords in the wrong order / without a test session** — see #1. Also: `PermitRootLogin no` does not affect `sudo` — root stays usable, just not via SSH.
6. **Backups on the same disk / never tested.** A copy on the same disk dies with the disk; an untested backup is a hope, not a plan. Test one restore. Use restic for encryption/versioning, rsync only for trusted hosts.
7. **Forgetting Docker images don't auto-update.** `unattended-upgrades` covers apt packages only. `mysql:8.0` and the app images drift vulnerable until you `docker compose pull`. Schedule it.
8. **Logs you never read.** fail2ban + auditd + journald are only useful if someone looks. A 5-minute weekly log glance (or netdata alert) turns them into an IDS; unread logs are just disk usage.
9. **Port-knocking / changing SSH port as "security".** Obscurity buys noise-reduction, not safety. Real security = key-only + fail2ban + patching + least privilege.
10. **Secrets in compose files, shell history, or CI logs.** `docker-compose.yml` with a hardcoded password ends up in the repo; `history | grep MYSQL_PASSWORD` leaks locally; CI logs echo env vars. Keep secrets in `.env` (600), inject via `env_file`/`${VAR}`, and treat any printed secret as compromised.

---

## 12. Further reading

- **SSH**: `man sshd_config`, `man ssh-keygen` — the canonical reference; `sudo sshd -T` shows effective config. `ssh-audit` (pip tool) grades your server's cipher/key state.
- **Firewall**: `man ufw`; Docker docs, "Docker and iptables" page — explains exactly why UFW can't see container ports.
- **Secrets**: `gitignore` docs (git-scm.com); `pass`/`gopass` for local secret storage; GitHub docs on secret scanning / PAT rotation.
- **Monitoring**: fail2ban docs (fail2ban.org); auditd — `man auditctl`, `man ausearch`; the `journalctl` man page.
- **TLS**: Cloudflare Tunnel docs (developers.cloudflare.com/cloudflare-one/connections/connect-networks) — cert lifecycle is fully managed; certbot docs if you ever go direct-TLS.
- **Backups**: restic docs (restic.readthedocs.io) — init/backup/snapshots/restore; "3-2-1 backup rule" as the design target.
- **General**: OWASP (owasp.org) — the *server hardening* cheat sheet and the top-10 list are the canonical threat catalogs; CIS Benchmarks for Ubuntu (cisecurity.org) — the full formal checklist if you ever need to satisfy an auditor.
- **This box's other modules**: `monitoring.md` (netdata, metrics), `networking.md` (Tailscale, tunnels), `docker.md` (compose, volumes), `systemd.md` (units, timers) — security touches all of them.

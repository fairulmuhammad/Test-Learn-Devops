# Lab 07: Monitoring & Logging

## Setup

**Prereqs:** Ubuntu 24.04 box (`wannacry`), docker CLI, systemd. Module: `modules/monitoring.md`.

**Note:** `sudo` needed for logrotate steps — marked `[ROOT]` below. Some commands inspect live container state; netdata and uptime-kuma containers are **currently exited** on this box (stopped 8 months ago) — do not be surprised, that is the point of Exercise 2. **Do NOT start/stop `magang-db`** (only live container, healthy, serves the app).

Reality check first — never trust the doc, check the box:

```console
$ curl -s -o /dev/null -w '%{http_code}\n' http://localhost:9090/
$ docker ps
$ docker ps -a | grep -E 'netdata|uptime'
```

Expected: port 9090 returns `200` but is **Cockpit**, not netdata; `docker ps` shows only `magang-db`; `docker ps -a` shows netdata + uptime-kuma as `Exited (0) 8 months ago`.

---

## Exercise 1 — Audit this boot's errors (journald)

**Goal:** Find failed services in the journal and trace the cause chain of one failed unit.

**Steps:**

1. List all errors + worse from this boot:
   ```console
   $ journalctl -p err -b
   ```
2. Pick one failed unit (e.g. `cloudflared`), read its full story this boot:
   ```console
   $ journalctl -u cloudflared -b
   ```
3. Find the unit file and its dependencies:
   ```console
   $ systemctl cat cloudflared
   ```
4. Check journal size (read-only — do NOT vacuum):
   ```console
   $ journalctl --disk-usage
   ```
5. Write 3 lines: what failed, why (cause chain — look for the `systemd-networkd-wait-online` timeout earlier in the log), what you'd fix.

**Expected output:** `journalctl -p err -b` shows lines like `Failed to start cloudflared.service`, a sudo "password is required" entry, and a networkd-wait-online timeout. `--disk-usage` reports ~1.3G.

**Verify:**
```console
$ journalctl -u cloudflared -b | tail -20
```

- [x] Found ≥1 failed unit and traced its cause chain

---

## Exercise 2 — Bring netdata back, verify it [OPTIONAL]

**Goal:** Restart the exited netdata container, verify its API, find key charts and a health alert config.

**Note:** Netdata container is currently **exited** on this box — this exercise restarts and then stops it. `[OPTIONAL]` because it changes container state; skip if you must keep the box untouched. **Do NOT touch `magang-db`.** Uptime-kuma (also exited) is covered by the same pattern — `docker start uptime-kuma`, check port 3001, `docker stop uptime-kuma`.

**Steps:**

1. Start the stopped netdata container:
   ```console
   $ docker start netdata
   ```
2. Wait ~10s, then verify the API:
   ```console
   $ curl -s localhost:19999/api/v1/info | head
   ```
3. Confirm the container's port (the classic gotcha — netdata is 19999, NOT 9090):
   ```console
   $ docker ps --format '{{.Names}}\t{{.Ports}}' | grep netdata
   ```
4. Find config and one health alert config:
   ```console
   $ ls /home/wannacry/server/netdata/config/health.d/
   ```
5. Check container logs for startup errors:
   ```console
   $ docker logs netdata --since 10m
   ```
6. Stop it again when done:
   ```console
   $ docker stop netdata
   ```

**Expected output:** API returns JSON with `version` and `hostname` fields. `docker ps` shows netdata with port `19999/tcp`. `health.d/` lists alert configs. Web UI at port 19999 (via tunnel if needed).

**Verify:**
```console
$ curl -s localhost:19999/api/v1/info | grep -E 'version|hostname'
$ docker ps -a | grep netdata    # should show Exited again after step 6
```

- [x] Netdata started, API verified, stopped again

---

## Exercise 3 — Write a logrotate config (test file only)

**Goal:** Create a rotation config and prove rotation works — using a throwaway `/tmp` file, NOT system logs.

**Note:** All writes stay in `/tmp`. No system log files are touched; nothing in `/etc/logrotate.d/` is modified or force-run.

**Steps:**

1. Create a test log file:
   ```console
   $ printf 'line 1\nline 2\nline 3\n' > /tmp/testapp.log
   ```
2. Write the rotation config to `/tmp/testapp.rotate`:
   ```console
   $ cat > /tmp/testapp.rotate <<'EOF'
/tmp/testapp.log {
    size 1k
    rotate 3
    compress
    missingok
    notifempty
}
EOF
   ```
3. Dry run — shows what WOULD happen, changes nothing `[ROOT]`:
   ```console
   $ sudo logrotate -d /tmp/testapp.rotate
   ```
4. Force run — actually rotates the test file `[ROOT]`:
   ```console
   $ sudo logrotate -f /tmp/testapp.rotate
   ```
5. Confirm the rotated, compressed file exists:
   ```console
   $ ls -la /tmp/testapp.log*
   ```
6. Repeat step 4 until rotation count reaches 3, then confirm the oldest file is deleted:
   ```console
   $ sudo logrotate -f /tmp/testapp.rotate
   $ ls /tmp/testapp.log*
   ```

**Expected output:** Dry run prints `considering log /tmp/testapp.log` and `rotating pattern`. After force runs, `testapp.log.1.gz` (then `.2.gz`, `.3.gz`) appear; when rotation count exceeds `rotate 3`, the oldest `.gz` is removed.

> **Gotchas hit on Ubuntu 24.04 (logrotate refuses, with these exact errors):**
> 1. Config file writable by group/others → `error: Ignoring ... because it is writable by group or others.` → `chmod 600` the config.
> 2. Config owned by non-root when run via sudo → `error: Ignoring ... because the file owner is wrong (should be root or user with uid 0).` → `sudo chown root:root` it.
> 3. Log parent dir world-writable (like `/tmp`) → `error: skipping ... because parent directory has insecure permissions ... Set "su" directive in config file` → add `su <user> <user>` to the config.
> 4. With `size N`, an empty/small log is NOT rotated even with `-f` — grow the file past the threshold between runs (`head -c 2048 /dev/zero | tr '\0' 'x' >> /tmp/testapp.log`).

**Verify:**
```console
$ ls /tmp/testapp.log* && ls /tmp/testapp.log*.gz | wc -l    # expect ≤ 3
```

- [x] Test file rotated to .1.gz and oldest pruned at count 3

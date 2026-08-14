# Monitoring & Logging

DevOps module. Monitoring = watch systems, collect data, alert when something breaks. Logging = record what happened, in order, with enough context to debug. Grounded in live state of this server (`wannacry` box, Ubuntu 24.04).

> **Reality check first.** Task brief assumed netdata on port 9090 and uptime-kuma running. Live verification says otherwise — that is itself the first lesson: **never trust the doc, check the box.**
>
> ```console
> $ curl -s -o /dev/null -w '%{http_code} %{content_type}\n' http://localhost:9090/
> 200 text/html          # <- this is Cockpit web console, NOT netdata
> $ docker ps            # only ONE container running
> NAMES       IMAGE       STATUS                 PORTS
> magang-db   mysql:8.0   Up 3 hours (healthy)   0.0.0.0:3306->3306/tcp
> $ docker ps -a | grep -E 'netdata|uptime'
> edbb181033a2   netdata/netdata         ... Exited (0) 8 months ago
> 361c3f35b358   louislam/uptime-kuma:1  ... Exited (0) 8 months ago
> ```

---

## 1. Overview

Monitoring answers "is it healthy right now, and what changed?". Logging answers "what exactly happened, and why?".

| Question | Tool type | Example tools |
|---|---|---|
| Is CPU high? | Metrics | netdata, Prometheus, Grafana |
| Why is it high? | Logs | journald, rsyslog, Loki |
| Where did the request go? | Traces | Jaeger, Tempo, OpenTelemetry |
| Tell me when it breaks | Alerting | netdata health, Uptime Kuma, Alertmanager |

The stack on this box (installed, mostly idle): netdata (docker, exited), uptime-kuma (docker, exited), journald (active, 1.3G of logs), Cockpit (active, port 9090), Prometheus/Grafana (not installed — later module).

## 2. The four pillars

### 2.1 Metrics — numbers over time
Counters, gauges, histograms. CPU %, RAM, disk free, request rate, latency. Store as time series (timestamp + value + labels). Cheap to collect, cheap to store, ideal for dashboards and thresholds.

### 2.2 Logs — discrete events
One line per event: timestamp, source, level, message. Structured (JSON) > unstructured (free text). Answer "what happened", not "how fast". Expensive to store — need rotation/retention policy (see §5).

### 2.3 Traces — request journey
Follow one request across services: service A → DB → service B → cache, with per-hop latency. Only relevant for distributed apps (microservices). Single host with one DB barely needs it.

### 2.4 Alerts — metrics + threshold + action
Alert = "condition true for N minutes → notify". The 4th pillar because data nobody looks at is worthless. Without alerts you have monitoring theater: pretty dashboards, broken service.

## 3. netdata

Real-time (per-second) system + app metrics, zero-config, web UI. Here: installed as docker container `netdata/netdata` (770MB image), **exited 8 months ago**. Config lives on host at `/home/wannacry/server/netdata/config/` (bind mount):

```console
$ ls /home/wannacry/server/netdata/config/
charts.d  custom-plugins.d  edit-config  go.d  health.d  netdata.conf  orig  otel.d  python.d  ssl
```

Docker wiring (from `docker inspect netdata`):
- Container default port **19999** (netdata web UI) — the classic gotcha: `9090` on this box is **Cockpit**, not netdata.
- Volumes: config → `/etc/netdata`, `/proc` → `/host/proc`, `/sys` → `/host/sys`, docker.sock → container (so netdata can read container metrics).

Why it exited: container was stopped when the old compose stack was dismantled. To bring it back:

```console
$ docker start netdata                        # container still exists, just stopped
$ curl -s localhost:19999/api/v1/info | head  # verify: JSON with version, mirrors, etc.
$ docker logs netdata --since 10m             # startup errors land here
```

Key netdata concepts:
- **Charts** — one per metric family (cpu, ram, net, disk, apps, docker).
- **Health/alert config** — `/etc/netdata/health.d/*.conf` in container, `health.d/` on host. Alert = expression over a chart, e.g. `cpu > 80` for 1 min.
- **Alarms** — netdata's built-in alerting: WARNING/CRITICAL states, notifies via email/telegram/webhook.
- **Streaming** — netdata can push metrics to a parent netdata; scale-up path if you ever outgrow one box.

## 4. uptime-kuma

Uptime monitoring for *services*, not hosts: "is https://example.com returning 200?". Docker image `louislam/uptime-kuma:1`, **exited 8 months ago**, data volume `/home/wannacry/server/uptime-kuma` → `/app/data` in container. Intended port 3001.

```console
$ docker start uptime-kuma
$ curl -s -o /dev/null -w '%{http_code}\n' localhost:3001   # 200 when up
```

Features worth knowing:
- **Monitors**: HTTP(s), TCP, ping, DNS, keyword search in response. HTTP monitor = probe URL, expect status 2xx/3xx (or a keyword), else mark DOWN.
- **Heartbeat / retries**: N failed checks before DOWN → filters transient blips.
- **Status pages**: public page showing green/red per service.
- **Notifications**: Telegram, Discord, email, webhook, ... fired on state change.
- **Dead man's switch** is a manual pattern here (see §7): add a monitor that must stay UP as "the host is alive" proxy, or use the API push monitor type.

Current live services it could monitor on this box: `magang-db` (mysql, port 3306), Cockpit (9090), the Next.js app on port 20128, Apache on 80, SSH on 22.

## 5. journald & logrotate — real commands from this box

### 5.1 journald (systemd's binary log)

```console
$ journalctl -p err -b                  # errors + worse, this boot
Aug 04 16:47:47 wannacry-server systemd-networkd-wait-online[670]: Timeout occurred...
Aug 04 16:48:02 wannacry-server systemd[1]: Failed to start cloudflared.service
Aug 04 19:43:43 wannacry-server sudo[54604]: wannacry : a password is required ; ...
```

What that output teaches:
- `cloudflared.service` fails at boot → real problem to investigate (network-wait timeout earlier in the log is the cause chain).
- Sudo "password is required" entries = someone tried `sudo` without a tty/password → also a security-relevant log line.

```console
$ journalctl -u cloudflared -b          # all log lines for ONE unit, this boot
$ journalctl -u cloudflared -f          # follow (tail -f equivalent)
$ journalctl --since "1 hour ago"       # time-filtered
$ journalctl --disk-usage               # how much disk the journal eats
Archived and active journals take up 1.3G in the file system.   # <- real number here
$ journalctl --vacuum-size=200M         # shrink journal to 200MB (DESTRUCTIVE: deletes old logs)
$ journalctl -k -b                      # kernel messages this boot
$ journalctl _PID=1                     # filter by field; _COMM=sshd works too
```

Journal = binary, not plain files. `journalctl` is the only reader. Rotation is automatic, size-capped in `/etc/systemd/journald.conf` (`SystemMaxUse=`).

### 5.2 logrotate — classic text-log rotation

journald self-rotates; rsyslog and Apache write plain files that **do not** — logrotate handles them. Drop-in configs in `/etc/logrotate.d/`, cron runs `logrotate` daily.

Real config on this box, `/etc/logrotate.d/apache2`:

```
/var/log/apache2/*.log {
	daily
	missingok
	rotate 14
	compress
	delaycompress
	notifempty
	create 640 root adm
	sharedscripts
	prerotate
		if [ -d /etc/logrotate.d/httpd-prerotate ]; then
			run-parts /etc/logrotate.d/httpd-prerotate
		fi
	endscript
	postrotate
		if pgrep -f ^/usr/sbin/apache2 > /dev/null; then
			invoke-rc.d apache2 reload 2>&1 | logger -t apache2.logrotate
		fi
	endscript
}
```

Directive cheat-sheet:

| Directive | Meaning |
|---|---|
| `daily` / `weekly` | rotate on this schedule (or `size 100M`) |
| `rotate 14` | keep 14 rotated files, then delete oldest |
| `compress` | gzip rotated files |
| `delaycompress` | skip compressing the most recent one (app may still write to it) |
| `missingok` | don't error if log file absent |
| `notifempty` | don't rotate empty files |
| `create 640 root adm` | recreate file with this mode/owner after rotate |
| `postrotate` | run after rotate — here: `apache2 reload` so Apache reopens its log fd |

Also present on this box: `/etc/logrotate.d/rsyslog` (rotate 4, weekly, compress), `ufw`, `apt`, `dpkg`, `apport`, `wtmp`, `btmp`, `bootlog`, `cloud-init`, `unattended-upgrades`.

```console
$ sudo logrotate -d /etc/logrotate.conf     # dry run: show what WOULD happen
$ sudo logrotate -f /etc/logrotate.conf     # force run now (test rotation)
```

**Why rotation matters, real numbers:** journald already holds **1.3G**. Apache access logs on a busy box grow GB/week. Unrotated logs = full disk = service outage. `/mnt/data` on this box is already at **100%** (195G used, 64M free) — full disk is a real failure mode here.

## 6. Disk / CPU / RAM basics

```console
$ df -h                       # disk usage per filesystem
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda2       266G   60G  193G  24% /
/dev/sda1       195G  195G   64M 100% /mnt/data   # <- FULL: investigate

$ free -h                     # RAM + swap
               total  used  free  shared  buff/cache  available
Mem:           1.7Gi 1.0Gi 107Mi   96Ki      795Mi      681Mi
Swap:          4.0Gi 517Mi 3.5Gi

$ top -b -n 1 | head -15      # live processes by CPU; 'top' interactive, 'q' quits
top - 19:48:59 up 3:03, 2 users, load average: 1.84, 1.27, 0.97
%Cpu(s): 26.8 us, 3.7 sy, 0.0 ni, 32.6 id, 36.3 wa ...
  PID USER  ...  %CPU  %MEM TIME+  COMMAND
10997 wannacry ... 30.8 10.6 1:54.80 next-server   # Next.js app eating CPU
 6087 dnsmasq ...  7.7  3.6 2:33.16 mysqld         # DB
```

Read the output, don't just run it:
- **load average 1.84** on a 4-core box = ~46% busy. Rule of thumb: load should stay under core count.
- **`wa` 36.3%** = high I/O wait — disk is the bottleneck right now, not CPU.
- **`available` 681Mi** — the number that matters (free + reclaimable cache). Ignore `free` column, it always looks scary.
- Swap in use (517Mi) = RAM pressure at some point; check `vmstat 1` / `iostat` for the story.
- `ps aux --sort=-%cpu | head` for a static snapshot; `top`/`htop` for interactive.

## 7. Alerting concepts

- **Threshold** — rule: `metric op value`. e.g. `disk_use% > 85`, `http_status != 200`. One threshold = simple, noisy. Two-stage (WARNING at 80, CRITICAL at 95) = better.
- **Duration / for** — condition must hold N minutes before firing. Kills flapping: load spike for 10s ≠ incident. (Netdata: "after 1m". Prometheus: `for: 5m`.)
- **Severity levels** — WARNING (heads up, no action yet) vs CRITICAL (page someone). Severity is about *blast radius*, not loudness.
- **State transitions** — alert fires (OK→ALERT), later resolves (ALERT→OK). Only notify on *transitions*, not continuously — otherwise alert fatigue and people mute you.
- **Dead man's switch** — watchdog pattern. Monitor that must fire if the monitoring itself dies. Classic: alert "no data for 10 minutes" on the metrics stream; or a scheduled heartbeat that must arrive, alert when it doesn't. Rationale: monitoring failure looks like "everything fine" — the worst kind of silence. Netdata equivalent: parent-child streaming + alert on missing child data; Uptime Kuma: push-type monitor.
- **Runbook link** — every alert text should say where to look / what to do. Alert without runbook = panic at 3am.

## 8. Ops cheat-sheet

| Task | Command |
|---|---|
| Errors this boot | `journalctl -p err -b` |
| Follow one service log | `journalctl -u cloudflared -f` |
| Logs since 1h | `journalctl --since "1 hour ago"` |
| Journal disk usage | `journalctl --disk-usage` |
| Shrink journal (destructive) | `sudo journalctl --vacuum-size=200M` |
| Disk usage | `df -h` |
| RAM + swap | `free -h` |
| Top processes live | `top` (or `htop`, `glances` — both installed here) |
| Top processes, snapshot | `ps aux --sort=-%cpu | head -15` |
| Ports listening | `ss -tlnp` |
| logrotate dry run | `sudo logrotate -d /etc/logrotate.conf` |
| logrotate force now | `sudo logrotate -f /etc/logrotate.conf` |
| Check netdata API | `curl -s localhost:19999/api/v1/info` |
| Docker containers (all) | `docker ps -a` |
| Docker logs, last 10m | `docker logs <name> --since 10m` |
| Service health | `systemctl is-active <unit>` |
| Load/CPU/I/O story | `vmstat 1 5` |

## 9. Hands-on exercises

**Exercise 1 — audit this boot's errors (journald)**
Run `journalctl -p err -b`. Pick one failed unit (e.g. `cloudflared`). Trace its full story: `journalctl -u cloudflared -b`, then find the unit file `systemctl cat cloudflared`, then check its dependencies for a failing prerequisite (note the networkd-wait-online timeout in the same log). Write 3 lines: what failed, why (cause chain), what you'd fix.

**Exercise 2 — bring netdata back, verify it**
`docker start netdata`. Wait ~10s, then `curl -s localhost:19999/api/v1/info` — confirm JSON with `version` and `hostname`. Open the web UI in a browser (port 19999 via tunnel if needed). Find: the RAM chart, the per-container docker chart, one health alert config in `health.d/`. Then `docker stop netdata`. Note: it's the only docker container NOT running on this box — investigate why the old compose stack stopped it.

**Exercise 3 — write a logrotate config**
Create `/tmp/testapp.log` with a few lines. Write `/tmp/testapp.rotate`:

```
/tmp/testapp.log {
    size 1k
    rotate 3
    compress
    missingok
    notifempty
}
```

Run `sudo logrotate -d /tmp/testapp.rotate` (dry run — shows what WOULD happen), then `sudo logrotate -f /tmp/testapp.rotate`, then `ls /tmp/testapp.log*` — verify `.1.gz` exists. Repeat the force run until rotation count reaches 3, confirm oldest file is deleted. That is exactly what `/etc/logrotate.d/apache2` does for real logs, daily.

## 10. Pitfalls

- **Trusting the doc instead of the box.** This brief assumed netdata on 9090. Reality: 9090 = Cockpit, netdata container exited. `curl` and `docker ps` beat any README.
- **Alert fatigue.** 50 noisy alerts → all muted → real incident missed. Fewer, well-tuned alerts beat many.
- **No dead man's switch.** Monitoring that dies silently looks like a healthy system. Always alert on absence of data too.
- **Unrotated logs fill the disk.** Journald already 1.3G here; `/mnt/data` already 100% full. Disk-full is a service outage — `logrotate` + `journald --vacuum` are prevention.
- **Watching the wrong memory number.** `free` column in `free -h` looks catastrophic; `available` is what actually matters.
- **Metrics without context.** A CPU spike means nothing without knowing what ran — correlate with logs (`journalctl --since`) before declaring incident.
- **Notifying on state, not transitions.** Continuous alerts get muted. Fire on change.
- **Ignoring load average vs core count.** Load 2.5 on a 2-core box = saturated; on a 16-core box = idle. Always compare to core count (`nproc`).

## 11. Further reading

- netdata docs — https://learn.netdata.cloud (health alerts, streaming)
- Uptime Kuma — https://github.com/louislam/uptime-kuma (monitor types, status pages)
- `man journalctl`, `man logrotate`, `/etc/logrotate.d/` on this box
- Prometheus docs — https://prometheus.io/docs/introduction/overview (metrics model, `for:` alerts)
- Grafana — https://grafana.com/docs (dashboards over Prometheus; next module)
- OpenTelemetry — https://opentelemetry.io (traces + unified signals, the "later" path)

# Systemd

> Ubuntu 24.04, systemd 255. All examples below are real units from this server (`wannacry-server`). Prefer system-level units in `/etc/systemd/system/` over user-level (`~/.config/systemd/user/`) — services keep running when nobody is logged in.

Systemd is PID 1: it boots the machine, starts/stops/monitors services, collects logs, and runs scheduled jobs. Everything it manages is a **unit**. Unit types you will touch daily:

| Type | Purpose | File suffix |
|---|---|---|
| service | long-running process | `.service` |
| timer | schedule that fires a service | `.timer` |
| target | group of units (boot milestone) | `.target` |
| socket | lazy activation via socket | `.socket` |
| mount / automount | filesystem mounts | `.mount` |
| path | trigger on file changes | `.path` |

## Anatomy of a `.service` unit

Real example from this server — `/etc/systemd/system/9router.service`:

```ini
[Unit]
Description=9router AI Agent Provider
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=wannacry
WorkingDirectory=/home/wannacry/.9router
ExecStartPre=/bin/sh -c 'pkill -f "9router" || true; sleep 1'
ExecStart=/home/wannacry/.nvm/versions/node/v22.22.0/bin/9router
Restart=always
RestartSec=3
KillMode=process
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Section by section:

- **`[Unit]`** — metadata + ordering.
  - `Description=` shows in `systemctl status`.
  - `After=network.target` — start only *after* network is up. Ordering only; does not pull the dependency in. To also pull it: `Wants=` (soft) or `Requires=` (hard).
  - `StartLimitIntervalSec=0` — disable the restart rate limiter (see Pitfalls). Default: 5 starts within 10s, then the unit is refused.

- **`[Service]`** — how to run the process.
  - `Type=simple` — `ExecStart` is the main process, systemd considers it started immediately. This server's other main type: `cloudflared.service` uses `Type=notify` (daemon signals readiness via `sd_notify`; must pair with `TimeoutStartSec=` so a never-notifying daemon fails fast instead of hanging).
  - `User=wannacry` — drop privileges. Run services as an unprivileged user, not root.
  - `WorkingDirectory=` — chdir before exec. `9router` loads `.env` from here.
  - `ExecStartPre=` — command run before start; failure aborts the start. Note the `|| true`: this one kills leftover processes and must not fail.
  - `ExecStart=` — the main command. Absolute path, no shell (no pipes/redirection — wrap in `/bin/bash -c '...'` if you need them, like `cloudflared-update.service` does).
  - `Restart=always` — restart on any exit, including clean exit and signal. Alternatives: `on-failure` (exit ≠ 0, signal, timeout; **not** on clean exit — what `cloudflared.service` uses), `on-abnormal`, `no`.
  - `RestartSec=3` — wait 3s between restarts. `cloudflared` uses `RestartSec=5s`.
  - `KillMode=process` — on stop, kill only the main process, not the whole cgroup. Needed for `9router` because it spawns child workers.
  - `StandardOutput=journal` / `StandardError=journal` — send stdout/stderr to the journal. Default on Ubuntu, but explicit is fine. This is why `journalctl -u 9router` shows the app's own output.
  - Other directives you will use:
    - `Environment="KEY=value"` or `EnvironmentFile=/etc/foo.env` — config without editing the unit (one line per `KEY=value`; `#` comments OK; no `export`).
    - `ExecStop=` — extra stop command beyond SIGTERM.
    - `TimeoutStopSec=10` — how long to wait for graceful stop before SIGKILL.
    - `LimitNOFILE=65535` — raise fd limit for servers that need it.
    - `ProtectSystem=strict`, `PrivateTmp=yes`, `NoNewPrivileges=yes`, `ReadOnlyPaths=/` — sandboxing hardening. Good hygiene, cheap to add, breaks apps that write outside their dirs — test after adding.

- **`[Install]`** — when to auto-start.
  - `WantedBy=multi-user.target` — standard: enable = symlink into `/etc/systemd/system/multi-user.target.wants/`. This is exactly what the `[Install]` section does; it is inert until you run `systemctl enable`.

## Targets vs runlevels

Runlevels (SysV) were numbers: 3 = multi-user text, 5 = graphical. Systemd replaced them with **targets** — named groups of units. `graphical.target` pulls in `multi-user.target`; `multi-user.target` pulls in everything needed for a text-mode server (network, ssh, cron, your services). This server's default:

```console
$ systemctl get-default
graphical.target
```

| Runlevel | Target |
|---|---|
| 0 | `poweroff.target` |
| 1 / S | `rescue.target` |
| 2–4 | `multi-user.target` |
| 5 | `graphical.target` |
| 6 | `reboot.target` |

`systemctl list-dependencies multi-user.target` shows what a boot pulls in — `cloudflared.service`, `docker.service`, `apache2.service`, etc. A unit with `WantedBy=multi-user.target` gets started by every boot that reaches multi-user.

## journalctl — reading logs

The journal is systemd's structured log. `9router` and `cloudflared` both write here via `StandardOutput=journal`.

```console
$ journalctl -u 9router --no-pager -n 8      # last 8 lines for one unit
$ journalctl -u cloudflared -f               # follow live
$ journalctl -u 9router --since "1 hour ago" # time window
$ journalctl -u docker -u containerd         # multiple units
$ journalctl -b -p err                       # this boot, errors only
$ journalctl -k                              # kernel messages
$ journalctl --disk-usage                    # how much space logs take
```

Real output shape (cloudflared, `-n 4`):

```
Aug 04 18:42:01 wannacry-server cloudflared[6025]: 2026-08-04T11:42:01Z WRN Failed to dial a quic connection ...
Aug 04 18:42:01 wannacry-server cloudflared[6025]: 2026-08-04T11:42:01Z INF Retrying connection in up to 4s ...
Aug 04 18:42:04 wannacry-server cloudflared[6025]: 2026-08-04T11:42:04Z INF Registered tunnel connection ... protocol=quic
```

Fields: timestamp, host, unit name + PID, then the message. Filter by field: `journalctl -u cloudflared _PID=6025`.

Real 9router restart history (`journalctl -u 9router`):

```
Jun 29 14:18:26 wannacry-server systemd[1]: 9router.service: Scheduled restart job, restart counter is at 249.
Jun 29 14:18:26 wannacry-server systemd[1]: 9router.service: Control process exited, code=killed, status=15/TERM
Jun 29 14:18:26 wannacry-server systemd[1]: 9router.service: Failed with result 'signal'.
```

"restart counter is at 249" + `result 'signal'` = the loop `Restart=always` was fighting. Diagnose with `systemctl status`, check `result='...'` (crash vs signal vs timeout), fix root cause, not just the restart.

Logs are persisted across boots only if `/var/log/journal/` exists (Ubuntu: yes, unless `Storage=volatile` in `/etc/systemd/journald.conf`).

## Timers

Scheduled jobs = `.timer` unit + the `.service` it triggers. Real pair on this server:

`/etc/systemd/system/cloudflared-update.timer`:
```ini
[Unit]
Description=Update cloudflared

[Timer]
OnCalendar=daily

[Install]
WantedBy=timers.target
```

`/etc/systemd/system/cloudflared-update.service`:
```ini
[Unit]
Description=Update cloudflared
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/bin/bash -c '/usr/bin/cloudflared update; code=$?; if [ $code -eq 11 ]; then systemctl restart cloudflared; exit 0; fi; exit $code'
```

Notes:
- The timer fires the service of the same name (`cloudflared-update.timer` → `cloudflared-update.service`). A timer without a same-named service fails.
- `OnCalendar=daily` = 00:00 local. Other forms: `Mon..Fri 02:00`, `*:0/15` (every 15 min), `weekly`, `OnBootSec=10min` (relative to boot), `OnUnitActiveSec=1h` (relative to last run — good for watchdogs).
- `systemctl enable cloudflared-update.timer` — enable the **timer**, not the service. `WantedBy=timers.target` makes it run at boot.
- Compare with `cron`: timers survive missed runs (catch-up), have persistent logs, can be inspected (`systemctl list-timers`). Ubuntu still ships `cron.service` and `logrotate.timer`, `apt-daily.timer` — real timers from `systemctl list-timers` on this box:

```
NEXT                         LEFT     LAST                          UNIT                    ACTIVATES
Tue 2026-08-04 20:09:00 WIB  25min    Tue 2026-08-04 19:39:03 WIB   4min ago  phpsessionclean.timer phpsessionclean.service
Wed 2026-08-05 00:00:00 WIB  4h 16min Tue 2026-08-04 16:47:21 WIB   2h ago    logrotate.timer       logrotate.service
```

## Common operations

| Task | Command |
|---|---|
| Start / stop / restart | `systemctl start|stop|restart <unit>` |
| Reload config (if unit supports) | `systemctl reload <unit>` |
| Auto-start at boot | `systemctl enable <unit>` |
| Disable auto-start | `systemctl disable <unit>` |
| Status (state, logs tail) | `systemctl status <unit>` |
| All running services | `systemctl list-units --type=service --state=running` |
| All units of a type | `systemctl list-units --type=timer` |
| Show the unit file as loaded | `systemctl cat <unit>` |
| Show effective settings | `systemctl show <unit> -p Restart` |
| Reload unit files after edit | `systemctl daemon-reload` |
| Follow logs | `journalctl -u <unit> -f` |
| Timers schedule | `systemctl list-timers` |
| Default target | `systemctl get-default` / `set-default multi-user.target` |
| Change boot target now | `systemctl isolate multi-user.target` |
| Reboot / poweroff | `systemctl reboot` / `systemctl poweroff` |
| Boot into rescue | `systemctl rescue` |

## Hands-on exercises

**1. Create, enable, and inspect a service.** Write `/etc/systemd/system/hello.service`:
```ini
[Unit]
Description=Hello daemon

[Service]
ExecStart=/bin/sh -c 'while true; do echo "hello $(date)"; sleep 30; done'
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
```
`systemctl daemon-reload`, `systemctl start hello`, `systemctl status hello`, `journalctl -u hello -f` (watch the hello lines), `systemctl enable hello`. Then stop it: note `Restart=always` — systemd brings it right back. Stop for good: `systemctl stop` + `systemctl disable`. Then remove the unit file and `daemon-reload` again.

**2. Kill it and watch the restart loop.** With `hello` running, `kill -9 $(systemctl show -p MainPID --value hello)`. Watch `systemctl status hello` and `journalctl -u hello`: `Main process exited, code=killed, status=9/KILL`, then `Scheduled restart job`. That is `Restart=always` + `RestartSec=2` in action. Now change the unit to `Restart=on-failure` (edit, `daemon-reload`, restart the unit), kill it again — SIGKILL still restarts (it's a failure), but a clean `systemctl stop` stays stopped.

**3. Build a backup timer.** Pair: `/etc/systemd/system/backup.service` running `/bin/tar czf /var/backups/home.tar.gz /home/wannacry`, and `/etc/systemd/system/backup.timer` with `OnCalendar=*-*-* 02:30:00` and `WantedBy=timers.target`. Enable the timer, verify it appears in `systemctl list-timers`, then verify the schedule without waiting: `systemd-analyze calendar backup.timer` (shows next fire time; `systemd-analyze calendar '*-*-* 02:30:00'` works on the raw expression too). To test immediately: `systemctl start backup.service` (start the service directly — timers never fire early).

## Pitfalls

- **`daemon-reload` after every edit.** Edit a unit file, and `systemctl` keeps serving the old version until you run `systemctl daemon-reload`. Editing + `restart` without reload = confusing "changes have no effect". `systemctl edit <unit>` (drop-in) still requires it.
- **`Restart=always` loops on a crashing app.** If `ExecStart` dies instantly, systemd restarts forever. Mitigations: `RestartSec=5`, `StartLimitIntervalSec=0` (disable the rate limit — what `9router` does — but then a broken app spins forever burning CPU), or leave the default limit so systemd gives up after 5 tries in 10s. Real example: 9router hit restart counter 249 with `result 'signal'` — that's the loop; fix the app, not the unit.
- **`enable` ≠ `start`.** `enable` only adds the boot symlink; the service does not run until you `start` it (or reboot). `systemctl enable --now` does both.
- **`After=` is not a dependency.** `After=network.target` only orders; if the unit isn't pulled in by something else (`Wants`/`Requires`/`WantedBy`), it never starts. Pair `After=` with `Wants=` when you need both (see `cloudflared.service`).
- **`ExecStart=` has no shell.** Pipes, `&&`, redirection, env expansion fail. Wrap in `/bin/sh -c '...'` (or `bash -c`).
- **Timer without same-named service** → timer fails at fire time. Every `.timer` needs its `.service` twin.
- **Enable the timer, not the service.** `systemctl enable backup.service` does nothing useful for a scheduled job; the timer's `[Install] WantedBy=timers.target` is what survives reboot.
- **Logs "missing".** Journal is volatile unless `/var/log/journal/` exists. `journalctl` after reboot only shows current boot (`-b`). Check `journalctl --disk-usage` and cap it in `/etc/systemd/journald.conf` (`SystemMaxUse=500M`) before it eats the disk.
- **Editing the wrong file.** `systemctl cat <unit>` shows the active definition including drop-ins. If you edit a file the unit doesn't load, nothing changes.

## Further reading

- `man systemd.unit`, `man systemd.service`, `man systemd.timer`, `man systemd.target`, `man journalctl`, `man systemd.exec` (hardening directives)
- systemd.io — official docs, including the [systemd for administrators](https://systemd.io/ADMIN_RESOURCES/) series
- freedesktop.org systemd manual pages: https://www.freedesktop.org/software/systemd/man/
- Ubuntu wiki: https://wiki.ubuntu.com/SystemdForUpstartUsers
- `systemd-analyze blame` — which units slow your boot; `systemd-analyze critical-chain` — boot dependency path

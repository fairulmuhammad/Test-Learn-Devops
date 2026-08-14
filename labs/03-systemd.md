# Lab 03: systemd — services, restart policies, timers

Hands-on extracted from `modules/systemd.md`. You create **test** units only, with unique names (`test-hello-<user>`, `test-backup-<user>`) so you never collide with real units.

> [WARNING] Never touch real services on this box: `9router`, `cloudflared`, `docker`. You only ever create/start/stop/enable/delete units named `test-*`. Each exercise cleans up after itself.

## Setup

Prereqs:
- Ubuntu with systemd as PID 1: `systemctl is-system-running`
- sudo access. Every step marked **[ROOT]** writes to `/etc/systemd/system/`, `/var/backups/`, kills root processes, or reads root-owned journal logs — it needs `sudo` and prompts for your password.
- Replace `wannacry` in unit names with your username if different.

Remember:
- `sudo systemctl daemon-reload` after **every** unit file edit — otherwise systemd keeps serving the old version.
- `enable` ≠ `start`. Enable only adds the boot symlink; the service does not run until started.

Verify before starting:

```console
$ systemctl is-system-running
running        # or degraded — fine, some unrelated unit failed
$ systemctl list-unit-files | grep -E 'test-(hello|backup)'
# no output expected — your test units don't exist yet
```

## Exercise 1: create, enable, inspect a service

**Goal:** write a `.service` unit by hand, load it, start it, read its logs, enable it for boot, then remove it completely.

**Steps:**

1. [ROOT] Write the unit file. Quoted `'EOF'` stops your shell from expanding `$(date)` — the service expands it at runtime:

```console
sudo tee /etc/systemd/system/test-hello-wannacry.service > /dev/null <<'EOF'
[Unit]
Description=Hello daemon (test)

[Service]
ExecStart=/bin/sh -c 'while true; do echo "hello $(date)"; sleep 30; done'
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF
```

2. [ROOT] Load it: `sudo systemctl daemon-reload`
3. [ROOT] Start it: `sudo systemctl start test-hello-wannacry`
4. [ROOT] Inspect state: `sudo systemctl status test-hello-wannacry`
5. [ROOT] Follow the logs (Ctrl-C stops the *follow*, not the service; first line appears within 30s):

```console
sudo journalctl -u test-hello-wannacry -f
```

6. [ROOT] Enable auto-start at boot: `sudo systemctl enable test-hello-wannacry`
7. [ROOT] Stop and disable: `sudo systemctl stop test-hello-wannacry && sudo systemctl disable test-hello-wannacry`
8. [ROOT] Cleanup — remove the unit and reload:

```console
sudo rm /etc/systemd/system/test-hello-wannacry.service && sudo systemctl daemon-reload
```

**Expected output:**
- Step 4: `Active: active (running) since ...` plus `Main PID:` and the last log lines.
- Step 5: lines like `Aug 04 18:42:01 wannacry-server test-hello-wannacry[1234]: hello Tue Aug 04 18:42:01 WIB 2026` every ~30s.
- Step 6: `Created symlink /etc/systemd/system/multi-user.target.wants/test-hello-wannacry.service`.
- Step 8: `systemctl status` now says `Unit test-hello-wannacry.service could not be found.`

**Verify:**

```console
sudo systemctl status test-hello-wannacry    # after step 4: active (running); after step 8: could not be found
```

- [x] Exercise 1 done

## Exercise 2: kill it and watch the restart loop

**Goal:** see `Restart=always` + `RestartSec=2` fight a `kill -9`, then switch the unit to `Restart=on-failure` and see that a clean stop stays stopped.

**Steps:**

1. [ROOT] Recreate the unit from Exercise 1 (same file, `Restart=always`):

```console
sudo tee /etc/systemd/system/test-hello-wannacry.service > /dev/null <<'EOF'
[Unit]
Description=Hello daemon (test)

[Service]
ExecStart=/bin/sh -c 'while true; do echo "hello $(date)"; sleep 30; done'
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF
```

2. [ROOT] Load and start: `sudo systemctl daemon-reload && sudo systemctl start test-hello-wannacry`
3. Get the main PID: `sudo systemctl show -p MainPID --value test-hello-wannacry` — note the number.
4. [ROOT] Kill it hard (service runs as root, so `sudo`):

```console
sudo kill -9 $(sudo systemctl show -p MainPID --value test-hello-wannacry)
```

5. [ROOT] Watch the fight — status and journal:

```console
sudo systemctl status test-hello-wannacry
sudo journalctl -u test-hello-wannacry -n 20
```

Wait ~3s (`RestartSec=2`), then check `status` again — it is back `active (running)`.
6. [ROOT] Change the policy to `on-failure`, reload, restart:

```console
sudo sed -i 's/Restart=always/Restart=on-failure/' /etc/systemd/system/test-hello-wannacry.service
sudo systemctl daemon-reload && sudo systemctl restart test-hello-wannacry
```

7. [ROOT] Kill again with the same `kill -9` — it still restarts: SIGKILL counts as a failure.
8. [ROOT] Now stop it cleanly: `sudo systemctl stop test-hello-wannacry` — wait a few seconds, check `status`. With `on-failure`, a clean exit is **not** a failure: it stays stopped.
9. [ROOT] Cleanup:

```console
sudo systemctl disable test-hello-wannacry
sudo rm /etc/systemd/system/test-hello-wannacry.service && sudo systemctl daemon-reload
```

**Expected output:**
- Step 4/5: journal shows `Main process exited, code=killed, status=9/KILL`, then `test-hello-wannacry.service: Scheduled restart job, restart counter is at N.` — the `Restart=always` loop in action (same pattern the module documents for `9router`, restart counter 249).
- Step 7: same `9/KILL` + restart again.
- Step 8: `Active: inactive (dead)` and **no** `Scheduled restart job` line after it.

**Verify:**

```console
sudo systemctl status test-hello-wannacry    # after step 8: Active: inactive (dead)
```

- [x] Exercise 2 done

## Exercise 3: build a backup timer

**Goal:** pair a `.timer` with its same-named `.service`, verify the schedule without waiting for 02:30, run the backup once manually, then tear it all down.

**Steps:**

1. [ROOT] Ensure the backup dir: `sudo mkdir -p /var/backups`
2. [ROOT] Write the service unit (a `oneshot` job — runs once and exits):

```console
sudo tee /etc/systemd/system/test-backup-wannacry.service > /dev/null <<'EOF'
[Unit]
Description=Test backup of the devops project (test)

[Service]
Type=oneshot
ExecStart=/bin/tar czf /var/backups/test-devops-wannacry.tar.gz /home/wannacry/devops-project/Test-Learn-Devops
EOF
```

(Tar a small dir, not the whole home — `tar czf ... /home/wannacry` would also work but is slow and big.)
3. [ROOT] Write the timer unit — the timer fires the **same-named** service (`test-backup-wannacry.timer` → `test-backup-wannacry.service`):

```console
sudo tee /etc/systemd/system/test-backup-wannacry.timer > /dev/null <<'EOF'
[Unit]
Description=Run test backup daily at 02:30

[Timer]
OnCalendar=*-*-* 02:30:00

[Install]
WantedBy=timers.target
EOF
```

4. [ROOT] Load both: `sudo systemctl daemon-reload`
5. [ROOT] Enable the **timer**, not the service — `WantedBy=timers.target` is what survives reboot:

```console
sudo systemctl enable test-backup-wannacry.timer
```

6. Verify the schedule without waiting (systemd 255 note: `systemd-analyze calendar` takes a calendar EXPRESSION, not a unit name; `list-timers` only shows a timer after it has been started):

```console
systemd-analyze calendar '*-*-* 02:30:00'
sudo systemctl start test-backup-wannacry.timer
systemctl list-timers | grep test-backup
```

7. [ROOT] Run it now — timers never fire early, so start the service directly:

```console
sudo systemctl start test-backup-wannacry.service
ls -lh /var/backups/test-devops-wannacry.tar.gz
```

8. [ROOT] Cleanup — stop and disable, remove units and archive, reload:

```console
sudo systemctl stop test-backup-wannacry.service test-backup-wannacry.timer
sudo systemctl disable test-backup-wannacry.timer
sudo rm /etc/systemd/system/test-backup-wannacry.service /etc/systemd/system/test-backup-wannacry.timer /var/backups/test-devops-wannacry.tar.gz
sudo systemctl daemon-reload
```

**Expected output:**
- Step 6: `systemd-analyze calendar '*-*-* 02:30:00'` prints the schedule and next elapse (next 02:30); `list-timers` shows `NEXT` = tomorrow 02:30, `ACTIVATES` = `test-backup-wannacry.service`.
- Step 7: archive exists, recent mtime, size = compressed devops-project.

**Verify:**

```console
systemctl list-timers | grep test-backup        # before cleanup: shows the timer; after: no output
systemd-analyze calendar '*-*-* 02:30:00'       # always works — expression form
```

- [x] Exercise 3 done

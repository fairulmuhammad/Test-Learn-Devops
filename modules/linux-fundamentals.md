# Linux Fundamentals

> Target: Ubuntu 24.04 server, user `wannacry`. Everything here is runnable as-is on that box.
> Prerequisite: SSH access to the server. No root required for exercises 1–2; exercise 3 uses `sudo`.

## Overview

Linux is the OS underneath almost every server, container, and cloud VM you will touch in DevOps. This module covers the minimum you must be fluent in: where things live on disk, how processes run, how permissions gate access, and how to glue commands together with pipes and redirection. Master this and everything else (systemd services, Docker, CI runners, Ansible) becomes easier, because all of them lean on these primitives.

## Key Concepts

### 1. Filesystem Hierarchy (FHS)

Linux organizes everything — files, devices, even running process info — under one root `/`. Key directories:

| Path | Purpose |
|---|---|
| `/` | Root of everything. All mounts hang off this tree. |
| `/bin`, `/sbin` | Essential user/admin binaries (`ls`, `cp`, `mount`). On Ubuntu these are symlinks to `/usr/bin` / `/usr/sbin`. |
| `/usr` | Most installed software: `/usr/bin`, `/usr/lib`, `/usr/share`. |
| `/etc` | System and app configuration files (plain text). |
| `/var` | Variable data: logs (`/var/log`), mail, spool, caches, `/var/lib` for state. |
| `/tmp` | Temporary files, wiped on reboot. World-writable (sticky bit). |
| `/home` | Per-user home directories (`/home/wannacry`). |
| `/root` | Root user's home (not under `/home`). |
| `/dev` | Device files (`/dev/sda`, `/dev/null`, `/dev/tty`). |
| `/proc` | Virtual filesystem exposing kernel + process data (`/proc/cpuinfo`, `/proc/1/`). Not real files on disk. |
| `/sys` | Virtual filesystem for kernel/device info. |
| `/opt` | Optional third-party software. |
| `/mnt`, `/media` | Manual mounts / removable media mounts. |

Rule of thumb: config in `/etc`, logs in `/var/log`, binaries in `/usr/bin`, your own stuff in `/home`.

### 2. Processes

A process is a running instance of a program. Each has a numeric PID; every process except the first (`systemd`, PID 1) has a parent (PPID). Processes form a tree.

- `systemd` is PID 1 on Ubuntu 24.04 — it starts and supervises everything else.
- Foreground processes occupy your shell; background processes (suffix `&`) don't.
- `kill` sends signals, not "kill commands": `SIGTERM` (15, polite shutdown, default), `SIGKILL` (9, forced, uncatchable), `SIGHUP` (1, hang up / reload config), `SIGINT` (2, Ctrl+C).
- A service is a long-running process managed by systemd; a daemon is any background process.

### 3. Users, Groups, Permissions

- Users authenticate and own processes/files. The superuser is `root` (UID 0). On Ubuntu, your user `wannacry` gets admin power through `sudo` (group `sudo`).
- Groups bundle users for shared access. `groups` shows your memberships; `id` shows UID/GID.
- Every file has an owner, a group, and a 10-character mode: `-rwxr-xr--`.

```
-  rwx  r-x  r--
│  └┬─┘ └┬─┘ └┬─
│   │    │    └── others (everyone else)
│   │    └─────── group members
│   └──────────── owner
└────────────── type: - file, d dir, l symlink, c char device, b block device
```

- Letters ↔ octal: `r=4`, `w=2`, `x=1`. `rwxr-xr--` = `754`. `rw-r--r--` = `644`. `rwx------` = `700`.
- `x` means *execute* for files, *search/traverse* for directories. To read a file's contents you need `r` on the file **and** `x` on every directory in its path.
- Special bits: setuid (4xxx, run as owner), setgid (2xxx, inherit group), sticky (1xxx, `t` — only owner can delete, e.g. `/tmp`).
- `sudo` = run one command as root; it is not "being root".

### 4. Pipes and Redirection

Standard streams: `stdin` (0, input), `stdout` (1, normal output), `stderr` (2, errors).

| Operator | Meaning |
|---|---|
| `>` | Redirect stdout to a file (overwrite). |
| `>>` | Append stdout to a file. |
| `2>` | Redirect stderr. |
| `2>&1` | Send stderr to wherever stdout goes (order matters: `> file 2>&1`). |
| `<` | Read file as stdin. |
| `\|` | Pipe: stdout of left command becomes stdin of right command. |
| `\| tee file` | Pass through to next command **and** write a copy to file. |
| `&` | Run command in background. |
| `;` | Run commands sequentially regardless of result. |
| `&&` | Run next only if previous succeeded (exit code 0). |
| `\|\|` | Run next only if previous failed. |
| `$?` | Exit code of last command (`0` = success). |

Pipes connect commands into pipelines: `ps aux | grep nginx | head -5`. This composition is the heart of the Unix way — small tools doing one thing, chained.

### 5. Essential commands at a glance

| Command | What it does | Typical use |
|---|---|---|
| `ls` | List directory contents | `ls -lah` (all, human sizes, long format) |
| `find` | Search files by name/type/size/time | `find /var/log -name "*.log" -mtime -7` |
| `grep` | Filter text by pattern | `grep -rn "listen" /etc/nginx/` |
| `ps` | Snapshot of processes | `ps aux`, `ps -ef` |
| `top` / `htop` | Live process + resource monitor | `top` (q to quit) |
| `df` | Disk usage per filesystem | `df -h` |
| `du` | Disk usage per directory | `du -sh /var/log/*` |
| `chmod` | Change permissions | `chmod 755 script.sh` |
| `chown` | Change owner/group | `chown wannacry:www-data app.log` |
| `ln` | Link files | `ln -s /opt/app/current /var/www/app` (symlink) |
| `tar` | Archive/compress | `tar -czf backup.tar.gz /etc` |
| `systemctl` | Control systemd services | `systemctl status nginx` |

## Command Cheat-Sheet

| Task | Command |
|---|---|
| See where you are | `pwd` |
| List files, hidden, sizes, human | `ls -lah` |
| Read file with line numbers | `cat -n file` |
| Page through a big file | `less /var/log/syslog` (q to quit) |
| Follow a log as it grows | `tail -f /var/log/syslog` |
| Find files by name | `find / -name "nginx.conf" 2>/dev/null` |
| Find files modified in last 7 days | `find /var/log -mtime -7 -type f` |
| Find large files | `find / -type f -size +100M -exec ls -lh {} \;` |
| Grep case-insensitive, recursive | `grep -rin "error" /etc/nginx/` |
| Grep with context lines | `grep -B2 -A2 "panic" app.log` |
| All my processes | `ps aux \| grep $USER` |
| Show process tree | `pstree -p` |
| Live resource view | `top` (sort by CPU: `P`, memory: `M`) |
| Disk free human-readable | `df -h` |
| Disk usage of a directory | `du -sh /var/www` |
| Top 10 biggest dirs under /var | `du -h --max-depth=1 /var \| sort -hr \| head -10` |
| Permissions of a file | `ls -l file` |
| Add execute for all | `chmod +x script.sh` |
| Set exact mode 644 | `chmod 644 file` |
| Change owner and group | `chown wannacry:devops file` |
| Recursive chown | `chown -R wannacry:devops /srv/app` |
| Symlink (file or dir) | `ln -s /real/target /shortcut` |
| Hard link | `ln /real/file /other/name` |
| Create tar.gz archive | `tar -czf backup.tar.gz /etc/nginx` |
| Extract tar.gz | `tar -xzf backup.tar.gz` |
| List archive contents | `tar -tzf backup.tar.gz` |
| Check a service | `systemctl status nginx` |
| Start/stop/restart a service | `sudo systemctl start/stop/restart nginx` |
| Enable service at boot | `sudo systemctl enable --now nginx` |
| See logs of a service | `journalctl -u nginx -f` |
| Read-only check, no output | `systemctl is-active nginx` |
| Redirect stdout to file | `cmd > out.log` |
| Redirect stderr to file | `cmd 2> err.log` |
| Both streams to one file | `cmd > all.log 2>&1` |
| Append instead of overwrite | `cmd >> app.log` |
| Pipe + capture copy | `cmd \| tee out.log` |
| Run only if previous OK | `mkdir -p /tmp/x && cd /tmp/x` |
| Run in background | `long-task.sh &` |
| Exit code of last command | `echo $?` |

## Hands-On Exercises

### Exercise 1 — Explore the filesystem and find things

```bash
cd ~
mkdir -p devops-lab/logs
echo "hello world" > devops-lab/logs/app.log
echo "ERROR: disk full" >> devops-lab/logs/app.log
ls -lah devops-lab/logs/
find devops-lab -name "*.log"
df -h
du -sh devops-lab
```

**Expected output (values will differ):**

```text
total 12K
drwxrwxr-x 2 wannacry wannacry 4.0K Aug  4 10:00 .
drwxrwxr-x 3 wannacry wannacry 4.0K Aug  4 10:00 ..
-rw-rw-r-- 1 wannacry wannacry   55 Aug  4 10:00 app.log
devops-lab/logs/app.log
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda2       100G   23G   77G  23% /
...
4.0K	devops-lab
```

Key takeaways: `find` returns the path(s) it matched; `df` shows mounted filesystems, not directories; `du -sh` gives one total for a tree.

### Exercise 2 — Processes, pipes, and grep

```bash
ps aux | grep -v grep | grep $USER
ps aux | sort -rk3 | head -5
top -bn1 | head -15
grep -c "ERROR" ~/devops-lab/logs/app.log
cat ~/devops-lab/logs/app.log | wc -l
echo "exit code of last pipe:" $?
```

**Expected output (values will differ):**

```text
wannacry   1234  0.0  0.1  15240  8768 pts/0    Ss   09:58   0:00 -bash
wannacry   1301  0.0  0.1  21368 10256 pts/0    R+   10:00   0:00 ps aux
...
USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
root         1  0.0  0.1 101652 13356 ?        Ss   Aug01   0:12 /sbin/init
...
1
2
exit code of last pipe: 0
```

Notes: `grep -v grep` drops the grep process itself from its own output; `sort -rk3` sorts by %CPU descending; `top -bn1` runs top once in batch mode instead of interactively; `wc -l` counts lines; `$?` after a successful pipeline is 0.

### Exercise 3 — Permissions, symlinks, archives, and a service check

```bash
cd ~/devops-lab
touch deploy.sh
chmod 755 deploy.sh
ls -l deploy.sh
ln -s deploy.sh shortcut-to-deploy
ls -l shortcut-to-deploy
tar -czf deploy-backup.tar.gz deploy.sh shortcut-to-deploy
tar -tzf deploy-backup.tar.gz
rm shortcut-to-deploy
systemctl is-active ssh 2>/dev/null || echo "ssh service not found"
sudo systemctl status ssh --no-pager | head -5
```

**Expected output (values will differ):**

```text
-rwxr-xr-x 1 wannacry wannacry 0 Aug  4 10:01 deploy.sh
lrwxrwxrwx 1 wannacry wannacry 10 Aug  4 10:01 shortcut-to-deploy -> deploy.sh
deploy.sh
shortcut-to-deploy
active
● ssh.service - OpenSSH server daemon
     Loaded: loaded (/usr/lib/systemd/system/ssh.service; enabled; preset: enabled)
     Active: active (running) since Mon 2026-08-03 09:00:12 UTC
   Main PID: 812 (sshd)
```

Notes: `755` = owner rwx, group r-x, others r-x — the standard for executable scripts; `tar -czf` archives *following* symlinks (the archive holds `deploy.sh`, not the link target's content); `is-active` prints `active`/`inactive`/`failed` and exits 0 only when active. On Ubuntu the SSH service is named `ssh` (not `sshd`).

## Common Pitfalls

1. **`chmod 777` for everything** — works, but any user can modify. Use the least permissive mode that works: `644` files, `755` scripts, `700` for secrets.
2. **Forgetting execute bit on directories** — `r` alone on a directory is useless; you need `x` to `cd` in or traverse it.
3. **`chown` the wrong way around** — order is `chown OWNER:GROUP file`, not group first.
4. **`rm` a symlink deletes the link, not the target** — but `rm -rf link/` (with trailing slash) or `rm -rf link` on a link to a directory in some tools can follow into the target. `tar` with symlinks can also surprise; check with `tar -tzvf` first.
5. **`>` wipes the file before the command runs** — `cat a.txt > a.txt` truncates `a.txt` to empty. Use `tee` or a temp file.
6. **Redirection order matters** — `cmd 2>&1 > file` sends only stdout to file; stderr still goes to the terminal. Correct: `cmd > file 2>&1`.
7. **`grep` from `ps aux` matches itself** — add `grep -v grep` or use `pgrep -f`.
8. **`df` vs `du` confusion** — `df` reports per-filesystem free space; `du` measures directory tree contents. A file deleted while still open can make `df` show space used that `du` can't find.
9. **`find` without `-type f` returns directories too** — you'll wonder why `grep` fails on "files" that are dirs.
10. **`sudo` not available on a plain user** — `wannacry` has sudo because it's in group `sudo`; on other boxes you may need `su -` to root instead.
11. **`systemctl` says "Failed to connect to bus"** — you're inside a container or chroot without systemd running. `service` or direct binary start may be the only option there.
12. **Exit code of a pipe is the last command's** — `false | true` exits 0. Use `set -o pipefail` in scripts to catch the left side failing.

## Further Reading

- `man` pages on the box: `man ls`, `man find`, `man grep`, `man bash`, `man systemctl` — first port of call.
- [Filesystem Hierarchy Standard (FHS)](https://refspecs.linuxfoundation.org/FHS_3.0/fhs-3.0.html) — the spec behind the directory layout.
- [Linux Command Line for Beginners — Ubuntu docs](https://ubuntu.com/tutorials/command-line-for-beginners)
- [TL;DR pages — community cheat sheets](https://tldr.sh/) (install: `sudo apt install tldr`)
- [explainshell.com](https://explainshell.com/) — paste a command, get a breakdown of every flag.
- [The Bash Guide](https://mywiki.wooledge.org/BashGuide) — deeper shell scripting.
- [DigitalOcean Linux Basics series](https://www.digitalocean.com/community/tutorials/linux-basics) — solid follow-up reading.

# Lab 01: Linux Fundamentals

**Module:** ../modules/linux-fundamentals.md
**Box:** Ubuntu 24.04, user `wannacry`
**Sudo needed:** only Exercise 3, last step — marked [ROOT]

## Setup

- Prereq: SSH access to the box (or a terminal as user `wannacry`)
- No packages to install — all commands are stock Ubuntu
- Create scratch workspace:

```bash
mkdir -p ~/scratch/devops-lab/logs
```

- All work happens under `~/scratch/devops-lab/` — nothing touches real system files
- [ROOT] steps need `sudo` (group `sudo`). No passwordless sudo on this box — the orchestrator provides the password when you reach those steps.

## Exercise 1 — Explore the filesystem and find things

**Goal:** create a small log file, then use `ls`, `find`, `df`, `du` to navigate and measure the filesystem.

**Steps:**

1. Create a log file with two lines:

```bash
echo "hello world" > ~/scratch/devops-lab/logs/app.log
echo "ERROR: disk full" >> ~/scratch/devops-lab/logs/app.log
```

2. List the logs directory with sizes:

```bash
ls -lah ~/scratch/devops-lab/logs/
```

3. Find every `*.log` file under the workspace:

```bash
find ~/scratch/devops-lab -name "*.log"
```

4. Check disk free space per filesystem:

```bash
df -h
```

5. Measure total size of the workspace tree:

```bash
du -sh ~/scratch/devops-lab
```

**Expected output (values will differ):**

```text
total 12K
drwxrwxr-x 2 wannacry wannacry 4.0K ... .
-rw-rw-r-- 1 wannacry wannacry   29 ... app.log
~/scratch/devops-lab/logs/app.log
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda2       100G   23G   77G  23% /
12K     ~/scratch/devops-lab
```

`find` prints the matched path; `df` shows mounted filesystems; `du -sh` gives one total for the tree.

**Verify:**

```bash
find ~/scratch/devops-lab -name "*.log"
```

[ ] returns `~/scratch/devops-lab/logs/app.log`

## Exercise 2 — Processes, pipes, and grep

**Goal:** inspect running processes with `ps`/`top`, chain commands with pipes, and filter with `grep`.

**Steps:**

1. List your own processes (drop the grep process itself from the output):

```bash
ps aux | grep -v grep | grep $USER
```

2. Top 5 processes by CPU:

```bash
ps aux | sort -rk3 | head -5
```

3. One-shot top snapshot (batch mode, no interactive UI):

```bash
top -bn1 | head -15
```

4. Count ERROR lines in the log from Exercise 1:

```bash
grep -c "ERROR" ~/scratch/devops-lab/logs/app.log
```

5. Count total lines with `wc -l`:

```bash
cat ~/scratch/devops-lab/logs/app.log | wc -l
```

6. Check the exit code of the last pipeline:

```bash
echo "exit code of last pipe:" $?
```

**Expected output (values will differ):**

```text
wannacry   1234  0.0  0.1  15240  8768 pts/0    Ss   09:58   0:00 -bash
USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
root         1  0.0  0.1 101652 13356 ?        Ss   Aug01   0:12 /sbin/init
top - 20:00:23 up ...
1
2
exit code of last pipe: 0
```

`grep -v grep` removes the grep process itself; `sort -rk3` sorts by %CPU descending; `$?` after a successful pipeline is `0`.

**Verify:**

```bash
echo $?
```

[ ] prints `0`

## Exercise 3 — Permissions, symlinks, archives, and a service check

**Goal:** make an executable script, symlink it, archive both with `tar`, and check the SSH service status.

**Steps:**

1. Create an empty script and give it mode `755`:

```bash
cd ~/scratch/devops-lab
touch deploy.sh
chmod 755 deploy.sh
ls -l deploy.sh
```

2. Symlink it, then inspect the link:

```bash
ln -s deploy.sh shortcut-to-deploy
ls -l shortcut-to-deploy
```

3. Archive both into a tarball, then list its contents:

```bash
tar -czf deploy-backup.tar.gz deploy.sh shortcut-to-deploy
tar -tzf deploy-backup.tar.gz
```

4. Remove the symlink (deletes the link, NOT the target):

```bash
rm shortcut-to-deploy
```

5. Check the SSH service without sudo:

```bash
systemctl is-active ssh 2>/dev/null || echo "ssh service not found"
```

6. [ROOT] Full service status (first 5 lines):

```bash
sudo systemctl status ssh --no-pager | head -5
```

**Expected output (values will differ):**

```text
-rwxr-xr-x 1 wannacry wannacry 0 ... deploy.sh
lrwxrwxrwx 1 wannacry wannacry 9 ... shortcut-to-deploy -> deploy.sh
deploy.sh
shortcut-to-deploy
active
● ssh.service - OpenSSH server daemon
     Loaded: loaded (/usr/lib/systemd/system/ssh.service; enabled; preset: enabled)
     Active: active (running) since ...
```

`755` = owner rwx, group r-x, others r-x. On Ubuntu the SSH service is named `ssh`, not `sshd`.

**Verify:**

```bash
ls -l ~/scratch/devops-lab/deploy.sh && tar -tzf ~/scratch/devops-lab/deploy-backup.tar.gz
```

[ ] `deploy.sh` shows `-rwxr-xr-x` and the tarball lists both entries

## Done

- [x] Exercise 1: created `~/scratch/devops-lab/logs/app.log`, `find` locates it
- [x] Exercise 2: piped `ps aux` through grep/sort, counted lines, exit code `0`
- [x] Exercise 3: `deploy.sh` executable, symlink archived, `ssh` service active
- [x] [ROOT] `sudo systemctl status ssh` ran without errors (status readable unprivileged; ssh active since boot)
- [ ] Cleanup (optional): `rm -rf ~/scratch/devops-lab`

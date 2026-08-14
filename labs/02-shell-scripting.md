# Lab 02: Shell Scripting

**Module:** ../modules/shell-scripting.md
**Box:** Ubuntu 24.04, user `wannacry`
**Sudo needed:** none

## Setup

- Prereq: Lab 01 done (comfort with `chmod`, `tar`, `~/scratch/`)
- Target shell: **Bash** (`/bin/bash`, the Ubuntu default)
- Create scratch workspace:

```bash
mkdir -p ~/scratch/shell-lab/data/config
mkdir -p ~/scratch/run_logs
```

- All scripts live in `~/scratch/shell-lab/` — nothing touches real project dirs
- Reference pattern from the module: `/home/wannacry/start_run.sh` (read it: `cat /home/wannacry/start_run.sh`)
- Every script starts with a shebang and `set -euo pipefail`

## Exercise 1 — Backup script

**Goal:** write `backup.sh` that tars a directory into `~/scratch/backups/<dirname>-<date>.tar.gz`, fails loudly on bad input.

**Steps:**

1. Create `~/scratch/shell-lab/backup.sh` with this content (or write your own — same behavior):

```bash
#!/bin/bash
# Purpose: back up a directory to ~/scratch/backups/<dirname>-<date>.tar.gz
# Usage:   ./backup.sh <directory>
set -euo pipefail

BACKUP_DIR="$HOME/scratch/backups"
LOG_FILE="$BACKUP_DIR/backup.log"

log() { echo "[$(date '+%F %T')] $*" >> "$LOG_FILE"; }

trap 'log "finish (exit $?)"' EXIT

[[ $# -eq 1 ]] || { echo "usage: $0 <dir>" >&2; exit 1; }
SRC="$1"
[[ -d "$SRC" ]] || { echo "ERROR: not a directory: $SRC" >&2; exit 1; }

mkdir -p "$BACKUP_DIR"
log "start: $SRC"
DEST="$BACKUP_DIR/$(basename "$SRC")-$(date +%F).tar.gz"
tar -czf "$DEST" "$SRC"
echo "backup created: $DEST"
```

2. Make it executable:

```bash
chmod +x ~/scratch/shell-lab/backup.sh
```

3. Make some data to back up:

```bash
echo "x=1" > ~/scratch/shell-lab/data/config/app.conf
```

4. Run it with a real directory:

```bash
~/scratch/shell-lab/backup.sh ~/scratch/shell-lab/data
```

5. Run it with a missing directory — must fail:

```bash
~/scratch/shell-lab/backup.sh /nonexistent
echo "exit code: $?"
```

6. Run it with no argument — must fail with usage:

```bash
~/scratch/shell-lab/backup.sh
echo "exit code: $?"
```

**Expected output (values will differ):**

```text
tar: Removing leading `/' from member names
backup created: /home/wannacry/scratch/backups/data-2026-08-04.tar.gz
ERROR: not a directory: /nonexistent
exit code: 1
usage: ./backup.sh <dir>
exit code: 1
```

**Verify:**

```bash
ls -l ~/scratch/backups/ && tar -tzf ~/scratch/backups/*.tar.gz
```

[ ] backup tarball exists, contains `data/config/app.conf`

## Exercise 2 — Argument parser

**Goal:** write `parse.sh` using `getopts` + `shift` that accepts `-n <name>`, a `-v` flag, and one positional arg.

**Steps:**

1. Create `~/scratch/shell-lab/parse.sh`:

```bash
#!/bin/bash
# Purpose: demo getopts parsing: -n <name>, -v flag, one positional target
# Usage:   ./parse.sh [-n name] [-v] <target>
set -euo pipefail

NAME=""
VERBOSE=false

usage() { echo "usage: $0 [-n name] [-v] <target>"; }

while getopts "n:vh" opt; do
    case "$opt" in
        n) NAME="$OPTARG" ;;
        v) VERBOSE=true ;;
        h) usage; exit 0 ;;
        *) usage >&2; exit 1 ;;
    esac
done
shift $((OPTIND - 1))

TARGET="${1:-}"
[[ -n "$TARGET" ]] || { usage >&2; exit 1; }

echo "name=$NAME verbose=$VERBOSE target=$TARGET"
```

2. Make it executable and run with flags + positional:

```bash
chmod +x ~/scratch/shell-lab/parse.sh
~/scratch/shell-lab/parse.sh -v -n alice prod
```

3. Run the help flag:

```bash
~/scratch/shell-lab/parse.sh -h
```

4. Run with no args — must exit 1:

```bash
~/scratch/shell-lab/parse.sh; echo "exit code: $?"
```

**Expected output:**

```text
name=alice verbose=true target=prod
usage: ./parse.sh [-n name] [-v] <target>
usage: ./parse.sh [-n name] [-v] <target>
exit code: 1
```

Flags parsed, `prod` left as the positional arg after `shift`.

**Verify:**

```bash
~/scratch/shell-lab/parse.sh -v -n alice prod
```

[ ] prints `name=alice verbose=true target=prod`

## Exercise 3 — Log rotator

**Goal:** write `rotator.sh` that deletes `.log` files older than 7 days in `~/scratch/run_logs/`, then wire it into cron.

**Steps:**

1. Create `~/scratch/shell-lab/rotator.sh`:

```bash
#!/bin/bash
# Purpose: delete *.log files in ~/scratch/run_logs older than 7 days
# Usage:   ./rotator.sh
set -euo pipefail

LOG_DIR="$HOME/scratch/run_logs"
mkdir -p "$LOG_DIR"

deleted=0
for f in "$LOG_DIR"/*.log; do
    [[ -f "$f" ]] || continue
    if [[ -n "$(find "$f" -mtime +7)" ]]; then
        echo "deleting: $f"
        rm -f "$f" || true
        deleted=$((deleted + 1))
    fi
done
echo "deleted $deleted file(s) older than 7 days"
```

2. Make it executable:

```bash
chmod +x ~/scratch/shell-lab/rotator.sh
```

3. Create one old log (mtime 10 days back) and one fresh log:

```bash
echo "old" > ~/scratch/run_logs/old.log
touch -d "10 days ago" ~/scratch/run_logs/old.log
echo "new" > ~/scratch/run_logs/new.log
```

4. Run the rotator:

```bash
~/scratch/shell-lab/rotator.sh
```

5. Confirm only the fresh log remains:

```bash
ls ~/scratch/run_logs/
```

6. Install the cron line (append to existing crontab, non-interactive — safer than `crontab -e`):

```bash
( crontab -l 2>/dev/null; echo "0 3 * * * /home/wannacry/scratch/shell-lab/rotator.sh >> /home/wannacry/scratch/run_logs/rotator.log 2>&1" ) | crontab -
```

7. Verify the cron job is installed:

```bash
crontab -l
```

8. Remove the test cron line when done (keeps the box clean):

```bash
crontab -l | grep -v "rotator.sh" | crontab -
crontab -l
```

**Expected output (values will differ):**

```text
deleting: /home/wannacry/scratch/run_logs/old.log
deleted 1 file(s) older than 7 days
new.log
0 3 * * * /home/wannacry/scratch/shell-lab/rotator.sh >> /home/wannacry/scratch/run_logs/rotator.log 2>&1
```

**Verify:**

```bash
ls ~/scratch/run_logs/ && crontab -l
```

[ ] only `new.log` remains; cron line listed (until step 8 removes it)

## Done

- [x] Exercise 1: `backup.sh` creates tarball for real dir, exits 1 for missing dir / no arg
- [x] Exercise 2: `parse.sh` prints `name=alice verbose=true target=prod`
- [x] Exercise 3: `rotator.sh` deleted the old log, kept the new one
- [x] Exercise 3: cron line installed and verified with `crontab -l`, then removed
- [ ] Cleanup (optional): `rm -rf ~/scratch/shell-lab ~/scratch/backups ~/scratch/run_logs`

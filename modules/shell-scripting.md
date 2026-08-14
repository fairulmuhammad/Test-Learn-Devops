# Shell Scripting

DevOps glue language. Services, cron jobs, CI pipelines, deploy scripts — all shell. This module covers Bash essentials with patterns taken from a real script on this box: `/home/wannacry/start_run.sh`.

Target shell: **Bash** (Ubuntu default `/bin/bash`). Scripts must be executable and start with a shebang.

---

## Overview

Shell scripting = running commands + controlling flow + handling errors. Three things make scripts break:

1. **Word splitting** — unquoted variables get split on spaces.
2. **Silent failures** — commands fail but the script keeps going.
3. **Missing quoting** — filenames with spaces, globs, special chars bite you.

Master quoting and `set -euo pipefail` and you avoid 90% of script bugs.

---

## Script Anatomy

Annotated real example — `/home/wannacry/start_run.sh` (a tracker that starts a background Python process):

```bash
#!/bin/bash                          # shebang: interpreter for the script
# Start HM Tracking Script           # comment
# Usage: ./start_run.sh              # usage note in header

set -e                               # exit on first error

LOG_DIR="$HOME/run_logs"             # variables: no spaces around =, quote values
mkdir -p "$LOG_DIR"                  # quoted var; mkdir -p = create if missing

VENV_PYTHON="$HOME/.hermes/hermes-agent/venv/bin/python3"
TRACK_SCRIPT="$HOME/track_run.py"
PID_FILE="/tmp/track_run.pid"

# Kill existing tracker if running
if [ -f "$PID_FILE" ]; then          # test -f: file exists?  (single brackets)
    OLD_PID=$(cat "$PID_FILE")       # command substitution $(...) captures output
    if ps -p "$OLD_PID" > /dev/null 2>&1; then   # check process alive; discard output
        echo "Killing old tracker (PID: $OLD_PID)"
        kill "$OLD_PID" || true      # || true: ignore failure, keep going
        sleep 1
    fi
fi

# Start tracker in background
$VENV_PYTHON "$TRACK_SCRIPT" > "$LOG_DIR/tracker.log" 2>&1 &   # redirect + background
NEW_PID=$!                           # $! = PID of last background job
echo "$NEW_PID" > "$PID_FILE"        # save PID for later cleanup
```

Patterns worth copying from this script:

| Pattern | Why |
|---|---|
| `#!/bin/bash` | Explicit interpreter |
| `set -e` | Fail fast |
| `"$VAR"` everywhere | No word splitting, no glob expansion |
| `$(...)` | Capture command output (never backticks) |
| `|| true` | Tolerate expected failures (process already dead) |
| `$!` + PID file | Manage background processes |
| `> file 2>&1 &` | Log output + detach |

---

## Core Syntax

### Shebang

First line, must be byte-for-byte first. Tells the kernel which interpreter runs the file.

```bash
#!/bin/bash        # bash
#!/usr/bin/env python3   # python — env finds interpreter in PATH
```

Script must be executable:

```bash
chmod +x start_run.sh
./start_run.sh     # runs via shebang
bash start_run.sh  # works too, ignores shebang
```

### Variables

```bash
NAME="world"            # NO spaces around = (unlike most languages)
NAME="hello world"      # quote values with spaces
readonly API_KEY="x"    # cannot be reassigned
export PATH="$PATH:/opt/bin"   # visible to child processes
echo "$NAME"            # expand: "$VAR" — always quote
echo "${NAME}_suffix"   # braces separate var name from text
echo "${NAME:-default}" # default if unset/empty
echo "${NAME:?must be set}"  # error out if unset
unset NAME              # remove
```

Environment variables: `HOME`, `USER`, `PATH`, `PWD`, `SHELL`. Script variables are local to the script unless `export`ed.

### Quoting Rules

```bash
"double quotes"   # expands $VAR, $(cmd), `cmd`
'single quotes'   # literal — no expansion at all
$'tab\there'      # ANSI escapes in single quotes
""                # empty string, safe
```

Rule: **quote every variable expansion unless you deliberately want splitting/globbing.**

```bash
file="my file.txt"
touch $file      # WRONG: creates "my" and "file.txt"
touch "$file"    # RIGHT: one file "my file.txt"
```

### Arrays

```bash
files=("a.txt" "b.txt" "c file.txt")
echo "${files[0]}"          # first element
echo "${files[@]}"          # all elements, each quoted separately
echo "${#files[@]}"         # count
files+=("d.txt")            # append
for f in "${files[@]}"; do  # loop — @ + quotes = safe with spaces
    echo "$f"
done
```

Never `for f in $files` (unquoted) — splits and globs. Never use arrays when a plain string or loop over glob works.

### Conditionals — `test` / `[ ]` vs `[[ ]]`

```bash
if [ "$count" -gt 5 ]; then      # POSIX test — spaces around [ and ] required
    echo "big"
fi

if [[ "$name" == "admin" ]]; then   # bash builtin: no word-splitting inside
    echo "admin"                    # supports ==, =~ regex, && ||
fi

if [ -f "$file" ]; then echo "exists"; fi     # file tests
if [ -d "$dir" ]; then echo "dir"; fi
if [ -z "$var" ]; then echo "empty"; fi       # -z empty, -n non-empty
if [ -x "$bin" ]; then echo "executable"; fi
```

File tests: `-f` file, `-d` directory, `-e` exists, `-r` readable, `-w` writable, `-x` executable, `-s` non-empty.

Numeric: `-eq -ne -gt -ge -lt -le`. String: `= != < >`. In `[[ ]]`: `==`, `!=`, `=~` regex, `&&`, `||`, no quoting needed inside.

```bash
[[ "$url" =~ ^https:// ]] && echo "secure"    # regex match
[[ -f "$f" && -s "$f" ]] && echo "non-empty file"
```

`[[ ]]` is bash-only (not POSIX sh). Prefer `[[ ]]` in bash scripts.

### Loops

```bash
# for — iterate a list
for env in dev staging prod; do
    echo "deploying to $env"
done

# for — C style
for ((i=1; i<=5; i++)); do
    echo "attempt $i"
done

# for — over files (globbing is fine and safe here)
for log in /var/log/*.log; do
    echo "found $log"
done

# while — read lines (file-safe: no word splitting)
while IFS= read -r line; do
    echo "got: $line"
done < input.txt

# while — wait for condition
while ! curl -sf http://localhost:8080/health; do
    sleep 2
done
echo "service up"
```

`break` exits loop, `continue` skips to next iteration. `read -r` preserves backslashes; `IFS=` prevents stripping leading/trailing whitespace.

### Functions

```bash
log() {
    local msg="$1"          # local: scoped, $1 = first arg
    echo "[$(date +%H:%M:%S)] $msg"
}

fail() {
    echo "ERROR: $*" >&2    # $* = all args joined; >&2 to stderr
    exit 1
}

log "starting deploy"
fail "no config found"
```

Functions must be **defined before called**. Return value = exit status of last command; `return N` sets it explicitly. `$1..$9`, `${10}`, `$@`, `$#` inside function = function's args, not script's.

### Exit Codes

```bash
exit 0      # success
exit 1      # generic error (1-255 allowed; 0 only success)
echo $?     # exit status of last command
```

Convention: 0 = success, non-zero = failure. `$?` is checked immediately after a command — any intervening command overwrites it.

```bash
if grep -q "ready" status.txt; then
    echo "ready"          # if/while can test commands directly
fi
```

### Argument Parsing — `$@`, `$#`, `shift`, `getopts`

```bash
echo "script: $0"          # script name
echo "arg count: $#"       # number of args
echo "all args: $@"        # all args, quoted properly
echo "first: $1"           # positional args: $1, $2, ...
shift                      # drop $1, $2 becomes $1
```

Simple loop over args:

```bash
for arg in "$@"; do
    echo "arg: $arg"
done
```

`getopts` — standard flag parser (dash: `-a`, options with values: `-o value`):

```bash
while getopts "ho:" opt; do        # h: flag, o: requires argument
    case "$opt" in
        h) usage; exit 0 ;;
        o) OUTPUT="$OPTARG" ;;
        *) usage; exit 1 ;;
    esac
done
shift $((OPTIND - 1))              # remove processed flags, rest = positional args
echo "output=$OUTPUT, positional=$*"
```

### Process Substitution

Feed command output where a file is expected — `<(...)` (as input) and `>(...)` (as output):

```bash
diff <(ls dir1) <(ls dir2)         # compare two listings without temp files
while read -r ip; do ping -c1 "$ip"; done < <(grep -E '^[0-9.]+$' hosts.txt)

# with process substitution, loop runs in current shell (variables persist)
# with a pipe, loop runs in a subshell (variables lost):
cat hosts.txt | while read -r ip; do :; done   # count lost after pipe
```

Process substitution gives `/dev/fd/N` paths — works with tools that only accept files. Bash-only, not POSIX sh.

### Cron Basics

```bash
crontab -e            # edit your cron jobs
crontab -l            # list them
```

Format: `minute hour day-of-month month day-of-week command`

```cron
*/5 * * * * /home/wannacry/devops-project/check.sh          # every 5 min
0 2 * * * /home/wannacry/devops-project/backup.sh           # 02:00 daily
0 9 * * 1 /home/wannacry/devops-project/report.sh           # Mon 09:00
@reboot /home/wannacry/devops-project/start_run.sh          # at boot
```

Cron rules that save your sanity:

1. **Use absolute paths** — cron runs with minimal environment (`PATH=/usr/bin:/bin`), no `$HOME` guaranteed, no login shell.
2. **Redirect output** — cron emails output by default (often to nowhere). Always: `>> /home/wannacry/run_logs/check.log 2>&1`.
3. **Use a wrapper script**, not inline commands — quoting hell and debugging in crontab is painful.
4. **Set your own env** at script top: `export PATH="/usr/local/bin:$PATH"`.
5. `%` is special in cron — escape as `\%` or put it in the script.

```cron
*/10 * * * * /home/wannacry/devops-project/check.sh >> /home/wannacry/run_logs/check.log 2>&1
```

---

## Error Handling — `set -euo pipefail`

The standard hardening line, put right after the shebang:

```bash
#!/bin/bash
set -euo pipefail
```

| Flag | What it does |
|---|---|
| `-e` | Exit immediately on any command returning non-zero |
| `-u` | Error on unset variable (`$UNDEFINED` aborts instead of expanding empty) |
| `-o pipefail` | Pipeline fails if **any** stage fails, not just the last (`a | b` fails if `a` fails) |
| `-x` | Print each command before running — debug mode |

Without `pipefail`: `grep missing file | head -1` exits 0 even though grep failed. With it: fails.

Caveats:

- `-e` doesn't trigger inside `if` conditions, `&&`/`||` lists, or commands whose failure is checked — that's by design.
- Explicitly tolerated failures need `|| true` (see `start_run.sh`: `kill "$OLD_PID" || true`).
- With `-u`, always give defaults: `${VAR:-default}`.
- With `-e`, command substitution failures abort: `PID=$(pgrep x)` aborts if pgrep finds nothing — use `|| true` or `-` defaults where appropriate.

Trap for cleanup on exit:

```bash
cleanup() {
    rm -f "$PID_FILE"
    echo "cleaned up"
}
trap cleanup EXIT          # runs on normal exit
trap 'echo interrupted' INT   # runs on Ctrl-C
```

`start_run.sh` writes a PID file precisely so a later run (or a trap) can clean up the background process.

---

## Reusable Script Template

```bash
#!/bin/bash
# Purpose: <what this script does>
# Usage:   ./script.sh [-v] [args...]
set -euo pipefail

# --- config ---
LOG_FILE="${LOG_FILE:-$HOME/run_logs/script.log}"
VERBOSE=false

# --- helpers ---
log()  { echo "[$(date '+%F %T')] $*" >> "$LOG_FILE"; }
die()  { echo "ERROR: $*" >&2; exit 1; }
usage(){ echo "Usage: $0 [-v] <target>"; exit 1; }

# --- argument parsing ---
while getopts "vh" opt; do
    case "$opt" in
        v) VERBOSE=true ;;
        h) usage ;;
        *) usage ;;
    esac
done
shift $((OPTIND - 1))
[[ $# -eq 1 ]] || usage
TARGET="$1"

# --- main ---
mkdir -p "$(dirname "$LOG_FILE")"

if [[ "$VERBOSE" == true ]]; then
    echo "target: $TARGET"
fi

log "start: $TARGET"
if [[ ! -d "$TARGET" ]]; then
    die "not a directory: $TARGET"
fi

for f in "$TARGET"/*; do
    [[ -f "$f" ]] || continue
    echo "processing: $(basename "$f")"
done

log "done: $TARGET"
```

Copy, edit config block, write main, done.

---

## Hands-On Exercises

**Exercise 1 — backup script.** Write `/home/wannacry/devops-project/backup.sh` that:
- takes one arg: a directory
- creates `~/backups/<dirname>-<date>.tar.gz` with `tar -czf`
- prints success with the backup path, exits 1 if arg missing or dir doesn't exist
- use `set -euo pipefail` and a `trap` to log start/finish

Check: `chmod +x backup.sh`, run with a real dir and a missing dir.

**Exercise 2 — argument parser.** Write `parse.sh` accepting `-n <name>` and `-v` flags plus one positional arg, using `getopts` + `shift`. Print parsed values. Then call it:
```bash
./parse.sh -v -n alice prod
./parse.sh -h
```
Expected: flags parsed, `prod` left as positional.

**Exercise 3 — log rotator.** Write `rotator.sh` that:
- loops over `~/run_logs/*.log` with `for f in ...; do`
- keeps files newer than 7 days (use `find "$HOME/run_logs" -name '*.log' -mtime +7 -delete` or `test` + `stat`)
- prints each file it deletes, `|| true` so one failure doesn't stop the loop

Then add a cron line: `0 3 * * * /home/wannacry/devops-project/rotator.sh >> $HOME/run_logs/rotator.log 2>&1` (install with `crontab -e`). Verify with `crontab -l`.

---

## Pitfalls

| Pitfall | Fix |
|---|---|
| **Spaces in filenames** — `rm $file` deletes two files | Always `"$file"` |
| **Word splitting** — `for x in $list` splits on spaces | `"${list[@]}"` or `while read -r` |
| **Globbing on expansion** — `rm $pattern` expands `*` | quote it: `rm "$pattern"` |
| **`command not found` vs `Permission denied`** — first = not in `$PATH` or typo; second = file exists but not executable | `chmod +x` or `bash script.sh`; check `which cmd` |
| **Unquoted `$(...)`** — output with spaces splits | `VAR="$(cmd)"` |
| **`if [ $var = x ]`** with empty `$var` — syntax error | `[ "$var" = x ]` or `[[ $var == x ]]` |
| **Spaces around `=`** — `NAME = "x"` runs `NAME` as command | `NAME="x"` |
| **Backticks** — unreadable, nested quoting breaks | `$(...)` |
| **CRLF line endings** — script copied from Windows fails with `\r: command not found` | `sed -i 's/\r$//' script.sh` or `dos2unix` |
| **Forgetting `chmod +x`** — `./script.sh` says permission denied | `chmod +x` |
| **Silent failures** — script continues after error | `set -euo pipefail` |
| **Cron env** — script works manually, fails in cron | absolute paths + redirect output + set `PATH` in script |
| **`$?` checked too late** | capture immediately: `rc=$?` |
| **Modifying script while running** — bash reads ahead; edits can corrupt execution | stop process first |
| **`tail -f` in cron/background scripts** | use `tail -n N` or `-F` |

Debugging: `bash -x script.sh` shows every command; add `set -x` temporarily.

---

## Further Reading

- `man bash` — the reference (search: `/ARRAYS`, `/getopts`)
- [Bash Guide — mywiki.wooledge.org/BashGuide](https://mywiki.wooledge.org/BashGuide)
- [Bash Pitfalls — mywiki.wooledge.org/BashPitfalls](https://mywiki.wooledge.org/BashPitfalls)
- [Google Shell Style Guide](https://google.github.io/styleguide/shellguide.html)
- [ShellCheck — shellcheck.net](https://www.shellcheck.net/) — lint your scripts; install with `apt install shellcheck`
- [ExplainShell](https://explainshell.com/) — paste any command, get breakdown
- `man 5 crontab` — cron format reference

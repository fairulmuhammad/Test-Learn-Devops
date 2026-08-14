# Lab 06: CI/CD

## Setup

- Prereqs: git, a GitHub account (workflow push is optional — **do NOT push** in this lab).
- All work happens in a scratch git repo: `/home/wannacry/scratch/ci-demo/`.
- SAFETY: do NOT push anything, and do NOT touch the `magang-rbtv` repo (`~/project/magang-rbtv`) or its real `.github/workflows/` — those workflows are ground truth to read, not to modify. Exercises 2–3 here are re-targeted versions of the module's exercises that keep the same concepts in the scratch repo.
- Source module: `modules/ci-cd.md`.

## Exercise 1: Minimal workflow in a scratch repo

**Goal:** create a real workflow file in a real git repo and validate it locally.

**Steps**

1. Create the scratch repo and workflow directory:
   ```bash
   mkdir -p ~/scratch/ci-demo/.github/workflows
   cd ~/scratch/ci-demo
   ```
2. Create `.github/workflows/hello.yml`:
   ```yaml
   name: Hello CI
   on: [push, workflow_dispatch]
   jobs:
     hello:
       runs-on: ubuntu-latest
       steps:
         - run: echo "Hello from ${{ github.actor }} on ${{ github.ref }}"
   ```
3. Validate the YAML parses:
   ```bash
   python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/hello.yml')); print('YAML OK')"
   ```
   (If `yaml` is missing: `pip install pyyaml --break-system-packages` or use `ruby -e "require 'yaml'; YAML.load_file('.github/workflows/hello.yml'); puts 'YAML OK'"`.)
4. Commit it (local only, no push):
   ```bash
   git init -b main
   git add . && git commit -m "add hello workflow"
   ```
5. Optional local lint with `actionlint` (catches workflow-syntax and expression errors without pushing):
   ```bash
   actionlint .github/workflows/hello.yml   # or: go install github.com/rhysd/actionlint/cmd/actionlint@latest
   ```

**Expected output:** step 3 prints `YAML OK`. Step 4 commits cleanly. `actionlint` prints nothing on success (exit 0).

**Verify:** `git -C ~/scratch/ci-demo log --oneline` shows the commit. If you ever push this repo to GitHub, the Actions tab would show a "Hello CI" run echoing `Hello from <you> on refs/heads/main`.

- [x] hello.yml created, YAML validated, commit made in scratch repo (not pushed)

## Exercise 2: Matrix + caching workflow (no real repo touched)

**Goal:** build the `tests.yml` shape from the module — a `quality` job gating a `tests` job that runs a PHP matrix with cached composer deps — as a linted YAML file in the scratch repo.

**Steps**

1. Create `.github/workflows/ci.yml` in the scratch repo:
   ```yaml
   name: CI
   on:
     push:
       branches: [ "main" ]
   jobs:
     quality:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - run: echo "pint --test + phpstan --memory-limit=2G would run here"
     tests:
       needs: quality
       runs-on: ubuntu-latest
       strategy:
         fail-fast: true
         matrix:
           php: [ '8.2', '8.3', '8.4' ]
       steps:
         - uses: actions/checkout@v4
         - name: Cache Composer dependencies
           uses: actions/cache@v4
           with:
             path: ~/.composer/cache/files
             key: ${{ runner.os }}-composer-${{ hashFiles('composer.lock') }}
             restore-keys: ${{ runner.os }}-composer-
         - uses: shivammathur/setup-php@v2
           with:
             php-version: ${{ matrix.php }}
         - run: echo "composer install && php artisan test on PHP ${{ matrix.php }}"
   ```
2. Validate YAML:
   ```bash
   python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('YAML OK')"
   ```
3. Lint with actionlint if installed:
   ```bash
   actionlint .github/workflows/ci.yml
   ```
4. Commit:
   ```bash
   git add . && git commit -m "add matrix CI workflow"
   ```

**Expected output:** `YAML OK`, actionlint silent. The `tests` job runs 3 times (one per PHP version); `needs: quality` makes it wait for quality to pass; the cache key changes when `composer.lock` changes.

**Verify:** `git -C ~/scratch/ci-demo status` is clean, log shows both commits. Answer: why does `${{ matrix.php }}` appear in step 2's `with:`? (Each matrix combo gets its own VM with its own value.)

- [x] ci.yml with matrix + cache written, validated, committed (not pushed)

## Exercise 3: Deploy job with an environment gate (file only)

**Goal:** write the CD shape from the module — `build` → `deploy` with an `environment: production` gate — without touching the real repo or real secrets.

**Steps**

1. Create `.github/workflows/cd.yml` in the scratch repo:
   ```yaml
   name: CD
   on:
     push:
       branches: [ "server" ]
     workflow_dispatch:
   env:
     IMAGE: ghcr.io/<you>/ci-demo
   jobs:
     build:
       runs-on: ubuntu-latest
       permissions:
         contents: read
         packages: write
       steps:
         - uses: actions/checkout@v4
         - name: Build image
           run: echo "docker/build-push-action would tag ${{ env.IMAGE }}:${{ github.sha }} here"
     deploy:
       needs: build
       runs-on: ubuntu-latest
       environment:
         name: production
         url: https://your-app.example.com
       steps:
         - name: Deploy over SSH
           uses: appleboy/ssh-action@v1
           with:
             host: ${{ secrets.SERVER_HOST }}
             username: ${{ secrets.SERVER_USER }}
             key: ${{ secrets.SSH_PRIVATE_KEY }}
             script: |
               git pull --ff-only
               docker compose up -d --build
   ```
2. Validate YAML:
   ```bash
   python3 -c "import yaml; yaml.safe_load(open('.github/workflows/cd.yml')); print('YAML OK')"
   ```
3. Commit:
   ```bash
   git add . && git commit -m "add CD workflow with environment gate"
   ```

**Expected output:** `YAML OK`. Secret values (`SERVER_HOST`, `SERVER_USER`, `SSH_PRIVATE_KEY`) are placeholders — in a real repo they live in **Settings → Environments → production → Environment secrets**, never in the YAML. GitHub never prints secret values; logs show `***`.

**Verify:** `git -C ~/scratch/ci-demo log --oneline | wc -l` shows 3 commits. Answer: what makes the deploy job wait in **pending** until a human approves? (An `environment: production` protection rule — required reviewers — set in Settings → Environments, not in the workflow file.)

**Note:** the real magang-rbtv repo's equivalent deploy triggers on `push: branches: [server]` — this repo's prod branch is named `server`. Leave the real repo untouched; this scratch file demonstrates the same shape.

- [x] cd.yml with environment gate written, validated, committed (not pushed)

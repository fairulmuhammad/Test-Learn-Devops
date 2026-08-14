# CI/CD

DevOps module. CI/CD = automated pipeline between "code committed" and "code running in production". Grounded in live state of this server and the `fairulmuhammad/magang-rbtv` repo (Laravel 12 + Filament 4, PHP 8.2/8.4, FrankenPHP Docker build, docker compose prod override).

Live inventory at time of writing:

```console
$ gh --version        # not installed on this box — GitHub CLI absent
$ ls ~/.git-credentials   # exists → git credential helper holds a PAT, usable via git push/pull
$ git -C ~/project/magang-rbtv remote -v
origin  https://fairulmuhammad:ghp_***@github.com/fairulmuhammad/magang-rbtv.git
$ git -C ~/project/magang-rbtv branch --show-current
server
```

The repo already has real GitHub Actions workflows (`.github/workflows/tests.yml`, `ci.yml`) — this module reads those as ground truth, not invented examples.

---

## 1. Overview: CI vs CD

| Term | What it does | Answer to |
|---|---|---|
| **CI** (Continuous Integration) | Every push: checkout → install deps → lint → static analysis → tests → build. Fast feedback. Fails the commit loudly. | "Does this code still work together?" |
| **CD** (Continuous Delivery) | CI + build artifact (image, package) that is **ready to deploy**; deploy to staging/prod still human-triggered or gated. | "Is this shippable?" |
| **CDE** (Continuous Deployment) | Every green pipeline auto-deploys to prod. | "Is it in production?" |

Pipeline = the whole automated chain. Stage = one named phase (lint, test, build, deploy). Job = unit of work a runner executes (can contain many steps, runs on one machine). Step = one command or one action. Artifact = file produced by a job and handed to another job (or downloaded later). Environment = named deployment target (staging, prod) with its own secrets + protection rules.

The repo's `.github/workflows/ci.yml` (real, in the repo today) is a pure-CI example: lint + test only, no deploy. The pipeline grows toward CD by adding `build` (docker image) and `deploy` (compose up on server) stages.

---

## 2. GitHub Actions anatomy

Workflow = YAML file in `.github/workflows/`. Every push/PR, GitHub matches the file's `on:` triggers against the event, spins up a fresh runner VM, and executes the jobs.

Annotated real workflow — `ci.yml` from the magang-rbtv repo, line by line:

```yaml
name: CI                                  # display name in the Actions tab

on:                                       # triggers — see table in §3
  push:
    branches: [ "main", "server" ]        # only these branches on push
  pull_request:
    branches: [ "main", "server" ]        # PRs targeting these branches

jobs:                                     # each job = fresh VM, runs in parallel by default
  test:
    runs-on: ubuntu-latest                # GitHub-hosted runner: Ubuntu 24.04, 4 vCPU, 16GB RAM

    services:                             # ephemeral helper container, same network as the job
      mysql:
        image: mysql:8.0                  # like docker compose, but for CI
        env:
          MYSQL_ROOT_PASSWORD: root
          MYSQL_DATABASE: testing
        ports:
          - 3306:3306
        options: --health-cmd="mysqladmin ping" --health-interval=10s --health-timeout=5s --health-retries=3

    steps:                                # sequential; one fails → job fails (unless continue-on-error)
      - uses: actions/checkout@v4         # action = reusable step from the marketplace; checks out the code

      - name: Setup PHP
        uses: shivammathur/setup-php@v2   # community action, pinned by major tag
        with:                             # action inputs
          php-version: '8.4'
          extensions: pdo, pdo_mysql, bcmath, curl, dom, fileinfo, intl, mbstring, openssl, xml, zip

      - name: Copy .env                   # run: = shell command step, not an action
        run: php -r "file_exists('.env') || copy('.env.example', '.env');"

      - name: Install Dependencies
        run: composer install -q --no-ansi --no-interaction --no-scripts --no-progress --prefer-dist

      - name: Run Pest Tests
        run: php artisan test
        env:                              # step-level env, overrides for this step only
          DB_CONNECTION: mysql
          DB_HOST: 127.0.0.1
          DB_PORT: 3306
```

The second real workflow, `tests.yml`, shows the bigger-picture pieces:

```yaml
permissions:                              # least-privilege for the GITHUB_TOKEN
  contents: read

concurrency:                              # §7 — one run per branch at a time
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

env:                                      # workflow-level env, visible to every job
  NODE_VERSION: '20'

jobs:
  quality:                                # lint + static analysis first
    steps:
      - run: ./vendor/bin/pint --test          # code style
      - run: ./vendor/bin/phpstan analyse --memory-limit=2G
        continue-on-error: true                # don't block on PHPStan (deliberate choice in this repo)

  tests:
    needs: quality                        # job dependency: runs only after `quality` passes
    strategy:
      fail-fast: true                     # matrix: one failure kills the rest
      matrix:
        php: [ '8.4' ]                    # §6 — expand to [ '8.2', '8.3', '8.4' ] to test more versions

  build-assets:                           # parallel with tests (no `needs`)
    runs-on: ubuntu-latest
    steps:
      - run: npm ci
      - run: npm run build                # Vite build → public/build must exist
```

Full CD example for this project (lint → test → build image → deploy) — the shape to grow into:

```yaml
name: CI/CD
on:
  push:
    branches: [ server ]
  workflow_dispatch:                      # manual trigger from the Actions tab

env:
  IMAGE: ghcr.io/fairulmuhammad/magang-rbtv

jobs:
  quality:                                # as in tests.yml — pint + phpstan
    ...
  tests:                                  # as in ci.yml — needs: quality, Pest + mysql service
    ...
  build:
    needs: tests
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write                     # needed to push to GHCR
    outputs:                              # pass the tag to the deploy job
      image: ${{ steps.meta.outputs.tags }}
    steps:
      - uses: actions/checkout@v4
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: ${{ env.IMAGE }}:${{ github.sha }}, ${{ env.IMAGE }}:latest

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment: production               # §5 — protection rules + prod secrets
    steps:
      - name: Deploy over SSH
        uses: appleboy/ssh-action@v1        # common pattern; alternatives: deploy keys, self-hosted runner
        with:
          host: ${{ secrets.SERVER_HOST }}  # values come from Environment secrets, never from the repo
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /home/wannacry/project/magang-rbtv
            git pull --ff-only
            docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
            docker system prune -f
```

Note: this repo runs on a branch named `server`, so deploy triggers off `push: branches: [server]` — the equivalent of "main" for this project.

---

## 3. Events / triggers

| Event | YAML | Fires when |
|---|---|---|
| Push | `on: push` (filter: `branches:`, `paths:`, `tags:`) | code pushed |
| Pull request | `on: pull_request` | PR opened / updated / reopened; `pull_request_target` = safe version that runs with base-branch secrets (use only for trusted PRs) |
| Schedule | `on: schedule: - cron: '0 3 * * *'` | cron, UTC, min interval 5 min, may be delayed on busy queues |
| Manual | `on: workflow_dispatch` | button in Actions tab (requires `workflow_dispatch` in file on default branch) |
| Repository dispatch | `on: repository_dispatch: types: [deploy]` | external API/webhook: `POST /repos/{owner}/{repo}/dispatches` |
| Another workflow | `on: workflow_run: workflows: [CI]` | the named workflow finishes (use for dependent pipelines) |
| Tag | `on: push: tags: ['v*']` | version tag pushed — classic release trigger |
| Path filter | `on: push: paths: ['app/**', '!docs/**']` | only when matching files change (skip CI on docs-only commits) |

Filters combine: `branches:` + `paths:` both must match. `workflow_dispatch` inputs can pass parameters:

```yaml
on:
  workflow_dispatch:
    inputs:
      env:
        description: Target environment
        required: true
        default: staging
```

---

## 4. Secrets

- Store in **Settings → Secrets and variables → Actions** (repo-level) or under an **Environment** (env-level, overrides repo on conflict).
- Referenced only as `${{ secrets.NAME }}`. GitHub never prints the value — it masks it in logs (any log line containing the secret's full value gets replaced with `***`).
- Secrets are **not available in `if:` conditions** and **not passed to fork PRs** (security). `pull_request` from a fork = zero secrets. Use `pull_request_target` only if you understand the checkout-attack risk.
- Do NOT put secrets in `env:` at workflow level for a `pull_request` trigger that forks can hit — same exposure problem.
- Rotate any secret that ever appears in a log, however briefly.

For this project: `SERVER_HOST`, `SERVER_USER`, `SSH_PRIVATE_KEY` belong in a `production` environment; `GITHUB_TOKEN` is auto-provided and needs no setup.

---

## 5. Environments & protection rules

Environment = named target (e.g. `staging`, `production`) created under **Settings → Environments**. Each holds:

- **Environment secrets** — visible only to jobs with `environment: <name>`. Not visible to jobs without it.
- **Protection rules**:
  - **Required reviewers** — humans must approve before the job runs (deploy gate).
  - **Wait timer** — mandatory delay (e.g. 5 min cooldown before prod deploy).
  - **Deployment branches** — only specified branches may deploy to this environment.
- **Deployment history** — timeline of every deploy with commit + actor.

```yaml
deploy:
  runs-on: ubuntu-latest
  environment:
    name: production
    url: https://your-app.example.com    # shown on the deployment card
```

Protection rules apply to the job, and the job waits (pending state) until reviewers approve. This is the CD gate: tests can be fully automated, but shipping to prod requires a human click.

---

## 6. Matrix builds

Run the same job N times with different parameter combos — standard for "test every PHP version":

```yaml
strategy:
  fail-fast: false          # true = one failure cancels the rest (default)
  matrix:
    php: ['8.2', '8.3', '8.4']
    db: ['sqlite', 'mysql']
    exclude:                # drop specific combos
      - php: '8.2'
        db: 'mysql'
    include:                # add extra fields to specific combos
      - php: '8.4'
        db: 'mysql'
        coverage: true
```

Each combo gets its own VM. Inside the job, values come from `${{ matrix.php }}`, `${{ matrix.db }}`. Repo's `tests.yml` uses `matrix: php: ['8.4']` today — one version, ready to expand.

---

## 7. Caching

Dependencies re-install on every fresh runner. Cache avoids the repeat download. Two mechanisms:

1. **`actions/cache`** — explicit path cache, keyed by lockfile hash:

```yaml
- name: Cache Composer dependencies
  uses: actions/cache@v4
  with:
    path: ~/.composer/cache/files        # composer's global cache dir
    key: ${{ runner.os }}-composer-${{ hashFiles('composer.lock') }}
    restore-keys: ${{ runner.os }}-composer-    # fallback: newest cache that matches prefix
```

2. **`actions/setup-*`** built-in caching — e.g. `setup-node` with `cache: 'npm'` auto-detects `package-lock.json` and caches `~/.npm`.

Rules of thumb:

- Key on `hashFiles('lockfile')` so a dependency change invalidates the cache; `restore-keys` gives a near-miss fallback so small updates still hit.
- Cache is per-branch + per-package, 10 GB limit per repo, entries expire after 7 days of no use.
- Cache only what's slow to fetch: composer cache, npm cache, `vendor/` (rarely), docker layers (via buildx cache, not `actions/cache`).

This repo caches `~/.composer/cache/files` in `tests.yml` exactly as above.

---

## 8. Concurrency

Prevent overlapping runs of the same workflow on the same branch (e.g. two pushes in a row: old run still deploying while new run starts):

```yaml
concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

`github.ref` = branch/tag → one group per branch. `cancel-in-progress: true` kills the older run. Common variants:

```yaml
group: deploy-${{ github.ref }}          # serialize deploys per branch
group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}
```

---

## 9. GitHub-hosted vs self-hosted runners

| | GitHub-hosted (`ubuntu-latest`) | Self-hosted |
|---|---|---|
| Setup | zero — instant VM per job | install `actions-runner` on your own machine/VM, register token per repo/org |
| Isolation | fresh VM each run, nothing persists | shared machine; stale state between runs is your problem |
| OS | ubuntu/windows/macos presets | anything: your Ubuntu 24.04 box, ARM, GPU |
| Network | public internet | can reach private network (DB, internal registry) — big reason to use it |
| Cost | free 2000 min/mo (public repos: free) | free, but you pay ops + security |
| Resources | fixed (e.g. 4 vCPU/16 GB) | whatever the box has |
| Security | sandboxed | untrusted code runs on your machine — never run untrusted fork PRs on it |

For this project: a self-hosted runner on this `wannacry` box could deploy directly (no SSH hop, no secrets for host/key). Trade-off: you must secure the runner label, restrict to trusted branches (`runs-on: [self-hosted, linux]` + branch protection), and keep the runner up to date.

---

## 10. GitLab CI comparison (brief)

Same ideas, different file:

- File: `.gitlab-ci.yml` at repo root (not `.github/workflows/`). No workflow files per event — one pipeline definition.
- Stages: `stages: [lint, test, build, deploy]` with per-job `stage:` and `needs:` for DAG.
- Runners: GitLab Runner binaries you install; `tags:` select which runner handles a job. No hosted runner in the free tier.
- Triggers: `rules:`/`only:`/`except:` clauses (e.g. `rules: - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'`).
- Variables: `variables:` + `$CI_JOB_TOKEN`; CI/CD variables in project settings, protected/masked variants.
- Caching: `cache:` keyword + `artifacts:` keyword built in.
- Services: `services: [mysql:8.0]` ≈ Actions `services:`.
- Environment: `environment: production` + `when: manual` for deploy gates.

Mental model: GitHub Actions = more files, event-driven, marketplace; GitLab CI = one file, stage-driven, self-managed runners.

---

## 11. Hands-on exercises

### Exercise 1 — Minimal workflow (scratch dir)

Create and validate a workflow that runs a one-liner on every push. Real files, in a scratch folder:

```bash
mkdir -p ~/scratch/ci-demo/.github/workflows
```

```yaml
# ~/scratch/ci-demo/.github/workflows/hello.yml
name: Hello CI
on: [push, workflow_dispatch]
jobs:
  hello:
    runs-on: ubuntu-latest
    steps:
      - run: echo "Hello from ${{ github.actor }} on ${{ github.ref }}"
```

Validate the YAML parses and the expression syntax is right (catches most typos before you push):

```bash
cd ~/scratch/ci-demo
git init -b main
git add . && git commit -m "add hello workflow"
git remote add origin https://github.com/<you>/ci-demo.git   # then push
# Result: Actions tab shows "Hello CI" run → echo step → green
```

To test locally without a repo: install `actionlint` (`go install github.com/rhysd/actionlint/cmd/actionlint@latest` or `brew install actionlint`) and run `actionlint .github/workflows/hello.yml` — lints workflow syntax, expressions, and common mistakes.

### Exercise 2 — Extend the real repo's ci.yml

In `~/project/magang-rbtv`:

1. Add a `build-assets` job (npm ci + `npm run build`) to `ci.yml`.
2. Change the `tests` job to a matrix over PHP `['8.2', '8.3', '8.4']` — the repo's Dockerfile and tests already cover 8.2+ (composer.json: `"php": "^8.2"`).
3. Push to the `server` branch, watch the Actions tab, confirm all matrix legs pass.

### Exercise 3 — Deploy job with an environment gate

1. In the GitHub repo: Settings → Environments → create `staging` with **required reviewer** = yourself.
2. Add a `deploy` job to `ci.yml`: `needs: tests`, `environment: staging`, SSH to this box via `appleboy/ssh-action@v1`, run `git pull --ff-only && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`.
3. Add `SERVER_HOST`, `SERVER_USER`, `SSH_PRIVATE_KEY` as staging environment secrets (values: this box's address, `wannacry`, and a deploy key from `~/.ssh`).
4. Push; watch the deploy job sit in **pending** until you approve — that's the protection rule working.

---

## 12. Pitfalls

**YAML gotchas**

- `on:` is parsed as boolean `true` in old YAML 1.1 parsers — GitHub handles it, but quote it (`"on":`) if a linter complains. Always leave a blank line after `on:` or the next key swallows it.
- Tabs are invalid — spaces only.
- `${{ ... }}` expressions: no quotes inside expressions; `${{ secrets.X }}` in a `run:` line must be passed via `env:` or the shell may mangle it (and it's safer — avoids log leaks).
- A bare `run: echo "a: b"` is fine, but a value starting with `{`, `[`, `*`, `&` needs quotes — YAML treats them as flow structures.
- `uses:` actions must be pinned: `@v4` (major tag) or better `@<full-sha>` for supply-chain hygiene. Never `@main` on a third-party action.
- Boolean trap: `continue-on-error: true` is a string `"true"` in some parsers — unquoted is fine here, but be consistent.
- Multiline scripts: use `run: |` block scalar; first line of indented block must be more indented than `run:`.

**Secret masking**

- Masking only replaces the **exact full value**. A secret with a trailing newline, or a base64/url-encoded variant of it, leaks.
- Secrets are masked per-value in logs, but the value still exists in the runner's env — a malicious step can exfiltrate it. Trust the workflow, not the event.
- Fork PRs get no secrets by default; `pull_request_target` runs with base-branch secrets and **checks out the fork's code** — classic supply-chain attack vector. Never `pull_request_target` + run untrusted code with secrets.

**Runner limits**

- Public repos: free, unlimited minutes (Linux). Private: 2000 min/month free (Linux), then billed per minute; macOS/Windows cost ~10x more.
- Job timeout default 6 h, max 35 h (hosted). Step timeout: `timeout-minutes: 5` per step.
- 256 MB log limit per job; 10 GB cache/repo; 90-day artifact retention (configurable, `actions/upload-artifact` `retention-days:`).
- Concurrency: max 20 concurrent jobs per repo (free tier), 1000 API calls/hour per repo.
- Runner is **ephemeral**: `vendor/`, `node_modules/`, DB state all gone after the job — that's why cache + services exist.
- `ubuntu-latest` moves: it's currently 24.04; pin to `ubuntu-24.04` if a change would break your build.

**Workflow-specific traps**

- `needs:` creates an implicit order; missing it = parallel jobs racing (e.g. deploy finishing before tests).
- Secrets referenced in `if:` conditions are never evaluated — condition silently false/true on missing value.
- `hashFiles()` on a missing file errors the job — guard with `|| ''`.
- Artifacts from a failed job: `if: always()` needed on the upload step if you want logs from failures.

---

## 13. Further reading

- GitHub Actions docs — https://docs.github.com/en/actions (workflow syntax reference is the authoritative cheat sheet)
- `actionlint` — https://github.com/rhysd/actionlint (local workflow linter; run it in this repo's CI)
- `actions/checkout` — https://github.com/actions/checkout
- `shivammathur/setup-php` — https://github.com/shivammathur/setup-php (PHP matrix + extensions + coverage)
- `docker/build-push-action` + `docker/login-action` + `docker/setup-buildx-action` — https://github.com/docker (GHCR build+push pattern)
- `appleboy/ssh-action` — https://github.com/appleboy/ssh-action (SSH deploy pattern)
- GitHub-hosted runner specs & limits — https://docs.github.com/en/actions/reference/runners-and-usage-limits
- GitLab CI YAML reference — https://docs.gitlab.com/ci/yaml/
- "GitHub Actions in Action" (book) — https://www.manning.com/books/github-actions-in-action

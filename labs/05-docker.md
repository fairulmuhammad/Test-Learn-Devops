# Lab 05: Docker — build, run, multi-stage, volumes

Hands-on extracted from `modules/docker.md`. Everything runs in `~/scratch/`. Every container, image, volume and network this lab creates is removed at the end of its exercise.

> [WARNING] `magang-db` (mysql:8.0) is a **real** running container on this box. Never stop/rm/restart it. Never run `docker compose down -v` except on the scratch project this lab creates (`~/scratch/compose-lab`) — on real projects (`magang-rbtv`, `server_homeserver`) it destroys data irreversibly.

## Setup

Prereqs:
- Docker Engine + Compose v2: `docker --version` (≥ 24), `docker compose version` (v2).
- Docker access without sudo: `id -nG | grep docker` — if no output, add yourself to the docker group: `sudo usermod -aG docker $USER`, then log out/in (or `newgrp docker`). Alternative: prefix every `docker` command with `sudo`.
- Scratch dir: `mkdir -p ~/scratch && cd ~/scratch`
- Record the baseline:

```console
docker ps                # only magang-db should be running
docker images | wc -l    # count pre-existing images
docker volume ls
```

After each exercise, `docker ps -a` / `docker images` / `docker volume ls` must be back to baseline (minus nothing new).

## Exercise 1: build, run, kill

**Goal:** turn a 5-line Dockerfile into an image, run it as a container, read its stdout logs, then remove both.

**Steps:**

1. Project dir:

```console
mkdir -p ~/scratch/pingpong && cd ~/scratch/pingpong
```

2. Write the Dockerfile. Quoted `'EOF'` keeps `$(date)` literal for the container:

```console
cat > Dockerfile <<'EOF'
FROM alpine:3.20
RUN apk add --no-cache curl
CMD ["sh", "-c", "while true; do echo \"$(date) pong\"; sleep 2; done"]
EOF
```

3. Build: `docker build -t pingpong .`
4. Run detached: `docker run -d --name pingpong pingpong` — if you get `name already in use`, clear the old one first: `docker rm -f pingpong`
5. Follow the logs (Ctrl-C stops following, not the container): `docker logs -f pingpong`
6. Stop and remove the container: `docker stop pingpong && docker rm pingpong`
7. Remove the image: `docker rmi pingpong`

**Expected output:**
- Step 3: `Successfully tagged pingpong:latest` (pulls `alpine:3.20`, ~8 MB — the image-vs-container size lesson from the module).
- Step 5: a `... pong` line every 2s.
- Step 6: stop takes a few seconds — SIGTERM, then SIGKILL after the grace period.

**Verify:**

```console
docker ps -a | grep pingpong    # no output
docker images | grep pingpong   # no output
```

- [x] Exercise 1 done

## Exercise 2: multi-stage size check

**Goal:** build the same toolchain two ways — single-stage (fat image keeps the build junk) vs multi-stage (runtime image drops it) — and compare sizes and layers.

**Steps:**

1. Project dir:

```console
mkdir -p ~/scratch/multistage && cd ~/scratch/multistage
```

2. Write `Dockerfile.fat` — single stage, toolchain kept in the image:

```console
cat > Dockerfile.fat <<'EOF'
FROM node:22-alpine AS build
RUN apk add --no-cache build-base python3 \
 && npm install -g typescript
EOF
```

3. Write `Dockerfile` — multi-stage: stage 1 builds the toolchain, stage 2 copies nothing and keeps only the runtime base:

```console
cat > Dockerfile <<'EOF'
FROM node:22-alpine AS build
RUN apk add --no-cache build-base python3 \
 && npm install -g typescript

FROM node:22-alpine
CMD ["node", "-e", "console.log('slim ok')"]
EOF
```

4. Build both:

```console
docker build -t fat -f Dockerfile.fat .
docker build -t slim -f Dockerfile .
```

5. Compare sizes: `docker images | grep -E 'fat|slim'`
6. Compare layers: `docker history slim | head -5` and `docker history fat | head -5`
7. Cleanup (leave `node:22-alpine` — it is the shared base; remove it too only if it was not in your baseline):

```console
docker rmi fat slim
```

**Expected output:**
- Step 5: `fat` is hundreds of MB (build-base + python3 + typescript layers); `slim` is only node:22-alpine — clearly smaller. This is exactly the multi-stage payoff from `modules/docker.md` section 2.
- Step 6: `slim`'s top layers are just the base + `CMD` — the stage-1 toolchain layers are gone; `fat` shows the big `apk add` / `npm install` layers.

**Verify:**

```console
docker images | grep -E 'fat|slim'    # after cleanup: no output
```

- [x] Exercise 2 done

## Exercise 3: compose + volume persistence

**Goal:** prove named volumes survive `docker compose down`, then clean the whole scratch project including the volume — in a sandbox, where it is safe.

**Steps:**

1. Project dir:

```console
mkdir -p ~/scratch/compose-lab && cd ~/scratch/compose-lab
```

2. Write `compose.yaml`. No `version:` key (obsolete in Compose v2), no `ports:` (host port 3306 already belongs to `magang-db`). Project name = dir name `compose-lab`, so the volume is `compose-lab_db_data` — cannot collide with real projects:

```console
cat > compose.yaml <<'EOF'
services:
  db:
    image: mysql:8.0
    volumes:
      - db_data:/var/lib/mysql
    environment:
      MYSQL_ROOT_PASSWORD: labpass123
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "127.0.0.1"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: always

volumes:
  db_data:
EOF
```

3. Start: `docker compose up -d`
4. Wait for health (mysql first init takes ~30–60s): `docker compose ps`
5. Write a marker into the volume:

```console
docker compose exec db sh -c 'echo hello > /var/lib/mysql/test.txt'
```

6. Tear down containers + network (volume survives): `docker compose down`
7. Bring it back up: `docker compose up -d` — wait for healthy again.
8. Read the marker back:

```console
docker compose exec db sh -c 'cat /var/lib/mysql/test.txt'
```

9. [CAUTION — scratch project only] Full cleanup including the volume:

```console
docker compose down -v
```

`down -v` deletes containers, network **and the named volume** — that is the point of the exercise, and it is safe here because this is `~/scratch/compose-lab`. Never run `down -v` on real projects; for them `down` alone is the safe teardown (volumes survive).

**Expected output:**
- Step 4: `STATUS` shows `Up ... (healthy)`.
- Step 6: `Container compose-lab-db-1  Removed` + `Network compose-lab_default  Removed` — and the volume is *not* listed as removed.
- Step 8: `hello` — the file survived `down` + `up`, proving data lives in the volume, not the container.

**Verify:**

```console
docker ps -a | grep compose-lab     # no output
docker volume ls | grep compose-lab # no output — down -v did its job
docker ps                           # back to baseline: only magang-db
```

- [x] Exercise 3 done

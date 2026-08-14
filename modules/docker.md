# Docker

DevOps module. Docker = container platform. Package app + deps into image, run image as isolated container. Grounded in live state of this server (`wannacry` box, Ubuntu 24.04, Docker Engine + Compose v2).

Live inventory at time of writing:

```console
$ docker ps
NAMES       IMAGE       STATUS                 PORTS
magang-db   mysql:8.0   Up 3 hours (healthy)   0.0.0.0:3306->3306/tcp

$ docker images            # (abridged)
magang-rbtv-app-dev      latest   1.61GB
netdata/netdata          latest   770MB
nextcloud                apache   1.44GB
redis                    7-alpine 41.4MB
mysql                    8.0      783MB
vaultwarden/server       alpine   154MB
alpine                   latest   8.44MB

$ docker volume ls        # (abridged)
magang-rbtv_db_data        # named volumes from compose
magang_rbtv_redis_data
magang_db_data
1e93d14cf680bc43ec...      # anonymous volumes — leftover cruft, prune candidates

$ docker network ls
bridge                      bridge    local   # default
host                        host      local   # host networking
none                        null      local
magang-rbtv_default         bridge    local   # created by docker compose
magang-rbtv_magang-octane-network bridge local
server_homeserver           bridge    local
```

Note the pattern: compose project `magang-rbtv` created its own bridge networks and named volumes. Anonymous hash-named volumes = orphaned data from containers that no longer exist.

---

## 1. Core concepts

| Concept | What it is | Analogy |
|---|---|---|
| **Image** | Immutable template: OS layer + runtime + app code + config. Built from Dockerfile. Read-only. | Class / ISO file |
| **Container** | Running instance of an image. Has own filesystem (writable layer), network namespace, process tree. Ephemeral — recreate freely. | Object / VM instance |
| **Dockerfile** | Recipe that builds an image, one instruction per layer. | Build script |
| **Registry** | Image storage/distribution. Docker Hub default. | App store / Git remote |
| **Volume / bind mount** | Persistent data that outlives container. | External hard drive |
| **Compose** | Declare multi-container app (services, networks, volumes) in YAML, manage with one command. | Terraform-lite for containers |

Lifecycle: `docker build` (Dockerfile → image) → `docker push` (image → registry) → `docker pull` (registry → host) → `docker run` (image → container).

**Images are immutable.** Never "patch" a running container — change the Dockerfile, rebuild, recreate. Container state that matters must live in a volume.

### Image vs container — real numbers from this box

`alpine:latest` is 8.44MB, `mysql:8.0` is 783MB, the local `magang-rbtv-app` images are 1.55GB each — because they bundle a PHP app + extensions + Composer deps. Multiple containers can share one image (copy-on-write: only the writable layer is per-container).

## 2. Dockerfile — annotated example (multi-stage)

Why multi-stage: first stage builds with full toolchain (huge), second stage copies only the compiled artifact into a slim runtime image. Final image small, no build junk, no secrets from build context.

```dockerfile
# ---- Stage 1: build ----
FROM node:22-alpine AS build
WORKDIR /app

# Copy manifests first -> layer cache. Deps reinstall only when package.json changes.
COPY package.json package-lock.json ./
RUN npm ci

# Copy source AFTER deps -> source edits reuse cached npm ci layer.
COPY . .
RUN npm run build

# ---- Stage 2: runtime ----
FROM node:22-alpine
ENV NODE_ENV=production
WORKDIR /app

# Copy only compiled output + prod deps from stage 1. Never COPY . .
COPY --from=build /app/dist ./dist
COPY --from=build /app/node_modules ./node_modules

# Run as non-root. Node alpine has user 'node' built in.
USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD wget -qO- http://127.0.0.1:3000/healthz || exit 1

CMD ["node", "dist/server.js"]
```

### Dockerfile best practices

| Rule | Why |
|---|---|
| `FROM` specific tag, pin digest for prod | `latest` changes under you — unreproducible builds |
| `.dockerignore` (node_modules, .git, .env, dist) | Shrinks build context, keeps secrets out of image |
| Combine `RUN` steps with `&&` | Fewer layers, smaller image |
| Install deps before copying source | Leverages layer cache |
| Multi-stage build | Final image = runtime only, not toolchain |
| `USER` non-root | Container root = host root on old kernels; least privilege |
| One process per container | `CMD` runs one thing; supervisor belongs in orchestrator |
| No secrets in `ENV`/`COPY` — use secrets/build args | `docker history` exposes every layer |
| `apt-get clean` / remove caches in same RUN | Kills dead weight in image |
| `EXPOSE` is documentation only | Does not publish ports |

## 3. Compose file — annotated example

Compose v2 (`docker compose`, no hyphen) is a plugin, YAML `version:` key is obsolete. Pattern below mirrors how `magang-rbtv` / `magang-db` run on this server: app + db + redis, named volume for DB, custom network, healthcheck, restart policy.

```yaml
name: myapp            # project name -> prefixes networks/volumes (like magang-rbtv_)

services:
  app:
    build: .           # or: image: myapp:1.0
    ports:
      - "8080:3000"    # host:container. Omit if nothing should be public.
    environment:
      - DB_HOST=db     # service name = DNS name on the compose network
    depends_on:
      db:
        condition: service_healthy   # wait for real readiness, not just "started"
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: "0.5"

  db:
    image: mysql:8.0
    volumes:
      - db_data:/var/lib/mysql      # named volume -> survives rm/up -d
    environment:
      MYSQL_ROOT_PASSWORD: "${MYSQL_ROOT_PASSWORD:?set me in .env}"  # fail fast if unset
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "127.0.0.1"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: always    # matches this box's magang-db: RestartPolicy always

  redis:
    image: redis:7-alpine
    restart: unless-stopped

volumes:
  db_data:             # declare named volumes here; anonymous ones are garbage

networks:
  default:             # compose creates its own bridge; no config needed
```

Commands:

```console
docker compose up -d          # build + start everything
docker compose ps             # status incl. health
docker compose logs -f app    # follow app logs
docker compose exec app sh    # shell into running container
docker compose down           # stop + remove containers + network (volumes survive)
docker compose down -v        # ALSO delete named volumes — destroys data, careful
docker compose config         # validate + print resolved config
docker compose build && docker compose up -d   # after Dockerfile change
```

## 4. Networks and volumes

### Networks

| Driver | Scope | Use case | Notes |
|---|---|---|---|
| `bridge` | single host | Default. Containers on same bridge resolve each other by name; isolated from host net | `docker network create mynet`; compose creates one per project (`magang-rbtv_default` on this box) |
| `host` | single host | Container shares host network stack — no NAT, max perf | No port mapping, no isolation. Bad default. |
| `overlay` | multi-host (Swarm) | Service discovery across nodes in a swarm | Requires swarm mode; not needed for single-server setups |
| `none` | — | Network-less container | Loopback only |

Rules of thumb: same-app containers → shared bridge (compose default). Container needs to reach host service → use `host.docker.internal` (Docker Desktop) or host gateway IP. Cross-host → overlay or reverse proxy, not bridge.

### Volumes vs bind mounts

| | Named volume | Bind mount |
|---|---|---|
| Managed by | Docker (`/var/lib/docker/volumes/`) | You (`/home/wannacry/...`) |
| Path | `myvol:/data` | `/host/path:/data` |
| Backup | `docker run --rm -v myvol:/data alpine tar czf - /data` | plain `rsync`/`tar` of the dir |
| Permissions | Docker initializes perms from image | **Host perms apply** — #1 source of "permission denied" (see Pitfalls) |
| Portability | Easy (`docker compose down && up` keeps data) | Depends on host path existing |
| Use for | DB data (`magang_db_data`), redis data | Config files, code you edit on host, logs |

Named volumes survive `docker compose down`. Bind mounts are the right tool when you want to edit files from the host (e.g. dev code, nginx configs).

## 5. Ops cheat-sheet

```console
# inspect
docker ps -a                          # all containers incl. stopped
docker images                         # local images
docker inspect <name>                 # full JSON: health, restart policy, limits, mounts
docker stats                          # live CPU/mem per container
docker logs -f --tail 100 <name>      # follow logs (container must log to stdout/stderr)
docker top <name>                     # processes inside container

# run / exec
docker run -d --name web -p 8080:3000 --restart unless-stopped --memory 512m --cpus 0.5 myapp:1.0
docker exec -it <name> sh             # shell in; use sh not bash (alpine has no bash)
docker cp <name>:/path/file ./file    # copy out

# build / clean
docker build -t myapp:1.0 .
docker image prune                    # dangling images
docker system df                      # disk usage by images/containers/volumes
docker system prune -a --volumes      # EVERYTHING unused: images, containers, networks, VOLUMES. Data loss.
docker volume prune                   # orphaned anonymous volumes (this box has ~20)
docker logs --since 24h <name>        # time-windowed logs

# restart policy (docker run)
--restart no|on-failure[:max]|always|unless-stopped
```

`docker logs` works only if the app writes to stdout/stderr (12-factor rule). File-based logs inside the container are invisible to `docker logs` — use a logging driver or volume.

## 6. Hands-on exercises

**Exercise 1 — build, run, kill (10 min).** Write this Dockerfile:

```dockerfile
FROM alpine:3.20
RUN apk add --no-cache curl
CMD ["sh", "-c", "while true; do echo \"$(date) pong\"; sleep 2; done"]
```

```console
docker build -t pingpong .
docker run -d --name pingpong pingpong
docker logs -f pingpong            # Ctrl-C to stop following
docker stop pingpong && docker rm pingpong
```

**Exercise 2 — multi-stage size check (15 min).** Build the Stage-1-only image from section 2 (`FROM node:22-alpine AS build` with `RUN npm ci`) and compare:

```console
docker build -t fat -f Dockerfile.fat .    # full build stage
docker build -t slim -f Dockerfile .       # multi-stage from section 2
docker images | grep -E 'fat|slim'         # observe size difference
docker history slim | head -5              # see layers, verify no node_modules junk
```

**Exercise 3 — compose + volume persistence (20 min).** Create `compose.yaml` with the section 3 file, plus a `data` service writing to `db_data`:

```console
docker compose up -d
docker compose exec db sh -c 'echo hello > /var/lib/mysql/test.txt'   # write into volume
docker compose down                      # containers gone, volume survives
docker compose up -d
docker compose exec db sh -c 'cat /var/lib/mysql/test.txt'            # still there
docker compose down -v                   # NOW the data dies — note the warning
```

Verify health with `docker compose ps` and `docker inspect <name> --format '{{.State.Health.Status}}'`.

## 7. Pitfalls

- **Bind mount permission denied** — host dir owned by UID 1000 (`wannacry`), container process runs as root or different UID; MySQL refuses to start with "Permission denied" on `/var/lib/mysql`. Fix: `chown -R 999:999 ./data` (mysql UID), or run container `--user $(id -u):$(id -g)`, or use a named volume (Docker sets perms from image). Check UID with `docker exec <name> id`.
- **`--restart` policies** — `no` (default) = container dies on host reboot or crash. `always` restarts even after manual `docker stop` (until you `docker rm`). `unless-stopped` restarts on crash/reboot but not after manual stop — best default for long-running services. `on-failure:5` caps retries. This box's `magang-db` uses `always`.
- **Port conflicts** — `0.0.0.0:3306->3306` already bound → "port is already allocated". Change host port (`-p 3307:3306`).
- **Dangling/anonymous volumes accumulate** — this box has ~20 hash-named volumes from deleted containers. `docker volume prune` to reclaim; never `prune -a` blindly on a prod host.
- **`latest` tags drift** — image pulled today ≠ image pulled in 6 months. Pin tags/digests for prod.
- **Compose `version:` key** — obsolete in Compose v2; specifying it prints a warning. Omit it.
- **Secrets in images** — `ENV MYSQL_PASSWORD=...` lands in `docker history` and gets committed to the layer. Use `.env` + `${VAR}` interpolation, or Docker secrets.
- **Container not healthy but "Up"** — no healthcheck = orchestrator can't tell. Add `HEALTHCHECK` in Dockerfile or `healthcheck:` in compose; use `depends_on: condition: service_healthy` instead of bare `depends_on` (which only waits for process start).
- **`docker compose down -v` / `docker volume rm`** — irreversible. Backup first.
- **Logs nowhere** — app writes to `/var/log/app.log` inside container instead of stdout → `docker logs` empty. Log to stdout, or mount a log volume.
- **`docker exec` as root on host-rooted mounts** — container root can write host bind-mounted files with host-root ownership. Least privilege: `USER` in Dockerfile, read-only mounts (`:ro`).

## 8. Further reading

- Docker docs — [Dockerfile reference](https://docs.docker.com/reference/dockerfile/), [docker compose](https://docs.docker.com/compose/), [storage](https://docs.docker.com/storage/), [networking](https://docs.docker.com/network/)
- [Best practices for writing Dockerfiles](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)
- [Multi-stage builds](https://docs.docker.com/build/building/multi-stage/)
- [Dockerfile linting: hadolint](https://github.com/hadolint/hadolint)
- 12-factor app — logs as event streams: <https://12factor.net/logs>

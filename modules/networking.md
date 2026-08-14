# Networking

> Target: Ubuntu 24.04 server, user `wannacry`, behind a home router (LAN `192.168.0.0/24`). Everything here is runnable as-is on that box.
> Prerequisite: SSH access. `ss`/`ip`/`curl` need no root; `ufw` needs `sudo`. All commands below were run against the live server — the tables show real output.

## Overview

DevOps work is 50% moving bytes between machines: containers, APIs, load balancers, SSH, backups. This module covers the mental model you need — IP addressing, ports, DNS, firewalls, proxies, tunnels — and the exact commands to inspect your own box. The box you are learning on is a good specimen: it has a home LAN IP, a Tailscale overlay IP, Docker bridge networks, and services listening on several ports.

## Key Concepts

### 1. IP Addressing and CIDR

An IP address identifies a machine on a network. IPv4 is 32 bits, written as four octets (`192.168.0.17`). IPv6 is 128 bits, written in hex groups (`fd7a:115c:a1e0::4001:fb38`) — you mostly meet it via Docker and Tailscale.

**CIDR** (`a.b.c.d/n`) says: first `n` bits are the network, the rest are the host. This machine's LAN interface:

```
ip addr show wlp3s0
# inet 192.168.0.17/24 ...
```

- `/24` = first 24 bits network → network `192.168.0.0`, hosts `192.168.0.1`–`192.168.0.254`, broadcast `192.168.0.255`.
- `/16` = 65,534 usable hosts (Docker uses these for bridge networks).
- `/32` = a single host — Tailscale assigns exactly this (`100.89.251.20/32`).

Common private ranges (RFC 1918, not routable on the public internet): `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`. Docker bridges on this box live in `172.17.0.0/16`–`172.22.0.0/16`; your home LAN is `192.168.0.0/24`; `127.0.0.0/8` is loopback (the machine talking to itself).

Real interfaces on this server:

| Interface | Address | Role |
|---|---|---|
| `lo` | `127.0.0.1/8` | Loopback — always there, talks to self |
| `wlp3s0` | `192.168.0.17/24` | Wi-Fi, home LAN, DHCP-assigned |
| `tailscale0` | `100.89.251.20/32` | Tailscale overlay network |
| `docker0`, `br-*` | `172.17.0.1/16` … `172.22.0.1/16` | Docker bridge networks |

The routing table (`ip route`) decides which interface handles which destination. Default route goes via the home router:

```
default via 192.168.0.1 dev wlp3s0 proto dhcp
192.168.0.0/24 dev wlp3s0 proto kernel scope link src 192.168.0.17
172.19.0.0/16 dev br-863e028d4a2b proto kernel scope link src 172.19.0.1
```

### 2. Ports and Sockets

A port is a 16-bit number (0–65535) that multiplexes connections onto one IP. A **socket** is IP + port + protocol (TCP/UDP). A service **listens** on a socket; a client **connects** to it.

- Well-known: `22` SSH, `53` DNS, `80` HTTP, `443` HTTPS, `3306` MySQL/MariaDB.
- `ss` (successor to `netstat`) shows sockets. `-t` TCP, `-u` UDP, `-l` listening only, `-n` numeric (no DNS lookups), `-p` show process.

Real output — everything listening on this server right now:

```
$ ss -tlnp
LISTEN  0.0.0.0:22        sshd                  <- SSH, all interfaces
LISTEN  0.0.0.0:3306      (docker)              <- MySQL container, all interfaces
LISTEN  0.0.0.0:20128     next-server (9router) <- 9router admin UI
LISTEN  *:80              (nginx/caddy)         <- HTTP reverse proxy
LISTEN  *:9090            (netdata)             <- netdata dashboard
LISTEN  127.0.0.53:53     systemd-resolved      <- local DNS stub, loopback only
LISTEN  100.89.251.20:443 (tailscale funnel)    <- HTTPS, Tailscale IP only
LISTEN  127.0.0.1:20241/20242  cloudflared      <- Cloudflare tunnel, loopback only
```

Read the bind address carefully — it is a security statement:

| Bind | Meaning |
|---|---|
| `0.0.0.0:port` or `*:port` | All interfaces — reachable from LAN **and** internet (if the router forwards). |
| `127.0.0.1:port` | Loopback only — only local processes can connect. Safe default for admin tools. |
| `100.89.251.20:port` | Only via the Tailscale network. |

Port 3306 binding to `0.0.0.0` while the firewall is off means anyone on your LAN can try MySQL. Loopback-bound services (`cloudflared`) are what a reverse proxy connects to on the same machine.

### 3. DNS and /etc/hosts

DNS maps names to IPs. Resolution order on Ubuntu 24.04 (systemd): `/etc/hosts` first, then the DNS servers configured per-interface (via `resolvectl`).

- `/etc/hosts` — static local overrides, checked before DNS. This box has `127.0.0.1 localhost` and `127.0.1.1 wannacry-server`. Useful for pinning a name to an IP during testing or blocking a host by pointing it at `127.0.0.1`.
- `resolvectl status` shows which DNS server each interface uses. On this box: Wi-Fi uses the home router `192.168.0.1`; `tailscale0` uses MagicDNS `100.100.100.100` (Tailscale's built-in resolver, which also resolves tailnet names like `wannacry-server.tail2ae7e6.ts.net`).
- `127.0.0.53` in `ss` output is systemd-resolved's local stub — apps send DNS queries there, it forwards upstream. That is why you see port 53 on loopback even with no DNS server installed.
- Diagnostics: `dig example.com`, `dig @1.1.1.1 example.com` (query a specific server), `getent hosts example.com` (honors /etc/hosts + DNS), `nslookup`, `resolvectl query name`.

### 4. Firewall: ufw (and what iptables is underneath)

`ufw` ("uncomplicated firewall") is the friendly wrapper over `iptables`/`nftables`, which is the kernel's packet-filtering engine. Default policy: **deny incoming, allow outgoing** — then you open specific ports.

> Note: `ufw status` needs root. On this box it must be run with `sudo` (no passwordless sudo is configured for this session), so the exact status is left as your first exercise.

```
sudo ufw status verbose        # show rules + default policy
sudo ufw allow 22/tcp          # open SSH
sudo ufw allow 443/tcp         # open HTTPS
sudo ufw allow from 192.168.0.0/24 to any port 3306   # MySQL only from LAN
sudo ufw deny 3306             # close it again
sudo ufw enable                # turn on (careful over SSH: allow 22 FIRST)
sudo ufw disable
sudo ufw delete 3              # delete rule number 3 (see: ufw status numbered)
```

SSH safety rule: always `sudo ufw allow 22/tcp` before `sudo ufw enable`, or you lock yourself out.

Concepts underneath (`iptables`): packets traverse chains — `INPUT` (to this host), `OUTPUT` (from this host), `FORWARD` (through this host, e.g. router/NAT). Each chain is a list of rules with a verdict: `ACCEPT`, `DROP`, `REJECT`, `LOG`. Docker bypasses ufw by writing its own `FORWARD` rules and publishing ports via NAT — a classic surprise: `ufw deny 3306` may not stop a published Docker container port unless you also restrict the publish (`-p 127.0.0.1:3306:3306`).

### 5. NAT and Port Forwarding

NAT (Network Address Translation) is how your one home-router public IP serves many devices. Outbound: your `192.168.0.17` becomes the router's public IP when leaving the LAN. Inbound: the router rewrites "public IP:port" to "LAN IP:port" — that rewrite rule is **port forwarding**, configured on the router admin page (usually `192.168.0.1`), not on the server.

```
Internet ──> router 203.0.113.7:443 ──(port forward)──> 192.168.0.17:443
```

On the server side, `net.ipv4.ip_forward` enables routing/NAT in the kernel — Docker sets it for its bridge networks. `iptables -t nat -L` shows NAT rules (Docker's `DOCKER` chain lives there).

### 6. Reverse Proxy

A reverse proxy sits in front of your services: clients talk to one entry point (port 80/443), the proxy forwards to the right backend by hostname or path. Nginx and Caddy are the common ones. Caddy wins on simplicity — it gets HTTPS certificates automatically (see TLS below).

```
                ┌───────────────────────────────────────────┐
                │            Reverse Proxy (:80/:443)       │
                │                                           │
  client ──►    │  app.example.com  ──► 127.0.0.1:3000      │──► app container
 (browser)      │  dash.example.com  ──► 127.0.0.1:9090     │──► netdata
                │  api.example.com   ──► 127.0.0.1:8080     │──► api
                └───────────────────────────────────────────┘
```

Why: one TLS certificate + one public port for many services, backends can stay on loopback, easy to add auth/rate-limiting/logging in one place. Your box already does this: `*:80` is a proxy layer in front of netdata (`:9090`), and 9router runs `cloudflared tunnel --url` which creates an outbound tunnel to Cloudflare — a reverse proxy variant where the public endpoint lives in Cloudflare's network, and the tunnel connection is initiated **from** your box (no open inbound port needed).

Minimal nginx `server` block:

```nginx
server {
    listen 80;
    server_name dash.example.com;
    location / {
        proxy_pass http://127.0.0.1:9090;
        proxy_set_header Host $host;
    }
}
```

Caddy equivalent (2 lines, auto-HTTPS):

```
dash.example.com {
    reverse_proxy 127.0.0.1:9090
}
```

### 7. TLS Basics

TLS (what HTTPS runs on) encrypts traffic and proves the server's identity. Core pieces:

- **Certificate**: binds a public key to a domain name, signed by a Certificate Authority (CA). Browsers trust the CA, so they trust the cert.
- **Private key**: stays on the server, used to decrypt. Never leave the server, never commit to git.
- **Handshake**: client and server negotiate, server presents cert, they exchange keys — after that, symmetric encryption.
- **Let's Encrypt** gives free 90-day certs; `certbot` automates issuance + renewal (`certbot --nginx`).
- Caddy does all of this automatically (ACME built in). Cloudflare tunnels also terminate TLS at Cloudflare's edge — your origin gets a `https://` URL without exposing port 443, and the hop between Cloudflare and your box travels over the tunnel (authenticated + encrypted).

Verify a cert from the client side: `openssl s_client -connect example.com:443 -servername example.com` (look for the certificate block and expiry), or just `curl -vI https://example.com`.

### 8. Overlay Networks: Tailscale and WireGuard

Tailscale and WireGuard solve "my services are behind a home NAT / on different networks" — they build an **overlay network** on top of the internet.

- **WireGuard** is the underlying VPN protocol: kernel-level, fast, peer-to-peer, key-based. Config lives in `/etc/wireguard/*.conf`. Each peer has a public/private keypair; traffic is encrypted end-to-end.
- **Tailscale** is WireGuard plus coordination: it handles key exchange, NAT traversal, and assigns you stable `100.x.y.z/32` addresses (CGNAT range `100.64.0.0/10`, not routable publicly). It punches through home NATs using STUN-like techniques and falls back to relayed (DERP) connections when it can't.

This server's tailnet (`tailscale status`):

```
100.89.251.20   wannacry-server     linux    this machine
100.124.216.29  desktop-p1oiaug     windows  offline
100.74.24.28    macbook-air-dinda   macOS    active; relay "sin"
```

You SSH in from anywhere via `ssh wannacry@100.89.251.20` without port forwarding or exposing SSH to the internet. MagicDNS (`100.100.100.100`) resolves tailnet names. Because it's an encrypted tunnel over ordinary internet paths, you can run services bound to the tailnet IP only (`ss` shows `100.89.251.20:443` — reachable from your devices, invisible to the LAN).

Quick mental map: **LAN** = home Wi-Fi, `192.168.0.x`; **Docker bridges** = containers talking to each other, `172.x`; **Tailscale** = your devices anywhere, `100.x`; **public internet** = everything behind the router's NAT.

## Diagnostics Cheat Sheet

| Goal | Command |
|---|---|
| Show IPs and interfaces | `ip addr` |
| Show routing table | `ip route` |
| Show listening TCP sockets + process | `ss -tlnp` |
| Show all sockets (incl. UDP, established) | `ss -tunap` |
| Who owns port N | `sudo ss -tlnp \| grep :N` |
| Test TCP connectivity | `nc -zv 192.168.0.17 3306` |
| Test an HTTP endpoint | `curl -v http://localhost:9090/` (or `-I` for headers only) |
| DNS lookup | `dig example.com` |
| Query a specific DNS server | `dig @1.1.1.1 example.com` |
| Hosts-file-aware lookup | `getent hosts example.com` |
| Show per-interface DNS | `resolvectl status` |
| Show firewall rules | `sudo ufw status verbose` |
| Show NAT rules | `sudo iptables -t nat -L -n` |
| Check TLS cert | `openssl s_client -connect example.com:443 -servername example.com` |
| ARP table (LAN neighbors) | `ip neigh` |
| Trace route to a host | `traceroute example.com` (or `mtr`) |
| Tailscale peer list | `tailscale status` |

## Hands-On Exercises

### Exercise 1: Inventory your listening ports (no root)

```bash
ss -tlnp
ip addr
ip route
```

Answer: which ports bind to `0.0.0.0` vs `127.0.0.1`? Which would be reachable from your phone on the same Wi-Fi? Which service is only reachable over Tailscale? Verify one service with `curl -v http://localhost:9090/` and one with `curl -v http://localhost:20128/`. Then check the firewall: `sudo ufw status verbose` — what is the default incoming policy, and is it what you want?

### Exercise 2: DNS experiments

```bash
dig example.com
dig @192.168.0.1 example.com      # your router's resolver
resolvectl status                  # which DNS does each interface use?
getent hosts example.com
```

Now add a temporary hosts override and watch it win over DNS:

```bash
echo "127.0.0.1 example.com" | sudo tee -a /etc/hosts
curl -v http://example.com/        # should hit your own box, not the real site
# remove it after testing:
sudo sed -i '/example.com/d' /etc/hosts
```

### Exercise 3: Run a service and expose it (root)

```bash
python3 -m http.server 8000 &      # serve current dir on :8000
curl -s localhost:8000 | head -5   # verify it works locally
ss -tlnp | grep 8000               # confirm the socket
sudo ufw allow 8000/tcp            # open the port in the firewall
curl -s http://192.168.0.17:8000 | head -5   # from your laptop/phone on the LAN
sudo ufw delete allow 8000/tcp     # close it again
kill %1                            # stop the server
```

If the LAN curl fails but localhost works: ufw is blocking, or the router's AP/client isolation is on. Check `sudo ufw status verbose` first. Then think: would anyone outside your house reach it? Only if the router port-forwards `:8000` — it doesn't, so no.

## Pitfalls

- **`0.0.0.0` bind ≠ "localhost".** A service on `0.0.0.0:3306` is reachable from the whole LAN. Bind `127.0.0.1` or the tailnet IP for anything you don't want exposed.
- **ufw and Docker fight.** Docker publishes ports by writing its own iptables `FORWARD` rules, bypassing ufw's INPUT chain. `ufw deny 3306` can leave a Docker-published 3306 open. Fix: publish on loopback (`docker run -p 127.0.0.1:3306:3306`) or manage Docker's `DOCKER-USER` chain.
- **Enabling ufw over SSH without allowing 22 first = lockout.**
- **Port forwarding happens on the router, not the server.** You can't "open a port to the internet" from the box alone; the router must forward, and many ISPs use CGNAT where you have no public IP at all — that's exactly the case Tailscale/Cloudflare tunnels solve.
- **`127.0.0.53` is not a rogue DNS server.** It's systemd-resolved's stub. Don't kill it to "free" port 53.
- **CIDR off-by-one**: `/24` gives 254 usable host addresses, not 256; `/32` is one specific host, not "a range".
- **TLS certs expire.** Let's Encrypt certs last 90 days; if renewal breaks (DNS record removed, service down), HTTPS silently fails for users. Check `certbot renew --dry-run` in cron/CI.
- **Don't commit private keys or `.env` with secrets** — anyone with repo access gets your TLS keys or DB passwords.
- **`ss` without `-p`** shows no process names (and `-p` needs root for other users' processes).
- **Tailscale relay ≠ direct**: "relay sin" in `tailscale status` means traffic is going through a DERP relay — slower than a direct WireGuard path. `tailscale ping <peer>` shows which.

## Further Reading

- `man ss`, `man ip`, `man ufw` — the primary sources on this box
- [Tailscale docs — how it works](https://tailscale.com/kb/1151/what-is-tailscale)
- [WireGuard quick start](https://www.wireguard.com/quickstart/)
- [nginx docs — HTTP proxying](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)
- [Caddy docs — reverse proxy](https://caddyserver.com/docs/quick-starts/reverse-proxy)
- [Let's Encrypt / certbot docs](https://certbot.eff.org/)
- [Cloudflare Tunnel docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
- [iptables tutorial (digitalocean)](https://www.digitalocean.com/community/tutorials/iptables-essentials-common-firewall-rules-and-commands)

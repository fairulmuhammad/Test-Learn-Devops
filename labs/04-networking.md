# Lab 04: Networking

## Setup

- Target: Ubuntu 24.04 server, user `wannacry`, on home LAN `192.168.0.0/24` (this box: `192.168.0.17/24`, Tailscale `100.89.251.20/32`).
- Prereqs: SSH access to the box. `ss`, `ip`, `curl`, `dig`, `getent`, `resolvectl` need **no root**. `ufw`, `/etc/hosts` edits need `sudo` — marked `[ROOT]`.
- SAFETY: this lab makes **no firewall changes that enable ufw**. If you ever run `sudo ufw enable` yourself, you MUST `sudo ufw allow 22/tcp` FIRST or you lock yourself out over SSH.
- Source module: `modules/networking.md`.

## Exercise 1: Inventory your listening ports

**Goal:** map every service listening on the box, classify its bind address, and check the firewall default policy.

**Steps**

1. List all listening TCP sockets with owning process:
   ```bash
   ss -tlnp
   ```
2. Show your IPs and interfaces:
   ```bash
   ip addr
   ```
3. Show the routing table:
   ```bash
   ip route
   ```
4. Hit two HTTP services to confirm they respond:
   ```bash
   curl -v http://localhost:9090/
   curl -v http://localhost:20128/
   ```
5. Check the firewall state and default policy:
   ```bash
   sudo ufw status verbose
   ```

**Expected output:** `ss -tlnp` shows SSH on `0.0.0.0:22`, MySQL on `0.0.0.0:3306`, a proxy on `*:80`, netdata on `*:9090`, systemd-resolved on `127.0.0.53:53`, Tailscale funnel on `100.89.251.20:443`, cloudflared on `127.0.0.1:20241/20242`. `ip addr` shows `lo`, `wlp3s0`, `tailscale0`, `docker0`/`br-*`. `ip route` shows `default via 192.168.0.1 dev wlp3s0`. `ufw status` shows "Status: inactive" and the default incoming policy.

**Verify:** answer these — which ports bind `0.0.0.0` vs `127.0.0.1`? Which would your phone on the same Wi-Fi reach? Which service is only reachable over Tailscale? Is the default incoming policy what you want?

- [x] `ss -tlnp` / `ip addr` / `ip route` / `ufw status verbose` run and bind classes identified

## Exercise 2: DNS experiments

**Goal:** see how name resolution works, which resolver each interface uses, and prove `/etc/hosts` beats DNS.

**Steps**

1. Look up a name with the default resolver:
   ```bash
   dig example.com
   ```
2. Query your router's resolver explicitly:
   ```bash
   dig @192.168.0.1 example.com
   ```
3. Show per-interface DNS servers:
   ```bash
   resolvectl status
   ```
4. Hosts-file-aware lookup:
   ```bash
   getent hosts example.com
   ```
5. Add a temporary override and watch it win:
   ```bash
   echo "127.0.0.1 example.com" | sudo tee -a /etc/hosts
   curl -v http://example.com/
   ```
6. Remove the override when done:
   ```bash
   sudo sed -i '/example.com/d' /etc/hosts
   ```

**Expected output:** `dig` shows `example.com` answering (query time, `ANSWER: 1`). `resolvectl status` shows Wi-Fi using `192.168.0.1`, `tailscale0` using MagicDNS `100.100.100.100`. After step 5, `curl -v http://example.com/` connects to your own box (`127.0.0.1`), not the real site.

**Verify:** after step 6, `getent hosts example.com` returns the real public IP again (override gone).

- [x] DNS queries run, resolver map understood, hosts override added and removed cleanly

## Exercise 3: Run a service and expose it on the LAN

**Goal:** start a throwaway HTTP server, verify it locally, open its port in ufw, reach it from the LAN, then close everything back down.

**Steps**

1. Serve the current directory on port 8000:
   ```bash
   python3 -m http.server 8000 &
   ```
2. Verify it works locally:
   ```bash
   curl -s localhost:8000 | head -5
   ```
3. Confirm the socket exists:
   ```bash
   ss -tlnp | grep 8000
   ```
4. Open the port in the firewall `[ROOT]`:
   ```bash
   sudo ufw allow 8000/tcp
   ```
5. From your laptop/phone on the same LAN, reach the box's LAN IP:
   ```bash
   curl -s http://192.168.0.17:8000 | head -5
   ```
6. Close the port again `[ROOT]`:
   ```bash
   sudo ufw delete allow 8000/tcp
   ```
7. Stop the server:
   ```bash
   kill %1
   ```

**Expected output:** step 2 and 5 both print the directory listing HTML. `ss -tlnp | grep 8000` shows `LISTEN 0.0.0.0:8000`. Step 4 prints `Rule added`.

**Verify:** after step 6, `sudo ufw status` shows no 8000 rule; after step 7, `ss -tlnp | grep 8000` returns nothing.

**Safety:** do NOT run `sudo ufw enable` in this exercise — it is not needed, and enabling without `sudo ufw allow 22/tcp` first locks you out over SSH. If the LAN curl fails while localhost works, check `sudo ufw status verbose`; also note the router only forwards port 8000 if you configured a port-forward rule on the router admin page (`192.168.0.1`) — nothing here does that, so the service is LAN-only.

- [x] http.server started, ufw 8000 rule added then deleted, service stopped, no lingering rules

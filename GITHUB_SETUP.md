# GitHub setup (one-time, needs PAT)

Everything is ready in this repo — CI/CD workflows, app, systemd unit. Only the
push + runner registration need a GitHub token.

## 1. Create repo + push (pick ONE)

### Via web (no CLI):
1. Create empty private repo `Test-Learn-Devops` at https://github.com/new
2. Then:
```bash
cd /home/wannacry/devops-project/Test-Learn-Devops
git remote add origin https://github.com/fairulmuhammad/Test-Learn-Devops.git
git push -u origin main
```

### Via gh CLI (needs `gh auth login` once):
```bash
cd /home/wannacry/devops-project/Test-Learn-Devops
gh repo create Test-Learn-Devops --private --source . --push
```

## 2. Register self-hosted runner (box, behind NAT — no inbound ports needed)

Runner on this box pulls jobs from GitHub (outbound only). CD deploy job
(`runs-on: self-hosted`) runs `docker compose up -d --build` right here.

```bash
mkdir -p ~/actions-runner && cd ~/actions-runner
curl -o actions-runner-linux-x64.tar.gz -L \
  https://github.com/actions/runner/releases/latest/download/actions-runner-linux-x64-2.319.1.tar.gz
tar xzf actions-runner-linux-x64.tar.gz
```

Get the registration token: repo Settings → Actions → Runners → New
self-hosted runner → copy the `./config.sh --url ... --token ...` command.
Run it (accept defaults), then install as a service:

```bash
sudo ./svc.sh install
sudo ./svc.sh start
```

## 3. Verify

- Push to main → CI runs (validate + build + health check) on GitHub's runners
- After CI green → CD job picks up on the box's runner → deploys to :8090
- Manual re-deploy anytime: Actions → CD → Run workflow
- Box-local (no GitHub needed): `sudo systemctl enable --now hello-app`

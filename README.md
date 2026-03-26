# ServiceNow PDI Keep-Alive

Automatically pings your ServiceNow Personal Developer Instance (PDI) at regular intervals to prevent it from being reclaimed due to inactivity.

> ServiceNow reclaims free PDIs after approximately **10 days of inactivity**. This script keeps yours alive by hitting the REST API on a schedule.

---

## How It Works

1. On each run, the script authenticates against the ServiceNow Table API (`/api/now/table/sys_user`) using basic auth.
2. A successful HTTP 200 response counts as instance activity and resets the inactivity timer.
3. If the REST ping fails (e.g. the instance has hibernated), it falls back to a browser-style `login.do` POST to wake it up, then confirms with a second ping.
4. All activity is logged to both the console and `servicenow_keepalive.log`.

---

## Files

```
sn-pdi-keepalive/
├── servicenow_keepalive.py        # The keep-alive script
└── .github/
    └── workflows/
        └── keepalive.yml          # GitHub Actions workflow (runs every 12 hours)
```

---

## Setup

### 1. GitHub Secrets

Go to **Settings → Secrets and variables → Actions** in your repo and add:

| Secret | Description | Example |
|---|---|---|
| `SN_INSTANCE` | Your PDI instance name | `dev12345` |
| `SN_USER` | Username to authenticate with | `admin` |
| `SN_PASSWORD` | Password for that user | `your-password` |

### 2. GitHub Actions Workflow

Create `.github/workflows/keepalive.yml` with the following content:

```yaml
name: ServiceNow PDI Keep-Alive

on:
  schedule:
    - cron: '0 */12 * * *'   # every 12 hours
  workflow_dispatch:           # allows manual trigger

jobs:
  keepalive:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install requests

      - name: Run keep-alive
        env:
          SN_INSTANCE: ${{ secrets.SN_INSTANCE }}
          SN_USER: ${{ secrets.SN_USER }}
          SN_PASSWORD: ${{ secrets.SN_PASSWORD }}
          SN_INTERVAL: '0.001'
        run: python servicenow_keepalive.py --once
```

### 3. Test It

Go to the **Actions** tab → **ServiceNow PDI Keep-Alive** → **Run workflow** to trigger a manual run and confirm you see:

```
✅  Ping successful — instance is alive  (HTTP 200)
✔  Single ping complete — exiting.
```

---

## Running Locally

Install the dependency:

```bash
pip install requests
```

Set environment variables:

```bash
export SN_INSTANCE="dev12345"
export SN_USER="admin"
export SN_PASSWORD="your-password"
```

Run once and exit:

```bash
python servicenow_keepalive.py --once
```

Run in a loop (pings every 12 hours):

```bash
python servicenow_keepalive.py
```

Run in the background:

```bash
nohup python servicenow_keepalive.py &
```

---

## Configuration

The script reads configuration from environment variables with fallback defaults in the `CONFIG` block at the top of the file.

| Environment Variable | Default | Description |
|---|---|---|
| `SN_INSTANCE` | `dev12345` | Your PDI instance name |
| `SN_USER` | `keepalive_user` | Username to authenticate with |
| `SN_PASSWORD` | `YourPassword!` | Password for that user |
| `SN_INTERVAL` | `12` | Hours between pings (loop mode only) |

---

## Usage

```
python servicenow_keepalive.py           # loop forever (local use)
python servicenow_keepalive.py --once    # ping once and exit (GitHub Actions / cron)
```

---

## Notes

- The user account used must have access to the `sys_user` table. The `admin` role works out of the box.
- The 12-hour ping interval gives a large safety margin well within the 10-day reclaim window.
- Logs are written to `servicenow_keepalive.log` in the working directory when run locally.

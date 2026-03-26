#!/usr/bin/env python3
"""
ServiceNow PDI Keep-Alive Script
=================================
Logs into your ServiceNow Personal Developer Instance at regular intervals
to prevent it from being reclaimed due to inactivity (instances are reclaimed
after ~10 days of inactivity on the free tier).

Usage:
    python servicenow_keepalive.py           # loop forever (local use)
    python servicenow_keepalive.py --once    # ping once and exit (GitHub Actions / cron)

Configuration:
    Set the environment variables below, or edit the CONFIG section directly.

Environment variables (recommended):
    SN_INSTANCE   - Your instance name, e.g. "dev12345"
    SN_USER       - Username of the dedicated keep-alive user
    SN_PASSWORD   - Password of that user
    SN_INTERVAL   - Ping interval in hours (default: 12)
"""

import argparse
import os
import sys
import time
import logging
import requests
from datetime import datetime, timezone

# ─────────────────────────── CONFIG ───────────────────────────────────────────
INSTANCE   = os.getenv("SN_INSTANCE",  "dev12345")       # e.g. dev12345
USERNAME   = os.getenv("SN_USER",      "keepalive_user") # dedicated PDI user
PASSWORD   = os.getenv("SN_PASSWORD",  "YourPassword!")  # that user's password
INTERVAL_H = float(os.getenv("SN_INTERVAL", "12"))       # hours between pings
# ──────────────────────────────────────────────────────────────────────────────

BASE_URL   = f"https://{INSTANCE}.service-now.com"
PING_URL   = f"{BASE_URL}/api/now/table/sys_user?sysparm_limit=1&sysparm_fields=user_name"
LOGIN_URL  = f"{BASE_URL}/login.do"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("servicenow_keepalive.log"),
    ],
)
log = logging.getLogger("sn-keepalive")


def ping(session: requests.Session) -> bool:
    """
    Hit the REST Table API with the authenticated session.
    Returns True on success, False on failure.
    """
    try:
        resp = session.get(
            PING_URL,
            auth=(USERNAME, PASSWORD),
            headers={"Accept": "application/json"},
            timeout=30,
        )
        if resp.status_code == 200:
            log.info("✅  Ping successful — instance is alive  (HTTP %s)", resp.status_code)
            return True
        else:
            log.warning("⚠️  Unexpected response: HTTP %s — %s", resp.status_code, resp.text[:200])
            return False
    except requests.exceptions.ConnectionError as exc:
        log.error("❌  Connection error (instance may be hibernating): %s", exc)
        return False
    except requests.exceptions.Timeout:
        log.error("❌  Request timed out after 30 s")
        return False
    except Exception as exc:
        log.error("❌  Unexpected error: %s", exc)
        return False


def wake_instance(session: requests.Session) -> bool:
    """
    If the REST ping fails, attempt a browser-style login to wake a hibernating instance.
    ServiceNow free-tier instances hibernate and need a web request to wake up.
    """
    log.info("🔄  Attempting wake-up login to %s ...", BASE_URL)
    try:
        resp = session.get(BASE_URL, timeout=60)   # initial GET — may be slow on wake
        log.info("    Wake GET returned HTTP %s", resp.status_code)

        wake_resp = session.post(
            LOGIN_URL,
            data={"user_name": USERNAME, "user_password": PASSWORD, "sys_action": "sysverb_login"},
            timeout=60,
        )
        if wake_resp.status_code in (200, 302):
            log.info("✅  Wake-up login succeeded (HTTP %s)", wake_resp.status_code)
            return True
        else:
            log.warning("⚠️  Wake-up login returned HTTP %s", wake_resp.status_code)
            return False
    except Exception as exc:
        log.error("❌  Wake-up failed: %s", exc)
        return False


def run_once(session: requests.Session) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    log.info("━" * 60)
    log.info("🕐  Keep-alive tick at %s", now)
    log.info("    Instance : %s", INSTANCE)
    log.info("    User     : %s", USERNAME)

    success = ping(session)
    if not success:
        log.info("    REST ping failed — trying browser wake-up ...")
        woken = wake_instance(session)
        if woken:
            time.sleep(10)          # give the instance a moment to fully start
            ping(session)           # confirm it's up
        else:
            log.error("    Could not reach instance. Will retry next cycle.")


def main() -> None:
    parser = argparse.ArgumentParser(description="ServiceNow PDI Keep-Alive")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Ping once and exit (use this in GitHub Actions / cron jobs)",
    )
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("  ServiceNow PDI Keep-Alive starting")
    log.info("  Instance : %s", INSTANCE)
    log.info("  User     : %s", USERNAME)
    if args.once:
        log.info("  Mode     : single ping (--once)")
    else:
        interval_s = int(INTERVAL_H * 3600)
        log.info("  Mode     : loop every %.1f hours (%d seconds)", INTERVAL_H, interval_s)
    log.info("=" * 60)

    session = requests.Session()
    session.headers.update({"User-Agent": "SN-PDI-KeepAlive/1.0"})

    if args.once:
        run_once(session)
        log.info("✔  Single ping complete — exiting.")
        sys.exit(0)

    try:
        interval_s = int(INTERVAL_H * 3600)
        while True:
            run_once(session)
            log.info("💤  Sleeping for %.1f hours ...", INTERVAL_H)
            time.sleep(interval_s)
    except KeyboardInterrupt:
        log.info("👋  Stopped by user.")


if __name__ == "__main__":
    main()

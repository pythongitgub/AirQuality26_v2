#!/usr/bin/env python3
"""Send AQ26 weekly completion email."""

from __future__ import annotations

import argparse
import json
import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

import yaml


def load_yaml(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/aq26_weekly_runtime.yml")
    args = parser.parse_args()

    runtime = load_yaml(args.config)
    paths = runtime.get("paths", {})
    logs = Path(paths.get("logs", "outputs/logs"))
    manifest_path = logs / "latest_bundle_manifest.json"
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587") or "587")
    smtp_user = os.getenv("SMTP_USERNAME", "").strip()
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
    mail_from = os.getenv("MAIL_FROM", "").strip() or smtp_user
    mail_to = os.getenv("MAIL_TO", "").strip()

    if not smtp_host or not smtp_user or not smtp_pass or not mail_from or not mail_to:
        raise SystemExit("Missing SMTP/MAIL secrets. Required: SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, MAIL_FROM, MAIL_TO.")

    subject_prefix = runtime.get("email", {}).get("subject_prefix", "AQ26 weekly production")
    msg = EmailMessage()
    msg["From"] = mail_from
    msg["To"] = mail_to
    msg["Subject"] = f"{subject_prefix}: completed"
    msg.set_content(
        "AQ26 weekly operational publishing has completed.\n\n"
        f"Evidence bundle: {manifest.get('bundle', 'not recorded')}\n"
        f"SHA256: {manifest.get('sha256', 'not recorded')}\n"
        f"Bytes: {manifest.get('bytes', 'not recorded')}\n\n"
        "Note: heavy historical science backfill remains in Colab/Drive unless validated outputs are included in this weekly bundle.\n"
    )

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls(context=context)
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)

    print(f"Completion email sent to {mail_to}.")


if __name__ == "__main__":
    main()

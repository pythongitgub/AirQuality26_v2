#!/usr/bin/env python3
from __future__ import annotations

import argparse
import mimetypes
import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path


def latest_run(root: Path) -> Path:
    marker = root / "LATEST_RUN.txt"
    if marker.exists():
        p = Path(marker.read_text(encoding="utf-8").strip())
        if p.exists():
            return p
    runs = sorted([p for p in root.glob("AQ26_WEEKLY_*") if p.is_dir()])
    if not runs:
        raise FileNotFoundError(f"No AQ26_WEEKLY_* runs under {root}")
    return runs[-1]


def attach_file(msg: EmailMessage, path: Path) -> None:
    ctype, _ = mimetypes.guess_type(path.name)
    if not ctype:
        ctype = "application/octet-stream"
    maintype, subtype = ctype.split("/", 1)
    msg.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)


def main() -> int:
    ap = argparse.ArgumentParser(description="Email latest AQ26 weekly report bundle")
    ap.add_argument("--latest-run-root", default="outputs/weekly_reports")
    ap.add_argument("--require-attachment", default="true")
    ap.add_argument("--max-attachment-mb", type=float, default=float(os.getenv("AQ26_EMAIL_MAX_ATTACHMENT_MB", "24")))
    args = ap.parse_args()

    run = latest_run(Path(args.latest_run_root))
    zips = sorted((run / "release").glob("AQ26_WEEKLY_VALIDATED_REPORT_BUNDLE_*.zip"))
    if not zips and args.require_attachment.lower() == "true":
        raise FileNotFoundError("No release ZIP was found to email")
    attachment = zips[-1] if zips else None

    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "587") or "587")
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    mail_from = os.getenv("MAIL_FROM", username).strip()
    mail_to = os.getenv("MAIL_TO", "scottchowen@gmail.com").strip()
    if not (host and username and password and mail_from and mail_to):
        print("Email not sent: SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, MAIL_FROM and MAIL_TO must be configured as repository secrets.")
        return 2

    body_extra = ""
    if attachment:
        size_mb = attachment.stat().st_size / (1024 * 1024)
        if size_mb > args.max_attachment_mb:
            body_extra = f"\nThe report ZIP was created but is {size_mb:.1f} MB, above the {args.max_attachment_mb:.1f} MB email attachment cap. Please download it from the GitHub Actions artifact instead.\n"
            attachment = None

    msg = EmailMessage()
    msg["From"] = mail_from
    msg["To"] = mail_to
    msg["Subject"] = f"AQ26 weekly comprehensive validated report — {run.name}"
    msg.set_content(
        "Attached is the AQ26 weekly comprehensive validated report bundle where size permits.\n\n"
        f"Run folder: {run}\n"
        f"GitHub repository: {os.getenv('GITHUB_REPOSITORY', 'unknown')}\n"
        f"GitHub run id: {os.getenv('GITHUB_RUN_ID', 'unknown')}\n"
        "\nThis is an automated controlled-review evidence pack. No third-party endorsement is implied.\n"
        + body_extra
    )
    if attachment:
        attach_file(msg, attachment)

    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context) as s:
            s.login(username, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port) as s:
            s.starttls(context=context)
            s.login(username, password)
            s.send_message(msg)
    print(f"Email sent to {mail_to}; attachment={attachment}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

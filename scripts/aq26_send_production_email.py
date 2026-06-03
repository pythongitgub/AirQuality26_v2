#!/usr/bin/env python3
from __future__ import annotations
import argparse, os, smtplib, ssl
from email.message import EmailMessage
from pathlib import Path


def read_latest(path: Path) -> Path:
    if path.exists():
        p = Path(path.read_text(encoding='utf-8').strip())
        if p.exists():
            return p
    raise FileNotFoundError(f'Latest bundle path not found or invalid: {path}')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--latest-path', default='outputs/aq26_production/latest_bundle_path.txt')
    args = ap.parse_args()
    bundle = read_latest(Path(args.latest_path))
    smtp_host = os.environ.get('SMTP_HOST','')
    smtp_port = int(os.environ.get('SMTP_PORT','587') or '587')
    smtp_user = os.environ.get('SMTP_USERNAME','')
    smtp_password = os.environ.get('SMTP_PASSWORD','')
    mail_from = os.environ.get('MAIL_FROM') or smtp_user
    mail_to = os.environ.get('MAIL_TO') or 'scottchowen@gmail.com'
    if not all([smtp_host, smtp_user, smtp_password, mail_from, mail_to]):
        print('Email skipped: SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, MAIL_FROM or MAIL_TO missing.')
        return 0
    msg = EmailMessage()
    msg['Subject'] = f'AQ26 weekly validated evidence bundle: {bundle.name}'
    msg['From'] = mail_from
    msg['To'] = mail_to
    msg.set_content(
        'Attached is the AirQuality26 weekly controlled-review evidence bundle.\n\n'
        'This is a provenance-controlled review update only. It does not assert causal, legal, health, liability or endorsement findings.\n'
    )
    data = bundle.read_bytes()
    # Keep attachment bounded for SMTP reliability. Full bundle is still available via GitHub artifact / Drive.
    if len(data) <= 20 * 1024 * 1024:
        msg.add_attachment(data, maintype='application', subtype='zip', filename=bundle.name)
    else:
        msg.set_content(msg.get_content() + f'\nBundle exceeded 20 MB ({len(data)} bytes), so it was not attached. Use the GitHub artifact or Google Drive upload.\n')
    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=60) as s:
            s.login(smtp_user, smtp_password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=60) as s:
            s.starttls(context=ssl.create_default_context())
            s.login(smtp_user, smtp_password)
            s.send_message(msg)
    print(f'Email sent to {mail_to}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

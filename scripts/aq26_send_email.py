#!/usr/bin/env python3
from __future__ import annotations
import email.message, mimetypes, os, smtplib, ssl
from pathlib import Path

def latest_zip():
    zips=sorted(Path('outputs/weekly_reports').glob('AQ26_WEEKLY_COMPREHENSIVE_REPORT_*.zip'), key=lambda p:p.stat().st_mtime, reverse=True)
    return zips[0] if zips else None

def main():
    host=os.getenv('SMTP_HOST'); port=int(os.getenv('SMTP_PORT') or '587')
    user=os.getenv('SMTP_USERNAME'); pwd=os.getenv('SMTP_PASSWORD')
    mail_from=os.getenv('MAIL_FROM') or user; mail_to=os.getenv('MAIL_TO')
    if not all([host,user,pwd,mail_from,mail_to]):
        print('SMTP/email secrets not complete; skipping email.'); return
    z=latest_zip()
    if not z: raise SystemExit('No weekly report ZIP found to email')
    msg=email.message.EmailMessage()
    msg['Subject']='AQ26 weekly comprehensive evidence report'
    msg['From']=mail_from; msg['To']=mail_to
    msg.set_content(f"AQ26 weekly comprehensive evidence report attached.\n\nArtifact: {z.name}\n\nThis is a controlled-review evidence bundle; no endorsement or causal claim is made.\n")
    data=z.read_bytes()
    maintype, subtype = (mimetypes.guess_type(z.name)[0] or 'application/zip').split('/',1)
    msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=z.name)
    ctx=ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=30) as s:
        s.starttls(context=ctx); s.login(user,pwd); s.send_message(msg)
    print(f'Email sent to {mail_to} with {z.name}')
if __name__=='__main__': main()

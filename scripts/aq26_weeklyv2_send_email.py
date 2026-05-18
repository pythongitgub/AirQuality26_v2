#!/usr/bin/env python3
from __future__ import annotations
import argparse, os, smtplib, ssl
from pathlib import Path
from email.message import EmailMessage
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output-root',default='outputs'); args=ap.parse_args()
    latest=Path(args.output_root)/'weeklyv2_reports'/'LATEST_ZIP.txt'
    if not latest.exists(): print('No WeeklyV2 ZIP to email'); return
    zpath=Path(latest.read_text(encoding='utf-8').strip())
    if not zpath.exists(): print(f'Missing ZIP: {zpath}'); return
    host=os.getenv('SMTP_HOST',''); port=int(os.getenv('SMTP_PORT','587') or '587'); user=os.getenv('SMTP_USERNAME',''); pw=os.getenv('SMTP_PASSWORD',''); frm=os.getenv('MAIL_FROM') or user; to=os.getenv('MAIL_TO','')
    if not all([host,user,pw,frm,to]): print('SMTP secrets incomplete; email skipped'); return
    msg=EmailMessage(); msg['Subject']='AQ26 WeeklyV2 evidence report'; msg['From']=frm; msg['To']=to
    msg.set_content('Attached is the AQ26 WeeklyV2 controlled-review evidence bundle. No external endorsement or causal attribution is claimed.')
    data=zpath.read_bytes()
    if len(data)<=24*1024*1024: msg.add_attachment(data, maintype='application', subtype='zip', filename=zpath.name)
    else: msg.set_content(msg.get_content()+f'\n\nBundle too large to attach: {zpath} ({len(data)} bytes). Use the GitHub artifact.')
    with smtplib.SMTP(host, port, timeout=60) as smtp:
        smtp.starttls(context=ssl.create_default_context()); smtp.login(user,pw); smtp.send_message(msg)
    print(f'Email sent to {to}')
if __name__=='__main__': main()

#!/usr/bin/env python3
import argparse, os, smtplib, ssl
from pathlib import Path
from email.message import EmailMessage
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--output-root",default="outputs"); args=ap.parse_args()
    latest=Path(args.output_root)/"weekly_reports/LATEST_ZIP.txt"
    if not latest.exists(): print("No latest ZIP; email skipped"); return
    z=Path(latest.read_text(encoding="utf-8").strip())
    host=os.getenv("SMTP_HOST",""); port=int(os.getenv("SMTP_PORT","587") or "587"); user=os.getenv("SMTP_USERNAME",""); pwd=os.getenv("SMTP_PASSWORD",""); frm=os.getenv("MAIL_FROM") or user; to=os.getenv("MAIL_TO","")
    if not all([host,user,pwd,frm,to]): print("SMTP/Mail secrets incomplete; email skipped"); return
    msg=EmailMessage(); msg["Subject"]="AQ26 weekly integrated evidence report"; msg["From"]=frm; msg["To"]=to
    msg.set_content("Attached is the AQ26 weekly integrated evidence report bundle. Treat as controlled-review evidence, not external endorsement or causal attribution.")
    data=z.read_bytes()
    if len(data)<=24*1024*1024: msg.add_attachment(data,maintype="application",subtype="zip",filename=z.name)
    else: msg.set_content(msg.get_content()+f"\n\nBundle too large to attach; use GitHub Actions artifact: {z}")
    with smtplib.SMTP(host,port,timeout=60) as smtp:
        smtp.starttls(context=ssl.create_default_context()); smtp.login(user,pwd); smtp.send_message(msg)
    print(f"Email sent to {to}")
if __name__=="__main__": main()

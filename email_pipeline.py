import imaplib
import email
import pandas as pd
import re
from bs4 import BeautifulSoup
from datetime import datetime
from email.header import decode_header
from config import EMAIL, PASSWORD, IMAP_SERVER
from logger import log_info, log_error


def decode_subject(subject):
    if subject is None:
        return ""
    decoded_parts = decode_header(subject)
    result = []
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(encoding or "utf-8", errors="ignore"))
        else:
            result.append(part)
    return "".join(result)


def extract_body(msg):
    try:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    return part.get_payload(decode=True).decode(errors="ignore")

            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    html = part.get_payload(decode=True).decode(errors="ignore")
                    return BeautifulSoup(html, "html.parser").get_text()
        else:
            if msg.get_content_type() == "text/plain":
                return msg.get_payload(decode=True).decode(errors="ignore")
            elif msg.get_content_type() == "text/html":
                html = msg.get_payload(decode=True).decode(errors="ignore")
                return BeautifulSoup(html, "html.parser").get_text()
    except Exception as e:
        log_error(f"Body extraction error: {e}")

    return ""


def extract_info(subject, body, sender):
    subject = subject or ""
    body = body or ""
    sender = sender or ""

    text = (subject + " " + body).lower()

    data = {
        "category": "unknown",
        "amount": None,
        "upi": False
    }

    try:
        if any(word in text for word in ["urgent", "verify", "click here", "suspended"]):
            data["category"] = "Phishing/Fraud"

        elif any(word in text for word in ["debited", "credited", "invoice", "receipt", "otp"]):
            data["category"] = "Transactional"

            match = re.search(r'₹\s?(\d+)', text)
            if match:
                data["amount"] = int(match.group(1))

        elif any(word in text for word in ["unsubscribe", "offer", "sale", "linkedin"]):
            data["category"] = "Social & Promotional"

        elif any(word in text for word in ["win money", "lottery", "free"]):
            data["category"] = "Spam"

        else:
            data["category"] = "Personal/Professional Interaction"

        if "upi" in text:
            data["upi"] = True

    except Exception as e:
        log_error(f"Info extraction error: {e}")

    return data


def read_emails():
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL, PASSWORD)
        mail.select("inbox")

        status, messages = mail.search(None, "ALL")
        email_ids = messages[0].split()

        all_data = []

        for num in email_ids[-5:]:
            status, data = mail.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(data[0][1])

            subject = decode_subject(msg["subject"])
            sender = msg["from"]
            body = extract_body(msg)

            info = extract_info(subject, body, sender)

            all_data.append({
                "time": datetime.now(),
                "sender": sender,
                "subject": subject,
                "category": info["category"],
                "amount": info["amount"],
                "upi": info["upi"]
            })

        df = pd.DataFrame(all_data)
        df.to_csv("emails_data.csv", mode='a', header=False, index=False)

        log_info("Emails processed successfully")

        return df

    except Exception as e:
        log_error(f"Pipeline error: {e}")
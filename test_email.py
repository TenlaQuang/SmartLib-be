import os
from dotenv import load_dotenv
import email_utils

# Nạp .env
load_dotenv()

def test_mail():
    test_email = "trandinhquang2005@gmail.com" # Email của bạn để test
    subject = "SmartLib - Test Email Connection"
    html = "<h1>Connection Successful!</h1><p>This is a test email from SmartLib system.</p>"
    
    print(f"Testing mail to: {test_email}")
    print(f"Using Sender: {os.getenv('SMTP_EMAIL')}")
    
    email_utils.send_html_email(test_email, subject, html)
    print("Mail sent request executed. Please check your inbox (and SPAM).")

if __name__ == "__main__":
    test_mail()

import os

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

email_func = '''
def send_email_notification(to_email: str, subject: str, body: str):
    sender_email = os.getenv("SMTP_EMAIL")
    sender_password = os.getenv("SMTP_PASSWORD")
    if not sender_email or not sender_password:
        print(f"Cảnh báo: Chưa cấu hình SMTP_EMAIL và SMTP_PASSWORD trong .env. Bỏ qua gửi email tới {to_email}.")
        print(f"Nội dung thư dự kiến:\\nTiêu đề: {subject}\\nNội dung: {body}")
        return
        
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = to_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
            print(f"Đã gửi email thành công tới {to_email}")
    except Exception as e:
        print(f"Lỗi khi gửi email tới {to_email}: {e}")
'''

if 'def send_email_notification' not in content:
    content = content.replace('@app.get("/")', email_func + '\\n@app.get("/")')
    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched main.py")
else:
    print("Already patched")

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_html_email(to_email: str, subject: str, html_content: str, text_content: str = ""):
    """Gửi email định dạng HTML chuyên nghiệp."""
    sender_email = os.getenv("SMTP_EMAIL")
    sender_password = os.getenv("SMTP_PASSWORD")
    
    if not sender_email or not sender_password:
        print("Bỏ qua gửi mail: Chưa cấu hình SMTP_EMAIL/SMTP_PASSWORD")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"SmartLib System <{sender_email}>"
    msg["To"] = to_email

    # Phần text (cho các mail client cũ)
    if not text_content:
        text_content = "Vui lòng xem email này bằng trình duyệt hỗ trợ HTML."
    
    part1 = MIMEText(text_content, "plain")
    part2 = MIMEText(html_content, "html")

    msg.attach(part1)
    msg.attach(part2)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
            print(f"Đã gửi mail tới: {to_email}")
    except Exception as e:
        print(f"Lỗi SMTP: {e}")

def get_approval_template(full_name: str, has_nfc: bool):
    """Template HTML cho việc duyệt đơn."""
    nfc_notice = ""
    if not has_nfc:
        nfc_notice = """
        <div style="background-color: #fff3cd; border: 1px solid #ffeeba; color: #856404; padding: 15px; border-radius: 8px; margin-top: 20px;">
            <strong>Lưu ý:</strong> Bạn chưa có thẻ NFC vật lý. Vui lòng đến thư viện trong giờ hành chính để được cấp thẻ và kích hoạt tài khoản hoàn toàn.
        </div>
        """
    else:
        nfc_notice = """
        <p style="color: #28a745; font-weight: bold;">Thẻ NFC của bạn đã được kích hoạt và sẵn sàng sử dụng!</p>
        """

    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
            <h2 style="color: #007bff; text-align: center;">Chúc mừng, {full_name}!</h2>
            <p>Đơn đăng ký thành viên <strong>SmartLib</strong> của bạn đã được phê duyệt thành công.</p>
            <p>Giờ đây bạn đã có thể truy cập các dịch vụ của thư viện.</p>
            {nfc_notice}
            <div style="text-align: center; margin-top: 30px;">
                <a href="https://smartlib-be.onrender.com" style="background-color: #007bff; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold;">Truy cập Hệ thống</a>
            </div>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;">
            <p style="font-size: 12px; color: #888; text-align: center;">Đây là email tự động, vui lòng không trả lời.</p>
        </div>
    </body>
    </html>
    """

def get_rejection_template(full_name: str, reason: str):
    """Template HTML cho việc từ chối đơn."""
    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
            <h2 style="color: #dc3545; text-align: center;">Thông báo về đơn đăng ký</h2>
            <p>Chào <strong>{full_name}</strong>,</p>
            <p>Rất tiếc, đơn đăng ký thành viên SmartLib của bạn không được phê duyệt tại thời điểm này.</p>
            <div style="background-color: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <strong>Lý do từ chối:</strong> {reason}
            </div>
            <p>Vui lòng kiểm tra lại thông tin hoặc liên hệ trực tiếp với thủ thư để được hỗ trợ.</p>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;">
            <p style="font-size: 12px; color: #888; text-align: center;">SmartLib Team</p>
        </div>
    </body>
    </html>
    """

def get_new_request_template(full_name: str, user_code: str):
    """Template HTML cho sinh viên khi vừa nộp đơn xong."""
    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
            <h2 style="color: #28a745; text-align: center;">Đăng ký thành công!</h2>
            <p>Chào <strong>{full_name}</strong> (MSSV: {user_code}),</p>
            <p>Chúng tôi đã nhận được đơn đăng ký thành viên SmartLib của bạn.</p>
            <p><strong>Trạng thái:</strong> Chờ thủ thư phê duyệt.</p>
            <p>Chúng tôi sẽ thông báo kết quả cho bạn qua email này ngay khi thủ thư xử lý đơn của bạn (thường trong vòng 24h làm việc).</p>
            <p>Cảm ơn bạn đã sử dụng dịch vụ của chúng tôi!</p>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;">
            <p style="font-size: 12px; color: #888; text-align: center;">SmartLib System</p>
        </div>
    </body>
    </html>
    """

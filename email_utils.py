import os
import requests
import json

def send_html_email(to_email: str, subject: str, html_content: str, text_content: str = ""):
    """Gửi email qua Google Apps Script Proxy (Giải pháp tối ưu cho Render Free)."""
    script_url = os.getenv("GOOGLE_SCRIPT_URL")
    
    if not script_url:
        print("Bỏ qua gửi mail: Chưa cấu hình GOOGLE_SCRIPT_URL")
        return

    payload = {
        "to": to_email,
        "subject": subject,
        "html": html_content
    }

    try:
        # Gửi request POST đến Google Script
        response = requests.post(script_url, data=json.dumps(payload))
        if response.text == "Success":
            print(f"Đã gửi mail thành công qua Google Script tới: {to_email}")
        else:
            print(f"Phản hồi từ Google Script: {response.text}")
    except Exception as e:
        print(f"Lỗi kết nối Google Script: {e}")

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
def get_remind_nfc_template(full_name: str):
    """Template HTML cho việc nhắc nhở sinh viên đến nhận thẻ NFC."""
    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
            <h2 style="color: #ff9800; text-align: center;">Nhắc nhở: Lên nhận thẻ SmartLib</h2>
            <p>Chào <strong>{full_name}</strong>,</p>
            <p>Tài khoản thư viện SmartLib của bạn đã được duyệt và sẵn sàng sử dụng.</p>
            <p>Tuy nhiên, hệ thống ghi nhận bạn <strong>chưa đến nhận thẻ NFC vật lý</strong> tại quầy thủ thư.</p>
            <div style="background-color: #fff3e0; border: 1px solid #ffe0b2; color: #e65100; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <strong>Hành động:</strong> Vui lòng mang theo thẻ sinh viên đến quầy thủ thư trong giờ hành chính để được cấp thẻ và hướng dẫn sử dụng.
            </div>
            <p>Cảm ơn bạn đã hợp tác!</p>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;">
            <p style="font-size: 12px; color: #888; text-align: center;">SmartLib System</p>
        </div>
    </body>
    </html>
    """

def get_reissue_nfc_template(full_name: str, nfc_tag_id: str):
    """Template HTML cho việc cấp lại thẻ NFC mới."""
    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
            <h2 style="color: #2196f3; text-align: center;">Thông báo: Cấp lại thẻ SmartLib</h2>
            <p>Chào <strong>{full_name}</strong>,</p>
            <p>Yêu cầu cấp lại thẻ của bạn đã được thực hiện thành công.</p>
            <div style="background-color: #e3f2fd; border: 1px solid #bbdefb; color: #0d47a1; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <strong>Thông tin thẻ mới:</strong><br>
                Mã số thẻ: <span style="font-family: monospace; font-weight: bold;">{nfc_tag_id}</span>
            </div>
            <p>Thẻ cũ của bạn đã được vô hiệu hóa để đảm bảo an toàn. Bạn có thể sử dụng thẻ mới này để mượn/trả sách ngay lập tức.</p>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;">
            <p style="font-size: 12px; color: #888; text-align: center;">SmartLib System</p>
        </div>
    </body>
    </html>
    """

def get_lock_nfc_template(full_name: str):
    """Template HTML cho việc khóa thẻ NFC."""
    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
            <h2 style="color: #d32f2f; text-align: center;">Thông báo: Khóa thẻ SmartLib</h2>
            <p>Chào <strong>{full_name}</strong>,</p>
            <p>Thẻ thư viện SmartLib của bạn vừa được hệ thống <strong>tạm khóa</strong> theo yêu cầu hoặc do phát hiện bất thường.</p>
            <div style="background-color: #ffebee; border: 1px solid #ffcdd2; color: #c62828; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <strong>Trạng thái:</strong> Thẻ của bạn hiện không thể dùng để mượn/trả sách hoặc ra vào thư viện.
            </div>
            <p>Nếu bạn bị mất thẻ, vui lòng đến quầy thủ thư để làm thủ tục cấp lại thẻ mới. Nếu đây là một nhầm lẫn, hãy liên hệ ngay với chúng tôi để được hỗ trợ mở khóa.</p>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;">
            <p style="font-size: 12px; color: #888; text-align: center;">SmartLib System</p>
        </div>
    </body>
    </html>
    """

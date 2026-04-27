# SmartLib Backend API

Đây là hệ thống Backend cho dự án Quản lý Thư viện thông minh (SmartLib). 
Backend được xây dựng dựa trên kiến trúc RESTful nhằm phục vụ ứng dụng Frontend (Web/Mobile), đảm nhận việc xử lý logic, quản lý sách, khu vực, danh mục và giao tiếp với cơ sở dữ liệu.

## 🛠️ Công nghệ sử dụng
- **Ngôn ngữ:** Python 3.10+
- **Framework chính:** FastAPI (Nhanh, tài liệu tự động, dễ sử dụng)
- **ORM & Database Tool:** SQLAlchemy
- **Cơ sở dữ liệu:** PostgreSQL (Lưu trữ và quản lý qua nền tảng [Neon.tech](https://neon.tech/))
- **Deployment Hosting:** [Render.com](https://render.com/)

---

## 📂 Kiến trúc Thư mục Code
Hệ thống được chia nhỏ thành các tệp với chức năng riêng biệt để dễ bảo trì và phát triển tính năng chung:

- `main.py`: File khởi chạy chính. Nơi định nghĩa và chứa toàn bộ các API (endpoints như `GET`, `POST`, v.v.).
- `database.py`: Cấu hình đọc kết nối với PostgreSQL Database qua URL.
- `models.py`: Định nghĩa cấu trúc các Bảng dữ liệu dựa theo SQLAlchemy (dành cho DB). Nếu cần thêm Bảng hoặc Cột mới vào Database, hãy sửa ở đây.
- `schemas.py`: Định nghĩa cấu trúc dữ liệu gửi lên và trả về (dựa theo Pydantic). Giúp FastAPI kiểm tra tính đúng đắn của dữ liệu (validate data).
- `requirements.txt`: Danh sách các thư viện Python dự án đang sử dụng.

---

## 💻 Hướng dẫn chạy cho Lập trình viên (Local Development)

Để làm việc với Project này trên máy tính cá nhân, bạn làm theo các bước sau:

### Bước 1: Khởi tạo trên máy
1. Mở Terminal (Command Prompt / PowerShell) trong thư mục gốc của Backend.
2. Tạo môi trường ảo (Virtual Environment) để quản lý thư viện riêng biệt với hệ thống máy:
   ```bash
   python -m venv venv
   ```
3. Kích hoạt môi trường ảo:
   - Trên **Windows**:
     ```bash
     venv\Scripts\activate
     ```
   - Trên **Mac/Linux**:
     ```bash
     source venv/bin/activate
     ```
4. Cài đặt toàn bộ thư viện cần thiết:
   ```bash
   pip install -r requirements.txt
   ```

### Bước 2: Cài đặt biến môi trường cho Database
1. Tạo một tệp mới có tên là `.env` đặt ngang hàng với file `main.py`.
2. Nội dung file `.env` bạn cần cấu hình chuỗi kết nối vào Neon Database (Hãy lấy link Neon connection string thực tế thay vào chỗ `your-neon-link`):
   ```env
   DATABASE_URL=your-neon-link-here
   ```
   *Lưu ý: Mặc định file `.env` đã được bỏ qua bởi file `.gitignore` để tránh đưa thông tin hệ thống quan trọng lên GitHub.*

### Bước 3: Chạy ứng dụng nội bộ (Local)
Mở Terminal, đảm bảo bạn đang ở môi trường ảo `venv` và chạy lệnh sau:
```bash
uvicorn main:app --reload
```
Tham số `--reload` giúp server tự khởi động lại mỗi khi bạn Ctrl+S (lưu code) mà không cần tắt đi bật lại.

**Truy cập vào ứng dụng:**
- **Kiểm thử API (Swagger UI):** Mở trình duyệt và truy cập: [http://localhost:8000/docs](http://localhost:8000/docs)
- Tại đây, FastAPI đã tạo sẵn bộ UI để bạn có thể test trực tiếp việc thêm/xóa/sửa (Try it out) giống hệt như trên Postman cấu hình sẵn.



**Happy Coding!** Nếu có thắc mắc trong quá trình ghép code, hãy tham khảo tài liệu của [FastAPI Docs](https://fastapi.tiangolo.com/) để làm quen với cấu trúc.

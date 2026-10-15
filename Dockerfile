# Sử dụng Python image chính thức, bản nhẹ (slim)
FROM python:3.10-slim

# Thiết lập thư mục làm việc trong container
WORKDIR /app

# Ngăn Python tự động biên dịch mã nguồn thành bytecode và lưu log trực tiếp
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Cài đặt các thư viện hệ thống cần thiết
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && apt-get clean && rm -rf /var/lib/apt/lists/*

# Sao chép và cài đặt các thư viện Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ mã nguồn ứng dụng vào container
COPY . /app/

# Khởi chạy ứng dụng FastAPI bằng Uvicorn trên cổng 8030
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8030"]

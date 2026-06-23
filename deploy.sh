#!/bin/bash
# Tự động hóa cài đặt và khởi chạy hệ thống ATS trên máy chủ Linux (VM)

echo "==============================================="
echo "   HỆ THỐNG ATS - TỰ ĐỘNG HÓA TRIỂN KHAI VM    "
echo "==============================================="

# 1. Đổi cổng từ 8080 (cục bộ) sang cổng 80 (chuẩn sản xuất)
echo "[1/3] Đang cấu hình cổng chạy web..."
if [ -f "docker-compose.yml" ]; then
    sed -i 's/"8080:80"/"80:80"/g' docker-compose.yml
    echo "-> Đã chuyển đổi cổng dịch vụ sang cổng 80 thành công."
else
    echo "-> ERROR: Không tìm thấy tệp docker-compose.yml!"
    exit 1
fi

# 2. Kiểm tra và cài đặt Docker/Docker Compose nếu chưa có
echo "[2/3] Kiểm tra môi trường Docker..."
if ! command -v docker &> /dev/null; then
    echo "-> Docker chưa cài đặt. Tiến hành cài đặt Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
else
    echo "-> Docker đã sẵn sàng."
fi

if ! command -v docker-compose &> /dev/null; then
    echo "-> Docker Compose chưa cài đặt. Tiến hành cài đặt..."
    sudo apt-get update
    sudo apt-get install docker-compose -y
else
    echo "-> Docker Compose đã sẵn sàng."
fi

# 3. Khởi chạy hệ thống bằng Docker Compose
echo "[3/3] Đang khởi tạo và chạy các container..."
sudo docker-compose down
sudo docker-compose up --build -d

echo "==============================================="
echo "          TRIỂN KHAI THÀNH CÔNG!              "
echo "==============================================="
echo "Bạn có thể truy cập hệ thống bằng IP của máy ảo hoặc"
echo "tên miền qua cổng 80 (ví dụ: http://tuyendungats.com)"
echo "==============================================="

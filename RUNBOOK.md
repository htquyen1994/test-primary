# Run Guide — Crypto Trading System

> Chạy từng service theo đúng thứ tự. Mỗi service cần **một terminal riêng**.

---

## Cách nhanh nhất

```powershell
# Từ thư mục gốc — mở 6 terminal tự động
.\start.ps1

# Dừng tất cả
.\stop.ps1
```

---

## Chạy thủ công từng service

### 1 · Redis

```powershell
cd workspace\backend-workspace
docker compose up -d

# Kiểm tra
docker exec trading_redis redis-cli ping
# → PONG
```

---

### 2 · Mock Exchange &nbsp;`:8001`

```powershell
cd workspace\mock-exchange-workspace

# Lần đầu
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ..\trading-core
pip install -r requirements.txt

# Các lần sau
.\.venv\Scripts\activate
$env:PYTHONPATH = "$PWD\..\trading-core"
python main.py

# Kiểm tra → http://localhost:8001/health
```

---

### 3 · Backend API &nbsp;`:8000`

```powershell
cd workspace\backend-workspace

# Lần đầu
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # rồi điền DATABASE_URL
python db\init_db.py     # tạo bảng SQL Server

# Các lần sau
.\.venv\Scripts\activate
$env:PYTHONPATH = "$PWD\..\trading-core"
uvicorn api.main:app --reload --port 8000

# Kiểm tra → http://localhost:8000/health
```

---

### 4 · Data Pipeline

```powershell
# Terminal mới, cùng thư mục backend-workspace
cd workspace\backend-workspace
.\.venv\Scripts\activate
$env:PYTHONPATH = "$PWD\..\trading-core"
python main.py
```

---

### 5 · Celery Worker

```powershell
# Terminal mới, cùng thư mục backend-workspace
cd workspace\backend-workspace
.\.venv\Scripts\activate
$env:PYTHONPATH = "$PWD\..\trading-core"

# Windows: bắt buộc dùng --pool=solo
# (prefork/billiard bị lỗi PermissionError WinError 5 trên Windows)
celery -A celery_app worker --loglevel=info --pool=solo -Q scoring,default
```

---

### 6 · Frontend &nbsp;`:5173`

```powershell
cd workspace\frontend-workspace

# Lần đầu
npm install

# Các lần sau
npm run dev

# Kiểm tra → http://localhost:5173
```

---

## URLs sau khi chạy xong

| Service        | URL                              |
|----------------|----------------------------------|
| Dashboard      | http://localhost:5173            |
| Trade Monitor  | http://localhost:5173/monitor    |
| Backend API    | http://localhost:8000/docs       |
| Mock Exchange  | http://localhost:8001/docs       |

---

## Dừng tất cả

```powershell
.\stop.ps1

# Hoặc thủ công: Ctrl+C trong mỗi terminal, rồi
docker compose -f workspace\backend-workspace\docker-compose.yml down
```

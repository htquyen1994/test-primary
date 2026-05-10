Bạn cần 3 terminal riêng biệt. Đây là từng bước:

Terminal 1 — FastAPI Backend
cd D:\workspace\trade-workspace\workspace\backend-workspace
.venv\Scripts\activate
.venv\Scripts\python db/init_db.py
.venv\Scripts\uvicorn api.main:app --reload --port 8000
Chờ thấy:

INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
Kiểm tra: mở browser → http://localhost:8000/health → phải thấy {"status":"ok"}

--------------------------
Terminal 2 — Celery Worker
Mở PowerShell mới, chạy:

cd D:\workspace\trade-workspace\workspace\backend-workspace
.venv\Scripts\activate
.venv\Scripts\celery -A celery_app worker --loglevel=info --pool=solo -Q scoring,default
Chờ thấy:

celery@HOSTNAME ready.

------------------------
Terminal 3 — Celery Beat
cd D:\workspace\trade-workspace\workspace\backend-workspace
.venv\Scripts\activate
.venv\Scripts\celery -A celery_app beat --loglevel=info

Chờ thấy:

celery beat v5.3.6 is starting.

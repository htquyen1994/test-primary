FROM python:3.10-slim

WORKDIR /app

# No gcc needed — all packages have pre-built wheels for Python 3.10 Linux
# Install Python dependencies first (cached layer)
COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt

# Copy source
COPY . .

# Default: run Celery worker
CMD ["celery", "-A", "celery_app", "worker", "--loglevel=info", "-Q", "scoring,default"]

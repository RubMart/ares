FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Resto de deps primero; PyTorch CPU al final para no sustituirlo por una build CUDA de PyPI.
RUN pip install --upgrade pip && \
    grep -vE '^torch([=<>]|$)' requirements.txt > /tmp/requirements.docker.txt && \
    pip install -r /tmp/requirements.docker.txt && \
    pip install torch --index-url https://download.pytorch.org/whl/cpu

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "."]

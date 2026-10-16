# Slim production image for Railway (stays under typical 4 GB limits).
# CPU-only PyTorch is much smaller than the default CUDA wheels pip pulls on Linux.

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# OpenMP for numpy/scikit-learn wheels on Debian slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU-only PyTorch (required for Railway image size). Do not install torch from PyPI alone.
RUN pip install --upgrade pip && \
    pip install --no-cache-dir "torch==2.5.1" --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt constraints.txt .
RUN pip install -r requirements.txt -c constraints.txt

# Pre-cache SentenceTransformer model during build so container startup is instant
# and never hangs or times out on the first user request.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY . .

# Default for local docker run or hosts without injected PORT; platforms inject PORT at runtime.
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "exec waitress-serve --listen=0.0.0.0:${PORT:-8080} main:app"]

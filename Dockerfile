FROM python:3.12-slim

# Install ffmpeg, nodejs (JS runtime for yt-dlp signature extraction) and curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create non-root user and persistent directories
RUN useradd -m -u 10001 appuser && \
    mkdir -p /app/downloads /app/data && \
    chown -R appuser:appuser /app

USER appuser

ENV HOST=0.0.0.0
ENV PORT=5000
EXPOSE 5000

CMD ["python", "run.py"]


# ---- Stage 1: Build ----
FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Stage 2: Runtime ----
FROM python:3.11-slim

WORKDIR /app

# Copy installed dependencies from builder stage
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Run the bot
CMD ["python", "main.py"]

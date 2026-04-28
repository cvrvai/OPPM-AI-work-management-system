# Build stage
FROM python:3.12-slim AS builder
WORKDIR /build
COPY services/project/requirements.txt .
RUN pip install --upgrade pip && pip install --prefix=/install --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=builder /install /usr/local
COPY shared/ /app/shared/
COPY services/project/ /app/
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
EXPOSE 8006
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8006"]

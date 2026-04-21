FROM python:3.12-slim

WORKDIR /app

# Install shared package dependencies (not the package itself, since PYTHONPATH handles import)
COPY packages/shared/ /shared/
RUN pip install --no-cache-dir /shared

# Install service dependencies
COPY apps/ai/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# PYTHONPATH allows 'import shared' to resolve /shared/ at runtime
ENV PYTHONPATH=/

# Copy service code
COPY apps/ai/ .

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]

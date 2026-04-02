FROM python:3.12-slim

WORKDIR /app

# Install shared package dependencies (not the package itself, since PYTHONPATH handles import)
COPY shared/ /shared/
RUN pip install --no-cache-dir /shared

# Install service dependencies
COPY services/mcp/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# PYTHONPATH allows 'import shared' to resolve /shared/ at runtime
ENV PYTHONPATH=/

# Copy service code
COPY services/mcp/ .

EXPOSE 8003

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]

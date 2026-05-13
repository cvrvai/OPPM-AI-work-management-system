FROM node:20-slim

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm ci

# Copy source
COPY . .

EXPOSE 5173

# Run vite directly so API_PROXY_BASE from docker-compose env is respected
# (npm run dev overrides it with cross-env API_PROXY_BASE=)
CMD ["npx", "vite", "--host", "0.0.0.0"]

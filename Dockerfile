# Stage 1: Build the React Frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app
COPY clista-swarm-ui/package*.json ./
RUN npm install
COPY clista-swarm-ui/ ./
RUN npm run build

# Stage 2: Build the Python Backend
FROM python:3.11-slim
WORKDIR /app

# Copy python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY *.py ./

# Copy built frontend from Stage 1
COPY --from=frontend-build /app/dist /app/clista-swarm-ui/dist

# Expose Cloud Run default port
EXPOSE 8080

# Run the gateway
CMD ["uvicorn", "gateway:app", "--host", "0.0.0.0", "--port", "8080"]

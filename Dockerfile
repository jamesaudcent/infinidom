# infinidom Framework
# AI-powered dynamic website generator

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy framework code
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY run.py .

# Sites folder is mounted as a volume
VOLUME /app/sites

# Environment variables (set via docker-compose or -e flags)
ENV AI_PROVIDER="openai"
ENV AI_API_KEY=""
ENV AI_MODEL="gpt-4o-mini"
ENV AI_MAX_TOKENS=16384
ENV CONTENT_MODE="expansive"
ENV PORT=8000

EXPOSE 8000

CMD ["python", "run.py"]

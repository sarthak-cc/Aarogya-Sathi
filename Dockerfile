# One small container: FastAPI serves the API and the web phone.
# Works on Render, Koyeb, Fly.io, Railway or Hugging Face Spaces (Docker). Set API keys as host secrets.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY frontend ./frontend
WORKDIR /app/backend
RUN useradd -m saathi
USER saathi
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]

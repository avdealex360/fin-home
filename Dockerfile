FROM python:3.12-slim

WORKDIR /app

RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/data/backups && \
    chown -R appuser:appuser /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

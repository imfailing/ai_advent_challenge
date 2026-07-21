# Веб-сервис анализа удалённого GitHub-репозитория.
# Локальный git не нужен — коммиты читаются через GitHub REST API.
FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 5011

# Прод-запуск под gunicorn.
CMD ["gunicorn", "--bind", "0.0.0.0:5011", \
     "--workers", "2", "--threads", "4", "--timeout", "300", "app:app"]

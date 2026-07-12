# Образ API-сервиса (сама модель — в контейнере ollama, см. docker-compose.yml)
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5008

# Прод-запуск под gunicorn: несколько воркеров + потоки для параллельных запросов.
# Ollama сериализует инференс, поэтому воркеры в основном дают параллелизм ввода-вывода
# (стриминг, health, очередь). gthread — чтобы стриминг не блокировал воркер.
CMD ["gunicorn", "--bind", "0.0.0.0:5008", \
     "--workers", "2", "--threads", "8", "--worker-class", "gthread", \
     "--timeout", "300", "service:app"]

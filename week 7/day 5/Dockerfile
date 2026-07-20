# Веб-сервис AI-дайджеста. git нужен для чтения истории репозитория.
FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 5011

# Репозиторий монтируется в /repo (см. docker-compose). safe.directory нужен,
# т.к. владелец примонтированного репо отличается от пользователя контейнера.
CMD ["sh", "-c", "git config --global --add safe.directory '*' && \
     gunicorn --bind 0.0.0.0:5011 --workers 2 --threads 4 --timeout 300 app:app"]

FROM python:3.10-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Базовые переменные окружения
ENV BASE_DELAY=30

# Запуск скрипта
CMD ["python", "пкпикапкиквк.py"]

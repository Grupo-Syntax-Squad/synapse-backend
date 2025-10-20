FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /usr/local /usr/local
COPY . .

ENV PYTHONUNBUFFERED=1
ENV TZ=America/Sao_Paulo

CMD alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port 80

FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir poetry==2.4.1

COPY backend/pyproject.toml backend/poetry.lock backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY backend/app ./app

RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

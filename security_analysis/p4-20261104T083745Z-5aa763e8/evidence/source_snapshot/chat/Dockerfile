FROM python:3.10-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY server.py database.py auth.py migrate.py ./
COPY index.html login.html register.html ./
COPY migrations/ ./migrations/

EXPOSE 8000

CMD ["uvicorn", "server:my_api", "--host", "127.0.0.1", "--port", "8000"]

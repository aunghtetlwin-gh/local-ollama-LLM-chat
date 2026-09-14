FROM python:3.10-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
COPY index.html .

EXPOSE 8000

CMD ["uvicorn", "server:my_api", "--host", "127.0.0.1", "--port", "8000"]
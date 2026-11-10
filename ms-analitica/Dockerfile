# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Dependencias para compilar paquetes C de ML y conector PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Directorio donde se montará el volumen persistente de modelos
RUN mkdir -p /app/models

EXPOSE 5000

CMD ["python", "wsgi.py"]
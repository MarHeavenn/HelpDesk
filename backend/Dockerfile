FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=8000

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Las migraciones se aplican antes de sembrar las cuentas demo; dev_server
# siembra usando repositorios que ya consultan las tablas.
CMD ["sh", "-c", "python -m migrations.run && python dev_server.py"]

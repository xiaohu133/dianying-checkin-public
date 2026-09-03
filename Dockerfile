FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    requests \
    curl_cffi \
    cryptography

COPY dian_client.py main.py /app/

ENV PYTHONUNBUFFERED=1
EXPOSE 8080

CMD ["python", "main.py"]

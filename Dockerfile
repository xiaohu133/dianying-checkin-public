FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    requests \
    curl_cffi \
    cryptography

COPY dian_client.py yingchao_client.py yingchao_signer.js hdh_security_bg.wasm main.py /app/

ENV PYTHONUNBUFFERED=1
EXPOSE 8080

CMD ["python", "main.py"]

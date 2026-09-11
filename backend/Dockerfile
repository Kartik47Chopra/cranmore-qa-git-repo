FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN sed '/^emergentintegrations/d' requirements.txt > /tmp/req.txt && pip install --no-cache-dir -r /tmp/req.txt
COPY . .
EXPOSE 10000
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port $PORT"]

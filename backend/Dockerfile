FROM python:3.12-slim

# System libs needed by Pillow / PyMuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
# emergentintegrations is a private Emergent package not available on PyPI and not imported by the app
RUN sed '/^emergentintegrations/d' requirements.txt > /tmp/req.txt && pip install --no-cache-dir -r /tmp/req.txt

EXPOSE 8001
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]

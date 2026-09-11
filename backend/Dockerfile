# ---- Build React ----
FROM node:22 AS fe
WORKDIR /fe
COPY frontend/package.json frontend/yarn.lock ./
RUN corepack enable && yarn install --frozen-lockfile
COPY frontend/ ./
ARG REACT_APP_BACKEND_URL=https://cranmore-qa-api.onrender.com
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL
RUN yarn build

# ---- Python ----
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt .
RUN sed '/^emergentintegrations/d' requirements.txt > /tmp/req.txt && pip install --no-cache-dir -r /tmp/req.txt
COPY backend/ ./
COPY --from=fe /fe/build ./static
EXPOSE 10000
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port $PORT"]

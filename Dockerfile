FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends default-jre-headless \
  && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements-spark.txt requirements.txt ./
RUN pip install --no-cache-dir -r requirements-spark.txt
COPY . .
ENTRYPOINT ["python", "-m", "src.main"]
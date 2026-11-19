FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir boto3==1.40.18
COPY create_bucket.py /app/create_bucket.py
CMD ["python", "/app/create_bucket.py"]

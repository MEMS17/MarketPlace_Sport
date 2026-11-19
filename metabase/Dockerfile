FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir requests==2.32.4
COPY provision_metabase.py /app/provision_metabase.py
CMD ["python", "/app/provision_metabase.py"]

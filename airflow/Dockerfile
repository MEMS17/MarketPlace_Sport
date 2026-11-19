FROM apache/airflow:3.1.8-python3.12
ARG AIRFLOW_VERSION=3.1.8
RUN pip install --no-cache-dir \
    "apache-airflow==${AIRFLOW_VERSION}" \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-3.12.txt" \
    "apache-airflow-providers-fab" \
    "apache-airflow-providers-postgres" \
    "apache-airflow-providers-amazon" \
    "requests" \
    "psycopg2-binary" \
    "pytest"

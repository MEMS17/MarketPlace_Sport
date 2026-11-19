import os
import time

import boto3
from botocore.exceptions import ClientError

client = boto3.client(
    "s3", endpoint_url=os.environ["MINIO_ENDPOINT"],
    aws_access_key_id=os.environ["MINIO_ROOT_USER"],
    aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
    region_name="us-east-1",
)
bucket = os.environ["MINIO_BUCKET"]
for attempt in range(30):
    try:
        try:
            client.head_bucket(Bucket=bucket)
        except ClientError as error:
            if error.response.get("ResponseMetadata", {}).get("HTTPStatusCode") != 404:
                raise
            client.create_bucket(Bucket=bucket)
        print(f"Bucket ready: {bucket}")
        break
    except Exception:
        if attempt == 29:
            raise
        time.sleep(2)

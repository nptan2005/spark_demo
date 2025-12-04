from datetime import datetime
from airflow import DAG
from airflow.providers.google.cloud.operators.dataproc import DataprocSubmitJobOperator

PROJECT_ID = "my-cdp-demo-01"
REGION = "asia-southeast1"
CLUSTER_NAME = "my-cluster"

PYSPARK_URI = "gs://my-cdp-bronze/jobs/sample_job.py"

JOB = {
    "reference": {"project_id": PROJECT_ID},
    "placement": {"cluster_name": CLUSTER_NAME},
    "pyspark_job": {"main_python_file_uri": PYSPARK_URI},
}

with DAG(
    dag_id="spark_test_dag",
    schedule_interval=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:

    run_spark = DataprocSubmitJobOperator(
        task_id="run_spark",
        job=JOB,
        region=REGION,
        project_id=PROJECT_ID,
    )
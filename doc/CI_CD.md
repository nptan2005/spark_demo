# ✅ MỤC TIÊU
````code
git push → GitHub Actions → Auth OIDC → Upload DAG → Composer DAG folder → Airflow load DAG → (optional) Trigger DAG
````

# BƯỚC 0 — CHUẨN HOÁ THÔNG TIN:

## Thông tin

```text
PROJECT_ID = my-cdp-demo-01
REGION = asia-southeast1
COMPOSER_ENV = airflow-test-01
REPO = nptan2005/spark_demo
SERVICE ACCOUNT CI = ci-deployer@my-cdp-demo-01.iam.gserviceaccount.com
WORKLOAD_IDENTITY_POOL = github-pool
WORKLOAD_IDENTITY_PROVIDER = github-provider
```

# BƯỚC 1 — TẠO SERVICE ACCOUNT CHO CI/CD:

Chạy trên **Cloud Shell**:

```bash
PROJECT_ID="my-cdp-demo-01"
SA_NAME="ci-deployer"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud iam service-accounts create "${SA_NAME}" \
  --display-name="GitHub CI deploy DAGs to Composer"
```

# BƯỚC 2 — GÁN QUYỀN CHO SERVICE ACCOUNT

## 2.1 — Cho phép CI upload DAG vào bucket Composer:

```bash
gcloud projects add-iam-policy-binding my-cdp-demo-01 \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.objectAdmin"
```

## 2.2 — Cho phép CI trigger DAG:

```bash
gcloud projects add-iam-policy-binding my-cdp-demo-01 \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/composer.admin"
```

## 2.3 — Cho phép CI impersonate qua OIDC:

Sẽ thực hiện ở bước 4.

# BƯỚC 3 — TẠO WORKLOAD IDENTITY POOL & OIDC PROVIDER:

```bash
POOL_ID="github-pool"
PROVIDER_ID="github-provider"

gcloud iam workload-identity-pools create "${POOL_ID}" \
  --location="global" \
  --display-name="GitHub Actions Pool"


gcloud iam workload-identity-pools providers create-oidc "${PROVIDER_ID}" \
  --location="global" \
  --workload-identity-pool="${POOL_ID}" \
  --display-name="GitHub Provider" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.actor=assertion.actor" \
  --attribute-condition="assertion.repository=='nptan2005/spark_demo'"
```

# BƯỚC 4 — CHO GITHUB REPO ĐƯỢC IMPERSONATE SERVICE ACCOUNT:

Bạn dùng repo:
👉 nptan2005/spark_demo

```bash
PROJECT_NUMBER=$(gcloud projects describe my-cdp-demo-01 --format="value(projectNumber)")
POOL_ID="github-pool"

gcloud iam service-accounts add-iam-policy-binding \
  ci-deployer@my-cdp-demo-01.iam.gserviceaccount.com \
  --project="my-cdp-demo-01" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/nptan2005/spark_demo"
```

# BƯỚC 5 — TẠO GIÁ TRỊ SECRET CHO GITHUB REPO:

Vào:
```
GitHub → spark_demo → Settings → Secrets and Variables → Actions → New Repository Secret
```

| **Key**                  |   **Values**                                                                   |
|--------------------------|--------------------------------------------------------------------------------|
|GCP_PROJECT|my-cdp-demo-01|
|GCP_SA_EMAIL|ci-deployer@my-cdp-demo-01.iam.gserviceaccount.com|
|WIF_POOL_ID|github-pool|
|WIF_PROVIDER_ID|github-provider|
|COMPOSER_ENV|airflow-test-01|
|COMPOSER_REGION|asia-southeast1|

# BƯỚC 6 — TẠO FILE WORKFLOW CI/CD:

Trong repo spark_demo, tạo file:

```
.github/workflows/deploy_dags.yml
```
## Với nội dung FULL & CHUẨN NHẤT:


```yaml
name: Deploy DAGs to Composer

on:
  push:
    branches: [ "main" ]
    paths:
      - "dags/**"

permissions:
  id-token: write
  contents: read

env:
  PROJECT_ID: ${{ secrets.GCP_PROJECT }}
  COMPOSER_ENV: ${{ secrets.COMPOSER_ENV }}
  COMPOSER_REGION: ${{ secrets.COMPOSER_REGION }}
  DAGS_DIR: "dags"

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Authenticate to Google Cloud via OIDC
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: "projects/${{ env.PROJECT_ID }}/locations/global/workloadIdentityPools/${{ secrets.WIF_POOL_ID }}/providers/${{ secrets.WIF_PROVIDER_ID }}"
          service_account: ${{ secrets.GCP_SA_EMAIL }}

      - name: Setup gcloud CLI
        uses: google-github-actions/setup-gcloud@v2
        with:
          project_id: ${{ env.PROJECT_ID }}
          export_default_credentials: true

      - name: Get Composer DAGS bucket
        id: dag_bucket
        run: |
          BUCKET=$(gcloud composer environments describe "${{ env.COMPOSER_ENV }}" \
            --location "${{ env.COMPOSER_REGION }}" \
            --format="value(config.dagGcsPrefix)")
          echo "bucket=$BUCKET" >> $GITHUB_OUTPUT

      - name: Sync DAGs to Composer
        run: |
          echo "Deploying DAG files..."
          gsutil -m rsync -r "./${{ env.DAGS_DIR }}" "${{ steps.dag_bucket.outputs.bucket }}"

      - name: Trigger DAG (optional)
        if: ${{ github.ref == 'refs/heads/main' }}
        run: |
          echo "Triggering DAG: spark_test_dag (change name if needed)"
          gcloud composer environments run "${{ env.COMPOSER_ENV }}" \
            --location "${{ env.COMPOSER_REGION }}" \
            dags trigger -- spark_test_dag || true
```

# 👌 TEST:

## 1️⃣ Tạo thư mục dags/ trong repo:

```code
spark_demo/dags/spark_test_dag.py
```
spark_test_dag.py:

```python
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
```

## 2️⃣ Commit + Push:

```bash
git add .
git commit -m "add spark dag"
git push origin main
```

→ GitHub Actions chạy
→ Tự động upload DAG
→ Airflow load DAG
→ Nếu bạn bật trigger thì DAG chạy luôn.



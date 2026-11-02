import os
from google.cloud import bigquery, storage
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
REGION = os.getenv("GCP_REGION", "southamerica-east1")

def get_bigquery_client() -> bigquery.Client:
    """Retorna cliente autenticado do BigQuery."""
    return bigquery.Client(project=PROJECT_ID, location=REGION)

def get_storage_client() -> storage.Client:
    """Retorna cliente autenticado do Google Cloud Storage."""
    return storage.Client(project=PROJECT_ID)

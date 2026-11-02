"""
Script de ingestão para Camada Bronze:
1. Gera ou carrega datasets de E-commerce (ex: Olist format).
2. Converte para formato Parquet particionado / otimizado.
3. Faz upload dos arquivos para o Google Cloud Storage (GCS).
"""

import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from src.utils.gcp_client import get_storage_client

load_dotenv()
BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")

def upload_file_to_gcs(local_file_path: str, destination_blob_name: str):
    """Envia um arquivo local para o bucket GCS."""
    if not BUCKET_NAME:
        print("[AVISO] GCS_BUCKET_NAME não configurado no .env. Salvando apenas localmente.")
        return

    storage_client = get_storage_client()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(destination_blob_name)

    print(f"Enviando {local_file_path} -> gs://{BUCKET_NAME}/{destination_blob_name}...")
    blob.upload_from_filename(local_file_path)
    print("Upload concluído com sucesso!")

def generate_sample_raw_data():
    """Cria uma amostra dos dados simulando ingestão inicial para testes imediatos."""
    os.makedirs("data/raw", exist_ok=True)
    
    # Amostra de Pedidos (Orders)
    orders = pd.DataFrame([
        {
            "order_id": "ord_001",
            "customer_id": "cust_101",
            "order_status": "delivered",
            "order_purchase_timestamp": "2026-09-01 10:20:00",
            "order_delivered_customer_date": "2026-09-05 14:10:00",
            "order_estimated_delivery_date": "2026-09-08 00:00:00"
        },
        {
            "order_id": "ord_002",
            "customer_id": "cust_102",
            "order_status": "delivered",
            "order_purchase_timestamp": "2026-09-02 11:30:00",
            "order_delivered_customer_date": "2026-09-10 16:00:00",
            "order_estimated_delivery_date": "2026-09-07 00:00:00"
        },
        {
            "order_id": "ord_003",
            "customer_id": "cust_103",
            "order_status": "shipped",
            "order_purchase_timestamp": "2026-09-03 15:45:00",
            "order_delivered_customer_date": None,
            "order_estimated_delivery_date": "2026-09-12 00:00:00"
        }
    ])
    orders_path = "data/raw/orders.parquet"
    orders.to_parquet(orders_path, index=False)
    print(f"Dataset de exemplo gerado: {orders_path}")
    return orders_path

if __name__ == "__main__":
    file_path = generate_sample_raw_data()
    # Para enviar para a nuvem quando as credenciais estiverem prontas:
    # upload_file_to_gcs(file_path, "bronze/orders/orders.parquet")

"""
finance_pipeline.py
────────────────────
DAG Airflow — orchestre le pipeline Finance BigData.
Exécution : toutes les heures
Ordre :
  1. scraping        → collecte toutes les sources
  2. batch_ingestion → déplace vers data/raw/
  3. minio_upload    → archive dans MinIO
  4. silver          → nettoyage + DuckDB
  5. gold            → KPIs + DuckDB
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import sys
import os

# ── Chemin vers le projet ─────────────────────────────────
PROJECT_DIR = "/opt/airflow/project"
sys.path.insert(0, PROJECT_DIR)
sys.path.insert(0, os.path.join(PROJECT_DIR, "scraping"))
sys.path.insert(0, os.path.join(PROJECT_DIR, "ingestion"))
sys.path.insert(0, os.path.join(PROJECT_DIR, "ingestion", "medallion"))

# ── Arguments par défaut ──────────────────────────────────
default_args = {
    "owner":            "finance",
    "depends_on_past":  False,
    "start_date":       datetime(2026, 5, 1),
    "retries":          3,
    "retry_delay":      timedelta(minutes=5),
    "email_on_failure": False,
}

# ── Définition du DAG ─────────────────────────────────────
dag = DAG(
    dag_id="finance_pipeline",
    default_args=default_args,
    description="Pipeline complet : scraping → ingestion → MinIO → Silver → Gold",
    schedule_interval="0 * * * *",   # toutes les heures
    catchup=False,
    tags=["finance", "bigdata", "medaillon"],
)


# ════════════════════════════════════════════════════════════
#  Tâches
# ════════════════════════════════════════════════════════════

def task_scraping():
    from main import collecter_tout
    df = collecter_tout()
    print(f"Scraping terminé : {len(df)} actifs collectés")


def task_batch_ingestion():
    sys.path.insert(0, os.path.join(PROJECT_DIR, "ingestion"))
    from batch_ingestion import batch_job
    batch_job()
    print("Batch ingestion terminé")


def task_minio_upload():
    from minio_uploader import upload_tout
    result = upload_tout()
    print(f"MinIO upload : {result['ok']} fichiers OK, {result['erreur']} erreurs")


def task_silver():
    from silver import transformer_silver
    df = transformer_silver()
    print(f"Silver terminé : {len(df)} lignes propres")


def task_gold():
    from gold import transformer_gold
    transformer_gold()
    print("Gold terminé : KPIs générés")


# ════════════════════════════════════════════════════════════
#  Opérateurs
# ════════════════════════════════════════════════════════════

t1_scraping = PythonOperator(
    task_id="scraping",
    python_callable=task_scraping,
    dag=dag,
)

t2_batch = PythonOperator(
    task_id="batch_ingestion",
    python_callable=task_batch_ingestion,
    dag=dag,
)

t3_minio = PythonOperator(
    task_id="minio_upload",
    python_callable=task_minio_upload,
    dag=dag,
)

t4_silver = PythonOperator(
    task_id="silver",
    python_callable=task_silver,
    dag=dag,
)

t5_gold = PythonOperator(
    task_id="gold",
    python_callable=task_gold,
    dag=dag,
)

# ── Ordre d'exécution ─────────────────────────────────────
t1_scraping >> t2_batch >> t3_minio >> t4_silver >> t5_gold
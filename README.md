## Technologies

| Composant | Technologie |
|---|---|
| Scraping | Python, BeautifulSoup, REST APIs |
| Streaming | Apache Kafka |
| Data Lake | MinIO (compatible S3) |
| Transformation | Python, Pandas, DuckDB/SQL |
| Orchestration | Apache Airflow |
| Data Warehouse | PostgreSQL |
| Visualisation | Streamlit, Plotly |

## Lancement rapide

### 1. Démarrer les services Docker
```bash
docker-compose up -d
```

### 2. Installer les dépendances Python
```bash
pip install -r requirements.txt
```

### 3. Lancer le pipeline manuellement
```bash
# Scraping
python scraping/main.py

# Ingestion batch
python ingestion/batch_ingestion.py --once

# Médaillon Silver + Gold
python ingestion/medallion/silver.py
python ingestion/medallion/gold.py

# Data Warehouse
python ingestion/dw_loader.py

# Contrôles qualité
python ingestion/data_quality.py

# Dashboard
streamlit run dashboard/app.py
```

### 4. Airflow (orchestration automatique)
Accessible sur : http://localhost:8082
- Login : admin / admin
- DAG : finance_pipeline (toutes les heures)

## Services

| Service | URL | Login |
|---|---|---|
| Airflow | http://localhost:8082 | admin/admin |
| MinIO | http://localhost:9001 | minioadmin/minioadmin123 |
| Kafka UI | http://localhost:8081 | — |
| Dashboard | http://localhost:8501 | — |

## Structure du projet
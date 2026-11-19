# Marketplace Sport Analytics

MVP de plateforme analytique pour une marketplace de matériel de sport. La source REST simulée génère des commandes déterministes par date. Airflow orchestre leur archivage dans MinIO et leur chargement vers PostgreSQL. Metabase est provisionné avec deux dashboards.

## Architecture

```mermaid
flowchart LR
    API[API Flask<br/>Bearer token] --> Hook[MarketplaceAPIHook]
    Hook --> DAG[Airflow 3.1.8]
    DAG -->|JSON brut, partition dt| S3[(MinIO / data-lake)]
    DAG -->|DELETE + INSERT par date| STG[(PostgreSQL staging)]
    STG --> DWH[(PostgreSQL dwh étoile)]
    DWH --> V[analytics views]
    V --> MB[Metabase<br/>2 dashboards]
```

## Démarrer

Prérequis : Docker Desktop avec Docker Compose v2, environ 8 Go de RAM disponibles. Depuis ce dossier :

```powershell
Copy-Item .env.example .env
docker compose up -d --build
docker compose ps
```

Le démarrage initial construit les services, crée les schémas PostgreSQL et le bucket MinIO, initialise Airflow et prépare Metabase. Les ports hôte sont choisis pour éviter les TP locaux existants.

| Service | Adresse hôte | Compte local par défaut |
| --- | --- | --- |
| Airflow | http://localhost:8080 | `admin` / `admin-local` |
| Metabase | http://localhost:3000 | `admin@marketplace.local` / `SportData2026!` |
| Console MinIO | http://localhost:9101 | `minio_admin` / `minio_password_local` |
| API | http://localhost:5001 | Bearer `formation-token-2026` |
| PostgreSQL DWH | `localhost:55433` | `marketplace` / `marketplace-local`, base `dwh` |

Valeurs de formation réservées à une machine locale. Modifier `.env` avant toute exposition réseau. `.env` est ignoré par Git.

## Exécuter le pipeline

L’API est simulée dans ce dépôt : `GET /orders?date=YYYY-MM-DD`, `/sellers`, `/products` et `/customers`; sauf `/health`, les routes demandent `Authorization: Bearer formation-token-2026`. Une date donnée renvoie toujours les mêmes commandes.

Le DAG `marketplace_orders_ingest_daily` s’exécute chaque jour et peut être déclenché manuellement dans Airflow. Pour vérifier vite le flux sur une date déterministe :

```powershell
docker compose exec airflow-worker airflow dags test marketplace_orders_ingest_daily 2026-04-07
docker compose exec postgres-dwh psql -U marketplace -d dwh -c "SELECT dt, count(DISTINCT order_id) AS commandes, sum(total) AS ca_eur, sum(commission) AS commission_eur FROM dwh.fact_orders WHERE dt='2026-04-07' GROUP BY dt;"
docker compose exec postgres-dwh psql -U marketplace -d dwh -c "SELECT * FROM analytics.daily_summary ORDER BY dt DESC LIMIT 5;"
```

Relancer la première commande avec la même date est attendu. Vérifier que `count(*)` pour `dt='2026-04-07'` ne double pas : staging et `dwh.fact_orders` suppriment puis rechargent la partition de date dans une transaction. L’objet brut `raw/orders/dt=2026-04-07/data.json` est écrasé au même chemin par le même résultat déterministe.

## Modèle

- `staging.orders` : date, identifiant et payload JSON de chaque commande.
- `dwh.dim_seller`, `dwh.dim_product`, `dwh.dim_date` : dimensions descriptives.
- `dwh.fact_orders` : grain d’une ligne produit achetée. Une commande comporte actuellement une ligne dans l’API simulée, mais l’identifiant de commande est conservé pour agréger correctement le panier.
- `analytics.daily_summary`, `analytics.seller_daily`, `analytics.category_daily` : tables d’agrégats remplacées par date à chaque run, utilisées par Metabase.

Le taux de commission est 12 %. Le chiffre d’affaires (`total`) est le montant payé pour la ligne; `commission` est calculée par l’API. Le panier moyen est la somme des lignes divisée par le nombre de commandes, jamais par le nombre de lignes.

## Dashboards

Au premier démarrage, `metabase-provision` crée la base de connexion, les questions SQL et les deux dashboards :

1. **Executive Summary - Sport** : CA du dernier jour chargé, évolution du CA sur 30 jours, top 5 vendeurs.
2. **Top Sellers - Sport** : top 10 vendeurs du mois chargé, commissions journalières, vendeurs sans vente récente.

Les indicateurs utilisent la dernière date présente dans le DWH. Après un premier run du DAG, rafraîchir la page Metabase.

## Tests et contrôles

```powershell
docker compose exec airflow-worker pytest /opt/airflow/tests -q
docker compose logs --tail 100 airflow-scheduler airflow-worker
docker compose logs --tail 100 metabase-provision
```

Les tests couvrent le chargement des DAGs, `catchup=False`, la présence du remplacement idempotent par date, ainsi que l’authentification et le déterminisme de l’API.

## Arrêter

```powershell
docker compose down
```

Les données persistent dans les volumes nommés. `docker compose down -v` supprime les bases, le bucket et les métadonnées Metabase.

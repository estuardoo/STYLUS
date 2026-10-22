# Retail Intelligence & Personal Shopping Assistant

Plataforma Big Data de retail en **Google Cloud** con datos de **H&M Personalized Fashion Recommendations**:
ingesta batch y streaming, lakehouse medallion (GCS + BigQuery), recomendaciones, asistente con
**Vertex AI Gemini**, tienda web con saldo simulado y control de costos automatizado.
Proyecto final · UTEC Taller de Arquitectura Big Data.

## Equipo

| Integrante | Perfil | Foco |
|---|---|---|
| Estuardo Oliver | ML / Analytics | Asistente Gemini, recomendaciones, analítica |
| Winston Quispe | Cloud Computing | Terraform, GCP, Pub/Sub, Dataflow, CI/CD, costos |
| Nicole Arenas | Datos + API + Modelado | Bronze/Silver/Gold, modelo estrella, FastAPI, Cloud SQL |
| Gianmarco Mejia | Dashboard / BI | KPIs, Looker Studio, presentación |

Tareas, pasos, despliegue y variables: `docs/gestion/Matriz_Auditoria_Proyecto.xlsx` · Guía: [`docs/DEPLOY.md`](docs/DEPLOY.md)

## Estructura

```
infra/terraform/          GCS, BigQuery, Pub/Sub, IAM, Cloud SQL, Cloud Run, WIF, presupuesto
ingestion/batch/          H&M -> Bronze (GCS) con manifiesto SHA-256
ingestion/streaming/      Replay de transacciones como eventos 2026 -> Pub/Sub
pipelines/batch/          Silver con Spark (Serverless for Apache Spark)
pipelines/streaming/      Dataflow: dedup, ventanas, datos tardíos, DLQ, métricas de lag
pipelines/reco/           Evaluación del recomendador (MAP@12, split temporal)
sql/                      bronze/ silver/ gold/ (modelo estrella y vistas BI)
api/                      FastAPI + web + asistente Gemini + wallet (Cloud Run / Cloud SQL)
cost/                     Calculadora de costos y costo real por pedido
docs/                     Entregas, arquitectura, despliegue, runbooks, demo, diccionario
tests/                    Pruebas unitarias (costos, replay, API)
data/                     SOLO LOCAL (excluido de Git)
```

## Inicio rápido (local, sin GCP)

```bash
cp .env.example .env
make setup test cost          # dependencias, pruebas y calculadora
make catalog-local            # catálogo H&M -> SQLite (data/retail_demo.db)
make api-local                # tienda en http://localhost:8080 · OpenAPI en /docs
make reco-eval                # MAP@12 con datos reales
```

## Despliegue en GCP

Resumen (detalle y variables en `docs/DEPLOY.md`):

```bash
make gcp-setup tf-bootstrap tf-init tf-plan   # revisar el plan
make tf-apply                                  # infraestructura
make ingest-raw bq-bronze silver-gcp bq-silver bq-gold
# GitHub > Actions > deploy-api  (usa Workload Identity Federation, sin llaves)
make catalog-gcp                               # Gold -> Cloud SQL
make dataflow-start replay ... dataflow-stop   # solo durante la demo
```

## Resultados medidos

| Indicador | Valor |
|---|---|
| Transacciones / pedidos / clientes / artículos | 31,788,324 / 9,080,179 / 1,371,980 / 105,542 |
| MAP@12 popularidad vs recompra + popularidad | 0.00875 vs 0.02622 (+200%) |
| Costo estimado producción | USD 281.83/mes · USD 0.00075 por pedido |

## Reglas

- Nunca versionar datos, credenciales ni `*.tfstate` (lo valida la CI).
- Eventos 2026 = re-emisión de transacciones reales: `source_t_dat` conserva la fecha original e `is_synthetic=true`.
- Precio, stock y saldo de la tienda son simulados; ninguna compra se ejecuta sin confirmación explícita.
- Datos: [H&M Kaggle](https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations), uso según las reglas de la competencia.

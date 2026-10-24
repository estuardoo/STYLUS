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

| Archivo | Para qué |
|---|---|
| `config/control_plataforma.json` | **Único lugar donde se editan inputs**: parámetros, APIs, cuentas, permisos, usuarios iniciales, datasets, tablas, columnas, secretos |
| `ops.py` | Orquestador: `python ops.py <comando>` (ver `python ops.py -h`) |
| `docs/gestion/Matriz_Auditoria_Proyecto.xlsx` | Tareas, perfiles, pasos 1-2-3 y orden de despliegue |
| [`docs/DEPLOY.md`](docs/DEPLOY.md) | Guía de despliegue |

## Estructura

```
config/                   JSON de control + archivos generados (no editar generated/)
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

## Panel de control (opcional, recomendado)

`python ops.py panel` abre http://127.0.0.1:8765 en tu navegador: edita toda la configuración
y las tablas (usuarios, permisos, cuentas, APIs) y ejecuta cada paso de `ops.py` con un botón, viendo el registro en vivo.
Corre solo en tu máquina (127.0.0.1); no lo expongas a la red. Si editas el JSON a mano, usa un editor que soporte UTF-8
con pestañas por sección. Es la forma recomendada de editar la configuración (en vez de tocar el JSON a mano).

## Inicio rápido (local, sin GCP)

```bash
pip install -r requirements.txt
python ops.py config                          # valida config/control_plataforma.json y genera configuración
python -m unittest discover -s tests          # pruebas
python cost/estimate_costs.py                 # calculadora de costos
python ops.py local                           # tienda en http://localhost:8080 · OpenAPI en /docs
python pipelines/reco/baseline_eval.py        # MAP@12 con datos reales
```

## Despliegue en GCP

Recomendado: Google Cloud Shell (ya trae gcloud, Terraform, Python, Docker). Detalle en `docs/DEPLOY.md`.

```bash
# 1. Editar config/control_plataforma.json (project_id, emails, billing_account, github_repo)
python ops.py config
python ops.py bootstrap && python ops.py plan && python ops.py apply
python ops.py subir-datos          # desde la PC que tiene data/raw
python ops.py bronze && python ops.py silver && python ops.py gold
python ops.py api                  # imagen + Cloud Run + catálogo en Cloud SQL
python ops.py verificar            # BigQuery real vs config/control_plataforma.json
python ops.py destroy              # al terminar
```

## Resultados medidos

| Indicador | Valor |
|---|---|
| Transacciones / pedidos / clientes / artículos | 31,788,324 / 9,080,179 / 1,371,980 / 105,542 |
| MAP@12 popularidad vs recompra + popularidad | 0.00875 vs 0.02622 (+200%) |
| Costo estimado producción | USD 370.83/mes · USD 0.00098 por pedido (Gemini 3.1 Flash-Lite) |

## Reglas

- Nunca versionar datos, credenciales ni `*.tfstate` (lo valida la CI). Contraseñas y tokens: Secret Manager, nunca config/control_plataforma.json.
- Eventos 2026 = re-emisión de transacciones reales: `source_t_dat` conserva la fecha original e `is_synthetic=true`.
- Precio, stock y saldo de la tienda son simulados; ninguna compra se ejecuta sin confirmación explícita.
- Datos: [H&M Kaggle](https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations), uso según las reglas de la competencia.

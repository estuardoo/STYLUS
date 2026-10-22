"""Genera docs/gestion/Matriz_Auditoria_Proyecto.xlsx y docs/DEPLOY.md desde una sola fuente.
Uso: python docs/_generadores/build_matriz.py   (desde la raíz del repo)
Ojo: sobrescribe los estados editados a mano en el Excel; actualizar aquí primero."""
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parents[2]
E, W, N, G, T = "Estuardo Oliver", "Winston Quispe", "Nicole Arenas", "Gianmarco Mejia", "Todo el equipo"
F1, F2, F3 = "24-oct-2026", "07-nov-2026", "20-nov-2026"
H, L, P = "Hecho", "Listo para desplegar", "Pendiente"

PERFILES = [
    (E, "ML / Analytics", "Chatbot con Vertex AI Gemini, analítica, recomendaciones; integra documentos y demo."),
    (W, "Cloud Computing", "Todo lo nube: Terraform, IAM, GCS, Pub/Sub, Dataflow (ingesta streaming), CI/CD, costos, DRP."),
    (N, "Datos + API + Modelado", "Bronze/Silver/Gold, calidad, modelo estrella, FastAPI y base transaccional."),
    (G, "Dashboard / BI", "KPIs, Looker Studio, calculadora y tablero de costos, diagramas y slides."),
]

# ID, paso, fase, nombre, acción, entregable, comando, depende, responsable, apoyo, estado, evidencia
TAREAS = [
    ("P1-01", 1, "Datos", "Auditoría de datos H&M", "Perfilar filas, nulos, fechas, cardinalidad y cobertura", "Word §4", "", "", N, E, H, "31.8M líneas, 9.08M pedidos, 1.37M clientes, 105,542 artículos"),
    ("P1-02", 1, "Gestión", "Ordenar carpeta y repositorio", "Estructura por capas; Amazon/zip archivados; secretos fuera", "README.md", "", "", E, W, H, "data/_archive y .secrets/ fuera de Git"),
    ("P1-03", 1, "Seguridad", "Proteger datos y secretos", ".gitignore + regla CI que bloquea CSV/ZIP/tfstate/credenciales", ".gitignore, .github/workflows/ci.yml", "", "", W, "", H, "Regla 'Sin datos ni secretos versionados'"),
    ("P1-04", 1, "Diseño", "Justificar stack GCP", "Decisión por capa con alternativa descartada", "Word §5", "", "", W, E, H, "Tabla de ADR"),
    ("P1-05", 1, "Diseño", "Diagrama end-to-end", "Fuentes, ingesta, almacenamiento, cómputo, exposición", "docs/architecture/arquitectura.png", "dot -Tpng docs/architecture/arquitectura_vertical.dot", "", G, W, H, "Graphviz regenerable"),
    ("P1-06", 1, "Diseño", "Integración multifuente", "Batch H&M + replay 2026; doble reloj source_t_dat/event_time", "Word §6", "", "P1-01", N, W, H, ""),
    ("P1-07", 1, "Diseño", "Ingesta y almacenamiento", "GCS medallion + BigQuery + Cloud SQL; formatos y particiones", "Word §7", "", "P1-06", N, W, H, ""),
    ("P1-08", 1, "Diseño", "Escalabilidad Black Friday", "Autoescalado, desacople, degradación controlada", "Word §8", "", "", W, N, H, "Escenario 5x en calculadora"),
    ("P1-09", 1, "Costos", "Calculadora y costo por pedido", "YAML -> Excel con fórmulas; 4 escenarios; año 1", "docs/entrega1/Calculadora_Costos_GCP.xlsx", "make cost", "", G, W, H, "Año 1 USD 4,058; USD 0.00075/pedido"),
    ("P1-10", 1, "Costos", "Automatizar control de costos", "Precios vía API, budget con alertas, costo real por pedido", "cost/, infra/terraform/main.tf", "make cost-refresh", "P2-01", W, G, L, "Probado local; activar billing export en consola"),
    ("P1-11", 1, "Resiliencia", "DRP / HA", "RPO/RTO por componente y runbook", "Word §10, docs/runbooks/drp.md", "", "", W, N, H, ""),
    ("P1-12", 1, "BI", "Catálogo de KPIs", "Metas de datos, streaming, modelo, API, negocio, costo", "Word §11", "", "", G, E, H, ""),
    ("P1-13", 1, "Datos", "Ingesta Bronze con manifiesto", "SHA-256 y filas por archivo; rsync idempotente", "ingestion/batch/upload_raw.py", "make manifest", "", N, W, H, "Manifiesto real en data/manifests/"),
    ("P1-14", 1, "Infra", "Terraform base", "Buckets, BigQuery, Pub/Sub+DLQ, IAM, Artifact Registry, budget", "infra/terraform/", "make tf-check", "", W, "", L, "tofu validate OK (sin credenciales)"),
    ("P1-15", 1, "Gestión", "Documento Word Entrega 1", "Examen + P1 profesional", "docs/entrega1/*.docx (+PDF)", "", "P1-01..P1-14", E, T, H, ""),
    ("P1-16", 1, "Gestión", "Matriz de auditoría y roles", "Tareas, pasos, despliegue y variables", "docs/gestion/Matriz_Auditoria_Proyecto.xlsx", "python docs/_generadores/build_matriz.py", "", E, T, H, "Este archivo"),
    ("P1-17", 1, "Infra", "Crear proyecto GCP", "Proyecto, facturación/créditos, accesos IAM del equipo", "Proyecto GCP", "ver hoja Despliegue D01-D03", "", W, "", P, ""),
    ("P1-18", 1, "Gestión", "Publicar repositorio GitHub", "Crear repo privado, push y CI en verde", "URL del repo", "git push -u origin main", "P1-17", W, T, P, "Git inicializado localmente"),
    ("P1-19", 1, "Gestión", "Revisión y envío Entrega 1", "Revisión cruzada del Word y envío antes de 23:59", "Word enviado", "", "P1-15", E, T, P, ""),

    ("P2-01", 2, "Infra", "Desplegar infraestructura dev", "Bootstrap de estado, plan y apply", "Recursos en GCP", "make gcp-setup tf-bootstrap tf-init tf-plan tf-apply", "P1-17", W, "", P, ""),
    ("P2-02", 2, "Datos", "Cargar Bronze (GCS + BigQuery)", "CSV primero, imágenes después; tablas externas y nativa particionada", "retail_bronze.*", "make ingest-raw bq-bronze", "P2-01", N, W, P, "SQL y script listos"),
    ("P2-03", 2, "Datos", "Silver con Spark", "Tipado, nulos, cuarentena con motivo, Parquet particionado, reporte conciliado", "pipelines/batch/silver_hm.py", "make silver-gcp", "P2-02", N, W, L, "Local: 546,741 filas, 3 rechazos inyectados detectados, conciliado"),
    ("P2-04", 2, "Datos", "Silver en BigQuery + vista de eventos", "LOAD DATA de Parquet; eventos deduplicados por event_id", "sql/silver/01_load_silver.sql", "make bq-silver", "P2-03", N, "", L, ""),
    ("P2-05", 2, "Modelado", "Gold: modelo estrella", "fact_sales, fact_orders, dim_article/customer/date/channel", "sql/gold/01_gold_model.sql", "make bq-gold", "P2-04", N, E, L, ""),
    ("P2-06", 2, "Streaming", "Replay de eventos 2026", "Transacciones reales re-emitidas con event_id idempotente", "ingestion/streaming/replay_publisher.py", "make replay", "P2-01", W, "", L, "Dry-run sobre datos reales OK"),
    ("P2-07", 2, "Streaming", "Ruta económica Pub/Sub -> BigQuery", "Suscripción BigQuery con DLQ", "infra/terraform/main.tf", "", "P2-01", W, "", L, ""),
    ("P2-08", 2, "Streaming", "Pipeline Dataflow", "Validación, dedup, ventanas 1 min, datos tardíos, DLQ, lag p50/p95", "pipelines/streaming/dataflow_events.py", "make dataflow-start / dataflow-stop", "P2-06", W, N, L, "DirectRunner: 350 mensajes -> 300 únicos, 2 a DLQ"),
    ("P2-09", 2, "ML", "Popularidad y catálogo de servicio", "reco_popular y v_catalog_serving en Gold", "sql/gold/01_gold_model.sql", "make bq-gold", "P2-05", E, N, L, ""),
    ("P2-10", 2, "ML", "Recomendador baseline + evaluación", "Split temporal, MAP@12: popularidad vs recompra", "docs/evaluacion_recomendador.md", "make reco-eval", "", E, "", H, "MAP@12 0.00875 vs 0.02622 (+200%)"),
    ("P2-11", 2, "Datos", "Diccionario de datos", "Columnas, reglas y linaje Silver/Gold/ops/OLTP", "docs/diccionario_datos.md", "", "", N, "", H, ""),
    ("P2-12", 2, "BI", "Vistas para tableros", "Ventas mensuales, top artículos, recurrencia, salud streaming", "sql/gold/02_kpi_views.sql", "make bq-gold", "P2-05", G, N, L, ""),
    ("P2-13", 2, "BI", "Dashboard borrador", "Primer tablero Looker Studio sobre las vistas Gold", "Enlace Looker Studio", "", "P2-12", G, "", P, ""),
    ("P2-14", 2, "Gestión", "Informe Entrega 2", "Evidencias: conteos, reporte de calidad, capturas", "Word Entrega 2", "", "P2-02..P2-13", E, T, P, ""),

    ("P3-01", 3, "API", "API FastAPI", "Catálogo, recomendaciones, asistente, carrito, checkout, wallet, pedidos, métricas, OpenAPI /docs", "api/main.py", "make api-local", "", N, W, L, "Pruebas automáticas OK"),
    ("P3-02", 3, "API", "Wallet transaccional", "Ledger append-only, ACID, idempotencia, sin sobregiro, confirmación explícita", "api/schema.sql", "make test", "", N, "", L, "Test: doble clic = 1 cobro; 409 sin saldo"),
    ("P3-03", 3, "ML", "Asistente Vertex AI Gemini", "Gemini interpreta; backend busca en catálogo real; respaldo por reglas", "api/assistant.py", "ASSISTANT_MODE=gemini", "P2-01", E, N, L, "Reglas probadas con catálogo real; Gemini requiere GCP"),
    ("P3-04", 3, "ML", "Recomendaciones en API", "Perfil por grupo + popularidad; cold-start explícito", "api/main.py", "", "", E, "", L, ""),
    ("P3-05", 3, "API", "Web tienda", "Chat, productos con imagen, carrito, confirmación, saldo, pedidos", "api/static/index.html", "make api-local", "", N, G, L, ""),
    ("P3-06", 3, "Infra", "Cloud SQL + Cloud Run + secretos", "Terraform de base, servicio, secretos y acceso público", "infra/terraform/cloudsql.tf, cloudrun.tf", "make tf-apply", "P2-01", W, "", L, "tofu validate OK"),
    ("P3-07", 3, "Infra", "CI/CD sin llaves", "Workload Identity Federation + workflow de despliegue", "infra/terraform/cicd.tf, .github/workflows/deploy.yml", "Actions > deploy-api", "P1-18", W, "", L, ""),
    ("P3-08", 3, "Datos", "Catálogo Gold -> Cloud SQL", "Cargar v_catalog_serving con Cloud SQL Auth Proxy", "Tabla articles en Cloud SQL", "make catalog-gcp", "P2-09, P3-06", N, W, P, "Local: 105,542 artículos cargados"),
    ("P3-09", 3, "BI", "Dashboard gerencial", "Ventas, ticket medio, top, recurrencia, recomendador", "Looker Studio", "", "P2-12", G, E, P, ""),
    ("P3-10", 3, "BI", "Dashboard operativo y de costos", "Eventos/min, lag, DLQ, costo real y USD/pedido", "Looker Studio", "", "P2-08, P1-10", G, W, P, ""),
    ("P3-11", 3, "Resiliencia", "Prueba de recuperación", "Clonar Cloud SQL por PITR y restaurar objeto GCS; medir RTO", "docs/runbooks/drp.md", "", "P3-06", W, N, P, "Runbook listo"),
    ("P3-12", 3, "Costos", "Costo real vs estimado", "Billing export, vista de costo real, recalibrar supuestos", "cost/real_cost_per_order.sql", "", "P1-10", G, W, P, ""),
    ("P3-13", 3, "Gestión", "Guion de demo end-to-end", "Caso bebé: asistente -> carrito -> compra -> evento -> Gold -> tablero", "docs/demo_script.md", "", "", E, T, H, ""),
    ("P3-14", 3, "Gestión", "Slides (8 puntos del PDF)", "Resumen, situación, KPI, productos, supuestos, arquitectura, calculadora, demo, conclusiones", "docs/slides/", "", "P3-01..P3-12", G, T, P, ""),
    ("P3-15", 3, "Gestión", "Documento final y trazabilidad", "Word final con evidencias y matriz requisito -> evidencia", "docs/", "", "P3-14", E, T, P, ""),
    ("P3-16", 3, "Costos", "Apagado post-demo", "Detener Dataflow; destruir recursos demo", "Checklist", "make dataflow-stop tf-destroy", "P3-15", W, "", P, ""),
]

# Paso, #, acción, comando, responsable, variables, verificación
DESPLIEGUE = [
    (1, "D01", "Instalar herramientas", "gcloud, terraform >= 1.6, python 3.11, git (docker opcional)", W, "", "gcloud --version; terraform -version"),
    (1, "D02", "Crear proyecto y vincular facturación", "gcloud projects create $GCP_PROJECT_ID && gcloud billing projects link $GCP_PROJECT_ID --billing-account=$BILLING_ACCOUNT", W, "GCP_PROJECT_ID, BILLING_ACCOUNT", "Proyecto visible en consola con facturación"),
    (1, "D03", "Autenticarse", "gcloud auth login && gcloud auth application-default login", T, "", "gcloud config list"),
    (1, "D04", "Configurar variables", "cp .env.example .env; cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars; editar ambos", W, "Hoja Variables", "make -n tf-plan muestra el proyecto correcto"),
    (1, "D05", "Publicar repo", "git remote add origin https://github.com/OWNER/REPO.git && git push -u origin main", W, "github_repo", "Workflow ci en verde"),
    (2, "D06", "Habilitar APIs base y acceso privado", "make gcp-setup", W, "GCP_PROJECT_ID, GCP_REGION", "Subred default con Private Google Access"),
    (2, "D07", "Bucket de estado de Terraform", "make tf-bootstrap", W, "GCP_PROJECT_ID", "gs://$GCP_PROJECT_ID-tfstate versionado"),
    (2, "D08", "Inicializar y planificar", "make tf-init tf-plan", W, "terraform.tfvars", "Plan sin errores; revisar recursos y costos"),
    (2, "D09", "Aplicar infraestructura", "make tf-apply && terraform -chdir=infra/terraform output", W, "", "Buckets, datasets, Pub/Sub, Cloud SQL, Cloud Run creados"),
    (2, "D10", "Cargar Bronze", "make ingest-raw bq-bronze (luego make ingest-images)", N, "GCS_RAW_BUCKET", "COUNT(*) = 31,788,324 en retail_bronze.transactions"),
    (2, "D11", "Silver con Spark", "make silver-gcp bq-silver", N, "GCS_LAKE_BUCKET", "_quality_report con conciliado=true"),
    (2, "D12", "Gold y vistas BI", "make bq-gold", N, "PRICE_DEMO_FACTOR", "Tablas fact_/dim_ y vistas v_*"),
    (2, "D13", "Streaming de prueba", "make dataflow-start; make replay; make dataflow-stop", W, "PUBSUB_TOPIC", "Filas en retail_ops.stream_metrics_1m y retail_silver.v_events"),
    (3, "D14", "Variables de GitHub", "Settings > Secrets and variables > Actions > Variables", W, "GCP_PROJECT_ID, GCP_REGION, GCP_WIF_PROVIDER, GCP_DEPLOYER_SA", "Variables creadas"),
    (3, "D15", "Desplegar API/web", "Actions > deploy-api > Run workflow (o make deploy-api)", W, "", "Smoke test /health y /ready en verde"),
    (3, "D16", "Cargar catálogo a Cloud SQL", "cloud-sql-proxy $(terraform output -raw cloudsql_connection) & ; export DATABASE_URL=postgresql+pg8000://retail_app:CLAVE@127.0.0.1:5432/retail; make catalog-gcp", N, "DATABASE_URL", "/ready devuelve 105,542 artículos"),
    (3, "D17", "Recarga de saldo demo", "curl -X POST $API_URL/api/v1/wallet/demo-topups -H 'X-Admin-Token: '$(gcloud secrets versions access latest --secret=retail-admin-token) -H 'Content-Type: application/json' -d '{\"amount_cents\":20000}'", E, "API_URL", "Saldo visible en la web"),
    (3, "D18", "Tableros", "Looker Studio > Agregar datos > BigQuery > retail_gold.v_* y retail_ops.*", G, "", "Tablero gerencial y operativo"),
    (3, "D19", "Costos reales", "Consola: Facturación > Exportar a BigQuery (dataset retail_ops); ejecutar cost/real_cost_per_order.sql", W, "billing_account", "Vista v_costo_real_mensual con datos"),
    (3, "D20", "Apagado", "make dataflow-stop; make tf-destroy (o enable_cloudsql=false y api_min_instances=0)", W, "", "Facturación diaria ~0"),
]

# Variable, dónde, ejemplo, uso, quién
VARIABLES = [
    ("GCP_PROJECT_ID", ".env, GitHub (variable)", "retail-hm-utec-2026", "ID único del proyecto (6-30 caracteres)", W),
    ("GCP_REGION", ".env, GitHub (variable)", "us-central1", "Región única del prototipo", W),
    ("BILLING_ACCOUNT", "Shell (solo D02)", "012345-6789AB-CDEF01", "Vincular facturación", W),
    ("GCS_RAW_BUCKET", ".env", "retail-hm-utec-2026-retail-raw", "Bronze (= output raw_bucket)", W),
    ("GCS_LAKE_BUCKET", ".env", "retail-hm-utec-2026-retail-lake", "Silver/Gold Parquet y tmp de Dataflow (= output lake_bucket)", W),
    ("PUBSUB_TOPIC", ".env", "retail-events", "Tópico de eventos", W),
    ("LOCAL_RAW_DIR", ".env", "data/raw", "Datos H&M locales", N),
    ("DATABASE_URL", ".env (local) / secreto retail-db-url (nube)", "sqlite:///./data/retail_demo.db", "Base transaccional de la API", N),
    ("ADMIN_TOKEN", ".env (local) / secreto retail-admin-token (nube)", "cambia-este-token", "Autoriza recargas de saldo demo", N),
    ("ASSISTANT_MODE", ".env / tfvars assistant_mode", "gemini | rules", "Vertex AI o reglas", E),
    ("GEMINI_MODEL", ".env / tfvars gemini_model", "gemini-2.5-flash-lite", "Modelo del asistente", E),
    ("PRICE_DEMO_FACTOR", ".env / tfvars price_demo_factor", "500", "Precio demo = precio H&M x factor (sintético)", E),
    ("IMAGES_DIR / IMAGES_BUCKET", ".env / automático en Cloud Run", "data/raw/images", "Origen de imágenes", N),
    ("REPLAY_TARGET_START", ".env", "2026-11-01", "Fecha base de los eventos 2026", W),
    ("REPLAY_EVENTS_PER_SEC", ".env", "50", "Ritmo del replay", W),
    ("project_id", "terraform.tfvars", "retail-hm-utec-2026", "Igual a GCP_PROJECT_ID", W),
    ("region", "terraform.tfvars", "us-central1", "Igual a GCP_REGION", W),
    ("env", "terraform.tfvars", "dev", "Sufijo de recursos (dev/demo/prod)", W),
    ("billing_account", "terraform.tfvars", "012345-6789AB-CDEF01", "Crea presupuesto con alertas; vacío = no", W),
    ("monthly_budget_usd", "terraform.tfvars", "50", "Monto del presupuesto", G),
    ("enable_cloudsql", "terraform.tfvars", "true", "Base transaccional (USD 8-11/mes)", W),
    ("cloudsql_tier / cloudsql_ha", "terraform.tfvars", "db-f1-micro / false", "Tamaño y alta disponibilidad", W),
    ("cloudsql_deletion_protection", "terraform.tfvars", "false", "true en producción", W),
    ("enable_cloud_run / api_public", "terraform.tfvars", "true / true", "Servicio web/API y acceso público", W),
    ("api_min_instances / api_max_instances", "terraform.tfvars", "0 / 3", "Escalado (min=1 en la demo evita arranque en frío)", W),
    ("api_image", "terraform.tfvars", "(por defecto hello)", "Imagen inicial; luego la publica GitHub Actions", W),
    ("assistant_mode / gemini_model / price_demo_factor", "terraform.tfvars", "gemini / gemini-2.5-flash-lite / 500", "Configuración de la API en Cloud Run", E),
    ("github_repo", "terraform.tfvars", "OWNER/REPO", "Habilita WIF para desplegar desde GitHub", W),
    ("pubsub_topic", "terraform.tfvars", "retail-events", "Nombre del tópico", W),
    ("GCP_WIF_PROVIDER", "GitHub (variable)", "terraform output -raw wif_provider", "Autenticación sin llaves", W),
    ("GCP_DEPLOYER_SA", "GitHub (variable)", "terraform output -raw deployer_sa", "Cuenta que despliega", W),
    ("API_URL", "Shell", "terraform output -raw api_url", "URL pública de la tienda", W),
]

RECURSOS = [
    ("Bucket estado Terraform", "${project}-tfstate", "make tf-bootstrap"), ("Bucket Bronze", "${project}-retail-raw", "main.tf"),
    ("Bucket Silver/Gold", "${project}-retail-lake", "main.tf"), ("Datasets BigQuery", "retail_bronze, retail_silver, retail_gold, retail_ops", "main.tf"),
    ("Tópicos Pub/Sub", "retail-events, retail-events-dlq, billing-budget-alerts", "main.tf"),
    ("Suscripciones", "retail-events-to-bq, retail-events-dataflow", "main.tf"),
    ("Cuentas de servicio", "sa-retail-ingest, sa-retail-pipeline, sa-retail-api, sa-retail-deployer", "main.tf, cicd.tf"),
    ("Artifact Registry", "retail", "main.tf"), ("Cloud SQL", "retail-pg-${env} / base retail / usuario retail_app", "cloudsql.tf"),
    ("Secretos", "retail-db-url, retail-admin-token", "cloudsql.tf"), ("Cloud Run", "retail-api", "cloudrun.tf"),
    ("Workload Identity", "pool github-${env} / provider github-oidc", "cicd.tf"), ("Presupuesto", "retail-bigdata-${env}", "main.tf"),
    ("Job Dataflow", "retail-events", "make dataflow-start"), ("Tablas operativas", "retail_ops.stream_metrics_1m, retail_ops.stream_dlq", "Dataflow"),
]

FONT, BOLD = Font(name="Arial", size=10), Font(name="Arial", size=10, bold=True)
HDR, FILL = Font(name="Arial", size=10, bold=True, color="FFFFFF"), PatternFill("solid", fgColor="1F3864")
BRD = Border(*(Side(style="thin", color="BFBFBF"),) * 4)
WRAP = Alignment(wrap_text=True, vertical="top")
PASO_FILL = {1: "DDEBF7", 2: "E2EFDA", 3: "FCE4D6"}


def sheet(wb, title, cols, widths, rows, index=None):
    ws = wb.create_sheet(title, index) if wb.worksheets and wb.active.title != "Sheet" else wb.active
    ws.title = title
    for i, (c, w) in enumerate(zip(cols, widths), 1):
        cell = ws.cell(1, i, c)
        cell.font, cell.fill, cell.border = HDR, FILL, BRD
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        ws.column_dimensions[get_column_letter(i)].width = w
    for r, row in enumerate(rows, 2):
        for c, v in enumerate(row, 1):
            cell = ws.cell(r, c, v)
            cell.font, cell.border, cell.alignment = FONT, BRD, WRAP
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{len(rows) + 1}"
    return ws


def build_xlsx(out):
    wb = Workbook()
    rol = {p[0]: p[1] for p in PERFILES}
    orden = {}
    rows = []
    for t in TAREAS:
        tid, paso, fase, nom, acc, ent, cmd, dep, resp, apoyo, est, evid = t
        orden[paso] = orden.get(paso, 0) + 1
        rows.append([tid, paso, orden[paso], {1: F1, 2: F2, 3: F3}[paso], fase, nom, acc, ent, cmd, dep, resp, None, apoyo, est, None, evid])
    cols = ["ID", "Paso", "Orden", "Fecha límite", "Fase", "Nombre de la tarea", "Acción / tarea", "Entregable (ruta)", "Comando",
            "Depende de", "Responsable", "Perfil", "Apoyo", "Estado", "¿Hecho?", "Evidencia / observación"]
    ws = sheet(wb, "Matriz", cols, [7, 6, 6, 12, 11, 28, 46, 32, 28, 13, 16, 18, 15, 14, 8, 38], rows)
    last = len(rows) + 1
    for r in range(2, last + 1):
        ws.cell(r, 12, f'=IFERROR(INDEX(Perfiles!$B$2:$B$5,MATCH(K{r},Perfiles!$A$2:$A$5,0)),"")').font = FONT
        ws.cell(r, 15, f'=IF(N{r}="Hecho","Sí","No")').font = FONT
        paso = ws.cell(r, 2).value
        for c in (1, 2, 3):
            ws.cell(r, c).fill = PatternFill("solid", fgColor=PASO_FILL[paso])
    dv = DataValidation(type="list", formula1=f'"{H},{L},{P},En curso,Bloqueado"')
    ws.add_data_validation(dv)
    dv.add(f"N2:N{last}")
    for txt, color in [(H, "C6EFCE"), (L, "DDEBF7"), ("En curso", "FFEB9C"), (P, "F2F2F2"), ("Bloqueado", "FFC7CE")]:
        ws.conditional_formatting.add(f"N2:N{last}", CellIsRule(operator="equal", formula=[f'"{txt}"'], fill=PatternFill("solid", fgColor=color)))

    wp = sheet(wb, "Perfiles", ["Integrante", "Perfil", "Responsabilidad", "Tareas", "Hechas", "Listas p/desplegar", "Pendientes", "% hecho"],
               [18, 22, 60, 8, 8, 12, 10, 9], [list(p) for p in PERFILES])
    for r in range(2, 6):
        wp.cell(r, 4, f"=COUNTIF(Matriz!$K$2:$K${last},A{r})")
        for c, st in zip((5, 6, 7), (H, L, P)):
            wp.cell(r, c, f'=COUNTIFS(Matriz!$K$2:$K${last},$A{r},Matriz!$N$2:$N${last},"{st}")')
        wp.cell(r, 8, f"=IF(D{r}>0,E{r}/D{r},0)").number_format = "0%"
        for c in range(4, 9):
            wp.cell(r, c).font, wp.cell(r, c).border = FONT, BRD

    sheet(wb, "Despliegue", ["Paso", "#", "Acción", "Comando", "Responsable", "Variables", "Verificación"],
          [6, 6, 30, 70, 16, 30, 40], [list(d) for d in DESPLIEGUE])
    sheet(wb, "Variables", ["Variable", "Dónde se define", "Ejemplo", "Uso", "Quién"], [34, 34, 34, 46, 16], [list(v) for v in VARIABLES])
    sheet(wb, "Recursos GCP", ["Recurso", "Nombre", "Definido en"], [24, 60, 22], [list(x) for x in RECURSOS])

    wr = wb.create_sheet("Resumen", 0)
    for i, (c, w) in enumerate(zip(["Paso", "Entrega", "Fecha", "Tareas", "Hechas", "Listas p/desplegar", "Pendientes", "% hecho", "% código listo"],
                                   [7, 40, 13, 8, 8, 12, 10, 9, 12]), 1):
        cell = wr.cell(1, i, c)
        cell.font, cell.fill, cell.border = HDR, FILL, BRD
        cell.alignment = Alignment(wrap_text=True, horizontal="center")
        wr.column_dimensions[get_column_letter(i)].width = w
    ent = [(1, "Examen + P1: diseño, costos, ingesta/storage", F1), (2, "P2: pipelines batch + streaming, modelado", F2),
           (3, "P3: API, asistente, tableros, demo, sustentación", F3)]
    for r, (paso, nom, fecha) in enumerate(ent, 2):
        wr.cell(r, 1, paso); wr.cell(r, 2, nom); wr.cell(r, 3, fecha)
        wr.cell(r, 4, f"=COUNTIF(Matriz!$B$2:$B${last},A{r})")
        for c, st in zip((5, 6, 7), (H, L, P)):
            wr.cell(r, c, f'=COUNTIFS(Matriz!$B$2:$B${last},$A{r},Matriz!$N$2:$N${last},"{st}")')
        wr.cell(r, 8, f"=IF(D{r}>0,E{r}/D{r},0)")
        wr.cell(r, 9, f"=IF(D{r}>0,(E{r}+F{r})/D{r},0)")
    wr.cell(5, 2, "TOTAL")
    for c in range(4, 8):
        col = get_column_letter(c)
        wr.cell(5, c, f"=SUM({col}2:{col}4)")
    wr.cell(5, 8, "=IF(D5>0,E5/D5,0)"); wr.cell(5, 9, "=IF(D5>0,(E5+F5)/D5,0)")
    for r in range(2, 6):
        for c in range(1, 10):
            wr.cell(r, c).font, wr.cell(r, c).border = (BOLD if r == 5 else FONT), BRD
        wr.cell(r, 8).number_format = wr.cell(r, 9).number_format = "0%"
    notas = ["Leyenda",
             "Paso 1 = Entrega 1 (24-oct) · Paso 2 = Entrega 2 (07-nov) · Paso 3 = repositorio 20-nov y sustentación 21-nov.",
             "Hecho = terminado con evidencia. Listo para desplegar = código probado localmente; falta ejecutarlo en GCP.",
             "Estado se elige en la hoja Matriz (lista desplegable); '¿Hecho?', perfiles y resumen se recalculan solos.",
             "Hojas Despliegue, Variables y Recursos GCP: guía para Terraform. Detalle en docs/DEPLOY.md."]
    for i, t in enumerate(notas):
        wr.cell(8 + i, 1, t).font = BOLD if i == 0 else FONT
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)


def md_table(cols, rows):
    esc = lambda v: str(v).replace("|", "\\|")
    return "\n".join(["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] + ["| " + " | ".join(esc(v) for v in r) + " |" for r in rows])


def build_md(out):
    txt = ["# Despliegue en GCP con Terraform", "",
           "Orden de ejecución por paso. Todos los nombres de variables y recursos están fijados aquí y en `infra/terraform`.", "",
           "## Pasos", "", md_table(["Paso", "#", "Acción", "Comando", "Responsable", "Variables", "Verificación"], DESPLIEGUE), "",
           "## Variables", "", md_table(["Variable", "Dónde se define", "Ejemplo", "Uso", "Quién"], VARIABLES), "",
           "## Recursos que crea", "", md_table(["Recurso", "Nombre", "Definido en"], RECURSOS), "",
           "## Notas", "",
           "- `plan` antes de `apply`; la CI solo ejecuta `fmt` y `validate`, nunca `apply`.",
           "- Dataflow cobra mientras corre: encenderlo solo para la demo (`make dataflow-start` / `make dataflow-stop`).",
           "- El estado de Terraform vive en `gs://$GCP_PROJECT_ID-tfstate` (versionado); nunca en Git.",
           "- Vertex AI Gemini no es gratuito (~USD 0.0005 por conversación); `assistant_mode = \"rules\"` lo evita."]
    out.write_text("\n".join(txt) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build_xlsx(ROOT / "docs/gestion/Matriz_Auditoria_Proyecto.xlsx")
    build_md(ROOT / "docs/DEPLOY.md")
    print(len(TAREAS), "tareas,", len(DESPLIEGUE), "pasos de despliegue,", len(VARIABLES), "variables")

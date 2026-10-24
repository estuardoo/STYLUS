# Despliegue en GCP

Todos los inputs (parámetros, nombres, tablas, columnas, usuarios iniciales y permisos) están en `config/control_plataforma.json`. `python ops.py config` los valida y genera las variables de Terraform (`infra/terraform/plataforma.auto.tfvars.json`), la configuración de ops (`config/generated/plataforma.json`) y las semillas de la API (`api/seed.json`).

## Dónde ejecutar

| Paso | Dónde | Por qué |
|---|---|---|
| subir-datos, local | PC con `data/raw` | Los 3.9 GB de CSV (y 29 GB de imágenes) están ahí |
| todo lo demás | Google Cloud Shell (recomendado) o la PC | Cloud Shell ya trae gcloud, Terraform, Python y Docker y está autenticado |

## Pasos

| Paso | # | Acción | Comando | Responsable | Insumo del JSON | Verificación |
|---|---|---|---|---|---|---|
| 1 | D01 | Instalar herramientas | Google Cloud CLI, Terraform >= 1.6, Python 3.10-3.12, git (o usar Cloud Shell, que ya las trae) | Winston Quispe |  | gcloud --version; terraform -version |
| 1 | D02 | Crear proyecto y vincular facturación | gcloud projects create <project_id>; gcloud billing projects link <project_id> --billing-account=<cuenta> | Winston Quispe | Parametros: project_id, billing_account | Proyecto con facturación en consola |
| 1 | D03 | Completar el JSON de control | Editar con `python ops.py panel` (o a mano) los campos marcados editables de config/control_plataforma.json: mínimo project_id y emails del equipo | Todo el equipo | Parametros, Usuarios | python ops.py config sin errores |
| 1 | D04 | Autenticarse | gcloud auth login; gcloud auth application-default login (en Cloud Shell no hace falta) | Todo el equipo |  | gcloud config list |
| 1 | D05 | Instalar dependencias | pip install -r requirements.txt | Todo el equipo |  | python ops.py estado |
| 1 | D06 | Publicar repo | git remote add origin https://github.com/OWNER/REPO.git; git push -u origin main | Estuardo Oliver | Parametros: github_repo | Workflow ci en verde |
| 2 | D07 | Preparar proyecto | python ops.py bootstrap | Winston Quispe | APIs, Parametros: region, dataproc_subnet, bucket_tfstate_suffix | APIs activas, bucket de estado, terraform init |
| 2 | D08 | Revisar plan | python ops.py plan | Winston Quispe | Todas las hojas | Plan sin errores; recursos esperados |
| 2 | D09 | Crear infraestructura | python ops.py apply | Winston Quispe | Todas las hojas | Buckets, datasets, tablas, Pub/Sub, IAM, Cloud SQL, Cloud Run |
| 2 | D10 | Subir datos H&M (desde la PC con data/raw) | python ops.py subir-datos  (imágenes: --con-imagenes) | Nicole Arenas | Parametros: local_raw_dir, bucket_raw_suffix | gs://<bucket raw>/hm/*.csv |
| 2 | D11 | Bronze | python ops.py bronze | Nicole Arenas | Datasets, Tablas | 31,788,324 filas en bronze.transactions |
| 2 | D12 | Silver (Serverless Spark) | python ops.py silver | Nicole Arenas | Parametros: dataproc_runtime | _quality_report conciliado=true |
| 2 | D13 | Gold y vistas BI | python ops.py gold | Nicole Arenas | Parametros: price_demo_factor | Tablas fact_/dim_ y vistas v_* |
| 2 | D14 | Streaming de prueba | python ops.py dataflow-iniciar; python ops.py replay; python ops.py dataflow-detener | Winston Quispe | Parametros: dataflow_*, replay_* | Filas en ops.stream_metrics_1m y silver.v_events |
| 3 | D15 | API, web y catálogo | python ops.py api | Nicole Arenas | Parametros: cloudrun_*, assistant_mode, gemini_model; Usuarios (app) | URL pública; /ready con 105,542 artículos |
| 3 | D16 | Verificar contra el JSON de control | python ops.py verificar | Todo el equipo | Tablas, Columnas | Matriz tabla por tabla: OK / FALTA / DIFERENTE |
| 3 | D17 | Despliegue desde GitHub | python ops.py github -> crear variable GCP_WIF_PROVIDER -> Actions > deploy-api | Winston Quispe | Parametros: github_repo | Workflow deploy-api en verde |
| 3 | D18 | Tableros | Looker Studio > Agregar datos > BigQuery > gold.v_* y ops.* | Gianmarco Mejia | Tablas (vistas) | Tablero gerencial y operativo |
| 3 | D19 | Costos reales | Consola: exportar facturación a BigQuery (dataset ops) -> parámetro billing_export_table -> python ops.py costo-real | Estuardo Oliver | Parametros: billing_export_table | ops.v_costo_real_mensual con datos |
| 3 | D20 | Apagado | python ops.py dataflow-detener; python ops.py destroy | Winston Quispe | Parametros: force_destroy_buckets | Facturación diaria ~0 |

## Atajo

```bash
python ops.py config
python ops.py todo     # bootstrap, apply, bronze, silver, gold, api, verificar
```

Requiere haber subido antes los datos con `python ops.py subir-datos` desde la PC.

## Notas

- `plan` antes de `apply`; la CI solo ejecuta `config --check`, pruebas, `fmt` y `validate`, nunca `apply`.
- Dataflow cobra mientras corre: encenderlo solo para la demo.
- El estado de Terraform vive en `gs://<project_id>-tfstate/retail/<env>` (versionado); nunca en Git.
- Contraseñas y tokens no van en config/control_plataforma.json: Terraform los genera en Secret Manager.
- Vertex AI Gemini no es gratuito (~USD 0.0014 por conversación con 3.1 Flash-Lite); `assistant_mode = rules` lo evita.
- `roles/owner` no se puede otorgar por API: quien crea el proyecto ya lo tiene; al resto se les da roles desde la hoja Usuarios.

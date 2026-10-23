# Guion de demo end-to-end (sustentación, ~8 min)

Caso de negocio: "Necesito algo para mi bebé". Todo lo mostrado sale de datos reales de H&M; precio, stock y saldo son simulados.

| # | Paso | Dónde | Qué se ve / evidencia |
|---|---|---|---|
| 1 | Contexto y arquitectura (30 s) | Slide 6 | Fuentes → ingesta → medallion → cómputo → exposición |
| 2 | Datos en Bronze/Silver | Consola BigQuery | `retail_silver.transactions` 31.8M filas; reporte de calidad conciliado |
| 3 | Streaming en vivo | Terminal: `python ops.py dataflow-iniciar` y `python ops.py replay` | Mensajes en Pub/Sub; filas nuevas en `retail_ops.stream_metrics_1m`, lag p95 |
| 4 | Asistente | Web (URL de Cloud Run) | Escribir "necesito algo para mi bebé": Gemini interpreta, catálogo real Baby/Children |
| 5 | Carrito y confirmación | Web | Agregar sugeridos; sin marcar "Confirmo" la compra se rechaza |
| 6 | Compra con saldo demo | Web | Saldo baja; doble clic no cobra dos veces (idempotencia) |
| 7 | La compra llega a analítica | BigQuery | Evento `web_demo` en `retail_silver.v_events` y en `fact_sales` tras `python ops.py gold` |
| 8 | Tableros | Looker Studio | Gerencial (ventas, ticket, top) y operativo (eventos/min, DLQ, costo/pedido) |
| 9 | Recomendador | `docs/evaluacion_recomendador.md` | MAP@12: popularidad 0.00875 vs recompra+popularidad 0.02622 (+200%) |
| 10 | Costos y cierre | Calculadora + `python ops.py dataflow-detener` | USD/pedido estimado vs real; apagado de recursos |

Preparación (día anterior): `python ops.py plan` / `apply` / `api` (incluye catálogo en Cloud SQL), recarga demo de saldo, workflow `deploy-api` en verde, abrir pestañas.
Plan B si falla la red o Vertex AI: `assistant_mode = rules` en el Excel y `python ops.py local` con el catálogo local.

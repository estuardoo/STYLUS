# Evaluación del recomendador (datos reales H&M)

Split temporal: entrenamiento hasta 2020-09-16 (exclusivo); test 2020-09-16 a 2020-09-22. Métrica MAP@12.

| Modelo | MAP@12 |
|---|---:|
| A. Popularidad última semana | 0.00875 |
| B. Recompra (8 semanas) + popularidad | 0.02622 |

Uplift B vs A: +199.7%. Clientes evaluados: 68,984; sin historial (cold-start, reciben A): 26,447.

Generado por `pipelines/reco/baseline_eval.py`. B es el modelo batch para clientes H&M con historial; la API de la tienda demo usa popularidad por grupo (perfil del historial) y popularidad global para cold-start.
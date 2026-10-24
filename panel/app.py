"""Panel de control local: edita config/control_plataforma.json y ejecuta ops.py desde el navegador.
Uso: python panel/app.py   (o python ops.py panel)   -> http://127.0.0.1:8765
Solo escucha en 127.0.0.1: no lo expongas a la red. No sustituye revisar `python ops.py plan` antes de aplicar.
"""
import datetime as dt
import json
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
CONFIG_JSON = ROOT / "config/control_plataforma.json"

app = FastAPI(title="Panel STYLUS")
JOBS: dict[str, dict] = {}  # id -> {lines: [], done: bool, comando, codigo}

# Secciones del JSON de control que se muestran como tabla editable en el panel.
# (clave en el JSON, etiqueta, columnas a mostrar en ese orden, ¿se puede agregar/quitar fila?)
SECCIONES = [
    ("usuarios", "Usuarios (equipo + tienda)", ["tipo", "id", "nombre", "email", "perfil", "roles_gcp", "saldo_inicial_cents"], True),
    ("permisos", "Permisos IAM", ["principal", "rol", "alcance", "motivo", "gestion"], True),
    ("cuentas_servicio", "Cuentas de servicio", ["clave", "account_id", "nombre", "descripcion"], True),
    ("datasets", "Datasets BigQuery", ["clave", "dataset_id", "descripcion", "borrar_contenido_en_destroy"], False),
    ("apis", "APIs de GCP a activar", None, True),
    ("secretos", "Secretos (solo nombres; el valor lo crea Terraform)", None, False),
    ("tablas", "Tablas (contrato con SQL/Spark; cambiar el nombre aquí no cambia el SQL)", None, False),
    ("columnas", "Columnas (contrato con SQL/Spark)", None, False),
]

# Comandos del orquestador expuestos en el panel: (clave, etiqueta, flags, peligroso)
COMANDOS = [
    ("config", "Validar / generar configuración", [], False),
    ("estado", "Ver estado", [], False),
    ("bootstrap", "1. Preparar proyecto (APIs, red, estado)", [], False),
    ("plan", "2. Revisar plan de Terraform", [], False),
    ("apply", "3. Crear infraestructura", ["--yes"], True),
    ("subir-datos", "4. Subir datos H&M a GCS", [], False),
    ("bronze", "5. Cargar Bronze", [], False),
    ("silver", "6. Procesar Silver (Spark)", [], False),
    ("gold", "7. Calcular Gold y vistas BI", [], False),
    ("api", "8. Desplegar API + catálogo", [], False),
    ("verificar", "9. Verificar BigQuery vs Excel", [], False),
    ("github", "Configurar variable de GitHub Actions", [], False),
    ("costo-real", "Ver costo real por pedido", [], False),
    ("destroy", "Destruir infraestructura", ["--yes"], True),
]


def leer_config():
    return json.loads(CONFIG_JSON.read_text(encoding="utf-8"))


def guardar_config(data):
    CONFIG_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


class CambiosParametros(BaseModel):
    valores: dict  # {clave: valor_nuevo}


class CambiosSeccion(BaseModel):
    filas: list  # reemplaza por completo la sección (editar/agregar/quitar filas desde la tabla)


@app.get("/", response_class=HTMLResponse)
def index():
    return (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/comandos")
def comandos():
    return [{"comando": c, "etiqueta": e, "peligroso": d} for c, e, _, d in COMANDOS]


@app.get("/api/secciones")
def secciones():
    return [{"clave": c, "etiqueta": e, "editable": ed} for c, e, _, ed in SECCIONES]


@app.get("/api/parametros")
def parametros():
    try:
        data = leer_config()
        return {"ok": True, "items": data["parametros"]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/parametros")
def guardar_parametros(cambios: CambiosParametros):
    try:
        data = leer_config()
        by_clave = {p["clave"]: p for p in data["parametros"]}
        rechazados = [k for k in cambios.valores if k not in by_clave or not by_clave[k].get("editable", True)]
        for clave, valor in cambios.valores.items():
            if clave not in rechazados:
                by_clave[clave]["valor"] = valor
        guardar_config(data)
        return {"ok": True, "rechazados": rechazados}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/seccion/{clave}")
def seccion_get(clave: str):
    cfg = {c: (c, e, cols, ed) for c, e, cols, ed in SECCIONES}.get(clave)
    if not cfg:
        return {"ok": False, "error": "sección desconocida"}
    try:
        data = leer_config()
        filas = data.get(clave, [])
        columnas = cfg[2] or (list(filas[0].keys()) if filas else [])
        return {"ok": True, "filas": filas, "columnas": columnas, "editable": cfg[3]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/seccion/{clave}")
def seccion_set(clave: str, cambios: CambiosSeccion):
    cfg = {c: (c, e, cols, ed) for c, e, cols, ed in SECCIONES}.get(clave)
    if not cfg or not cfg[3]:
        return {"ok": False, "error": "sección no editable desde el panel"}
    try:
        data = leer_config()
        data[clave] = cambios.filas
        guardar_config(data)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _run_job(job_id, comando, flags):
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "ops.py"), comando, *flags],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )
    for line in proc.stdout:
        JOBS[job_id]["lines"].append(line.rstrip())
    proc.wait()
    JOBS[job_id]["done"] = True
    JOBS[job_id]["codigo"] = proc.returncode


@app.post("/api/ejecutar/{comando}")
def ejecutar(comando: str):
    cfg = {c: (c, e, f, d) for c, e, f, d in COMANDOS}.get(comando)
    if not cfg:
        return {"ok": False, "error": "comando desconocido"}
    _, _, flags, _ = cfg
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {"lines": [], "done": False, "comando": comando, "inicio": dt.datetime.now().isoformat()}
    threading.Thread(target=_run_job, args=(job_id, comando, flags), daemon=True).start()
    return {"ok": True, "job_id": job_id}


@app.get("/api/log/{job_id}")
def log_stream(job_id: str):
    def gen():
        enviado = 0
        while True:
            job = JOBS.get(job_id)
            if job is None:
                yield "data: " + json.dumps({"error": "job no encontrado"}) + "\n\n"
                return
            nuevas = job["lines"][enviado:]
            enviado += len(nuevas)
            for linea in nuevas:
                yield "data: " + json.dumps({"linea": linea}) + "\n\n"
            if job["done"] and enviado >= len(job["lines"]):
                yield "data: " + json.dumps({"fin": True, "codigo": job.get("codigo", 0)}) + "\n\n"
                return
            time.sleep(0.5)
    return StreamingResponse(gen(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    print("Panel de control: http://127.0.0.1:8765  (Ctrl+C para detener)")
    uvicorn.run(app, host="127.0.0.1", port=8765)

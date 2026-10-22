"""Asistente de compras. Gemini (Vertex AI) solo interpreta la intención; el backend busca en el
catálogo real y arma el carrito propuesto. Nunca compra: siempre requiere confirmación del usuario.
ASSISTANT_MODE=gemini usa Vertex AI; cualquier otro valor (o un error de Gemini) usa reglas."""
import json
import os
import unicodedata

GRUPOS = ["Ladieswear", "Baby/Children", "Divided", "Menswear", "Sport"]

# Palabras clave en español -> filtros del catálogo H&M
REGLAS = [
    (("bebe", "recien nacido", "baby"), {"grupo": "Baby/Children", "seccion": "Baby"}),
    (("nino", "nina", "ninos", "ninas", "infantil", "kids"), {"grupo": "Baby/Children"}),
    (("hombre", "caballero", "papa"), {"grupo": "Menswear"}),
    (("mujer", "dama", "mama"), {"grupo": "Ladieswear"}),
    (("deporte", "gym", "correr", "sport"), {"grupo": "Sport"}),
]
TIPOS = {  # prefijos de product_type_name de H&M
    "pijama": ["Pyjama"], "body": ["Bodysuit", "Underwear body"], "medias": ["Socks"], "calcetines": ["Socks"],
    "polo": ["T-shirt", "Polo shirt"], "camiseta": ["T-shirt", "Top"], "vestido": ["Dress"], "pantalon": ["Trousers"],
    "short": ["Shorts"], "zapatos": ["Sneakers", "Sandals", "Boots", "Ballerinas", "Pre-walkers", "Flat shoe"],
    "zapatillas": ["Sneakers"], "chompa": ["Sweater", "Cardigan"], "sueter": ["Sweater"], "casaca": ["Jacket", "Coat"],
    "chaqueta": ["Jacket"], "gorro": ["Hat", "Beanie"], "falda": ["Skirt"], "camisa": ["Shirt", "Blouse"],
    "leggings": ["Leggings"], "enterizo": ["Jumpsuit", "Dungarees"], "manta": ["Blanket"], "babero": ["Baby Bib"],
    "juguete": ["Toy", "Soft Toys"], "saco de dormir": ["Sleeping sack", "Sleep Bag"], "bano": ["Swim"],
}


def _norm(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def intent_reglas(msg):
    m = _norm(msg)
    intent = {"grupo": "", "seccion": "", "tipos": [], "palabras": [], "presupuesto_max": None,
              "respuesta_breve": "Encontré estas opciones en el catálogo:"}
    for claves, filtro in REGLAS:
        if any(k in m.split() or k in m for k in claves):
            intent.update(filtro)
            break
    intent["tipos"] = sorted({v for k, vs in TIPOS.items() if k in m for v in vs})
    nums = [int(t) for t in m.replace("$", " ").split() if t.isdigit()]
    if nums and any(w in m for w in ("menos", "maximo", "hasta", "presupuesto")):
        intent["presupuesto_max"] = max(nums) * 100
    return intent


def intent_gemini(msg, tipos_validos):
    from google import genai  # import diferido: solo en modo gemini
    from google.genai import types

    client = genai.Client(vertexai=True, project=os.environ["GCP_PROJECT_ID"],
                          location=os.getenv("GEMINI_LOCATION", os.getenv("GCP_REGION", "us-central1")))
    schema = {
        "type": "OBJECT",
        "properties": {
            "grupo": {"type": "STRING", "enum": GRUPOS + [""]},
            "seccion": {"type": "STRING", "description": "texto contenido en la sección, ej. 'Baby'"},
            "tipos": {"type": "ARRAY", "items": {"type": "STRING", "enum": tipos_validos}},
            "palabras": {"type": "ARRAY", "items": {"type": "STRING"}},
            "presupuesto_max": {"type": "INTEGER", "nullable": True, "description": "en centavos"},
            "respuesta_breve": {"type": "STRING"},
        },
        "required": ["grupo", "tipos", "respuesta_breve"],
    }
    prompt = ("Eres el asistente de una tienda de moda. Traduce el pedido del cliente a filtros de catálogo. "
              "No inventes productos ni precios. respuesta_breve: una frase amable en español.\n"
              f"Pedido: {msg}")
    r = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"), contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema,
                                           temperature=0, max_output_tokens=400))
    out = json.loads(r.text)
    out.setdefault("seccion", "")
    out.setdefault("palabras", [])
    out.setdefault("presupuesto_max", None)
    return out


def reply(msg, search, tipos_validos, k=6):
    """search(intent, k) -> lista de productos del catálogo real."""
    modo = "reglas"
    intent = intent_reglas(msg)
    if os.getenv("ASSISTANT_MODE", "rules") == "gemini":
        try:
            intent, modo = intent_gemini(msg, tipos_validos), "gemini"
        except Exception as e:  # cuota, red o credenciales: degradación controlada
            modo = f"reglas (Gemini no disponible: {type(e).__name__})"
    productos = search(intent, k)
    if not productos and intent.get("tipos"):  # relajar filtros antes de rendirse
        productos = search({**intent, "tipos": [], "palabras": []}, k)
    carrito = [{"article_id": p["article_id"], "qty": 1} for p in productos[:3]]
    texto = intent["respuesta_breve"] if productos else "No encontré artículos para ese pedido en el catálogo."
    return {
        "respuesta": texto, "productos": productos, "carrito_propuesto": carrito,
        "requiere_confirmacion": True, "modo": modo, "filtros": intent,
        "aviso": "Demostración: los precios y el saldo son simulados; no se cobra dinero real.",
    }

"""Calcula la página de cada título del índice a partir del PDF (segunda pasada de build_guia.js)."""
import json
import sys
from pypdf import PdfReader

toc = json.load(open(sys.argv[1], encoding="utf-8"))
pages = [p.extract_text() or "" for p in PdfReader(sys.argv[2]).pages]
out, desde = {}, 0
for _, t in toc:
    for i in range(desde, len(pages)):
        if any(l.strip() == t for l in pages[i].splitlines()):
            out[t], desde = i + 1, i
            break
json.dump(out, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False)
print(f"{len(out)}/{len(toc)} títulos ubicados; faltan:", [t for _, t in toc if t not in out])

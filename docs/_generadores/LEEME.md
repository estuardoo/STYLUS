# Generadores de entregables

Regeneran el Word y la matriz a partir de los datos del repo (requiere Node con `docx`, LibreOffice y poppler).

```bash
python cost/estimate_costs.py                                   # cost/output/resumen.json (lo usa el Word)
python docs/_generadores/build_matriz.py docs/gestion/Matriz_Auditoria_Proyecto.xlsx
node docs/_generadores/build_word.js . docs/entrega1/Entrega1_Arquitectura_BigData_Retail.docx
soffice --headless --convert-to pdf --outdir /tmp docs/entrega1/Entrega1_Arquitectura_BigData_Retail.docx
python docs/_generadores/toc_pages.py /tmp/Entrega1_Arquitectura_BigData_Retail.pdf docs/entrega1/Entrega1_Arquitectura_BigData_Retail.docx.toc.json /tmp/pages.json
node docs/_generadores/build_word.js . docs/entrega1/Entrega1_Arquitectura_BigData_Retail.docx /tmp/pages.json
python docs/_generadores/toc_embed.py docs/entrega1/Entrega1_Arquitectura_BigData_Retail.docx
```
Nota: la matriz se edita a mano durante el proyecto; regenerarla sobrescribe los estados.

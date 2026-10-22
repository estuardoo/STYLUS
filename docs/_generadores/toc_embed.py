"""Mueve el índice estático (calculado del render) dentro del campo TOC de Word.
Word lo muestra tal cual y lo recalcula al abrir (updateFields)."""
import re, sys, zipfile, shutil
src = sys.argv[1]
tmp = src + ".tmp"
with zipfile.ZipFile(src) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename == "word/document.xml":
            x = data.decode("utf-8")
            end_p = '<w:p><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p></w:sdtContent></w:sdt>'
            m = re.search(re.escape(end_p) + r'(.*?)(<w:p>(?:(?!</w:p>).)*?<w:br w:type="page"/>)', x, re.S)
            assert m, "estructura TOC no encontrada"
            x = x[:m.start()] + m.group(1) + end_p + x[m.start(2):]
            data = x.encode("utf-8")
        zout.writestr(item, data)
shutil.move(tmp, src)
print("toc embebido")

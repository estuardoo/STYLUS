import json,subprocess,sys,re
pdf,toc,out=sys.argv[1:4]
heads=json.load(open(toc)); n=int(re.search(r"Pages:\s+(\d+)",subprocess.run(["pdfinfo",pdf],capture_output=True,text=True).stdout).group(1))
pages={}
txt=[subprocess.run(["pdftotext","-f",str(i),"-l",str(i),"-layout",pdf,"-"],capture_output=True,text=True).stdout for i in range(1,n+1)]
for _,h in heads:
    for i,t in enumerate(txt[3:],4):  # tras el índice
        if any(l.strip().startswith(h) for l in t.splitlines()): pages[h]=i; break
missing=[h for _,h in heads if h not in pages]
print("faltan:",missing); json.dump(pages,open(out,"w"),ensure_ascii=False)

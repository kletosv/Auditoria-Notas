"""Leitor estrito do Edital 58/SED/2025, DOE 11.960.
Não extrapolar resultados para outros editais nem afirmar vigência.
"""
import re
from pathlib import Path
import fitz

COLS=['doc','arquivo','doe','edital','matricula','servidor','trienio','ano1','ano2','ano3',
      'antes1','antes2','antes3','media_antes','depois1','depois2','depois3',
      'media_depois','campos_alterados','pagina_pdf','pagina_doe','origem','situacao']

VAL=re.compile(r'^(?:\d{1,3},\d{2}|C\d{3})$')
MAT=re.compile(r'^\d{7,11}$')

def parse_rows(txt):
    lines=[x.strip() for x in txt.splitlines() if x.strip()]
    rows={}
    for i, token in enumerate(lines):
        if not MAT.fullmatch(token):
            continue
        # Nome aparece depois da matrícula; exatamente quatro valores do triênio.
        if i+5>=len(lines): continue
        name=lines[i+1]
        vals=lines[i+2:i+6]
        if not name or MAT.fullmatch(name) or not all(VAL.fullmatch(v) for v in vals):
            continue
        rows[token]=(name,vals)
    return rows

def extrair_medias(pdf_path, doc_id=''):
    path=Path(pdf_path)
    with fitz.open(path) as pdf:
        pages=[p.get_text('text') for p in pdf]
    full='\n'.join(pages)
    marker=re.search(r'EDITAL\s+N\.?\s*58/SED/2025\b',full,re.I)
    if not marker or not re.search(r'11[.\s]*960',full[:500]):
        return []
    end=re.search(r'(?m)^\s*EDITAL\s+N\.?\s*\d+/SED/2025\b',full[marker.end():],re.I)
    block=full[marker.start():marker.end()+end.start()] if end else full[marker.start():]
    a=re.search(r'Onde\s+consta\s*:',block,re.I)
    b=re.search(r'Passe\s+a\s+constar\s*:',block,re.I)
    if not (a and b and a.end()<b.start()): return []
    old=parse_rows(block[a.end():b.start()])
    new=parse_rows(block[b.end():])
    startpage=next((i+1 for i,t in enumerate(pages) if 'EDITAL N. 58/SED/2025' in t),0)
    results=[]
    for mat in sorted(set(old)&set(new)):
        oname,ov=old[mat]; nname,nv=new[mat]
        changed=[f'NOTA {y}' for y,x,z in zip((2021,2022,2023),ov[:3],nv[:3]) if x!=z]
        if ov[3]!=nv[3]:changed.append('MÉDIA')
        if oname!=nname:changed.append('NOME')
        results.append(dict(zip(COLS,[doc_id,path.name,'11.960','58/SED/2025',mat,nname,
            '2021–2023','2021','2022','2023',*ov,*nv,', '.join(changed) or 'SEM MUDANÇA IDENTIFICADA',
            startpage,'179–181','DOE 11.872 Suplemento II, Edital 26/SED/2025',
            'RETIFICAÇÃO COMPROVADA NO ATO; PUBLICAÇÕES POSTERIORES NÃO VERIFICADAS'])) )
    return results

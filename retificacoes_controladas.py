"""Varredura conservadora de pares 'Onde consta' / 'Passe a constar'.
Detecta candidatos em todos os PDFs processados; não confirma vigência jurídica.
Apenas emite par quando matrícula aparece com valor nos dois lados do mesmo bloco.
"""
import hashlib, re
from pathlib import Path
from datetime import datetime
import fitz

COLUNAS = ['doc','arquivo','doe','data_publicacao','edital','pagina_pdf','pagina_impressa',
           'matricula','nome_antes','nome_depois','exercicio','nota_antes','nota_depois',
           'alterou_nota','campo_alterado','situacao','evidencia']


def _linhas(t):
    partes = re.split(r'(?m)^\s*(\d{7,11})\s*$', t)
    saida = {}
    for j in range(1, len(partes), 2):
        mat = partes[j].strip(); bloco = partes[j+1]
        nota = re.search(r'(?m)^\s*(\d{1,3}[,.]\d{2}|C\d{3})\s*$', bloco)
        if not nota: continue
        nome = ' '.join(x.strip() for x in bloco[:nota.start()].splitlines() if x.strip())
        if nome: saida[mat] = (nome, nota.group(1).replace('.', ','))
    return saida


def _metadata(path, joined):
    name=Path(path).name
    m=re.search(r'DO(\d{5})',name,re.I); doe=m.group(1) if m else ''
    d=re.search(r'DO\d{5}[_ -](\d{2})[_ -](\d{2})[_ -](\d{4})',name,re.I)
    date=f'{d.group(1)}/{d.group(2)}/{d.group(3)}' if d else ''
    acts=list(re.finditer(r'(?i)\b(?:EDITAL|RETIFICA[CÇ][ÃA]O|RESOLU[CÇ][ÃA]O|PORTARIA)\s*(?:N[.º°]?\s*)?[\w./-]+',joined))
    return doe,date,acts


def extrair_retificacoes(pdf_path):
    path=Path(pdf_path)
    try:
        with fitz.open(path) as doc: texts=[p.get_text('text') for p in doc]
    except Exception:
        return []
    joined='\n'.join(texts)
    if not re.search(r'(?i)\b(?:ONDE\s+CONSTA|PASSE\s+A\s+CONSTAR)\b',joined): return []
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    doe,date,acts=_metadata(path,joined)
    # Procura cada par no mesmo trecho documental; limita no próximo par/ato, evitando cruzar editais.
    markers=list(re.finditer(r'(?i)\b(?:ONDE\s+CONSTA|PASSE\s+A\s+CONSTAR)\s*:',joined))
    out=[]; seen=set()
    for i,m in enumerate(markers):
        if not re.search(r'(?i)ONDE\s+CONSTA',m.group()): continue
        nxt=next((x for x in markers[i+1:] if re.search(r'(?i)PASSE\s+A\s+CONSTAR',x.group())),None)
        if not nxt: continue
        # Reject if a new act header occurs between the two labels.
        between=joined[m.end():nxt.start()]
        if re.search(r'(?im)^\s*(?:EDITAL|PORTARIA|RESOLU[CÇ][ÃA]O)\s+N[.º°]',between): continue
        end=next((x.start() for x in markers[i+1:] if x.start()>nxt.end()),len(joined))
        after=joined[nxt.end():end]
        before=_linhas(between); new=_linhas(after)
        if not before or not new: continue
        # infer nearby act label and exercise only when explicit; never guess from value
        prefix=joined[max(0,m.start()-1200):m.start()]
        actmatches=list(re.finditer(r'(?i)\bEDITAL\s+N[.º°]?\s*[\w./-]+',prefix))
        edital=actmatches[-1].group(0).strip() if actmatches else 'ATO NÃO IDENTIFICADO'
        yrm=re.search(r'(?i)(?:exerc[ií]cio|ciclo avaliativo|nota)\s*(?:de|do|da)?\s*(20(?:19|2[0-6]))',joined[max(0,m.start()-350):m.start()]+' '+between)
        year=yrm.group(1) if yrm else 'INDETERMINADO'
        page_idx=next((j+1 for j,t in enumerate(texts) if m.group() in t),0)
        for mat in sorted(set(before)&set(new)):
            old,newv=before[mat],new[mat]
            fields=[]
            if old[0]!=newv[0]: fields.append('NOME')
            if old[1]!=newv[1]: fields.append('NOTA/CÓDIGO')
            key=(mat,edital,old,newv,page_idx)
            if key in seen: continue
            seen.add(key)
            out.append(dict(zip(COLUNAS,[digest,path.name,doe,date,edital,page_idx,'NÃO EXTRAÍDA',mat,
                old[0],newv[0],year,old[1],newv[1],'SIM' if old[1]!=newv[1] else 'NÃO',
                ', '.join(fields) if fields else 'SEM ALTERAÇÃO IDENTIFICADA',
                'CANDIDATA — PAR IDENTIFICADO; VIGÊNCIA E ATO POSTERIOR NÃO CONFIRMADOS',
                f'{path.name}, página PDF {page_idx}; par textual Onde consta/Passe a constar. Conferir cabeçalho, tabela e página impressa.'])))
    return out

# Compatibilidade com versões anteriores e testes já existentes.
def extrair_edital_44(pdf_path):
    return [r for r in extrair_retificacoes(pdf_path) if r.get('doe')=='11575' and '44/2024' in r.get('edital','')]

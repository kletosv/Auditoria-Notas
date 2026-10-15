"""Extração conservadora de despachos TORNAR SEM EFEITO com objeto e linha identificados.
A comprovação é do conteúdo do despacho, NÃO da vigência final nem de atos posteriores.
"""
import re
from pathlib import Path
import fitz

COLS=['doc','arquivo','doe','pagina_pdf','pagina_doe','matricula','servidor','cargo','ato_anterior','doe_anterior','periodo_declarado','cabecalho_periodo','valores','objeto','escopo','situacao','evidencia']


def extrair_cancelamentos(path,doc_id='',doe=''):
    path=Path(path)
    output=[]
    with fitz.open(path) as pdf:
        for page_idx,page in enumerate(pdf):
            text=page.get_text('text',sort=True)
            # O despacho deve conter a frase explícita, não só palavras soltas no entorno.
            if 'TORNAR SEM EFEITO' not in text.upper(): continue
            segments=re.split(r'(?im)^\s*DESPACHO DO PRESIDENTE DA CRADI/SED\s*$',text)
            for seg in segments:
                m=re.search(r'TORNAR\s+SEM\s+EFEITO\s+o\s+(ANEXO\s+ÚNICO\s+DO\s+)?EDITAL\s+N\.?\s*(\d+/(?:SED/)?20\d{2})',seg,re.I)
                if not m: continue
                original=re.search(r'(?:Diário Oficial\s+Eletrônico\s+n\.?\s*)(1[012][.\s]?\d{3})(\s*-\s*Suplemento)?',seg,re.I)
                declared=re.search(r'referente\s+ao[s]?\s+ciclo[s]?\s+avaliativo[s]?\s+de\s+([\d,\s e]+)\.',seg,re.I)
                header=re.search(r'Nota\s+(20\d{2})',seg,re.I)
                scope=re.search(r'na\s+parte\s+que\s+publicou\s+(a[s]?\s+nota[s]?\s+da\s+servidora)',seg,re.I)
                if not (original and scope): continue
                periodo=' '.join(declared.group(1).split()) if declared else ''
                # Apenas linhas com matrícula no início e Professor/cargo explícito.
                for line in seg.splitlines():
                    row=re.match(r'^\s*(\d{7,11})\s+(.+?)\s{2,}(Professor|Administrativo|Especialista|Técnico|Tecnico)\s+(.+?)\s*$',line,re.I)
                    if not row: continue
                    mat,nome,cargo,tail=row.groups()
                    values=re.findall(r'(?<!\w)(?:\d{1,3},\d{2}|C\d{3})(?!\w)',tail)
                    if not values: continue
                    old_doe=re.sub(r'\D','',original.group(1))
                    if original.group(2):old_doe+=' - Suplemento'
                    conflict=bool(periodo and header and header.group(1) not in re.findall(r'20\d{2}',periodo))
                    status='PENDENTE DE AVALIAÇÃO DOCUMENTAL — DIVERGÊNCIA DE EXERCÍCIO' if conflict else 'OBJETO DO DESPACHO IDENTIFICADO — POSTERIORES PENDENTES'
                    evidence=' '.join(seg[m.start():].split())[:850]
                    output.append(dict(zip(COLS,[doc_id,path.name,str(doe),page_idx+1,str(page_idx+1),mat,nome.strip(),cargo,m.group(0).replace('TORNAR SEM EFEITO o ','').strip(),old_doe,periodo,header.group(1) if header else '', ' | '.join(values),'NOTA PUBLICADA EM PARTE DO EDITAL','PARTE DO EDITAL QUE PUBLICOU A(S) NOTA(S) DA SERVIDORA',status,evidence])))
    return list({(x['doc'],x['pagina_pdf'],x['matricula'],x['ato_anterior']):x for x in output}.values())

"""Histórico conservador por matrícula e exercício (2019–2024).

Não equipara extração de candidato a ato confirmado. Não presume que uma
publicação mais recente substitui outra nem que média de triênio é nota anual.
"""
import hashlib
import re
import pandas as pd

YEARS = tuple(str(y) for y in range(2019, 2025))
EVENT_COLS = [
    'ID do evento','Matrícula','Servidor','Exercício','DOE','Arquivo','Página',
    'Tipo de ocorrência','Natureza do valor','Campo afetado','Nota na Base Geral',
    'Nota publicada (extração)','Código publicado (extração)',
    'Onde consta (texto do ato)','Passe a constar (texto do ato)',
    'Valor revogado (comprovado)','Valor tornado sem efeito (comprovado)',
    'Ato anterior relacionado','Ato posterior relacionado','Situação da cadeia',
    'Estado documental','Trecho da publicação','Contexto do ato'
]
SUMMARY_COLS = [
    'Matrícula','Servidor','Exercício','Nota na Base Geral',
    'Notas anuais publicadas (candidatas)','Códigos publicados (candidatos)',
    'Valores anteriores identificados','Valores posteriores identificados',
    'Valores revogados (comprovados)','Valores tornados sem efeito (comprovados)',
    'Nota documental vigente (confirmada)','Total de eventos','Primeiro DOE localizado',
    'Último DOE localizado','Cobertura posterior','Situação da vigência',
    'IDs dos eventos','Referências DOE/página'
]

def s(x):
    return '' if x is None or pd.isna(x) else str(x).strip()

def unique(vals, limit=3000):
    return ' | '.join(dict.fromkeys(s(v) for v in vals if s(v)))[:limit]

def get_pairs(t):
    """Extrai apenas expressão literal; não atribui o texto ao campo sem prova."""
    t = re.sub(r'\s+', ' ', s(t))
    a = re.search(r'\bONDE\s+CONSTA\s*[:\-]?\s*(.{1,180}?)(?=\bPASSE\s+A\s+CONSTAR\b|$)',t,re.I)
    b = re.search(r'\bPASSE\s+A\s+CONSTAR\s*[:\-]?\s*(.{1,180}?)(?=\bONDE\s+CONSTA\b|$)',t,re.I)
    return (s(a.group(1)) if a else '', s(b.group(1)) if b else '')

def field_hint(text):
    t=s(text)
    found=[]
    for field,pattern in [
        ('NOTA',r'\bNOTA\b|\bPONTUA[CÇ][AÃ]O\b'),
        ('MÉDIA',r'\bM[EÉ]DIA\b'),
        ('CÓDIGO',r'\bC[OÓ]DIGO\b|\bC\d{3}\b'),
        ('MATRÍCULA',r'\bMATR[IÍ]CULA\b'),
        ('NOME',r'\bNOME\b'),
        ('CARGO',r'\bCARGO\b'),
        ('LOTAÇÃO',r'\bLOTA[CÇ][AÃ]O\b')
    ]:
        if re.search(pattern,t,re.I): found.append(field)
    return ', '.join(found)+' (INDÍCIO)' if found else 'A CONFIRMAR NO ATO'

def nature(context):
    t=s(context).upper()
    if re.search(r'M[EÉ]DIA\s+(?:FINAL\s+)?(?:DO\s+)?(?:TRI[EÊ]NIO|QUADRI[EÊ]NIO|QUINQU[EÊ]NIO)|M[EÉ]DIA\s+FINAL',t):
        return 'MÉDIA DE PERÍODO — NÃO TRATAR COMO NOTA ANUAL'
    return 'NATUREZA A CONFIRMAR'

def construir(hits, details):
    hits = hits if hits is not None else pd.DataFrame()
    details = details if details is not None else pd.DataFrame()
    grouped={}
    for _,d in details.iterrows():
        k=(s(d.get('doc')),s(d.get('page')),s(d.get('matricula')),s(d.get('exercicio')))
        grouped.setdefault(k,[]).append(d)
    rows=[]
    for _,h in hits.iterrows():
        k=(s(h.get('_doc')),s(h.get('Página')),s(h.get('Matrícula')),s(h.get('Ano')))
        ev=grouped.get(k,[])
        notes=unique(d.get('nota_publicada') for d in ev)
        codes=unique(d.get('codigo') for d in ev)
        context=unique((d.get('fonte_contexto') for d in ev),2000)
        nature_value=nature(context+' '+s(h.get('Trecho')))
        # Texto que inclui a expressão não basta para demonstrar valores anteriores/novos
        # de uma linha de tabela. Manter vazio até a extração por campo e vínculo de ato.
        onde,passe=get_pairs(h.get('Trecho'))
        if not re.search(r'\bONDE\s+CONSTA\b',s(h.get('Trecho')),re.I): onde=''
        if not re.search(r'\bPASSE\s+A\s+CONSTAR\b',s(h.get('Trecho')),re.I): passe=''
        eid=hashlib.sha256('|'.join([s(h.get(x)) for x in ('_doc','Página','Tipo','Matrícula','Ano','Trecho')]).encode()).hexdigest()[:24]
        rows.append([eid,s(h.get('Matrícula')),s(h.get('Servidor')),s(h.get('Ano')),
                     h.get('DOE'),s(h.get('Arquivo')),h.get('Página'),s(h.get('Tipo')),
                     nature_value,field_hint(s(h.get('Trecho'))+' '+context),s(h.get('Nota na base')),
                     notes,codes,onde,passe,'','','','','NÃO VERIFICADA — PESQUISAR PUBLICAÇÕES POSTERIORES',
                     'CANDIDATO DOCUMENTAL — NÃO HOMOLOGADO',s(h.get('Trecho')),context])
    timeline=pd.DataFrame(rows,columns=EVENT_COLS).drop_duplicates(subset=['ID do evento'])
    if not timeline.empty:
        timeline['_ord']=pd.to_numeric(timeline['DOE'],errors='coerce')
        timeline=timeline.sort_values(['Matrícula','Exercício','_ord','Página','ID do evento'],kind='stable').drop(columns='_ord')
    summary=[]
    # Uma linha por exercício para cada matrícula encontrada; anos sem ocorrência
    # NÃO equivalem a nota inexistente nem a exercício elegível.
    for mat,group in timeline.groupby('Matrícula',sort=True):
        for year in YEARS:
            g=group[group['Exercício']==year]
            undetermined=group[group['Exercício']=='INDETERMINADO']
            if not g.empty:
                person=unique(g['Servidor'])
                base=unique(g['Nota na Base Geral'])
                yearly=g[g['Natureza do valor']!='MÉDIA DE PERÍODO — NÃO TRATAR COMO NOTA ANUAL']
                notes=unique(yearly['Nota publicada (extração)'])
                codes=unique(yearly['Código publicado (extração)'])
                old=unique(g['Onde consta (texto do ato)'])
                new=unique(g['Passe a constar (texto do ato)'])
                ids=unique(g['ID do evento'])
                refs=unique((f"DOE {s(r['DOE'])} p.{s(r['Página'])}" for _,r in g.iterrows()))
                status='NÃO CONFIRMADA — PESQUISA POSTERIOR NECESSÁRIA'
                first,last=s(g.iloc[0]['DOE']),s(g.iloc[-1]['DOE'])
            else:
                person=unique(group['Servidor']);base=notes=codes=old=new=ids=refs=first=last=''
                status='SEM OCORRÊNCIA ASSOCIADA AO EXERCÍCIO NESTE LOTE'
            if not undetermined.empty:
                status+='; HÁ OCORRÊNCIAS COM EXERCÍCIO INDETERMINADO'
            summary.append([mat,person,year,base,notes,codes,old,new,'','','',len(g),first,last,
                            'NÃO COMPROVADA PARA TODO O UNIVERSO DOCUMENTAL',status,ids,refs])
    return timeline,pd.DataFrame(summary,columns=SUMMARY_COLS)

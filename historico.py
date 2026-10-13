"""Robô Formiga 12: trilha documental por matrícula, sem homologação automática.

Uma associação entre atos é hipótese para conferência, nunca revogação ou
retificação comprovada. O universo é apenas o lote de PDFs processado.
"""
import hashlib
import re
import unicodedata
import pandas as pd

YEARS = tuple(str(y) for y in range(2019, 2025))
EVENT_COLS = [
 'ID do evento','Matrícula','Servidor','Exercício','DOE','Arquivo','Página',
 'Tipo de ocorrência','Natureza do valor','Campo afetado','Nota na Base Geral',
 'Nota publicada (extração)','Código publicado (extração)',
 'Onde consta (texto do ato)','Passe a constar (texto do ato)',
 'Valor revogado (comprovado)','Valor tornado sem efeito (comprovado)',
 'Ato anterior relacionado','Ato posterior relacionado','Situação da cadeia',
 'Estado documental','Trecho da publicação','Contexto do ato',
 'Eventos anteriores possíveis','Eventos posteriores possíveis',
 'Pesquisa posterior no lote','Alerta de interpretação',
 'Relação posterior','Motivo da relação','Conferência exigida',
 'Nota anterior (ato identificado)','Nota posterior (ato identificado)','Edital relacionado']
SUMMARY_COLS = [
 'Matrícula','Servidor','Exercício','Nota na Base Geral',
 'Notas anuais publicadas (candidatas)','Códigos publicados (candidatos)',
 'Valores anteriores identificados','Valores posteriores identificados',
 'Valores revogados (comprovados)','Valores tornados sem efeito (comprovados)',
 'Nota documental vigente (confirmada)','Total de eventos','Primeiro DOE localizado',
 'Último DOE localizado','Cobertura posterior','Situação da vigência',
 'IDs dos eventos','Referências DOE/página','Eventos posteriores possíveis',
 'Tipos de ocorrências','Alerta de interpretação',
 'Quantidade de atos posteriores possíveis','Ação recomendada',
 'Retificações tabulares identificadas (ato)','Notas anteriores (ato)','Notas posteriores (ato)']

def s(v):
    if v is None: return ''
    try:
        if pd.isna(v): return ''
    except (TypeError,ValueError): pass
    return str(v).strip()

def unique(vals, limit=3000):
    return ' | '.join(dict.fromkeys(s(v) for v in vals if s(v)))[:limit]

def norm(t):
    return ''.join(c for c in unicodedata.normalize('NFKD',s(t).upper()) if not unicodedata.combining(c))

def nature(t):
    t=norm(t)
    if re.search(r'MEDIA\s+(?:FINAL\s+)?(?:DO\s+)?(?:TRIENIO|QUADRIENIO|QUINQUENIO)|MEDIA\s+FINAL',t):
        return 'MÉDIA DE PERÍODO — NÃO TRATAR COMO NOTA ANUAL'
    return 'NATUREZA A CONFIRMAR'

def field_hint(t):
    t=norm(t)
    fields=[]
    for name,pat in [('NOTA',r'\bNOTA\b|PONTUACAO'),('MÉDIA',r'\bMEDIA\b'),
                     ('CÓDIGO',r'\bCODIGO\b|\bC\d{3}\b'),('MATRÍCULA',r'\bMATRICULA\b'),
                     ('NOME',r'\bNOME\b'),('CARGO',r'\bCARGO\b'),('LOTAÇÃO',r'\bLOTACAO\b')]:
        if re.search(pat,t): fields.append(name)
    return ', '.join(fields)+' (INDÍCIO)' if fields else 'A CONFIRMAR NO ATO'

def get_pairs(t):
    # Só captura quando AMBOS os rótulos constam do próprio trecho extraído.
    t=re.sub(r'\s+',' ',s(t))
    m=re.search(r'\bONDE\s+CONSTA\s*[:\-]?\s*(.{1,180}?)\s*\bPASSE\s+A\s+CONSTAR\s*[:\-]?\s*(.{1,180})',t,re.I)
    if not m: return '',''
    return s(m.group(1)),s(m.group(2))

def construir(hits, details, controlled=None):
    hits=hits if hits is not None else pd.DataFrame()
    details=details if details is not None else pd.DataFrame()
    controlled = controlled if controlled is not None else pd.DataFrame()
    groups={}
    for _,d in details.iterrows():
        k=tuple(s(d.get(x)) for x in ('doc','page','matricula','exercicio'))
        groups.setdefault(k,[]).append(d)
    events=[]
    for _,h in hits.iterrows():
        k=tuple(s(h.get(x)) for x in ('_doc','Página','Matrícula','Ano'))
        ds=groups.get(k,[])
        context=unique((d.get('fonte_contexto') for d in ds),1800)
        nt=nature(context+' '+s(h.get('Trecho')))
        notes='' if nt.startswith('MÉDIA DE PERÍODO') else unique(d.get('nota_publicada') for d in ds)
        codes='' if nt.startswith('MÉDIA DE PERÍODO') else unique(d.get('codigo') for d in ds)
        onde,passe=get_pairs(context)
        if not (onde and passe):
            onde,passe=get_pairs(h.get('Trecho'))
        eid=hashlib.sha256('|'.join(s(h.get(x)) for x in ('_doc','Página','Tipo','Matrícula','Ano','Trecho')).encode()).hexdigest()[:24]
        alert=[]
        if nt.startswith('MÉDIA'): alert.append('MÉDIA DE PERÍODO: NÃO IMPUTAR COMO NOTA ANUAL')
        if onde and passe: alert.append('PAR ONDE CONSTA/PASSE A CONSTAR LOCALIZADO NO CONTEXTO — CONFERIR SE PERTENCE À MESMA LINHA E MATRÍCULA')
        if s(h.get('Ano')) not in YEARS: alert.append('EXERCÍCIO INDETERMINADO')
        if s(h.get('Tipo')) in ('RETIFICACAO','TORNAR_SEM_EFEITO','REVOGACAO','ANULACAO'):
            alert.append('ALCANCE DO ATO NÃO DEMONSTRADO: CONFERIR ORIGINAL E POSTERIORES')
        events.append(dict(zip(EVENT_COLS,[eid,s(h.get('Matrícula')),s(h.get('Servidor')),s(h.get('Ano')),
            h.get('DOE'),s(h.get('Arquivo')),h.get('Página'),s(h.get('Tipo')),nt,
            field_hint(s(h.get('Trecho'))+' '+context),s(h.get('Nota na base')),notes,codes,
            onde,passe,'','','','','NÃO VERIFICADA — PESQUISAR PUBLICAÇÕES POSTERIORES',
            'CANDIDATO DOCUMENTAL — NÃO HOMOLOGADO',s(h.get('Trecho')),context,
            '','','NÃO COMPROVADA — LOTE PARCIAL','; '.join(alert),
            'NÃO COMPROVADA','', 'VERIFICAR ATO INTEGRAL E ALCANCE DA ALTERAÇÃO','','',''])))
    # Eventos tabulares identificados no Edital 44/2024; mantê-los mesmo quando
    # a triagem genérica não encontrou a matrícula naquela página.
    for _,r in controlled.iterrows():
        mat=s(r.get('matricula')); year=s(r.get('exercicio'))
        same=hits[(hits['Matrícula'].astype(str)==mat) & (hits['Ano'].astype(str)==year)] if not hits.empty else pd.DataFrame()
        base=unique(same['Nota na base']) if not same.empty else ''
        old=s(r.get('nota_antes')); new=s(r.get('nota_depois'))
        eid=hashlib.sha256(('RET_CONTROLADA|'+s(r.get('doc'))+'|'+s(r.get('edital'))+'|'+mat+'|'+year).encode()).hexdigest()[:24]
        notes='Nota '+old+' → '+new if old != new else 'Nota mantida '+new
        context=s(r.get('evidencia'))
        events.append(dict(zip(EVENT_COLS,[eid,mat,s(r.get('nome_depois')),year,
            s(r.get('doe')),s(r.get('arquivo')),s(r.get('pagina_pdf')),
            'RETIFICACAO — TABELA IDENTIFICADA','NOTA ANUAL — EDITAL 44/2024',
            s(r.get('campo_alterado')),base,'','',
            old,new,'','','','',
            'RETIFICAÇÃO COMPROVADA NO ATO; PUBLICAÇÕES POSTERIORES NÃO INVESTIGADAS',
            'ALTERAÇÃO TABULAR IDENTIFICADA — VIGÊNCIA NÃO CONFIRMADA',
            notes,context,'','','NÃO COMPROVADA — LOTE PARCIAL',
            'CONFERIR PUBLICAÇÕES POSTERIORES E BASE GERAL',
            'NÃO COMPROVADA','',
            'PESQUISAR ATOS POSTERIORES; NÃO HOMOLOGAR VIGÊNCIA',old,new,s(r.get('edital'))])))
    timeline=pd.DataFrame(events,columns=EVENT_COLS).drop_duplicates(subset=['ID do evento'])
    if timeline.empty:
        return timeline,pd.DataFrame(columns=SUMMARY_COLS)
    timeline['_ord']=pd.to_numeric(timeline['DOE'],errors='coerce')
    timeline['_page']=pd.to_numeric(timeline['Página'],errors='coerce')
    timeline=timeline.sort_values(['Matrícula','_ord','_page','ID do evento'],kind='stable')
    # Links são possibilidades cronológicas, não inferência de efeito jurídico.
    for mat,group in timeline.groupby('Matrícula',sort=False):
        for idx,row in group.iterrows():
            y=s(row['Exercício']); n=row['_ord']
            if y not in YEARS or pd.isna(n): continue
            compatible=group[(group['Exercício'].astype(str)==y) & group['_ord'].notna()]
            earlier=compatible[compatible['_ord']<n]
            later=compatible[compatible['_ord']>n]
            # Mesma edição não significa ato posterior; ordenar somente entre edições diferentes.
            timeline.at[idx,'Eventos anteriores possíveis']=unique(earlier['ID do evento'],1000)
            timeline.at[idx,'Eventos posteriores possíveis']=unique(later['ID do evento'],1000)
            timeline.at[idx,'Relação posterior']=('POSSÍVEL — NÃO COMPROVADA' if len(later) else 'NENHUMA RELAÇÃO DEMONSTRADA')
            timeline.at[idx,'Motivo da relação']=('MESMA MATRÍCULA E EXERCÍCIO; DOE NUMERICAMENTE POSTERIOR' if len(later) else '')
            timeline.at[idx,'Pesquisa posterior no lote']=('HÁ CANDIDATOS EM DOE POSTERIOR — EXAMINAR' if len(later) else
                'NÃO LOCALIZADO NESTE LOTE — NÃO PROVA AUSÊNCIA')
    timeline=timeline.drop(columns=['_ord','_page'])
    summary=[]
    for mat,group in timeline.groupby('Matrícula',sort=True):
        person=unique(group['Servidor'])
        uncertain=group[group['Exercício'].astype(str)=='INDETERMINADO']
        for year in YEARS:
            g=group[group['Exercício'].astype(str)==year]
            valid=g[g['Natureza do valor']!='MÉDIA DE PERÍODO — NÃO TRATAR COMO NOTA ANUAL']
            base=unique(g['Nota na Base Geral'])
            refs=unique(f"DOE {s(r['DOE'])} p.{s(r['Página'])}" for _,r in g.iterrows())
            state=('NÃO CONFIRMADA — INVESTIGAR CADEIA E COBERTURA' if len(g) else
                   'SEM EVENTO ASSOCIADO AO EXERCÍCIO NESTE LOTE')
            if len(uncertain): state+='; HÁ EVENTOS COM EXERCÍCIO INDETERMINADO'
            summary.append([mat,person,year,base,unique(valid['Nota publicada (extração)']),
                unique(valid['Código publicado (extração)']),unique(g['Onde consta (texto do ato)']),
                unique(g['Passe a constar (texto do ato)']),'','','',len(g),
                s(g.iloc[0]['DOE']) if len(g) else '',s(g.iloc[-1]['DOE']) if len(g) else '',
                'NÃO COMPROVADA PARA TODO O UNIVERSO DOCUMENTAL',state,
                unique(g['ID do evento']),refs,unique(g['Eventos posteriores possíveis']),
                unique(g['Tipo de ocorrência']),unique(g['Alerta de interpretação']),
                int(g['Eventos posteriores possíveis'].astype(str).str.len().gt(0).sum()),
                ('REVISAR ATOS POSTERIORES E O ALCANCE DA RETIFICAÇÃO' if len(g) else
                 'CONFERIR BASE GERAL E PESQUISAR PUBLICAÇÕES DO EXERCÍCIO'),
                int(g['Edital relacionado'].astype(str).str.len().gt(0).sum()),
                unique(g['Nota anterior (ato identificado)']),
                unique(g['Nota posterior (ato identificado)'])])
    return timeline,pd.DataFrame(summary,columns=SUMMARY_COLS)

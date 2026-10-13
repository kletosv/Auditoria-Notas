"""Histórico documental conservador por matrícula: indícios, não homologação.

Usa apenas ocorrências extraídas dos PDFs carregados. Não inventa sequência jurídica,
notas revogadas ou vigência. A ordem por número do DOE é apenas indicativa.
"""
import hashlib
import re
import pandas as pd

COLS = ["ID do evento", "Matrícula", "Servidor", "Exercício", "DOE", "Arquivo", "Página", "Tipo de ocorrência", "Campo afetado (a confirmar)", "Nota na Base Geral", "Nota publicada (extração)", "Código publicado (extração)", "Onde consta (a conferir)", "Passe a constar (a conferir)", "Nota revogada / sem efeito (comprovada)", "Ato posterior relacionado", "Estado documental", "Trecho da publicação", "Contexto do ato"]


def _str(x):
    return "" if pd.isna(x) else str(x)


def _pair(text):
    # Extração somente quando a expressão e seu conteúdo aparecem no MESMO trecho.
    # A tabela pode estar fora do trecho; nesse caso, deixa em branco.
    t = re.sub(r"\s+", " ", _str(text))
    a = re.search(r"ONDE\s+CONSTA\s*[:\-]?\s*(.{1,120}?)(?=\bPASSE\s+A\s+CONSTAR\b|$)", t, re.I)
    b = re.search(r"PASSE\s+A\s+CONSTAR\s*[:\-]?\s*(.{1,120}?)(?=\bONDE\s+CONSTA\b|$)", t, re.I)
    return (a.group(1).strip(' :-;') if a else '', b.group(1).strip(' :-;') if b else '')


def construir(hits, details):
    if hits is None or hits.empty:
        return pd.DataFrame(columns=COLS), pd.DataFrame(columns=["Matrícula", "Servidor", "Exercício", "Nota na Base Geral", "Notas extraídas dos DOEs", "Códigos extraídos", "Ocorrências", "Situação da vigência", "Último DOE localizado"])
    # Evitar produto cartesiano entre várias evidências da mesma página/matrícula/ano.
    details = details.copy() if details is not None else pd.DataFrame()
    grouped = {}
    if not details.empty:
        for _, d in details.iterrows():
            k = (_str(d.get('doc')), _str(d.get('page')), _str(d.get('matricula')), _str(d.get('exercicio')))
            grouped.setdefault(k, []).append(d)
    rows=[]
    for _, h in hits.iterrows():
        k=(_str(h.get('_doc')), _str(h.get('Página')), _str(h.get('Matrícula')), _str(h.get('Ano')))
        evid=grouped.get(k, [])
        # Na ausência de relação inequívoca entre registros da mesma página, não escolher valor arbitrário.
        notas={_str(x.get('nota_publicada')) for x in evid if _str(x.get('nota_publicada'))}
        codigos={_str(x.get('codigo')) for x in evid if _str(x.get('codigo'))}
        nota=next(iter(notas)) if len(notas)==1 else ''
        codigo=next(iter(codigos)) if len(codigos)==1 else ''
        contexto=' | '.join(sorted({_str(x.get('fonte_contexto')) for x in evid if _str(x.get('fonte_contexto'))}))[:1500]
        onde,passe=_pair(_str(h.get('Trecho')))
        typ=_str(h.get('Tipo'))
        # Só se pode inferir um campo se estiver explícito no trecho; caso contrário, não afirmar.
        trecho=_str(h.get('Trecho'))
        campo='A CONFIRMAR NO ATO'
        if re.search(r'\b(?:NOTA|PONTUA[CÇ][AÃ]O)\b',trecho,re.I): campo='NOTA (INDÍCIO)'
        elif re.search(r'\bMATR[IÍ]CULA\b',trecho,re.I): campo='MATRÍCULA (INDÍCIO)'
        elif re.search(r'\bNOME\b',trecho,re.I): campo='NOME (INDÍCIO)'
        eid=hashlib.sha256('|'.join([_str(h.get(x)) for x in ['_doc','Página','Tipo','Matrícula','Ano','Trecho']]).encode()).hexdigest()[:20]
        rows.append([eid,_str(h.get('Matrícula')),_str(h.get('Servidor')),_str(h.get('Ano')),h.get('DOE'),_str(h.get('Arquivo')),h.get('Página'),typ,campo,_str(h.get('Nota na base')),nota,codigo,onde,passe,'','', 'PENDENTE — VERIFICAR ATOS POSTERIORES',trecho,contexto])
    timeline=pd.DataFrame(rows,columns=COLS).drop_duplicates(subset=['ID do evento'])
    timeline=timeline.sort_values(['Matrícula','Exercício','DOE','Página','ID do evento'],kind='stable')
    summary=[]
    for (mat,year),g in timeline.groupby(['Matrícula','Exercício'],sort=False):
        def unique(col):
            return ' | '.join(dict.fromkeys(str(v) for v in g[col] if _str(v)))[:1200]
        summary.append([mat,unique('Servidor'),year,unique('Nota na Base Geral'),unique('Nota publicada (extração)'),unique('Código publicado (extração)'),len(g),'NÃO CONFIRMADA — EXIGE PESQUISA POSTERIOR',g['DOE'].iloc[-1]])
    cols=['Matrícula','Servidor','Exercício','Nota na Base Geral','Notas extraídas dos DOEs','Códigos extraídos','Ocorrências','Situação da vigência','Último DOE localizado']
    return timeline,pd.DataFrame(summary,columns=cols)

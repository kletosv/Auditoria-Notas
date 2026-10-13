"""Relatório de seis abas; não presume vigência, omissão ou revogação."""
from io import BytesIO
import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

NAMES=['CONSOLIDADO','INCLUSÕES','RETIFICAÇÕES','ONDE CONSTA E PASSE A CONSTAR','TORNAR SEM EFEITO','HISTÓRICO POR MATRÍCULA']

def excel_bytes(docs,hits,differences=None,decisions=None,version='',timeline=None,per_matricula=None,controlled=None,medias=None):
    hits=hits if hits is not None else pd.DataFrame()
    timeline=timeline if timeline is not None else pd.DataFrame()
    per_matricula=per_matricula if per_matricula is not None else pd.DataFrame()
    controlled=controlled if controlled is not None else pd.DataFrame()
    medias=medias if medias is not None else pd.DataFrame()
    differences=differences if differences is not None else pd.DataFrame()
    sheets={}
    # Consolidado não junta notas alternativas em uma mesma célula: cada evidência tem sua linha.
    records=[]
    if not timeline.empty:
        for _,r in timeline.iterrows():
            records.append({'Matrícula':r.get('Matrícula',''),'Servidor':r.get('Servidor',''),
                'Exercício':r.get('Exercício',''),'Nota Base Geral':r.get('Nota na Base Geral',''),
                'Nota publicada':r.get('Nota publicada (extração)',''),
                'Código publicado':r.get('Código publicado (extração)',''),
                'Tipo / natureza':r.get('Tipo de ocorrência',''),
                'Situação':r.get('Estado documental',''), 'DOE':r.get('DOE',''),
                'Página':r.get('Página',''),'ID evento':r.get('ID do evento','')})
    # Desagregar múltiplos valores extraídos de uma mesma ocorrência.
    expanded=[]
    for rec in records:
        notes=str(rec['Nota publicada']).split(' | ') if rec['Nota publicada'] else ['']
        codes=str(rec['Código publicado']).split(' | ') if rec['Código publicado'] else ['']
        for note in notes:
            for code in codes:
                row=rec.copy();row['Nota publicada']=note;row['Código publicado']=code
                expanded.append(row)
    sheets['CONSOLIDADO']=pd.DataFrame(expanded,columns=['Matrícula','Servidor','Exercício','Nota Base Geral','Nota publicada','Código publicado','Tipo / natureza','Situação','DOE','Página','ID evento'])
    # Inclusão exige prova da omissão anterior: triagem genérica não satisfaz esse critério.
    sheets['INCLUSÕES']=pd.DataFrame(columns=['Matrícula','Servidor','Exercício','Nota incluída','Código','DOE anterior','Edital anterior','Prova de omissão','DOE inclusão','Página','Situação'])
    ret=[]
    if not controlled.empty:
        for _,r in controlled.iterrows():
            ret.append({'Matrícula':r.get('matricula',''),'Servidor':r.get('nome_depois',''),
                'Exercício':r.get('exercicio',''),'Nota Base Geral':'',
                'Nota anterior no DOE':r.get('nota_antes',''),'Nota retificada no DOE':r.get('nota_depois',''),
                'Campo alterado':r.get('campo_alterado',''),'DOE':r.get('doe',''),
                'Edital':r.get('edital',''),'Página':r.get('pagina_impressa',''),
                'Situação':'ALTERAÇÃO IDENTIFICADA; COMPARAR BASE E POSTERIORES'})
    # Valor da Base Geral é obtido somente quando há correspondência inequívoca de matrícula/exercício.
    if not hits.empty:
        for r in ret:
            matches=hits[(hits['Matrícula'].astype(str)==str(r['Matrícula'])) & (hits['Ano'].astype(str)==str(r['Exercício']))]
            vals=list(dict.fromkeys(str(v).strip() for v in matches['Nota na base'] if str(v).strip()))
            if len(vals)==1:r['Nota Base Geral']=vals[0]
    sheets['RETIFICAÇÕES']=pd.DataFrame(ret,columns=['Matrícula','Servidor','Exercício','Nota Base Geral','Nota anterior no DOE','Nota retificada no DOE','Campo alterado','DOE','Edital','Página','Situação'])
    media_rows=[]
    for _,r in medias.iterrows():
        media_rows.append({'Matrícula':r.get('matricula',''),'Servidor':r.get('servidor',''),
            'Triênio':r.get('trienio',''),'Nota '+str(r.get('ano1',''))+' anterior':r.get('antes1',''),
            'Nota '+str(r.get('ano2',''))+' anterior':r.get('antes2',''),
            'Nota '+str(r.get('ano3',''))+' anterior':r.get('antes3',''),
            'Média anterior':r.get('media_antes',''),
            'Nota '+str(r.get('ano1',''))+' corrigida':r.get('depois1',''),
            'Nota '+str(r.get('ano2',''))+' corrigida':r.get('depois2',''),
            'Nota '+str(r.get('ano3',''))+' corrigida':r.get('depois3',''),
            'Média corrigida':r.get('media_depois',''),
            'Campos alterados':r.get('campos_alterados',''),'DOE':r.get('doe',''),
            'Edital':r.get('edital',''),'Publicação de origem':r.get('origem',''),
            'Páginas DOE':r.get('pagina_doe',''),'Situação':r.get('situacao','')})
    sheets['ONDE CONSTA E PASSE A CONSTAR']=pd.DataFrame(media_rows)
    # Sem prova do alcance, atos classificados não podem ser descritos como efetivados.
    t=timeline[timeline['Tipo de ocorrência'].astype(str).str.contains('TORNAR_SEM_EFEITO',na=False)] if not timeline.empty else pd.DataFrame()
    sheets['TORNAR SEM EFEITO']=t.drop(columns=['Contexto do ato'],errors='ignore').copy()
    hist=timeline.copy()
    if not medias.empty:
        extras=[]
        for _,r in medias.iterrows():
            extras.append({'Matrícula':r['matricula'],'Servidor':r['servidor'],'Exercício':r['trienio'],
                'DOE':r['doe'],'Arquivo':r['arquivo'],'Página':r['pagina_doe'],
                'Tipo de ocorrência':'RETIFICAÇÃO DE MÉDIA DO TRIÊNIO',
                'Natureza do valor':'MÉDIA DE PERÍODO — NÃO TRATAR COMO NOTA ANUAL',
                'Campo afetado':r['campos_alterados'],
                'Onde consta (texto do ato)':f"{r['antes1']}; {r['antes2']}; {r['antes3']}; MÉDIA {r['media_antes']}",
                'Passe a constar (texto do ato)':f"{r['depois1']}; {r['depois2']}; {r['depois3']}; MÉDIA {r['media_depois']}",
                'Estado documental':r['situacao'],'Edital relacionado':r['edital']})
        hist=pd.concat([hist,pd.DataFrame(extras)],ignore_index=True)
    sheets['HISTÓRICO POR MATRÍCULA']=hist.drop(columns=['Contexto do ato'],errors='ignore')
    buf=BytesIO()
    with pd.ExcelWriter(buf,engine='openpyxl') as writer:
        for name in NAMES:
            frame=sheets[name].copy().fillna('')
            if frame.empty and len(frame.columns)==0:frame=pd.DataFrame(columns=['Sem registros comprovados'])
            for col in frame.columns:
                if 'Matrícula' in str(col) or str(col)=='DOE':frame[col]=frame[col].astype(str)
            frame.to_excel(writer,sheet_name=name,index=False)
            ws=writer.sheets[name];ws.freeze_panes='A2';ws.sheet_view.showGridLines=False
            for c in ws[1]:
                c.fill=PatternFill('solid',fgColor='17324D');c.font=Font(bold=True,color='FFFFFF');c.alignment=Alignment(wrap_text=True)
            ws.row_dimensions[1].height=32
            for i,col in enumerate(frame.columns,1):
                ws.column_dimensions[get_column_letter(i)].width=min(43,max(17,len(str(col))+3))
                if 'Matrícula' in str(col) or str(col)=='DOE':
                    for row in ws.iter_rows(min_row=2,min_col=i,max_col=i):row[0].number_format='@'
            if ws.max_row>1:ws.auto_filter.ref=ws.dimensions
    return buf.getvalue()

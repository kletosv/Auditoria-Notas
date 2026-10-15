"""Relatório de seis abas; não presume vigência, omissão ou revogação."""
from io import BytesIO
import re
from collections import defaultdict
import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

NAMES=['CONSOLIDADO','INCLUSÕES','RETIFICAÇÕES','ONDE CONSTA E PASSE A CONSTAR','TORNAR SEM EFEITO','HISTÓRICO POR MATRÍCULA']

def excel_bytes(docs,hits,differences=None,decisions=None,version='',timeline=None,per_matricula=None,controlled=None,medias=None,base_lookup=None):
    hits=hits if hits is not None else pd.DataFrame()
    timeline=timeline if timeline is not None else pd.DataFrame()
    per_matricula=per_matricula if per_matricula is not None else pd.DataFrame()
    controlled=controlled if controlled is not None else pd.DataFrame()
    medias=medias if medias is not None else pd.DataFrame()
    differences=differences if differences is not None else pd.DataFrame()
    sheets={}
    base_lookup=base_lookup or {}
    def base_note(mat,year):
        import re
        key=re.sub(r'\D','',str(mat))
        return str(base_lookup.get(key,{}).get('NOTA '+str(year),'')).strip() if str(year) in ('2019','2020','2021','2022','2023','2024') else ''
    # Consolidado não junta notas alternativas em uma mesma célula: cada evidência tem sua linha.
    records=[]
    if not timeline.empty:
        for _,r in timeline.iterrows():
            records.append({'Matrícula':r.get('Matrícula',''),'Servidor':r.get('Servidor',''),
                'Exercício':r.get('Exercício',''),'Nota Base Geral':base_note(r.get('Matrícula',''),r.get('Exercício','')) or r.get('Nota na Base Geral',''),
                'Nota publicada':r.get('Nota publicada (extração)',''),
                'Código publicado':r.get('Código publicado (extração)',''),
                'Tipo / natureza':r.get('Tipo de ocorrência',''),
                'Alerta de exercício':('EXERCÍCIO INDETERMINADO — NÃO ATRIBUIR NOTA A ANO' if str(r.get('Exercício','')) not in ('2019','2020','2021','2022','2023','2024') else ''),
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
    sheets['CONSOLIDADO']=pd.DataFrame(expanded,columns=['Matrícula','Servidor','Exercício','Nota Base Geral','Nota publicada','Código publicado','Tipo / natureza','Alerta de exercício','Situação','DOE','Página','ID evento'])
    # Inclusão oficial não se confunde com ausência de registro na Base Geral.
    # Sem comprovação da omissão na publicação anterior, não há linha confirmada.
    inclusao_cols=['Matrícula','Servidor','Exercício','O que foi incluído?',
        'Como está na Base Geral','Como deverá ficar na Base Geral',
        'Em qual D.O. consta a inclusão?','A inclusão já consta na Base?',
        'Houve alteração posterior?','Em qual D.O.?','Situação da inclusão',
        'Providência necessária','Cargo','Vínculo','Histórico documental e observações']
    sheets['INCLUSÕES']=pd.DataFrame(columns=inclusao_cols)
    ret=[]
    if not controlled.empty:
        for _,r in controlled.iterrows():
            ret.append({'Matrícula':r.get('matricula',''),'Servidor':r.get('nome_depois',''),
                'Exercício':r.get('exercicio',''),'Nota Base Geral':base_note(r.get('matricula',''),r.get('exercicio','')),
                'Nota anterior no DOE':r.get('nota_antes',''),'Nota retificada no DOE':r.get('nota_depois',''),
                'Campo alterado':r.get('campo_alterado',''),'DOE':r.get('doe',''),
                'Edital':r.get('edital',''),'Página':r.get('pagina_impressa',''),
                'Situação':'ALTERAÇÃO IDENTIFICADA; COMPARAR BASE E POSTERIORES'})
    # Fallback conservador: hits podem conter a nota da base, mas não são a Base Geral inteira.
    # A consulta direta ao CSV carregado pelo usuário tem precedência.
    if not hits.empty:
        for r in ret:
            if r['Nota Base Geral']:
                continue
            matches=hits[(hits['Matrícula'].astype(str)==str(r['Matrícula'])) & (hits['Ano'].astype(str)==str(r['Exercício']))]
            vals=list(dict.fromkeys(str(v).strip() for v in matches['Nota na base'] if str(v).strip() and str(v).strip().lower()!='nan'))
            if len(vals)==1:
                r['Nota Base Geral']=vals[0]
    def normalized_note(value):
        raw=str(value).strip()
        if not raw or raw.lower()=='nan': return ''
        if re.fullmatch(r'[0-9]+(?:[.,][0-9]+)?',raw):
            try: return ('%.4f' % float(raw.replace(',','.'))).rstrip('0').rstrip('.')
            except ValueError: pass
        return raw.upper()
    ret_out=[]
    for r in ret:
        base=normalized_note(r['Nota Base Geral']); new=normalized_note(r['Nota retificada no DOE'])
        same=bool(base and new and base==new)
        r['Comparação Base x Retificada']=('COINCIDE COM ESTA RETIFICAÇÃO' if same else
            'DIVERGE — CONFERIR VIGÊNCIA' if base and new else 'NÃO COMPARÁVEL — DADO AUSENTE')
        # Sem cobertura documental posterior comprovada, não declarar SIM ou NÃO.
        r['O que foi alterado?']=r.get('Campo alterado','')
        r['Nota Base']=r.get('Nota Base Geral','')
        r['Nota Retificada']=r.get('Nota retificada no DOE','')
        r['D.O. onde consta a alteração']=r.get('DOE','')
        r['Houve alteração posterior?']='PENDENTE'
        r['Em qual D.O.?']=''
        r['A nota da Base já está corrigida?']='PENDENTE' if base and new else 'PENDENTE — DADOS INSUFICIENTES'
        r['Observação de validação']=('Coincide com a retificação localizada; falta verificar atos posteriores.' if same else
            'Diferença localizada; confirmar cadeia de publicações antes de corrigir a Base Geral.')
        ret_out.append(r)
    ret_cols=['Matrícula','Servidor','Exercício','O que foi alterado?','Nota Base',
        'Nota Retificada','D.O. onde consta a alteração','Houve alteração posterior?',
        'Em qual D.O.?','A nota da Base já está corrigida?',
        'Nota anterior no DOE','Campo alterado','Comparação Base x Retificada',
        'DOE','Edital','Página','Situação','Observação de validação']
    sheets['RETIFICAÇÕES']=pd.DataFrame(ret_out,columns=ret_cols)
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
    # O objeto atingido deve ser explícito e comprovado pelo texto do ato.
    # Uma mera classificação TORNAR_SEM_EFEITO não comprova NOTA, MÉDIA ou RETIFICAÇÃO.
    t=timeline[timeline['Tipo de ocorrência'].astype(str).str.contains('TORNAR_SEM_EFEITO',na=False)] if not timeline.empty else pd.DataFrame()
    sem_cols=['Matrícula','Servidor','Exercício / Período','O que foi tornado sem efeito?',
        'Nota ou média atingida','D.O. da publicação original','Data e página da publicação original',
        'D.O. que tornou sem efeito','Data e página do cancelamento','Motivo informado no ato',
        'Houve publicação posterior?','Em qual D.O.?','Como está na Base Geral',
        'Como deverá ficar na Base Geral','Providência necessária','Situação da comprovação',
        'Resumo explicativo / Histórico','Ato anterior atingido (comprovado)',
        'Escopo atingido (comprovado)','Arquivo de origem','Página da ocorrência','ID do evento']
    sem_rows=[]
    for _,r in t.iterrows():
        mat=str(r.get('Matrícula','')).strip()
        ano=str(r.get('Exercício','')).strip()
        doe=str(r.get('DOE','')).strip()
        pg=str(r.get('Página','')).strip()
        # Apenas usar campos de comprovação explícitos, nunca deduzir pelo tipo de ocorrência.
        obj=str(r.get('Objeto tornado sem efeito (comprovado)','')).strip()
        if obj.upper() not in ('NOTA','MÉDIA','RETIFICAÇÃO','OUTRO ATO'): obj='PENDENTE DE IDENTIFICAÇÃO'
        ato=str(r.get('Ato anterior atingido (comprovado)','')).strip()
        escopo=str(r.get('Escopo atingido (comprovado)','')).strip()
        valor=str(r.get('Valor atingido (comprovado)','')).strip()
        comprovado=bool(obj!='PENDENTE DE IDENTIFICAÇÃO' and ato and escopo)
        status='COMPROVADO — CONFERIR POSTERIORES' if comprovado else 'PENDENTE — IDENTIFICAR ATO ANTERIOR E ALCANCE'
        resumo=(f'{obj}: {valor}. Ato anterior: {ato}. Escopo: {escopo}. '
                'Conferir publicações posteriores antes de corrigir a Base Geral.' if comprovado else
                f'O DOE {doe}, página {pg}, contém ocorrência candidata de tornar sem efeito. '
                'Ainda não foi comprovado se atinge nota, média, retificação ou outro ato; não alterar a Base Geral.')
        sem_rows.append({'Matrícula':mat,'Servidor':r.get('Servidor',''),
            'Exercício / Período':ano,'O que foi tornado sem efeito?':obj,
            'Nota ou média atingida':valor if comprovado else '',
            'D.O. da publicação original':r.get('DOE original comprovado','') if comprovado else '',
            'Data e página da publicação original':r.get('Data e página original comprovadas','') if comprovado else '',
            'D.O. que tornou sem efeito':doe,
            'Data e página do cancelamento':f'Página {pg}' if pg else '',
            'Motivo informado no ato':r.get('Motivo literal do ato',''),
            'Houve publicação posterior?':'PENDENTE','Em qual D.O.?':'',
            'Como está na Base Geral':base_note(mat,ano),
            'Como deverá ficar na Base Geral':'PENDENTE DE VALIDAÇÃO',
            'Providência necessária':'CONFERIR ATO ANTERIOR E PUBLICAÇÕES POSTERIORES',
            'Situação da comprovação':status,'Resumo explicativo / Histórico':resumo,
            'Ato anterior atingido (comprovado)':ato if comprovado else '',
            'Escopo atingido (comprovado)':escopo if comprovado else '',
            'Arquivo de origem':r.get('Arquivo',''),'Página da ocorrência':pg,
            'ID do evento':r.get('ID do evento','')})
    sheets['TORNAR SEM EFEITO']=pd.DataFrame(sem_rows,columns=sem_cols)
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
    # Histórico legível: uma linha por matrícula; valores somente com período e fonte.
    # Eventos sem exercício definido não são atribuídos a um ano por suposição.
    summary=[]
    if not hist.empty and 'Matrícula' in hist.columns:
        def clean(v):
            return '' if pd.isna(v) else str(v).strip()
        def dedup(values):
            return list(dict.fromkeys(v for v in values if v))
        def canonical_name(values):
            names=dedup(clean(v) for v in values)
            groups={}
            for name in names:
                key=re.sub(r'\\s+',' ',name).casefold()
                groups.setdefault(key,[]).append(name)
            return next(iter(groups.values()))[0] if groups else ''
        def event_kind(raw):
            t=raw.upper().replace('_',' ')
            if 'MÉDIA' in t or 'MEDIA' in t: return 'Retificação de média'
            if 'TORNAR SEM EFEITO' in t: return 'Ato de tornar sem efeito (objeto não confirmado)'
            if 'RETIFIC' in t: return 'Retificação'
            if 'INCLUS' in t: return 'Inclusão (a confirmar)'
            if 'ANULA' in t: return 'Anulação (a confirmar)'
            if 'REVOGA' in t: return 'Revogação (a confirmar)'
            return 'Publicação / ocorrência documental'
        for mat,grp in hist.groupby('Matrícula',dropna=False,sort=False):
            mat=clean(mat)
            if not mat: continue
            g=grp.copy()
            if 'DOE' in g:
                g['_sort_doe']=pd.to_numeric(g['DOE'],errors='coerce')
                g=g.sort_values(['_sort_doe'],kind='stable')
            kinds=dedup(event_kind(clean(r.get('Tipo de ocorrência',''))) for _,r in g.iterrows())
            years=set()
            refs=[]
            media_details=[]
            for _,r in g.iterrows():
                year=clean(r.get('Exercício',''))
                if re.fullmatch(r'20(?:19|2[0-4])',year) or re.fullmatch(r'20(?:19|2[0-4])–20(?:19|2[0-4])',year):
                    years.add(year)
                doe=clean(r.get('DOE','')); pg=clean(r.get('Página',''))
                if doe:
                    refs.append('DOE '+doe+(' p. '+pg if pg else ''))
                if 'MÉDIA' in clean(r.get('Tipo de ocorrência','')).upper():
                    old=clean(r.get('Onde consta (texto do ato)',''))
                    new=clean(r.get('Passe a constar (texto do ato)',''))
                    if old and new and year and doe:
                        old_avg=re.search(r'MÉDIA\\s+([\\d.,]+)',old)
                        new_avg=re.search(r'MÉDIA\\s+([\\d.,]+)',new)
                        if old_avg and new_avg:
                            media_details.append(f'Média {year}: {old_avg.group(1)} → {new_avg.group(1)} (DOE {doe})')
            years_sorted=sorted(years,key=lambda y:(int(y[:4]),len(y),y))
            refs=dedup(refs)
            detail=dedup(media_details)
            event_labels='; '.join(kinds[:4]) + ('; outras ocorrências' if len(kinds)>4 else '')
            if detail:
                summary_text='; '.join(detail[:2])+'. '
            else:
                summary_text=event_labels+'. ' if event_labels else 'Ocorrências documentais identificadas. '
            if len(g)>1:
                summary_text+=f'{len(g)} registros encontrados no lote. '
            summary_text+='Efeitos posteriores e vigência ainda não comprovados.'
            pending=('EXERCÍCIO NÃO IDENTIFICADO EM PARTE DOS REGISTROS; ' if any(
                clean(v) in ('','INDETERMINADO') for v in g.get('Exercício',[])) else '')
            pending+='VERIFICAR ATOS POSTERIORES E SUPLEMENTOS'
            summary.append({
                'Matrícula':mat,
                'Servidor':canonical_name(g.get('Servidor',[])),
                'Exercícios com ocorrências':', '.join(years_sorted) if years_sorted else 'NÃO IDENTIFICADO',
                'O que foi encontrado?':event_labels,
                'Resumo do histórico':summary_text[:450],
                'Situação da Base Geral':'A VERIFICAR — SEM VIGÊNCIA DOCUMENTAL CONFIRMADA',
                'Providência necessária':'CONFERIR PUBLICAÇÕES E COMPARAR COM A BASE',
                'Diários e páginas':'; '.join(refs[:18]) + (f'; +{len(refs)-18} referências' if len(refs)>18 else ''),
                'Pendências':pending
            })
    sheets['HISTÓRICO POR MATRÍCULA']=pd.DataFrame(summary,columns=[
        'Matrícula','Servidor','Exercícios com ocorrências','O que foi encontrado?',
        'Resumo do histórico','Situação da Base Geral','Providência necessária',
        'Diários e páginas','Pendências'])

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
            if name=='HISTÓRICO POR MATRÍCULA':
                for letter,width in {'A':18,'B':35,'C':26,'D':46,'E':85,'F':44,'G':45,'H':75,'I':58}.items():
                    ws.column_dimensions[letter].width=width
                for row in ws.iter_rows(min_row=2):
                    for cell in row:cell.alignment=Alignment(vertical='top',wrap_text=True)
                    ws.row_dimensions[row[0].row].height=62
            if name=='TORNAR SEM EFEITO':
                obj_col=4
                ws.column_dimensions['D'].width=34
                ws.column_dimensions['P'].width=49
                ws.column_dimensions['Q'].width=76
                for row in ws.iter_rows(min_row=2):
                    cell=row[obj_col-1]
                    is_pending='PENDENTE' in str(cell.value).upper()
                    cell.fill=PatternFill('solid',fgColor='FFF2CC' if is_pending else 'FCE4D6')
                    cell.font=Font(bold=True,color='9C5700' if is_pending else '9C0006')
                    cell.alignment=Alignment(wrap_text=True,vertical='center')
                    row[16].alignment=Alignment(wrap_text=True,vertical='center')
                    ws.row_dimensions[cell.row].height=42
            if ws.max_row>1:ws.auto_filter.ref=ws.dimensions
    return buf.getvalue()

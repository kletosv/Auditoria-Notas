"""Exportação Excel do Robô Formiga. Somente resultados documentais da sessão."""
from io import BytesIO
from datetime import datetime
import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

CATEGORIES = {"INCLUSAO":"INCLUSÃO", "RETIFICACAO":"RETIFICAÇÃO", "REPUBLICACAO":"REPUBLICAÇÃO", "ANULACAO":"ANULAÇÃO", "TORNAR_SEM_EFEITO":"TORNAR SEM EFEITO", "REVOGACAO":"REVOGAÇÃO"}
AUDIT_FIELDS = ["chave","status","DOE","Arquivo","Página","Tipo","Matrícula","Servidor","Ano","Nota na base","Valor extraído do DOE","Nota validada","Código validado","DOE da evidência","Página da evidência","Ato/Edital","Evidência e histórico posterior","Responsável","Data UTC"]

def excel_bytes(docs, hits, differences=None, decisions=None, version="", timeline=None, per_matricula=None):
    """Abas separadas; sem homologação implícita, sem alteração da Base Geral."""
    decisions = decisions or {}
    differences = differences if differences is not None else pd.DataFrame()
    hits = hits.copy()
    if not hits.empty:
        hits = hits.drop(columns=["_doc"], errors="ignore")
    coverage = docs.rename(columns={"numero":"DOE","name":"Arquivo","tipo":"Tipo","pages":"Páginas","done_pages":"Páginas lidas","status":"Situação","error":"Erro"}).drop(columns=["id"],errors="ignore")
    audited = pd.DataFrame(list(decisions.values()), columns=AUDIT_FIELDS)
    corrections = audited[audited["status"] == "CORREÇÃO NECESSÁRIA"].copy() if not audited.empty else audited.copy()
    pending = hits[(hits["Situação"].astype(str).str.contains("PENDENTE|CANDIDATO|INDETERMINADO",case=False,na=False)) | (hits["Ano"].astype(str)=="INDETERMINADO")].copy() if not hits.empty else hits.copy()
    summary = pd.DataFrame([
        ["Versão do motor", version], ["Gerado em", datetime.now().strftime("%d/%m/%Y %H:%M")],
        ["Documentos registrados",len(docs)], ["Documentos com extração concluída",int((docs["status"]=="EXTRACAO CONCLUIDA - REVISAR").sum()) if not docs.empty else 0],
        ["Candidatos à revisão",len(hits)], ["Exercício indeterminado",int((hits["Ano"].astype(str)=="INDETERMINADO").sum()) if not hits.empty else 0],
        ["Diferenças aparentes (não homologadas)",len(differences)],
        ["Decisões manuais registradas",len(audited)], ["Correções indicadas pelo operador",len(corrections)],
        ["Importante","Extração não equivale a validação; conferir ato, cabeçalho, matrícula, exercício, códigos e publicações posteriores."],
        ["Escopo","Somente PDFs do lote carregado nesta execução; não consultar DOE externo automaticamente."],
    ],columns=["Indicador","Valor"])
    sheets = {"RESUMO":summary, "COBERTURA DOE":coverage}
    if per_matricula is not None:
        sheets["CONSOLIDADO MATRÍCULA"] = per_matricula
    if timeline is not None:
        sheets["HISTÓRICO DOCUMENTAL"] = timeline
        sheets["EXERCÍCIO INDETERMINADO"] = timeline[timeline["Exercício"].astype(str)=="INDETERMINADO"].copy()
    for code,label in CATEGORIES.items():
        sheets[label] = hits[hits["Tipo"].astype(str).str.upper()==code].copy() if not hits.empty else hits.copy()
    sheets["OUTRAS OCORRÊNCIAS"] = hits[~hits["Tipo"].astype(str).str.upper().isin(CATEGORIES)].copy() if not hits.empty else hits.copy()
    sheets["PENDÊNCIAS"] = pending
    sheets["DIVERGÊNCIAS APARENTES"] = differences.drop(columns=["_doc","doc","page","matricula","exercicio","_base_num","_pub_num","chave"],errors="ignore")
    sheets["AUDITORIA MANUAL"] = audited
    if timeline is not None and not timeline.empty:
        sheets["ATOS POSTERIORES POSSÍVEIS"] = timeline[timeline["Eventos posteriores possíveis"].astype(str).str.len()>0].copy()
        sheets["ALERTAS INTERPRETAÇÃO"] = timeline[timeline["Alerta de interpretação"].astype(str).str.len()>0].copy()
    sheets["CORREÇÕES CONFERIDAS"] = corrections
    buf=BytesIO()
    with pd.ExcelWriter(buf,engine="openpyxl") as writer:
        for sheet_name,frame in sheets.items():
            frame = frame.copy().fillna("")
            # Matrículas e códigos são identificadores textuais; não converter em números.
            for col in ("Matrícula","Código Cxxx","Código validado", "Código publicado (extração)"):
                if col in frame.columns: frame[col]=frame[col].astype(str)
            frame.to_excel(writer,sheet_name=sheet_name,index=False)
            ws=writer.sheets[sheet_name]
            ws.freeze_panes="A2"
            ws.sheet_view.showGridLines=False
            ws.row_dimensions[1].height=27
            for cell in ws[1]:
                cell.fill=PatternFill("solid",fgColor="183153")
                cell.font=Font(name="Calibri",bold=True,color="FFFFFF",size=11)
                cell.alignment=Alignment(vertical="center")
            for idx,col in enumerate(frame.columns,1):
                if col in ("Trecho","Trecho da publicação","Contexto do ato","Evidência e histórico posterior","fonte_contexto"):
                    width=65
                elif col in ("Servidor","Arquivo","Ato/Edital"):
                    width=37
                elif col in ("Matrícula","Nota na base","Valor extraído do DOE","Nota validada","Código validado"):
                    width=20
                else:
                    width=max(14,min(30,len(str(col))+4))
                ws.column_dimensions[get_column_letter(idx)].width=width
                if col in ("Matrícula","Código validado","Código Cxxx", "Código publicado (extração)"):
                    for row in ws.iter_rows(min_row=2,min_col=idx,max_col=idx):
                        row[0].number_format="@"
            if ws.max_row>1:
                ws.auto_filter.ref=ws.dimensions
                for row in ws.iter_rows(min_row=2):
                    for cell in row:
                        if cell.row%2==0: cell.fill=PatternFill("solid",fgColor="F1F6FA")
    return buf.getvalue()

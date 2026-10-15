"""Dashboard SIDA/ELÚCIDA — apresentação e triagem; Engine 8.0 permanece intacta."""
from pathlib import Path
import hashlib
import io
import json
from datetime import datetime, timezone
import re
import tempfile
import unicodedata

import pandas as pd
import streamlit as st
import engine
from relatorios import excel_bytes
from historico import construir

st.set_page_config(page_title="Auditoria SIDA / ELÚCIDA", page_icon="🐜", layout="wide")
st.markdown("""<style>
.block-container{padding-top:2rem;max-width:1500px}
[data-testid="stMetric"]{border:1px solid rgba(120,120,120,.18);border-radius:12px;padding:14px}
[data-testid="stMetricLabel"]{font-size:.95rem}
</style>""", unsafe_allow_html=True)
st.title("🐜 Auditoria SIDA / ELÚCIDA")
st.caption("Painel de acompanhamento documental • Engine V19 • Histórico V19 • seis abas documentais • localização ≠ validação ≠ conclusão")
st.warning("Os resultados são CANDIDATOS, não correções confirmadas. Não altere a Base Geral com base nesta triagem. O Streamlit Cloud não garante armazenamento persistente e este protótipo não é repositório oficial de dados pessoais.")

# Manter os dados enviados apenas na sessão/instância do aplicativo.
# Não salvar CSV ou PDFs no repositório público do GitHub.
with st.expander("1 · Carregar documentos e executar varredura", expanded=False):
    base_upload=st.file_uploader("Base Geral (CSV)", type=["csv"], accept_multiple_files=False)
    pdf_uploads=st.file_uploader("PDFs do lote a auditar", type=["pdf"], accept_multiple_files=True)
    st.caption("Envie somente o lote pretendido. O motor processa os PDFs em ordem numérica crescente; não consulta o DOE na internet.")
    execute=st.button("▶ Iniciar / retomar extração", type="primary")
    if base_upload is None or not pdf_uploads:
        st.caption("Para iniciar, é necessário que a Base Geral (CSV) e pelo menos um PDF estejam carregados nesta sessão.")

if execute and (base_upload is None or not pdf_uploads):
    st.error("Os arquivos não estão disponíveis nesta sessão. Recarregue o CSV e os PDFs e tente novamente.")
elif execute:
    with st.status("Executando extração documental…", expanded=True) as status:
        try:
            with tempfile.TemporaryDirectory(prefix="sida_") as tmp:
                root=Path(tmp)
                folder=root/"pdfs"
                folder.mkdir()
                base_path=root/"base_geral.csv"
                base_path.write_bytes(base_upload.getvalue())
                seen=set()
                for f in pdf_uploads:
                    data=f.getvalue()
                    digest=hashlib.sha256(data).hexdigest()
                    if digest in seen:
                        continue
                    seen.add(digest)
                    safe=Path(f.name).name
                    (folder/safe).write_bytes(data)
                progress=st.progress(0)
                label=st.empty()
                total=len(seen)
                for idx,(filename,result) in enumerate(engine.run_folder(folder,base_path),start=1):
                    label.write(f"**{filename}** — {result}")
                    progress.progress(min(idx/max(total,1),1.0))
                status.update(label="Extração encerrada — revisão documental necessária",state="complete",expanded=False)
        except Exception as exc:
            status.update(label="Não foi possível concluir a extração",state="error")
            st.error(f"Falha: {type(exc).__name__}: {exc}")

# O connect() da Engine gerencia o esquema e a versão do SQLite.
try:
    con=engine.connect()
    docs=pd.read_sql_query("SELECT id, numero, name, tipo, pages, done_pages, status, error FROM docs ORDER BY numero, CASE tipo WHEN 'PRINCIPAL' THEN 0 WHEN 'SUPLEMENTO' THEN 1 ELSE 2 END, name",con)
    hits=pd.read_sql_query("""SELECT d.numero AS DOE,d.name AS Arquivo,h.page AS Página,
        h.tipo AS Tipo,h.matricula AS Matrícula,h.servidor AS Servidor,
        h.exercicio AS Ano,h.base_valor AS 'Nota na base',h.trecho AS Trecho,
        h.situacao AS Situação,h.doc AS _doc
        FROM hits h JOIN docs d ON d.id=h.doc
        ORDER BY d.numero,h.page,h.matricula,h.exercicio""",con)
    detail=pd.read_sql_query("SELECT doc,page,matricula,exercicio,nota_publicada,codigo,fonte_contexto FROM audit_details",con)
    controlled=pd.read_sql_query("SELECT * FROM retificacoes_controladas ORDER BY doe,matricula",con)
    medias=pd.read_sql_query("SELECT * FROM medias_controladas ORDER BY doe,matricula",con)
    cancelamentos=pd.read_sql_query("SELECT * FROM cancelamentos_controlados ORDER BY doe,matricula",con)
    meta=con.execute("SELECT value FROM meta WHERE key='engine_version'").fetchone()
    con.close()
except Exception as exc:
    st.error(f"Erro ao consultar o banco de dados: {exc}")
    st.stop()

timeline, per_matricula = construir(hits, detail, controlled)
n_complete=int((docs.status=="EXTRACAO CONCLUIDA - REVISAR").sum()) if not docs.empty else 0
n_incomplete=int((docs.status=="PESQUISA INCOMPLETA").sum()) if not docs.empty else 0
n_undetermined=int((hits.Ano.astype(str)=="INDETERMINADO").sum()) if not hits.empty else 0
m1,m2,m3,m4=st.columns(4)
m1.metric("Arquivos registrados",len(docs))
m2.metric("Extração completa",n_complete)
m3.metric("Candidatos à revisão",len(hits))
m4.metric("Exercício indeterminado",n_undetermined)
st.caption(f"Versão registrada: {meta[0] if meta else 'não informada'} • Pesquisa incompleta: {n_incomplete} • Correções homologadas: nenhuma registrada por este protótipo")

tab_docs,tab_hits,tab_compare,tab_audit,tab_history,tab_about=st.tabs(["📚 Cobertura dos DOEs","🔎 Candidatos e filtros","⚖️ Comparação exploratória","🗂️ Auditoria de divergências","🕰️ Histórico por matrícula","ℹ️ Critérios e limites"])
with tab_history:
    st.subheader("Histórico documental por matrícula — preliminar")
    if not controlled.empty:
        st.success(f"Retificações tabulares identificadas no Edital 44/2024: {len(controlled)} matrícula(s). Vigência ainda não confirmada.")
        st.dataframe(controlled.rename(columns={"matricula":"Matrícula","nome_depois":"Servidor","nota_antes":"Onde consta","nota_depois":"Passe a constar","exercicio":"Exercício"}),hide_index=True,use_container_width=True)
    st.warning("A sequência de DOE é apenas cronológica. Não comprova vigência, revogação ou inexistência de atos posteriores. Campos não comprovados permanecem em branco.")
    if per_matricula.empty:
        st.info("Nenhuma ocorrência disponível nesta instância.")
    else:
        pesquisa=st.text_input("Matrícula ou nome do servidor", key="historico_pesquisa")
        filtered_summary=per_matricula.copy()
        if pesquisa:
            m=(filtered_summary["Matrícula"].astype(str)+" "+filtered_summary["Servidor"].astype(str)).str.contains(re.escape(pesquisa),case=False,na=False)
            filtered_summary=filtered_summary[m]
        st.dataframe(filtered_summary,hide_index=True,use_container_width=True)
        selected_mats=filtered_summary["Matrícula"].astype(str).unique().tolist()
        st.dataframe(timeline[timeline["Matrícula"].astype(str).isin(selected_mats)],hide_index=True,use_container_width=True)
with tab_docs:
    st.subheader("Acompanhamento dos DOEs")
    if docs.empty:
        st.info("Nenhum DOE processado nesta instância. Carregue a base e os PDFs acima.")
    else:
        shown=docs.rename(columns={"numero":"DOE","name":"Arquivo","tipo":"Tipo","pages":"Páginas","done_pages":"Páginas lidas","status":"Situação","error":"Erro"})
        st.dataframe(shown[["DOE","Arquivo","Tipo","Páginas","Páginas lidas","Situação","Erro"]],hide_index=True,use_container_width=True,height=420)
        st.download_button("Baixar controle de cobertura (CSV)",shown.drop(columns=["id"]).to_csv(index=False,sep=";").encode("utf-8-sig"),"cobertura_sida.csv","text/csv")
with tab_hits:
    st.subheader("Ocorrências candidatas — não validadas")
    if hits.empty:
        st.info("Nenhum candidato registrado nesta instância.")
    else:
        c1,c2,c3,c4=st.columns(4)
        options=sorted(hits.DOE.dropna().unique().tolist())
        selected=c1.multiselect("DOE",options)
        kinds=c2.multiselect("Tipo de ato",sorted(hits.Tipo.dropna().unique().tolist()))
        years=c3.multiselect("Exercício",sorted(hits.Ano.dropna().astype(str).unique().tolist()))
        query=c4.text_input("Matrícula ou servidor",placeholder="Pesquisar…")
        filtered=hits.copy()
        if selected: filtered=filtered[filtered.DOE.isin(selected)]
        if kinds: filtered=filtered[filtered.Tipo.isin(kinds)]
        if years: filtered=filtered[filtered.Ano.astype(str).isin(years)]
        if query:
            q=unicodedata.normalize("NFKD",query).encode("ascii","ignore").decode().lower()
            searchable=(filtered["Matrícula"].fillna("").astype(str)+" "+filtered["Servidor"].fillna("").astype(str))
            norm=searchable.map(lambda x:unicodedata.normalize("NFKD",x).encode("ascii","ignore").decode().lower())
            filtered=filtered[norm.str.contains(re.escape(q),regex=True)]
        st.caption(f"Exibindo {len(filtered):,} de {len(hits):,} candidatos. A classificação é automática e precisa ser confirmada na fonte.")
        cols=["DOE","Arquivo","Página","Tipo","Matrícula","Servidor","Ano","Nota na base","Trecho","Situação"]
        st.dataframe(filtered[cols],hide_index=True,use_container_width=True,height=500)
        st.download_button("Baixar candidatos filtrados (CSV)",filtered[cols].to_csv(index=False,sep=";").encode("utf-8-sig"),"candidatos_sida_filtrados.csv","text/csv")
with tab_compare:
    st.subheader("Comparação exploratória — não homologada")
    st.info("Só são exibidas diferenças numéricas quando o motor armazenou explicitamente um valor publicado para a mesma matrícula, página e exercício. A correspondência das colunas e o histórico de retificações ainda precisam de revisão humana.")
    if hits.empty or detail.empty:
        st.write("Ainda não há dados suficientes para comparação.")
    else:
        joined=hits.merge(detail,left_on=["_doc","Página","Matrícula","Ano"],right_on=["doc","page","matricula","exercicio"],how="left")
        def numeric(value):
            s=str(value or "").strip().replace(" ","")
            if not re.fullmatch(r"\d{1,3}(?:,\d{1,2}|\.\d{1,2})?",s):return None
            return float(s.replace(",","."))
        joined["_base_num"]=joined["Nota na base"].map(numeric)
        joined["_pub_num"]=joined["nota_publicada"].map(numeric)
        paired=joined[joined._base_num.notna() & joined._pub_num.notna()].copy()
        paired["Diferença aparente"]=paired._pub_num-paired._base_num
        differences=paired[paired["Diferença aparente"].abs()>0.00001].copy()
        display_cols=["DOE","Arquivo","Página","Tipo","Matrícula","Servidor","Ano","Nota na base","nota_publicada","Diferença aparente","Trecho","Situação"]
        if differences.empty:
            st.write("Nenhuma diferença numérica pôde ser calculada com os campos explicitamente armazenados. Isso **não** significa ausência de divergências.")
        else:
            differences=differences.rename(columns={"nota_publicada":"Valor extraído do DOE"})
            display_cols=["Valor extraído do DOE" if x=="nota_publicada" else x for x in display_cols]
            st.metric("Diferenças aparentes para conferência",len(differences))
            st.dataframe(differences[display_cols],hide_index=True,use_container_width=True,height=450)
            st.download_button("Baixar diferenças aparentes (CSV)",differences[display_cols].to_csv(index=False,sep=";").encode("utf-8-sig"),"diferencas_aparentes_sida.csv","text/csv")

# Registro manual de conferência. Não modifica as tabelas da Engine.
# A persistência durável é feita por exportação/importação de CSV; não pelo disco do Streamlit.
AUDIT_FIELDS=["chave","status","DOE","Arquivo","Página","Tipo","Matrícula","Servidor","Ano",
              "Nota na base","Valor extraído do DOE","Nota validada","Código validado",
              "DOE da evidência","Página da evidência","Ato/Edital","Evidência e histórico posterior",
              "Responsável","Data UTC"]
STATUS_OPTIONS=["PENDENTE","CONSISTENTE","CORREÇÃO NECESSÁRIA","INDETERMINADO / ANÁLISE HUMANA"]
if "sida_audit_records" not in st.session_state:
    st.session_state.sida_audit_records={}

def row_key(row):
    # Estável entre reprocessamentos com mesmo arquivo/linha/ano/valor.
    identity=[str(row.get(k,"")) for k in ["Arquivo","Página","Tipo","Matrícula","Ano","Trecho","Valor extraído do DOE"]]
    return hashlib.sha256(json.dumps(identity,ensure_ascii=False).encode("utf-8")).hexdigest()

def audit_csv(records):
    frame=pd.DataFrame(list(records.values()),columns=AUDIT_FIELDS)
    return frame.to_csv(index=False,sep=";").encode("utf-8-sig")

with tab_audit:
    st.subheader("Auditoria de divergências — conferência humana")
    st.info("As decisões abaixo são registros de conferência feitos pelo operador. Não são validações automáticas e não alteram a Base Geral. Para manter o trabalho após reinicializações, baixe o CSV de auditoria e importe-o na próxima sessão.")
    upload_review=st.file_uploader("Restaurar auditoria anterior (CSV exportado por este painel)",type=["csv"],key="sida_review_import")
    if upload_review is not None and st.button("Importar decisões de auditoria",key="sida_review_import_btn"):
        try:
            imported=pd.read_csv(io.BytesIO(upload_review.getvalue()),sep=";",encoding="utf-8-sig",dtype=str,keep_default_na=False)
            if not {"chave","status"}.issubset(imported.columns):
                raise ValueError("CSV sem as colunas obrigatórias chave e status")
            count=0
            for record in imported.to_dict("records"):
                if record["status"] not in STATUS_OPTIONS:
                    continue
                key=record["chave"].strip()
                if not re.fullmatch(r"[0-9a-f]{64}",key):
                    continue
                st.session_state.sida_audit_records[key]={k:str(record.get(k,"")) for k in AUDIT_FIELDS}
                count+=1
            st.success(f"{count} decisões importadas. Confirme se pertencem ao mesmo lote e versão.")
        except Exception as exc:
            st.error(f"Não foi possível importar: {exc}")

    if hits.empty or detail.empty:
        st.warning("Não há candidatos suficientes nesta instância para registrar conferências.")
    else:
        joined_audit=hits.merge(detail,left_on=["_doc","Página","Matrícula","Ano"],right_on=["doc","page","matricula","exercicio"],how="left")
        def parse_num_audit(value):
            value=str(value or "").strip()
            if not re.fullmatch(r"\d{1,3}(?:[,\.]\d{1,2})?",value):
                return None
            return float(value.replace(",","."))
        joined_audit["_base_num"]=joined_audit["Nota na base"].map(parse_num_audit)
        joined_audit["_pub_num"]=joined_audit["nota_publicada"].map(parse_num_audit)
        candidates=joined_audit[joined_audit._base_num.notna() & joined_audit._pub_num.notna()].copy()
        candidates=candidates[(candidates._pub_num-candidates._base_num).abs()>0.00001].copy()
        candidates=candidates.rename(columns={"nota_publicada":"Valor extraído do DOE"})
        candidates["chave"]=candidates.apply(row_key,axis=1)
        candidates=candidates.drop_duplicates(subset=["chave"]).reset_index(drop=True)
        current_keys=set(candidates["chave"])
        records=st.session_state.sida_audit_records
        pending=sum(key not in records or records[key].get("status")=="PENDENTE" for key in current_keys)
        consistent=sum(key in records and records[key].get("status")=="CONSISTENTE" for key in current_keys)
        corrections=sum(key in records and records[key].get("status")=="CORREÇÃO NECESSÁRIA" for key in current_keys)
        a,b,c=st.columns(3)
        a.metric("Ainda pendentes",pending)
        b.metric("Marcadas consistentes",consistent)
        c.metric("Correções registradas pelo operador",corrections)
        st.caption("Contagens relativas aos candidatos desta instância. Uma marcação manual não constitui homologação institucional.")
        search=st.text_input("Localizar matrícula, servidor ou DOE",key="audit_search")
        if search:
            mask=(candidates["Matrícula"].astype(str)+" "+candidates["Servidor"].astype(str)+" "+candidates["DOE"].astype(str)).str.contains(re.escape(search),case=False,na=False)
            candidates=candidates[mask]
        show_cols=["DOE","Página","Tipo","Matrícula","Servidor","Ano","Nota na base","Valor extraído do DOE"]
        st.dataframe(candidates[show_cols].head(500),hide_index=True,use_container_width=True,height=250)
        if not candidates.empty:
            choices=list(candidates.index)
            def label_for(idx):
                r=candidates.loc[idx]
                return f"DOE {r['DOE']} • pág. {r['Página']} • {r['Matrícula']} • {r['Servidor']} • {r['Ano']}"
            chosen=st.selectbox("Selecionar ocorrência para conferir",choices,format_func=label_for,key="audit_select")
            r=candidates.loc[chosen]
            key=r["chave"]
            existing=records.get(key,{})
            st.caption(f"Fonte inicial: {r['Arquivo']} — página {r['Página']} — tipo indicado: {r['Tipo']}")
            st.code(str(r.get("Trecho","")),language=None)
            st.markdown("#### Notas por exercício — associação preliminar")
            st.caption("Os anos e valores são extraídos automaticamente. Confira os cabeçalhos originais antes de decidir. Média do triênio não é nota anual; códigos Cxxx não são convertidos.")
            # Exibe todos os anos localizados na MESMA publicação, página e matrícula.
            same=joined_audit[
                (joined_audit["_doc"].astype(str)==str(r["_doc"])) &
                (joined_audit["Página"].astype(str)==str(r["Página"])) &
                (joined_audit["Matrícula"].astype(str)==str(r["Matrícula"]))
            ].copy()
            if not same.empty:
                same=same.rename(columns={"nota_publicada":"Valor extraído do DOE","codigo":"Código Cxxx"})
                same=same.drop_duplicates(subset=["Ano","Valor extraído do DOE","Código Cxxx","Trecho"])
                same=same.sort_values("Ano")
                cols=["Ano","Valor extraído do DOE","Código Cxxx","Nota na base","Situação"]
                st.dataframe(same[cols].fillna(""),hide_index=True,use_container_width=True)
            st.markdown("#### Histórico localizado da matrícula no lote")
            history=joined_audit[joined_audit["Matrícula"].astype(str)==str(r["Matrícula"])].copy()
            history=history.sort_values(["DOE","Página","Ano"])
            hist_cols=["DOE","Arquivo","Página","Tipo","Ano","Nota na base","nota_publicada","codigo","Situação"]
            history=history.rename(columns={"nota_publicada":"Valor extraído do DOE","codigo":"Código Cxxx"})
            hist_cols=["Valor extraído do DOE" if x=="nota_publicada" else "Código Cxxx" if x=="codigo" else x for x in hist_cols]
            history=history.drop_duplicates(subset=["Arquivo","Página","Tipo","Ano","Valor extraído do DOE","Código Cxxx"])
            st.dataframe(history[hist_cols].fillna(""),hide_index=True,use_container_width=True,height=min(320,85+35*len(history)))
            st.caption("Histórico restrito aos PDFs deste lote. A ordem de publicação não determina, por si só, qual nota prevalece.")
            with st.form("sida_audit_form"):
                current_status=existing.get("status","PENDENTE")
                status=st.selectbox("Resultado da conferência",STATUS_OPTIONS,index=STATUS_OPTIONS.index(current_status) if current_status in STATUS_OPTIONS else 0)
                x,y=st.columns(2)
                valid_note=x.text_input("Nota confirmada no DOE (se aplicável)",value=existing.get("Nota validada",""))
                valid_code=y.text_input("Código confirmado (Cxxx, se aplicável)",value=existing.get("Código validado",""))
                x,y=st.columns(2)
                evidence_doe=x.text_input("DOE da evidência (número e suplemento)",value=existing.get("DOE da evidência",""))
                evidence_page=y.text_input("Página da evidência",value=existing.get("Página da evidência",""))
                act=st.text_input("Ato / edital / publicação",value=existing.get("Ato/Edital",""))
                evidence=st.text_area("Evidência, conferência do cabeçalho e retificações posteriores",value=existing.get("Evidência e histórico posterior",""),height=120)
                reviewer=st.text_input("Responsável pela conferência",value=existing.get("Responsável",""))
                saved=st.form_submit_button("Salvar decisão nesta sessão",type="primary")
            if saved:
                confirmed=status in ("CONSISTENTE","CORREÇÃO NECESSÁRIA")
                if confirmed and not (evidence_doe.strip() and evidence_page.strip() and act.strip() and evidence.strip() and reviewer.strip()):
                    st.error("Para marcar como consistente ou correção necessária, informe DOE, página, ato, evidência e responsável.")
                elif status=="CORREÇÃO NECESSÁRIA" and not (valid_note.strip() or valid_code.strip()):
                    st.error("Para registrar correção necessária, informe a nota ou código documentalmente confirmado.")
                else:
                    records[key]={
                        "chave":key,"status":status,"DOE":str(r["DOE"]),"Arquivo":str(r["Arquivo"]),
                        "Página":str(r["Página"]),"Tipo":str(r["Tipo"]),"Matrícula":str(r["Matrícula"]),
                        "Servidor":str(r["Servidor"]),"Ano":str(r["Ano"]),"Nota na base":str(r["Nota na base"]),
                        "Valor extraído do DOE":str(r["Valor extraído do DOE"]),"Nota validada":valid_note,
                        "Código validado":valid_code,"DOE da evidência":evidence_doe,"Página da evidência":evidence_page,
                        "Ato/Edital":act,"Evidência e histórico posterior":evidence,"Responsável":reviewer,
                        "Data UTC":datetime.now(timezone.utc).isoformat(timespec="seconds")}
                    st.success("Decisão registrada nesta sessão. Baixe o CSV para preservar o histórico.")
    if st.session_state.sida_audit_records:
        all_records=st.session_state.sida_audit_records
        st.download_button("⬇️ Baixar histórico de auditoria (CSV)",audit_csv(all_records),
                           "historico_auditoria_sida.csv","text/csv",key="download_audit_history")
        approved={k:v for k,v in all_records.items() if v.get("status")=="CORREÇÃO NECESSÁRIA"}
        if approved:
            st.download_button("⬇️ Baixar correções registradas (CSV)",audit_csv(approved),
                               "correcoes_registradas_sida.csv","text/csv",key="download_audit_corrections")
        st.caption("O CSV de correções é um registro de decisões humanas, não uma alteração automática da Base Geral.")

# Exportação integral em Excel com uma aba para cada situação de ocorrência.
# Dados desta instância; não inclui PDFs ou informações de outros lotes.
st.divider()
st.subheader("📥 Relatório SIDA — seis abas homologadas")
st.caption("Seis abas: Consolidado, Inclusões, Retificações, Onde Consta e Passe a Constar, Tornar Sem Efeito e Histórico por Matrícula. Inclusões sem comprovação permanecem vazias; não homologar vigência.")
try:
    # A tabela de diferenças é reconstruída somente quando a associação ano/valor existe.
    export_diffs = differences[display_cols].copy() if "differences" in globals() and "display_cols" in globals() and not differences.empty else pd.DataFrame(columns=["DOE","Arquivo","Página","Tipo","Matrícula","Servidor","Ano","Nota na base","Valor extraído do DOE","Diferença aparente","Trecho","Situação"])
    # Ler a Base Geral carregada nesta sessão, inclusive matrículas sem hit no DOE.
    # Não persistir os dados pessoais no repositório ou no arquivo de código.
    base_lookup={}
    if base_upload is not None:
        with tempfile.TemporaryDirectory(prefix='sida_base_') as btmp:
            bpath=Path(btmp)/'base.csv'
            bpath.write_bytes(base_upload.getvalue())
            base_lookup=engine.load_base_csv(bpath)
    export_data = excel_bytes(docs,hits,export_diffs,st.session_state.sida_audit_records,meta[0] if meta else "",timeline=timeline,per_matricula=per_matricula,controlled=controlled,medias=medias,cancelamentos=cancelamentos,base_lookup=base_lookup)
    st.download_button("⬇️ Baixar relatório completo (.xlsx)",data=export_data,file_name="Relatorio_Robo_Formiga_SIDA.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",key="sida_xlsx_full")
except Exception as exc:
    st.error(f"Falha ao gerar o Excel: {type(exc).__name__}: {exc}")

with tab_about:
    st.markdown("""**Regras do painel**

- Os PDFs enviados são a única fonte de extração desta execução; o aplicativo não pesquisa diários externos.
- A leitura é realizada por edição numérica crescente, distinguindo principal, suplemento e extra.
- **Extração concluída** significa leitura automatizada das páginas, não auditoria validada.
- **Candidato** não é correção comprovada. Código `Cxxx` não é convertido automaticamente em nota.
- Para concluir uma divergência é necessário conferir cabeçalho, exercício, matrícula, linha, nota/código, ato anterior e possíveis retificações posteriores.
- Não existe botão de aplicação automática de correções na Base Geral.
- Não publique bases nominais nem PDFs contendo dados pessoais em repositório público.

**Persistência:** o SQLite local pode ser apagado em reinicializações ou redeploys do Streamlit Community Cloud. A nova aba permite exportar e importar decisões de conferência em CSV; o arquivo deve ser mantido em armazenamento privado e seguro. Esta interface não garante armazenamento durável.
""")

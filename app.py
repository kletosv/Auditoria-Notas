"""Dashboard SIDA/ELÚCIDA — apresentação e triagem; Engine 6.0 permanece intacta."""
from pathlib import Path
import hashlib
import re
import tempfile
import unicodedata

import pandas as pd
import streamlit as st
import engine

st.set_page_config(page_title="Auditoria SIDA / ELÚCIDA", page_icon="🐜", layout="wide")
st.markdown("""<style>
.block-container{padding-top:2rem;max-width:1500px}
[data-testid="stMetric"]{border:1px solid rgba(120,120,120,.18);border-radius:12px;padding:14px}
[data-testid="stMetricLabel"]{font-size:.95rem}
</style>""", unsafe_allow_html=True)
st.title("🐜 Auditoria SIDA / ELÚCIDA")
st.caption("Painel de acompanhamento documental • Engine 6.0 • localização ≠ validação ≠ conclusão")
st.warning("Os resultados são CANDIDATOS, não correções confirmadas. Não altere a Base Geral com base nesta triagem. O Streamlit Cloud não garante armazenamento persistente e este protótipo não é repositório oficial de dados pessoais.")

# Manter os dados enviados apenas na sessão/instância do aplicativo.
# Não salvar CSV ou PDFs no repositório público do GitHub.
with st.expander("1 · Carregar documentos e executar varredura", expanded=False):
    base_upload=st.file_uploader("Base Geral (CSV)", type=["csv"], accept_multiple_files=False)
    pdf_uploads=st.file_uploader("PDFs do lote a auditar", type=["pdf"], accept_multiple_files=True)
    st.caption("Envie somente o lote pretendido. O motor processa os PDFs em ordem numérica crescente; não consulta o DOE na internet.")
    execute=st.button("▶ Iniciar / retomar extração", type="primary", disabled=not(base_upload and pdf_uploads))

if execute:
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
    meta=con.execute("SELECT value FROM meta WHERE key='engine_version'").fetchone()
    con.close()
except Exception as exc:
    st.error(f"Erro ao consultar o banco de dados: {exc}")
    st.stop()

n_complete=int((docs.status=="EXTRACAO CONCLUIDA - REVISAR").sum()) if not docs.empty else 0
n_incomplete=int((docs.status=="PESQUISA INCOMPLETA").sum()) if not docs.empty else 0
n_undetermined=int((hits.Ano.astype(str)=="INDETERMINADO").sum()) if not hits.empty else 0
m1,m2,m3,m4=st.columns(4)
m1.metric("Arquivos registrados",len(docs))
m2.metric("Extração completa",n_complete)
m3.metric("Candidatos à revisão",len(hits))
m4.metric("Exercício indeterminado",n_undetermined)
st.caption(f"Versão registrada: {meta[0] if meta else 'não informada'} • Pesquisa incompleta: {n_incomplete} • Correções homologadas: nenhuma registrada por este protótipo")

tab_docs,tab_hits,tab_compare,tab_about=st.tabs(["📚 Cobertura dos DOEs","🔎 Candidatos e filtros","⚖️ Comparação exploratória","ℹ️ Critérios e limites"])
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
with tab_about:
    st.markdown("""**Regras do painel**

- Os PDFs enviados são a única fonte de extração desta execução; o aplicativo não pesquisa diários externos.
- A leitura é realizada por edição numérica crescente, distinguindo principal, suplemento e extra.
- **Extração concluída** significa leitura automatizada das páginas, não auditoria validada.
- **Candidato** não é correção comprovada. Código `Cxxx` não é convertido automaticamente em nota.
- Para concluir uma divergência é necessário conferir cabeçalho, exercício, matrícula, linha, nota/código, ato anterior e possíveis retificações posteriores.
- Não existe botão de aplicação automática de correções na Base Geral.
- Não publique bases nominais nem PDFs contendo dados pessoais em repositório público.

**Persistência:** o SQLite local pode ser apagado em reinicializações ou redeploys do Streamlit Community Cloud. Faça download dos CSVs de acompanhamento; esta interface não garante armazenamento durável.
""")

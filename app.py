import csv, io, sqlite3, time
from pathlib import Path
import streamlit as st
from engine import connect,run_folder,DB
st.set_page_config(page_title="Auditoria SIDA / ELÚCIDA",page_icon="🐜",layout="wide")
st.title("🐜 Auditoria SIDA / ELÚCIDA")
st.caption("Processamento automático dos PDFs locais, em ordem numérica crescente • progresso salvo em SQLite")
st.warning("A extração automática produz CANDIDATOS. Ela NÃO comprova retificações nem valida notas. Cada publicação precisa de conferência humana, inclusive cabeçalho, exercício, código e eventual ato posterior.")
folder=st.text_input("Pasta dos PDFs deste lote (somente os enviados hoje)",value="pdfs")
base=st.text_input("Planilha Base Geral exportada como CSV UTF-8",value="base_geral.csv")
if st.button("▶ Iniciar / retomar varredura",type="primary"):
    if not Path(folder).is_dir():st.error("Pasta de PDFs não encontrada.")
    else:
        progress=st.progress(0);status=st.empty()
        files=list(Path(folder).glob("*.pdf"))
        if not files:st.error("Nenhum PDF encontrado.")
        else:
            for i,(name,result) in enumerate(run_folder(folder,base)):
                status.write(f"{name}: {result}")
                progress.progress(min(1,(i+1)/max(len(files),1)))
            st.success("Varredura disponível concluída. Revise os candidatos antes de marcar DOEs como auditados.")
con=connect()
docs=con.execute("SELECT id,name,numero,tipo,pages,done_pages,status,error FROM docs ORDER BY numero,CASE tipo WHEN 'PRINCIPAL' THEN 0 ELSE 1 END,name").fetchall()
hits=con.execute("SELECT d.numero,d.name,h.page,h.tipo,h.matricula,h.servidor,h.exercicio,h.base_valor,h.trecho,h.situacao FROM hits h JOIN docs d ON d.id=h.doc ORDER BY d.numero,h.page").fetchall()
c1,c2,c3,c4=st.columns(4)
c1.metric("PDFs únicos processados",len(docs))
c2.metric("Extração completa",sum(x[6] in ('EXTRACAO CONCLUIDA - REVISAR','CONCLUIDO') for x in docs))
c3.metric("DOEs auditados e validados",sum(x[6]=='CONCLUIDO' for x in docs))
c4.metric("Candidatos para revisão",len(hits))
if docs:
    st.progress(sum(x[6]=='CONCLUIDO' for x in docs)/len(docs))
    st.subheader("DOEs — ordem crescente")
    st.dataframe([dict(DOE=x[2],Arquivo=x[1],Tipo=x[3],Paginas=x[4],Lidas=x[5],Situacao=x[6],Erro=x[7]) for x in docs],use_container_width=True,hide_index=True)
if hits:
    st.subheader("Ocorrências candidatas (não validadas)")
    fields=["DOE","Arquivo","Página","Tipo","Matrícula","Servidor na base","Exercício candidato","Valor na base","Trecho do PDF","Situação"]
    st.dataframe([dict(zip(fields,row)) for row in hits],use_container_width=True,hide_index=True)
    buf=io.StringIO();writer=csv.writer(buf,delimiter=';');writer.writerow(fields);writer.writerows(hits)
    st.download_button("Baixar candidatos CSV",buf.getvalue().encode('utf-8-sig'),file_name="candidatos_sida.csv",mime="text/csv")
st.info("O painel acompanha automaticamente a leitura de PDFs enquanto este programa estiver aberto e em execução. A confirmação documental final não é automática.")
con.close()

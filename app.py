import csv
import hmac
import io
import tempfile
from pathlib import Path

import streamlit as st
from engine import connect, run_folder

st.set_page_config(page_title='Auditoria SIDA / ELÚCIDA', page_icon='🐜', layout='wide')
st.title('🐜 Auditoria SIDA / ELÚCIDA')

# Fail closed: do not accept sensitive files without an access secret.
try:
    password = st.secrets.get('APP_PASSWORD', '')
except Exception:
    password = ''
if not password:
    st.error('Acesso ainda não configurado. No Streamlit, abra App settings → Secrets e defina APP_PASSWORD = "uma-senha-forte". Não envie arquivos até concluir.')
    st.stop()
if not st.session_state.get('authenticated', False):
    with st.form('login'):
        entered = st.text_input('Senha de acesso', type='password')
        submitted = st.form_submit_button('Entrar')
    if submitted:
        if hmac.compare_digest(entered, str(password)):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error('Senha incorreta.')
    st.stop()

st.warning('A extração identifica candidatos; não comprova alterações de notas. O servidor do Streamlit não é armazenamento permanente. Não use este protótipo como repositório oficial de dados pessoais.')
base_file = st.file_uploader('Base Geral (CSV UTF-8)', type=['csv'])
pdfs = st.file_uploader('PDFs do lote de hoje', type=['pdf'], accept_multiple_files=True)
if st.button('▶ Iniciar / retomar varredura', type='primary', disabled=not(base_file and pdfs)):
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp) / 'pdfs'
        folder.mkdir()
        base_path = Path(temp) / 'base_geral.csv'
        base_path.write_bytes(base_file.getvalue())
        for i, file in enumerate(pdfs):
            safe_name = Path(file.name).name
            if safe_name.lower().endswith('.pdf'):
                (folder / f'{i:03d}_{safe_name}').write_bytes(file.getvalue())
        progress = st.progress(0)
        status = st.empty()
        for i, (name, result) in enumerate(run_folder(folder, base_path)):
            status.write(f'{name}: {result}')
            progress.progress((i + 1) / len(pdfs))
        st.success('Extração encerrada. Os resultados precisam de revisão documental.')

con = connect()
docs = con.execute('SELECT numero,name,tipo,pages,done_pages,status,error FROM docs ORDER BY numero,name').fetchall()
hits = con.execute('SELECT d.numero,d.name,h.page,h.tipo,h.matricula,h.servidor,h.exercicio,h.base_valor,h.trecho,h.situacao FROM hits h JOIN docs d ON d.id=h.doc ORDER BY d.numero,h.page').fetchall()
a,b,c = st.columns(3)
a.metric('Arquivos registrados',len(docs))
b.metric('Extração completa',sum(r[5] in ('EXTRACAO CONCLUIDA - REVISAR','CONCLUIDO') for r in docs))
c.metric('Candidatos à revisão',len(hits))
if docs:
    st.subheader('Acompanhamento dos DOEs')
    st.dataframe([dict(zip(['DOE','Arquivo','Tipo','Páginas','Páginas lidas','Situação','Erro'],r)) for r in docs],hide_index=True,use_container_width=True)
if hits:
    st.subheader('Ocorrências candidatas — não validadas')
    columns=['DOE','Arquivo','Página','Tipo','Matrícula','Servidor','Ano','Nota na base','Trecho','Situação']
    st.dataframe([dict(zip(columns,r)) for r in hits],hide_index=True,use_container_width=True)
    output=io.StringIO()
    writer=csv.writer(output,delimiter=';')
    writer.writerow(columns)
    writer.writerows(hits)
    st.download_button('Baixar candidatos CSV',output.getvalue().encode('utf-8-sig'),file_name='candidatos_sida.csv',mime='text/csv')
con.close()

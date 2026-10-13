"""Teste documental controlado, não substitui o motor do Streamlit.
Uso: python teste_controlado.py caminho/para/DOE_11575.pdf
Extrai o Edital 44/2024 e compara as tabelas Onde consta/Passe a constar.
"""
import re, sys, csv, pathlib
import fitz

def extrair(pdf):
    doc=fitz.open(pdf)
    texto='\n'.join(p.get_text() for p in doc)
    inicio=texto.find('EDITAL N. 44/2024')
    fim=texto.find('EDITAL N. 45/2024', inicio)
    if inicio<0 or fim<0: raise ValueError('Não foi possível delimitar o Edital 44/2024.')
    trecho=texto[inicio:fim]
    a=re.search(r'Onde consta\s*:',trecho,re.I)
    b=re.search(r'Passe a constar\s*:',trecho,re.I)
    if not a or not b: raise ValueError('Não foram encontradas ambas as tabelas.')
    def linhas(t):
        # O texto do PDF pode quebrar o nome em linhas; detectar matrícula e valor final por bloco.
        partes=re.split(r'(?m)^\s*(\d{7,11})\s*$',t)
        saida={}
        for j in range(1,len(partes),2):
            matricula=partes[j].strip(); bloco=partes[j+1]
            nota=re.search(r'(?m)^\s*(\d{1,3},\d{2}|C\d{3})\s*$',bloco)
            if not nota: continue
            nome=' '.join(x.strip() for x in bloco[:nota.start()].splitlines() if x.strip())
            if nome: saida[matricula]=(nome,nota.group(1))
        return saida
    antes=linhas(trecho[a.end():b.start()]); depois=linhas(trecho[b.end():]); registros=[]
    for m in sorted(set(antes)|set(depois)):
        ant=antes.get(m); pos=depois.get(m)
        registros.append({'matricula':m,'nome_antes':ant[0] if ant else '', 'nome_depois':pos[0] if pos else '',
          'exercicio':'2022','nota_antes':ant[1] if ant else '', 'nota_depois':pos[1] if pos else '',
          'alterou_nota': 'SIM' if ant and pos and ant[1]!=pos[1] else 'NAO' if ant and pos else 'PENDENTE',
          'doe':'11.575','data_publicacao':'05/08/2024','edital':'44/2024','pagina':'16-17',
          'vigencia':'NAO CONFIRMADA - PESQUISAR ATOS POSTERIORES'})
    return registros

if __name__=='__main__':
    if len(sys.argv)<2: raise SystemExit('Informe o caminho do PDF')
    rows=extrair(sys.argv[1]);dest=pathlib.Path(__file__).with_name('teste_edital_44_2024.csv')
    with dest.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print('Linhas:',len(rows),'Arquivo:',dest)
    for row in rows:print(row['matricula'],row['nota_antes'],'->',row['nota_depois'])

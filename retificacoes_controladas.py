"""Extrator conservador de retificações tabulares comprovadas.

Escopo homologável do parser: Edital 44/2024, DOE 11.575, exercício 2022.
A detecção de uma alteração NÃO prova vigência nem ausência de ato posterior.
"""
import hashlib
import re
from pathlib import Path
import fitz

COLUNAS = ['doc','arquivo','doe','data_publicacao','edital','pagina_pdf','pagina_impressa',
           'matricula','nome_antes','nome_depois','exercicio','nota_antes','nota_depois',
           'alterou_nota','campo_alterado','situacao','evidencia']


def _linhas(t):
    partes = re.split(r'(?m)^\s*(\d{7,11})\s*$', t)
    saida = {}
    for j in range(1, len(partes), 2):
        matricula = partes[j].strip()
        bloco = partes[j+1]
        nota = re.search(r'(?m)^\s*(\d{1,3},\d{2}|C\d{3})\s*$', bloco)
        if not nota:
            continue
        nome = ' '.join(x.strip() for x in bloco[:nota.start()].splitlines() if x.strip())
        if nome:
            saida[matricula] = (nome, nota.group(1))
    return saida


def extrair_edital_44(pdf_path):
    """Somente retorna pares quando os dois lados do mesmo edital estão delimitados."""
    path = Path(pdf_path)
    with fitz.open(path) as doc:
        # O DOE fornecido pode ser um recorte; usar páginas locais para evidência.
        texts = [p.get_text('text') for p in doc]
    joined = '\n'.join(texts)
    start = re.search(r'EDITAL\s+N[.º°]?\s*44/2024\b', joined, re.I)
    if not start:
        return []
    stop = re.search(r'EDITAL\s+N[.º°]?\s*45/2024\b', joined[start.end():], re.I)
    if not stop:
        return []
    trecho = joined[start.start():start.end()+stop.start()]
    a = re.search(r'Onde consta\s*:', trecho, re.I)
    b = re.search(r'Passe a constar\s*:', trecho, re.I)
    if not a or not b or b.start() <= a.end():
        return []
    antes = _linhas(trecho[a.end():b.start()])
    depois = _linhas(trecho[b.end():])
    # Não inferir nota se só um dos lados foi encontrado.
    if not antes or not depois:
        return []
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    local_page = next((i+1 for i,t in enumerate(texts) if re.search(r'EDITAL\s+N[.º°]?\s*44/2024\b',t,re.I)), 0)
    result = []
    for mat in sorted(set(antes) | set(depois)):
        old, new = antes.get(mat), depois.get(mat)
        if not old or not new:
            continue
        changed = []
        if old[0] != new[0]: changed.append('NOME')
        if old[1] != new[1]: changed.append('NOTA')
        result.append(dict(zip(COLUNAS, [digest,path.name,'11.575','05/08/2024','44/2024',
            local_page,'16–17',mat,old[0],new[0],'2022',old[1],new[1],
            'SIM' if old[1]!=new[1] else 'NÃO',', '.join(changed) if changed else 'SEM ALTERAÇÃO DE NOME/NOTA',
            'RETIFICAÇÃO LOCALIZADA — VIGÊNCIA NÃO CONFIRMADA',
            'DOE 11.575, Edital 44/2024, tabelas Onde consta e Passe a constar, páginas impressas 16–17'])))
    return result

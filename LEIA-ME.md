# Robô Formiga — Atualização 16 (incremental e conservadora)

## Arquivos
Substituir `app.py`, `engine.py`, `historico.py`, `relatorios.py`, `retificacoes_controladas.py` e adicionar `medias_controladas.py`. Não substituir a Base Geral. Manter `requirements.txt` existente (fitz/PyMuPDF, pandas, openpyxl, streamlit).

## O que foi implementado
- Excel com seis abas homologadas, sem abas extras.
- Consolidado com notas extraídas individualizadas e natureza documental explícita; não presume vigência.
- Inclusões: **somente omissões documentalmente comprovadas**; como o motor ainda não verifica a publicação anterior, a aba fica vazia. Candidatos permanecem no histórico.
- Retificações: compara Base Geral quando identificável e os valores do Edital 44/2024.
- Onde Consta e Passe a Constar: leitor **validado apenas para o formato do Edital 58/SED/2025, DOE 11.960**, ciclo 2021–2023, com composição anterior/corrigida e médias.
- Tornar sem efeito: lista candidatos com alcance não comprovado, sem convertê-los em anulação.
- Histórico por matrícula: preserva eventos candidatos e inclui retificações de médias como eventos próprios de triênio.

## Limites
A extração automática do Edital 58 não é generalizada para todos os diários. A pesquisa de publicações posteriores não está concluída. Não homologar nota vigente, omissão ou efeito jurídico a partir do relatório. A versão muda o esquema da base SQLite local e requer nova extração dos PDFs; salve antes o relatório e decisões manuais.

## Teste de referência
DOE 11.960/2025, Edital 58/SED/2025, matrícula 106286021: 2021 0,00→C002; 2022 0,00→70,00; 2023 80,33→80,33; média 26,78→75,17.

# Robô Formiga — V19.1 (candidata a testes)

Atualização incremental da V19. Não homologada; não modifica a Base Geral.

## O que foi corrigido
- Novo módulo `cancelamentos_controlados.py`: identifica despachos com texto expresso **TORNAR SEM EFEITO**, edital anterior, DOE original, matrícula e valores na mesma linha. O leitor não contém filtro fixo por número de DOE.
- O motor armazena as extrações controladas em tabela própria, separadas das ocorrências candidatas.
- A aba **TORNAR SEM EFEITO** apresenta o objeto limitado à **parte do edital que publicou a nota**, sem inferir cancelamento de outros atos ou vigência atual.
- O **HISTÓRICO POR MATRÍCULA** acrescenta, quando disponível, um resumo dos cancelamentos identificados.
- Matrículas 43496021 e 43496024: permanece **PENDENTE DE AVALIAÇÃO DOCUMENTAL**, pois o ato declara 2020 e o cabeçalho informa Nota 2019.

## Validação técnica realizada
- Compilação de todos os arquivos Python.
- Leitura do PDF fornecido do DOE 11.883: seis matrículas em quatro despachos, identificando a divergência das duas matrículas.
- Exportação experimental das seis abas com registros controlados de cancelamento.

## Limites
- A extração controlada reconhece um formato específico de despacho e não é universal para todos os editais ou PDFs.
- **Não houve processamento integral dos 47 PDFs** nesta rodada nem verificação exaustiva de publicações posteriores.
- O número de páginas do cancelamento corresponde à página PDF; verificar paginação impressa no documento.
- A inclusão permanece candidata; a vigência final permanece pendente.
- A aba Histórico só traz os novos dados após reprocessar os PDFs com esta versão.

## Instalação
Substituir os arquivos Python do repositório pelos **sete** `.py` deste pacote; manter o `requirements.txt` atual (`streamlit`, `pandas`, `PyMuPDF`, `openpyxl`). Faça backup. Recarregue Base Geral e PDFs no Streamlit e execute novo processamento. A alteração de versão reinicia a triagem no banco local; o Streamlit Cloud pode não persistir os dados entre sessões.

# Robô Formiga — V19 (candidata a testes)

## Entrega
Atualização do código-fonte Streamlit. **Não homologada documentalmente.** A Base Geral não é alterada.

## Alterações
- Versão do motor elevada para 9.0, com leitura de anos até 2025; processamento de PDFs por lote sem filtro por DOE 11.883. O código V18 já não tinha filtro explícito por esse número.
- INCLUSÕES passa a receber **candidatos** detectados, devidamente marcados PENDENTE, sem presumir inclusão oficial, situação final da Base ou providência automática.
- TORNAR SEM EFEITO inclui no resumo referências textuais a editais/DOE detectadas no contexto do ato, como **indícios para conferência**, sem inventar o objeto cancelado.
- HISTÓRICO POR MATRÍCULA inclui exemplos de retificações anuais controladas com exercício, valor anterior, valor posterior e DOE, além dos exemplos de médias já existentes.
- Corrigida repetição de comandos de limpeza no reset de base.

## Limitações e testes obrigatórios
- O leitor controlado de retificações continua restrito ao Edital 44/2024; o de médias, ao Edital 58/SED/2025. Outros formatos não estão homologados.
- Referências textuais não comprovam vínculo entre atos, vigência ou ausência de publicações posteriores.
- Inclusões não são classificadas como confirmadas até identificação do objeto e confronto documental.
- A pesquisa depende exclusivamente dos PDFs enviados. A cobertura integral do DOE e suplementos deve ser conferida separadamente.
- A divergência das matrículas 43496021 e 43496024 continua PENDENTE DE AVALIAÇÃO DOCUMENTAL.
- Testar com lote sem DOE 11.883 e depois com lote completo; conferir as seis abas e comparar com os PDFs originais.

## Instalação
Substitua os seis arquivos `.py` no projeto GitHub/Streamlit pelos seis deste pacote, preservando seu `requirements.txt` (streamlit, pandas, PyMuPDF, openpyxl). Faça backup da V18. Ao mudar a versão do motor, os candidatos anteriores do SQLite são arquivados e a triagem é reiniciada. Não publique CSVs nominais ou PDFs em repositório público.

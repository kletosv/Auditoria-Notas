# Robô Formiga — V19.2 candidata a testes (15/10/2026)

## Correção principal: aba INCLUSÕES
- A coluna D deixa de repetir apenas “PENDENTE”: descreve o indício de objeto e exercício **somente quando** existe valor único extraído, exercício explícito e menção a inclusão de nota no contexto. Caso contrário explica a insuficiência. **Não é confirmação documental.**
- A coluna H compara o valor candidato à Base quando há elementos suficientes, rotulando COINCIDE/DIVERGE **COM VALOR CANDIDATO**. Sem vínculo/ano confiável, fica pendente.
- A coluna F **não recomenda alteração** antes de confirmar edital, linha, objeto, vínculo, elegibilidade e atos posteriores.
- A coluna G mantém DOE/página; novas colunas incluem arquivo, ID de evento, contexto do ato, critério e valor candidato.
- A coluna I distingue evento posterior possível de ausência de prova no lote.
- Retificações de média não devem ser homologadas como inclusões; candidatos ambíguos ficam expressamente sinalizados.

## Mantido da V19.1
- Seis abas, leitores de retificações, médias e cancelamentos, inclusive DOE 11.883 sem filtro fixo.
- Matrículas 43496021/43496024: **PENDENTE DE AVALIAÇÃO DOCUMENTAL**.
- A Base Geral não é alterada.

## Limites importantes
- Esta é uma atualização conservadora de **triagem**, não um leitor universal de editais de inclusão. Não conclui vigência nem a inexistência de atos posteriores.
- Os 979 registros candidatos não equivalem a 979 inclusões confirmadas.
- Não houve execução integral com os 47 PDFs nesta atualização.
- Uma nova versão de motor força reprocessamento do lote no banco SQLite.

## Instalação
Faça backup e substitua os sete arquivos `.py` do GitHub pelos do ZIP; mantenha `requirements.txt` (`streamlit`, `pandas`, `PyMuPDF`, `openpyxl`). Recarregue Base Geral e PDFs, execute a extração e baixe o Excel.

# Robô Formiga — V19.3 candidata a testes (19/10/2026)

## Evolução da aba INCLUSÕES
- A triagem passa a registrar indícios textuais de objeto (nota/pontuação, código, média/período, matrícula e identificação do servidor) em coluna própria.
- Cada linha recebe uma justificativa objetiva da pendência e sinalização de confiabilidade formal do exercício extraído.
- Esses rótulos são **indícios do texto**, não comprovação de inclusão nem autorização para alterar a Base Geral.
- A coluna “O que foi incluído?” passa a explicitar os indícios encontrados mesmo quando não há associação segura com matrícula/exercício/valor.

## Limites
- Não é um extrator universal; layout de tabela, cabeçalho, ato anterior e linha individual ainda exigem validação documental.
- Os 979 candidatos não equivalem a 979 inclusões comprovadas.
- Não foi executado o lote completo dos 47 PDFs nesta atualização.
- A Base Geral permanece sem alterações automáticas.

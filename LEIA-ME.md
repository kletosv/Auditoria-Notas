# Robô Formiga — Atualização 17 (consolidada para teste)

Esta versão SUBSTITUI a atualização 17 anterior (ainda não publicada). Faça backup do repositório antes de substituir os arquivos.

## Atualizações incluídas
- Preserva correções da versão 17 anterior: busca direta da nota na Base Geral CSV; exercícios indeterminados sinalizados; atos de tornar sem efeito permanecem candidatos sem prova do alcance.
- RETIFICAÇÕES: mantém matrícula, servidor, exercício; acrescenta campo alterado, nota da Base, nota retificada, DOE da alteração, alteração posterior, DOE posterior, status de correção da Base. Preserva colunas de origem, edital, página, notas anteriores e observação. Normaliza representação numérica na comparação, sem declarar vigência.
- INCLUSÕES: prepara as 15 colunas aprovadas, incluindo natureza, Base atual, resultado esperado, DOE, inclusão já na Base, posterioridade, situação, providência, cargo, vínculo e histórico. Continua VAZIA enquanto não existir comprovação da omissão na publicação original; não inventa inclusão.
- HISTÓRICO POR MATRÍCULA: agora é um resumo por matrícula, com contagem de eventos, tipos, notas candidatas, DOE/páginas e pendências. O vínculo não é inferido quando a fonte não o contém. A data exata de cada evento depende da fonte e não é inventada.
- Preserva seis abas, inclusive ONDE CONSTA E PASSE A CONSTAR.

## Limitações relevantes
- Ainda NÃO existe pesquisa exaustiva automática de atos posteriores. Por isso, as colunas de SIM/NÃO referentes à vigência posterior ficam PENDENTE, mesmo quando a nota da Base coincide com a retificação.
- O histórico executivo não substitui a trilha de eventos; referências são limitadas ao lote processado. Eventos com vínculos distintos da mesma matrícula não podem ser separados sem informação de vínculo.
- O parser de inclusão documental e prova de omissão ainda precisa ser implementado e testado com editais específicos.
- Não recalcular nem substituir automaticamente médias de triênio, quadriênio ou quinquênio.
- O arquivo XLSX de teste contém dados de teste controlado e NÃO constitui auditoria do DOE.

## Instalação
Substitua os seis arquivos .py no GitHub pelos arquivos do ZIP (app.py, engine.py, historico.py, relatorios.py, retificacoes_controladas.py, medias_controladas.py). Preserve requirements.txt. Faça novo upload da Base Geral e dos PDFs e gere um novo relatório.

## Revisão da aba TORNAR SEM EFEITO (versão 17)
- Coluna D: **O que foi tornado sem efeito?** em destaque visual (laranja/vermelho para objeto comprovado; amarelo para PENDENTE DE IDENTIFICAÇÃO).
- Exibe separadamente objeto, valor atingido, DOE original, DOE de cancelamento, página, motivo, publicações posteriores, situação da Base, providência e resumo explicativo.
- **Não presume** que um ato genérico atingiu uma NOTA ou MÉDIA; só usa objeto comprovado por campo documental explícito.
- Uma retificação tornada sem efeito não cancela automaticamente a nota original.
- Não inventa datas, páginas, valores ou situação de vigência; quando ausentes, campos permanecem vazios ou PENDENTE.
- A extração automatizada do objeto/ato original ainda precisa de validação documental; esta revisão melhora a apresentação e preserva a segurança das conclusões.

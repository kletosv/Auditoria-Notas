# Robô Formiga V19.5 — candidata a testes

## Objetivo
Ampliar a varredura de retificações para todos os PDFs processados (Diários principais, suplementos e extras), em vez de executar o leitor especializado somente quando o número do DOE é 11.575.

## Alterações
- Corrigida a atribuição da página PDF: agora é calculada pela posição exata do marcador no texto concatenado, evitando associar ocorrências repetidas à primeira página que contém a mesma expressão.
- A chave de deduplicação preserva a posição da ocorrência para reduzir a fusão de eventos distintos no mesmo ato.
- `retificacoes_controladas.py`: novo `extrair_retificacoes()` procura pares textuais “Onde consta” / “Passe a constar” em todos os PDFs, identifica matrículas comuns aos dois lados e registra o DOE inferido do nome do arquivo, página PDF, edital próximo e valores anterior/novo.
- `engine.py`: chama o extrator em cada PDF e atualiza a versão do motor para reconstruir os dados derivados, evitando misturar resultados da lógica anterior.
- Mantém as seis abas e os outros módulos da V19.3.

## Limites e cautelas
- Esta é uma varredura de **candidatos**, não um extrator universal nem uma conclusão jurídica.
- O pareamento depende de texto extraível e de estrutura compatível com “Onde consta” / “Passe a constar”. Retificações com outros formatos, imagens escaneadas ou tabelas fragmentadas podem não ser detectadas.
- “Exercício” pode ficar `INDETERMINADO`; não atribuir valor a um ano sem evidência local suficiente.
- Não confirma vigência, efeito jurídico, vínculo funcional ou ausência de publicação posterior.
- A Base Geral não é alterada automaticamente.
- O caso de regressão do DOE 11.575 / Edital 44/2024 deve ser conferido após o processamento completo; o teste inicial encontrou outros editais nesse mesmo Diário, evidenciando que a cobertura anterior era estreita.

## Instalação
1. Faça uma cópia dos arquivos atuais do projeto.
2. Substitua os sete arquivos `.py` pelos arquivos deste pacote.
3. Mantenha o `requirements.txt` já usado pelo projeto.
4. Reprocesse os PDFs e a Base Geral para reconstruir os dados com a nova versão do motor.
5. Compare a aba RETIFICAÇÕES com os Diários fonte antes de qualquer uso operacional.

## Testes realizados nesta preparação
- Correção da lógica de mapeamento página-texto revisada.
- A compilação sintática deve ser executada após instalação no ambiente do projeto.
- Não foi realizada nova varredura dos 47 PDFs nesta preparação.
- Não homologada; a cobertura completa e os falsos positivos/negativos ainda precisam de validação documental.

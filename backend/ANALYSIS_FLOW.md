# Fluxo determinístico e reconciliação de tentativas

- EAN: OFF → validação dos ingredientes → regras alimentares → avaliação quantitativa e observações verificadas → persistência → HTTP. A análise funciona sem Gemini e nunca usa ausência de conflito como garantia de segurança.
- `gemini_enrichment_enabled` é falso por padrão. Quando habilitado, apenas reordena explicações já verificadas, com limite padrão de 3 s, máximo de 10 s. Falhas, respostas inválidas e respostas tardias preservam o resultado local. Duas chamadas opcionais podem permanecer em execução por processo; saturação retorna imediatamente o resultado local. Essas threads não acessam o banco.
- O SDK recebe timeout explícito e uma tentativa; o limite de espera da análise opcional é aplicado também pelo chamador, independentemente do comportamento do SDK. A extração por foto continua exigindo leitura da imagem antes de existir um produto estruturado; não se inventa um produto quando a extração falha.
- O cache inclui a nova versão do fluxo e a configuração de enriquecimento, além de produto, perfil e versões das regras. Um lock por chave evita processamento simultâneo duplicado no mesmo processo. A chave única no PostgreSQL impede linhas de análise duplicadas entre processos; o lock em memória não é uma garantia distribuída contra chamadas externas duplicadas.

## Associação e compatibilidade

A migração aditiva `20261117000000_link_capture_analysis` cria `request_id`, `analysis_id`, `analysis_origin` e `processing_status` em `product_captures`. **Ela deve ser aplicada por um responsável antes de implantar este backend. Não é executada automaticamente.** Nenhum vínculo é inferido para capturas antigas.

O POST aceita `request_id` opcional (UUID). EAN reserva a tentativa antes da consulta externa e repetições do mesmo UUID/produto retornam a mesma tentativa. `GET /profiles/{id}/captures/requests/{request_id}` consulta somente a tentativa daquele usuário. Estados: `pending`, `completed`, `failed`; capturas legadas sem associação retornam `unlinked`. Uma tentativa não encontrada ainda não comprova que a requisição original terminou.

`analysis_origin` informa `generated` ou `cache`. O histórico usa exclusivamente `analysis_id`, nunca a última análise do produto. As análises legadas continuam em `/history/analyses`; não são apagadas ou atribuídas a capturas novas. O produto no histórico ainda referencia o cadastro do produto, sem snapshot imutável por captura.

Os campos anteriores continuam presentes, e os novos são aditivos. O Android envia um UUID estável durante recriação da tela, reconcilia falhas de rede/5xx ou respostas pendentes por até 6 s, sem reenviar o POST, e mantém resultado não confirmado separado de falha definitiva. Resultados de outras tentativas nunca são usados como substitutos.

## Testes com PostgreSQL

O worker confirma `current_database() = 'nutriIA_test'` antes das gravações. Quando necessário, cria as novas colunas apenas dentro da transação de teste, com rollback de DDL e dados; não executa o arquivo de migração nem altera a tabela de versões Prisma. O teste compara as colunas antes/depois para confirmar o rollback.

`NUTRIIA_AUDIT_REAL_OFF=1` ativa medições explícitas de Ninho/Miojo com OFF real; normalmente OFF/Gemini são simulados. O benchmark não chama Gemini nem modifica produção.

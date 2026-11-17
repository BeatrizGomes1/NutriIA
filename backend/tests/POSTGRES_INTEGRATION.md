# Integracao HTTP + PostgreSQL

Executar na raiz do repositorio, em PowerShell:

```powershell
$env:NUTRIIA_RUN_DB_TESTS = '1'
backend/.venv/Scripts/python.exe -m pytest backend/tests -q -p no:cacheprovider
```

Sem a flag, somente o cenario de PostgreSQL e ignorado. O teste de validacao
da URL continua ativo e nao abre conexoes.

O teste prefere NUTRIIA_TEST_DATABASE_URL, quando fornecida no ambiente.
Essa URL deve apontar exatamente para nutriIA_test. Caso contrario, usa as
credenciais da DATABASE_URL do ambiente ou le a DATABASE_URL de backend/.env,
substituindo o nome do banco por nutriIA_test antes de iniciar o subprocesso.
Nenhuma conexao e aberta para o banco de origem e nenhum .env e modificado.
URLs e credenciais nunca sao impressas pelo teste.

O subprocesso recebe DATABASE_URL antes de importar qualquer modulo da aplicacao.
Ele valida o nome na URL e SELECT current_database() antes de importar app.main.
Cada INSERT/UPDATE e precedido por nova verificacao de current_database(); qualquer
outro banco interrompe o cenario. DDL e comandos destrutivos sao rejeitados.
As tres migracoes existentes devem estar previamente aplicadas; o teste nao cria
bancos, tabelas ou executa migracoes.

Servicos de autenticacao, perfis, workflow, cache e persistencia sao reais. Somente
a fabrica de sessoes e direcionada a uma conexao PostgreSQL protegida por uma
transacao externa, com savepoints para os commits dos servicos. Ao final, rollback
reverte todo o cenario, inclusive eventual atualizacao de produto preexistente.
O teste confirma que o usuario nao permanece e que o produto anterior foi restaurado.

OFF usa httpx.MockTransport para uma fixture representativa de Nutella com EAN
3017620422003 e leite em po. Isso valida o adaptador sem depender do cadastro remoto.
O Gemini tem resposta favoravel simulada: o endpoint deve dispensar sua chamada
quando existe conflito confirmado. O teste tambem gera essa resposta pela funcao
real de construcao do prompt e a envia ao parser real, confirmando not_recommended.
Nao ha chamada externa ao Gemini ou ao OFF neste cenario.

Verificacoes: cadastro, hash de senha, login, assinatura/validade dos tokens,
rejeicao sem Bearer, auth/me, captura EAN, evidencia do derivado lacteo, nutrientes,
registro da analise/capturas, hash do refresh token, cache, historico e rollback.
Erros do worker sao apresentados com fase, tipo e SQLSTATE quando disponivel,
sem traceback, SQL, parametros, senhas, tokens ou URLs.

Este teste habilita a continuidade dos testes Android para esses contratos.
Nao comprova conectividade do dispositivo, transporte HTTPS, captura por foto,
servicos externos ao vivo ou todos os cenarios de alergia.


O cenario quantitativo troca muscle_gain por weight_loss para o mesmo produto,
verifica proteinas, calorias/fibras, invalida cache pelo perfil e consulta o historico.
As linhas temporais de analises/capturas recebem horarios UTC na sessao de teste:
o now() do PostgreSQL seria identico para todos os savepoints da transacao externa,
ao contrario das transacoes independentes dos servicos em producao. Nao ha mudanca
na geracao de timestamps da aplicacao.

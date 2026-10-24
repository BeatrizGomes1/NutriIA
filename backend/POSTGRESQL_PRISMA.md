# PostgreSQL e Prisma Migrate

## O que esta estrutura cria

- `user_profiles`: perfil, objetivo e termos alimentares declarados.
- `products`: catálogo compartilhado por EAN, com dados do rótulo e da fonte.
- `product_captures`: histórico de cada captura por usuário, inclusive quando o produto não foi encontrado.
- `analysis_results`: resultados personalizados por usuário e produto.
- `ingredient_matches`: ingredientes e evidências associados a cada análise.

`products.ean` é único quando informado. Assim, capturas diferentes podem apontar para o mesmo produto e reutilizar os dados do catálogo. A análise pertence a um usuário, não ao catálogo global. `analysis_results.cache_key` é uma chave opcional única: futuramente a camada Python pode gerar um SHA-256 com o ID do usuário, produto normalizado, perfil relevante e versões do prompt/modelo e buscar a análise antes de chamar a IA. Incluir o usuário evita reutilizar análises personalizadas entre contas. A migração prepara o campo e a restrição, mas ainda não implementa essa lógica de aplicação.

## Pré-requisitos

- Node.js e npm;
- PostgreSQL instalado ou acessível;
- uma base vazia chamada `nutriia` (pode ser criada no pgAdmin ou com `CREATE DATABASE nutriia;`).

## Configuração e primeira migração (PowerShell)

Execute os comandos abaixo a partir da pasta `backend`:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edite `backend/.env` e adicione a URL do banco, sem substituir as variáveis existentes:

```env
DATABASE_URL="postgresql://USUARIO:SENHA@localhost:5432/nutriia?schema=public"
```

Substitua `USUARIO` e `SENHA` pelos dados locais do PostgreSQL. Não compartilhe nem versione o `.env`.

Instale as ferramentas Prisma e valide o schema:

```powershell
npm install
npm run db:validate
```

Aplique a migração versionada e confira o estado:

```powershell
npm run db:migrate
npm run db:status
```

O `migrate dev` pode pedir um nome de migração se detectar alterações novas. A migração inicial já está em `prisma/migrations/20261017000000_init_nutriia/`.

Para inspecionar as tabelas visualmente:

```powershell
npm run db:studio
```

## Migrações futuras e produção

Quando o schema mudar durante o desenvolvimento, use `npm run db:migrate` e versione a nova pasta criada em `prisma/migrations/`. Em ambiente de produção, depois de disponibilizar a base e a variável `DATABASE_URL`, aplique apenas migrações já revisadas com:

```powershell
npm run db:deploy
```

## Observações importantes

- Este passo prepara o schema e as migrações; ainda não conecta os serviços Python ao banco.
- `cache_key` só evita chamadas repetidas quando o futuro serviço Python calcular e consultar essa chave antes da chamada ao Gemini.
- A unicidade do EAN evita duplicar o produto no catálogo; não substitui validação/normalização do código recebido.
- `image_reference` deve armazenar uma referência/URL controlada, não o conteúdo binário da imagem.
- `nutrition_table` e `serving_information` são JSONB para acomodar rótulos com estruturas variáveis.

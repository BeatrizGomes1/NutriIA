# Contexto

O backend tem access JWT, cadastro/login, consulta por EAN e análise por provedor. Ainda não há refresh sessions persistidas, recuperação de senha, análise de foto/OCR nem reconhecimento de nomes alternativos de ingredientes. O prompt do Gemini precisa orientar explicitamente esse reconhecimento sem fabricar evidências.

# Objetivo

Implementar refresh token rotativo e revogável, recuperação de senha com token de uso único enviado por SMTP, análise de foto de rótulo via entrada multimodal da Interactions API e equivalências/nomes alternativos para análise mock e prompt Gemini. Não usar chave Gemini real nem executar migrações em banco externo.

# Prompt utilizado

Construa as rotas para renovar sessão, solicitar e confirmar redefinição de senha e analisar foto de rótulo. Persistir hashes de tokens e sessões, revogar sessão no reset, responder genericamente a pedidos de recuperação e proteger contra reutilização. Receber imagem multipart validada e limitada, extrair dados estruturados pelo Gemini e encaminhar ao fluxo de análise existente. Atualizar o prompt para sinônimos, traduções e derivados relacionados, exigindo trecho literal e explicação com ressalvas, sem confundir equivalência química. Melhorar o mock para reconhecer português/inglês, incluindo leite/sugar e derivados citados. Não inventar fatos quando a extração for incerta.

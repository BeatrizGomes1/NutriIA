# Decisão

O produto deve ser tratado como um aplicativo mobile completo, não apenas como
um módulo de análise nutricional. A estrutura deve contemplar autenticação,
onboarding, perfil, scanner EAN/foto, consulta de produtos, OCR/visão,
análise contextualizada, histórico e restrições.

A pasta específica `gemini/` será substituída por `integrations/`, pois o
provedor de IA ainda está em aberto. A futura camada HTTP será representada
por `api/`, sem endpoints neste primeiro commit.

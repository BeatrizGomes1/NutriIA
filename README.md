# 🥗 Assistente Nutricional com LLM

> Leitura crítica de rótulos alimentares e análise nutricional personalizada usando IA.

---

## 📌 Sobre o Projeto

Muitos alimentos ultraprocessados usam termos técnicos (como *maltodextrina*, *dextrose*, *caseinato* ou *soro de leite*) para mascarar açúcares e lactose[cite: 1]. 

Este aplicativo mobile analisa rótulos e tabelas nutricionais via **Visão Computacional** e **LLMs**, traduzindo dados complexos em diagnósticos diretos de acordo com o perfil, metas e restrições alimentares do usuário[cite: 1].

---

## ✨ Funcionalidades

* **Detecção de Ingredientes Ocultos:** Identifica sinônimos de açúcares, aditivos e alérgenos[cite: 1].
* **Veredito Personalizado:** Avaliação instantânea em `[RECOMENDADO]`, `[COM MODERAÇÃO]` ou `[EVITAR]`[cite: 1].
* **Explicabilidade:** Justificativas curtas (2 a 3 frases) em linguagem acessível[cite: 1].
* **Leitura Rápida:** Captura via foto (OCR/Vision) ou código de barras (EAN)[cite: 1].

---

## 📱 Fluxo da Aplicação

[Perfil do Usuário] ➔ [Leitura do Rótulo] ➔ [Análise via LLM] ➔ [Veredito + Alertas]


---

## 🛠️ Tecnologias

* **Mobile:** Android Nativo (Kotlin + Jetpack Compose)[cite: 1]
* **Leitura de Código:** Google ML Kit[cite: 1]
* **Integração / Backend:** Python / Node.js / Java (Spring Boot)[cite: 1]
* **API Externa:** Open Food Facts[cite: 1]
* **IA / LLM:** Llama 3 (via Groq Cloud API ou Ollama)[cite: 1]

---

## 🧪 Exemplo de Uso

* **Perfil:** Foco em emagrecimento | Restrição a Lactose e Açúcar
* **Produto:** Iogurte de Morango ("Zero Adição de Açúcares")
* **Ingredientes:** *Leite reconstituído, soro de leite em pó, preparado de morango (suco concentrado de maçã, maltodextrina), sucralose.*[cite: 1]

### 🤖 Retorno da IA

* **Veredito:** `[EVITAR]`[cite: 1]
* **Alertas:** Contém **Soro de Leite em Pó** e **Maltodextrina / Suco Concentrado**[cite: 1].
* **Justificativa:** *"Apesar de indicar 'Zero Açúcar', contém maltodextrina e suco concentrado de fruta, que elevam a glicemia. A presença de soro de leite também viola sua restrição à lactose."*[cite: 1]

---

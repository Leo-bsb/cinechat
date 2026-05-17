# 🎬 CineChat IA — Documentação Técnica

## Visão Geral

O **CineChat** é uma aplicação de chat inteligente construída com **Streamlit** que permite ao usuário fazer perguntas em linguagem natural sobre uma base de filmes (formato IMDB Top 1000). As respostas são geradas pelo modelo **Gemini 2.5 Flash** (Google), que recebe como contexto apenas os filmes mais relevantes para cada pergunta.

---

## Arquitetura Geral

```
┌────────────────────────────────────────────────────────────┐
│                      Usuário (Browser)                     │
└────────────────────────┬───────────────────────────────────┘
                         │ Pergunta em texto
                         ▼
┌────────────────────────────────────────────────────────────┐
│                   Streamlit (Frontend + Backend)           │
│                                                            │
│   ┌─────────────┐     ┌──────────────────────────────┐    │
│   │   Sidebar   │     │        Área Principal         │    │
│   │  Estatísticas│    │  Histórico de Mensagens       │    │
│   │  Top Gêneros│     │  Input + Botão Enviar         │    │
│   │  Diagnóstico│     └──────────────┬───────────────┘    │
│   └─────────────┘                    │                     │
└─────────────────────────────────────┼─────────────────────┘
                                       │
                         ┌─────────────▼──────────────┐
                         │   buscar_filmes_relevantes  │
                         │   (filtragem local por token│
                         │    + top-20 IMDB como âncora│
                         └─────────────┬──────────────┘
                                       │ Subconjunto de filmes (≤80)
                         ┌─────────────▼──────────────┐
                         │       Gemini API            │
                         │  (gemini-2.5-flash-lite)    │
                         │  Prompt = contexto + pergunta│
                         └─────────────┬──────────────┘
                                       │ Resposta em texto
                         ┌─────────────▼──────────────┐
                         │   Exibição no Chat          │
                         │   + Atualização do histórico│
                         └────────────────────────────┘
```

---

## Fluxo Completo de Execução

### 1. Inicialização da Aplicação

Ao iniciar o Streamlit, as seguintes etapas ocorrem **uma única vez** (via `@st.cache_data` / `@st.cache_resource`):

```
Startup
  ├── carregar_filmes()          → lê filmes_db.csv e normaliza colunas
  ├── construir_indice()         → cria coluna '_busca' (texto pesquisável em lowercase)
  └── inicializar_modelo()       → configura Gemini com a GEMINI_API_KEY do secrets.toml
```

### 2. Carregamento e Normalização dos Dados (`carregar_filmes`)

| Etapa | Descrição |
|---|---|
| Leitura do CSV | Tenta UTF-8, fallback para latin-1 |
| Renomear colunas | Mapeia nomes originais IMDB → nomes internos (`titulo`, `ano`, `genero`, etc.) |
| Conversão de tipos | `ano` → Int64, `duracao_raw` → `duracao_min` (float), `bilheteria_raw` → `bilheteria_milhoes_usd` |
| Elenco principal | Concatena `star1..star4` em `elenco_principal` |
| Limpeza | Remove colunas intermediárias após transformação |

### 3. Construção do Índice de Busca (`construir_indice`)

Cria uma coluna `_busca` que é a concatenação em **lowercase** dos campos: `titulo`, `genero`, `diretor`, `elenco_principal`, `sinopse`, `ano`. Essa coluna permite busca por tokens sem chamar a API a cada caractere digitado.

### 4. Ciclo de Mensagem (por envio do usuário)

```
Usuário digita pergunta → clica "Enviar"
        │
        ▼
1. Adiciona mensagem ao mensagens_display (exibição imediata)
        │
        ▼
2. chat_com_gemini(historico, pergunta)
        │
        ├── buscar_filmes_relevantes(pergunta, top_n=80)
        │       ├── Tokeniza a pergunta (palavras ≥ 3 chars)
        │       ├── Pontua cada filme: nº de tokens encontrados em _busca
        │       ├── Filtra filmes com score > 0, ordena por [score ↓, IMDB ↓]
        │       ├── Sempre inclui top-20 por nota IMDB (contexto geral)
        │       ├── Combina e deduplica → até 80 filmes
        │       └── Serializa cada filme em uma linha compacta (linha_compacta)
        │
        ├── Monta prompt_com_contexto:
        │       "=== FILMES RELEVANTES ({n}) ===\n{contexto}\n=== FIM ===\n\nPergunta: ..."
        │
        └── model.start_chat(history=historico).send_message(prompt)
                │
                └── Retorna resposta em texto (ou mensagem de erro tratada)
        │
        ▼
3. Atualiza historico_chat (formato Gemini: role/parts)
4. Atualiza mensagens_display (formato interno: role/content)
5. st.rerun() → re-renderiza a interface com o novo estado
```

---

## Componentes Principais

### `carregar_filmes() → pd.DataFrame`
- **Cache:** `@st.cache_data` (executa apenas na primeira carga)
- **Entrada:** arquivo `filmes_db.csv` no diretório raiz
- **Saída:** DataFrame normalizado com colunas padronizadas

### `construir_indice(dataframe) → pd.DataFrame`
- **Cache:** `@st.cache_data`
- **Entrada:** DataFrame normalizado
- **Saída:** mesmo DataFrame com coluna `_busca` adicionada

### `linha_compacta(row) → str`
- Serializa um filme em uma única linha para uso no prompt da LLM
- Formato: `Título (Ano) | Gênero | Dir | Elenco | Duração | IMDB | Bilheteria | Sinopse[:100]`

### `buscar_filmes_relevantes(pergunta, top_n=80) → str`
- Realiza busca local por tokens para selecionar o subconjunto mais relevante
- **Estratégia de fallback:** se nenhum token der match, retorna os `top_n` por nota IMDB
- **Âncora:** sempre inclui os 20 melhores por IMDB para responder perguntas gerais

### `chat_com_gemini(historico, mensagem) → str`
- Orquestra a chamada à API Gemini
- Injeta contexto filtrado no prompt
- Trata erros de quota (HTTP 429) com mensagem amigável ao usuário

### `inicializar_modelo() → GenerativeModel`
- **Cache:** `@st.cache_resource` (singleton por sessão)
- Lê `GEMINI_API_KEY` de `.streamlit/secrets.toml`
- Configura o modelo com `SYSTEM_PROMPT_BASE`, temperatura 0.7 e máx. 800 tokens

---

## Gerenciamento de Estado (Session State)

| Chave | Tipo | Descrição |
|---|---|---|
| `historico_chat` | `list[dict]` | Histórico no formato Gemini (`role`/`parts`) enviado à API a cada turno |
| `mensagens_display` | `list[dict]` | Histórico no formato de exibição (`role`/`content`) renderizado no chat |

O botão **"Limpar conversa"** zera ambas as listas e chama `st.rerun()`.

---

## System Prompt

O `SYSTEM_PROMPT_BASE` define a personalidade e as regras do assistente:

- Responder **sempre em português do Brasil**
- Basear respostas **exclusivamente na base de dados fornecida**
- Ser preciso com dados numéricos (notas, bilheterias, anos)
- Usar formatação clara (listas, bullet points)
- Comunicar quando uma pergunta não puder ser respondida com os dados disponíveis
- Tom caloroso e apaixonado por cinema

---

## Interface (Layout Streamlit)

```
┌─────────────────────────────────────────────────────────┐
│  SIDEBAR                   │  ÁREA PRINCIPAL            │
│  ─────────                 │  ─────────────             │
│  Logo + Título             │  Hero Title "CINECHAT"     │
│  Estatísticas (cards)      │                            │
│    · Nº de filmes          │  Histórico de mensagens    │
│    · Bilheteria total      │   (user / AI alternados)   │
│  Período de anos           │                            │
│  Top 6 gêneros (chips)     │  Input text + Botão Enviar │
│  Diagnóstico (expander)    │                            │
│  Botão Limpar              │                            │
└─────────────────────────────────────────────────────────┘
```

---

## Tratamento de Erros

| Cenário | Comportamento |
|---|---|
| `filmes_db.csv` não encontrado | `st.error()` + retorna DataFrame vazio |
| Encoding inválido (UTF-8) | Fallback automático para `latin-1` |
| `GEMINI_API_KEY` ausente | `st.error()` + `st.stop()` (encerra a app) |
| Quota excedida (HTTP 429) | Mensagem amigável com tempo de espera extraído do erro |
| Qualquer outra exceção da API | Mensagem de aviso com o texto do erro |

---

## Dependências

| Biblioteca | Uso |
|---|---|
| `streamlit` | Framework de UI e gerenciamento de estado |
| `pandas` | Leitura, normalização e filtragem do CSV |
| `collections.Counter` | Contagem de gêneros para exibição no sidebar |
| `google.generativeai` | Integração com a API Gemini |
| `re` (stdlib) | Extração do tempo de espera em erros de quota |

---

## Configuração Necessária

```toml
# .streamlit/secrets.toml
GEMINI_API_KEY = "AIza..."
```

```
projeto/
├── app.py              # código principal
├── filmes_db.csv       # base de dados IMDB Top 1000
└── .streamlit/
    └── secrets.toml    # chave da API Gemini
```

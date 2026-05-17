import streamlit as st
import pandas as pd
from collections import Counter
import google.generativeai as genai

# ── Configuração da página ──────────────────────────────────────────────────
st.set_page_config(
    page_title="🎬 CineChat IA",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS personalizado ───────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@300;400;500;600&display=swap');

  .stApp { background: #0a0a0f; color: #e8e6e0; }

  section[data-testid="stSidebar"] {
      background: #0f0f1a;
      border-right: 1px solid #1e1e30;
  }

  .hero-title {
      font-family: 'Bebas Neue', sans-serif;
      font-size: 3.2rem;
      letter-spacing: 4px;
      background: linear-gradient(135deg, #e8c97a 0%, #c8860a 50%, #e8c97a 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      line-height: 1;
      margin-bottom: 0;
  }
  .hero-sub {
      font-family: 'Inter', sans-serif;
      font-size: 0.85rem;
      letter-spacing: 3px;
      color: #6b6b80;
      text-transform: uppercase;
      margin-top: 4px;
  }

  .msg-user {
      background: linear-gradient(135deg, #1a1a2e, #16213e);
      border: 1px solid #2a2a45;
      border-radius: 16px 16px 4px 16px;
      padding: 14px 18px;
      margin: 8px 0;
      font-family: 'Inter', sans-serif;
      font-size: 0.95rem;
      color: #d4d4e8;
  }
  .msg-ai {
      background: linear-gradient(135deg, #1a1206, #211a08);
      border: 1px solid #3d2f0a;
      border-radius: 16px 16px 16px 4px;
      padding: 14px 18px;
      margin: 8px 0;
      font-family: 'Inter', sans-serif;
      font-size: 0.95rem;
      color: #e8e2c8;
      line-height: 1.6;
  }
  .msg-label-user {
      font-size: 0.7rem; letter-spacing: 2px; color: #4a4a6a;
      text-transform: uppercase; margin-bottom: 4px; text-align: right;
  }
  .msg-label-ai {
      font-size: 0.7rem; letter-spacing: 2px; color: #6b5010;
      text-transform: uppercase; margin-bottom: 4px;
  }

  .stat-card {
      background: #0f0f1a;
      border: 1px solid #1e1e30;
      border-radius: 12px;
      padding: 16px;
      text-align: center;
  }
  .stat-number {
      font-family: 'Bebas Neue', sans-serif;
      font-size: 2rem;
      color: #c8860a;
      line-height: 1;
  }
  .stat-label {
      font-size: 0.7rem;
      letter-spacing: 2px;
      color: #6b6b80;
      text-transform: uppercase;
  }

  .genre-chip {
      display: inline-block;
      background: #1e1e30;
      border: 1px solid #2a2a45;
      border-radius: 20px;
      padding: 3px 10px;
      font-size: 0.75rem;
      color: #9090b0;
      margin: 2px;
  }

  .stTextInput > div > div > input {
      background: #0f0f1a !important;
      border: 1px solid #2a2a45 !important;
      color: #e8e6e0 !important;
      border-radius: 12px !important;
  }

  .stButton > button {
      background: linear-gradient(135deg, #c8860a, #e8c97a) !important;
      color: #0a0a0f !important;
      border: none !important;
      border-radius: 10px !important;
      font-family: 'Inter', sans-serif !important;
      font-weight: 600 !important;
      letter-spacing: 1px !important;
  }

  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: #0a0a0f; }
  ::-webkit-scrollbar-thumb { background: #2a2a45; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

# ── Carregar e normalizar base de dados ────────────────────────────────────
@st.cache_data
def carregar_filmes() -> pd.DataFrame:
    """
    Carrega o CSV no novo formato IMDB Top 1000 e normaliza as colunas
    para os nomes internos usados pelo restante do app.
    """
    try:
        df = pd.read_csv(
            "filmes_db.csv",
            encoding="utf-8",
            quotechar='"',
            skipinitialspace=True,
            on_bad_lines="warn",
        )
    except UnicodeDecodeError:
        df = pd.read_csv(
            "filmes_db.csv",
            encoding="latin-1",
            quotechar='"',
            skipinitialspace=True,
            on_bad_lines="warn",
        )
    except FileNotFoundError:
        st.error("❌ Arquivo 'filmes_db.csv' não encontrado.")
        return pd.DataFrame()

    # ── Normalizar nomes de colunas (remove espaços extras, BOM, etc.) ──
    df.columns = df.columns.str.strip()

    # ── Renomear colunas para nomes internos ──
    rename_map = {
        "Series_Title":   "titulo",
        "Released_Year":  "ano",
        "Genre":          "genero",
        "Director":       "diretor",
        "IMDB_Rating":    "nota_imdb",
        "Overview":       "sinopse",
        "Certificate":    "certificado",
        "Runtime":        "duracao_raw",
        "Meta_score":     "metascore",
        "Gross":          "bilheteria_raw",
        "No_of_Votes":    "votos",
        "Star1":          "star1",
        "Star2":          "star2",
        "Star3":          "star3",
        "Star4":          "star4",
        "Poster_Link":    "poster",
    }
    df = df.rename(columns=rename_map)

    # ── Limpar / converter tipos ──
    # Ano: alguns valores podem ser "PG" ou string inválida
    df["ano"] = pd.to_numeric(df["ano"], errors="coerce").astype("Int64")

    # Duração em minutos (ex.: "142 min" → 142)
    if "duracao_raw" in df.columns:
        df["duracao_min"] = (
            df["duracao_raw"].astype(str).str.extract(r"(\d+)")[0].astype(float)
        )
    else:
        df["duracao_min"] = float("nan")

    # Bilheteria em milhões de USD (ex.: "28,341,469" → 28.34)
    if "bilheteria_raw" in df.columns:
        df["bilheteria_milhoes_usd"] = (
            df["bilheteria_raw"]
            .astype(str)
            .str.replace(",", "", regex=False)
            .pipe(pd.to_numeric, errors="coerce")
            .div(1_000_000)
        )
    else:
        df["bilheteria_milhoes_usd"] = float("nan")

    # Elenco principal (concatenar as quatro estrelas)
    star_cols = [c for c in ["star1", "star2", "star3", "star4"] if c in df.columns]
    if star_cols:
        df["elenco_principal"] = (
            df[star_cols]
            .fillna("")
            .agg(lambda x: ", ".join(filter(None, x)), axis=1)
        )
    else:
        df["elenco_principal"] = ""

    # Nota IMDB numérica
    df["nota_imdb"] = pd.to_numeric(df["nota_imdb"], errors="coerce")

    # Descartar colunas intermediárias desnecessárias
    df = df.drop(columns=["duracao_raw", "bilheteria_raw"] + star_cols, errors="ignore")

    return df


df = carregar_filmes()

# ── Pré-computar índice de busca (uma vez, em cache) ──────────────────────
@st.cache_data
def construir_indice(dataframe: pd.DataFrame) -> pd.DataFrame:
    """
    Cria uma coluna '_busca' com todo o texto pesquisável em lowercase,
    para filtrar filmes relevantes antes de chamar a API.
    """
    df2 = dataframe.copy()
    campos = ["titulo", "genero", "diretor", "elenco_principal", "sinopse", "ano"]
    subcols = [c for c in campos if c in df2.columns]
    # Converte cada célula individualmente para str, tratando NA/None/float NaN
    def _para_str(v):
        if v is None:
            return ""
        s = str(v)
        return "" if s in ("nan", "NA", "<NA>", "None") else s

    df2["_busca"] = (
        df2[subcols]
        .map(_para_str)
        .agg(" ".join, axis=1)
        .str.lower()
    )
    return df2


@st.cache_data
def linha_compacta(r: pd.Series) -> str:
    """Serializa um filme em uma linha curta para o prompt."""
    bilheteria = f"${r['bilheteria_milhoes_usd']:.1f}M" if pd.notna(r.get("bilheteria_milhoes_usd")) else "N/D"
    duracao    = f"{int(r['duracao_min'])}min"           if pd.notna(r.get("duracao_min"))            else "N/D"
    ano        = str(r["ano"])                              if pd.notna(r["ano"])                        else "N/D"
    imdb       = str(r["nota_imdb"])                        if pd.notna(r["nota_imdb"])                  else "N/D"
    return (
        f"{r['titulo']} ({ano}) | Gênero:{r['genero']} | Dir:{r['diretor']} | "
        f"Elenco:{r['elenco_principal']} | {duracao} | IMDB:{imdb} | "
        f"Bilheteria:{bilheteria} | Sinopse:{str(r['sinopse'])[:100]}"
    )


DF_INDEXADO = construir_indice(df) if not df.empty else df


def buscar_filmes_relevantes(pergunta: str, top_n: int = 80) -> str:
    """
    Filtra os filmes mais relevantes para a pergunta usando busca por tokens.
    Estratégia:
      1. Divide a pergunta em tokens (palavras ≥ 3 chars)
      2. Pontua cada filme pelo número de tokens encontrados no campo _busca
      3. Retorna os top_n com maior pontuação (mín. 1 match) + sempre inclui
         os 20 melhores por IMDB como âncora para perguntas gerais.
    Se nenhum token der match, retorna os top_n por IMDB (fallback).
    """
    if DF_INDEXADO.empty:
        return ""

    tokens = [t for t in pergunta.lower().split() if len(t) >= 3]

    if tokens:
        scores = DF_INDEXADO["_busca"].apply(
            lambda txt: sum(1 for t in tokens if t in txt)
        )
        # filmes com ao menos 1 match, ordenados por score desc, depois IMDB desc
        mask = scores > 0
        ranked = (
            DF_INDEXADO[mask]
            .assign(_score=scores[mask])
            .sort_values(["_score", "nota_imdb"], ascending=[False, False])
        )
        # sempre inclui top-20 por IMDB como contexto geral
        top_imdb = DF_INDEXADO.nlargest(20, "nota_imdb")
        combined = pd.concat([ranked.head(top_n), top_imdb]).drop_duplicates(subset="titulo")
        selecionados = combined.head(top_n)
    else:
        selecionados = DF_INDEXADO.nlargest(top_n, "nota_imdb")

    linhas = [linha_compacta(r) for _, r in selecionados.iterrows()]
    return "\n".join(linhas)


SYSTEM_PROMPT_BASE = f"""Você é o CineChat, um assistente especialista em cinema com personalidade apaixonada e culta.
Você tem acesso a uma base de dados com {len(df)} filmes e responde baseando-se EXCLUSIVAMENTE nela.
A cada mensagem, um subconjunto relevante dos filmes será fornecido como contexto.

INSTRUÇÕES OBRIGATÓRIAS:
- Responda SEMPRE em português do Brasil, independentemente do idioma da pergunta
- Seja preciso com os dados: notas IMDB, bilheterias, anos, diretores, elenco
- Quando listar filmes, use formatação clara (bullet points ou numeração)
- Você pode fazer análises, comparações, rankings e recomendações com base nos dados
- Se a pergunta não puder ser respondida com os dados fornecidos, diga isso claramente
- Seja caloroso, entusiasmado e mostre paixão pelo cinema
- Ao citar bilheteria, use formato "$XXX milhões" ou "$X bilhão"
- Ao citar nota IMDB, mencione que é a nota do IMDB
- Se perguntarem sobre filmes fora da base, informe que não estão na sua base atual
"""

# ── Configurar Gemini via secrets ──────────────────────────────────────────
@st.cache_resource
def inicializar_modelo():
    """Lê a API key do secrets.toml e inicializa o modelo Gemini."""
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except KeyError:
        st.error(
            "❌ Chave 'GEMINI_API_KEY' não encontrada em `.streamlit/secrets.toml`.\n\n"
            "Adicione:\n```toml\nGEMINI_API_KEY = \"AIza...\"\n```"
        )
        st.stop()

    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        model_name="gemini-2.5-flash-lite",
        system_instruction=SYSTEM_PROMPT_BASE,
        generation_config=genai.GenerationConfig(
            temperature=0.7,
            max_output_tokens=800,
        ),
    )


model = inicializar_modelo()


def chat_com_gemini(historico: list, mensagem: str) -> str:
    """
    Busca filmes relevantes localmente e injeta apenas eles no prompt,
    reduzindo drasticamente o número de tokens por requisição.
    """
    contexto = buscar_filmes_relevantes(mensagem)
    n_filmes = len(contexto.splitlines()) if contexto else 0

    prompt_com_contexto = (
        f"=== FILMES RELEVANTES DA BASE ({n_filmes} de {len(df)}) ===\n"
        f"{contexto}\n"
        f"=== FIM DO CONTEXTO ===\n\n"
        f"Pergunta: {mensagem}"
    )

    try:
        chat = model.start_chat(history=historico)
        response = chat.send_message(prompt_com_contexto)
        return response.text
    except Exception as e:
        err = str(e)
        if "429" in err or "quota" in err.lower():
            import re
            delay = re.search(r"retry.*?(\d+)s", err)
            wait = delay.group(1) if delay else "alguns"
            return (
                f"⏳ Limite de requisições atingido. "
                f"Aguarde **{wait} segundos** e tente novamente.\n\n"
                f"_Dica: o plano gratuito do Gemini permite 20 req/dia no gemini-2.5-flash. "
                f"Considere usar `gemini-1.5-flash` que tem limites maiores._"
            )
        return f"⚠️ Erro ao consultar a IA: {err}"


# ── Estado da sessão ────────────────────────────────────────────────────────
if "historico_chat" not in st.session_state:
    st.session_state.historico_chat = []
if "mensagens_display" not in st.session_state:
    st.session_state.mensagens_display = []

# ── SIDEBAR ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='text-align:center; padding: 20px 0 10px;'>
        <div style='font-size:2.5rem;'>🎬</div>
        <div style='font-family:"Bebas Neue",sans-serif; font-size:1.5rem;
                    letter-spacing:3px; color:#c8860a;'>CINECHAT</div>
        <div style='font-size:0.65rem; letter-spacing:2px; color:#6b6b80;'>ASSISTENTE DE CINEMA IA</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    if not df.empty:
        st.markdown("**📊 Base de Dados**")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-number">{len(df)}</div>
                <div class="stat-label">Filmes</div>
            </div>""", unsafe_allow_html=True)
        with col2:
            bilheteria_total = df["bilheteria_milhoes_usd"].sum(skipna=True) / 1000
            bilheteria_fmt = f"${bilheteria_total:.1f}B" if bilheteria_total > 0 else "N/D"
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-number">{bilheteria_fmt}</div>
                <div class="stat-label">Bilheteria</div>
            </div>""", unsafe_allow_html=True)

        ano_min = int(df["ano"].min(skipna=True)) if df["ano"].notna().any() else "?"
        ano_max = int(df["ano"].max(skipna=True)) if df["ano"].notna().any() else "?"
        melhor_imdb = df["nota_imdb"].max(skipna=True)

        st.markdown(f"""
        <div style='margin-top:10px; font-size:0.75rem; color:#6b6b80;'>
            🗓️ <b style='color:#9090b0;'>{ano_min}</b> — <b style='color:#9090b0;'>{ano_max}</b>  •  
            ⭐ Melhor IMDB: <b style='color:#c8860a;'>{melhor_imdb}</b>
        </div>""", unsafe_allow_html=True)

        # Top gêneros
        generos: list[str] = []
        for g in df["genero"].dropna():
            generos.extend([x.strip() for x in str(g).split(",")])
        top_generos = Counter(generos).most_common(6)

        st.markdown(
            "<div style='margin-top:12px; font-size:0.75rem; color:#6b6b80; letter-spacing:1px;'>GÊNEROS</div>",
            unsafe_allow_html=True,
        )
        chips_html = "".join(
            [f'<span class="genre-chip">{g} <span style="color:#c8860a;">{c}</span></span>'
             for g, c in top_generos]
        )
        st.markdown(f"<div>{chips_html}</div>", unsafe_allow_html=True)

    st.divider()

    # Debug: mostrar estado real do CSV
    with st.expander("🔧 Diagnóstico da base", expanded=False):
        st.markdown(f"**Linhas lidas:** {len(df)}")
        st.markdown(f"**Colunas:** {', '.join(df.columns.tolist())}")
        if "bilheteria_milhoes_usd" in df.columns:
            n_bill = df["bilheteria_milhoes_usd"].notna().sum()
            st.markdown(f"**Filmes c/ bilheteria:** {n_bill}/{len(df)}")
        if "nota_imdb" in df.columns:
            st.markdown(f"**IMDB válidos:** {df['nota_imdb'].notna().sum()}")

    if st.button("🗑️ Limpar conversa"):
        st.session_state.historico_chat = []
        st.session_state.mensagens_display = []
        st.rerun()

# ── ÁREA PRINCIPAL ──────────────────────────────────────────────────────────
st.markdown("""
<div style='padding: 24px 0 8px;'>
    <div class='hero-title'>CINECHAT</div>
    <div class='hero-sub'>Assistente Inteligente de Cinema · Gemini 2.5 Flash</div>
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div style='font-size:0.8rem; color:#4a4a6a; margin-bottom:24px;'>
    Base com <b style='color:#c8860a;'>{len(df)}</b> filmes selecionados •
    Faça perguntas sobre diretores, elenco, bilheteria, gêneros, notas e muito mais.
</div>
""", unsafe_allow_html=True)

# Contêiner de mensagens
with st.container():
    if not st.session_state.mensagens_display:
        st.markdown("""
        <div style='text-align:center; padding: 60px 20px; color:#2a2a45;'>
            <div style='font-size:4rem; margin-bottom:16px;'>🎥</div>
            <div style='font-family:"Bebas Neue",sans-serif; font-size:1.5rem;
                        letter-spacing:3px; color:#1e1e30;'>INICIE A CONVERSA</div>
            <div style='font-size:0.8rem; letter-spacing:1px; color:#2a2a3a; margin-top:8px;'>
                Pergunte sobre qualquer filme da base de dados
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        for msg in st.session_state.mensagens_display:
            if msg["role"] == "user":
                st.markdown(f"""
                <div class='msg-label-user'>Você</div>
                <div class='msg-user'>{msg['content']}</div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class='msg-label-ai'>🎬 CineChat IA</div>
                <div class='msg-ai'>{msg['content']}</div>
                """, unsafe_allow_html=True)

# ── Input de mensagem ───────────────────────────────────────────────────────
st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

col_input, col_btn = st.columns([5, 1])

with col_input:
    user_input = st.text_input(
        label="",
        placeholder="Ex: Quais são os melhores filmes de crime? Qual o filme mais rentável?",
        label_visibility="collapsed",
        key="chat_input",
    )

with col_btn:
    enviar = st.button("▶ Enviar", use_container_width=True)

# ── Processar envio ─────────────────────────────────────────────────────────
if enviar and user_input.strip():
    pergunta = user_input.strip()

    st.session_state.mensagens_display.append({"role": "user", "content": pergunta})

    with st.spinner("🎬 Consultando a base de filmes..."):
        resposta = chat_com_gemini(st.session_state.historico_chat, pergunta)

    st.session_state.historico_chat.append({"role": "user",  "parts": [pergunta]})
    st.session_state.historico_chat.append({"role": "model", "parts": [resposta]})

    st.session_state.mensagens_display.append({"role": "assistant", "content": resposta})

    st.rerun()
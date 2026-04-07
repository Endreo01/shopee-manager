import streamlit as st
import time

st.set_page_config(
    page_title="Zanup · Shopee Manager",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
[data-testid="stSidebar"] { background: #0f3638; }
[data-testid="stSidebar"] * { color: #e0f0f1 !important; }

/* ESSA LINHA ESCONDE O MENU NATIVO DO STREAMLIT QUE ESTAVA DUPLICANDO AS PÁGINAS */
[data-testid="stSidebarNav"] { display: none !important; }

[data-testid="stMetric"] {
    background: #f9f8f5; border: 1px solid #dcd9d5;
    border-radius: 12px; padding: 16px !important;
    box-shadow: 0 1px 4px rgba(15,54,56,0.06);
}
[data-testid="stMetricValue"] { color: #0f3638 !important; font-weight: 700; }
.stButton > button {
    background: #01696f; color: white; border: none;
    border-radius: 8px; font-weight: 600;
    transition: background 0.2s;
}
.stButton > button:hover { background: #0c4e54; }
.section-title { font-size: 22px; font-weight: 700; color: #0f3638; margin-bottom: 4px; }
.section-sub   { color: #7a7974; font-size: 14px; margin-bottom: 20px; }
.badge-ok  { display:inline-block; background:#d4dfcc; color:#1e3f0a; border-radius:20px; padding:2px 12px; font-size:13px; font-weight:600; }
.badge-err { display:inline-block; background:#e0ced7; color:#561740; border-radius:20px; padding:2px 12px; font-size:13px; font-weight:600; }
</style>
""", unsafe_allow_html=True)

# ── Carrega os Secrets automaticamente ──────────────────
def _load_secrets():
    if st.session_state.get("_secrets_loaded"):
        return
    try:
        shopee = st.secrets.get("shopee", {})
        keys = ["partner_id", "partner_key", "shop_id", "access_token", "refresh_token"]
        for k in keys:
            if shopee.get(k) and not st.session_state.get(k):
                st.session_state[k] = shopee[k]
        
        if st.session_state.get("access_token"):
            st.session_state["authenticated"] = True
            
        st.session_state["_secrets_loaded"] = True
    except Exception:
        pass

# Executa o carregamento antes de montar a página
_load_secrets()

# ── Estado de sessão ──────────────────────────────────
for k, v in {"authenticated": False, "partner_id": "", "partner_key": "",
             "shop_id": "", "access_token": "", "refresh_token": "",
             "page": "🏠 Dashboard"}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Sidebar ───────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛒 Shopee Manager")
    st.markdown("**Zanup Marketplace**")
    st.divider()
    pages = ["🏠 Dashboard", "⚙️ Configurações", "📦 Produtos",
             "💰 Atualizar Preços", "📦 Estoque", "📣 Anúncios (Ads)",
             "🛍️ Pedidos", "🔄 Token / Auth"]
    selected = st.radio("Navegação", pages, label_visibility="collapsed")
    st.session_state.page = selected
    st.divider()
    if st.session_state.authenticated:
        st.markdown('<span class="badge-ok">✅ API Conectada</span>', unsafe_allow_html=True)
        st.caption(f"Shop ID: `{st.session_state.shop_id}`")
    else:
        st.markdown('<span class="badge-err">⚠️ Não configurada</span>', unsafe_allow_html=True)
        st.caption("Configure em ⚙️ Configurações")

# ── Roteamento ────────────────────────────────────────
page = st.session_state.page
if   page == "🏠 Dashboard":         from pages.dashboard      import render; render()
elif page == "⚙️ Configurações":     from pages.configuracoes  import render; render()
elif page == "📦 Produtos":           from pages.produtos       import render; render()
elif page == "💰 Atualizar Preços":   from pages.precos         import render; render()
elif page == "📦 Estoque":            from pages.estoque        import render; render()
elif page == "📣 Anúncios (Ads)":     from pages.ads            import render; render()
elif page == "🛍️ Pedidos":           from pages.pedidos        import render; render()
elif page == "🔄 Token / Auth":       from pages.auth_token     import render; render()

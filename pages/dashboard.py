import streamlit as st
import shopee_client as sc

def render():
    st.markdown('<p class="section-title">🏠 Dashboard</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Visão geral da sua loja Shopee</p>', unsafe_allow_html=True)

    if not st.session_state.get("authenticated"):
        st.info("👋 Bem-vindo! Configure suas credenciais em **⚙️ Configurações** para começar.")
        st.markdown("""
        ### Como começar em 3 passos:
        1. Acesse **⚙️ Configurações**
        2. Preencha Partner ID, Partner Key e Shop ID
        3. Vá em **🔄 Token / Auth** e depois volte ao Dashboard
        """)
        return

    with st.spinner("Carregando dados da loja..."):
        info = sc.get_shop_info()

    if "error" in info:
        st.error(f"Erro ao conectar: {info['error']}")
        return

    shop = info.get("response", {})
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🏪 Loja", shop.get("shop_name", "—"))
    col2.metric("⭐ Avaliação", shop.get("shop_score", {}).get("overall_star", "—"))
    col3.metric("📦 Pedidos Pendentes", shop.get("order_count", "—"))
    col4.metric("🌍 País", shop.get("country", "BR"))
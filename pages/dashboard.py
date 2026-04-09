import streamlit as st
import shopee_client as sc


def render():
    st.markdown('<div class="section-title">🏠 Visão Geral — Zanup</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Métricas em tempo real da sua loja Shopee</div>', unsafe_allow_html=True)

    if not st.session_state.get("authenticated"):
        st.warning("⚠️ Conecte a API da Shopee em **⚙️ Configurações** primeiro.")
        return

    col_refresh, _ = st.columns([1, 5])
    with col_refresh:
        atualizar = st.button("🔄 Atualizar", use_container_width=True)

    if atualizar or "dashboard_metrics" not in st.session_state:
        with st.spinner("Carregando métricas da loja..."):
            metrics = sc.get_dashboard_metrics()
        if metrics.get("error"):
            st.error(f"❌ Erro ao carregar métricas: {metrics['error']}")
            return
        st.session_state["dashboard_metrics"] = metrics

    m = st.session_state["dashboard_metrics"]

    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📦 Produtos Ativos", f"{m.get('produtos_ativos', 0):,}")
    with col2:
        st.metric(
            "🛍️ Pedidos p/ Enviar",
            f"{m.get('pedidos_pendentes', 0):,}",
            help="Status READY_TO_SHIP — últimos 15 dias",
        )
    with col3:
        st.metric(
            "⚠️ Estoque Zerado",
            f"{m.get('estoque_zerado', 0):,}",
            help="Amostra dos primeiros 200 produtos ativos",
        )

    st.divider()
    st.caption("💡 Use o menu lateral para gerenciar produtos, preços, estoque e pedidos.")

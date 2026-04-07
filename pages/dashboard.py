import streamlit as st

def render():
    st.markdown('<div class="section-title">Visão Geral Zanup</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Métricas da sua loja Shopee</div>', unsafe_allow_html=True)
    
    if not st.session_state.get("authenticated"):
        st.warning("Conecte a API da Shopee na aba Configurações primeiro.")
        return

    # Exemplo de cards que você pode criar futuramente puxando dados da API
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="Pedidos Pendentes", value="15")
    with col2:
        st.metric(label="Produtos Ativos", value="342")
    with col3:
        st.metric(label="Estoque Baixo", value="8")

import streamlit as st
import shopee_client as sc

def render():
    st.markdown('<p class="section-title">⚙️ Configurações da API</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Insira suas credenciais do Shopee Open Platform</p>', unsafe_allow_html=True)

    with st.expander("ℹ️ Como obter suas credenciais?"):
        st.markdown("""
        1. Acesse [open.shopee.com](https://open.shopee.com) → **My Apps**
        2. Copie o **Partner ID** e o **Partner Key** do seu app
        3. O **Shop ID** é o ID numérico da sua loja vendedora
        4. O **Access Token** você obtém na aba **🔄 Token / Auth**
        > ⚠️ Em produção, use a função **Secrets** do Streamlit Cloud (Manage App → Secrets)
        """)

    col1, col2 = st.columns(2)
    with col1:
        partner_id  = st.text_input("Partner ID *", value=st.session_state.get("partner_id",""), placeholder="Ex: 1234567")
        partner_key = st.text_input("Partner Key *", value=st.session_state.get("partner_key",""), type="password")
    with col2:
        shop_id      = st.text_input("Shop ID *", value=st.session_state.get("shop_id",""), placeholder="Ex: 987654321")
        access_token = st.text_input("Access Token", value=st.session_state.get("access_token",""), type="password")
    refresh_token = st.text_input("Refresh Token", value=st.session_state.get("refresh_token",""), type="password")

    c1, c2, _ = st.columns([1,1,2])
    with c1:
        if st.button("💾 Salvar", use_container_width=True):
            if not partner_id or not partner_key or not shop_id:
                st.error("Partner ID, Partner Key e Shop ID são obrigatórios.")
            else:
                st.session_state.update({
                    "partner_id": partner_id.strip(), "partner_key": partner_key.strip(),
                    "shop_id": shop_id.strip(), "access_token": access_token.strip(),
                    "refresh_token": refresh_token.strip(),
                    "authenticated": bool(access_token.strip())
                })
                st.success("✅ Configurações salvas!")
    with c2:
        if st.button("🔍 Testar Conexão", use_container_width=True):
            with st.spinner("Testando..."):
                r = sc.get_shop_info()
            if "error" in r:
                st.error(f"❌ {r['error']}")
            else:
                st.success("✅ Conexão OK!")
                st.json(r.get("response", r))
import streamlit as st
import shopee_client as sc


def render():
    st.markdown('<p class="section-title">🔄 Token / Autorização OAuth</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Autorize o app na sua conta Shopee e gerencie tokens</p>', unsafe_allow_html=True)

    # --- Auto-detect code e shop_id na URL (retorno automático da Shopee) ---
    params = st.query_params
    if "code" in params and "shop_id" in params:
        code    = params["code"]
        shop_id = params["shop_id"]
        st.info("🔄 Retorno detectado da Shopee! Trocando code por token automaticamente...")
        with st.spinner("Obtendo token..."):
            result = sc.get_access_token_from_code(code, int(shop_id))
        if "access_token" in result:
            st.balloons()
            st.success("✅ Autenticação concluída com sucesso!")
            st.query_params.clear()
            st.rerun()
        else:
            st.error(f"❌ Falha na troca de token: {result}")
        st.stop()

    st.info("""
    **Fluxo OAuth Shopee:**
    1. Clique em **Gerar URL de Autorização** abaixo
    2. Acesse a URL gerada e autorize o app na sua conta Shopee
    3. Você será redirecionado de volta automaticamente com o token
    4. Se não redirecionar, cole o `code` manualmente no Passo 2
    """)

    st.divider()
    st.markdown("#### Passo 1 — Gerar URL de autorização")
    if st.button("🔗 Gerar URL de Autorização"):
        if not st.session_state.get("partner_id"):
            st.warning("Configure o Partner ID em ⚙️ Configurações primeiro.")
        else:
            auth_url = sc.get_auth_url("https://shopee-manager.streamlit.app")
            st.markdown("**Acesse esta URL:**")
            st.code(auth_url)
            st.caption("Após autorizar, você será redirecionado de volta com o token automaticamente.")

    st.divider()
    st.markdown("#### Passo 2 — Inserir o código manualmente (fallback)")
    st.caption("Use apenas se o redirecionamento automático não funcionou.")
    col1, col2 = st.columns(2)
    with col1:
        auth_code = st.text_input("Código de autorização (code)", placeholder="Cole aqui o código recebido na URL de retorno")
    with col2:
        shop_id_input = st.text_input("Shop ID", placeholder="Número da loja que autorizou")

    if st.button("🔑 Obter Access Token"):
        if not auth_code or not shop_id_input:
            st.warning("Preencha o code e o Shop ID.")
        else:
            with st.spinner("Trocando code por token..."):
                result = sc.get_access_token_from_code(auth_code.strip(), int(shop_id_input.strip()))
            if "error" in result:
                st.error(f"❌ Erro: {result['error']}")
            elif "access_token" in result:
                st.success("✅ Access Token obtido com sucesso!")
                st.code(f"Novo token: {result['access_token'][:20]}...")
                st.rerun()
            else:
                st.warning(f"Resposta inesperada: {result}")

    st.divider()
    st.markdown("#### Renovar Access Token (usando Refresh Token)")
    if st.button("🔄 Renovar Access Token"):
        if not st.session_state.get("refresh_token"):
            st.warning("Nenhum Refresh Token configurado. Vá em ⚙️ Configurações.")
        else:
            with st.spinner("Renovando token..."):
                result = sc.refresh_access_token()
            if "error" in result:
                st.error(f"Erro: {result['error']}")
            elif "access_token" in result:
                st.success("✅ Access Token renovado com sucesso!")
                st.code(f"Novo token: {result['access_token'][:20]}...")
                st.rerun()
            else:
                st.warning(f"Resposta: {result}")

    st.divider()
    st.markdown("#### Status atual dos tokens")
    col1, col2 = st.columns(2)
    with col1:
        at = st.session_state.get("access_token", "")
        st.metric("Access Token", "✅ Configurado" if at else "❌ Não configurado")
    with col2:
        rt = st.session_state.get("refresh_token", "")
        st.metric("Refresh Token", "✅ Configurado" if rt else "❌ Não configurado")

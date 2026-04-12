import streamlit as st
import shopee_client as sc


def render():
    st.markdown('<p class="section-title">🔄 Token / Auth</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Geração e renovação de tokens de acesso à API Shopee</p>', unsafe_allow_html=True)

    # ── Captura automática do code via URL ────────────────────────────────────
    params    = st.query_params
    code_url  = params.get("code", "")
    shopid_url = params.get("shop_id", "")

    if code_url:
        st.success("✅ Code capturado automaticamente da URL! Clique em **Trocar pelo Token** abaixo.")
        st.info(f"Code: `{code_url}`  |  Shop ID: `{shopid_url}`")

        if st.button("🔑 Trocar Code por Access Token", type="primary"):
            with st.spinner("Trocando code por token..."):
                result = sc.exchange_code_for_token(code_url, shop_id=shopid_url or None)

            st.write("Retorno bruto:")
            st.json(result)

            if result.get("access_token"):
                at = result["access_token"]
                rt = result.get("refresh_token", "")
                st.session_state["access_token"]  = at
                st.session_state["refresh_token"] = rt
                st.session_state["authenticated"] = True
                st.success("✅ Access Token obtido com sucesso!")
                st.code(f"access_token = \"{at}\"", language="toml")
                st.code(f"refresh_token = \"{rt}\"", language="toml")
                st.warning("⚠️ Copie os tokens acima e atualize nos **Secrets do Streamlit**!")
                # Limpa os params da URL após uso
                st.query_params.clear()
            else:
                st.error(f"❌ Falha: {result.get('error', 'Erro desconhecido')}")

        st.divider()

    # ── Passo 1: Gerar URL de Autorização ─────────────────────────────────────
    st.markdown("### Passo 1 — Autorizar o App na Shopee")
    st.info("Clique no botão abaixo para gerar a URL. Você será redirecionado de volta automaticamente com o code já capturado.")

    if st.button("🔗 Gerar URL de Autorização", use_container_width=False):
        if not st.session_state.get("partner_id") or not st.session_state.get("partner_key"):
            st.warning("⚠️ Configure e salve o Partner ID e Partner Key em **⚙️ Configurações** primeiro.")
        else:
            url = sc.get_auth_url()
            st.success("URL gerada!")
            st.markdown(f"### [👉 Clique aqui para autorizar o app na Shopee]({url})")
            st.caption("Após autorizar, você voltará automaticamente para esta página com o code já preenchido.")
            st.code(url, language="text")

    st.divider()

    # ── Passo 2: Manual (fallback) ─────────────────────────────────────────────
    st.markdown("### Passo 2 — Trocar Code Manualmente (fallback)")
    st.caption("Use apenas se a captura automática não funcionar.")

    col1, col2 = st.columns(2)
    with col1:
        code_manual = st.text_input("Code", placeholder="Cole o code aqui")
    with col2:
        shop_id_manual = st.text_input(
            "Shop ID",
            value=st.session_state.get("shop_id", ""),
            placeholder="Ex: 560644869"
        )

    if st.button("🔑 Trocar Code Manualmente"):
        if not code_manual:
            st.warning("Cole o code gerado pela Shopee.")
        else:
            with st.spinner("Trocando code por token..."):
                result = sc.exchange_code_for_token(code_manual, shop_id=shop_id_manual or None)

            st.json(result)

            if result.get("access_token"):
                at = result["access_token"]
                rt = result.get("refresh_token", "")
                st.session_state["access_token"]  = at
                st.session_state["refresh_token"] = rt
                st.session_state["authenticated"] = True
                st.success("✅ Token obtido!")
                st.code(f"access_token = \"{at}\"", language="toml")
                st.code(f"refresh_token = \"{rt}\"", language="toml")
                st.warning("⚠️ Copie os tokens acima e atualize nos **Secrets do Streamlit**!")
            else:
                st.error(f"❌ Falha: {result.get('error', 'Erro desconhecido')}")

    st.divider()

    # ── Renovar Access Token ───────────────────────────────────────────────────
    st.markdown("### Renovar Access Token")
    st.info("Use quando o Access Token expirar (validade: 4 horas). O Refresh Token dura 30 dias.")

    refresh_input = st.text_input(
        "Refresh Token",
        value=st.session_state.get("refresh_token", ""),
        type="password",
        placeholder="Cole aqui ou já está preenchido da sessão"
    )

    if st.button("🔄 Renovar Access Token"):
        token_to_use = refresh_input.strip()
        if not token_to_use:
            st.warning("⚠️ Refresh Token vazio.")
        else:
            st.session_state["refresh_token"] = token_to_use
            with st.spinner("Renovando token..."):
                result = sc.refresh_access_token()

            st.json(result)

            if result.get("access_token"):
                at = result["access_token"]
                rt = result.get("refresh_token", "")
                st.success("✅ Token renovado!")
                st.code(f"access_token = \"{at}\"", language="toml")
                st.code(f"refresh_token = \"{rt}\"", language="toml")
                st.warning("⚠️ Copie os tokens acima e atualize nos **Secrets do Streamlit**!")
            else:
                st.error(f"❌ Falha: {result.get('error', 'Erro desconhecido')}")

    st.divider()

    # ── Status dos tokens na sessão ────────────────────────────────────────────
    st.markdown("### 📋 Tokens na sessão")
    col_a, col_b = st.columns(2)
    with col_a:
        at = st.session_state.get("access_token", "")
        st.metric("Access Token", "✅ Preenchido" if at else "❌ Vazio")
    with col_b:
        rt = st.session_state.get("refresh_token", "")
        st.metric("Refresh Token", "✅ Preenchido" if rt else "❌ Vazio")
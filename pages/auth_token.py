import streamlit as st
import shopee_client as sc


def render():
    st.markdown('<p class="section-title">🔄 Token / Auth</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Geração e renovação de tokens de acesso à API Shopee</p>', unsafe_allow_html=True)

    # ── Passo 1: Gerar URL de Autorização ──────────────────────────────────
    st.markdown("### Passo 1 — Autorizar o App na Shopee")
    st.info("Clique no botão abaixo para gerar a URL de autorização. Abra o link, autorize o app e você será redirecionado de volta com um `code` na URL.")

    if st.button("🔗 Gerar URL de Autorização", use_container_width=False):
        if not st.session_state.get("partner_id") or not st.session_state.get("partner_key"):
            st.warning("⚠️ Configure e salve o Partner ID e Partner Key em **Configurações** primeiro.")
        else:
            url = sc.get_auth_url()
            st.success("URL gerada com sucesso!")
            st.markdown(f"[👉 Clique aqui para autorizar o app na Shopee]({url})", unsafe_allow_html=False)
            st.code(url, language="text")

    st.divider()

    # ── Passo 2: Trocar Code por Token ─────────────────────────────────────
    st.markdown("### Passo 2 — Trocar o Code pelo Access Token")
    st.info("Após autorizar, copie o `code` que aparece na URL de retorno e cole abaixo.")

    col1, col2 = st.columns(2)
    with col1:
        code_input = st.text_input("Code (retornado pela Shopee na URL)", placeholder="Cole o code aqui")
    with col2:
        shop_id_input = st.text_input(
            "Shop ID (confirme)",
            value=st.session_state.get("shop_id", ""),
            placeholder="Ex: 560644869"
        )

    if st.button("🔑 Trocar Code por Access Token", use_container_width=False):
        if not code_input:
            st.warning("Cole o code gerado pela Shopee.")
        else:
            with st.spinner("Trocando code por token..."):
                result = sc.exchange_code_for_token(code_input, shop_id=shop_id_input or None)

            st.write("Retorno bruto:")
            st.json(result)

            if result.get("access_token"):
                st.success("✅ Access Token obtido com sucesso!")
                st.write(f"**Access Token:** `{result['access_token']}`")
                st.write(f"**Refresh Token:** `{result.get('refresh_token', '')}`")
                st.info("Os tokens foram salvos automaticamente na sessão. Vá em **Configurações** e salve para persistir.")
            else:
                st.error(f"❌ Falha: {result.get('error', 'Erro desconhecido')}")

    st.divider()

    # ── Passo 3: Renovar Access Token ──────────────────────────────────────
    st.markdown("### Renovar Access Token (usando Refresh Token)")
    st.info("Se o Access Token expirou (validade: 4 horas), use o Refresh Token para obter um novo sem precisar re-autorizar.")

    refresh_input = st.text_input(
        "Refresh Token",
        value=st.session_state.get("refresh_token", ""),
        type="password",
        placeholder="Cole aqui ou já está preenchido da sessão"
    )

    if st.button("🔄 Renovar Access Token", use_container_width=False):
        token_to_use = refresh_input.strip()
        if not token_to_use:
            st.warning("⚠️ Refresh Token vazio. Cole o Refresh Token acima antes de renovar.")
        elif not st.session_state.get("partner_id") or not st.session_state.get("partner_key"):
            st.warning("⚠️ Configure e salve as credenciais em **Configurações** primeiro.")
        else:
            # Garante que o refresh token está na sessão antes de chamar
            st.session_state["refresh_token"] = token_to_use

            with st.spinner("Renovando token..."):
                result = sc.refresh_access_token()

            st.write("Retorno bruto:")
            st.json(result)

            if result.get("access_token"):
                st.success("✅ Access Token renovado com sucesso!")
                st.write(f"**Novo Access Token:** `{result['access_token']}`")
                st.write(f"**Novo Refresh Token:** `{result.get('refresh_token', '')}`")
                st.info("Tokens atualizados na sessão. Vá em **Configurações** e salve para persistir.")
            else:
                st.error(f"❌ Falha ao renovar: {result.get('error', 'Erro desconhecido')}")
                if result.get("details"):
                    st.write("Detalhes:")
                    st.json(result["details"])

    st.divider()
    st.markdown("### 📋 Tokens ativos na sessão")
    col_a, col_b = st.columns(2)
    with col_a:
        at = st.session_state.get("access_token", "")
        st.metric("Access Token", "✅ Preenchido" if at else "❌ Vazio")
    with col_b:
        rt = st.session_state.get("refresh_token", "")
        st.metric("Refresh Token", "✅ Preenchido" if rt else "❌ Vazio")

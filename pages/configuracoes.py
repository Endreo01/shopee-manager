import streamlit as st
import shopee_client as sc


def render():
    st.markdown('<p class="section-title">⚙️ Configurações da API</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Insira suas credenciais do Shopee Open Platform</p>', unsafe_allow_html=True)

    with st.expander("ℹ️ Como obter suas credenciais?", expanded=False):
        st.markdown("""
        1. Acesse [open.shopee.com](https://open.shopee.com) e faça login
        2. Vá em **My Apps → Create App** (ou use um app existente)
        3. Em **Authorization Information**, copie o **Partner ID** e o **Partner Key**
        4. O **Shop ID** é o ID numérico da sua loja vendedora
        5. O **Access Token** você obtém via OAuth na aba **🔄 Token / Auth**

        > ⚠️ **Segurança:** Em produção no Streamlit Cloud, use a função **Secrets**
        > (Manage App → Secrets) para não expor suas chaves no código.
        """)

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        partner_id = st.text_input(
            "Partner ID (App ID) *",
            value=st.session_state.get("partner_id", ""),
            placeholder="Ex: 1234567",
            help="Número inteiro, encontrado no painel do seu app"
        )
        partner_key = st.text_input(
            "Partner Key (Secret Key) *",
            value=st.session_state.get("partner_key", ""),
            type="password",
            placeholder="Chave longa de letras e números",
        )

    with col2:
        shop_id = st.text_input(
            "Shop ID *",
            value=st.session_state.get("shop_id", ""),
            placeholder="Ex: 987654321",
            help="ID numérico da sua loja Shopee"
        )
        access_token = st.text_input(
            "Access Token",
            value=st.session_state.get("access_token", ""),
            type="password",
            placeholder="Obtido via OAuth (aba Token / Auth)",
        )

    refresh_token = st.text_input(
        "Refresh Token",
        value=st.session_state.get("refresh_token", ""),
        type="password",
        placeholder="Necessário para renovar o Access Token automaticamente",
    )

    st.divider()
    col_btn1, col_btn2, _ = st.columns([1, 1, 2])

    with col_btn1:
        if st.button("💾 Salvar Configurações", use_container_width=True):
            if not partner_id or not partner_key or not shop_id:
                st.error("Partner ID, Partner Key e Shop ID são obrigatórios.")
            else:
                st.session_state["partner_id"] = partner_id.strip()
                st.session_state["partner_key"] = partner_key.strip()
                st.session_state["shop_id"] = shop_id.strip()
                st.session_state["access_token"] = access_token.strip()
                st.session_state["refresh_token"] = refresh_token.strip()
                st.session_state["authenticated"] = bool(access_token.strip())
                st.success("✅ Configurações salvas com sucesso!")

    with col_btn2:
        if st.button("🔍 Testar Conexão", use_container_width=True):
            if not partner_id or not partner_key or not shop_id:
                st.warning("Preencha e salve Partner ID, Partner Key e Shop ID antes de testar.")
            else:
                st.session_state["partner_id"] = partner_id.strip()
                st.session_state["partner_key"] = partner_key.strip()
                st.session_state["shop_id"] = shop_id.strip()
                st.session_state["access_token"] = access_token.strip()
                st.session_state["refresh_token"] = refresh_token.strip()
                st.session_state["authenticated"] = bool(access_token.strip())

                with st.spinner("Testando conexão com a Shopee..."):
                    result = sc.get_shop_info()

                st.write("Retorno bruto da API:")
                st.json(result)

                if "error" in result:
                    st.error(f"❌ Erro ao conectar: {result['error']}")
                    if result.get("details"):
                        st.write("Detalhes do erro:")
                        st.json(result["details"])
                else:
                    st.success("✅ Conexão estabelecida com sucesso!")
                    st.write("Resposta tratada:")
                    st.json(result.get("response", result))

    st.divider()
    st.markdown("### 🔒 Usando Streamlit Secrets (Recomendado para equipe)")
    st.code("""
# Em Streamlit Community Cloud, vá em:
# Manage App → Settings → Secrets
# Cole isso lá (substitua pelos valores reais):

[shopee]
partner_id = "1234567"
partner_key = "sua_chave_aqui"
shop_id = "987654321"
access_token = "seu_token_aqui"
refresh_token = "seu_refresh_token_aqui"
""", language="toml")
    st.caption("Com os Secrets configurados, o app carrega as credenciais automaticamente sem precisar digitar.")

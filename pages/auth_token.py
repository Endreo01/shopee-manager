import streamlit as st
from shopee_client import get_auth_url, get_access_token_from_code, refresh_access_token

st.title("Autenticacao Shopee")

# --- Auto-detect code e shop_id na URL (retorno automatico da Shopee) ---
params = st.query_params
if "code" in params and "shop_id" in params:
    code     = params["code"]
    shop_id  = params["shop_id"]
    st.info("Retorno detectado da Shopee! Trocando code por token...")
    with st.spinner("Obtendo token..."):
        result = get_access_token_from_code(code, int(shop_id))
    if "access_token" in result:
        st.balloons()
        st.success("Autenticacao concluida com sucesso!")
        st.query_params.clear()
        st.rerun()
    else:
        st.error(f"Falha na troca de token: {result}")
    st.stop()

# --- Passo 1: Gerar URL ---
st.markdown("### 1) Gerar URL de autorizacao")
if st.button("Gerar URL"):
    if not st.session_state.get("partner_id") or not st.session_state.get("partner_key"):
        st.warning("Configure Partner ID e Partner Key em Configuracoes primeiro.")
    else:
        redirect_url = "https://shopee-manager.streamlit.app"
        auth_url = get_auth_url(redirect_url)
        st.session_state["auth_url"] = auth_url
        st.code(auth_url)
        st.info("Abra essa URL, faca login e autorize a loja. A Shopee vai redirecionar de volta automaticamente.")

# --- Passo 2: Obter token manualmente (fallback) ---
st.markdown("### 2) Obter Access Token (manual)")
st.caption("Use apenas se o redirecionamento automatico nao funcionar.")
auth_code     = st.text_input("Codigo de autorizacao (code)", placeholder="Cole aqui o codigo recebido na URL de retorno")
shop_id_input = st.text_input("Shop ID", placeholder="Numero da loja que autorizou")

col1, col2 = st.columns(2)
with col1:
    if st.button("Obter Access Token"):
        if not auth_code or not shop_id_input:
            st.warning("Preencha o code e o Shop ID.")
        else:
            with st.spinner("Trocando code por token..."):

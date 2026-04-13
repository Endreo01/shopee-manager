import streamlit as st
import shopee_client as sc
from zoneinfo import ZoneInfo
from datetime import datetime

BR = ZoneInfo("America/Sao_Paulo")



def _secret_ads(key):
    try:
        return st.secrets["shopee_ads"][key]
    except Exception:
        return None

def _secao_credenciais():
    st.markdown("### 🔑 Credenciais da API Shopee")

    with st.expander("ℹ️ Como obter suas credenciais?", expanded=False):
        st.markdown("""
        1. Acesse [open.shopee.com](https://open.shopee.com) e faça login
        2. Vá em **My Apps** → selecione seu app
        3. Copie o **Partner ID** e o **Partner Key** (Live)
        4. O **Shop ID** é o ID numérico da sua loja vendedora
        5. O **Access Token** é gerado na seção **Token** abaixo
        """)

    col1, col2 = st.columns(2)
    with col1:
        partner_id = st.text_input("Partner ID *",
            value=st.session_state.get("partner_id", ""),
            placeholder="Ex: 2031988")
        partner_key = st.text_input("Partner Key *",
            value=st.session_state.get("partner_key", ""),
            type="password", placeholder="shpk...")
    with col2:
        shop_id = st.text_input("Shop ID *",
            value=st.session_state.get("shop_id", ""),
            placeholder="Ex: 560644869")
        access_token = st.text_input("Access Token",
            value=st.session_state.get("access_token", ""),
            type="password", placeholder="Gerado na seção Token abaixo")

    refresh_token = st.text_input("Refresh Token",
        value=st.session_state.get("refresh_token", ""),
        type="password", placeholder="Gerado junto com o Access Token")

    col_s, col_t, _ = st.columns([1, 1, 2])
    with col_s:
        if st.button("💾 Salvar", use_container_width=True):
            if not partner_id or not partner_key or not shop_id:
                st.error("Partner ID, Partner Key e Shop ID são obrigatórios.")
            else:
                st.session_state["partner_id"]    = partner_id.strip()
                st.session_state["partner_key"]   = partner_key.strip()
                st.session_state["shop_id"]        = shop_id.strip()
                st.session_state["access_token"]  = access_token.strip()
                st.session_state["refresh_token"] = refresh_token.strip()
                st.session_state["authenticated"] = bool(access_token.strip())
                st.success("✅ Credenciais salvas!")

    with col_t:
        if st.button("🔍 Testar Conexão", use_container_width=True):
            st.session_state["partner_id"]    = partner_id.strip()
            st.session_state["partner_key"]   = partner_key.strip()
            st.session_state["shop_id"]        = shop_id.strip()
            st.session_state["access_token"]  = access_token.strip()
            st.session_state["refresh_token"] = refresh_token.strip()
            st.session_state["authenticated"] = bool(access_token.strip())
            with st.spinner("Testando..."):
                result = sc.get_shop_info()
            if result.get("error"):
                st.error(f"❌ {result['error']}")
            else:
                st.success(f"✅ Conectado! Loja: **{result.get('shop_name','')}** | {result.get('region','')} | {result.get('status','')}")


def _secao_token():
    st.markdown("---")
    st.markdown("### 🔄 Token / Autorização")

    # Captura automática do code via URL
    params     = st.query_params
    code_url   = params.get("code", "")
    shopid_url = params.get("shop_id", "")

    if code_url:
        st.success("✅ Code capturado automaticamente da URL!")
        st.info(f"Code: `{code_url}`  |  Shop ID: `{shopid_url}`")
        if st.button("🔑 Trocar Code por Access Token", type="primary"):
            with st.spinner("Trocando..."):
                result = sc.exchange_code_for_token(code_url, shop_id=shopid_url or None)
            st.json(result)
            if result.get("access_token"):
                at = result["access_token"]
                rt = result.get("refresh_token", "")
                st.session_state["access_token"]  = at
                st.session_state["refresh_token"] = rt
                st.session_state["authenticated"] = True
                st.success("✅ Token obtido!")
                st.warning("⚠️ Copie e salve nos **Secrets do Streamlit**:")
                st.code(f'access_token = "{at}"\nrefresh_token = "{rt}"', language="toml")
                st.query_params.clear()
            else:
                st.error(f"❌ {result.get('error','Erro desconhecido')}")
        st.divider()

    # Gerar URL
    st.markdown("#### Passo 1 — Gerar URL de Autorização")
    st.info("Clique abaixo para gerar o link. Após autorizar na Shopee, você volta aqui com o code já capturado.")

    if st.button("🔗 Gerar URL de Autorização"):
        if not st.session_state.get("partner_id") or not st.session_state.get("partner_key"):
            st.warning("Salve o Partner ID e Partner Key antes.")
        else:
            url = sc.get_auth_url()
            st.markdown(f"### [👉 Clique aqui para autorizar]({url})")
            st.code(url, language="text")

    st.markdown("#### Passo 2 — Code Manual (fallback)")
    col1, col2 = st.columns(2)
    with col1:
        code_manual = st.text_input("Code", placeholder="Cole o code aqui")
    with col2:
        shop_manual = st.text_input("Shop ID", value=st.session_state.get("shop_id",""))

    if st.button("🔑 Trocar Code Manualmente"):
        if not code_manual:
            st.warning("Cole o code.")
        else:
            with st.spinner("Trocando..."):
                result = sc.exchange_code_for_token(code_manual, shop_id=shop_manual or None)
            st.json(result)
            if result.get("access_token"):
                at = result["access_token"]
                rt = result.get("refresh_token", "")
                st.session_state["access_token"]  = at
                st.session_state["refresh_token"] = rt
                st.session_state["authenticated"] = True
                st.success("✅ Token obtido!")
                st.warning("⚠️ Copie e salve nos **Secrets do Streamlit**:")
                st.code(f'access_token = "{at}"\nrefresh_token = "{rt}"', language="toml")
            else:
                st.error(f"❌ {result.get('error','Erro desconhecido')}")

    st.markdown("#### Renovar Access Token")
    st.info("Access Token dura 4h. Refresh Token dura 30 dias.")
    refresh_input = st.text_input("Refresh Token",
        value=st.session_state.get("refresh_token",""),
        type="password", key="rt_renovar")

    if st.button("🔄 Renovar Token"):
        if not refresh_input.strip():
            st.warning("Refresh Token vazio.")
        else:
            st.session_state["refresh_token"] = refresh_input.strip()
            with st.spinner("Renovando..."):
                result = sc.refresh_access_token()
            st.json(result)
            if result.get("access_token"):
                at = result["access_token"]
                rt = result.get("refresh_token","")
                st.success("✅ Token renovado!")
                st.warning("⚠️ Copie e salve nos **Secrets do Streamlit**:")
                st.code(f'access_token = "{at}"\nrefresh_token = "{rt}"', language="toml")
            else:
                st.error(f"❌ {result.get('error','Erro desconhecido')}")

    # Status
    st.markdown("#### 📋 Status dos Tokens")
    ca, cb = st.columns(2)
    ca.metric("Access Token",  "✅ OK" if st.session_state.get("access_token") else "❌ Vazio")
    cb.metric("Refresh Token", "✅ OK" if st.session_state.get("refresh_token") else "❌ Vazio")

    st.markdown("#### 📝 Secrets do Streamlit")
    st.caption("Após obter os tokens, salve no Streamlit Cloud → Manage App → Settings → Secrets:")
    st.code("""[shopee]
partner_id    = "2031988"
partner_key   = "sua_partner_key"
shop_id       = "560644869"
access_token  = "token_gerado_aqui"
refresh_token = "refresh_gerado_aqui"

[supabase]
anon_key = "sb_publishable_k6EdTrPP-YRrf74h3rqJ4Q_q6LgQacS"
""", language="toml")



def _secao_ads_creds():
    st.markdown("---")
    st.markdown("### 📣 Credenciais do App de Ads")
    st.info("O app de Ads usa um Partner ID e Partner Key separados, mas o mesmo Shop ID e Access Token.")

    col1, col2 = st.columns(2)
    with col1:
        ads_partner_id = st.text_input(
            "Ads Partner ID *",
            value=st.session_state.get("ads_partner_id", "") or _secret_ads("partner_id") or "",
            placeholder="Ex: 2032349"
        )
    with col2:
        ads_partner_key = st.text_input(
            "Ads Partner Key *",
            value=st.session_state.get("ads_partner_key", "") or _secret_ads("partner_key") or "",
            type="password",
            placeholder="shpk..."
        )

    if st.button("💾 Salvar Credenciais de Ads", use_container_width=False):
        if not ads_partner_id or not ads_partner_key:
            st.error("Preencha o Ads Partner ID e Ads Partner Key.")
        else:
            st.session_state["ads_partner_id"]  = ads_partner_id.strip()
            st.session_state["ads_partner_key"] = ads_partner_key.strip()
            st.success("✅ Credenciais de Ads salvas!")

    st.markdown("#### 📝 Secrets do Streamlit — bloco Ads")
    st.code("""[shopee_ads]
partner_id  = "2032349"
partner_key = "shpk6b746761466d436f414b7353414556534c697771754d64705a4777465846"
""", language="toml")
    st.caption("Adicione este bloco nos Secrets do Streamlit Cloud para persistir as credenciais de Ads.")


def render():
    st.markdown('<p class="section-title">⚙️ Configurações</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Credenciais da API e gerenciamento de tokens</p>', unsafe_allow_html=True)

    _secao_credenciais()
    _secao_token()
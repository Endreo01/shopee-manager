import streamlit as st
import requests
import time
import hmac
import hashlib

BASE_URL = "https://partner.shopeemobile.com"

def _get_creds():
    return {
        "partner_id": int(st.session_state.get("partner_id", 0) or 0),
        "partner_key": st.session_state.get("partner_key", ""),
        "shop_id": int(st.session_state.get("shop_id", 0) or 0),
    }

def _sign(path, timestamp):
    c = _get_creds()
    base = f"{c['partner_id']}{path}{timestamp}"
    return hmac.new(c["partner_key"].encode(), base.encode(), hashlib.sha256).hexdigest()

def render():
    st.markdown('<p class="section-title">🔄 Token / Autorização OAuth</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Gere a URL, autorize a loja e obtenha os tokens</p>', unsafe_allow_html=True)

    c = _get_creds()
    if not c["partner_id"] or not c["partner_key"] or not c["shop_id"]:
        st.warning("Preencha Partner ID, Partner Key e Shop ID em Configurações antes de continuar.")
        return

    st.markdown("### 1) Gerar URL de autorização")
    if st.button("🔗 Gerar URL"):
        ts = int(time.time())
        path = "/api/v2/shop/auth_partner"
        sign = _sign(path, ts)
        redirect_url = "https://shopee-manager.streamlit.app"
        auth_url = (
            f"{BASE_URL}{path}"
            f"?partner_id={c['partner_id']}"
            f"&timestamp={ts}"
            f"&sign={sign}"
            f"&redirect={redirect_url}"
        )
        st.session_state["auth_url"] = auth_url
        st.code(auth_url)
        st.info("Abra essa URL, faça login e autorize a loja. Depois copie o parâmetro code da URL de retorno.")

    if st.session_state.get("auth_url"):
        st.markdown("### 2) Code de autorização")
        code = st.text_input("Cole aqui o code retornado pela Shopee")
        if st.button("🔐 Trocar code por token"):
            if not code:
                st.warning("Cole o code primeiro.")
                return

            ts = int(time.time())
            path = "/api/v2/auth/token/get"
            sign = _sign(path, ts)

            params = {
                "partner_id": c["partner_id"],
                "timestamp": ts,
                "sign": sign,
            }
            body = {
                "code": code,
                "shop_id": c["shop_id"],
                "partner_id": c["partner_id"],
            }

            try:
                resp = requests.post(BASE_URL + path, params=params, json=body, timeout=20)
                data = resp.json()
                st.json(data)

                if "access_token" in data:
                    st.session_state["access_token"] = data["access_token"]
                    st.session_state["refresh_token"] = data.get("refresh_token", "")
                    st.session_state["authenticated"] = True
                    st.success("Tokens obtidos com sucesso!")
                else:
                    st.error("Não foi possível obter os tokens. Confira o retorno acima.")
            except Exception as e:
                st.error(str(e))

    st.markdown("### 3) Status atual")
    st.write("Access Token:", "✅" if st.session_state.get("access_token") else "❌")
    st.write("Refresh Token:", "✅" if st.session_state.get("refresh_token") else "❌")

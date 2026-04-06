"""
Cliente para a Shopee Open Platform API v2.
Documentacao: https://open.shopee.com/developer-guide/4
"""
import hashlib
import hmac
import time
import requests
import streamlit as st

BASE_URL = "https://partner.shopeemobile.com"


def _get_credentials():
    if not st.session_state.get("partner_id") and "shopee" in st.secrets:
        s = st.secrets["shopee"]
        st.session_state["partner_id"]    = s.get("partner_id", "")
        st.session_state["partner_key"]   = s.get("partner_key", "")
        st.session_state["shop_id"]       = s.get("shop_id", "")
        st.session_state["access_token"]  = s.get("access_token", "")
        st.session_state["refresh_token"] = s.get("refresh_token", "")
        st.session_state["authenticated"] = bool(s.get("access_token", ""))
    return {
        "partner_id":   int(st.session_state.get("partner_id", 0) or 0),
        "partner_key":  st.session_state.get("partner_key", ""),
        "shop_id":      int(st.session_state.get("shop_id", 0) or 0),
        "access_token": st.session_state.get("access_token", ""),
    }


def _sign(api_path, timestamp, access_token="", shop_id=0):
    creds = _get_credentials()
    base = f"{creds['partner_id']}{api_path}{timestamp}{access_token}{shop_id}"
    return hmac.new(
        creds["partner_key"].encode("utf-8"),
        base.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _call(method, api_path, params=None, body=None):
    creds = _get_credentials()
    if not creds["partner_id"] or not creds["partner_key"]:
        return {"error": "Credenciais nao configuradas. Acesse Configuracoes."}

    ts   = int(time.time())
    sign = _sign(api_path, ts, creds["access_token"], creds["shop_id"])

    base_params = {
        "partner_id":   creds["partner_id"],
        "timestamp":    ts,
        "access_token": creds["access_token"],
        "shop_id":      creds["shop_id"],
        "sign":         sign,
    }
    if params:
        base_params.update(params)

    url = BAS

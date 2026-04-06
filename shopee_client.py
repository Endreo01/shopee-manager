"""
shopee_client.py
Cliente para a Shopee Open Platform API v2.
Documentação: https://open.shopee.com/developer-guide/4
"""

import hashlib
import hmac
import time
import requests
import streamlit as st

BASE_URL = "https://partner.shopeemobile.com"


def _get_credentials():
    """Lê as credenciais do st.session_state ou dos Secrets do Streamlit Cloud."""
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


def _sign(api_path: str, timestamp: int, access_token: str = "", shop_id: int = 0) -> str:
    """
    Gera a assinatura HMAC-SHA256 conforme documentação Shopee v2.
    Base string: partner_id + api_path + timestamp + access_token + shop_id
    """
    creds = _get_credentials()
    base = f"{creds['partner_id']}{api_path}{timestamp}{access_token}{shop_id}"
    return hmac.new(
        creds["partner_key"].encode("utf-8"),
        base.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _call(method: str, api_path: str, params: dict = None, body: dict = None) -> dict:
    """Executa uma chamada autenticada à API Shopee v2."""
    creds = _get_credentials()

    if not creds["partner_id"] or not creds["partner_key"]:
        return {"error": "Credenciais não configuradas. Acesse ⚙️ Configurações."}

    ts = int(time.time())
    sign = _sign(api_path, ts, creds["access_token"], creds["shop_id"])

    base_params = {
        "partner_id": creds["partner_id"],
        "timestamp": ts,
        "access_token": creds["access_token"],
        "shop_id": creds["shop_id"],
        "sign": sign,
    }
    if params:
        base_params.update(params)

    url = BASE_URL + api_path
    try:
        if method.upper() == "GET":
            resp = requests.get(url, params=base_params, timeout=15)
        else:
            resp = requests.post(url, params=base_params, json=body or {}, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


# ─── Funções públicas por módulo ──────────────────────────────────────────────

# SHOP
def get_shop_info() -> dict:
    return _call("GET", "/api/v2/shop/get_shop_info")


# PRODUTOS
def get_item_list(offset: int = 0, page_size: int = 50, status: str = "NORMAL") -> dict:
    return _call("GET", "/api/v2/product/get_item_list", {
        "offset": offset, "page_size": page_size, "item_status": status
    })


def get_item_base_info(item_ids: list) -> dict:
    return _call("GET", "/api/v2/product/get_item_base_info", {
        "item_id_list": ",".join(map(str, item_ids))
    })


def update_price(item_id: int, model_id: int, current_price: float) -> dict:
    body = {
        "item_id": item_id,
        "price_list": [{"model_id": model_id, "original_price": current_price}]
    }
    return _call("POST", "/api/v2/product/update_price", body=body)


def update_stock(item_id: int, model_id: int, normal_stock: int) -> dict:
    body = {
        "item_id": item_id,
        "stock_list": [{"model_id": model_id, "normal_stock": normal_stock}]
    }
    return _call("POST", "/api/v2/product/update_stock", body=body)


# PEDIDOS
def get_order_list(time_from: int, time_to: int, status: str = "READY_TO_SHIP") -> dict:
    return _call("GET", "/api/v2/order/get_order_list", {
        "time_range_field": "create_time",
        "time_from": time_from,
        "time_to": time_to,
        "page_size": 50,
        "order_status": status,
    })


def get_order_detail(order_sn_list: list) -> dict:
    return _call("GET", "/api/v2/order/get_order_detail", {
        "order_sn_list": ",".join(order_sn_list),
        "response_optional_fields": "item_list,recipient_address,note"
    })


# ADS
def get_ads_campaigns() -> dict:
    return _call("GET", "/api/v2/ads/get_all_campaigns")


def toggle_campaign(campaign_id: int, operation: str) -> dict:
    """operation: 'ON' ou 'OFF'"""
    body = {"campaign_id": campaign_id, "operation": operation}
    return _call("POST", "/api/v2/ads/update_campaign_status", body=body)


# AUTH / TOKEN
def get_auth_url(redirect_url: str = "https://shopee-manager.streamlit.app") -> str:
    """Gera a URL de autorização OAuth para o lojista."""
    creds = _get_credentials()
    ts = int(time.time())
    path = "/api/v2/shop/auth_partner"
    base = f"{creds['partner_id']}{path}{ts}"
    sign = hmac.new(
        creds["partner_key"].encode(), base.encode(), hashlib.sha256
    ).hexdigest()
    return (
        f"{BASE_URL}{path}"
        f"?partner_id={creds['partner_id']}"
        f"&timestamp={ts}&sign={sign}"
        f"&redirect={redirect_url}"
    )


def get_access_token_from_code(code: str, shop_id: int) -> dict:
    """Troca o code de autorização da Shopee por access_token e refresh_token."""
    creds = _get_credentials()
    path  = "/api/v2/auth/token/get"
    ts    = int(time.time())
    base  = f"{creds['partner_id']}{path}{ts}"
    sign  = hmac.new(creds["partner_key"].encode(), base.encode(), hashlib.sha256).hexdigest()
    body  = {
        "code":       code,
        "shop_id":    shop_id,
        "partner_id": creds["partner_id"]
    }
    params = {
        "partner_id": creds["partner_id"],
        "timestamp":  ts,
        "sign":       sign
    }
    try:
        resp = requests.post(BASE_URL + path, params=params, json=body, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if "access_token" in data:
            st.session_state["access_token"]  = data["access_token"]
            st.session_state["refresh_token"] = data.get("refresh_token", "")
            st.session_state["shop_id"]       = shop_id
            st.session_state["authenticated"] = True
        return data
    except Exception as e:
        return {"error": str(e)}


def refresh_access_token() -> dict:
    """Usa o refresh_token para obter um novo access_token."""
    creds = _get_credentials()
    path = "/api/v2/auth/access_token/get"
    ts = int(time.time())
    base = f"{creds['partner_id']}{path}{ts}"
    sign = hmac.new(
        creds["partner_key"].encode(), base.encode(), hashlib.sha256
    ).hexdigest()
    body = {
        "refresh_token": st.session_state.get("refresh_token", ""),
        "partner_id": creds["partner_id"],
        "shop_id": creds["shop_id"],
    }
    params = {
        "partner_id": creds["partner_id"],
        "timestamp": ts,
        "sign": sign,
    }
    try:
        resp = requests.post(BASE_URL + path, params=params, json=body, timeout=15)
        data = resp.json()
        if "access_token" in data:
            st.session_state["access_token"] = data["access_token"]
            st.session_state["refresh_token"] = data.get("refresh_token", st.session_state["refresh_token"])
        return data
    except Exception as e:
        return {"error": str(e)}

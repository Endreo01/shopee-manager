import hashlib
import hmac
import time
import requests
import streamlit as st

BASE_URL = "https://partner.shopeemobile.com"
APP_REDIRECT = "https://shopee-manager.streamlit.app"

# Renova se faltar menos de 30 minutos para expirar
TOKEN_REFRESH_THRESHOLD = 30 * 60  # segundos


def _get_credentials():
    return {
        "partner_id": int(st.session_state.get("partner_id", 0) or 0),
        "partner_key": st.session_state.get("partner_key", ""),
        "shop_id": int(st.session_state.get("shop_id", 0) or 0),
        "access_token": st.session_state.get("access_token", ""),
        "refresh_token": st.session_state.get("refresh_token", ""),
    }


def _token_needs_refresh() -> bool:
    expire_time = st.session_state.get("token_expire_time", 0)
    if not expire_time:
        return False
    return (int(expire_time) - int(time.time())) < TOKEN_REFRESH_THRESHOLD


def _auto_refresh_token():
    if not _token_needs_refresh():
        return
    refresh_token = st.session_state.get("refresh_token", "")
    if not refresh_token:
        return
    result = refresh_access_token()
    if result.get("access_token"):
        st.toast("🔄 Access Token renovado automaticamente!", icon="✅")


def _sign(api_path: str, timestamp: int, access_token: str = "", shop_id: int = 0) -> str:
    creds = _get_credentials()
    base = f"{creds['partner_id']}{api_path}{timestamp}{access_token}{shop_id}"
    return hmac.new(
        creds["partner_key"].encode("utf-8"),
        base.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _call(method: str, api_path: str, params: dict | None = None, body: dict | None = None) -> dict:
    creds = _get_credentials()

    if not creds["partner_id"] or not creds["partner_key"] or not creds["shop_id"]:
        return {"error": "Partner ID, Partner Key e Shop ID são obrigatórios."}

    if api_path != "/api/v2/shop/auth_partner" and not creds["access_token"]:
        return {"error": "Access Token ausente. Gere o token na aba Token / Auth."}

    _auto_refresh_token()
    creds = _get_credentials()

    ts = int(time.time())
    sign = _sign(api_path, ts, creds["access_token"], creds["shop_id"])

    req_params = {
        "partner_id": creds["partner_id"],
        "timestamp": ts,
        "sign": sign,
        "shop_id": creds["shop_id"],
        "access_token": creds["access_token"],
    }
    if params:
        req_params.update(params)

    url = f"{BASE_URL}{api_path}"

    try:
        if method.upper() == "GET":
            resp = requests.get(url, params=req_params, timeout=30)
        else:
            resp = requests.post(url, params=req_params, json=body or {}, timeout=30)

        data = resp.json()

        if resp.status_code != 200:
            return {
                "error": data.get("message") or data.get("error") or f"HTTP {resp.status_code}",
                "details": data,
                "status_code": resp.status_code,
            }

        if data.get("error"):
            return {
                "error": data.get("message") or data.get("error"),
                "details": data,
            }

        if data.get("expire_time"):
            st.session_state["token_expire_time"] = data["expire_time"]

        return data
    except Exception as e:
        return {"error": str(e)}


# ── Endpoints existentes ──────────────────────────────────────────────────────

def get_shop_info() -> dict:
    return _call("GET", "/api/v2/shop/get_shop_info")


def get_item_list(offset: int = 0, page_size: int = 50, status: str = "NORMAL") -> dict:
    return _call("GET", "/api/v2/product/get_item_list", {
        "offset": offset,
        "page_size": page_size,
        "item_status": status,
    })


def get_item_base_info(item_ids: list) -> dict:
    return _call("GET", "/api/v2/product/get_item_base_info", {
        "item_id_list": ",".join(map(str, item_ids))
    })


def get_item_extra_info(item_ids: list) -> dict:
    return _call("GET", "/api/v2/product/get_item_extra_info", {
        "item_id_list": ",".join(map(str, item_ids))
    })


def update_price(item_id: int, model_id: int, current_price: float) -> dict:
    body = {
        "item_id": item_id,
        "price_list": [{"model_id": model_id, "original_price": current_price}],
    }
    return _call("POST", "/api/v2/product/update_price", body=body)


def update_stock(item_id: int, model_id: int, normal_stock: int) -> dict:
    body = {
        "item_id": item_id,
        "stock_list": [{"model_id": model_id, "normal_stock": normal_stock}],
    }
    return _call("POST", "/api/v2/product/update_stock", body=body)


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
        "response_optional_fields": "item_list,recipient_address,note",
    })


def get_ads_campaigns() -> dict:
    return _call("GET", "/api/v2/ads/get_all_campaigns")


def toggle_campaign(campaign_id: int, operation: str) -> dict:
    body = {"campaign_id": campaign_id, "operation": operation}
    return _call("POST", "/api/v2/ads/update_campaign_status", body=body)


def get_auth_url() -> str:
    creds = _get_credentials()
    ts = int(time.time())
    path = "/api/v2/shop/auth_partner"
    base = f"{creds['partner_id']}{path}{ts}"
    sign = hmac.new(
        creds["partner_key"].encode("utf-8"),
        base.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return (
        f"{BASE_URL}{path}"
        f"?partner_id={creds['partner_id']}"
        f"&timestamp={ts}"
        f"&sign={sign}"
        f"&redirect={APP_REDIRECT}"
    )


def exchange_code_for_token(code: str, shop_id: int | None = None) -> dict:
    creds = _get_credentials()
    use_shop_id = int(shop_id or creds["shop_id"] or 0)
    path = "/api/v2/auth/token/get"
    ts = int(time.time())
    base = f"{creds['partner_id']}{path}{ts}"
    sign = hmac.new(
        creds["partner_key"].encode("utf-8"),
        base.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    params = {"partner_id": creds["partner_id"], "timestamp": ts, "sign": sign}
    body = {"code": code, "partner_id": creds["partner_id"], "shop_id": use_shop_id}

    try:
        resp = requests.post(f"{BASE_URL}{path}", params=params, json=body, timeout=30)
        data = resp.json()
        if resp.status_code != 200:
            return {
                "error": data.get("message") or data.get("error") or f"HTTP {resp.status_code}",
                "details": data,
            }
        if data.get("access_token"):
            st.session_state["access_token"] = data["access_token"]
            st.session_state["refresh_token"] = data.get("refresh_token", "")
            st.session_state["shop_id"] = str(use_shop_id)
            st.session_state["authenticated"] = True
            if data.get("expire_time"):
                st.session_state["token_expire_time"] = data["expire_time"]
        return data
    except Exception as e:
        return {"error": str(e)}


def refresh_access_token() -> dict:
    creds = _get_credentials()
    path = "/api/v2/auth/access_token/get"
    ts = int(time.time())
    base = f"{creds['partner_id']}{path}{ts}"
    sign = hmac.new(
        creds["partner_key"].encode("utf-8"),
        base.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    params = {"partner_id": creds["partner_id"], "timestamp": ts, "sign": sign}
    body = {
        "refresh_token": creds["refresh_token"],
        "partner_id": creds["partner_id"],
        "shop_id": creds["shop_id"],
    }

    try:
        resp = requests.post(f"{BASE_URL}{path}", params=params, json=body, timeout=30)
        data = resp.json()
        if resp.status_code != 200:
            return {
                "error": data.get("message") or data.get("error") or f"HTTP {resp.status_code}",
                "details": data,
            }
        if data.get("access_token"):
            st.session_state["access_token"] = data["access_token"]
            st.session_state["refresh_token"] = data.get("refresh_token", creds["refresh_token"])
            st.session_state["authenticated"] = True
            if data.get("expire_time"):
                st.session_state["token_expire_time"] = data["expire_time"]
        return data
    except Exception as e:
        return {"error": str(e)}


# ── Funções novas ─────────────────────────────────────────────────────────────

def get_all_item_ids(status: str = "NORMAL") -> list[int]:
    """Pagina automaticamente e retorna todos os item_ids da loja."""
    all_ids = []
    offset = 0
    while True:
        result = get_item_list(offset=offset, page_size=100, status=status)
        items = result.get("response", {}).get("item", [])
        if not items:
            break
        all_ids.extend(i["item_id"] for i in items)
        if not result.get("response", {}).get("has_next_page", False):
            break
        offset += 100
    return all_ids


def search_item(keyword: str, search_by: str = "name", offset: int = 0, page_size: int = 40) -> dict:
    """
    Busca produtos por nome ou SKU.
    search_by: 'name' → item_name  |  'sku' → item_sku
    """
    extra = {"offset": offset, "page_size": page_size}
    if search_by == "sku":
        extra["item_sku"] = keyword
    else:
        extra["item_name"] = keyword
    return _call("GET", "/api/v2/product/search_item", extra)


def get_items_with_details(item_ids: list[int]) -> list[dict]:
    """Busca base_info + extra_info em lotes de 50 e mescla num único dict por produto."""
    all_items = []
    for i in range(0, len(item_ids), 50):
        batch = item_ids[i:i + 50]
        base_list  = get_item_base_info(batch).get("response", {}).get("item_list", [])
        extra_list = get_item_extra_info(batch).get("response", {}).get("item_extra_info_list", [])
        extra_map  = {e["item_id"]: e for e in extra_list}
        for item in base_list:
            extra = extra_map.get(item.get("item_id"), {})
            item["view_count"]      = extra.get("view_count", 0)
            item["liked_count"]     = extra.get("liked_count", item.get("liked_count", 0))
            item["sold_count"]      = extra.get("sold_count", 0)
            item["conversion_rate"] = extra.get("conversion_rate", 0)
            all_items.append(item)
    return all_items

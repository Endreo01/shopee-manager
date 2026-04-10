import hashlib
import hmac
import time
import requests
import streamlit as st


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_int(val):
    """Converte para int com segurança, removendo espaços e caracteres invisíveis."""
    try:
        return int(str(val).strip())
    except (ValueError, TypeError):
        return None


def _get_creds():
    pid  = st.session_state.get("partner_id")   or _secret("partner_id")
    pkey = st.session_state.get("partner_key")  or _secret("partner_key")
    sid  = st.session_state.get("shop_id")      or _secret("shop_id")
    at   = st.session_state.get("access_token") or _secret("access_token")
    rt   = st.session_state.get("refresh_token")or _secret("refresh_token")
    return (
        str(pid).strip()  if pid  else None,
        str(pkey).strip() if pkey else None,
        str(sid).strip()  if sid  else None,
        str(at).strip()   if at   else None,
        str(rt).strip()   if rt   else None,
    )


def _secret(key):
    try:
        return st.secrets["shopee"][key]
    except Exception:
        return None


BASE_URL = "https://partner.shopeemobile.com"


# ── Assinatura ────────────────────────────────────────────────────────────────

def _sign(path, timestamp, access_token, shop_id, partner_id, partner_key):
    base = f"{partner_id}{path}{timestamp}{access_token}{shop_id}"
    return hmac.new(partner_key.encode(), base.encode(), hashlib.sha256).hexdigest()


def _sign_no_auth(path, timestamp, partner_id, partner_key):
    base = f"{partner_id}{path}{timestamp}"
    return hmac.new(partner_key.encode(), base.encode(), hashlib.sha256).hexdigest()


# ── Chamada genérica ──────────────────────────────────────────────────────────

def _call(method, path, extra_params=None, body=None, require_auth=True):
    pid, pkey, sid, at, _ = _get_creds()

    if not pid or not pkey:
        return {"error": "Partner ID / Partner Key não configurados. Acesse ⚙️ Configurações."}
    if require_auth and (not sid or not at):
        return {"error": "Shop ID / Access Token não configurados. Acesse ⚙️ Configurações."}

    pid_int = _safe_int(pid)
    sid_int = _safe_int(sid)

    if pid_int is None:
        return {"error": f"Partner ID inválido: '{pid}'. Deve ser numérico."}
    if require_auth and sid_int is None:
        return {"error": f"Shop ID inválido: '{sid}'. Deve ser numérico."}

    timestamp = int(time.time())

    if require_auth:
        sign = _sign(path, timestamp, at, sid_int, pid_int, pkey)
        params = {
            "partner_id":   pid_int,
            "timestamp":    timestamp,
            "access_token": at,
            "shop_id":      sid_int,
            "sign":         sign,
        }
    else:
        sign = _sign_no_auth(path, timestamp, pid_int, pkey)
        params = {
            "partner_id": pid_int,
            "timestamp":  timestamp,
            "sign":       sign,
        }

    if extra_params:
        params.update(extra_params)

    url = BASE_URL + path
    try:
        if method == "GET":
            resp = requests.get(url, params=params, timeout=30)
        else:
            payload = body if body is not None else (extra_params or {})
            resp = requests.post(url, params=params, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        try:
            details = e.response.json()
        except Exception:
            details = {}
        return {"error": str(e), "details": details}
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


# ── Shop ──────────────────────────────────────────────────────────────────────

def get_shop_info():
    result = _call("GET", "/api/v2/shop/get_shop_info")
    if result.get("error"):
        return result
    resp = result.get("response", result)
    return {
        "shop_name": resp.get("shop_name", ""),
        "region":    resp.get("region", ""),
        "status":    resp.get("status", ""),
        "raw":       result,
    }


# ── Auth / Token ──────────────────────────────────────────────────────────────

def get_auth_url():
    pid, pkey, _, _, _ = _get_creds()
    timestamp = int(time.time())
    redirect  = "https://localhost"
    path      = "/api/v2/shop/auth_partner"
    sign      = _sign_no_auth(path, timestamp, _safe_int(pid), pkey)
    return (
        f"{BASE_URL}{path}"
        f"?partner_id={pid}"
        f"&timestamp={timestamp}"
        f"&sign={sign}"
        f"&redirect={redirect}"
    )


def exchange_code_for_token(code, shop_id=None):
    pid, pkey, sid, _, _ = _get_creds()
    sid       = shop_id or sid
    path      = "/api/v2/auth/token/get"
    timestamp = int(time.time())
    sign      = _sign_no_auth(path, timestamp, _safe_int(pid), pkey)

    params = {"partner_id": _safe_int(pid), "timestamp": timestamp, "sign": sign}
    body   = {"code": code, "shop_id": _safe_int(sid), "partner_id": _safe_int(pid)}

    try:
        resp = requests.post(BASE_URL + path, params=params, json=body, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

    at = data.get("access_token") or data.get("response", {}).get("access_token")
    rt = data.get("refresh_token") or data.get("response", {}).get("refresh_token")

    if at:
        st.session_state["access_token"]  = at
        st.session_state["refresh_token"] = rt or ""
        st.session_state["authenticated"] = True

    return data


def refresh_access_token():
    pid, pkey, sid, _, rt = _get_creds()
    if not rt:
        return {"error": "Refresh Token não encontrado na sessão."}

    path      = "/api/v2/auth/access_token/get"
    timestamp = int(time.time())
    sign      = _sign_no_auth(path, timestamp, _safe_int(pid), pkey)

    params = {"partner_id": _safe_int(pid), "timestamp": timestamp, "sign": sign}
    body   = {"refresh_token": rt, "shop_id": _safe_int(sid), "partner_id": _safe_int(pid)}

    try:
        resp = requests.post(BASE_URL + path, params=params, json=body, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

    at_new = data.get("access_token") or data.get("response", {}).get("access_token")
    rt_new = data.get("refresh_token") or data.get("response", {}).get("refresh_token")

    if at_new:
        st.session_state["access_token"]  = at_new
        st.session_state["refresh_token"] = rt_new or rt
        st.session_state["authenticated"] = True

    return data


# ── Produtos ──────────────────────────────────────────────────────────────────

def get_item_list(offset=0, page_size=100, status="NORMAL"):
    return _call("GET", "/api/v2/product/get_item_list", {
        "offset":      offset,
        "page_size":   page_size,
        "item_status": status,
    })


def get_item_base_info(item_ids):
    return _call("GET", "/api/v2/product/get_item_base_info", {
        "item_id_list":          ",".join(str(i) for i in item_ids),
        "need_tax_info":         True,
        "need_complaint_policy": False,
    })


def get_item_extra_info(item_ids):
    return _call("GET", "/api/v2/product/get_item_extra_info", {
        "item_id_list": ",".join(str(i) for i in item_ids),
    })


def get_all_item_ids(status="NORMAL"):
    all_ids = []
    offset  = 0
    while True:
        result = get_item_list(offset=offset, page_size=100, status=status)
        items  = result.get("response", {}).get("item", [])
        if not items:
            break
        all_ids.extend(i["item_id"] for i in items)
        if not result.get("response", {}).get("has_next_page", False):
            break
        offset += 100
    return all_ids


def get_items_with_details(item_ids):
    all_items = []
    for i in range(0, len(item_ids), 50):
        batch      = item_ids[i:i + 50]
        base_list  = get_item_base_info(batch).get("response", {}).get("item_list", [])
        extra_list = get_item_extra_info(batch).get("response", {}).get("item_list", [])
        extra_map  = {e["item_id"]: e for e in extra_list}
        for item in base_list:
            extra = extra_map.get(item.get("item_id"), {})
            item["sale"]          = extra.get("sale", 0)
            item["views"]         = extra.get("views", 0)
            item["likes"]         = extra.get("likes", 0)
            item["rating_star"]   = extra.get("rating_star", 0)
            item["comment_count"] = extra.get("comment_count", 0)
            all_items.append(item)
    return all_items


def find_by_sku_exact(sku, status="NORMAL"):
    sku_alvo = sku.strip().lower()
    all_ids  = get_all_item_ids(status=status)
    matched  = []
    for i in range(0, len(all_ids), 50):
        res = get_item_base_info(all_ids[i:i + 50])
        for it in res.get("response", {}).get("item_list", []):
            if (it.get("item_sku") or "").strip().lower() == sku_alvo:
                matched.append(it["item_id"])
    return matched


# ── Preços ────────────────────────────────────────────────────────────────────

def update_price(item_id, model_id=0, price=None):
    return _call(
        "POST",
        "/api/v2/product/update_price",
        body={
            "item_id":    _safe_int(item_id),
            "price_list": [{"model_id": _safe_int(model_id) or 0, "original_price": float(price)}],
        },
    )


def update_item_price(item_id, price):
    return update_price(item_id, model_id=0, price=price)


# ── Estoque ───────────────────────────────────────────────────────────────────

def update_stock(item_id, model_id=0, stock=0):
    return _call(
        "POST",
        "/api/v2/product/update_stock",
        body={
            "item_id":    _safe_int(item_id),
            "stock_list": [{"model_id": _safe_int(model_id) or 0, "normal_stock": int(stock)}],
        },
    )


# ── Pedidos ───────────────────────────────────────────────────────────────────

def get_order_list(time_from, time_to, page_size=50, cursor="", status="READY_TO_SHIP"):
    return _call("GET", "/api/v2/order/get_order_list", {
        "time_range_field": "create_time",
        "time_from":        int(time_from),
        "time_to":          int(time_to),
        "page_size":        page_size,
        "cursor":           cursor,
        "order_status":     status,
    })


def get_order_detail(order_sn_list):
    return _call("GET", "/api/v2/order/get_order_detail", {
        "order_sn_list":            ",".join(order_sn_list),
        "response_optional_fields": "item_list,package_list,buyer_info",
    })


def get_all_orders(time_from, time_to, status="READY_TO_SHIP"):
    all_sns = []
    cursor  = ""
    while True:
        result     = get_order_list(time_from, time_to, page_size=50, cursor=cursor, status=status)
        order_list = result.get("response", {}).get("order_list", [])
        if not order_list:
            break
        all_sns.extend(o["order_sn"] for o in order_list)
        more   = result.get("response", {}).get("more", False)
        cursor = result.get("response", {}).get("next_cursor", "")
        if not more or not cursor:
            break
    return all_sns


# ── Ads ───────────────────────────────────────────────────────────────────────

def get_ads_campaigns():
    return _call("GET", "/api/v2/ads/get_all_campaigns", {
        "page_size":   100,
        "page_number": 1,
    })


def toggle_campaign(campaign_id, action):
    return _call(
        "POST",
        "/api/v2/ads/update_campaign_status",
        body={
            "campaign_id":     _safe_int(campaign_id),
            "campaign_status": action,
        },
    )


# ── Dashboard ─────────────────────────────────────────────────────────────────

def get_dashboard_metrics():
    metrics = {
        "produtos_ativos":   0,
        "pedidos_pendentes": 0,
        "estoque_zerado":    0,
        "error":             None,
    }

    result = get_item_list(offset=0, page_size=1, status="NORMAL")
    if result.get("error"):
        metrics["error"] = result["error"]
        return metrics
    metrics["produtos_ativos"] = result.get("response", {}).get("total_count", 0)

    now       = int(time.time())
    time_from = now - 15 * 86400
    all_sns   = get_all_orders(time_from, now, status="READY_TO_SHIP")
    metrics["pedidos_pendentes"] = len(all_sns)

    all_ids = get_all_item_ids(status="NORMAL")
    zerado  = 0
    for i in range(0, min(len(all_ids), 200), 50):
        res = get_item_base_info(all_ids[i:i + 50])
        for it in res.get("response", {}).get("item_list", []):
            sl    = it.get("stock_info_v2", {}).get("seller_stock", [])
            total = sl[0].get("stock", 0) if sl else 0
            if total == 0:
                zerado += 1
    metrics["estoque_zerado"] = zerado

    return metrics
import hashlib
import hmac
import time
import requests
import streamlit as st


def _load_secrets():
    try:
        cfg = st.secrets["shopee"]
        return (
            cfg["partner_id"],
            cfg["partner_key"],
            cfg["shop_id"],
            cfg["access_token"],
        )
    except Exception:
        return None, None, None, None


BASE_URL = "https://partner.shopeemobile.com"


def _sign(path, timestamp, access_token, shop_id, partner_id, partner_key):
    base = f"{partner_id}{path}{timestamp}{access_token}{shop_id}"
    return hmac.new(partner_key.encode(), base.encode(), hashlib.sha256).hexdigest()


def _call(method, path, extra_params=None):
    partner_id, partner_key, shop_id, access_token = _load_secrets()
    if not partner_id:
        return {"error": "Credenciais nao configuradas em st.secrets['shopee']"}

    timestamp = int(time.time())
    sign = _sign(path, timestamp, access_token, shop_id, partner_id, partner_key)

    params = {
        "partner_id": partner_id,
        "timestamp": timestamp,
        "access_token": access_token,
        "shop_id": shop_id,
        "sign": sign,
    }
    if extra_params:
        params.update(extra_params)

    url = BASE_URL + path
    try:
        if method == "GET":
            resp = requests.get(url, params=params, timeout=30)
        else:
            resp = requests.post(url, params=params, json=extra_params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


# ── Produtos ──────────────────────────────────────────────────────────────────

def get_item_list(offset=0, page_size=100, status="NORMAL"):
    return _call("GET", "/api/v2/product/get_item_list", {
        "offset": offset,
        "page_size": page_size,
        "item_status": status,
    })


def get_item_base_info(item_ids):
    return _call("GET", "/api/v2/product/get_item_base_info", {
        "item_id_list": ",".join(str(i) for i in item_ids),
        "need_tax_info": True,
        "need_complaint_policy": False,
    })


def get_item_extra_info(item_ids):
    """Retorna: sale, views, likes, rating_star, comment_count por item."""
    return _call("GET", "/api/v2/product/get_item_extra_info", {
        "item_id_list": ",".join(str(i) for i in item_ids),
    })


def get_all_item_ids(status="NORMAL"):
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


def find_by_sku_exact(sku, status="NORMAL"):
    """
    Busca pelo SKU EXATO do vendedor dentro da propria loja.
    Retorna lista de item_ids que batem com o SKU.
    Uso: item_ids = sc.find_by_sku_exact("15314")
    """
    sku_alvo = sku.strip().lower()
    all_ids = get_all_item_ids(status=status)
    matched = []
    for i in range(0, len(all_ids), 50):
        batch = all_ids[i:i + 50]
        res = get_item_base_info(batch)
        for it in res.get("response", {}).get("item_list", []):
            item_sku = (it.get("item_sku") or "").strip().lower()
            if item_sku == sku_alvo:
                matched.append(it["item_id"])
    return matched


def get_items_with_details(item_ids):
    """
    Busca base_info + extra_info e mescla em um unico dict por produto.
    Campos mesclados: sale, views, likes, rating_star, comment_count.
    """
    all_items = []
    for i in range(0, len(item_ids), 50):
        batch = item_ids[i:i + 50]
        base_list = get_item_base_info(batch).get("response", {}).get("item_list", [])
        extra_list = get_item_extra_info(batch).get("response", {}).get("item_list", [])
        extra_map = {e["item_id"]: e for e in extra_list}
        for item in base_list:
            extra = extra_map.get(item.get("item_id"), {})
            item["sale"] = extra.get("sale", 0)
            item["views"] = extra.get("views", 0)
            item["likes"] = extra.get("likes", 0)
            item["rating_star"] = extra.get("rating_star", 0)
            item["comment_count"] = extra.get("comment_count", 0)
            all_items.append(item)
    return all_items


# ── Precos ────────────────────────────────────────────────────────────────────

def update_item_price(item_id, price):
    return _call("POST", "/api/v2/product/update_price", {
        "item_id": item_id,
        "price_list": [{"model_id": 0, "original_price": price}],
    })


# ── Estoque ───────────────────────────────────────────────────────────────────

def update_stock(item_id, stock):
    return _call("POST", "/api/v2/product/update_stock", {
        "item_id": item_id,
        "stock_list": [{"model_id": 0, "normal_stock": stock}],
    })


# ── Pedidos ───────────────────────────────────────────────────────────────────

def get_order_list(time_from, time_to, page_size=20, cursor=""):
    return _call("GET", "/api/v2/order/get_order_list", {
        "time_range_field": "create_time",
        "time_from": time_from,
        "time_to": time_to,
        "page_size": page_size,
        "cursor": cursor,
        "order_status": "READY_TO_SHIP",
    })


def get_order_detail(order_sn_list):
    return _call("GET", "/api/v2/order/get_order_detail", {
        "order_sn_list": ",".join(order_sn_list),
        "response_optional_fields": "item_list,package_list,buyer_info",
    })

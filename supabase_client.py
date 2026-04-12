from supabase import create_client
import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
import time

BR          = ZoneInfo("America/Sao_Paulo")
SUPABASE_URL = "https://ykftaprbjaupdvbglkmt.supabase.co"
PAGE_SIZE    = 1000   # máximo por chamada Supabase


def _get_key():
    try:
        return st.secrets["supabase"]["anon_key"]
    except Exception:
        return st.session_state.get("supabase_key", "")


@st.cache_resource
def _client():
    key = _get_key()
    if not key:
        return None
    return create_client(SUPABASE_URL, key)


def _fetch_all(table, filters=None, order_col=None, order_desc=False):
    """
    Pagina automaticamente o Supabase e retorna TODOS os registros,
    contornando o limite padrão de 1000 linhas.
    """
    sb = _client()
    if sb is None:
        return []

    all_data = []
    offset   = 0

    while True:
        q = sb.table(table).select("*")
        if filters:
            for col, op, val in filters:
                if op == "eq":
                    q = q.eq(col, val)
                elif op == "gte":
                    q = q.gte(col, val)
                elif op == "in":
                    q = q.in_(col, val)
        if order_col:
            q = q.order(order_col, desc=order_desc)
        q = q.range(offset, offset + PAGE_SIZE - 1)
        res = q.execute()
        batch = res.data or []
        all_data.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    return all_data


# ── Produtos ──────────────────────────────────────────────────────────────────

def salvar_produtos(df: pd.DataFrame):
    sb = _client()
    if sb is None:
        return {"error": "Supabase não configurado"}
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "item_id":       int(r["ID"]),
            "item_name":     r["Nome"],
            "item_sku":      r["SKU"],
            "item_status":   r["Status"],
            "est_vendedor":  int(r["Est. Vendedor"]),
            "est_full":      int(r["Est. Full"]),
            "preco":         float(r["Preco (R$)"]),
            "vendas":        int(r["Vendas"]),
            "views":         int(r["Views"]),
            "conversao":     float(r["Conversao (%)"]),
            "curtidas":      int(r["Curtidas"]),
            "avaliacao":     float(r["Avaliacao"]),
            "comentarios":   int(r["Comentarios"]),
            "atualizado_em": datetime.now(BR).isoformat(),
        })
    for i in range(0, len(rows), 500):
        sb.table("produtos").upsert(rows[i:i+500]).execute()
    return {"ok": True, "total": len(rows)}


def carregar_produtos_db() -> pd.DataFrame:
    data = _fetch_all("produtos", order_col="item_name")
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data).rename(columns={
        "item_id":     "ID",
        "item_name":   "Nome",
        "item_sku":    "SKU",
        "item_status": "Status",
        "est_vendedor":"Est. Vendedor",
        "est_full":    "Est. Full",
        "preco":       "Preco (R$)",
        "vendas":      "Vendas",
        "views":       "Views",
        "conversao":   "Conversao (%)",
        "curtidas":    "Curtidas",
        "avaliacao":   "Avaliacao",
        "comentarios": "Comentarios",
        "atualizado_em":"Atualizado em",
    })
    return df


def ultima_atualizacao_produtos() -> str:
    sb = _client()
    if sb is None:
        return ""
    res = sb.table("produtos").select("atualizado_em").order("atualizado_em", desc=True).limit(1).execute()
    return res.data[0]["atualizado_em"] if res.data else ""


# ── Pedidos ───────────────────────────────────────────────────────────────────

def salvar_pedidos(orders: list):
    sb = _client()
    if sb is None:
        return {"error": "Supabase não configurado"}
    rows = []
    for o in orders:
        addr = o.get("recipient_address") or {}
        # Calcula faturamento real somando itens (total_amount vem zerado da API)
        fat_real = 0.0
        for it in (o.get("item_list") or []):
            preco = float(it.get("model_discounted_price") or it.get("model_original_price") or 0)
            qtd   = int(it.get("model_quantity_purchased") or 1)
            fat_real += preco * qtd
        rows.append({
            "order_sn":        o.get("order_sn"),
            "order_status":    o.get("order_status"),
            "total_amount":    round(fat_real, 2),
            "buyer_username":  o.get("buyer_username", ""),
            "buyer_name":      (o.get("buyer_info") or {}).get("name", ""),
            "recipient_address": f"{addr.get('full_address','')} - {addr.get('city','')} / {addr.get('state','')}",
            "create_time":     o.get("create_time"),
            "update_time":     o.get("update_time"),
            "ship_by_date":    o.get("ship_by_date"),
            "tracking_no":     ((o.get("package_list") or [{}])[0]).get("tracking_no", ""),
            "payment_method":  o.get("payment_method", ""),
            "note":            o.get("note", ""),
            "itens":           o.get("item_list", []),
            "raw":             o,
            "atualizado_em":   datetime.now(BR).isoformat(),
        })
    for i in range(0, len(rows), 500):
        sb.table("pedidos").upsert(rows[i:i+500]).execute()
    return {"ok": True, "total": len(rows)}


def carregar_pedidos_db(status=None, days=30, time_from=None) -> pd.DataFrame:
    """
    Carrega pedidos do Supabase paginando tudo.
    Aceita time_from (unix timestamp) ou days para calcular automaticamente.
    """
    if time_from is None:
        time_from = int(time.time()) - days * 86400

    filters = [("create_time", "gte", time_from)]
    if status and status != "TODOS":
        filters.append(("order_status", "eq", status))

    data = _fetch_all("pedidos", filters=filters, order_col="create_time", order_desc=True)
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data)


def ultima_atualizacao_pedidos() -> str:
    sb = _client()
    if sb is None:
        return ""
    res = sb.table("pedidos").select("atualizado_em").order("atualizado_em", desc=True).limit(1).execute()
    return res.data[0]["atualizado_em"] if res.data else ""
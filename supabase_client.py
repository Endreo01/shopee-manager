from supabase import create_client
import streamlit as st
import pandas as pd
from datetime import datetime

SUPABASE_URL = "https://ykftaprbjaupdvbglkmt.supabase.co"

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


# ── Produtos ──────────────────────────────────────────────────────────────────

def salvar_produtos(df: pd.DataFrame):
    """Upsert de todos os produtos no Supabase."""
    sb = _client()
    if sb is None:
        return {"error": "Supabase não configurado"}
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "item_id":      int(r["ID"]),
            "item_name":    r["Nome"],
            "item_sku":     r["SKU"],
            "item_status":  r["Status"],
            "est_vendedor": int(r["Est. Vendedor"]),
            "est_full":     int(r["Est. Full"]),
            "preco":        float(r["Preco (R$)"]),
            "vendas":       int(r["Vendas"]),
            "views":        int(r["Views"]),
            "conversao":    float(r["Conversao (%)"]),
            "curtidas":     int(r["Curtidas"]),
            "avaliacao":    float(r["Avaliacao"]),
            "comentarios":  int(r["Comentarios"]),
            "atualizado_em": datetime.utcnow().isoformat(),
        })
    # Upsert em lotes de 500
    for i in range(0, len(rows), 500):
        sb.table("produtos").upsert(rows[i:i+500]).execute()
    return {"ok": True, "total": len(rows)}


def carregar_produtos_db() -> pd.DataFrame:
    """Carrega todos os produtos salvos no Supabase."""
    sb = _client()
    if sb is None:
        return pd.DataFrame()
    res = sb.table("produtos").select("*").execute()
    if not res.data:
        return pd.DataFrame()
    df = pd.DataFrame(res.data)
    df = df.rename(columns={
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
    """Retorna a data/hora da última sincronização."""
    sb = _client()
    if sb is None:
        return ""
    res = sb.table("produtos").select("atualizado_em").order("atualizado_em", desc=True).limit(1).execute()
    if res.data:
        return res.data[0]["atualizado_em"]
    return ""


# ── Pedidos ───────────────────────────────────────────────────────────────────

def salvar_pedidos(orders: list):
    """Upsert de pedidos no Supabase."""
    sb = _client()
    if sb is None:
        return {"error": "Supabase não configurado"}
    rows = []
    for o in orders:
        addr = o.get("recipient_address", {})
        rows.append({
            "order_sn":       o.get("order_sn"),
            "order_status":   o.get("order_status"),
            "total_amount":   float(o.get("total_amount", 0)),
            "buyer_username": o.get("buyer_username", ""),
            "buyer_name":     (o.get("buyer_info") or {}).get("name", ""),
            "recipient_address": f"{addr.get('full_address','')} - {addr.get('city','')} / {addr.get('state','')}",
            "create_time":    o.get("create_time"),
            "update_time":    o.get("update_time"),
            "ship_by_date":   o.get("ship_by_date"),
            "tracking_no":    (o.get("package_list") or [{}])[0].get("tracking_no", ""),
            "payment_method": o.get("payment_method", ""),
            "note":           o.get("note", ""),
            "itens":          o.get("item_list", []),
            "raw":            o,
            "atualizado_em":  datetime.utcnow().isoformat(),
        })
    for i in range(0, len(rows), 500):
        sb.table("pedidos").upsert(rows[i:i+500]).execute()
    return {"ok": True, "total": len(rows)}


def carregar_pedidos_db(status=None, days=30) -> pd.DataFrame:
    """Carrega pedidos do Supabase com filtro opcional de status."""
    sb = _client()
    if sb is None:
        return pd.DataFrame()
    import time
    time_from = int(time.time()) - days * 86400
    q = sb.table("pedidos").select("*").gte("create_time", time_from)
    if status and status != "TODOS":
        q = q.eq("order_status", status)
    res = q.order("create_time", desc=True).execute()
    if not res.data:
        return pd.DataFrame()
    return pd.DataFrame(res.data)


def ultima_atualizacao_pedidos() -> str:
    sb = _client()
    if sb is None:
        return ""
    res = sb.table("pedidos").select("atualizado_em").order("atualizado_em", desc=True).limit(1).execute()
    if res.data:
        return res.data[0]["atualizado_em"]
    return ""
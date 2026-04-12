import streamlit as st
import shopee_client as sc
import supabase_client as sdb
import pandas as pd
import time
from datetime import datetime
from zoneinfo import ZoneInfo

BR = ZoneInfo("America/Sao_Paulo")
STATUS_TODOS = ["READY_TO_SHIP","PROCESSED","SHIPPED","COMPLETED","CANCELLED","IN_CANCEL"]


def _ts(ts):
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(int(ts), tz=BR).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return ""


def _fat_pedido(order):
    """Soma model_discounted_price * qtd de cada item — valor real da venda."""
    total = 0.0
    for item in (order.get("item_list") or []):
        preco = float(item.get("model_discounted_price") or item.get("model_original_price") or 0)
        qtd   = int(item.get("model_quantity_purchased") or 1)
        total += preco * qtd
    return round(total, 2)


def _build_df(orders):
    rows = []
    for o in orders:
        addr  = o.get("recipient_address") or {}
        pkgs  = o.get("package_list") or [{}]
        itens = o.get("item_list") or []
        rows.append({
            "Order SN":      o.get("order_sn", ""),
            "Status":        o.get("order_status", ""),
            "Faturamento":   _fat_pedido(o),
            "Comprador":     o.get("buyer_username", ""),
            "Destinatário":  addr.get("name", ""),
            "Cidade":        addr.get("city", ""),
            "Estado":        addr.get("state", ""),
            "Endereço":      addr.get("full_address", ""),
            "Rastreio":      pkgs[0].get("tracking_no", "") if pkgs else "",
            "Pagamento":     (o.get("payment_info") or [{}])[0].get("payment_method", ""),
            "Nota":          o.get("note", ""),
            "Qtd Itens":     len(itens),
            "Criado em":     _ts(o.get("create_time")),
            "Atualizado em": _ts(o.get("update_time")),
            "Enviar até":    _ts(o.get("ship_by_date")),
        })
    return pd.DataFrame(rows)


def _hoje_inicio_br():
    agora = datetime.now(BR)
    return int(agora.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())


def _sincronizar_todos(time_from, time_to):
    all_sns = []
    for status in STATUS_TODOS:
        sns = sc.get_all_orders(time_from, time_to, status=status)
        all_sns.extend(sns)
    all_sns = list(dict.fromkeys(all_sns))
    if not all_sns:
        return [], []

    all_orders = []
    prog = st.progress(0, text=f"Carregando detalhes de {len(all_sns)} pedidos...")
    for i in range(0, len(all_sns), 50):
        batch  = all_sns[i:i+50]
        detail = sc.get_order_detail(batch)
        all_orders.extend(detail.get("response", {}).get("order_list", []))
        prog.progress(min((i+50)/len(all_sns), 1.0),
                      text=f"Detalhes: {min(i+50,len(all_sns))} de {len(all_sns)}...")
    prog.empty()
    return all_sns, all_orders


def render():
    st.markdown('<p class="section-title">🛍️ Pedidos</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Consulte e gerencie os pedidos da sua loja</p>', unsafe_allow_html=True)

    # ── Controles em linha ────────────────────────────────────────────────────
    col1, col2, col3 = st.columns([1, 1.3, 1.3])
    with col1:
        opcoes = {"Hoje": 0, "7 dias": 7, "15 dias": 15, "30 dias": 30, "60 dias": 60}
        periodo_sel = st.selectbox("Período", list(opcoes.keys()))
        dias        = opcoes[periodo_sel]
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        btn_db = st.button("⚡ Carregar do Banco", use_container_width=True)
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        btn_api = st.button("🔄 Sincronizar com API", use_container_width=True)

    ultima = sdb.ultima_atualizacao_pedidos()
    if ultima:
        try:
            dt = datetime.fromisoformat(ultima.replace("Z", "+00:00")).astimezone(BR)
            st.caption(f"🕐 Banco atualizado em: {dt.strftime('%d/%m/%Y %H:%M')} (Brasília)")
        except Exception:
            pass

    now       = int(time.time())
    time_from = _hoje_inicio_br() if dias == 0 else now - dias * 86400

    # ── Carregar do banco ─────────────────────────────────────────────────────
    if btn_db:
        with st.spinner("Carregando do banco..."):
            df_raw = sdb.carregar_pedidos_db(time_from=time_from)
        if df_raw.empty:
            st.warning("Banco vazio para esse período. Use **Sincronizar com API**.")
            st.stop()
        orders = [r for r in df_raw["raw"].tolist() if r]
        df     = _build_df(orders)
        st.session_state["pedidos_df"]  = df
        st.session_state["pedidos_raw"] = orders
        st.success(f"✅ {len(df):,} pedido(s) carregado(s) do banco!")

    # ── Sincronizar com API ───────────────────────────────────────────────────
    if btn_api:
        with st.spinner("Buscando todos os status na Shopee..."):
            sns, all_orders = _sincronizar_todos(time_from, now)
        if not all_orders:
            st.info("Nenhum pedido encontrado para o período.")
            st.stop()
        with st.spinner("Salvando no banco..."):
            sdb.salvar_pedidos(all_orders)
        df = _build_df(all_orders)
        st.session_state["pedidos_df"]  = df
        st.session_state["pedidos_raw"] = all_orders
        st.success(f"✅ {len(df):,} pedido(s) sincronizados!")

    if st.session_state.get("pedidos_df") is None:
        st.info("👆 Clique em **Carregar do Banco** ou **Sincronizar com API**.")
        st.stop()

    df     = st.session_state["pedidos_df"]
    orders = st.session_state.get("pedidos_raw", [])

    # ── Filtros locais ────────────────────────────────────────────────────────
    st.divider()
    col_f1, col_f2, col_f3 = st.columns([1.5, 1.5, 2])
    with col_f1:
        status_filtro = st.multiselect("Status", ["TODOS"] + STATUS_TODOS, default=["TODOS"])
    with col_f2:
        busca_sn = st.text_input("Order SN", placeholder="2504XXX ; 2504YYY")
    with col_f3:
        busca_comprador = st.text_input("Comprador", placeholder="Nome ou username")

    df_fil = df.copy()
    if status_filtro and "TODOS" not in status_filtro:
        df_fil = df_fil[df_fil["Status"].isin(status_filtro)]
    if busca_sn.strip():
        termos = [t.strip() for t in busca_sn.split(";") if t.strip()]
        mask   = pd.Series([False]*len(df_fil), index=df_fil.index)
        for t in termos:
            mask |= df_fil["Order SN"].str.contains(t, case=False, na=False)
        df_fil = df_fil[mask]
    if busca_comprador.strip():
        df_fil = df_fil[df_fil["Comprador"].str.contains(busca_comprador.strip(), case=False, na=False)]

    # ── Métricas ──────────────────────────────────────────────────────────────
    fat   = df_fil["Faturamento"].sum()
    ticket = df_fil["Faturamento"].mean() if len(df_fil) > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Pedidos", f"{len(df_fil):,}")
    c2.metric("Faturamento",   f"R$ {fat:,.2f}")
    c3.metric("Ticket Médio",  f"R$ {ticket:,.2f}")
    c4.metric("Itens Totais",  f"{df_fil['Qtd Itens'].sum():,}")

    st.divider()

    # ── Tabela ────────────────────────────────────────────────────────────────
    if df_fil.empty:
        st.info("Nenhum pedido encontrado com esse filtro.")
    else:
        st.dataframe(
            df_fil,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Faturamento": st.column_config.NumberColumn(format="R$ %.2f"),
                "Qtd Itens":   st.column_config.NumberColumn(),
            },
        )
        csv = df_fil.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Exportar CSV", data=csv,
                           file_name="pedidos_shopee.csv", mime="text/csv")

    # ── JSON ──────────────────────────────────────────────────────────────────
    if orders:
        with st.expander("📄 Ver JSON completo"):
            sns_fil = set(df_fil["Order SN"].tolist())
            st.json([o for o in orders if o.get("order_sn") in sns_fil])
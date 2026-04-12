import streamlit as st
import shopee_client as sc
import supabase_client as sdb
import pandas as pd
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BR = ZoneInfo("America/Sao_Paulo")

STATUS_OPCOES = [
    "READY_TO_SHIP",
    "PROCESSED",
    "SHIPPED",
    "COMPLETED",
    "CANCELLED",
    "IN_CANCEL",
]

def _ts(ts):
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(int(ts), tz=BR).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return ""

def _parse_valor(v):
    """Converte valor da API — pode vir como centavos int ou float real."""
    try:
        v = float(v)
        # Shopee BR retorna em centavos quando > 10000 e o pedido médio < R$1000
        # Heurística: se valor > 50000, provavelmente está em centavos
        if v > 50000:
            return v / 100
        return v
    except Exception:
        return 0.0

def _build_df(orders):
    rows = []
    for o in orders:
        addr  = o.get("recipient_address") or {}
        pkgs  = o.get("package_list") or [{}]
        itens = o.get("item_list") or []
        valor = _parse_valor(o.get("total_amount", 0))
        rows.append({
            "Order SN":       o.get("order_sn", ""),
            "Status":         o.get("order_status", ""),
            "Total (R$)":     valor,
            "Comprador":      o.get("buyer_username", ""),
            "Destinatário":   addr.get("name", ""),
            "Cidade":         addr.get("city", ""),
            "Estado":         addr.get("state", ""),
            "Endereço":       addr.get("full_address", ""),
            "Rastreio":       pkgs[0].get("tracking_no", "") if pkgs else "",
            "Pagamento":      o.get("payment_method", ""),
            "Nota":           o.get("note", ""),
            "Qtd Itens":      len(itens),
            "Criado em":      _ts(o.get("create_time")),
            "Atualizado em":  _ts(o.get("update_time")),
            "Enviar até":     _ts(o.get("ship_by_date")),
        })
    return pd.DataFrame(rows)


def _sincronizar_status(status_list, time_from, time_to):
    """Busca múltiplos status em paralelo e une os resultados."""
    all_orders = []
    all_sns    = []

    for status in status_list:
        sns = sc.get_all_orders(time_from, time_to, status=status)
        all_sns.extend(sns)

    if not all_sns:
        return [], []

    # Deduplicar
    all_sns = list(dict.fromkeys(all_sns))

    prog = st.progress(0, text="Carregando detalhes dos pedidos...")
    for i in range(0, len(all_sns), 50):
        batch  = all_sns[i:i+50]
        detail = sc.get_order_detail(batch)
        all_orders.extend(detail.get("response", {}).get("order_list", []))
        prog.progress(min((i+50) / len(all_sns), 1.0),
                      text=f"Detalhes: {min(i+50, len(all_sns))} de {len(all_sns)}...")
    prog.empty()
    return all_sns, all_orders


def render():
    st.markdown('<p class="section-title">🛍️ Pedidos</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Consulte e gerencie os pedidos da sua loja</p>', unsafe_allow_html=True)

    # ── Controles ─────────────────────────────────────────────────────────────
    col1, col2 = st.columns([1, 2])
    with col1:
        dias = st.selectbox("Período", [1, 7, 15, 30, 60],
                            format_func=lambda x: f"Hoje" if x == 1 else f"Últimos {x} dias")
    with col2:
        status_sel = st.multiselect(
            "Status",
            STATUS_OPCOES,
            default=["READY_TO_SHIP"],
            help="Selecione um ou mais status para buscar"
        )

    busca_sn = st.text_input("🔍 Buscar Order SN", placeholder="Ex: 2504XXXXXXXX  (separe com ;)")

    col_db, col_api, _ = st.columns([1.5, 1.5, 3])
    with col_db:
        btn_db = st.button("⚡ Carregar do Banco", use_container_width=True)
    with col_api:
        btn_api = st.button("🔄 Sincronizar com API", use_container_width=True)

    ultima = sdb.ultima_atualizacao_pedidos()
    if ultima:
        try:
            dt = datetime.fromisoformat(ultima.replace("Z", "+00:00")).astimezone(BR)
            st.caption(f"🕐 Banco atualizado em: {dt.strftime('%d/%m/%Y %H:%M')} (horário de Brasília)")
        except Exception:
            st.caption(f"🕐 Banco atualizado em: {ultima[:19]}")

    if not status_sel:
        st.warning("Selecione ao menos um status.")
        st.stop()

    # ── Carregar do banco ─────────────────────────────────────────────────────
    if btn_db:
        with st.spinner("Carregando pedidos do banco..."):
            df_raw = sdb.carregar_pedidos_db(status=None, days=dias)
        if df_raw.empty:
            st.warning("Banco vazio para esse filtro. Use **Sincronizar com API**.")
            st.stop()
        # Filtra status selecionados
        df_raw = df_raw[df_raw["order_status"].isin(status_sel)]
        orders = [r for r in df_raw["raw"].tolist() if r]
        df = _build_df(orders)
        st.session_state["pedidos_df"]  = df
        st.session_state["pedidos_raw"] = orders
        st.success(f"✅ {len(df):,} pedido(s) carregado(s) do banco!")

    # ── Sincronizar com API ───────────────────────────────────────────────────
    if btn_api:
        now       = int(time.time())
        time_from = now - dias * 86400

        with st.spinner(f"Buscando pedidos ({', '.join(status_sel)})..."):
            sns, all_orders = _sincronizar_status(status_sel, time_from, now)

        if not all_orders:
            st.info("Nenhum pedido encontrado.")
            st.stop()

        with st.spinner("Salvando no banco..."):
            sdb.salvar_pedidos(all_orders)

        df = _build_df(all_orders)
        st.session_state["pedidos_df"]  = df
        st.session_state["pedidos_raw"] = all_orders
        st.success(f"✅ {len(df):,} pedido(s) encontrados e salvos!")

    if st.session_state.get("pedidos_df") is None:
        st.info("👆 Clique em **Carregar do Banco** ou **Sincronizar com API**.")
        st.stop()

    df     = st.session_state["pedidos_df"]
    orders = st.session_state.get("pedidos_raw", [])

    # ── Filtro local por Order SN ─────────────────────────────────────────────
    if busca_sn.strip():
        termos = [t.strip() for t in busca_sn.split(";") if t.strip()]
        mask   = pd.Series([False] * len(df), index=df.index)
        for t in termos:
            mask |= df["Order SN"].str.contains(t, case=False, na=False)
        df = df[mask]

    # ── Métricas ──────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    total_fat = df["Total (R$)"].sum()
    ticket    = df["Total (R$)"].mean() if len(df) > 0 else 0
    c1.metric("Total Pedidos",  f"{len(df):,}")
    c2.metric("Faturamento",    f"R$ {total_fat:,.2f}")
    c3.metric("Ticket Médio",   f"R$ {ticket:,.2f}")
    c4.metric("Itens Totais",   f"{df['Qtd Itens'].sum():,}")

    st.divider()

    # ── Tabela ────────────────────────────────────────────────────────────────
    if df.empty:
        st.info("Nenhum pedido encontrado.")
    else:
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Total (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Qtd Itens":  st.column_config.NumberColumn(),
            },
        )
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Exportar CSV", data=csv,
                           file_name="pedidos_shopee.csv", mime="text/csv")

    # ── JSON completo ─────────────────────────────────────────────────────────
    if orders:
        with st.expander("📄 Ver JSON completo"):
            if busca_sn.strip():
                sns_filtrados = set(df["Order SN"].tolist())
                st.json([o for o in orders if o.get("order_sn") in sns_filtrados])
            else:
                st.json(orders)
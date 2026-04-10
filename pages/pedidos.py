import streamlit as st
import shopee_client as sc
import supabase_client as sdb
import pandas as pd
import time
import json
from datetime import datetime, timedelta


def _ts(ts):
    if not ts:
        return ""
    return datetime.fromtimestamp(int(ts)).strftime("%d/%m/%Y %H:%M")


def _build_df(orders):
    rows = []
    for o in orders:
        addr  = o.get("recipient_address") or {}
        buyer = o.get("buyer_info") or {}
        pkgs  = o.get("package_list") or [{}]
        itens = o.get("item_list") or []
        rows.append({
            "Order SN":        o.get("order_sn", ""),
            "Status":          o.get("order_status", ""),
            "Total (R$)":      float(o.get("total_amount", 0)),
            "Comprador":       o.get("buyer_username", ""),
            "Nome Destinat.":  addr.get("name", ""),
            "Cidade":          addr.get("city", ""),
            "Estado":          addr.get("state", ""),
            "Endereço":        addr.get("full_address", ""),
            "Rastreio":        pkgs[0].get("tracking_no", "") if pkgs else "",
            "Pagamento":       o.get("payment_method", ""),
            "Nota":            o.get("note", ""),
            "Qtd Itens":       len(itens),
            "Criado em":       _ts(o.get("create_time")),
            "Atualizado em":   _ts(o.get("update_time")),
            "Enviar até":      _ts(o.get("ship_by_date")),
        })
    return pd.DataFrame(rows)


def render():
    st.markdown('<p class="section-title">🛍️ Pedidos</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Consulte e gerencie os pedidos da sua loja</p>', unsafe_allow_html=True)

    # ── Controles ─────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        dias = st.selectbox("Período", [7, 15, 30, 60], format_func=lambda x: f"Últimos {x} dias")
    with col2:
        status = st.selectbox("Status", [
            "TODOS", "READY_TO_SHIP", "PROCESSED", "SHIPPED",
            "COMPLETED", "CANCELLED", "IN_CANCEL"
        ])
    with col3:
        busca_sn = st.text_input("Buscar Order SN", placeholder="Ex: 2504XXXXXXXX")

    col_db, col_api, _ = st.columns([1.5, 1.5, 3])
    with col_db:
        btn_db = st.button("⚡ Carregar do Banco", use_container_width=True,
                           help="Lê pedidos já salvos no Supabase")
    with col_api:
        btn_api = st.button("🔄 Sincronizar com API", use_container_width=True,
                            help="Busca pedidos na Shopee e salva no banco")

    ultima = sdb.ultima_atualizacao_pedidos()
    if ultima:
        st.caption(f"🕐 Banco atualizado em: {ultima[:19].replace('T', ' ')}")

    # ── Carregar do banco ─────────────────────────────────────────────────────
    if btn_db:
        with st.spinner("Carregando pedidos do banco..."):
            df_raw = sdb.carregar_pedidos_db(
                status=status if status != "TODOS" else None,
                days=dias
            )
        if df_raw.empty:
            st.warning("Banco vazio para esse filtro. Tente **Sincronizar com API**.")
            st.stop()
        # Reconstrói o df completo a partir do campo raw
        orders = [r for r in df_raw["raw"].tolist() if r]
        df = _build_df(orders)
        st.session_state["pedidos_df"]     = df
        st.session_state["pedidos_raw"]    = orders
        st.success(f"✅ {len(df):,} pedido(s) carregado(s) do banco!")

    # ── Sincronizar com API ───────────────────────────────────────────────────
    if btn_api:
        now       = int(time.time())
        time_from = now - dias * 86400
        status_api = status if status != "TODOS" else "READY_TO_SHIP"

        with st.spinner("Buscando pedidos na API Shopee..."):
            all_sns = sc.get_all_orders(time_from, now, status=status_api)

        if not all_sns:
            st.info("Nenhum pedido encontrado para o período e status selecionados.")
            st.stop()

        all_orders = []
        prog = st.progress(0, text="Carregando detalhes...")
        for i in range(0, len(all_sns), 50):
            batch  = all_sns[i:i+50]
            detail = sc.get_order_detail(batch)
            all_orders.extend(detail.get("response", {}).get("order_list", []))
            prog.progress(min((i+50) / len(all_sns), 1.0))
        prog.empty()

        with st.spinner("Salvando no banco..."):
            sdb.salvar_pedidos(all_orders)

        df = _build_df(all_orders)
        st.session_state["pedidos_df"]  = df
        st.session_state["pedidos_raw"] = all_orders
        st.success(f"✅ {len(df):,} pedido(s) sincronizados e salvos!")

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
    c1.metric("Total Pedidos",  f"{len(df):,}")
    c2.metric("Faturamento",    f"R$ {df['Total (R$)'].sum():,.2f}")
    c3.metric("Ticket Médio",   f"R$ {df['Total (R$)'].mean():,.2f}" if len(df) > 0 else "R$ 0,00")
    c4.metric("Itens Totais",   f"{df['Qtd Itens'].sum():,}")

    st.divider()

    # ── Tabela completa ───────────────────────────────────────────────────────
    if df.empty:
        st.info("Nenhum pedido encontrado com esse filtro.")
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
        with st.expander("📄 Ver JSON completo dos pedidos"):
            if busca_sn.strip():
                sns_filtrados = set(df["Order SN"].tolist())
                orders_filtrados = [o for o in orders if o.get("order_sn") in sns_filtrados]
                st.json(orders_filtrados)
            else:
                st.json(orders)
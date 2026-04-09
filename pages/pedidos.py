import streamlit as st
import shopee_client as sc
import time
from datetime import datetime, timedelta
import pandas as pd


def render():
    st.markdown('<p class="section-title">🛍️ Pedidos</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Consulte os pedidos da sua loja Shopee</p>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        dias = st.selectbox("Período", [7, 15, 30], index=0, format_func=lambda x: f"Últimos {x} dias")
    with col2:
        status = st.selectbox("Status", [
            "READY_TO_SHIP", "PROCESSED", "SHIPPED", "COMPLETED", "CANCELLED", "IN_CANCEL"
        ], index=0)

    if st.button("🔍 Buscar Pedidos", type="primary"):
        now       = int(time.time())
        time_from = int((datetime.now() - timedelta(days=dias)).timestamp())

        with st.spinner("Buscando pedidos..."):
            # Pagina automaticamente para pegar todos os pedidos do período
            all_sns = sc.get_all_orders(time_from=time_from, time_to=now, status=status)

        if not all_sns:
            st.info("Nenhum pedido encontrado para o período e status selecionados.")
            return

        st.success(f"✅ {len(all_sns)} pedido(s) encontrado(s) — carregando detalhes...")

        all_orders = []
        prog = st.progress(0, text="Carregando detalhes...")
        for i in range(0, len(all_sns), 50):
            batch  = all_sns[i:i + 50]
            detail = sc.get_order_detail(batch)
            orders = detail.get("response", {}).get("order_list", [])
            all_orders.extend(orders)
            prog.progress(min((i + 50) / max(len(all_sns), 1), 1.0))
        prog.empty()

        if not all_orders:
            st.warning("Pedidos encontrados mas sem detalhes retornados pela API.")
            return

        rows = []
        for o in all_orders:
            rows.append({
                "Order SN":   o.get("order_sn"),
                "Status":     o.get("order_status"),
                "Total (R$)": o.get("total_amount", 0),
                "Criado em":  datetime.fromtimestamp(o.get("create_time", 0)).strftime("%d/%m/%Y %H:%M")
                              if o.get("create_time") else "",
                "Itens":      len(o.get("item_list", [])),
                "Nota":       o.get("note", ""),
            })

        df = pd.DataFrame(rows)

        # Métricas rápidas
        c1, c2, c3 = st.columns(3)
        c1.metric("Total de Pedidos", len(df))
        c2.metric("Valor Total (R$)", f"R$ {df['Total (R$)'].sum():,.2f}")
        c3.metric("Itens Totais", df["Itens"].sum())

        st.divider()
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Total (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Itens":      st.column_config.NumberColumn(),
            },
        )

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Exportar CSV", data=csv,
                           file_name="pedidos_shopee.csv", mime="text/csv")

        with st.expander("📄 Ver JSON completo"):
            st.json(all_orders)

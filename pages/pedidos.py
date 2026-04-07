import streamlit as st
import shopee_client as sc
import time
from datetime import datetime, timedelta


def render():
    st.markdown('<p class="section-title">🛒 Pedidos</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Consulte os pedidos da sua loja Shopee</p>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        dias = st.selectbox("Período", [7, 15, 30], index=0, format_func=lambda x: f"Últimos {x} dias")
    with col2:
        status = st.selectbox("Status", [
            "READY_TO_SHIP", "PROCESSED", "SHIPPED", "COMPLETED", "CANCELLED", "IN_CANCEL"
        ], index=0)

    if st.button("🔍 Buscar Pedidos"):
        now = int(time.time())
        time_from = int((datetime.now() - timedelta(days=dias)).timestamp())

        with st.spinner("Buscando pedidos..."):
            result = sc.get_order_list(time_from=time_from, time_to=now, status=status)

        if result.get("error"):
            st.error(f"❌ Erro: {result['error']}")
            return

        order_list = result.get("response", {}).get("order_list", [])
        if not order_list:
            st.info("Nenhum pedido encontrado para o período e status selecionados.")
            return

        order_sns = [o["order_sn"] for o in order_list]
        st.success(f"✅ {len(order_sns)} pedido(s) encontrado(s)")

        with st.spinner("Carregando detalhes dos pedidos..."):
            # Busca em lotes de 50
            all_orders = []
            for i in range(0, len(order_sns), 50):
                batch = order_sns[i:i+50]
                detail = sc.get_order_detail(batch)
                orders = detail.get("response", {}).get("order_list", [])
                all_orders.extend(orders)

        if not all_orders:
            st.json(result)
            return

        import pandas as pd
        rows = []
        for o in all_orders:
            rows.append({
                "Order SN": o.get("order_sn"),
                "Status": o.get("order_status"),
                "Total (R$)": o.get("total_amount", 0),
                "Criado em": datetime.fromtimestamp(o.get("create_time", 0)).strftime("%d/%m/%Y %H:%M") if o.get("create_time") else "",
                "Itens": len(o.get("item_list", [])),
                "Nota": o.get("note", ""),
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        with st.expander("📄 Ver JSON completo"):
            st.json(all_orders)

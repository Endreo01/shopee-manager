import streamlit as st
import shopee_client as sc
import supabase_client as sdb
import pandas as pd
import time
from datetime import datetime, timedelta


def render():
    st.markdown('<div class="section-title">🏠 Visão Geral — Zanup</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Métricas em tempo real da sua loja Shopee</div>', unsafe_allow_html=True)

    if not st.session_state.get("authenticated"):
        st.warning("⚠️ Conecte a API da Shopee em **⚙️ Configurações** primeiro.")
        return

    col_periodo, col_refresh, _ = st.columns([1.5, 1, 3])
    with col_periodo:
        dias = st.selectbox("Período", [7, 15, 30], format_func=lambda x: f"Últimos {x} dias", label_visibility="collapsed")
    with col_refresh:
        atualizar = st.button("🔄 Atualizar", use_container_width=True)

    cache_key = f"dash_{dias}"

    if atualizar or cache_key not in st.session_state:
        with st.spinner("Carregando métricas..."):
            now       = int(time.time())
            time_from = now - dias * 86400

            # ── Pedidos do banco ──────────────────────────────────────────────
            df_pedidos = sdb.carregar_pedidos_db(status=None, days=dias)

            # Se banco vazio, tenta API
            if df_pedidos.empty:
                all_sns    = sc.get_all_orders(time_from, now, status="READY_TO_SHIP")
                pedidos_pendentes = len(all_sns)
                faturamento = 0.0
                ticket_medio = 0.0
                top_produtos = pd.DataFrame()
            else:
                pedidos_pendentes = len(df_pedidos[df_pedidos["order_status"] == "READY_TO_SHIP"])
                faturamento  = float(df_pedidos["total_amount"].sum())
                ticket_medio = float(df_pedidos["total_amount"].mean()) if len(df_pedidos) > 0 else 0.0

                # Top produtos pelos itens dos pedidos
                all_itens = []
                for itens in df_pedidos["itens"].dropna():
                    if isinstance(itens, list):
                        all_itens.extend(itens)
                if all_itens:
                    df_itens = pd.DataFrame(all_itens)
                    if "item_name" in df_itens.columns and "model_quantity_purchased" in df_itens.columns:
                        top_produtos = (
                            df_itens.groupby("item_name")["model_quantity_purchased"]
                            .sum().reset_index()
                            .rename(columns={"item_name": "Produto", "model_quantity_purchased": "Qtd Vendida"})
                            .sort_values("Qtd Vendida", ascending=False)
                            .head(5)
                        )
                    else:
                        top_produtos = pd.DataFrame()
                else:
                    top_produtos = pd.DataFrame()

            # ── Produtos do banco ─────────────────────────────────────────────
            df_produtos = sdb.carregar_produtos_db()
            if df_produtos.empty:
                res = sc.get_item_list(offset=0, page_size=1, status="NORMAL")
                total_produtos = res.get("response", {}).get("total_count", 0)
                estoque_zerado = 0
            else:
                total_produtos = len(df_produtos[df_produtos["Status"] == "NORMAL"])
                estoque_zerado = len(df_produtos[
                    (df_produtos["Status"] == "NORMAL") &
                    (df_produtos["Est. Vendedor"] == 0)
                ])

        st.session_state[cache_key] = {
            "pedidos_pendentes": pedidos_pendentes,
            "faturamento":       faturamento,
            "ticket_medio":      ticket_medio,
            "total_produtos":    total_produtos,
            "estoque_zerado":    estoque_zerado,
            "top_produtos":      top_produtos,
            "total_pedidos":     len(df_pedidos) if not df_pedidos.empty else 0,
        }

    m = st.session_state[cache_key]

    # ── Cards de métricas ─────────────────────────────────────────────────────
    st.divider()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("📦 Produtos Ativos",    f"{m['total_produtos']:,}")
    c2.metric("🛍️ Pedidos p/ Enviar", f"{m['pedidos_pendentes']:,}")
    c3.metric("💰 Faturamento",        f"R$ {m['faturamento']:,.2f}")
    c4.metric("🎯 Ticket Médio",       f"R$ {m['ticket_medio']:,.2f}")
    c5.metric("⚠️ Estoque Zerado",     f"{m['estoque_zerado']:,}")

    st.divider()

    # ── Top produtos ──────────────────────────────────────────────────────────
    col_top, col_info = st.columns([2, 1])

    with col_top:
        st.markdown("#### 🏆 Top 5 Produtos Mais Vendidos")
        top = m.get("top_produtos")
        if top is not None and not top.empty:
            st.dataframe(top, use_container_width=True, hide_index=True)
        else:
            st.info("Sincronize pedidos para ver os mais vendidos.")

    with col_info:
        st.markdown("#### 📊 Resumo do Período")
        st.markdown(f"""
        | Métrica | Valor |
        |---|---|
        | Total de Pedidos | {m['total_pedidos']:,} |
        | Faturamento | R$ {m['faturamento']:,.2f} |
        | Ticket Médio | R$ {m['ticket_medio']:,.2f} |
        | Produtos Ativos | {m['total_produtos']:,} |
        | Estoque Zerado | {m['estoque_zerado']:,} |
        """)

    st.divider()
    ultima_p = sdb.ultima_atualizacao_produtos()
    ultima_o = sdb.ultima_atualizacao_pedidos()
    col_a, col_b = st.columns(2)
    col_a.caption(f"🛍️ Produtos atualizados: {ultima_p[:19].replace('T',' ') if ultima_p else 'nunca'}")
    col_b.caption(f"📦 Pedidos atualizados: {ultima_o[:19].replace('T',' ') if ultima_o else 'nunca'}")
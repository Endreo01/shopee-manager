import streamlit as st
import shopee_client as sc
import supabase_client as sdb
import pandas as pd
import time
from datetime import datetime
from zoneinfo import ZoneInfo

BR = ZoneInfo("America/Sao_Paulo")

def _fmt_ultima(ultima):
    if not ultima:
        return "nunca"
    try:
        dt = datetime.fromisoformat(ultima.replace("Z", "+00:00")).astimezone(BR)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return ultima[:19]

def _parse_valor(v):
    try:
        v = float(v)
        if v > 50000:
            return v / 100
        return v
    except Exception:
        return 0.0

def render():
    st.markdown('<div class="section-title">🏠 Visão Geral — Zanup</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Métricas em tempo real da sua loja Shopee</div>', unsafe_allow_html=True)

    if not st.session_state.get("authenticated"):
        st.warning("⚠️ Conecte a API da Shopee em **⚙️ Configurações** primeiro.")
        return

    col_periodo, col_refresh, _ = st.columns([1.5, 1, 3])
    with col_periodo:
        dias = st.selectbox("Período", [7, 15, 30],
                            format_func=lambda x: f"Últimos {x} dias",
                            label_visibility="collapsed")
    with col_refresh:
        atualizar = st.button("🔄 Atualizar", use_container_width=True)

    cache_key = f"dash_{dias}"

    if atualizar or cache_key not in st.session_state:
        with st.spinner("Carregando métricas..."):
            now       = int(time.time())
            time_from = now - dias * 86400

            # ── Pedidos do banco ──────────────────────────────────────────────
            df_pedidos = sdb.carregar_pedidos_db(status=None, days=dias)

            if df_pedidos.empty:
                # Fallback API — só READY_TO_SHIP
                all_sns = sc.get_all_orders(time_from, now, status="READY_TO_SHIP")
                pedidos_pendentes = len(all_sns)
                faturamento  = 0.0
                ticket_medio = 0.0
                top_produtos = pd.DataFrame()
                total_pedidos = pedidos_pendentes
            else:
                pedidos_pendentes = len(df_pedidos[df_pedidos["order_status"] == "READY_TO_SHIP"])
                total_pedidos     = len(df_pedidos)

                # Faturamento — corrige centavos
                faturamento = sum(
                    _parse_valor(v) for v in df_pedidos["total_amount"].tolist()
                )
                ticket_medio = faturamento / total_pedidos if total_pedidos > 0 else 0.0

                # Top produtos
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
                            .rename(columns={"item_name": "Produto", "model_quantity_purchased": "Qtd"})
                            .sort_values("Qtd", ascending=False)
                            .head(5)
                        )
                    else:
                        top_produtos = pd.DataFrame()
                else:
                    top_produtos = pd.DataFrame()

            # ── Produtos do banco ─────────────────────────────────────────────
            df_produtos = sdb.carregar_produtos_db()
            if df_produtos.empty:
                # Fallback API — pega total real
                res = sc.get_item_list(offset=0, page_size=1, status="NORMAL")
                total_produtos = res.get("response", {}).get("total_count", 0)
                estoque_zerado = 0
            else:
                total_produtos = len(df_produtos[df_produtos["Status"] == "NORMAL"])
                estoque_zerado = len(df_produtos[
                    (df_produtos["Status"] == "NORMAL") &
                    (df_produtos["Est. Vendedor"].astype(float) == 0)
                ])

        st.session_state[cache_key] = {
            "pedidos_pendentes": pedidos_pendentes,
            "total_pedidos":     total_pedidos,
            "faturamento":       faturamento,
            "ticket_medio":      ticket_medio,
            "total_produtos":    total_produtos,
            "estoque_zerado":    estoque_zerado,
            "top_produtos":      top_produtos,
        }

    m = st.session_state[cache_key]

    # ── Cards ─────────────────────────────────────────────────────────────────
    st.divider()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("📦 Produtos Ativos",    f"{m['total_produtos']:,}")
    c2.metric("🛍️ Pedidos p/ Enviar", f"{m['pedidos_pendentes']:,}")
    c3.metric("💰 Faturamento",        f"R$ {m['faturamento']:,.2f}")
    c4.metric("🎯 Ticket Médio",       f"R$ {m['ticket_medio']:,.2f}")
    c5.metric("⚠️ Estoque Zerado",     f"{m['estoque_zerado']:,}")

    st.divider()

    # ── Top produtos + Resumo ─────────────────────────────────────────────────
    col_top, col_resumo = st.columns([2, 1])

    with col_top:
        st.markdown("#### 🏆 Top 5 Produtos Mais Vendidos")
        top = m.get("top_produtos")
        if top is not None and not top.empty:
            st.dataframe(top, use_container_width=True, hide_index=True)
        else:
            st.info("Sincronize pedidos para ver os mais vendidos.")

    with col_resumo:
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
    col_a.caption(f"🛍️ Produtos: {_fmt_ultima(ultima_p)}")
    col_b.caption(f"📦 Pedidos: {_fmt_ultima(ultima_o)}")
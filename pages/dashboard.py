import streamlit as st
import shopee_client as sc
import pandas as pd
import time
from datetime import datetime, timedelta


# ── Helpers de período ────────────────────────────────────────────────────────

def _periodo_timestamps(opcao, mes_ano=None):
    now = datetime.now()
    if opcao == "Hoje":
        inicio = now.replace(hour=0, minute=0, second=0, microsecond=0)
        fim    = now
    elif opcao == "Últimos 7 dias":
        inicio = now - timedelta(days=7)
        fim    = now
    elif opcao == "Últimos 15 dias":
        inicio = now - timedelta(days=15)
        fim    = now
    elif opcao == "Últimos 30 dias":
        inicio = now - timedelta(days=30)
        fim    = now
    elif opcao == "Por mês" and mes_ano:
        ano, mes = mes_ano
        inicio   = datetime(ano, mes, 1)
        if mes == 12:
            fim = datetime(ano + 1, 1, 1) - timedelta(seconds=1)
        else:
            fim = datetime(ano, mes + 1, 1) - timedelta(seconds=1)
    else:
        inicio = now - timedelta(days=7)
        fim    = now
    return int(inicio.timestamp()), int(fim.timestamp())


def _label_periodo(opcao, mes_ano=None):
    if opcao == "Por mês" and mes_ano:
        meses = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
        return f"{meses[mes_ano[1]-1]}/{mes_ano[0]}"
    return opcao


# ── Coleta de dados ───────────────────────────────────────────────────────────

def _coletar_dados(time_from, time_to):
    dados = {
        "pedidos":          [],
        "faturamento":      0.0,
        "produtos_ativos":  0,
        "estoque_zerado":   0,
        "top_produtos":     [],
        "views_total":      0,
        "conversao_media":  0.0,
        "erros":            [],
    }

    # ── Pedidos ───────────────────────────────────────────────────────────────
    try:
        todos_status = ["READY_TO_SHIP", "PROCESSED", "SHIPPED", "COMPLETED"]
        todos_pedidos = []
        for status in todos_status:
            sns = sc.get_all_orders(time_from, time_to, status=status)
            todos_pedidos.extend([(sn, status) for sn in sns])

        # Detalha em lotes
        all_sns    = [p[0] for p in todos_pedidos]
        status_map = {p[0]: p[1] for p in todos_pedidos}
        detalhes   = []
        for i in range(0, len(all_sns), 50):
            res = sc.get_order_detail(all_sns[i:i+50])
            detalhes.extend(res.get("response", {}).get("order_list", []))

        dados["pedidos"] = detalhes
        dados["faturamento"] = sum(
            float(o.get("total_amount", 0))
            for o in detalhes
            if o.get("order_status") in ["SHIPPED", "COMPLETED"]
        )
    except Exception as e:
        dados["erros"].append(f"Pedidos: {e}")

    # ── Produtos ativos ───────────────────────────────────────────────────────
    try:
        res = sc.get_item_list(offset=0, page_size=1, status="NORMAL")
        dados["produtos_ativos"] = res.get("response", {}).get("total_count", 0)
    except Exception as e:
        dados["erros"].append(f"Produtos: {e}")

    # ── Top produtos + views + estoque zerado ─────────────────────────────────
    try:
        all_ids = sc.get_all_item_ids(status="NORMAL")
        extra_list = []
        base_list  = []

        for i in range(0, min(len(all_ids), 300), 50):
            batch = all_ids[i:i+50]
            r_extra = sc.get_item_extra_info(batch)
            extra_list.extend(r_extra.get("response", {}).get("item_list", []))
            r_base = sc.get_item_base_info(batch)
            base_list.extend(r_base.get("response", {}).get("item_list", []))

        # Estoque zerado
        zerado = 0
        for it in base_list:
            sl = it.get("stock_info_v2", {}).get("seller_stock", [])
            if (sl[0].get("stock", 0) if sl else 0) == 0:
                zerado += 1
        dados["estoque_zerado"] = zerado

        # Top 5 mais vendidos
        extra_sorted = sorted(extra_list, key=lambda x: x.get("sale", 0) or 0, reverse=True)[:5]
        base_map     = {b["item_id"]: b for b in base_list}
        top = []
        for e in extra_sorted:
            iid  = e.get("item_id")
            base = base_map.get(iid, {})
            pi   = base.get("price_info", [{}])
            preco = pi[0].get("current_price", 0) if pi else 0
            top.append({
                "nome":    base.get("item_name", f"ID {iid}")[:45],
                "vendas":  e.get("sale", 0) or 0,
                "views":   e.get("views", 0) or 0,
                "preco":   preco,
                "rating":  e.get("rating_star", 0) or 0,
            })
        dados["top_produtos"] = top

        # Views e conversão geral
        views_total = sum(e.get("views", 0) or 0 for e in extra_list)
        sales_total = sum(e.get("sale", 0) or 0 for e in extra_list)
        dados["views_total"]     = views_total
        dados["conversao_media"] = round(sales_total / views_total * 100, 2) if views_total > 0 else 0.0

    except Exception as e:
        dados["erros"].append(f"Produtos/Extra: {e}")

    return dados


# ── Render ────────────────────────────────────────────────────────────────────

def render():
    st.markdown('<div class="section-title">🏠 Dashboard — Zanup</div>', unsafe_allow_html=True)

    if not st.session_state.get("authenticated"):
        st.warning("⚠️ Conecte a API da Shopee em **⚙️ Configurações** primeiro.")
        return

    # ── Seletor de período ────────────────────────────────────────────────────
    st.markdown("### 📅 Selecione o período")
    col_p, col_mes, col_btn = st.columns([2, 1.5, 1])

    with col_p:
        opcao = st.radio(
            "Período",
            ["Hoje", "Últimos 7 dias", "Últimos 15 dias", "Últimos 30 dias", "Por mês"],
            horizontal=True,
            label_visibility="collapsed",
        )

    mes_ano = None
    with col_mes:
        if opcao == "Por mês":
            now    = datetime.now()
            meses  = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                      "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
            anos   = list(range(now.year - 1, now.year + 1))
            col_m, col_a = st.columns(2)
            with col_m:
                mes = st.selectbox("Mês", range(1, 13), index=now.month - 1,
                                   format_func=lambda x: meses[x-1])
            with col_a:
                ano = st.selectbox("Ano", anos, index=len(anos) - 1)
            mes_ano = (ano, mes)

    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        btn_carregar = st.button("🚀 Carregar Dashboard", type="primary", use_container_width=True)

    # Botão atualizar (só aparece se já carregou)
    if st.session_state.get("dash_dados"):
        col_att, col_info = st.columns([1, 4])
        with col_att:
            btn_atualizar = st.button("🔄 Atualizar", use_container_width=True)
        with col_info:
            ultima = st.session_state.get("dash_ultima_att", "")
            if ultima:
                st.caption(f"Última atualização: {ultima}")
        if btn_atualizar:
            btn_carregar = True

    # ── Carrega dados ─────────────────────────────────────────────────────────
    if btn_carregar:
        time_from, time_to = _periodo_timestamps(opcao, mes_ano)
        label = _label_periodo(opcao, mes_ano)

        with st.spinner(f"Carregando dados — {label}..."):
            dados = _coletar_dados(time_from, time_to)

        st.session_state["dash_dados"]       = dados
        st.session_state["dash_periodo"]     = label
        st.session_state["dash_ultima_att"]  = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    if not st.session_state.get("dash_dados"):
        st.info("👆 Selecione o período e clique em **Carregar Dashboard**.")
        return

    dados  = st.session_state["dash_dados"]
    label  = st.session_state.get("dash_periodo", "")

    if dados["erros"]:
        with st.expander("⚠️ Avisos da API"):
            for e in dados["erros"]:
                st.warning(e)

    st.divider()

    # ── KPIs principais ───────────────────────────────────────────────────────
    st.markdown(f"#### 📊 Resumo — {label}")
    pedidos = dados["pedidos"]

    qtd_pendentes  = sum(1 for o in pedidos if o.get("order_status") == "READY_TO_SHIP")
    qtd_enviados   = sum(1 for o in pedidos if o.get("order_status") in ["SHIPPED", "COMPLETED"])
    qtd_cancelados = sum(1 for o in pedidos if o.get("order_status") == "CANCELLED")
    qtd_total      = len(pedidos)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("💰 Faturamento",       f"R$ {dados['faturamento']:,.2f}",
              help="Pedidos enviados + concluídos no período")
    c2.metric("🛍️ Total de Pedidos",  f"{qtd_total:,}")
    c3.metric("📦 Prontos p/ Enviar", f"{qtd_pendentes:,}")
    c4.metric("✅ Enviados/Concluídos",f"{qtd_enviados:,}")
    c5.metric("❌ Cancelados",         f"{qtd_cancelados:,}")

    st.divider()

    col_left, col_right = st.columns([1.6, 1])

    # ── Top 5 produtos mais vendidos ──────────────────────────────────────────
    with col_left:
        st.markdown("#### 🏆 Top 5 Produtos Mais Vendidos")
        top = dados.get("top_produtos", [])
        if top:
            df_top = pd.DataFrame(top)
            df_top.columns = ["Produto", "Vendas", "Views", "Preço (R$)", "Avaliação"]
            df_top["Conv. (%)"] = df_top.apply(
                lambda r: round(r["Vendas"] / r["Views"] * 100, 1) if r["Views"] > 0 else 0,
                axis=1,
            )
            st.dataframe(
                df_top,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Preço (R$)":  st.column_config.NumberColumn(format="R$ %.2f"),
                    "Avaliação":   st.column_config.NumberColumn(format="%.1f ⭐"),
                    "Conv. (%)":   st.column_config.NumberColumn(format="%.1f%%"),
                    "Vendas":      st.column_config.ProgressColumn(
                                       format="%d",
                                       min_value=0,
                                       max_value=max(p["vendas"] for p in top) or 1,
                                   ),
                },
            )
        else:
            st.info("Sem dados de produtos disponíveis.")

    # ── Métricas de loja + estoque ────────────────────────────────────────────
    with col_right:
        st.markdown("#### 🏪 Saúde da Loja")
        st.metric("📦 Produtos Ativos",   f"{dados['produtos_ativos']:,}")
        st.metric("⚠️ Estoque Zerado",    f"{dados['estoque_zerado']:,}",
                  help="Amostra dos primeiros 300 produtos ativos")
        st.metric("👁️ Views (amostra)",   f"{dados['views_total']:,}")
        st.metric("📈 Conversão Média",   f"{dados['conversao_media']:.2f}%")

        st.divider()
        st.markdown("#### 📣 Fonte de Vendas")
        st.info(
            "Disponível via API de Analytics da Shopee.\n\n"
            "Requer permissão **`analytics`** habilitada no seu app no Open Platform.",
            icon="🔒",
        )

    # ── Pedidos recentes ──────────────────────────────────────────────────────
    st.divider()
    st.markdown("#### 🛒 Pedidos Recentes")
    if pedidos:
        rows = []
        for o in sorted(pedidos, key=lambda x: x.get("create_time", 0), reverse=True)[:20]:
            rows.append({
                "Order SN":   o.get("order_sn", ""),
                "Status":     o.get("order_status", ""),
                "Total (R$)": float(o.get("total_amount", 0)),
                "Itens":      len(o.get("item_list", [])),
                "Criado em":  datetime.fromtimestamp(o.get("create_time", 0)).strftime("%d/%m/%Y %H:%M")
                              if o.get("create_time") else "",
            })
        df_ped = pd.DataFrame(rows)
        st.dataframe(
            df_ped,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Total (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Status": st.column_config.TextColumn(),
            },
        )
        csv = df_ped.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Exportar Pedidos CSV", data=csv,
                           file_name=f"pedidos_{label.replace('/','-')}.csv",
                           mime="text/csv")
    else:
        st.info("Nenhum pedido encontrado no período selecionado.")
import streamlit as st
import shopee_client as sc
import supabase_client as sdb
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BR = ZoneInfo("America/Sao_Paulo")


def _ts(ts):
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(int(ts), tz=BR).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(ts)


def render():
    st.markdown('<p class="section-title">🏷️ Descontos</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Gerencie suas promoções de desconto — Central de Marketing Shopee</p>', unsafe_allow_html=True)

    tab_lista, tab_criar, tab_editar = st.tabs([
        "📋 Minhas Promoções",
        "➕ Criar Promoção",
        "✏️ Adicionar Produtos a Promoção",
    ])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — LISTAR PROMOÇÕES
    # ══════════════════════════════════════════════════════════════════════════
    with tab_lista:
        if st.button("🔍 Carregar Promoções", use_container_width=False):
            with st.spinner("Buscando promoções..."):
                result = sc.get_discount_list()

            if result.get("error"):
                st.error(f"❌ {result['error']}")
                if result.get("details"):
                    st.json(result["details"])
            else:
                discounts = result.get("response", {}).get("discount_list", [])
                if not discounts:
                    st.info("Nenhuma promoção encontrada.")
                    st.json(result)
                else:
                    st.session_state["discounts"] = discounts
                    st.success(f"✅ {len(discounts)} promoção(ões) encontrada(s)")

        if st.session_state.get("discounts"):
            rows = []
            for d in st.session_state["discounts"]:
                rows.append({
                    "ID":          d.get("discount_id"),
                    "Nome":        d.get("discount_name", ""),
                    "Status":      d.get("discount_status", ""),
                    "Início":      _ts(d.get("start_time")),
                    "Fim":         _ts(d.get("end_time")),
                    "Produtos":    d.get("item_count", 0),
                })
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Detalhes de uma promoção
            st.divider()
            st.markdown("#### Ver itens de uma promoção")
            nomes = [f"{r['ID']} — {r['Nome']}" for _, r in df.iterrows()]
            escolha = st.selectbox("Selecione", nomes, key="disc_detail_sel")
            idx = nomes.index(escolha)
            disc_id = st.session_state["discounts"][idx]["discount_id"]

            if st.button("🔍 Ver Produtos da Promoção"):
                with st.spinner("Buscando produtos..."):
                    res = sc.get_discount_items(disc_id)
                if res.get("error"):
                    st.error(f"❌ {res['error']}")
                else:
                    items = res.get("response", {}).get("item_list", [])
                    if items:
                        rows_i = []
                        for it in items:
                            rows_i.append({
                                "Item ID":        it.get("item_id"),
                                "Nome":           it.get("item_name",""),
                                "Preço Promo":    it.get("item_promotion_price", 0),
                                "Preço Original": it.get("item_original_price", 0),
                                "Estoque Promo":  it.get("purchase_limit", 0),
                            })
                        st.dataframe(pd.DataFrame(rows_i), use_container_width=True, hide_index=True,
                                     column_config={
                                         "Preço Promo":    st.column_config.NumberColumn(format="R$ %.2f"),
                                         "Preço Original": st.column_config.NumberColumn(format="R$ %.2f"),
                                     })
                    else:
                        st.info("Nenhum produto nesta promoção.")
                        st.json(res)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — CRIAR PROMOÇÃO
    # ══════════════════════════════════════════════════════════════════════════
    with tab_criar:
        st.markdown("#### Nova Promoção de Desconto")
        st.info("Cria uma promoção do tipo **Minha Promoção** na Central de Marketing da Shopee.")

        nome_promo = st.text_input("Nome da Promoção *", placeholder="Ex: Wanpy Especial Abril")

        col_ini, col_fim = st.columns(2)
        with col_ini:
            data_ini  = st.date_input("Data de início *", value=datetime.now(BR).date())
            hora_ini  = st.time_input("Hora de início *", value=datetime.now(BR).replace(hour=9, minute=0).time())
        with col_fim:
            data_fim  = st.date_input("Data de fim *", value=(datetime.now(BR) + timedelta(days=7)).date())
            hora_fim  = st.time_input("Hora de fim *", value=datetime.now(BR).replace(hour=23, minute=59).time())

        dt_ini = int(datetime.combine(data_ini, hora_ini, tzinfo=BR).timestamp())
        dt_fim = int(datetime.combine(data_fim, hora_fim, tzinfo=BR).timestamp())

        if st.button("✅ Criar Promoção", type="primary"):
            if not nome_promo.strip():
                st.warning("Digite o nome da promoção.")
            elif dt_fim <= dt_ini:
                st.warning("A data de fim deve ser após a data de início.")
            else:
                with st.spinner("Criando promoção..."):
                    res = sc.create_discount(nome_promo.strip(), dt_ini, dt_fim)
                if res.get("error"):
                    st.error(f"❌ {res['error']}")
                    if res.get("details"):
                        st.json(res["details"])
                else:
                    disc_id = res.get("response", {}).get("discount_id")
                    st.success(f"✅ Promoção criada! ID: `{disc_id}`")
                    st.info("Agora vá para a aba **Adicionar Produtos** para incluir produtos nesta promoção.")
                    st.session_state["novo_disc_id"] = disc_id

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — ADICIONAR PRODUTOS A UMA PROMOÇÃO
    # ══════════════════════════════════════════════════════════════════════════
    with tab_editar:
        st.markdown("#### Adicionar Produtos a uma Promoção Existente")

        disc_id_input = st.text_input(
            "ID da Promoção *",
            value=str(st.session_state.get("novo_disc_id", "")),
            placeholder="Cole o ID da promoção"
        )

        st.divider()
        st.markdown("#### Selecionar Produtos")

        # Carregar catálogo
        col_db, col_api, _ = st.columns([1.5, 1.5, 3])
        with col_db:
            btn_db = st.button("⚡ Carregar do Banco", use_container_width=True, key="desc_db")
        with col_api:
            btn_api = st.button("🔄 Buscar da API", use_container_width=True, key="desc_api")

        if btn_db:
            df_cat = sdb.carregar_produtos_db()
            if df_cat.empty:
                st.warning("Banco vazio. Use **Buscar da API**.")
            else:
                df_cat = df_cat[df_cat["Status"] == "NORMAL"]
                st.session_state["desconto_catalogo"] = df_cat
                st.success(f"✅ {len(df_cat):,} produtos carregados!")

        if btn_api:
            all_ids = sc.get_all_item_ids(status="NORMAL")
            rows = []
            for i in range(0, min(len(all_ids), 200), 50):
                res = sc.get_item_base_info(all_ids[i:i+50])
                for it in res.get("response", {}).get("item_list", []):
                    pi = it.get("price_info", [{}])
                    rows.append({
                        "ID":         it.get("item_id"),
                        "Nome":       it.get("item_name",""),
                        "SKU":        it.get("item_sku",""),
                        "Preco (R$)": float(pi[0].get("current_price",0)) if pi else 0,
                        "Status":     it.get("item_status",""),
                    })
            st.session_state["desconto_catalogo"] = pd.DataFrame(rows)
            st.success(f"✅ {len(rows)} produtos carregados!")

        if st.session_state.get("desconto_catalogo") is not None:
            df_cat = st.session_state["desconto_catalogo"]

            col_tipo, col_busca = st.columns([1.2, 3])
            with col_tipo:
                tipo = st.selectbox("Buscar por", ["Nome", "SKU", "ID"], key="desc_tipo")
            with col_busca:
                termo = st.text_input("Termo (use ; para múltiplos)", key="desc_termo")

            df_fil = df_cat.copy()
            if termo.strip():
                termos = [t.strip() for t in termo.split(";") if t.strip()]
                if tipo == "Nome":
                    mask = pd.Series([False]*len(df_fil), index=df_fil.index)
                    for t in termos:
                        mask |= df_fil["Nome"].str.contains(t, case=False, na=False)
                    df_fil = df_fil[mask]
                elif tipo == "SKU":
                    mask = pd.Series([False]*len(df_fil), index=df_fil.index)
                    for t in termos:
                        mask |= df_fil["SKU"].str.contains(t, case=False, na=False)
                    df_fil = df_fil[mask]
                elif tipo == "ID":
                    ids = [int(x) for x in termo.replace(";",",").split(",") if x.strip().isdigit()]
                    df_fil = df_fil[df_fil["ID"].isin(ids)]

            if not df_fil.empty:
                st.caption(f"{len(df_fil)} produto(s) filtrados")
                st.dataframe(df_fil[["ID","Nome","SKU","Preco (R$)"]].head(100),
                             use_container_width=True, hide_index=True,
                             column_config={"Preco (R$)": st.column_config.NumberColumn(format="R$ %.2f")})

                st.divider()
                st.markdown("#### Configurar Desconto")

                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    tipo_desc = st.selectbox("Tipo", ["Percentual (%)", "Valor fixo (R$)"], key="add_tipo")
                with col_b:
                    if tipo_desc == "Percentual (%)":
                        pct = st.number_input("Desconto (%)", 1.0, 99.0, 10.0, 0.5, key="add_pct")
                    else:
                        val = st.number_input("Desconto (R$)", 0.01, value=5.0, step=0.01, key="add_val")
                with col_c:
                    limite = st.number_input("Limite de compra por cliente (0 = sem limite)", 0, value=0, key="add_lim")

                if st.button("🚀 Adicionar à Promoção", type="primary"):
                    if not disc_id_input.strip():
                        st.warning("Informe o ID da promoção.")
                    else:
                        item_list = []
                        for _, row in df_fil.iterrows():
                            preco = float(row["Preco (R$)"])
                            if tipo_desc == "Percentual (%)":
                                preco_promo = round(preco * (1 - pct/100), 2)
                            else:
                                preco_promo = round(max(preco - val, 0.01), 2)
                            item_list.append({
                                "item_id":               int(row["ID"]),
                                "item_promotion_price":  preco_promo,
                                "purchase_limit":        int(limite),
                                "model_list":            [],
                            })

                        with st.spinner(f"Adicionando {len(item_list)} produto(s)..."):
                            res = sc.add_discount_items(int(disc_id_input.strip()), item_list)

                        if res.get("error"):
                            st.error(f"❌ {res['error']}")
                            if res.get("details"):
                                st.json(res["details"])
                        else:
                            st.success(f"✅ {len(item_list)} produto(s) adicionados à promoção!")
                            st.json(res)
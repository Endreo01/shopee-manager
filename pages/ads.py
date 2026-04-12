import streamlit as st
import shopee_client as sc
import pandas as pd
import io
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

BR = ZoneInfo("America/Sao_Paulo")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _gerar_xlsx_sem_ads(df):
    """Gera XLSX dos produtos sem Ads com coluna 'anunciar' para o usuário preencher."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Produtos sem Ads"

    thin   = Side(style="thin", color="CCCCCC")
    brd    = Border(left=thin, right=thin, top=thin, bottom=thin)
    hfill  = PatternFill("solid", start_color="0F3638")
    hfont  = Font(bold=True, color="FFFFFF", name="Arial", size=10)
    halign = Alignment(horizontal="center", vertical="center")
    yfill  = PatternFill("solid", start_color="FFF9C4")  # amarelo suave p/ coluna anunciar

    headers = ["item_id", "nome", "sku", "estoque", "vendas", "preco", "anunciar (sim/nao)"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = hfont; cell.fill = hfill
        cell.alignment = halign; cell.border = brd

    for row_idx, (_, r) in enumerate(df.iterrows(), 2):
        vals = [
            r.get("item_id", ""),
            r.get("item_name", ""),
            r.get("item_sku", ""),
            r.get("stock", 0),
            r.get("sales", 0),
            r.get("price", 0),
            "",  # coluna anunciar — usuário preenche
        ]
        for col_idx, val in enumerate(vals, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.border = brd
            cell.font   = Font(name="Arial", size=10)
            if col_idx == 7:
                cell.fill      = yfill
                cell.alignment = Alignment(horizontal="center")
            if col_idx == 6:
                cell.number_format = 'R$ #,##0.00'

    ws.column_dimensions["A"].width = 16
    ws.column_dimensions["B"].width = 50
    ws.column_dimensions["C"].width = 14
    ws.column_dimensions["D"].width = 10
    ws.column_dimensions["E"].width = 10
    ws.column_dimensions["F"].width = 14
    ws.column_dimensions["G"].width = 20

    # Aba instrucoes
    wi = wb.create_sheet("Instruções")
    instrucoes = [
        ["Campo",               "Descrição"],
        ["item_id",             "Não altere — ID do produto na Shopee"],
        ["anunciar (sim/nao)",  "Preencha 'sim' para criar Ad | 'nao' para ignorar"],
    ]
    hf2 = PatternFill("solid", start_color="01696F")
    for ri, row in enumerate(instrucoes, 1):
        for ci, val in enumerate(row, 1):
            cell = wi.cell(row=ri, column=ci, value=val)
            cell.border = brd
            cell.font   = Font(name="Arial", size=10, bold=(ri==1), color="FFFFFF" if ri==1 else "000000")
            if ri == 1: cell.fill = hf2
    wi.column_dimensions["A"].width = 22
    wi.column_dimensions["B"].width = 45

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _chunk(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i+size]


# ── Render ────────────────────────────────────────────────────────────────────

def render():
    st.markdown('<p class="section-title">📣 Anúncios (Ads)</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Gerencie campanhas de produto da Shopee Ads</p>', unsafe_allow_html=True)

    tab_com, tab_sem, tab_roas = st.tabs([
        "✅ Produtos COM Ads",
        "🔍 Produtos SEM Ads",
        "⚡ Atualizar ROAS em Massa",
    ])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — PRODUTOS COM ADS
    # ══════════════════════════════════════════════════════════════════════════
    with tab_com:
        st.markdown("#### Campanhas de produto ativas")

        if st.button("🔍 Carregar Campanhas", key="load_campaigns"):
            with st.spinner("Buscando campanhas..."):
                res = sc.get_all_product_campaigns()
            if res.get("error"):
                st.error(f"❌ {res['error']}")
                if res.get("details"):
                    st.json(res["details"])
            else:
                campaigns = res.get("response", {}).get("campaign_list", [])
                st.session_state["ads_campaigns"] = campaigns
                if not campaigns:
                    st.info("Nenhuma campanha encontrada.")
                else:
                    st.success(f"✅ {len(campaigns)} campanha(s) encontrada(s)")

        if st.session_state.get("ads_campaigns"):
            camps = st.session_state["ads_campaigns"]
            rows  = []
            for c in camps:
                rows.append({
                    "Campaign ID":  c.get("campaign_id"),
                    "Item ID":      c.get("item_id"),
                    "Nome":         c.get("item_name", ""),
                    "Status":       c.get("campaign_status", ""),
                    "ROAS Alvo":    c.get("roas_target", 0),
                    "ROAS Real":    c.get("roas", 0),
                    "Orçamento":    c.get("budget", 0),
                    "Gasto Hoje":   c.get("cost", 0),
                    "Cliques":      c.get("clicks", 0),
                    "Impressões":   c.get("impressions", 0),
                    "Conversões":   c.get("orders", 0),
                })
            df_c = pd.DataFrame(rows)

            # Filtros
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                filtro_status = st.multiselect("Status", ["TODOS","active","paused","ended"], default=["TODOS"])
            with col_f2:
                filtro_nome = st.text_input("Filtrar por nome", placeholder="Digite parte do nome...")

            df_fil = df_c.copy()
            if filtro_status and "TODOS" not in filtro_status:
                df_fil = df_fil[df_fil["Status"].isin(filtro_status)]
            if filtro_nome.strip():
                df_fil = df_fil[df_fil["Nome"].str.contains(filtro_nome.strip(), case=False, na=False)]

            st.caption(f"Exibindo {len(df_fil)} de {len(df_c)} campanhas")

            st.dataframe(df_fil, use_container_width=True, hide_index=True,
                         column_config={
                             "ROAS Alvo":  st.column_config.NumberColumn(format="%.2f"),
                             "ROAS Real":  st.column_config.NumberColumn(format="%.2f"),
                             "Orçamento":  st.column_config.NumberColumn(format="R$ %.2f"),
                             "Gasto Hoje": st.column_config.NumberColumn(format="R$ %.2f"),
                         })

            csv = df_fil.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Exportar CSV", data=csv,
                               file_name="campanhas_ads.csv", mime="text/csv")

            # ── Atualizar ROAS individual ──────────────────────────────────
            st.divider()
            st.markdown("#### Atualizar ROAS individual")
            nomes   = [f"{r['Campaign ID']} — {r['Nome'][:60]}" for _, r in df_fil.iterrows()]
            if nomes:
                escolha  = st.selectbox("Selecione a campanha", nomes, key="camp_sel")
                idx      = nomes.index(escolha)
                camp     = df_fil.iloc[idx]
                roas_atual = float(camp.get("ROAS Alvo") or 0)

                col_r, col_b_upd, col_btn = st.columns([1, 1, 1])
                with col_r:
                    novo_roas = st.number_input("Novo ROAS", 0.1, 100.0,
                                                value=roas_atual or 3.0, step=0.1, key="roas_ind")
                with col_b_upd:
                    novo_orc = st.number_input("Novo Orçamento (R$)", 1.0, 10000.0,
                                               value=float(camp.get("Orçamento") or 10.0),
                                               step=1.0, key="orc_ind")
                with col_btn:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("💾 Atualizar", key="update_ind"):
                        with st.spinner("Atualizando..."):
                            r1 = sc.update_campaign_roas(camp["Campaign ID"], novo_roas)
                            r2 = sc.update_campaign_budget(camp["Campaign ID"], novo_orc)
                        if r1.get("error"):
                            st.error(f"❌ ROAS: {r1['error']}")
                        elif r2.get("error"):
                            st.error(f"❌ Orçamento: {r2['error']}")
                        else:
                            st.success("✅ Campanha atualizada!")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — PRODUTOS SEM ADS
    # ══════════════════════════════════════════════════════════════════════════
    with tab_sem:
        st.markdown("#### Produtos elegíveis para Ads (sem campanha ativa)")
        st.info("A Shopee retorna automaticamente os produtos com estoque disponíveis para anunciar.")

        col_b1, col_b2, _ = st.columns([1.5, 1.5, 3])
        with col_b1:
            btn_rec = st.button("🔍 Carregar Produtos Elegíveis", use_container_width=True)
        with col_b2:
            btn_upload = False  # só aparece após carregar

        if btn_rec:
            with st.spinner("Buscando produtos elegíveis para Ads..."):
                res = sc.get_all_recommended_items()
            if res.get("error"):
                st.error(f"❌ {res['error']}")
                if res.get("details"):
                    st.json(res["details"])
            else:
                items = res.get("response", {}).get("item_list", [])
                st.session_state["ads_sem"] = items
                if not items:
                    st.info("Nenhum produto elegível encontrado. Todos os produtos já possuem Ads ou estoque zerado.")
                else:
                    st.success(f"✅ {len(items)} produto(s) elegível(is)")

        if st.session_state.get("ads_sem"):
            items = st.session_state["ads_sem"]
            df_sem = pd.DataFrame([{
                "item_id":   it.get("item_id"),
                "item_name": it.get("item_name",""),
                "item_sku":  it.get("item_sku",""),
                "stock":     it.get("stock", 0),
                "sales":     it.get("sales", 0),
                "price":     it.get("price", 0),
            } for it in items])

            # Filtros locais
            filtro_sem = st.text_input("Filtrar por nome ou SKU", placeholder="Digite para filtrar...", key="filtro_sem")
            df_show = df_sem.copy()
            if filtro_sem.strip():
                df_show = df_show[
                    df_show["item_name"].str.contains(filtro_sem, case=False, na=False) |
                    df_show["item_sku"].str.contains(filtro_sem, case=False, na=False)
                ]

            st.caption(f"{len(df_show)} produto(s) elegíveis")
            st.dataframe(df_show.rename(columns={
                "item_id":"ID","item_name":"Nome","item_sku":"SKU",
                "stock":"Estoque","sales":"Vendas","price":"Preço (R$)"
            }), use_container_width=True, hide_index=True,
                         column_config={"Preço (R$)": st.column_config.NumberColumn(format="R$ %.2f")})

            # Download XLSX
            xlsx_bytes = _gerar_xlsx_sem_ads(df_show)
            st.download_button(
                "📥 Baixar XLSX para selecionar produtos",
                data=xlsx_bytes,
                file_name="produtos_sem_ads.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

            st.divider()
            st.markdown("#### Criar Ads via XLSX preenchido")
            st.info("Preencha a coluna **anunciar (sim/nao)** com `sim` nos produtos que deseja anunciar e faça o upload.")

            arquivo = st.file_uploader("Upload do XLSX preenchido", type=["xlsx"], key="ads_upload")
            if arquivo:
                df_up = pd.read_excel(arquivo, dtype={"item_id": str})
                df_sim = df_up[df_up["anunciar (sim/nao)"].str.strip().str.lower() == "sim"]
                st.success(f"✅ {len(df_sim)} produto(s) marcados para anunciar")

                if not df_sim.empty:
                    col_c1, col_c2, col_c3 = st.columns(3)
                    with col_c1:
                        roas_novo = st.number_input("ROAS alvo", 0.1, 100.0, 3.0, 0.1, key="roas_novo")
                    with col_c2:
                        budget_dia = st.number_input("Orçamento diário (R$)", 1.0, 10000.0, 50.0, 1.0, key="budget_novo")
                    with col_c3:
                        data_ini_ads = st.date_input("Data de início", value=datetime.now(BR).date(), key="ads_date")

                    start_date_str = data_ini_ads.strftime("%d-%m-%Y")

                    st.caption(f"Serão criados **{len(df_sim)}** anúncios individuais (um por produto).")

                    if st.button("🚀 Criar Anúncios", type="primary", key="criar_ads"):
                        erros   = []
                        sucesso = 0
                        prog    = st.progress(0, text="Criando anúncios...")
                        total   = len(df_sim)

                        for i, (_, row) in enumerate(df_sim.iterrows()):
                            item_id = int(str(row["item_id"]).strip())
                            res = sc.create_product_campaign(
                                item_id    = item_id,
                                budget     = budget_dia,
                                roas_target= roas_novo,
                                start_date = start_date_str,
                            )
                            if res.get("error"):
                                erros.append(f"ID {item_id}: {res['error']}")
                            else:
                                sucesso += 1
                            prog.progress((i+1)/total, text=f"Criando {i+1} de {total}...")

                        prog.empty()
                        if sucesso:
                            st.success(f"✅ {sucesso} anúncio(s) criado(s) com sucesso!")
                        if erros:
                            st.warning(f"⚠️ {len(erros)} erro(s):")
                            for e in erros[:20]:
                                st.caption(f"• {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — ATUALIZAR ROAS EM MASSA
    # ══════════════════════════════════════════════════════════════════════════
    with tab_roas:
        st.markdown("#### Atualizar ROAS de múltiplas campanhas de uma vez")
        st.info("Selecione campanhas usando checkboxes ou filtros, defina o novo ROAS e aplique em massa.")

        if not st.session_state.get("ads_campaigns"):
            st.warning("Carregue as campanhas primeiro na aba **✅ Produtos COM Ads**.")
        else:
            camps = st.session_state["ads_campaigns"]
            df_m  = pd.DataFrame([{
                "Selecionar":   False,
                "Campaign ID":  c.get("campaign_id"),
                "Nome":         c.get("item_name",""),
                "Status":       c.get("campaign_status",""),
                "ROAS Atual":   float(c.get("roas_target") or 0),
                "Orçamento":    float(c.get("budget") or 0),
            } for c in camps])

            # Filtro rápido antes do editor
            filtro_m = st.text_input("Filtrar por nome antes de selecionar", key="filtro_massa")
            if filtro_m.strip():
                df_m = df_m[df_m["Nome"].str.contains(filtro_m.strip(), case=False, na=False)]

            st.caption("Marque a coluna **Selecionar** nos produtos que deseja atualizar:")
            df_editado = st.data_editor(
                df_m,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Selecionar":  st.column_config.CheckboxColumn("✅ Selecionar"),
                    "ROAS Atual":  st.column_config.NumberColumn(format="%.2f"),
                    "Orçamento":   st.column_config.NumberColumn(format="R$ %.2f"),
                },
                disabled=["Campaign ID","Nome","Status","ROAS Atual","Orçamento"],
            )

            df_sel = df_editado[df_editado["Selecionar"] == True]
            st.caption(f"**{len(df_sel)}** campanha(s) selecionada(s)")

            if not df_sel.empty:
                col_r, col_o, col_btn = st.columns([1, 1, 1])
                with col_r:
                    roas_massa = st.number_input("Novo ROAS para todos", 0.1, 100.0, 3.0, 0.1, key="roas_massa")
                with col_o:
                    aplicar_orc = st.checkbox("Também atualizar orçamento?", key="aplic_orc")
                    if aplicar_orc:
                        orc_massa = st.number_input("Novo orçamento (R$)", 1.0, 10000.0, 50.0, 1.0, key="orc_massa")
                with col_btn:
                    st.markdown("<br>", unsafe_allow_html=True)
                    btn_massa = st.button(f"🚀 Aplicar em {len(df_sel)} campanha(s)", type="primary", key="btn_massa")

                if btn_massa:
                    erros   = []
                    sucesso = 0
                    prog    = st.progress(0, text="Atualizando ROAS...")
                    total   = len(df_sel)

                    for i, (_, row) in enumerate(df_sel.iterrows()):
                        cid = int(row["Campaign ID"])
                        r1  = sc.update_campaign_roas(cid, roas_massa)
                        if r1.get("error"):
                            erros.append(f"ID {cid}: {r1['error']}")
                        else:
                            sucesso += 1
                            if aplicar_orc:
                                sc.update_campaign_budget(cid, orc_massa)
                        prog.progress((i+1)/total, text=f"Atualizando {i+1} de {total}...")

                    prog.empty()
                    if sucesso:
                        st.success(f"✅ {sucesso} campanha(s) atualizada(s)!")
                    if erros:
                        st.warning(f"⚠️ {len(erros)} erro(s):")
                        for e in erros[:20]:
                            st.caption(f"• {e}")
                    # Limpa cache para recarregar
                    st.session_state.pop("ads_campaigns", None)
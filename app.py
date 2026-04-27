import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# 頁面設定
st.set_page_config(page_title="塗料生產績效儀表板", layout="wide")

st.title("📊 塗料生產績效與耗用分析儀表板")
st.markdown("依據 MES/Excel 數據進行系統化分析 (Data Flow 整合版)")

# ==========================================
# [ HELPER ] Smart multiselect with "All" label
# ==========================================
def smart_multiselect(label: str, options: list):
    """
    顯示一個 multiselect，當全部選取時 label 顯示 'All'，
    內部仍回傳完整選項清單供篩選使用。
    """
    all_options = sorted([str(o) for o in options])
    if not all_options:
        return []

    # 狀態 key 用於記住是否全選
    state_key = f"_smartsel_{label}"
    if state_key not in st.session_state:
        st.session_state[state_key] = True  # 預設全選

    toggle = st.sidebar.checkbox(f"全選 {label}", value=st.session_state[state_key], key=f"_chk_{label}")
    st.session_state[state_key] = toggle

    if toggle:
        # 全選時直接顯示 placeholder = "All"，不顯示個別選項
        st.sidebar.markdown(
            f"<div style='background:#f0f2f6;border-radius:6px;padding:6px 12px;"
            f"margin-bottom:8px;color:#555;font-size:0.85rem'>"
            f"<b>{label}</b>: <span style='color:#1f77b4'>All ({len(all_options)} 項)</span></div>",
            unsafe_allow_html=True,
        )
        return all_options
    else:
        selected = st.sidebar.multiselect(
            f"{label} (選擇項目)",
            options=all_options,
            default=all_options[:1] if all_options else [],
        )
        return selected if selected else all_options


# ==========================================
# [ DATA SOURCE & DATA LOAD ]
# ==========================================
st.sidebar.header("📂 [1] 資料匯入 (Data Load)")
uploaded_file = st.sidebar.file_uploader("請上傳資料檔 (支援 CSV 或 Excel)", type=["csv", "xlsx"])

if uploaded_file is not None:
    try:
        # 讀取資料
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file, engine="python", sep=None)
        else:
            df = pd.read_excel(uploaded_file)

        # ==========================================
        # [ DATA CLEANING ]
        # ==========================================
        df = df.dropna(subset=["塗料編號"])

        if "年月" in df.columns:
            df["年月"] = df["年月"].astype(str).str.replace(r"\.0$", "", regex=True)

        cat_cols = ["線別", "油漆廠商", "顏色", "樹脂", "用途"]
        for col in cat_cols:
            if col in df.columns:
                df[col] = df[col].fillna("未定義").astype(str)

        numeric_cols = ["合計理論耗用", "合計實際耗用", "合計績效%", "設定績效%"]
        for shift in ["A", "B", "C", "D"]:
            numeric_cols.extend(
                [f"{shift}班理論耗用", f"{shift}班實際耗用", f"{shift}班績效%"]
            )

        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # ==========================================
        # [ DATA MODELING ]
        # ==========================================
        if (
            "合計績效%" not in df.columns
            and "合計理論耗用" in df.columns
            and "合計實際耗用" in df.columns
        ):
            df["合計績效%"] = np.where(
                df["合計實際耗用"] != 0,
                (df["合計理論耗用"] / df["合計實際耗用"]) * 100,
                np.nan,
            )

        if "合計實際耗用" in df.columns and "合計理論耗用" in df.columns:
            df["Δ耗用 (Deviation)"] = df["合計實際耗用"] - df["合計理論耗用"]
            df["Δ% (Dev % )"] = np.where(
                df["合計理論耗用"] != 0,
                (df["Δ耗用 (Deviation)"] / df["合計理論耗用"]) * 100,
                np.nan,
            )

        # ==========================================
        # [ DASHBOARD FILTER ]
        # ==========================================
        st.sidebar.header("🔍 [2] 儀表板篩選 (Filters)")

        def get_unique(col):
            return sorted(df[col].dropna().unique()) if col in df.columns else []

        sel_line     = smart_multiselect("線別 (Line)",       get_unique("線別"))
        sel_color    = smart_multiselect("顏色 (Color)",      get_unique("顏色"))
        sel_resin    = smart_multiselect("樹脂 (Resin)",      get_unique("樹脂"))
        sel_supplier = smart_multiselect("廠商 (Supplier)",   get_unique("油漆廠商"))
        sel_purpose  = smart_multiselect("用途 (Purpose)",    get_unique("用途"))   # ← 新增
        sel_month    = smart_multiselect("年月 (Month)",      get_unique("年月"))

        def col_isin(col, vals):
            if col in df.columns:
                return df[col].isin(vals)
            return pd.Series(True, index=df.index)

        mask = (
            col_isin("線別",    sel_line)
            & col_isin("顏色",   sel_color)
            & col_isin("樹脂",   sel_resin)
            & col_isin("油漆廠商", sel_supplier)
            & col_isin("用途",   sel_purpose)
            & col_isin("年月",   sel_month)
        )
        filtered_df = df[mask].copy()

        # ==========================================
        # [ KPI 總覽 ]
        # ==========================================
        st.markdown("### 🎯 決策指標 (Decision Making KPIs)")
        if not filtered_df.empty:
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)

            avg_perf = filtered_df["合計績效%"].mean()
            total_delta = filtered_df["Δ耗用 (Deviation)"].sum()
            worst_paint = (
                filtered_df.loc[filtered_df["合計績效%"].idxmin()]
                if not filtered_df["合計績效%"].isna().all()
                else None
            )

            kpi1.metric(
                "整體平均績效",
                f"{avg_perf:.2f}%" if pd.notnull(avg_perf) else "N/A",
            )
            kpi2.metric(
                "總差異耗用 (實際 - 理論)",
                f"{total_delta:,.0f} 單位",
                "異常超耗" if total_delta > 0 else "耗用節省",
                delta_color="inverse",
            )
            if worst_paint is not None:
                kpi3.metric(
                    "需改善塗料 (效能最低)",
                    f"{worst_paint['塗料編號']}",
                    f"{worst_paint['合計績效%']:.2f}%",
                )
            else:
                kpi3.metric("需改善塗料", "無資料")

            kpi4.metric("篩選塗料總數", f"{len(filtered_df)} 筆")
        else:
            st.warning("查無符合篩選條件的資料。")

        st.divider()

        # ==========================================
        # [ VISUALIZATION ]
        # ==========================================
        st.markdown("### 📈 視覺化分析 (Visualization)")

        tab1, tab2, tab3, tab4 = st.tabs(
            [
                "🔥 班別熱力圖 (Heatmap)",
                "📊 理論與實際比較 (Bar)",
                "📉 耗用差異分析 (Deviation)",
                "📈 趨勢與關聯分析 (Trend)",
            ]
        )

        # ── Tab 1: Improved Heatmap ──────────────────────────────────────────
        with tab1:
            st.subheader("1. 班別績效熱力圖 (Shift Performance Heatmap)")
            st.markdown(
                "核心分析：快速識別哪個班別在特定塗料上表現最弱。"
                " 數字為平均績效%，**紅色 = 低績效，綠色 = 高績效**。"
            )

            shift_cols = [
                c
                for c in ["A班績效%", "B班績效%", "C班績效%", "D班績效%"]
                if c in filtered_df.columns
            ]

            if shift_cols:
                df_unpivot = pd.melt(
                    filtered_df,
                    id_vars=["塗料編號"],
                    value_vars=shift_cols,
                    var_name="班別",
                    value_name="績效%",
                )
                df_unpivot["班別"] = df_unpivot["班別"].str.replace("班績效%", "")
                df_unpivot = df_unpivot.dropna(subset=["績效%"])

                heatmap_data = (
                    df_unpivot.groupby(["塗料編號", "班別"])["績效%"]
                    .mean()
                    .reset_index()
                )

                # Pivot to matrix for annotation support
                pivot = heatmap_data.pivot(
                    index="塗料編號", columns="班別", values="績效%"
                )

                shifts_ordered = [s for s in ["A", "B", "C", "D"] if s in pivot.columns]
                pivot = pivot[shifts_ordered]

                z_vals  = pivot.values
                x_vals  = list(pivot.columns)
                y_vals  = list(pivot.index)

                # Annotation text: show value or blank if NaN
                annotations = []
                for yi, paint in enumerate(y_vals):
                    for xi, shift in enumerate(x_vals):
                        val = z_vals[yi][xi]
                        text = f"<b>{val:.1f}%</b>" if not np.isnan(val) else ""
                        # Choose contrasting font color based on value range
                        mid = np.nanmean(z_vals)
                        font_color = "white" if (not np.isnan(val) and val < mid) else "#1a1a1a"
                        annotations.append(
                            dict(
                                x=shift,
                                y=paint,
                                text=text,
                                showarrow=False,
                                font=dict(size=12, color=font_color),
                                xref="x",
                                yref="y",
                            )
                        )

                # Determine color range centered around 100%
                all_vals = z_vals[~np.isnan(z_vals)]
                if len(all_vals) > 0:
                    zmin = max(0, np.percentile(all_vals, 5))
                    zmax = np.percentile(all_vals, 95)
                    zmid = 100.0
                else:
                    zmin, zmax, zmid = 80, 120, 100

                fig_heat = go.Figure(
                    data=go.Heatmap(
                        z=z_vals,
                        x=x_vals,
                        y=y_vals,
                        colorscale=[
                            [0.0,  "#d73027"],   # 深紅 (低績效)
                            [0.25, "#f46d43"],
                            [0.45, "#fdae61"],
                            [0.5,  "#ffffbf"],   # 中黃 (接近目標)
                            [0.6,  "#a6d96a"],
                            [0.8,  "#66bd63"],
                            [1.0,  "#1a9850"],   # 深綠 (高績效)
                        ],
                        zmin=zmin,
                        zmax=zmax,
                        zmid=zmid,
                        colorbar=dict(
                            title="績效%",
                            ticksuffix="%",
                            thickness=18,
                            len=0.8,
                        ),
                        hoverongaps=False,
                        hovertemplate="塗料: %{y}<br>班別: %{x}<br>績效: %{z:.2f}%<extra></extra>",
                        xgap=2,   # 格線間距讓區塊更清晰
                        ygap=2,
                    )
                )

                fig_heat.update_layout(
                    annotations=annotations,
                    xaxis=dict(
                        title="班別 (Shift)",
                        side="top",
                        tickfont=dict(size=14, color="#333"),
                    ),
                    yaxis=dict(
                        title="塗料編號",
                        autorange="reversed",
                        tickfont=dict(size=11),
                    ),
                    height=max(400, len(y_vals) * 36 + 120),
                    margin=dict(l=120, r=60, t=80, b=40),
                    plot_bgcolor="#f8f8f8",
                    paper_bgcolor="white",
                )

                # 加入目標績效參考線說明
                st.info("📌 色階中點設定為 **100%**（目標績效）。黃色 = 接近目標，紅色 = 低於目標，綠色 = 超越目標。")
                st.plotly_chart(fig_heat, use_container_width=True)

                # 補充：低績效 Top 5 清單
                worst5 = heatmap_data.nsmallest(5, "績效%")[["塗料編號", "班別", "績效%"]]
                if not worst5.empty:
                    with st.expander("⚠️ 績效最低 Top 5 (需優先改善)"):
                        st.dataframe(
                            worst5.style.background_gradient(subset=["績效%"], cmap="RdYlGn"),
                            use_container_width=True,
                        )
            else:
                st.info("資料缺少班別績效欄位，無法繪製熱力圖。")

        # ── Tab 2 ────────────────────────────────────────────────────────────
        with tab2:
            st.subheader("2. 理論耗用 vs 實際耗用 (Theoretical vs Actual)")
            df_bar = (
                filtered_df.groupby("塗料編號")[["合計理論耗用", "合計實際耗用"]]
                .sum()
                .reset_index()
            )

            fig_bar = go.Figure()
            fig_bar.add_trace(
                go.Bar(
                    x=df_bar["塗料編號"],
                    y=df_bar["合計理論耗用"],
                    name="理論耗用 (Theoretical)",
                    marker_color="rgb(55, 83, 109)",
                )
            )
            fig_bar.add_trace(
                go.Bar(
                    x=df_bar["塗料編號"],
                    y=df_bar["合計實際耗用"],
                    name="實際耗用 (Actual)",
                    marker_color="rgb(26, 118, 255)",
                )
            )
            fig_bar.update_layout(
                barmode="group", xaxis_title="塗料編號", yaxis_title="耗用量"
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        # ── Tab 3 ────────────────────────────────────────────────────────────
        with tab3:
            st.subheader("3. 耗用差異圖表 (Deviation Chart)")
            st.markdown(
                "分析 `Δ耗用 = 實際 - 理論`。數值大於 0 表示**超耗 (紅色)**，小於 0 表示**節省 (綠色)**。"
            )

            df_dev = (
                filtered_df.groupby("塗料編號")["Δ耗用 (Deviation)"].sum().reset_index()
            )
            df_dev["顏色標示"] = np.where(
                df_dev["Δ耗用 (Deviation)"] > 0, "超耗 (Over)", "節省 (Under)"
            )

            fig_dev = px.bar(
                df_dev,
                x="塗料編號",
                y="Δ耗用 (Deviation)",
                color="顏色標示",
                color_discrete_map={"超耗 (Over)": "red", "節省 (Under)": "green"},
            )
            fig_dev.add_hline(y=0, line_dash="solid", line_color="black")
            fig_dev.update_layout(
                xaxis_title="塗料編號", yaxis_title="差異量 (Δ耗用)"
            )
            st.plotly_chart(fig_dev, use_container_width=True)

        # ── Tab 4 ────────────────────────────────────────────────────────────
        with tab4:
            st.subheader("4. 績效趨勢與廠商分析 (Trend & Supplier Comparison)")
            col_trend1, col_trend2 = st.columns(2)

            with col_trend1:
                df_trend = (
                    filtered_df.groupby("年月")["合計績效%"].mean().reset_index()
                )
                df_trend = df_trend.sort_values("年月")
                fig_trend = px.line(
                    df_trend,
                    x="年月",
                    y="合計績效%",
                    markers=True,
                    title="隨時間變化的平均績效趨勢",
                )
                fig_trend.add_hline(
                    y=100,
                    line_dash="dash",
                    line_color="red",
                    annotation_text="目標 100%",
                )
                st.plotly_chart(fig_trend, use_container_width=True)

            with col_trend2:
                if "油漆廠商" in filtered_df.columns:
                    df_sup = (
                        filtered_df.groupby("油漆廠商")["合計績效%"]
                        .mean()
                        .reset_index()
                    )
                    fig_sup = px.bar(
                        df_sup,
                        x="油漆廠商",
                        y="合計績效%",
                        color="合計績效%",
                        color_continuous_scale="Blues",
                        title="各油漆廠商平均績效比較",
                    )
                    fig_sup.add_hline(
                        y=100, line_dash="dash", line_color="red"
                    )
                    st.plotly_chart(fig_sup, use_container_width=True)

            # 用途分析 (新增) ──────────────────────────────────────────────
            if "用途" in filtered_df.columns:
                st.markdown("#### 用途別績效比較")
                df_purpose = (
                    filtered_df.groupby("用途")["合計績效%"].mean().reset_index()
                )
                fig_purpose = px.bar(
                    df_purpose,
                    x="用途",
                    y="合計績效%",
                    color="合計績效%",
                    color_continuous_scale="RdYlGn",
                    title="各用途平均績效比較",
                    text_auto=".1f",
                )
                fig_purpose.add_hline(
                    y=100, line_dash="dash", line_color="red", annotation_text="目標 100%"
                )
                st.plotly_chart(fig_purpose, use_container_width=True)

        # 原始資料檢視
        with st.expander("🔍 檢視轉換後的底層資料 (Data View)"):
            st.dataframe(filtered_df)

    except Exception as e:
        st.error(f"資料處理時發生錯誤，請確認檔案格式是否符合。錯誤詳情：{e}")

else:
    st.info("👈 請於左側面板上傳您的資料集 (Data Source) 以驅動分析引擎。")

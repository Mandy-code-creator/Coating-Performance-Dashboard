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
# [ DATA SOURCE & DATA LOAD ]
# ==========================================
st.sidebar.header("📂 [1] 資料匯入 (Data Load)")
uploaded_file = st.sidebar.file_uploader("請上傳資料檔 (支援 CSV 或 Excel)", type=['csv', 'xlsx'])

if uploaded_file is not None:
    try:
        # 讀取資料
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, engine='python', sep=None)
        else:
            df = pd.read_excel(uploaded_file)

        # ==========================================
        # [ DATA CLEANING ]
        # ==========================================
        # 1. 處理 Missing (空值) 與欄位格式化
        df = df.dropna(subset=['塗料編號']) # 排除沒有塗料編號的無效數據
        
        if '年月' in df.columns:
            # 將年月轉為字串並去除可能的浮點數小數點 (如 202603.0 -> 202603)
            df['年月'] = df['年月'].astype(str).str.replace(r'\.0$', '', regex=True)

        # 確保特定分類欄位為字串
        cat_cols = ['線別', '油漆廠商', '顏色', '樹脂', '用途']
        for col in cat_cols:
            if col in df.columns:
                df[col] = df[col].fillna('未定義').astype(str)

        # 2. 數值標準化與格式化 (確保為浮點數，去除異常文字)
        numeric_cols = ['合計理論耗用', '合計實際耗用', '合計績效%', '設定績效%']
        for shift in ['A', 'B', 'C', 'D']:
            numeric_cols.extend([f'{shift}班理論耗用', f'{shift}班實際耗用', f'{shift}班績效%'])
            
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # ==========================================
        # [ DATA MODELING ]
        # ==========================================
        # 建立 Measure (計算指標)
        # 績效% = 理論 / 實際 (依據現有資料邏輯) 或 實際 / 理論 (若資料缺失則補算)
        if '合計績效%' not in df.columns and '合計理論耗用' in df.columns and '合計實際耗用' in df.columns:
            df['合計績效%'] = np.where(df['合計實際耗用'] != 0, (df['合計理論耗用'] / df['合計實際耗用']) * 100, np.nan)
            
        # Δ耗用 = 實際耗用 - 理論耗用 (大於0代表超耗)
        if '合計實際耗用' in df.columns and '合計理論耗用' in df.columns:
            df['Δ耗用 (Deviation)'] = df['合計實際耗用'] - df['合計理論耗用']
            df['Δ% (Dev % )'] = np.where(df['合計理論耗用'] != 0, (df['Δ耗用 (Deviation)'] / df['合計理論耗用']) * 100, np.nan)

        # ==========================================
        # [ DASHBOARD FILTER (POWER BI LAYER) ]
        # ==========================================
        st.sidebar.header("🔍 [2] 儀表板篩選 (Filters)")
        
        st.sidebar.markdown("**階層式連動篩選 (Cascading Filters)**")
        
        # 1. 選擇時間 (Month)
        months = sorted(df['年月'].dropna().unique()) if '年月' in df.columns else []
        sel_month = st.sidebar.multiselect("1. 年月 (Month)", options=months, default=months)
        df_step1 = df[df['年月'].isin(sel_month)] if '年月' in df.columns else df
        
        # 2. 選擇線別 (Line) - 選項會依據已選的「年月」自動更新
        lines = sorted(df_step1['線別'].dropna().unique()) if '線別' in df_step1.columns else []
        sel_line = st.sidebar.multiselect("2. 線別 (Line)", options=lines, default=lines)
        df_step2 = df_step1[df_step1['線別'].isin(sel_line)] if '線別' in df_step1.columns else df_step1
        
        # 3. 選擇用途 (Usage) - 加入您要求的「用途」篩選，選項會依據前兩步自動更新
        usages = sorted(df_step2['用途'].dropna().unique()) if '用途' in df_step2.columns else []
        sel_usage = st.sidebar.multiselect("3. 用途 (Usage)", options=usages, default=usages)
        df_step3 = df_step2[df_step2['用途'].isin(sel_usage)] if '用途' in df_step2.columns else df_step2

        st.sidebar.markdown("---")
        st.sidebar.markdown("**其他屬性篩選**")
        
        def get_unique_step3(col): return sorted(df_step3[col].dropna().unique()) if col in df_step3.columns else []
        
        sel_color = st.sidebar.multiselect("顏色 (Color)", options=get_unique_step3('顏色'), default=get_unique_step3('顏色'))
        sel_resin = st.sidebar.multiselect("樹脂 (Resin)", options=get_unique_step3('樹脂'), default=get_unique_step3('樹脂'))
        sel_supplier = st.sidebar.multiselect("廠商 (Supplier)", options=get_unique_step3('油漆廠商'), default=get_unique_step3('油漆廠商'))

        # 應用最終篩選器
        mask = (
            df_step3.get('顏色', pd.Series(True, index=df_step3.index)).isin(sel_color) &
            df_step3.get('樹脂', pd.Series(True, index=df_step3.index)).isin(sel_resin) &
            df_step3.get('油漆廠商', pd.Series(True, index=df_step3.index)).isin(sel_supplier)
        )
        filtered_df = df_step3[mask].copy()

        # ==========================================
        # [ DECISION MAKING ] KPI 總覽
        # ==========================================
        st.markdown("### 🎯 決策指標 (Decision Making KPIs)")
        if not filtered_df.empty:
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            
            avg_perf = filtered_df['合計績效%'].mean()
            total_delta = filtered_df['Δ耗用 (Deviation)'].sum()
            worst_paint = filtered_df.loc[filtered_df['合計績效%'].idxmin()] if not filtered_df['合計績效%'].isna().all() else None
            
            kpi1.metric("整體平均績效", f"{avg_perf:.2f}%" if pd.notnull(avg_perf) else "N/A")
            kpi2.metric("總差異耗用 (實際 - 理論)", f"{total_delta:,.0f} 單位", "異常超耗" if total_delta > 0 else "耗用節省", delta_color="inverse")
            
            if worst_paint is not None:
                kpi3.metric("需改善塗料 (效能最低)", f"{worst_paint['塗料編號']}", f"{worst_paint['合計績效%']:.2f}%")
            else:
                kpi3.metric("需改善塗料", "無資料")
                
            kpi4.metric("篩選塗料總數", f"{len(filtered_df)} 筆")
        else:
            st.warning("查無符合篩選條件的資料。")

        st.divider()

        # ==========================================
        # [ DATA TRANSFORM & ANALYSIS LAYER ]
        # ==========================================
        st.markdown("### 📈 視覺化分析 (Visualization)")
        
        tab1, tab2, tab3, tab4 = st.tabs(["🔥 班別熱力圖 (Heatmap)", "📊 理論與實際比較 (Bar)", "📉 耗用差異分析 (Deviation)", "📈 趨勢與關聯分析 (Trend)"])

        with tab1:
            st.subheader("1. 塗料整體績效熱力圖 (Overall Performance Heatmap)")
            st.markdown("核心分析：快速識別特定塗料的整體表現 (顏色越紅代表績效越低)")
            
            # 檢查是否有 合計績效% 欄位
            if '合計績效%' in filtered_df.columns:
                # 依據塗料編號計算平均合計績效 (以防多筆相同編號)
                heatmap_data = filtered_df.groupby('塗料編號')['合計績效%'].mean().reset_index()
                
                # 新增一個固定欄位名稱作為 X 軸
                heatmap_data['指標'] = '合計績效 (Total %)'
                
                # 轉為 Pivot 格式矩陣
                pivot_df = heatmap_data.pivot(index='塗料編號', columns='指標', values='合計績效%')
                
                # 💡 動態計算高度：每個塗料編號分配 25 pixel 的高度，確保 129 個塗料也能全部顯示
                unique_paints = pivot_df.index.tolist()
                dynamic_height = max(400, len(unique_paints) * 25)
                
                fig_heat = go.Figure(data=go.Heatmap(
                    z=pivot_df.values,
                    x=pivot_df.columns.tolist(),
                    y=unique_paints,
                    text=np.round(pivot_df.values, 1), # 顯示 1 位小數點
                    texttemplate="%{text}%",           # 將 % 符號加進方塊內
                    colorscale='RdYlGn',               # 紅(低) -> 黃 -> 綠(高)
                    hoverongaps=False
                ))
                
                fig_heat.update_layout(
                    xaxis_title="", 
                    yaxis_title="塗料編號", 
                    height=dynamic_height,             # 套用動態高度
                    yaxis=dict(dtick=1),               # 💡 強制顯示所有 Y 軸標籤 (不自動隱藏)
                    xaxis=dict(side='top')             # 將 X 軸標籤移至頂部
                )
                
                st.plotly_chart(fig_heat, use_container_width=True)
            else:
                st.info("資料缺少「合計績效%」欄位，無法繪製熱力圖。")
        with tab2:
            st.subheader("2. 理論耗用 vs 實際耗用 (Theoretical vs Actual)")
            # 依據塗料編號分組加總
            df_bar = filtered_df.groupby('塗料編號')[['合計理論耗用', '合計實際耗用']].sum().reset_index()
            
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(x=df_bar['塗料編號'], y=df_bar['合計理論耗用'], name='理論耗用 (Theoretical)', marker_color='rgb(55, 83, 109)'))
            fig_bar.add_trace(go.Bar(x=df_bar['塗料編號'], y=df_bar['合計實際耗用'], name='實際耗用 (Actual)', marker_color='rgb(26, 118, 255)'))
            fig_bar.update_layout(barmode='group', xaxis_title="塗料編號", yaxis_title="耗用量")
            st.plotly_chart(fig_bar, use_container_width=True)

        with tab3:
            st.subheader("3. 耗用差異圖表 (Deviation Chart)")
            st.markdown("分析 `Δ耗用 = 實際 - 理論`。數值大於 0 表示**超耗 (紅色)**，小於 0 表示**節省 (綠色)**。")
            
            df_dev = filtered_df.groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index()
            # 設定顏色標籤
            df_dev['顏色標示'] = np.where(df_dev['Δ耗用 (Deviation)'] > 0, '超耗 (Over)', '節省 (Under)')
            
            fig_dev = px.bar(df_dev, x='塗料編號', y='Δ耗用 (Deviation)', color='顏色標示',
                             color_discrete_map={'超耗 (Over)': 'red', '節省 (Under)': 'green'})
            fig_dev.add_hline(y=0, line_dash="solid", line_color="black")
            fig_dev.update_layout(xaxis_title="塗料編號", yaxis_title="差異量 (Δ耗用)")
            st.plotly_chart(fig_dev, use_container_width=True)

        with tab4:
            st.subheader("4. 績效趨勢與廠商分析 (Trend & Supplier Comparison)")
            col_trend1, col_trend2 = st.columns(2)
            
            with col_trend1:
                # 趨勢圖 (Trend Chart)
                df_trend = filtered_df.groupby('年月')['合計績效%'].mean().reset_index()
                df_trend = df_trend.sort_values('年月')
                fig_trend = px.line(df_trend, x='年月', y='合計績效%', markers=True, title="隨時間變化的平均績效趨勢")
                fig_trend.add_hline(y=100, line_dash="dash", line_color="red", annotation_text="目標 100%")
                st.plotly_chart(fig_trend, use_container_width=True)
                
            with col_trend2:
                # 廠商表現比較 (Supplier / Resin)
                if '油漆廠商' in filtered_df.columns:
                    df_sup = filtered_df.groupby('油漆廠商')['合計績效%'].mean().reset_index()
                    fig_sup = px.bar(df_sup, x='油漆廠商', y='合計績效%', color='合計績效%', color_continuous_scale='Blues', title="各油漆廠商平均績效比較")
                    fig_sup.add_hline(y=100, line_dash="dash", line_color="red")
                    st.plotly_chart(fig_sup, use_container_width=True)

        # 原始資料檢視
        with st.expander("🔍 檢視轉換後的底層資料 (Data View)"):
            st.dataframe(filtered_df)

    except Exception as e:
        st.error(f"資料處理時發生錯誤，請確認檔案格式是否符合。錯誤詳情：{e}")

else:
    st.info("👈 請於左側面板上傳您的資料集 (Data Source) 以驅動分析引擎。")

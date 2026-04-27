import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import math
from plotly.subplots import make_subplots

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
        # [ DATA CLEANING & MODELING ]
        # ==========================================
        df = df.dropna(subset=['塗料編號']).copy()
        
        if '年月' in df.columns:
            df['年月'] = df['年月'].astype(str).str.replace(r'\.0$', '', regex=True)

        cat_cols = ['線別', '油漆廠商', '顏色', '樹脂', '用途']
        for col in cat_cols:
            if col in df.columns:
                df[col] = df[col].fillna('未定義').astype(str).str.strip()

        numeric_cols = ['合計理論耗用', '合計實際耗用', '合計績效%', '設定績效%']
        for shift in ['A', 'B', 'C', 'D']:
            numeric_cols.extend([f'{shift}班理論耗用', f'{shift}班實際耗用', f'{shift}班績效%'])
            
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 建立 Measure (計算指標)
        if '合計績效%' not in df.columns and '合計理論耗用' in df.columns and '合計實際耗用' in df.columns:
            df['合計績效%'] = np.where(df['合計實際耗用'] != 0, (df['合計理論耗用'] / df['合計實際耗用']) * 100, np.nan)
            
        if '合計實際耗用' in df.columns and '合計理論耗用' in df.columns:
            df['Δ耗用 (Deviation)'] = df['合計實際耗用'] - df['合計理論耗用']
            df['Δ% (Dev % )'] = np.where(df['合計理論耗用'] != 0, (df['Δ耗用 (Deviation)'] / df['合計理論耗用']) * 100, np.nan)

        # [ LOGIC CHỈNH SỬA: Nhóm GE00/GE01 để sắp xếp trên biểu đồ ]
        df['Sort_Group'] = df['塗料編號'].apply(lambda x: 'GE00_01_Group' if any(g in str(x) for g in ['GE00', 'GE01']) else str(x))

        # ==========================================
        # [ DASHBOARD FILTER (階層式連動篩選) ]
        # ==========================================
        st.sidebar.header("🔍 [2] 儀表板篩選 (Filters)")
        
        # 1. 選擇時間 (Month)
        months = sorted(df['年月'].dropna().unique()) if '年月' in df.columns else []
        sel_month = st.sidebar.multiselect("1. 年月 (Month)", options=months, default=months)
        df_step1 = df[df['年月'].isin(sel_month)] if '年月' in df.columns else df
        
        # 2. 選擇線別 (Line)
        lines = sorted(df_step1['線別'].dropna().unique()) if '線別' in df_step1.columns else []
        sel_line = st.sidebar.multiselect("2. 線別 (Line)", options=lines, default=lines)
        df_step2 = df_step1[df_step1['線別'].isin(sel_line)] if '線別' in df_step1.columns else df_step1
        
        # 3. 選擇用途 (Usage)
        usages = sorted(df_step2['用途'].dropna().unique()) if '用途' in df_step2.columns else []
        sel_usage = st.sidebar.multiselect("3. 用途 (Usage)", options=usages, default=usages)
        df_step3 = df_step2[df_step2['用途'].isin(sel_usage)] if '用途' in df_step2.columns else df_step2

        st.sidebar.markdown("---")
        st.sidebar.markdown("**其他屬性篩選**")
        
        def get_unique_step3(col): return sorted(df_step3[col].dropna().unique()) if col in df_step3.columns else []
        
        sel_color = st.sidebar.multiselect("顏色 (Color)", options=get_unique_step3('顏色'), default=get_unique_step3('顏色'))
        sel_resin = st.sidebar.multiselect("樹脂 (Resin)", options=get_unique_step3('樹脂'), default=get_unique_step3('樹脂'))
        sel_supplier = st.sidebar.multiselect("廠商 (Supplier)", options=get_unique_step3('油漆廠商'), default=get_unique_step3('油漆廠商'))

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
            
            # 統計篩選後的獨立塗料編號數量
            total_paint_codes = len(filtered_df['塗料編號'].unique())
            
            kpi1.metric("整體平均績效", f"{avg_perf:.2f}%" if pd.notnull(avg_perf) else "N/A")
            kpi2.metric("總差異耗用 (實際 - 理論)", f"{total_delta:,.0f} 單位", "異常超耗" if total_delta > 0 else "耗用節省", delta_color="inverse")
            
            if worst_paint is not None:
                kpi3.metric("需改善塗料 (效能最低)", f"{worst_paint['塗料編號']}", f"{worst_paint['合計績效%']:.2f}%")
            else:
                kpi3.metric("需改善塗料", "無資料")
                
            kpi4.metric("分析塗料總數", f"{total_paint_codes} 支")
        else:
            st.warning("查無符合篩選條件的資料。")
            total_paint_codes = 0

        st.divider()

        # ==========================================
        # [ VISUALIZATION LAYER ]
        # ==========================================
        st.markdown("### 📈 視覺化分析 (Visualization)")
        
        # 產生共用的排序列表 (GE00與GE01群組化)
        sort_order = filtered_df.sort_values(by=['Sort_Group', '塗料編號'])['塗料編號'].unique().tolist()
        
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "🔥 整體績效熱力圖 (Heatmap)", 
            "📊 理論與實際比較 (Bar)", 
            "📉 耗用差異分析 (Deviation)", 
            "🎯 績效散佈趨勢 (Scatter)", 
            "📈 趨勢與廠商分析 (Trend)"
        ])

        with tab1:
            st.subheader(f"1. 塗料整體績效熱力圖 (共分析 {total_paint_codes} 支塗料)")
            st.markdown("核心分析：快速識別所有塗料的整體表現。資料已自動分欄顯示以節省空間 (顏色越紅代表績效越低)。")
            
            if '合計績效%' in filtered_df.columns:
                # 依據塗料編號計算平均合計績效
                heatmap_data = filtered_df.dropna(subset=['合計績效%']).groupby('塗料編號')['合計績效%'].mean().reset_index()
                heatmap_data['Sort_Group'] = heatmap_data['塗料編號'].apply(lambda x: 'GE00_01_Group' if any(g in str(x) for g in ['GE00', 'GE01']) else str(x))
                heatmap_data = heatmap_data.sort_values(by=['Sort_Group', '塗料編號'])
                
                total_items = len(heatmap_data)
                
                if total_items > 0:
                    items_per_column = 30 
                    num_cols = math.ceil(total_items / items_per_column)
                    
                    fig_heat = make_subplots(rows=1, cols=num_cols, shared_yaxes=False, horizontal_spacing=0.08)
                    z_min = heatmap_data['合計績效%'].min()
                    z_max = heatmap_data['合計績效%'].max()
                    
                    for i in range(num_cols):
                        start_idx = i * items_per_column
                        end_idx = min((i + 1) * items_per_column, total_items)
                        chunk_df = heatmap_data.iloc[start_idx:end_idx]
                        
                        y_labels = chunk_df['塗料編號'].tolist()[::-1]
                        z_values = chunk_df['合計績效%'].tolist()[::-1]
                        
                        z_2d = [[val] for val in z_values]
                        text_2d = [[f"{val:.1f}%"] for val in z_values]
                        
                        fig_heat.add_trace(
                            go.Heatmap(
                                z=z_2d, x=['合計績效%'], y=y_labels, text=text_2d, texttemplate="%{text}",
                                colorscale='RdYlGn', zmin=z_min, zmax=z_max,
                                showscale=(i == num_cols - 1), hoverinfo='y+z'
                            ),
                            row=1, col=i+1
                        )
                        fig_heat.update_xaxes(side='top', row=1, col=i+1)
                        fig_heat.update_yaxes(dtick=1, row=1, col=i+1)
                    
                    dynamic_height = max(400, items_per_column * 28)
                    fig_heat.update_layout(height=dynamic_height, margin=dict(t=50, b=20, l=10, r=10), plot_bgcolor='white')
                    st.plotly_chart(fig_heat, use_container_width=True)
                else:
                    st.warning("目前篩選條件下沒有足夠的資料繪製圖表。")

        with tab2:
            st.subheader("2. 理論耗用 vs 實際耗用 (Theoretical vs Actual)")
            df_bar = filtered_df.groupby('塗料編號')[['合計理論耗用', '合計實際耗用']].sum().reset_index()
            
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(x=df_bar['塗料編號'], y=df_bar['合計理論耗用'], name='理論耗用 (理論值)', marker_color='rgb(55, 83, 109)'))
            fig_bar.add_trace(go.Bar(x=df_bar['塗料編號'], y=df_bar['合計實際耗用'], name='實際耗用 (實際值)', marker_color='rgb(26, 118, 255)'))
            fig_bar.update_layout(barmode='group', xaxis_title="塗料編號", yaxis_title="耗用量", xaxis={'categoryorder':'array', 'categoryarray':sort_order})
            st.plotly_chart(fig_bar, use_container_width=True)

        with tab3:
            st.subheader("3. 耗用差異圖表 (Deviation Chart)")
            st.markdown("分析 `Δ耗用 = 實際 - 理論`。數值大於 0 表示**超耗 (紅色)**，小於 0 表示**節省 (綠色)**。")
            df_dev = filtered_df.groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index()
            df_dev['顏色標示'] = np.where(df_dev['Δ耗用 (Deviation)'] > 0, '超耗 (Over)', '節省 (Under)')
            
            fig_dev = px.bar(df_dev, x='塗料編號', y='Δ耗用 (Deviation)', color='顏色標示',
                             color_discrete_map={'超耗 (Over)': 'red', '節省 (Under)': 'green'})
            fig_dev.add_hline(y=0, line_dash="solid", line_color="black")
            fig_dev.update_layout(xaxis_title="塗料編號", yaxis_title="差異量 (Δ耗用)", xaxis={'categoryorder':'array', 'categoryarray':sort_order})
            st.plotly_chart(fig_dev, use_container_width=True)

        # --- 新增的 Scatter Plot Tab ---
# --- 新增的 Scatter Plot Tab ---
        with tab4:
            st.subheader("4. 績效散佈趨勢圖 (Scatter Trend & Outliers)")
            
            # Ghi chú quy tắc màu sắc (Legend / Notes) hiển thị trực tiếp trên Dashboard
            st.markdown("""
            **💡 績效燈號規則 (Quy tắc cảnh báo):**
            * 🔴 **紅色 (嚴重耗損):** < 85% *(Hao hụt nghiêm trọng)*
            * 🟡 **黃色 (注意耗損):** 85% - 95% *(Cần chú ý)*
            * 🔵 **藍色 (接近達標):** 95% - 100% *(Gần đạt chuẩn)*
            * 🟢 **綠色 (達標/節省):** ≥ 100% *(Đạt chuẩn / Tiết kiệm)*
            
            *(👉 圓圈大小代表「理論耗用量」，大紅圈為首要改善目標 / Vòng tròn càng to, lượng hao hụt theo lý thuyết càng lớn. Vòng tròn TO MÀU ĐỎ là mục tiêu cần cải thiện gấp!)*
            """)
            
            # 確保有資料繪圖
            if not filtered_df.empty and '合計績效%' in filtered_df.columns:
                plot_df = filtered_df.copy()
                
                # 1. Thiết lập quy tắc phân loại nhóm hiệu suất
                conditions = [
                    plot_df['合計績效%'] < 85,
                    (plot_df['合計績效%'] >= 85) & (plot_df['合計績效%'] < 95),
                    (plot_df['合計績效%'] >= 95) & (plot_df['合計績效%'] < 100),
                    plot_df['合計績效%'] >= 100
                ]
                choices = ['< 85% (嚴重耗損)', '85% - 95% (注意耗損)', '95% - 100% (接近達標)', '≥ 100% (達標/節省)']
                plot_df['績效級別'] = np.select(conditions, choices, default='未知')
                
                # 2. Quy định màu sắc chuẩn xác cho từng nhóm
                color_map = {
                    '< 85% (嚴重耗損)': '#d73027',    # Đỏ
                    '85% - 95% (注意耗損)': '#fee08b',   # Vàng
                    '95% - 100% (接近達標)': '#4575b4',  # Xanh dương
                    '≥ 100% (達標/節省)': '#1a9850'      # Xanh lá
                }
                
                # 3. Vẽ biểu đồ Scatter
                fig_scatter = px.scatter(
                    plot_df,
                    x='塗料編號',
                    y='合計績效%',
                    color='績效級別',
                    color_discrete_map=color_map,
                    size='合計理論耗用' if '合計理論耗用' in plot_df.columns else None,
                    hover_data=['用途', '線別', '年月', '合計理論耗用', '合計實際耗用'],
                    size_max=35, # Tăng kích thước chấm to lên một chút để dễ nhìn hơn
                    category_orders={"績效級別": ['< 85% (嚴重耗損)', '85% - 95% (注意耗損)', '95% - 100% (接近達標)', '≥ 100% (達標/節省)']}
                )
                
                # Thêm đường line mốc 100%
                fig_scatter.add_hline(y=100, line_dash="dash", line_color="black", annotation_text="目標 (100%)")
                
                fig_scatter.update_layout(
                    xaxis_title="塗料編號", 
                    yaxis_title="合計績效 (%)",
                    xaxis={'categoryorder':'array', 'categoryarray':sort_order},
                    height=550,
                    legend_title_text="績效級別 (Legend)",
                    legend=dict(
                        orientation="h", # Chuyển chú thích màu nằm ngang cho đỡ chiếm diện tích
                        yanchor="bottom",
                        y=1.02,
                        xanchor="right",
                        x=1
                    )
                )
                st.plotly_chart(fig_scatter, use_container_width=True)

        with tab5:
            st.subheader("5. 績效趨勢與廠商分析 (Trend & Supplier Comparison)")
            col_trend1, col_trend2 = st.columns(2)
            
            with col_trend1:
                if '年月' in filtered_df.columns:
                    df_trend = filtered_df.groupby('年月')['合計績效%'].mean().reset_index()
                    df_trend = df_trend.sort_values('年月')
                    fig_trend = px.line(df_trend, x='年月', y='合計績效%', markers=True, title="隨時間變化的平均績效趨勢")
                    fig_trend.add_hline(y=100, line_dash="dash", line_color="red", annotation_text="目標 100%")
                    st.plotly_chart(fig_trend, use_container_width=True)
                
            with col_trend2:
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

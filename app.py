import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import math

# ==========================================
# [ 0. PAGE CONFIG & CSS ]
# ==========================================
st.set_page_config(page_title="塗料生產績效看板", layout="wide")

st.markdown("""
<style>
.stPlotlyChart {
    border-radius: 8px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    background-color: white;
    overflow: hidden;
}
[data-testid="stKPIs"] div{
    border: 1px solid #e6e6e6;
    border-radius: 8px;
    padding: 10px;
    background-color: #f9fbfd;
}
</style>
""", unsafe_allow_html=True)

st.title("📊 塗料生產績效與耗用分析儀表板")
st.markdown("<b>依據 MES/Excel 數據進行系統化分析 (高階決策最佳化佈局)</b>", unsafe_allow_html=True)

# ==========================================
# [ 1. DATA SOURCE & DATA LOAD ]
# ==========================================
st.sidebar.header("📂 [1] 資料匯入 (Data Load)")
uploaded_file = st.sidebar.file_uploader("請上傳資料檔 (支援 CSV 或 Excel)", type=['csv', 'xlsx'])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, encoding='utf-8-sig', dtype=str)
        else:
            df = pd.read_excel(uploaded_file, dtype=str)

        df.columns = df.columns.str.strip()
        df = df.dropna(how='all')
        
        if '線別' in df.columns:
            df['線別'] = df['線別'].astype(str).str.strip()
            df = df[(df['線別'] != '線別') & (df['線別'] != 'nan') & (df['線別'] != '')]

        cat_cols = ['線別', '塗料編號', '用途', '年月', '油漆廠商', '顏色', '樹脂']
        for col in cat_cols:
            if col in df.columns:
                df[col] = df[col].fillna('未定義').astype(str).str.strip()

        numeric_cols = ['合計理論耗用', '合計實際耗用', '合計績效%', '設定績效%']
        shift_cols = []
        for shift in ['A', 'B', 'C', 'D']:
            cols = [f'{shift}班理論耗用', f'{shift}班實際耗用', f'{shift}班績效%']
            numeric_cols.extend(cols)
            if f'{shift}班績效%' in df.columns:
                shift_cols.append(f'{shift}班績效%')
                
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce')

        if '合計績效%' not in df.columns or df['合計績效%'].isnull().all():
            df['合計績效%'] = np.where(df['合計實際耗用'] > 0, (df['合計理論耗用'] / df['合計實際耗用']) * 100, np.nan)
        
        df['Δ耗用 (Deviation)'] = df['合計實際耗用'] - df['合計理論耗用']
        df['Sort_Group'] = df['塗料編號'].apply(lambda x: 'GE00_01_Group' if any(g in str(x) for g in ['GE00', 'GE01']) else str(x))

        # ==========================================
        # [ COLOR MAP & GRADE ] 
        # ==========================================
        conds_global = [
            df['合計績效%'] < 80, 
            (df['合計績效%'] >= 80) & (df['合計績效%'] < 90), 
            (df['合計績效%'] >= 90) & (df['合計績效%'] < 100), 
            (df['合計績效%'] >= 100) & (df['合計績效%'] <= 110),
            df['合計績效%'] > 110
        ]
        labels_global = ['🔴 < 80%', '🟠 80% - 90%', '🟢 90% - 100%', '🌱 100% - 110%', '🔵 > 110%']
        perf_color_map = {
            '🔴 < 80%': '#990000', '🟠 80% - 90%': '#FF8C00', '🟢 90% - 100%': '#008000',
            '🌱 100% - 110%': '#ADFF2F', '🔵 > 110%': '#00008B'
        }
        df['績效等級'] = np.select(conds_global, labels_global, default='未知')

        # ==========================================
        # 🔥 [VIEW SWITCH] - CHỌN VIEW 1 HOẶC VIEW 2
        # ==========================================
        st.sidebar.markdown("---")
        st.sidebar.header("🎯 [模式切換] 分析視角")
        view_mode = st.sidebar.radio("請選擇分析視角：", ["View 1: 全體分析 (All Items)", "View 2: 嚴重超耗分析 (Δ耗用 > 200)"], index=0)

        if "View 2" in view_mode:
            df_active = df[df['Δ耗用 (Deviation)'] > 200].copy()
            st.sidebar.warning(f"目前顯示: View 2 (共 {len(df_active)} 支超耗塗料)")
        else:
            df_active = df.copy()

        # ==========================================
        # [ 2. DASHBOARD FILTER ]
        # ==========================================
        st.sidebar.header("🔍 [2] 篩選控制台")
        available_months = sorted(df_active['年月'].unique(), reverse=True)
        sel_month = st.sidebar.multiselect("1. 選擇年月", options=available_months, default=available_months[:1])
        df_s1 = df_active[df_active['年月'].isin(sel_month)]
        
        sel_line = st.sidebar.multiselect("2. 選擇線別", options=sorted(df_s1['線別'].unique()), default=df_s1['線別'].unique())
        df_s2 = df_s1[df_s1['線別'].isin(sel_line)]
        
        sel_usage = st.sidebar.multiselect("3. 選擇用途", options=sorted(df_s2['用途'].unique()), default=df_s2['用途'].unique())
        filtered_df = df_s2[df_s2['用途'].isin(sel_usage)]

        # ==========================================
        # [ 3. VISUALIZATION ]
        # ==========================================
        st.markdown(f"### 📈 視覺化分析與根因探討 ({view_mode})")
        
        sort_order = filtered_df.sort_values(by=['Sort_Group', '塗料編號'])['塗料編號'].unique().tolist()
        total_paints = len(sort_order)
        items_per_chart = 40
        num_charts = math.ceil(total_paints / items_per_chart) if items_per_chart else 0

        tab_overview, tab_pareto, tab_rootcause, tab_scatter, tab_bar, tab_dev = st.tabs([
            "🍩 [總覽] 績效分佈", "🚨 [決策] 優先改善清單", "📦 [根因] 穩定度分析", 
            "🎯 [全景] 績效燈號", "📊 [明細] 耗用對比", "📉 [明細] 差異分析"
        ])

        common_layout = dict(
            plot_bgcolor='white',
            font=dict(color='black', family='Arial', size=13, weight='bold'),
            yaxis=dict(showline=True, linewidth=2, linecolor='black', mirror=True, gridcolor='#e6e6e6', title_font=dict(weight='bold'))
        )

        with tab_overview:
            st.subheader("1. 產線整體績效總覽與行動清單")
            if not filtered_df.empty:
                k1, k2, k3 = st.columns(3)
                avg_perf = filtered_df['合計績效%'].mean()
                total_delta = filtered_df['Δ耗用 (Deviation)'].sum()
                k1.metric("平均總績效 (理論值基準)", f"{avg_perf:.2f}%")
                k2.metric("總差異耗用 (實際 - 理論)", f"{total_delta:,.0f}", delta_color="inverse")
                k3.metric("分析區間內塗料總數", f"{total_paints} 支")
            
            st.divider()
            col_pie, col_table = st.columns([4, 6])
            
            with col_pie:
                pie_df = filtered_df.dropna(subset=['合計績效%', '績效等級'])
                if not pie_df.empty:
                    pie_counts = pie_df['績效等級'].value_counts().reset_index()
                    pie_counts.columns = ['績效等級', '塗料數量']
                    fig_pie = px.pie(
                        pie_counts, values='塗料數量', names='績效等級', color='績效等級',
                        color_discrete_map=perf_color_map, hole=0.4,
                        category_orders={"績效等級": labels_global}
                    )
                    fig_pie.update_traces(textposition='inside', textinfo='percent+label+value', marker=dict(line=dict(color='black', width=2)), textfont_size=14)
                    fig_pie.update_layout(title="<b>塗料績效等級比例 (Performance Distribution)</b>", showlegend=True, font=dict(weight='bold', color='black'))
                    st.plotly_chart(fig_pie, use_container_width=True)
            
            with col_table:
                st.markdown("##### 🚨 Top 10 嚴重超耗塗料清單 (Top 10 Over-consumption)")
                over_used_df = filtered_df[filtered_df['Δ耗用 (Deviation)'] > 200].copy()
                if not over_used_df.empty:
                    decision_table = over_used_df.sort_values(by='Δ耗用 (Deviation)', ascending=False).head(10)
                    show_cols = ['塗料編號', '油漆廠商', '線別', '合計績效%', 'Δ耗用 (Deviation)']
                    decision_table = decision_table[show_cols]
                    decision_table.columns = ['塗料編號 (Paint ID)', '油漆廠商 (Supplier)', '線別 (Line)', '合計績效 (%)', '🔥 超耗量 (Over-used)']
                    st.dataframe(decision_table.style.format({'合計績效 (%)': '{:.2f}%', '🔥 超耗量 (Over-used)': '{:,.0f}'}), use_container_width=True, hide_index=True)
                else:
                    st.success("🎉 目前無超耗塗料！")

        with tab_pareto:
            st.subheader("2. 異常超耗柏拉圖 (Pareto Priority)")
            pareto_df = filtered_df[filtered_df['Δ耗用 (Deviation)'] > 0].groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index()
            if not pareto_df.empty:
                pareto_df = pareto_df.sort_values(by='Δ耗用 (Deviation)', ascending=False)
                pareto_df['累計%'] = pareto_df['Δ耗用 (Deviation)'].cumsum() / pareto_df['Δ耗用 (Deviation)'].sum() * 100
                top_pareto = pareto_df.head(20)
                fig_pareto = go.Figure()
                fig_pareto.add_trace(go.Bar(x=top_pareto['塗料編號'], y=top_pareto['Δ耗用 (Deviation)'], name='超耗量 (Over-used)', marker_color='#990000'))
                fig_pareto.add_trace(go.Scatter(x=top_pareto['塗料編號'], y=top_pareto['累計%'], name='累計% (Cumulative %)', yaxis='y2', line=dict(color='#00008B', width=3)))
                
                fig_pareto.update_layout(**common_layout)
                fig_pareto.update_layout(
                    xaxis=dict(title=dict(text="<b>塗料編號 (Paint ID)</b>", standoff=40), tickangle=-90, automargin=True, showline=True, linewidth=2, linecolor='black', mirror=True),
                    yaxis=dict(title="<b>超耗量 (Over-used Volume)</b>"),
                    yaxis2=dict(title="<b>累計% (Cumulative %)</b>", overlaying='y', side='right', range=[0, 105], showline=True, linewidth=2, linecolor='black'),
                    height=650, title="<b>Top 20 成本流失最大塗料排行 (Top 20 Highest Cost Loss)</b>",
                    showlegend=True, margin=dict(b=160)
                )
                st.plotly_chart(fig_pareto, use_container_width=True)

        with tab_rootcause:
            st.subheader("3. 穩定度分析 (Stability Analysis)")
            col1, col2 = st.columns(2)
            NO_RED_PALETTE = ['#1f77b4', '#ff7f0e', '#2ca02c', '#9467bd', '#8c564b', '#7f7f7f', '#bcbd22', '#17becf']
            with col1:
                if '油漆廠商' in filtered_df.columns and not filtered_df.empty:
                    fig_box1 = px.box(filtered_df, x='油漆廠商', y='合計績效%', color='油漆廠商', points="all", hover_data=['塗料編號'], color_discrete_sequence=NO_RED_PALETTE)
                    fig_box1.add_hline(y=100, line_dash="dash", line_color="red", line_width=3)
                    fig_box1.add_hline(y=90, line_dash="dot", line_color="deepskyblue", line_width=2)
                    fig_box1.add_hline(y=110, line_dash="dot", line_color="deepskyblue", line_width=2)
                    fig_box1.add_annotation(x=1, y=100, xref="paper", yref="y", text="<b>🎯 Target: 100%</b>", showarrow=False, xanchor="right", yanchor="bottom", font=dict(color="red", size=14, weight="bold"))
                    
                    fig_box1.update_layout(**common_layout)
                    fig_box1.update_layout(height=550, title="<b>供應商品質穩定度 (Supplier QC)</b>", 
                                           xaxis=dict(title="<b>油漆廠商 (Supplier)</b>", showline=True, linewidth=2, linecolor='black', mirror=True, title_font=dict(weight='bold')), 
                                           yaxis_title="<b>合計績效 (%)</b>", showlegend=False)
                    st.plotly_chart(fig_box1, use_container_width=True)
            with col2:
                if shift_cols:
                    shift_df = pd.melt(filtered_df, id_vars=['塗料編號'], value_vars=shift_cols, var_name='班別', value_name='績效%').dropna(subset=['績效%'])
                    shift_df['班別'] = shift_df['班別'].str.replace('班績效%', '班')
                    if not shift_df.empty:
                        fig_box2 = px.box(shift_df, x='班別', y='績效%', color='班別', points="all", hover_data=['塗料編號'], color_discrete_sequence=NO_RED_PALETTE)
                        fig_box2.add_hline(y=100, line_dash="dash", line_color="red", line_width=3)
                        fig_box2.add_hline(y=90, line_dash="dot", line_color="deepskyblue", line_width=2)
                        fig_box2.add_hline(y=110, line_dash="dot", line_color="deepskyblue", line_width=2)
                        fig_box2.add_annotation(x=1, y=100, xref="paper", yref="y", text="<b>🎯 Target: 100%</b>", showarrow=False, xanchor="right", yanchor="bottom", font=dict(color="red", size=14, weight="bold"))
                        
                        fig_box2.update_layout(**common_layout)
                        fig_box2.update_layout(height=550, title="<b>班別操作穩定度 (Shift Operations)</b>", 
                                               xaxis=dict(title="<b>班別 (Shift)</b>", showline=True, linewidth=2, linecolor='black', mirror=True, title_font=dict(weight='bold')), 
                                               yaxis_title="<b>績效 (%)</b>", showlegend=False)
                        st.plotly_chart(fig_box2, use_container_width=True)

        with tab_scatter:
            st.subheader(f"4. 塗料績效燈號全景總覽 (共 {total_paints} 支)")
            
            st.info("""
            💡 **圖表說明 (How to read this chart):**
            * **X軸 (X-Axis):** 塗料排序序號 (Paint Sequence No.).
            * **Y軸 (Y-Axis):** 合計績效 (Total Performance %). 
            * **圓點大小 (Bubble Size):** 代表「合計理論耗用」量 (Theoretical Consumption). 圓點越大，系統設定上的預期耗用量越高.
            * **基準線 (Reference Lines):** 🎯 **Target (100%)** 為紅虛線；**90% & 110%** 為深天藍色點線.
            * 🚨 **Top 5 改善名單:** 系統會自動找出耗損最大的5支塗料，並在右側列出明細。
            """)
            
            if not filtered_df.empty:
                plot_df = filtered_df.dropna(subset=['合計理論耗用', '合計績效%']).copy()
                plot_df = plot_df[plot_df['合計理論耗用'] > 0] 
                if not plot_df.empty:
                    seq_map = {code: i+1 for i, code in enumerate(sort_order)}
                    plot_df['塗料序號'] = plot_df['塗料編號'].map(seq_map)
                    
                    fig = px.scatter(
                        plot_df, x='塗料序號', y='合計績效%', color='績效等級',
                        color_discrete_map=perf_color_map,
                        size='合計理論耗用', size_max=30,
                        category_orders={"績效等級": labels_global},
                        hover_name='塗料編號'
                    )

                    top5_dev = plot_df.sort_values(by='Δ耗用 (Deviation)', ascending=False).head(5)
                    
                    # 1. Vẽ mũi tên chỉ vào Top 5
                    for rank, (_, row) in enumerate(top5_dev.iterrows(), start=1):
                        fig.add_annotation(
                            x=row['塗料序號'],       
                            y=row['合計績效%'],       
                            text=f"🚨 Top {rank}",  
                            showarrow=True,          
                            arrowhead=3,             
                            arrowsize=1.5,           
                            arrowwidth=2,            
                            arrowcolor="#990000",    
                            ax=0,                    
                            ay=-45,                  
                            font=dict(color="#990000", size=11, weight="bold"),
                            bgcolor="rgba(255, 255, 255, 0.85)", 
                            bordercolor="#990000",   
                            borderwidth=1,
                            borderpad=3
                        )
                    
                    # 2. Tạo bảng danh sách Top 5 bên phải (nhúng thẳng vào Plotly)
                    top5_text = "<span style='color:#990000; font-size:14px'><b>🚨 Top 5<br>改善名單</b></span><br><br>"
                    for rank, (_, row) in enumerate(top5_dev.iterrows(), start=1):
                        top5_text += f"<span style='font-size:12px; color:#333'><b>Top {rank}</b></span><br>"
                        top5_text += f"<span style='font-size:11px; color:#000'>{row['塗料編號']}</span><br>"
                        top5_text += f"<span style='font-size:12px; color:#990000'><b>Δ {row['Δ耗用 (Deviation)']:,.0f}</b></span><br><br>"
                    
                    top5_text = top5_text[:-8] # Cắt bỏ 2 thẻ <br> thừa ở cuối cùng

                    fig.add_annotation(
                        x=1.015, y=0.75,  # Đặt tọa độ X sang bên phải, Y tụt xuống 1 chút so với Legend
                        xref="paper", yref="paper",
                        xanchor="left", yanchor="top",
                        text=top5_text,
                        showarrow=False,
                        align="left",
                        bgcolor="#f9fbfd",
                        bordercolor="#e6e6e6",
                        borderwidth=1,
                        borderpad=10
                    )

                    y_min = plot_df['合計績效%'].min() - 5
                    y_max = max(120, plot_df['合計績效%'].max() + 5)
                    fig.update_yaxes(range=[y_min, y_max])

                    fig.add_hline(y=100, line_dash="dash", line_color="red", line_width=3)
                    fig.add_hline(y=90, line_dash="dot", line_color="deepskyblue", line_width=2)
                    fig.add_hline(y=110, line_dash="dot", line_color="deepskyblue", line_width=2)
                    
                    fig.add_annotation(x=0.99, y=100, xref="paper", yref="y", text="<b>🎯 Target: 100%</b>", showarrow=False, xanchor="right", yanchor="bottom", yshift=8, font=dict(color="red", size=16, weight="bold"), bgcolor="rgba(255,255,255,0.7)")
                    fig.add_annotation(x=0.99, y=90, xref="paper", yref="y", text="<b>90% Bound</b>", showarrow=False, xanchor="right", yanchor="top", yshift=-5, font=dict(color="deepskyblue", size=13, weight="bold"), bgcolor="rgba(255,255,255,0.7)")
                    fig.add_annotation(x=0.99, y=110, xref="paper", yref="y", text="<b>110% Bound</b>", showarrow=False, xanchor="right", yanchor="bottom", yshift=5, font=dict(color="deepskyblue", size=13, weight="bold"), bgcolor="rgba(255,255,255,0.7)")

                    fig.update_layout(**common_layout)
                    fig.update_layout(
                        height=700, 
                        title="<b>全廠塗料績效分佈圖 (Overall Performance Scatter)</b>",
                        xaxis=dict(title=f"<b>塗料排序序號 (Paint Sequence No.) - 總計: {total_paints} 支 (Total Items)</b>", showline=True, linewidth=2, linecolor='black', mirror=True, title_font=dict(weight='bold')),
                        yaxis_title="<b>合計績效 (%)</b>",
                        margin=dict(r=150) # Tăng lề phải để chứa vừa bảng Top 5
                    )
                    fig.update_traces(marker=dict(line=dict(width=1, color='black')))
                    
                    # In duy nhất một biểu đồ (bảng danh sách đã nằm gọn bên trong biểu đồ)
                    st.plotly_chart(fig, use_container_width=True)

        with tab_bar:
            st.subheader("5. 單一塗料：理論耗用 vs 實際耗用明細")
            for i in range(num_charts):
                start_idx = i * items_per_chart
                current_batch = sort_order[start_idx : start_idx + items_per_chart]
                batch_df = filtered_df[filtered_df['塗料編號'].isin(current_batch)]
                df_bar = batch_df.groupby('塗料編號')[['合計理論耗用', '合計實際耗用']].sum().reset_index()
                fig_bar = go.Figure()
                fig_bar.add_trace(go.Bar(x=df_bar['塗料編號'], y=df_bar['合計理論耗用'], name='理論 (Theoretical)', marker_color='#34495e', marker_line_color='black', marker_line_width=1.5))
                fig_bar.add_trace(go.Bar(x=df_bar['塗料編號'], y=df_bar['合計實際耗用'], name='實際 (Actual)', marker_color='#3498db', marker_line_color='black', marker_line_width=1.5))
                
                fig_bar.update_layout(**common_layout)
                fig_bar.update_layout(
                    barmode='group', height=550, 
                    title=f"<b>第 {i+1} 組耗用對比 (Group {i+1} Comparison)</b>", 
                    xaxis=dict(title=dict(text="<b>塗料編號 (Paint ID)</b>", standoff=40), tickangle=-90, automargin=True, showline=True, linewidth=2, linecolor='black', mirror=True),
                    yaxis=dict(title="<b>耗用量 (Consumption)</b>"),
                    margin=dict(b=160)
                )
                st.plotly_chart(fig_bar, use_container_width=True)

        with tab_dev:
            st.subheader("6. 單一塗料：耗用差異絕對值")
            for i in range(num_charts):
                start_idx = i * items_per_chart
                current_batch = sort_order[start_idx : start_idx + items_per_chart]
                batch_df = filtered_df[filtered_df['塗料編號'].isin(current_batch)]
                df_dev = batch_df.groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index()
                df_dev['Color'] = np.where(df_dev['Δ耗用 (Deviation)'] > 0, '超耗 (Over)', '節省 (Save)')
                
                fig_dev = px.bar(df_dev, x='塗料編號', y='Δ耗用 (Deviation)', color='Color', color_discrete_map={'超耗 (Over)': '#990000', '節省 (Save)': '#008000'})
                fig_dev.add_hline(y=0, line_color="black", line_width=2)
                
                fig_dev.update_layout(**common_layout)
                fig_dev.update_layout(
                    height=550, 
                    title=f"<b>第 {i+1} 組差異明細 (Group {i+1} Deviation)</b>", 
                    xaxis=dict(title=dict(text="<b>塗料編號 (Paint ID)</b>", standoff=40), tickangle=-90, automargin=True, showline=True, linewidth=2, linecolor='black', mirror=True),
                    yaxis=dict(title="<b>差異量 (Deviation)</b>"),
                    margin=dict(b=160)
                )
                fig_dev.update_traces(marker=dict(line=dict(width=1.5, color='black')))
                st.plotly_chart(fig_dev, use_container_width=True)

        with st.expander("🔍 檢視底層明細資料 (Raw Data View)"):
            st.dataframe(filtered_df)

        # ==========================================
        # [ 4. EXPORT REPORT TO HTML ] 
        # ==========================================
        st.sidebar.markdown("---")
        st.sidebar.header("📥 [4] 快速匯出報表 (HTML Export)")
        
        report_view_sel = st.sidebar.radio(
            "選擇報表內容 (Select Report Content):",
            ["View 1: All Items", "View 2: Deviation > 200"]
        )
        
        if st.sidebar.button("📄 產生 HTML 報表 (Generate Report)"):
            try:
                latest_month = df['年月'].dropna().max()
                target_usages = ['正面漆', '背面漆'] 
                df_word = df[(df['用途'].isin(target_usages)) & (df['年月'] == latest_month)].copy()
                
                if "View 2" in report_view_sel:
                    df_word = df_word[df_word['Δ耗用 (Deviation)'] > 150]
                    report_title_suffix = "(Deviation > 200)"
                else:
                    report_title_suffix = "(Full Report)"

                if df_word.empty:
                    st.sidebar.error("❌ 找不到最新月份數據。(No data for the latest month)")
                else:
                    lines = sorted(df_word['線別'].unique())
                    html_content = f"""
                    <html>
                    <head>
                        <meta charset='UTF-8'>
                        <title>Performance Report</title>
                        <style>
                            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 20px; background-color: #f4f7f6; }}
                            .container {{ background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); max-width: 1200px; margin: auto; }}
                            h1 {{ color: #2c3e50; text-align: center; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
                            h2 {{ color: #e67e22; margin-top: 50px; border-bottom: 1px dashed #ccc; padding-bottom: 5px; }}
                            h3 {{ color: #34495e; margin-top: 30px; }}
                            
                            .keep-together {{
                                page-break-inside: avoid;
                                break-inside: avoid;
                                margin-bottom: 20px;
                            }}

                            .styled-table {{ border-collapse: collapse; margin: 25px 0; font-size: 0.9em; font-family: sans-serif; width: 100%; box-shadow: 0 0 20px rgba(0, 0, 0, 0.15); }}
                            .styled-table thead tr {{ background-color: #009879; color: #ffffff; text-align: center; }}
                            .styled-table th, .styled-table td {{ padding: 12px 15px; border: 1px solid #ddd; text-align: center; }}
                            .styled-table tbody tr {{ border-bottom: 1px solid #dddddd; }}
                            .styled-table tbody tr:nth-of-type(even) {{ background-color: #f3f3f3; }}
                            .styled-table tbody tr:last-of-type {{ border-bottom: 2px solid #009879; }}
                        </style>
                    </head>
                    <body>
                    <div class="container">
                        <h1>📊 塗料生產績效報告 - {latest_month} {report_title_suffix}</h1>
                    """
                    
                    for line in lines:
                        html_content += f"<h2>🏭 線別 (Line): {line}</h2>"
                        df_line = df_word[df_word['線別'] == line].copy()
                        
                        sort_order_line = df_line.sort_values(by=['Sort_Group', '塗料編號'])['塗料編號'].unique().tolist()
                        total_paints_line = len(sort_order_line)
                        
                        # --- 1. SCATTER PLOT (Export Version) ---
                        plot_df_line = df_line.dropna(subset=['合計理論耗用', '合計績效%']).copy()
                        plot_df_line = plot_df_line[plot_df_line['合計理論耗用'] > 0]
                        if not plot_df_line.empty:
                            seq_map_line = {code: i+1 for i, code in enumerate(sort_order_line)}
                            plot_df_line['塗料序號'] = plot_df_line['塗料編號'].map(seq_map_line)
                            
                            fig_line = px.scatter(
                                plot_df_line, x='塗料序號', y='合計績效%', color='績效等級',
                                symbol='用途', 
                                hover_data={'用途': True, '合計績效%': True}, 
                                color_discrete_map=perf_color_map, size='合計理論耗用', size_max=30,
                                category_orders={"績效等級": labels_global}, hover_name='塗料編號'
                            )

                            top5_dev_line = plot_df_line.sort_values(by='Δ耗用 (Deviation)', ascending=False).head(5)
                            for rank, (_, row) in enumerate(top5_dev_line.iterrows(), start=1):
                                fig_line.add_annotation(
                                    x=row['塗料序號'],       
                                    y=row['合計績效%'],       
                                    text=f"🚨 Top {rank}",  
                                    showarrow=True,          
                                    arrowhead=3,             
                                    arrowsize=1.5,           
                                    arrowwidth=2,            
                                    arrowcolor="#990000",    
                                    ax=0,                    
                                    ay=-45,                  
                                    font=dict(color="#990000", size=11, weight="bold"),
                                    bgcolor="rgba(255, 255, 255, 0.85)", 
                                    bordercolor="#990000",   
                                    borderwidth=1,
                                    borderpad=3
                                )
                            
                            # Nhúng bảng Top 5 vào biểu đồ trong Export HTML
                            top5_text_exp = "<span style='color:#990000; font-size:14px'><b>🚨 Top 5<br>改善名單</b></span><br><br>"
                            for rank, (_, row) in enumerate(top5_dev_line.iterrows(), start=1):
                                top5_text_exp += f"<span style='font-size:12px; color:#333'><b>Top {rank}</b></span><br>"
                                top5_text_exp += f"<span style='font-size:11px; color:#000'>{row['塗料編號']}</span><br>"
                                top5_text_exp += f"<span style='font-size:12px; color:#990000'><b>Δ {row['Δ耗用 (Deviation)']:,.0f}</b></span><br><br>"
                            
                            top5_text_exp = top5_text_exp[:-8]

                            fig_line.add_annotation(
                                x=1.015, y=0.75,
                                xref="paper", yref="paper",
                                xanchor="left", yanchor="top",
                                text=top5_text_exp,
                                showarrow=False,
                                align="left",
                                bgcolor="#f9fbfd",
                                bordercolor="#e6e6e6",
                                borderwidth=1,
                                borderpad=10
                            )

                            y_min_exp = plot_df_line['合計績效%'].min() - 5
                            y_max_exp = max(120, plot_df_line['合計績效%'].max() + 5)
                            fig_line.update_yaxes(range=[y_min_exp, y_max_exp])
                            
                            fig_line.add_hline(y=100, line_dash="dash", line_color="red", line_width=3)
                            fig_line.add_hline(y=90, line_dash="dot", line_color="deepskyblue", line_width=2)
                            fig_line.add_hline(y=110, line_dash="dot", line_color="deepskyblue", line_width=2)
                            
                            fig_line.add_annotation(x=0.99, y=100, xref="paper", yref="y", text="<b>🎯 Target: 100%</b>", showarrow=False, xanchor="right", yanchor="bottom", yshift=8, font=dict(color="red", size=16, weight="bold"), bgcolor="rgba(255,255,255,0.7)")
                            fig_line.add_annotation(x=0.99, y=90, xref="paper", yref="y", text="<b>90% Bound</b>", showarrow=False, xanchor="right", yanchor="top", yshift=-5, font=dict(color="deepskyblue", size=13, weight="bold"), bgcolor="rgba(255,255,255,0.7)")
                            fig_line.add_annotation(x=0.99, y=110, xref="paper", yref="y", text="<b>110% Bound</b>", showarrow=False, xanchor="right", yanchor="bottom", yshift=5, font=dict(color="deepskyblue", size=13, weight="bold"), bgcolor="rgba(255,255,255,0.7)")
                            
                            fig_line.update_layout(**common_layout)
                            fig_line.update_layout(
                                height=700,
                                title=f"<b>Line {line} 績效概覽 (Performance Overview)</b>",
                                xaxis=dict(title=f"<b>塗料排序序號 (Paint Sequence No.) - 總計: {total_paints_line} 支 (Total Items)</b>", showline=True, linewidth=2, linecolor='black', mirror=True, title_font=dict(weight='bold')), 
                                yaxis_title="<b>合計績效 (%)</b>",
                                margin=dict(r=150)
                            )
                            fig_line.update_traces(marker=dict(line=dict(width=1, color='black')))
                            
                            html_content += "<div class='keep-together'>"
                            html_content += fig_line.to_html(full_html=False, include_plotlyjs='cdn')
                            html_content += "</div>"
                        
                        # --- 2. PARETO CHART (Export Version) ---
                        html_content += "<div class='keep-together'>"
                        html_content += f"<h3>🚨 異常超耗柏拉圖 (Pareto Priority)</h3>"
                        pareto_df_exp = df_line[df_line['Δ耗用 (Deviation)'] > 0].groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index()
                        if not pareto_df_exp.empty:
                            pareto_df_exp = pareto_df_exp.sort_values(by='Δ耗用 (Deviation)', ascending=False)
                            pareto_df_exp['累計%'] = pareto_df_exp['Δ耗用 (Deviation)'].cumsum() / pareto_df_exp['Δ耗用 (Deviation)'].sum() * 100
                            top_pareto_exp = pareto_df_exp.head(20)
                            
                            fig_pareto_exp = go.Figure()
                            fig_pareto_exp.add_trace(go.Bar(x=top_pareto_exp['塗料編號'], y=top_pareto_exp['Δ耗用 (Deviation)'], name='超耗量 (Over-used)', marker_color='#990000'))
                            fig_pareto_exp.add_trace(go.Scatter(x=top_pareto_exp['塗料編號'], y=top_pareto_exp['累計%'], name='累計% (Cumulative %)', yaxis='y2', line=dict(color='#00008B', width=3)))
                            
                            fig_pareto_exp.update_layout(**common_layout)
                            fig_pareto_exp.update_layout(
                                xaxis=dict(title=dict(text="<b>塗料編號 (Paint ID)</b>", standoff=40), tickangle=-90, automargin=True, showline=True, linewidth=2, linecolor='black', mirror=True),
                                yaxis=dict(title="<b>超耗量 (Over-used Volume)</b>"),
                                yaxis2=dict(title="<b>累計% (Cumulative %)</b>", overlaying='y', side='right', range=[0, 105], showline=True, linewidth=2, linecolor='black'),
                                height=650, title=f"<b>Line {line} - Top 20 成本流失最大塗料排行 (Top 20 Highest Cost Loss)</b>",
                                showlegend=True, margin=dict(b=160)
                            )
                            html_content += fig_pareto_exp.to_html(full_html=False, include_plotlyjs='cdn')
                            html_content += "</div>"
                        else:
                            html_content += "<p style='color:green; font-weight:bold;'>🎉 目前無超耗塗料！ (No over-consumption for this line)</p>"
                            html_content += "</div>"

                        # --- 3. TOP 10 TABLE (Export Version) ---
                        html_content += "<div class='keep-together'>"
                        html_content += f"<h3>📋 Top 10 嚴重超耗塗料清單 (Top 10 Over-consumption Table)</h3>"
                        over_used_df_line = df_line[df_line['Δ耗用 (Deviation)'] > 200].copy()
                        if not over_used_df_line.empty:
                            top10_table = over_used_df_line.sort_values(by='Δ耗用 (Deviation)', ascending=False).head(10)
                            show_cols = ['塗料編號', '用途', '油漆廠商', '線別', '合計績效%', 'Δ耗用 (Deviation)']
                            top10_table = top10_table[show_cols]
                            top10_table.columns = ['塗料編號 (Paint ID)', '用途 (Usage)', '油漆廠商 (Supplier)', '線別 (Line)', '合計績效 (%)', '🔥 超耗量 (Over-used)']
                            
                            top10_table['合計績效 (%)'] = top10_table['合計績效 (%)'].apply(lambda x: f"{x:.2f}%")
                            top10_table['🔥 超耗量 (Over-used)'] = top10_table['🔥 超耗量 (Over-used)'].apply(lambda x: f"{x:,.0f}")
                            
                            html_table = top10_table.to_html(index=False, classes='styled-table', escape=False)
                            html_content += html_table
                            html_content += "</div>"
                        else:
                            html_content += "<p style='color:green; font-weight:bold;'>🎉 目前無超耗塗料！ (No over-consumption for this line)</p>"
                            html_content += "</div>"
                        
                    html_content += "</div></body></html>"
                    st.sidebar.download_button("📥 下載報表 (Download HTML)", data=html_content.encode('utf-8'), file_name=f"Report_{latest_month}.html", mime="text/html")
            except Exception as e:
                st.sidebar.error(f"Error: {e}")

    except Exception as e:
        st.error(f"System Error：{e}")
else:
    st.info("👈 請上傳 MES 數據檔案。(Please upload MES Data file)")

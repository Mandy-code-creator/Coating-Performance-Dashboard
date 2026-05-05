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
.stPlotlyChart { border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); background-color: white; overflow: hidden; }
[data-testid="stKPIs"] div{ border: 1px solid #e6e6e6; border-radius: 8px; padding: 10px; background-color: #f9fbfd; }
.chart-note { background-color: #fff3cd; padding: 15px; border-radius: 5px; border-left: 5px solid #ffc107; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

st.title("📊 塗料生產績效與耗用分析儀表板")
st.markdown("<b>依據 MES/Excel 數據進行系統化分析 (高階決策最佳化佈局)</b>", unsafe_allow_html=True)

# ==========================================
# [ FUNCTIONS FOR SYNCING DESIGN ] 
# ==========================================
def create_scatter_chart(data, title, paints_order):
    if data.empty: return None
    plot_df = data[data['合計理論耗用'] > 0].copy()
    if plot_df.empty: return None
    
    seq_map = {code: i+1 for i, code in enumerate(paints_order)}
    plot_df['塗料序號'] = plot_df['塗料編號'].map(seq_map)
    
    fig = px.scatter(plot_df, x='塗料序號', y='合計績效%', color='績效等級',
                     color_discrete_map=perf_color_map, size='合計理論耗用', size_max=30,
                     category_orders={"績效等級": labels_global}, hover_name='塗料編號')
    
    # Cố định Y-axis 120 và Label không bị đè
    fig.update_yaxes(range=[max(0, plot_df['合計績效%'].min() - 10), 120])
    fig.add_hline(y=100, line_dash="dash", line_color="red", line_width=3)
    fig.add_hline(y=90, line_dash="dot", line_color="deepskyblue", line_width=2)
    fig.add_hline(y=110, line_dash="dot", line_color="deepskyblue", line_width=2)
    
    fig.add_annotation(x=0.99, y=100, xref="paper", yref="y", text="<b>🎯 Target: 100%</b>", showarrow=False, xanchor="right", yanchor="bottom", yshift=8, bgcolor="rgba(255,255,255,0.8)", font=dict(color="red", size=14))
    fig.add_annotation(x=0.99, y=110, xref="paper", yref="y", text="<b>110% Bound</b>", showarrow=False, xanchor="right", yanchor="bottom", yshift=5, bgcolor="rgba(255,255,255,0.8)", font=dict(color="deepskyblue", size=12))
    
    fig.update_layout(plot_bgcolor='white', font=dict(color='black', family='Arial', weight='bold'), height=700, title=f"<b>{title}</b>")
    fig.update_xaxes(showline=True, linewidth=2, linecolor='black', mirror=True)
    fig.update_traces(marker=dict(line=dict(width=1, color='black')))
    return fig

def create_pareto_chart(data, title):
    pareto_df = data[data['Δ耗用 (Deviation)'] > 0].groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index().sort_values(by='Δ耗用 (Deviation)', ascending=False)
    if pareto_df.empty: return None
    
    pareto_df['累計%'] = pareto_df['Δ耗用 (Deviation)'].cumsum() / pareto_df['Δ耗用 (Deviation)'].sum() * 100
    top_p = pareto_df.head(40)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(x=top_p['塗料編號'], y=top_p['Δ耗用 (Deviation)'], marker_color='#990000', name='Over-used'))
    fig.add_trace(go.Scatter(x=top_p['塗料編號'], y=top_p['累計%'], yaxis='y2', line=dict(color='#00008B', width=3), name='Cumulative %'))
    
    fig.update_layout(
        plot_bgcolor='white', height=650, title=f"<b>{title}</b>",
        yaxis=dict(title="<b>Over-used (kg)</b>", showline=True, linewidth=2, linecolor='black'),
        yaxis2=dict(title="<b>Cumulative %</b>", overlaying='y', side='right', range=[0, 105], showline=True, linewidth=2, linecolor='black'),
        font=dict(color='black', family='Arial', weight='bold')
    )
    fig.update_xaxes(tickangle=-90, showline=True, linewidth=2, linecolor='black')
    return fig

# ==========================================
# [ 1. DATA SOURCE & DATA LOAD ]
# ==========================================
st.sidebar.header("📂 [1] Data Load")
uploaded_file = st.sidebar.file_uploader("Upload File", type=['csv', 'xlsx'])

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file, encoding='utf-8-sig', dtype=str) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file, dtype=str)
        df.columns = df.columns.str.strip()
        df = df.dropna(how='all')
        
        if '線別' in df.columns:
            df['線別'] = df['線別'].astype(str).str.strip()
            df = df[(df['線別'] != '線別') & (df['線別'] != 'nan') & (df['線別'] != '')]

        for col in ['線別', '塗料編號', '用途', '年月', '油漆廠商']:
            if col in df.columns: df[col] = df[col].fillna('Unknown').astype(str).str.strip()

        numeric_cols = ['合計理論耗用', '合計實際耗用', '合計績效%']
        for shift in ['A', 'B', 'C', 'D']: numeric_cols.extend([f'{shift}班理論耗用', f'{shift}班實際耗用', f'{shift}班績效%'])
        for col in numeric_cols:
            if col in df.columns: df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

        df['Δ耗用 (Deviation)'] = df['合計實際耗用'] - df['合計理論耗用']
        if '合計績效%' not in df.columns or df['合計績效%'].sum() == 0:
            df['合計績效%'] = np.where(df['合計實際耗用'] > 0, (df['合計理論耗用'] / df['合計實際耗用']) * 100, 0)
        df['Sort_Group'] = df['塗料編號'].apply(lambda x: 'GE00_01_Group' if any(g in str(x) for g in ['GE00', 'GE01']) else str(x))

        labels_global = ['🔴 < 80%', '🟠 80% - 90%', '🟢 90% - 100%', '🌱 100% - 110%', '🔵 > 110%']
        perf_color_map = {'🔴 < 80%': '#990000', '🟠 80% - 90%': '#FF8C00', '🟢 90% - 100%': '#008000', '🌱 100% - 110%': '#ADFF2F', '🔵 > 110%': '#00008B'}
        conds = [df['合計績效%'] < 80, (df['合計績效%'] < 90), (df['合計績效%'] < 100), (df['合計績效%'] <= 110), df['合計績效%'] > 110]
        df['績效等級'] = np.select(conds, labels_global, default='未知')

        # ==========================================
        # 🔥 [VIEW SWITCH] - PHÂN TÁCH VIEW 1 VÀ VIEW 2
        # ==========================================
        st.sidebar.markdown("---")
        st.sidebar.header("🎯 [2] Analysis View")
        view_mode = st.sidebar.radio("Select Mode:", ["View 1: All Items", "View 2: Deviation > 500"])
        df_active = df[df['Δ耗用 (Deviation)'] >= 500].copy() if "View 2" in view_mode else df.copy()

        available_months = sorted(df_active['年月'].unique(), reverse=True)
        sel_month = st.sidebar.multiselect("Select Month", options=available_months, default=available_months[:1])
        df_filtered = df_active[df_active['年月'].isin(sel_month)]
        sel_line = st.sidebar.multiselect("Select Line", options=sorted(df_filtered['線別'].unique()), default=df_filtered['線別'].unique())
        filtered_df = df_filtered[df_filtered['線別'].isin(sel_line)]

        # ==========================================
        # [ 3. VISUALIZATION ]
        # ==========================================
        st.markdown(f"### 📈 Performance Analysis ({view_mode})")
        sort_order = filtered_df.sort_values(by=['Sort_Group', '塗料編號'])['塗料編號'].unique().tolist()
        
        tab1, tab2, tab3 = st.tabs(["📊 Performance Map", "🚨 Pareto Analysis", "📋 Raw Data"])

        with tab1:
            fig_sc = create_scatter_chart(filtered_df, "Overall Performance Map", sort_order)
            if fig_sc: 
                st.plotly_chart(fig_sc, use_container_width=True)
                
                # 🔥 CHÚ THÍCH CỤ THỂ CHO SẾP (LEGEND EXPLANATION)
                st.markdown("""
                <div class='chart-note'>
                    <b>💡 Legend Interpretation:</b><br>
                    1. <b>Dot Size (Bubble):</b> Represents <b>Theoretical Consumption (合計理論耗用)</b>. <br>
                    &nbsp;&nbsp;&nbsp; - <i>Large Dots:</i> High volume items (Priority items). Errors here lead to significant cost loss.<br>
                    &nbsp;&nbsp;&nbsp; - <i>Small Dots:</i> Low volume items.<br>
                    2. <b>Dot Color:</b> Represents <b>Performance Level</b> (Red is critical).<br>
                    3. <b>Y-Axis:</b> Total Performance % (Target is 100%).
                </div>
                """, unsafe_allow_html=True)

        with tab2:
            fig_pa = create_pareto_chart(filtered_df, "Over-consumption Pareto")
            if fig_pa: st.plotly_chart(fig_pa, use_container_width=True)

        with tab3:
            st.dataframe(filtered_df.sort_values(by='Δ耗用 (Deviation)', ascending=False), use_container_width=True)

        # ==========================================
        # [ 4. HTML EXPORT ] - MIRRORING APP 100%
        # ==========================================
        st.sidebar.markdown("---")
        st.sidebar.header("📥 [3] Report Export")
        export_mode = st.sidebar.radio("Export Data Choice:", ["Export View 1 (All)", "Export View 2 (>500)"])
        
        if st.sidebar.button("📄 Generate HTML Report"):
            df_html_source = df[df['Δ耗用 (Deviation)'] >= 500].copy() if "View 2" in export_mode else df.copy()
            latest_month = df_html_source['年月'].max()
            df_html = df_html_source[(df_html_source['用途'] == '正面漆') & (df_html_source['年月'] == latest_month)].copy()
            
            html_content = f"""
            <html><head><meta charset='UTF-8'><style>
                body {{ font-family: Segoe UI, sans-serif; padding: 20px; background: #f4f7f6; }}
                .container {{ background: white; padding: 30px; border-radius: 10px; max-width: 1200px; margin: auto; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }}
                h1 {{ text-align: center; color: #2c3e50; border-bottom: 2px solid #3498db; }}
                .legend-box {{ background: #fff3cd; padding: 15px; border-radius: 5px; border-left: 5px solid #ffc107; margin: 20px 0; font-size: 0.9em; }}
                .styled-table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                .styled-table thead tr {{ background-color: #009879; color: white; }}
                .styled-table th, .styled-table td {{ padding: 12px; border: 1px solid #ddd; text-align: center; }}
            </style></head><body><div class='container'>
                <h1>📊 Paint Production Performance Report - {latest_month}</h1>
                <div class='legend-box'>
                    <b>Legend Note:</b><br>
                    - <b>Bubble Size:</b> Theoretical Consumption (Larger = Higher priority/volume).<br>
                    - <b>Colors:</b> Performance level (Red < 80%, Green 90-100%, Blue > 110%).<br>
                    - <b>Report Mode:</b> {export_mode}
                </div>
            """
            for line in sorted(df_html['線別'].unique()):
                df_line = df_html[df_html['線別'] == line].copy()
                order_line = df_line.sort_values(by=['Sort_Group', '塗料編號'])['塗料編號'].unique().tolist()
                
                html_content += f"<h2>🏭 Line: {line}</h2>"
                fig1 = create_scatter_chart(df_line, f"Line {line} Performance Map", order_line)
                if fig1: html_content += fig1.to_html(full_html=False, include_plotlyjs='cdn')
                
                fig2 = create_pareto_chart(df_line, f"Line {line} Pareto Analysis")
                if fig2: html_content += fig2.to_html(full_html=False, include_plotlyjs='cdn')

                html_content += "<h3>📋 Top 10 Over-consumption</h3><table class='styled-table'><thead><tr><th>ID</th><th>Supplier</th><th>Perf %</th><th>Over (kg)</th></tr></thead><tbody>"
                for _, row in df_line.sort_values(by='Δ耗用 (Deviation)', ascending=False).head(10).iterrows():
                    html_content += f"<tr><td>{row['塗料編號']}</td><td>{row['油漆廠商']}</td><td>{row['合計績效%']:.2f}%</td><td>{row['Δ耗用 (Deviation)']:,.0f}</td></tr>"
                html_content += "</tbody></table>"

            html_content += "</div></body></html>"
            st.sidebar.download_button("📥 Download Report", data=html_content.encode('utf-8'), file_name=f"Report_{latest_month}.html", mime="text/html")

    except Exception as e:
        st.error(f"System Error: {e}")
else:
    st.info("👈 Please upload MES data file to begin.")

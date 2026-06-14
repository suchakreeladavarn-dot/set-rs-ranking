# -*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import os
import sys

# Ensure current directory is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import rs_ranking

# Configure Streamlit page layout
st.set_page_config(
    page_title="Stan Weinstein RS Ranking Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium styling to match the dark theme of the HTML report
st.markdown("""
<style>
    /* Force page background to match the dark theme */
    .stApp {
        background-color: #090d16 !important;
        background-image: 
            radial-gradient(at 0% 0%, rgba(29, 78, 216, 0.15) 0px, transparent 50%),
            radial-gradient(at 50% 0%, rgba(76, 29, 149, 0.1) 0px, transparent 50%),
            radial-gradient(at 100% 100%, rgba(17, 24, 39, 0.8) 0px, transparent 50%) !important;
        background-attachment: fixed !important;
        color: #f3f4f6 !important;
    }
    
    /* Force sidebar background to be dark */
    section[data-testid="stSidebar"] {
        background-color: #111827 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
    }
    
    /* Make text in main app and sidebar white/light-grey */
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, .stApp p, .stApp span, .stApp label, .stApp li {
        color: #f3f4f6 !important;
    }
    
    /* Markdown text container */
    div[data-testid="stMarkdownContainer"] {
        color: #f3f4f6 !important;
    }
    
    /* Sidebar text color overrides */
    section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] p,
    section[data-testid="stSidebar"] label {
        color: #e5e7eb !important;
    }

    /* Style the header card */
    .app-header {
        font-family: 'Outfit', sans-serif;
        background: rgba(22, 30, 49, 0.6) !important;
        backdrop-filter: blur(12px) !important;
        padding: 2rem;
        border-radius: 20px;
        margin-bottom: 2rem;
        box-shadow: 0 10px 25px rgba(0,0,0,0.3);
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        background-image: 
            radial-gradient(at 0% 0%, rgba(29, 78, 216, 0.2) 0px, transparent 50%),
            radial-gradient(at 100% 100%, rgba(17, 24, 39, 0.6) 0px, transparent 50%) !important;
    }
    .app-header h1 {
        margin: 0 !important;
        font-size: 2.2rem !important;
        font-weight: 800 !important;
        background: linear-gradient(135deg, #ffffff 30%, #a5b4fc 100%) !important;
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
    }
    .app-header p {
        margin: 0.5rem 0 0 0 !important;
        font-size: 1rem !important;
        color: #9ca3af !important;
    }

    /* Inputs fields styling */
    input[type="text"], input[type="number"], select {
        background-color: rgba(17, 24, 39, 0.8) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
    }
    
    /* Make dropdown select boxes dark */
    div[data-baseweb="select"] > div {
        background-color: rgba(17, 24, 39, 0.8) !important;
        color: white !important;
        border-color: rgba(255, 255, 255, 0.15) !important;
    }
    
    /* Dropdown options list styling */
    ul[role="listbox"] {
        background-color: #111827 !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
    }
    
    ul[role="listbox"] li:hover {
        background-color: rgba(59, 130, 246, 0.2) !important;
    }

    /* Style the file uploader widget */
    section[data-testid="stFileUploader"] {
        background-color: rgba(17, 24, 39, 0.4) !important;
        border: 1px dashed rgba(255, 255, 255, 0.1) !important;
        border-radius: 12px !important;
        padding: 1rem !important;
    }

    /* Action Buttons styling */
    .stButton>button {
        background: linear-gradient(135deg, #3b82f6, #8b5cf6) !important;
        color: white !important;
        font-weight: 600 !important;
        border: none !important;
        padding: 0.6rem 2.5rem !important;
        border-radius: 12px !important;
        transition: all 0.3s !important;
        box-shadow: 0 4px 15px rgba(59, 130, 246, 0.3) !important;
        width: 100%;
    }
    .stButton>button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(59, 130, 246, 0.5) !important;
    }
    
    /* Download buttons (secondary buttons styling) */
    .stDownloadButton>button {
        background: rgba(255, 255, 255, 0.05) !important;
        color: #f3f4f6 !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        padding: 0.4rem 1.2rem !important;
        border-radius: 8px !important;
        transition: all 0.2s !important;
    }
    .stDownloadButton>button:hover {
        background: rgba(255, 255, 255, 0.1) !important;
        border-color: rgba(59, 130, 246, 0.4) !important;
        color: white !important;
    }
    
    /* Divider styling */
    hr {
        border-color: rgba(255, 255, 255, 0.08) !important;
    }
</style>
""", unsafe_allow_html=True)
# App Title Area
st.markdown("""
<div class="app-header">
    <h1>📈 Stan Weinstein RS Ranking Dashboard</h1>
    <p>Real-time stock relative strength scanning and ranking tool using Mansfield Relative Strength (RS) to screen for Stage 2 breakout stocks.</p>
</div>
""", unsafe_allow_html=True)

# Sidebar Configuration
st.sidebar.markdown("### ⚙️ Scan Configuration")

benchmark = st.sidebar.text_input(
    "Benchmark Ticker",
    value="^SET.BK",
    help="e.g. ^SET.BK (Thai SET Index), ^GSPC (S&P 500 Index)"
).strip()

ma_length = st.sidebar.number_input(
    "Moving Average Period",
    min_value=10,
    max_value=300,
    value=200,
    step=10,
    help="Period length for calculating Mansfield RS moving average (Default is 200 bars/weeks, or 30 weeks in Stan Weinstein's original setup)"
)

min_mcap = st.sidebar.number_input(
    "Min Market Cap (M Baht)",
    min_value=0.0,
    value=0.0,
    step=500.0,
    help="Filters out stocks with market cap below this threshold in Million Baht (Set to 0 to disable filter)"
)

# Stock Source Selection
st.sidebar.markdown("### 📋 Stock List Source")
stock_source_type = st.sidebar.selectbox(
    "Select Stock List:",
    ["Use Default List (709 Stocks)", "Upload Custom CSV File"]
)

stock_source = "set_stocks.csv"
uploaded_file = None

if stock_source_type == "Upload Custom CSV File":
    uploaded_file = st.sidebar.file_uploader(
        "Upload CSV file containing stock symbols",
        type=["csv"],
        help="CSV file must have a column header like 'symbol', 'Ticker', or 'SYMBOL' containing stock tickers."
    )
    if uploaded_file is not None:
        try:
            df_uploaded = pd.read_csv(uploaded_file)
            stock_source = df_uploaded
            st.sidebar.success(f"Successfully uploaded! Found {len(df_uploaded)} rows.")
        except Exception as e:
            st.sidebar.error(f"Error reading file: {str(e)}")
            stock_source = None
    else:
        st.sidebar.warning("Please upload a CSV file or choose the default list.")
        stock_source = None

# Action Area
st.markdown("### 🔍 Execution")
col_btn, col_info = st.columns([1, 3])

with col_btn:
    analyze_button = st.button("🚀 Start RS Ranking Scan")

output_filename = "rs_ranking_report.html"

# Run calculation if button is clicked
if analyze_button:
    if stock_source is None:
        st.error("Please prepare a valid stock list source before scanning.")
    else:
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        
        def update_progress(message, percent):
            status_text.markdown(f"**Calculation Status:** {message}")
            progress_bar.progress(percent)
            
        with st.spinner("Scanning and downloading data in progress..."):
            try:
                success, result = rs_ranking.run_scan(
                    stock_source=stock_source,
                    benchmark=benchmark,
                    ma_length=ma_length,
                    min_mcap=min_mcap,
                    output_path=output_filename,
                    progress_callback=update_progress
                )
                
                if success:
                    st.success("Calculations and scanning completed successfully!")
                    st.balloons()
                else:
                    st.error(f"Scan failed: {result}")
            except Exception as e:
                st.error(f"An error occurred during analysis: {str(e)}")
                st.info("Tip: Please check if the Benchmark symbol is correct or if your CSV file is formatted properly.")

# Render Area: Load and show report if it exists
if os.path.exists(output_filename):
    st.markdown("---")
    st.markdown("### 📊 Latest RS Ranking Report")
    
    # Download Button
    try:
        with open(output_filename, "r", encoding="utf-8") as f:
            html_content = f.read()
            
        st.download_button(
            label="📥 Download HTML Report File",
            data=html_content,
            file_name="rs_ranking_report.html",
            mime="text/html"
        )
        
        # Embed the generated HTML without an inner iframe scrollbar
        components.html(html_content, height=1350, scrolling=False)
    except Exception as e:
        st.error(f"Could not load the report file for rendering: {str(e)}")
else:
    st.info("No report data available yet. Please click the button above to start your first stock scan.")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #6b7280; font-size: 0.85rem; padding: 1rem 0;">
    Stan Weinstein Mansfield RS Web Dashboard • Real-time data powered by Yahoo Finance • Access reports anytime, anywhere.
</div>
""", unsafe_allow_html=True)

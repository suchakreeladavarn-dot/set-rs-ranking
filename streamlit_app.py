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
    page_title="Stan Weinstein RS Ranking",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium styling to make the iframe cover the entire screen
st.markdown("""
<style>
    /* Hide Streamlit top header and bottom footer */
    header[data-testid="stHeader"] {
        display: none !important;
    }
    footer {
        display: none !important;
    }
    
    /* Make page take full width and height with zero padding */
    .stApp {
        background-color: #090d16 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    
    /* Remove padding of main block container to allow full-screen iframe */
    [data-testid="stAppViewBlockContainer"] {
        padding: 0 !important;
        margin: 0 !important;
        max-width: 100vw !important;
        height: 100vh !important;
        overflow: hidden !important;
    }
    
    /* Force the iframe and its container to occupy full screen */
    iframe {
        width: 100vw !important;
        height: 100vh !important;
        border: none !important;
        margin: 0 !important;
        padding: 0 !important;
        display: block !important;
    }
    div[data-testid="stHtml"] {
        height: 100vh !important;
    }
    
    /* Style the sidebar to look premium */
    section[data-testid="stSidebar"] {
        background-color: #111827 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
    }
    
    /* Ensure all sidebar labels and headings are readable */
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        color: #f3f4f6 !important;
    }
    
    /* Style buttons in sidebar */
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
        margin-top: 1rem !important;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(59, 130, 246, 0.5) !important;
    }

    .stDownloadButton>button {
        background: rgba(255, 255, 255, 0.05) !important;
        color: #f3f4f6 !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        padding: 0.5rem 1.2rem !important;
        border-radius: 8px !important;
        transition: all 0.2s !important;
        width: 100% !important;
        margin-top: 0.5rem !important;
    }
    
    .stDownloadButton>button:hover {
        background: rgba(255, 255, 255, 0.1) !important;
        border-color: rgba(59, 130, 246, 0.4) !important;
        color: white !important;
    }
    
    /* Style the file uploader widget in sidebar */
    section[data-testid="stFileUploader"] {
        background-color: rgba(17, 24, 39, 0.4) !important;
        border: 1px dashed rgba(255, 255, 255, 0.1) !important;
        border-radius: 12px !important;
        padding: 0.75rem !important;
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
    
    /* Divider styling */
    hr {
        border-color: rgba(255, 255, 255, 0.08) !important;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar Header & Controls
st.sidebar.markdown("""
<div style="text-align: center; margin-bottom: 1.5rem; margin-top: -1rem;">
    <h2 style="color: white; font-family: 'Outfit', sans-serif; font-weight: 800; margin-bottom: 0.1rem; font-size: 1.6rem;">📈 RS Scanner</h2>
    <p style="color: #9ca3af; font-size: 0.8rem; margin: 0;">Stan Weinstein Relative Strength</p>
</div>
""", unsafe_allow_html=True)

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

st.sidebar.markdown("---")

# Execution Area inside Sidebar
st.sidebar.markdown("### 🔍 Execution")
analyze_button = st.sidebar.button("🚀 Start RS Ranking Scan")

output_filename = "rs_ranking_report.html"

# Run calculation if button is clicked
if analyze_button:
    if stock_source is None:
        st.sidebar.error("Please prepare a valid stock list source before scanning.")
    else:
        progress_bar = st.sidebar.progress(0.0)
        status_text = st.sidebar.empty()
        
        def update_progress(message, percent):
            status_text.markdown(f"**Status:** {message}")
            progress_bar.progress(percent)
            
        with st.sidebar.spinner("Scanning in progress..."):
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
                    st.sidebar.success("Scanning completed successfully!")
                    st.balloons()
                else:
                    st.sidebar.error(f"Scan failed: {result}")
            except Exception as e:
                st.sidebar.error(f"Error: {str(e)}")

# Download Button inside Sidebar if report exists
if os.path.exists(output_filename):
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📥 Export Report")
    try:
        with open(output_filename, "r", encoding="utf-8") as f:
            html_content = f.read()
            
        st.sidebar.download_button(
            label="📥 Download HTML Report",
            data=html_content,
            file_name="rs_ranking_report.html",
            mime="text/html"
        )
    except Exception as e:
        st.sidebar.error(f"Error: {str(e)}")

# Render Area: Load and show report as full screen in the main panel
if os.path.exists(output_filename):
    try:
        with open(output_filename, "r", encoding="utf-8") as f:
            html_content = f.read()
        # Embed the generated HTML with 100% viewport coverage
        components.html(html_content, scrolling=True)
    except Exception as e:
        st.write(f"Error loading report: {str(e)}")
else:
    st.write("No report data available yet. Please use the sidebar to start your first stock scan.")

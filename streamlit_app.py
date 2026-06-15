# -*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components
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
    initial_sidebar_state="collapsed"
)

# Custom premium styling to make the iframe cover the entire screen and place the floating Scan button
st.markdown("""
<style>
    /* Hide Streamlit top header and bottom footer */
    header[data-testid="stHeader"] {
        display: none !important;
    }
    footer {
        display: none !important;
    }
    
    /* Hide sidebar completely */
    section[data-testid="stSidebar"] {
        display: none !important;
    }
    button[data-testid="stSidebarCollapseButton"] {
        display: none !important;
    }
    
    /* Lock html, body, and all Streamlit main containers from scrolling and match background gradient exactly */
    html, body, .stApp, div[data-testid="stAppViewContainer"], div[data-testid="stAppViewBlockContainer"] {
        overflow: hidden !important;
        height: 100vh !important;
        width: 100vw !important;
        margin: 0 !important;
        padding: 0 !important;
        background-color: #090d16 !important;
        background-image: 
            radial-gradient(at 0% 0%, rgba(29, 78, 216, 0.15) 0px, transparent 50%),
            radial-gradient(at 50% 0%, rgba(76, 29, 149, 0.1) 0px, transparent 50%),
            radial-gradient(at 100% 100%, rgba(17, 24, 39, 0.8) 0px, transparent 50%) !important;
        background-attachment: fixed !important;
        -ms-overflow-style: none !important;  /* IE and Edge */
        scrollbar-width: none !important;  /* Firefox */
    }
    
    /* Hide scrollbars for Chrome, Safari and Opera */
    ::-webkit-scrollbar {
        display: none !important;
    }
    
    /* Force the iframe to occupy full screen, positioned absolutely to the viewport */
    iframe {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
        border: none !important;
        margin: 0 !important;
        padding: 0 !important;
        display: block !important;
        z-index: 1 !important;
    }
    
    iframe::-webkit-scrollbar {
        display: none !important;
    }
    
    /* Make sure Streamlit wrapper HTML block doesn't add padding or overflow */
    div[data-testid="stHtml"] {
        height: 100vh !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    
    /* Style the Scan button to float at the top-right of the screen and stay completely fixed */
    div.stButton {
        position: fixed !important;
        top: 1.5rem !important;
        right: 2rem !important;
        z-index: 999999 !important;
        margin: 0 !important;
        padding: 0 !important;
        width: auto !important;
    }
    
    div.stButton > button {
        background: linear-gradient(135deg, #3b82f6, #8b5cf6) !important;
        color: white !important;
        font-weight: 600 !important;
        border: none !important;
        padding: 0.5rem 1.2rem !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 15px rgba(59, 130, 246, 0.3) !important;
        width: auto !important;
        cursor: pointer !important;
        transition: all 0.2s !important;
        font-size: 0.85rem !important;
    }
    
    div.stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(59, 130, 246, 0.5) !important;
    }
</style>
""", unsafe_allow_html=True)

# Default configuration parameters
benchmark = "^SET.BK"
ma_length = 200
min_mcap = 0.0
stock_source = "set_stocks.csv"
output_filename = "rs_ranking_report.html"

# Check if scan query parameter is set to trigger a new calculation
if "scan" in st.query_params:
    # Remove parameter to prevent infinite loop on page refresh
    st.query_params.pop("scan")
    
    # Use toast notifications to show progress cleanly on full-screen app
    def update_progress(message, percent):
        st.toast(f"⏳ {message} ({int(percent * 100)}%)")
        
    try:
        st.toast("🚀 Initiating stock scan...")
        success, result = rs_ranking.run_scan(
            stock_source=stock_source,
            benchmark=benchmark,
            ma_length=ma_length,
            min_mcap=min_mcap,
            output_path=output_filename,
            progress_callback=update_progress
        )
        
        if success:
            st.toast("✅ Scanning completed successfully!")
            st.balloons()
            st.rerun()  # Force Streamlit to rerun and refresh the iframe content
        else:
            st.toast(f"❌ Scan failed: {result}")
    except Exception as e:
        st.toast(f"❌ Error: {str(e)}")

# Render Area: Load and show report as full screen in the main panel
if os.path.exists(output_filename):
    # Render native Streamlit Scan button at the top right (floats over iframe)
    if st.button("🚀 Scan Now"):
        st.query_params["scan"] = "true"
        st.rerun()

    try:
        with open(output_filename, "r", encoding="utf-8") as f:
            html_content = f.read()
        # Embed the generated HTML with 100% viewport coverage
        components.html(html_content, scrolling=True)
    except Exception as e:
        st.write(f"Error loading report: {str(e)}")
else:
    st.write("No report data available yet.")
    if st.button("🚀 Start First Scan Now"):
        st.query_params["scan"] = "true"
        st.rerun()

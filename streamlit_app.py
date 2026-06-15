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
    
    /* Lock html, body, and all Streamlit main containers from scrolling to keep the layout static */
    html, body, .stApp, div[data-testid="stAppViewContainer"] {
        overflow: hidden !important;
        height: 100vh !important;
        width: 100vw !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    
    /* Make page take full width and height with zero padding */
    .stApp {
        background-color: #090d16 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    
    /* Set up main block container as a flex column to stack header row and iframe */
    [data-testid="stAppViewBlockContainer"] {
        padding: 0.5rem 1.5rem 0 1.5rem !important;
        margin: 0 !important;
        max-width: 100vw !important;
        height: 100vh !important;
        display: flex !important;
        flex-direction: column !important;
        overflow: hidden !important;
        gap: 0.5rem !important;
    }
    
    /* Force the iframe to occupy the remaining screen height, positioned in the flex flow */
    iframe {
        position: relative !important;
        width: 100% !important;
        height: calc(100vh - 65px) !important;
        border: none !important;
        margin: 0 !important;
        padding: 0 !important;
        display: block !important;
        z-index: 1 !important;
    }
    
    /* Make sure Streamlit wrapper divs don't block the layout */
    div[data-testid="stHtml"] {
        height: calc(100vh - 65px) !important;
    }
    
    /* Style the Scan button with the premium gradient design, positioned normally inside the header row */
    div.stButton {
        margin: 0 !important;
        padding: 0 !important;
        display: flex !important;
        justify-content: flex-end !important;
    }
    
    div.stButton > button {
        background: linear-gradient(135deg, #3b82f6, #8b5cf6) !important;
        color: white !important;
        font-weight: 600 !important;
        border: none !important;
        padding: 0.5rem 1.5rem !important;
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

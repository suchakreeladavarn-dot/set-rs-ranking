# -*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components
import os
import sys
import importlib
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import json

# Ensure current directory is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import rs_ranking
importlib.reload(rs_ranking)

def get_yfinance_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    })
    retries = Retry(total=5, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504, 429])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session


# Configure Streamlit page layout
st.set_page_config(
    page_title="Stan Weinstein RS Ranking",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

def show_pe_band_page(symbol):
    # Enable scrolling and override the custom full-screen css for this sub-page
    st.markdown("""
    <style>
        html, body, .stApp, div[data-testid="stAppViewContainer"], div[data-testid="stAppViewBlockContainer"] {
            overflow: auto !important;
            height: auto !important;
            width: auto !important;
            background-color: #090d16 !important;
        }
        
        /* Premium Back Button Style */
        div.back-btn-wrapper > button {
            background: rgba(30, 41, 59, 0.6) !important;
            color: #9ca3af !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            border-radius: 8px !important;
            padding: 0.5rem 1rem !important;
            font-weight: 500 !important;
            cursor: pointer !important;
            transition: all 0.2s !important;
        }
        div.back-btn-wrapper > button:hover {
            color: white !important;
            border-color: #3b82f6 !important;
            background: rgba(59, 130, 246, 0.1) !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # Header with Back button aligned nicely
    col_title, col_back = st.columns([4, 1])
    with col_title:
        st.title(f"📈 {symbol} Valuation PE Band (5 Years)")
    with col_back:
        st.write("<div class='back-btn-wrapper'>", unsafe_allow_html=True)
        if st.button("🔙 Back to Dashboard"):
            st.query_params.pop("pe_band", None)
            st.rerun()
        st.write("</div>", unsafe_allow_html=True)
        
    ticker = symbol + ".BK" if not symbol.endswith(".BK") else symbol
    
    with st.spinner(f"Fetching financial history for {ticker} from Yahoo Finance..."):
        try:
            session = get_yfinance_session()
            t_obj = yf.Ticker(ticker, session=session)
            
            # Fetch weekly prices
            prices_df = t_obj.history(period="5y", interval="1wk")
            if prices_df.empty:
                st.error(f"Could not find historical stock prices for {ticker}.")
                return
                
            prices = prices_df['Close']
            
            # Fetch annual financials
            eps_series = None
            try:
                annual_stmt = t_obj.income_stmt
                for idx in ['Diluted EPS', 'Basic EPS']:
                    if idx in annual_stmt.index:
                        eps_series = annual_stmt.loc[idx]
                        break
            except Exception:
                try:
                    annual_stmt = t_obj.financials
                    for idx in ['Diluted EPS', 'Basic EPS']:
                        if idx in annual_stmt.index:
                            eps_series = annual_stmt.loc[idx]
                            break
                except Exception:
                    pass
            
            # Use cached PE value from market_caps_cache.json to avoid rate limiting
            current_pe = None
            try:
                cache_file = "market_caps_cache.json"
                if os.path.exists(cache_file):
                    with open(cache_file, "r", encoding="utf-8") as f:
                        cache = json.load(f)
                        if symbol in cache:
                            current_pe = cache[symbol].get("pe_ttm")
            except Exception:
                pass
                
            current_price = prices.iloc[-1]
            
            fallback_eps = None
            if current_pe and current_pe > 0:
                fallback_eps = current_price / current_pe
                
            if eps_series is None or eps_series.isna().all():
                if fallback_eps:
                    eps_series = pd.Series([fallback_eps], index=[pd.Timestamp(datetime.now())])
                else:
                    eps_series = pd.Series([current_price / 15.0], index=[pd.Timestamp(datetime.now())])
            
            eps_series = eps_series.dropna()
            if eps_series.empty:
                if fallback_eps:
                    eps_series = pd.Series([fallback_eps], index=[pd.Timestamp(datetime.now())])
                else:
                    eps_series = pd.Series([current_price / 15.0], index=[pd.Timestamp(datetime.now())])
                    
            # Normalize all index datetimes to timezone-naive datetime64[ns] to avoid resolution (s, ms, us vs ns) and timezone mismatches.
            def to_naive_ns(index):
                dt_index = pd.to_datetime(index)
                if dt_index.tz is not None:
                    dt_index = dt_index.tz_localize(None)
                return dt_index.astype('datetime64[ns]')

            prices.index = to_naive_ns(prices.index)
                
            eps_chrono = eps_series.sort_index()
            eps_chrono.index = to_naive_ns(eps_chrono.index)
                
            today = pd.Timestamp(datetime.now())
            if today not in eps_chrono.index:
                today_eps = fallback_eps if fallback_eps is not None else eps_chrono.iloc[-1]
                eps_chrono[today] = today_eps
                
            # Re-normalize to naive ns in case pandas assignment altered index dtype/resolution
            eps_chrono = eps_chrono.sort_index()
            eps_chrono.index = to_naive_ns(eps_chrono.index)
            
            combined_index = eps_chrono.index.union(prices.index)
            eps_combined = eps_chrono.reindex(combined_index)
            eps_combined = eps_combined.interpolate(method='time').ffill().bfill()
            
            eps_weekly = eps_combined.reindex(prices.index)
            
            # Calculate weekly PE
            pe_weekly = prices / eps_weekly
            pe_weekly = pe_weekly.clip(lower=0, upper=200)
            
            # Calculate stats
            avg_pe = pe_weekly.mean()
            std_pe = pe_weekly.std()
            
            # SD lines
            pe_p2 = avg_pe + 2 * std_pe
            pe_p1 = avg_pe + std_pe
            pe_avg = avg_pe
            pe_m1 = avg_pe - std_pe
            pe_m2 = avg_pe - 2 * std_pe
            
            # Calculate current SD level
            curr_pe_val = current_pe if (current_pe is not None and current_pe > 0) else pe_weekly.iloc[-1]
            curr_sd_level = (curr_pe_val - avg_pe) / std_pe if std_pe > 0 else 0
            
            # Layout metrics
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Current Price", f"{current_price:.2f} THB")
            col2.metric("Current P/E", f"{curr_pe_val:.2f}x")
            col3.metric("5Y Average P/E", f"{avg_pe:.2f}x")
            col4.metric("5Y P/E Std Dev", f"{std_pe:.2f}")
            col5.metric("Current SD Level", f"{curr_sd_level:+.2f} SD")
            
            # Tabs for both P/E Band views
            tab1, tab2 = st.tabs(["📊 Price Chart with P/E Valuation Bands", "📉 P/E Ratio with Standard Deviation Lines"])
            
            with tab1:
                # Price vs PE multiples * EPS_t
                fig1 = go.Figure()
                fig1.add_trace(go.Scatter(x=prices.index, y=prices, name=f"Stock Price ({symbol})", line=dict(color="#ffffff", width=2)))
                fig1.add_trace(go.Scatter(x=prices.index, y=pe_p2 * eps_weekly, name=f"+2 SD Band ({pe_p2:.1f}x)", line=dict(color="#f87171", width=1, dash="dash")))
                fig1.add_trace(go.Scatter(x=prices.index, y=pe_p1 * eps_weekly, name=f"+1 SD Band ({pe_p1:.1f}x)", line=dict(color="#fb7185", width=1, dash="dash")))
                fig1.add_trace(go.Scatter(x=prices.index, y=pe_avg * eps_weekly, name=f"Average Band ({pe_avg:.1f}x)", line=dict(color="#94a3b8", width=1.5)))
                fig1.add_trace(go.Scatter(x=prices.index, y=pe_m1 * eps_weekly, name=f"-1 SD Band ({pe_m1:.1f}x)", line=dict(color="#34d399", width=1, dash="dash")))
                fig1.add_trace(go.Scatter(x=prices.index, y=pe_m2 * eps_weekly, name=f"-2 SD Band ({pe_m2:.1f}x)", line=dict(color="#10b981", width=1, dash="dash")))
                
                fig1.update_layout(
                    template="plotly_dark",
                    xaxis_title="Date",
                    yaxis_title="Stock Price (THB)",
                    plot_bgcolor="#090d16",
                    paper_bgcolor="#090d16",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig1, use_container_width=True)
                
            with tab2:
                # P/E ratio over time vs SD lines
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=pe_weekly.index, y=pe_weekly, name="Weekly P/E Ratio", line=dict(color="#3b82f6", width=2)))
                fig2.add_shape(type="line", x0=pe_weekly.index[0], y0=pe_p2, x1=pe_weekly.index[-1], y1=pe_p2, line=dict(color="#f87171", width=1, dash="dash"))
                fig2.add_shape(type="line", x0=pe_weekly.index[0], y0=pe_p1, x1=pe_weekly.index[-1], y1=pe_p1, line=dict(color="#fb7185", width=1, dash="dash"))
                fig2.add_shape(type="line", x0=pe_weekly.index[0], y0=pe_avg, x1=pe_weekly.index[-1], y1=pe_avg, line=dict(color="#94a3b8", width=1.5))
                fig2.add_shape(type="line", x0=pe_weekly.index[0], y0=pe_m1, x1=pe_weekly.index[-1], y1=pe_m1, line=dict(color="#34d399", width=1, dash="dash"))
                fig2.add_shape(type="line", x0=pe_weekly.index[0], y0=pe_m2, x1=pe_weekly.index[-1], y1=pe_m2, line=dict(color="#10b981", width=1, dash="dash"))
                
                # Annotate lines
                fig2.add_annotation(x=pe_weekly.index[-1], y=pe_p2, text=f"+2 SD ({pe_p2:.1f}x)", showarrow=False, xshift=10)
                fig2.add_annotation(x=pe_weekly.index[-1], y=pe_p1, text=f"+1 SD ({pe_p1:.1f}x)", showarrow=False, xshift=10)
                fig2.add_annotation(x=pe_weekly.index[-1], y=pe_avg, text=f"AVG ({pe_avg:.1f}x)", showarrow=False, xshift=10)
                fig2.add_annotation(x=pe_weekly.index[-1], y=pe_m1, text=f"-1 SD ({pe_m1:.1f}x)", showarrow=False, xshift=10)
                fig2.add_annotation(x=pe_weekly.index[-1], y=pe_m2, text=f"-2 SD ({pe_m2:.1f}x)", showarrow=False, xshift=10)
                
                fig2.update_layout(
                    template="plotly_dark",
                    xaxis_title="Date",
                    yaxis_title="P/E Multiple (x)",
                    plot_bgcolor="#090d16",
                    paper_bgcolor="#090d16",
                    showlegend=False
                )
                st.plotly_chart(fig2, use_container_width=True)
                
        except Exception as e:
            st.error(f"Error calculating P/E Band: {e}")

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

# Check if pe_band query parameter is set to show valuation bands
if "pe_band" in st.query_params:
    symbol = st.query_params["pe_band"]
    show_pe_band_page(symbol)
    st.stop()

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

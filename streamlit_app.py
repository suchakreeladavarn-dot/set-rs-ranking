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
            background-image: 
                radial-gradient(at 0% 0%, rgba(29, 78, 216, 0.15) 0px, transparent 50%),
                radial-gradient(at 50% 0%, rgba(76, 29, 149, 0.1) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(17, 24, 39, 0.8) 0px, transparent 50%) !important;
            background-attachment: fixed !important;
        }
        
        /* Force bright white text color for readability */
        h1, h2, h3, h4, h5, h6, .stMarkdown, p, li, span {
            color: #ffffff !important;
        }
        
        /* Target metric value text and labels */
        div[data-testid="stMetricValue"], div[data-testid="stMetricValue"] > div {
            color: #ffffff !important;
            font-weight: 700 !important;
        }
        div[data-testid="stMetricLabel"] p {
            color: #94a3b8 !important; /* slightly softer white/grey for labels */
        }
        
        /* Style Streamlit Tabs headers */
        button[data-baseweb="tab"] p {
            color: #ffffff !important;
        }
        
        /* Premium Back Button Style */
        div.back-btn-wrapper > button {
            background: rgba(30, 41, 59, 0.6) !important;
            color: #ffffff !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
            border-radius: 8px !important;
            padding: 0.5rem 1rem !important;
            font-weight: 600 !important;
            cursor: pointer !important;
            transition: all 0.2s !important;
        }
        div.back-btn-wrapper > button:hover {
            color: white !important;
            border-color: #3b82f6 !important;
            background: rgba(59, 130, 246, 0.2) !important;
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
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#ffffff"),
                    legend=dict(
                        orientation="h", 
                        yanchor="bottom", 
                        y=1.02, 
                        xanchor="right", 
                        x=1,
                        font=dict(color="#ffffff")
                    ),
                    yaxis=dict(
                        showgrid=False,
                        title_font=dict(color="#ffffff"),
                        tickfont=dict(color="#ffffff")
                    ),
                    xaxis=dict(
                        showgrid=False,
                        title_font=dict(color="#ffffff"),
                        tickfont=dict(color="#ffffff")
                    )
                )
                st.plotly_chart(fig1, use_container_width=True)
                
            with tab2:
                # P/E ratio over time vs SD lines
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=pe_weekly.index, y=pe_weekly, name="Weekly P/E Ratio", line=dict(color="#ffffff", width=2)))
                fig2.add_shape(type="line", x0=pe_weekly.index[0], y0=pe_p2, x1=pe_weekly.index[-1], y1=pe_p2, line=dict(color="#f87171", width=1, dash="dash"))
                fig2.add_shape(type="line", x0=pe_weekly.index[0], y0=pe_p1, x1=pe_weekly.index[-1], y1=pe_p1, line=dict(color="#fb7185", width=1, dash="dash"))
                fig2.add_shape(type="line", x0=pe_weekly.index[0], y0=pe_avg, x1=pe_weekly.index[-1], y1=pe_avg, line=dict(color="#94a3b8", width=1.5))
                fig2.add_shape(type="line", x0=pe_weekly.index[0], y0=pe_m1, x1=pe_weekly.index[-1], y1=pe_m1, line=dict(color="#34d399", width=1, dash="dash"))
                fig2.add_shape(type="line", x0=pe_weekly.index[0], y0=pe_m2, x1=pe_weekly.index[-1], y1=pe_m2, line=dict(color="#10b981", width=1, dash="dash"))
                
                # Annotate lines
                fig2.add_annotation(x=pe_weekly.index[-1], y=pe_p2, text=f"+2 SD ({pe_p2:.1f}x)", showarrow=False, xshift=10, font=dict(color="#ffffff"))
                fig2.add_annotation(x=pe_weekly.index[-1], y=pe_p1, text=f"+1 SD ({pe_p1:.1f}x)", showarrow=False, xshift=10, font=dict(color="#ffffff"))
                fig2.add_annotation(x=pe_weekly.index[-1], y=pe_avg, text=f"AVG ({pe_avg:.1f}x)", showarrow=False, xshift=10, font=dict(color="#ffffff"))
                fig2.add_annotation(x=pe_weekly.index[-1], y=pe_m1, text=f"-1 SD ({pe_m1:.1f}x)", showarrow=False, xshift=10, font=dict(color="#ffffff"))
                fig2.add_annotation(x=pe_weekly.index[-1], y=pe_m2, text=f"-2 SD ({pe_m2:.1f}x)", showarrow=False, xshift=10, font=dict(color="#ffffff"))
                
                fig2.update_layout(
                    template="plotly_dark",
                    xaxis_title="Date",
                    yaxis_title="P/E Multiple (x)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#ffffff"),
                    showlegend=False,
                    yaxis=dict(
                        showgrid=False,
                        title_font=dict(color="#ffffff"),
                        tickfont=dict(color="#ffffff")
                    ),
                    xaxis=dict(
                        showgrid=False,
                        title_font=dict(color="#ffffff"),
                        tickfont=dict(color="#ffffff")
                    )
                )
                st.plotly_chart(fig2, use_container_width=True)
                
        except Exception as e:
            st.error(f"Error calculating P/E Band: {e}")

def show_pbv_band_page(symbol):
    # Enable scrolling and override the custom full-screen css for this sub-page
    st.markdown("""
    <style>
        html, body, .stApp, div[data-testid="stAppViewContainer"], div[data-testid="stAppViewBlockContainer"] {
            overflow: auto !important;
            height: auto !important;
            width: auto !important;
            background-color: #090d16 !important;
            background-image: 
                radial-gradient(at 0% 0%, rgba(29, 78, 216, 0.15) 0px, transparent 50%),
                radial-gradient(at 50% 0%, rgba(76, 29, 149, 0.1) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(17, 24, 39, 0.8) 0px, transparent 50%) !important;
            background-attachment: fixed !important;
        }
        
        /* Force bright white text color for readability */
        h1, h2, h3, h4, h5, h6, .stMarkdown, p, li, span {
            color: #ffffff !important;
        }
        
        /* Target metric value text and labels */
        div[data-testid="stMetricValue"], div[data-testid="stMetricValue"] > div {
            color: #ffffff !important;
            font-weight: 700 !important;
        }
        div[data-testid="stMetricLabel"] p {
            color: #94a3b8 !important;
        }
        
        /* Style Streamlit Tabs headers */
        button[data-baseweb="tab"] p {
            color: #ffffff !important;
        }
        
        /* Premium Back Button Style */
        div.back-btn-wrapper > button {
            background: rgba(30, 41, 59, 0.6) !important;
            color: #ffffff !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
            border-radius: 8px !important;
            padding: 0.5rem 1rem !important;
            font-weight: 600 !important;
            cursor: pointer !important;
            transition: all 0.2s !important;
        }
        div.back-btn-wrapper > button:hover {
            color: white !important;
            border-color: #3b82f6 !important;
            background: rgba(59, 130, 246, 0.2) !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # Header with Back button aligned nicely
    col_title, col_back = st.columns([4, 1])
    with col_title:
        st.title(f"📈 {symbol} Valuation PBV Band (5 Years)")
    with col_back:
        st.write("<div class='back-btn-wrapper'>", unsafe_allow_html=True)
        if st.button("🔙 Back to Dashboard"):
            st.query_params.pop("pbv_band", None)
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
            
            # Fetch balance sheet financials to compute Book Value per Share (BVPS)
            bv_series = None
            try:
                bs = t_obj.balance_sheet
                equity_keys = ['Common Stock Equity', 'Stockholders Equity', 'Total Equity Gross Minority Interest', 'Tangible Book Value']
                equity = None
                for k in equity_keys:
                    if k in bs.index:
                        equity = bs.loc[k]
                        break
                
                shares_keys = ['Ordinary Shares Number', 'Share Issued']
                shares = None
                for k in shares_keys:
                    if k in bs.index:
                        shares = bs.loc[k]
                        break
                        
                if equity is not None and shares is not None:
                    bv_series = equity / shares
            except Exception:
                pass
            
            # Use cached PBV value from market_caps_cache.json to avoid rate limiting
            current_pbv = None
            try:
                cache_file = "market_caps_cache.json"
                if os.path.exists(cache_file):
                    with open(cache_file, "r", encoding="utf-8") as f:
                        cache = json.load(f)
                        if symbol in cache:
                            current_pbv = cache[symbol].get("pbv_latest")
            except Exception:
                pass
                
            current_price = prices.iloc[-1]
            
            fallback_bv = None
            if current_pbv and current_pbv > 0:
                fallback_bv = current_price / current_pbv
                
            if bv_series is None or bv_series.isna().all():
                if fallback_bv:
                    bv_series = pd.Series([fallback_bv], index=[pd.Timestamp(datetime.now())])
                else:
                    bv_series = pd.Series([current_price / 1.0], index=[pd.Timestamp(datetime.now())])
            
            bv_series = bv_series.dropna()
            if bv_series.empty:
                if fallback_bv:
                    bv_series = pd.Series([fallback_bv], index=[pd.Timestamp(datetime.now())])
                else:
                    bv_series = pd.Series([current_price / 1.0], index=[pd.Timestamp(datetime.now())])
                    
            # Normalize all index datetimes to timezone-naive datetime64[ns] to avoid resolution and timezone mismatches.
            def to_naive_ns(index):
                dt_index = pd.to_datetime(index)
                if dt_index.tz is not None:
                    dt_index = dt_index.tz_localize(None)
                return dt_index.astype('datetime64[ns]')

            prices.index = to_naive_ns(prices.index)
                
            bv_chrono = bv_series.sort_index()
            bv_chrono.index = to_naive_ns(bv_chrono.index)
                
            today = pd.Timestamp(datetime.now())
            if today not in bv_chrono.index:
                today_bv = fallback_bv if fallback_bv is not None else bv_chrono.iloc[-1]
                bv_chrono[today] = today_bv
                
            # Re-normalize to naive ns in case pandas assignment altered index dtype/resolution
            bv_chrono = bv_chrono.sort_index()
            bv_chrono.index = to_naive_ns(bv_chrono.index)
            
            combined_index = bv_chrono.index.union(prices.index)
            bv_combined = bv_chrono.reindex(combined_index)
            bv_combined = bv_combined.interpolate(method='time').ffill().bfill()
            
            bv_weekly = bv_combined.reindex(prices.index)
            
            # Calculate weekly PBV
            pbv_weekly = prices / bv_weekly
            pbv_weekly = pbv_weekly.clip(lower=0, upper=10)
            
            # Calculate stats
            avg_pbv = pbv_weekly.mean()
            std_pbv = pbv_weekly.std()
            
            # SD lines
            pbv_p2 = avg_pbv + 2 * std_pbv
            pbv_p1 = avg_pbv + std_pbv
            pbv_avg = avg_pbv
            pbv_m1 = avg_pbv - std_pbv
            pbv_m2 = avg_pbv - 2 * std_pbv
            
            # Calculate current SD level
            curr_pbv_val = current_pbv if (current_pbv is not None and current_pbv > 0) else pbv_weekly.iloc[-1]
            curr_sd_level = (curr_pbv_val - avg_pbv) / std_pbv if std_pbv > 0 else 0
            
            # Layout metrics
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Current Price", f"{current_price:.2f} THB")
            col2.metric("Current P/BV", f"{curr_pbv_val:.2f}x")
            col3.metric("5Y Average P/BV", f"{avg_pbv:.2f}x")
            col4.metric("5Y P/BV Std Dev", f"{std_pbv:.2f}")
            col5.metric("Current SD Level", f"{curr_sd_level:+.2f} SD")
            
            # Tabs for both P/BV Band views
            tab1, tab2 = st.tabs(["📊 Price Chart with P/BV Valuation Bands", "📉 P/BV Ratio with Standard Deviation Lines"])
            
            with tab1:
                # Price vs PBV multiples * BV_t
                fig1 = go.Figure()
                fig1.add_trace(go.Scatter(x=prices.index, y=prices, name=f"Stock Price ({symbol})", line=dict(color="#ffffff", width=2)))
                fig1.add_trace(go.Scatter(x=prices.index, y=pbv_p2 * bv_weekly, name=f"+2 SD Band ({pbv_p2:.1f}x)", line=dict(color="#f87171", width=1, dash="dash")))
                fig1.add_trace(go.Scatter(x=prices.index, y=pbv_p1 * bv_weekly, name=f"+1 SD Band ({pbv_p1:.1f}x)", line=dict(color="#fb7185", width=1, dash="dash")))
                fig1.add_trace(go.Scatter(x=prices.index, y=pbv_avg * bv_weekly, name=f"Average Band ({pbv_avg:.1f}x)", line=dict(color="#94a3b8", width=1.5)))
                fig1.add_trace(go.Scatter(x=prices.index, y=pbv_m1 * bv_weekly, name=f"-1 SD Band ({pbv_m1:.1f}x)", line=dict(color="#34d399", width=1, dash="dash")))
                fig1.add_trace(go.Scatter(x=prices.index, y=pbv_m2 * bv_weekly, name=f"-2 SD Band ({pbv_m2:.1f}x)", line=dict(color="#10b981", width=1, dash="dash")))
                
                fig1.update_layout(
                    template="plotly_dark",
                    xaxis_title="Date",
                    yaxis_title="Stock Price (THB)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#ffffff"),
                    legend=dict(
                        orientation="h", 
                        yanchor="bottom", 
                        y=1.02, 
                        xanchor="right", 
                        x=1,
                        font=dict(color="#ffffff")
                    ),
                    yaxis=dict(
                        showgrid=False,
                        title_font=dict(color="#ffffff"),
                        tickfont=dict(color="#ffffff")
                    ),
                    xaxis=dict(
                        showgrid=False,
                        title_font=dict(color="#ffffff"),
                        tickfont=dict(color="#ffffff")
                    )
                )
                st.plotly_chart(fig1, use_container_width=True)
                
            with tab2:
                # P/BV ratio over time vs SD lines
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=pbv_weekly.index, y=pbv_weekly, name="Weekly P/BV Ratio", line=dict(color="#ffffff", width=2)))
                fig2.add_shape(type="line", x0=pbv_weekly.index[0], y0=pbv_p2, x1=pbv_weekly.index[-1], y1=pbv_p2, line=dict(color="#f87171", width=1, dash="dash"))
                fig2.add_shape(type="line", x0=pbv_weekly.index[0], y0=pbv_p1, x1=pbv_weekly.index[-1], y1=pbv_p1, line=dict(color="#fb7185", width=1, dash="dash"))
                fig2.add_shape(type="line", x0=pbv_weekly.index[0], y0=pbv_avg, x1=pbv_weekly.index[-1], y1=pbv_avg, line=dict(color="#94a3b8", width=1.5))
                fig2.add_shape(type="line", x0=pbv_weekly.index[0], y0=pbv_m1, x1=pbv_weekly.index[-1], y1=pbv_m1, line=dict(color="#34d399", width=1, dash="dash"))
                fig2.add_shape(type="line", x0=pbv_weekly.index[0], y0=pbv_m2, x1=pbv_weekly.index[-1], y1=pbv_m2, line=dict(color="#10b981", width=1, dash="dash"))
                
                # Annotate lines
                fig2.add_annotation(x=pbv_weekly.index[-1], y=pbv_p2, text=f"+2 SD ({pbv_p2:.1f}x)", showarrow=False, xshift=10, font=dict(color="#ffffff"))
                fig2.add_annotation(x=pbv_weekly.index[-1], y=pbv_p1, text=f"+1 SD ({pbv_p1:.1f}x)", showarrow=False, xshift=10, font=dict(color="#ffffff"))
                fig2.add_annotation(x=pbv_weekly.index[-1], y=pbv_avg, text=f"AVG ({pbv_avg:.1f}x)", showarrow=False, xshift=10, font=dict(color="#ffffff"))
                fig2.add_annotation(x=pbv_weekly.index[-1], y=pbv_m1, text=f"-1 SD ({pbv_m1:.1f}x)", showarrow=False, xshift=10, font=dict(color="#ffffff"))
                fig2.add_annotation(x=pbv_weekly.index[-1], y=pbv_m2, text=f"-2 SD ({pbv_m2:.1f}x)", showarrow=False, xshift=10, font=dict(color="#ffffff"))
                
                fig2.update_layout(
                    template="plotly_dark",
                    xaxis_title="Date",
                    yaxis_title="P/BV Multiple (x)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#ffffff"),
                    showlegend=False,
                    yaxis=dict(
                        showgrid=False,
                        title_font=dict(color="#ffffff"),
                        tickfont=dict(color="#ffffff")
                    ),
                    xaxis=dict(
                        showgrid=False,
                        title_font=dict(color="#ffffff"),
                        tickfont=dict(color="#ffffff")
                    )
                )
                st.plotly_chart(fig2, use_container_width=True)
                
        except Exception as e:
            st.error(f"Error calculating P/BV Band: {e}")

def show_div_band_page(symbol):
    # Enable scrolling and override the custom full-screen css for this sub-page
    st.markdown("""
    <style>
        html, body, .stApp, div[data-testid="stAppViewContainer"], div[data-testid="stAppViewBlockContainer"] {
            overflow: auto !important;
            height: auto !important;
            width: auto !important;
            background-color: #090d16 !important;
            background-image: 
                radial-gradient(at 0% 0%, rgba(29, 78, 216, 0.15) 0px, transparent 50%),
                radial-gradient(at 50% 0%, rgba(76, 29, 149, 0.1) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(17, 24, 39, 0.8) 0px, transparent 50%) !important;
            background-attachment: fixed !important;
        }
        
        /* Force bright white text color for readability */
        h1, h2, h3, h4, h5, h6, .stMarkdown, p, li, span {
            color: #ffffff !important;
        }
        
        /* Target metric value text and labels */
        div[data-testid="stMetricValue"], div[data-testid="stMetricValue"] > div {
            color: #ffffff !important;
            font-weight: 700 !important;
        }
        div[data-testid="stMetricLabel"] p {
            color: #94a3b8 !important;
        }
        
        /* Style Streamlit Tabs headers */
        button[data-baseweb="tab"] p {
            color: #ffffff !important;
        }
        
        /* Premium Back Button Style */
        div.back-btn-wrapper > button {
            background: rgba(30, 41, 59, 0.6) !important;
            color: #ffffff !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
            border-radius: 8px !important;
            padding: 0.5rem 1rem !important;
            font-weight: 600 !important;
            cursor: pointer !important;
            transition: all 0.2s !important;
        }
        div.back-btn-wrapper > button:hover {
            color: white !important;
            border-color: #3b82f6 !important;
            background: rgba(59, 130, 246, 0.2) !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # Header with Back button aligned nicely
    col_title, col_back = st.columns([4, 1])
    with col_title:
        st.title(f"📈 {symbol} Dividend Yield Spread (5 Years)")
    with col_back:
        st.write("<div class='back-btn-wrapper'>", unsafe_allow_html=True)
        if st.button("🔙 Back to Dashboard"):
            st.query_params.pop("div_band", None)
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
            
            # Helper to normalize indexes to timezone-naive datetime64[ns]
            def to_naive_ns(index):
                dt_index = pd.to_datetime(index)
                if dt_index.tz is not None:
                    dt_index = dt_index.tz_localize(None)
                return dt_index.astype('datetime64[ns]')

            prices.index = to_naive_ns(prices.index)
            
            # Fetch dividends
            dividends = t_obj.dividends
            if dividends.empty:
                st.warning(f"Stock {symbol} has no dividend history available. Dividend Yield Spread valuation cannot be computed.")
                return
                
            dividends.index = to_naive_ns(dividends.index)
            
            # Calculate TTM dividends for each weekly date
            ttm_div = []
            for date in prices.index:
                start_date = date - pd.Timedelta(days=365)
                mask = (dividends.index > start_date) & (dividends.index <= date)
                ttm_sum = dividends[mask].sum()
                ttm_div.append(ttm_sum)
                
            ttm_div_series = pd.Series(ttm_div, index=prices.index)
            div_yield_weekly = (ttm_div_series / prices) * 100.0
            
            # Thai 10Y Government Bond yield series (interpolated historically)
            bond_dates = [
                '2020-01-01', '2020-12-31', '2021-12-31', '2022-12-31', 
                '2023-12-31', '2024-12-31', '2025-12-31', '2026-12-31'
            ]
            bond_yields = [
                1.47, 1.30, 2.25, 2.49, 
                2.69, 2.27, 1.59, 2.26
            ]
            bond_series = pd.Series(bond_yields, index=pd.to_datetime(bond_dates))
            bond_series.index = to_naive_ns(bond_series.index)
            
            combined_index = bond_series.index.union(prices.index)
            bond_combined = bond_series.reindex(combined_index).interpolate(method='time').ffill().bfill()
            bond_weekly = bond_combined.reindex(prices.index)
            
            # Calculate Yield Spread
            spread_weekly = div_yield_weekly - bond_weekly
            
            # Calculate spread statistics
            avg_spread = spread_weekly.mean()
            std_spread = spread_weekly.std()
            
            # SD levels
            spread_p2 = avg_spread + 2 * std_spread
            spread_p1 = avg_spread + std_spread
            spread_avg = avg_spread
            spread_m1 = avg_spread - std_spread
            spread_m2 = avg_spread - 2 * std_spread
            
            # Use cached Div Yield value from market_caps_cache.json if available
            current_div = None
            try:
                cache_file = "market_caps_cache.json"
                if os.path.exists(cache_file):
                    with open(cache_file, "r", encoding="utf-8") as f:
                        cache = json.load(f)
                        if symbol in cache:
                            current_div = cache[symbol].get("div_yield_ttm")
            except Exception:
                pass
                
            current_price = prices.iloc[-1]
            current_bond = bond_weekly.iloc[-1]
            
            curr_spread_val = (current_div - current_bond) if current_div is not None else spread_weekly.iloc[-1]
            curr_sd_level = (curr_spread_val - avg_spread) / std_spread if std_spread > 0 else 0
            
            # Layout metrics
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Current Price", f"{current_price:.2f} THB")
            col2.metric("Current Yield Spread", f"{curr_spread_val:.2f}%")
            col3.metric("5Y Average Spread", f"{avg_spread:.2f}%")
            col4.metric("Current 10Y Bond Yield", f"{current_bond:.2f}%")
            col5.metric("Current SD Level", f"{curr_sd_level:+.2f} SD")
            
            # Yield Spread over time vs SD lines (Direct rendering, no price bands tab)
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=spread_weekly.index, y=spread_weekly, name="Weekly Yield Spread", line=dict(color="#ffffff", width=2)))
            fig2.add_shape(type="line", x0=spread_weekly.index[0], y0=spread_p2, x1=spread_weekly.index[-1], y1=spread_p2, line=dict(color="#f87171", width=1, dash="dash"))
            fig2.add_shape(type="line", x0=spread_weekly.index[0], y0=spread_p1, x1=spread_weekly.index[-1], y1=spread_p1, line=dict(color="#fb7185", width=1, dash="dash"))
            fig2.add_shape(type="line", x0=spread_weekly.index[0], y0=spread_avg, x1=spread_weekly.index[-1], y1=spread_avg, line=dict(color="#94a3b8", width=1.5))
            fig2.add_shape(type="line", x0=spread_weekly.index[0], y0=spread_m1, x1=spread_weekly.index[-1], y1=spread_m1, line=dict(color="#34d399", width=1, dash="dash"))
            fig2.add_shape(type="line", x0=spread_weekly.index[0], y0=spread_m2, x1=spread_weekly.index[-1], y1=spread_m2, line=dict(color="#10b981", width=1, dash="dash"))
            
            # Annotate lines
            fig2.add_annotation(x=spread_weekly.index[-1], y=spread_p2, text=f"+2 SD ({spread_p2:.2f}%)", showarrow=False, xshift=10, font=dict(color="#ffffff"))
            fig2.add_annotation(x=spread_weekly.index[-1], y=spread_p1, text=f"+1 SD ({spread_p1:.2f}%)", showarrow=False, xshift=10, font=dict(color="#ffffff"))
            fig2.add_annotation(x=spread_weekly.index[-1], y=spread_avg, text=f"AVG ({spread_avg:.2f}%)", showarrow=False, xshift=10, font=dict(color="#ffffff"))
            fig2.add_annotation(x=spread_weekly.index[-1], y=spread_m1, text=f"-1 SD ({spread_m1:.2f}%)", showarrow=False, xshift=10, font=dict(color="#ffffff"))
            fig2.add_annotation(x=spread_weekly.index[-1], y=spread_m2, text=f"-2 SD ({spread_m2:.2f}%)", showarrow=False, xshift=10, font=dict(color="#ffffff"))
            
            fig2.update_layout(
                template="plotly_dark",
                xaxis_title="Date",
                yaxis_title="Yield Spread (%)",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#ffffff"),
                showlegend=False,
                yaxis=dict(
                    showgrid=False,
                    zeroline=False,
                    title_font=dict(color="#ffffff"),
                    tickfont=dict(color="#ffffff")
                ),
                xaxis=dict(
                    showgrid=False,
                    zeroline=False,
                    title_font=dict(color="#ffffff"),
                    tickfont=dict(color="#ffffff")
                )
            )
            st.plotly_chart(fig2, use_container_width=True)
                
        except Exception as e:
            st.error(f"Error calculating Yield Spread: {e}")

def show_roic_page(symbol):
    # Enable scrolling and override the custom full-screen css for this sub-page
    st.markdown("""
    <style>
        html, body, .stApp, div[data-testid="stAppViewContainer"], div[data-testid="stAppViewBlockContainer"] {
            overflow: auto !important;
            height: auto !important;
            width: auto !important;
            background-color: #090d16 !important;
            background-image: 
                radial-gradient(at 0% 0%, rgba(29, 78, 216, 0.15) 0px, transparent 50%),
                radial-gradient(at 50% 0%, rgba(76, 29, 149, 0.1) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(17, 24, 39, 0.8) 0px, transparent 50%) !important;
            background-attachment: fixed !important;
        }
        
        /* Force bright white text color for readability */
        h1, h2, h3, h4, h5, h6, .stMarkdown, p, li, span {
            color: #ffffff !important;
        }
        
        /* Target metric value text and labels */
        div[data-testid="stMetricValue"], div[data-testid="stMetricValue"] > div {
            color: #ffffff !important;
            font-weight: 700 !important;
        }
        div[data-testid="stMetricLabel"] p {
            color: #94a3b8 !important;
        }
        
        /* Premium Back Button Style */
        div.back-btn-wrapper > button {
            background: rgba(30, 41, 59, 0.6) !important;
            color: #ffffff !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
            border-radius: 8px !important;
            padding: 0.5rem 1rem !important;
            font-weight: 600 !important;
            cursor: pointer !important;
            transition: all 0.2s !important;
        }
        div.back-btn-wrapper > button:hover {
            color: white !important;
            border-color: #3b82f6 !important;
            background: rgba(59, 130, 246, 0.2) !important;
        }

        /* Premium Financial Details Table Styling */
        .financial-table-container {
            width: 100%;
            overflow-x: auto;
            margin-top: 1.5rem;
            margin-bottom: 2rem;
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            background: rgba(17, 24, 39, 0.4);
            backdrop-filter: blur(10px);
        }

        .financial-table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-family: inherit;
            color: #ffffff;
        }

        .financial-table th {
            background: rgba(30, 41, 59, 0.8);
            color: #94a3b8;
            font-weight: 600;
            padding: 1rem;
            font-size: 0.9rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .financial-table td {
            padding: 1rem;
            font-size: 0.95rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            color: #e2e8f0;
        }

        .financial-table tr:last-child td {
            border-bottom: none;
        }

        .financial-table tr:hover {
            background: rgba(255, 255, 255, 0.02);
        }
        
        .financial-table td.year-cell {
            font-weight: 600;
            color: #3b82f6;
        }

        .financial-table td.metric-cell {
            font-family: monospace;
        }
    </style>
    """, unsafe_allow_html=True)

    # Header with Back button aligned nicely
    col_title, col_back = st.columns([4, 1])
    with col_title:
        st.title(f"📊 {symbol} Historical ROIC (Annual)")
    with col_back:
        st.write("<div class='back-btn-wrapper'>", unsafe_allow_html=True)
        if st.button("🔙 Back to Dashboard"):
            st.query_params.pop("roic", None)
            st.rerun()
        st.write("</div>", unsafe_allow_html=True)
        
    ticker = symbol + ".BK" if not symbol.endswith(".BK") else symbol
    
    with st.spinner(f"Fetching financial history for {ticker} from Yahoo Finance..."):
        try:
            session = get_yfinance_session()
            t_obj = yf.Ticker(ticker, session=session)
            
            # Fetch financials
            inc = t_obj.income_stmt
            bs = t_obj.balance_sheet
            
            if inc.empty or bs.empty:
                st.error(f"Could not find financial statements for {ticker} on Yahoo Finance.")
                return
                
            # Intersect available years
            years = inc.columns.intersection(bs.columns)
            years = sorted(list(years)) # sort chronological
            
            if not years:
                st.error("No overlapping annual financial data found for aligning Income Statement and Balance Sheet.")
                return
                
            roic_data = []
            for y in years:
                # Net Income
                ni = None
                for k in ['Net Income Common Stockholders', 'Net Income', 'Diluted NI Availto Com Stockholders']:
                    if k in inc.index:
                        val = inc.loc[k]
                        ni_val = val.loc[y] if isinstance(val, pd.Series) else val
                        if pd.notna(ni_val):
                            ni = ni_val
                            break
                            
                # Debt
                debt = 0
                if 'Total Debt' in bs.index:
                    val = bs.loc['Total Debt']
                    d_val = val.loc[y] if isinstance(val, pd.Series) else val
                    debt = d_val if pd.notna(d_val) else 0
                    
                # Equity
                equity = None
                for k in ['Stockholders Equity', 'Common Stock Equity', 'Total Equity Gross Minority Interest']:
                    if k in bs.index:
                        val = bs.loc[k]
                        eq_val = val.loc[y] if isinstance(val, pd.Series) else val
                        if pd.notna(eq_val) and eq_val > 0:
                            equity = eq_val
                            break
                            
                if ni is not None and equity is not None:
                    ic = debt + equity
                    if ic > 0:
                        roic_val = (ni / ic) * 100
                        year_str = y.strftime('%Y')
                        roic_data.append({
                            "Year": year_str,
                            "ROIC": roic_val,
                            "Net Income (M)": ni / 1e6,
                            "Total Debt (M)": debt / 1e6,
                            "Equity (M)": equity / 1e6,
                            "Invested Capital (M)": ic / 1e6
                        })
            
            if not roic_data:
                st.error("Could not compute ROIC from the available financial data.")
                return
                
            df_roic = pd.DataFrame(roic_data)
            
            # Show metrics for latest year
            latest = roic_data[-1]
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Latest ROIC", f"{latest['ROIC']:.2f}%")
            col2.metric("Net Income (Latest)", f"{latest['Net Income (M)']:.1f}M THB")
            col3.metric("Invested Capital (Latest)", f"{latest['Invested Capital (M)']:.1f}M THB")
            col4.metric("Debt / Equity Ratio", f"{(latest['Total Debt (M)']/latest['Equity (M)']):.2f}" if latest['Equity (M)'] > 0 else "N/A")
            
            # Add premium plotting with Plotly
            fig = go.Figure()
            # Bar chart for ROIC values
            fig.add_trace(go.Bar(
                x=df_roic["Year"],
                y=df_roic["ROIC"],
                text=[f"{v:.2f}%" for v in df_roic["ROIC"]],
                textposition='outside',
                marker_color='#10b981', # Green
                textfont=dict(size=15, color="#ffffff", family="sans-serif"),
                name="ROIC (%)",
                hovertemplate="Year %{x}<br>ROIC: %{y:.2f}%<extra></extra>"
            ))
            
            # Line chart on same graph
            fig.add_trace(go.Scatter(
                x=df_roic["Year"],
                y=df_roic["ROIC"],
                mode='lines+markers',
                line=dict(color='#3b82f6', width=4), # Blue
                marker=dict(size=10, color='#ffffff', line=dict(color='#3b82f6', width=2.5)),
                name="Trend",
                hoverinfo='skip'
            ))
            
            fig.update_layout(
                template="plotly_dark",
                xaxis_title="Fiscal Year",
                yaxis_title="Return on Invested Capital (ROIC %)",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                height=500,
                margin=dict(t=30, b=50, l=60, r=30),
                font=dict(color="#ffffff", size=14),
                showlegend=False,
                yaxis=dict(
                    showgrid=True,
                    gridcolor="rgba(255,255,255,0.1)",
                    zeroline=True,
                    zerolinecolor="rgba(255,255,255,0.2)",
                    title_font=dict(size=16, color="#ffffff"),
                    tickfont=dict(size=14, color="#ffffff"),
                    ticksuffix="%"
                ),
                xaxis=dict(
                    showgrid=False,
                    title_font=dict(size=16, color="#ffffff"),
                    tickfont=dict(size=14, color="#ffffff"),
                    type='category'
                )
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Display detailed data table
            st.subheader("📋 Financial Details Table")
            
            table_rows = []
            for item in roic_data:
                y_val = item["Year"]
                r_val = f"{item['ROIC']:.2f}%"
                ni_val = f"{item['Net Income (M)']:,.1f}M THB"
                debt_val = f"{item['Total Debt (M)']:,.1f}M THB"
                eq_val = f"{item['Equity (M)']:,.1f}M THB"
                ic_val = f"{item['Invested Capital (M)']:,.1f}M THB"
                row_html = f'<tr><td class="year-cell">{y_val}</td><td class="metric-cell" style="color: #10b981; font-weight: 600;">{r_val}</td><td class="metric-cell">{ni_val}</td><td class="metric-cell">{debt_val}</td><td class="metric-cell">{eq_val}</td><td class="metric-cell">{ic_val}</td></tr>'
                table_rows.append(row_html)
                
            table_html = f'<div class="financial-table-container"><table class="financial-table"><thead><tr><th>Year</th><th>ROIC</th><th>Net Income (M)</th><th>Total Debt (M)</th><th>Equity (M)</th><th>Invested Capital (M)</th></tr></thead><tbody>{"".join(table_rows)}</tbody></table></div>'
            st.markdown(table_html, unsafe_allow_html=True)
            
            st.info("ℹ️ **หมายเหตุ**: ข้อมูลทางการเงินดึงข้อมูลรายปีล่าสุดจาก Yahoo Finance (สูงสุด 4-5 ปี) โดยสูตรคำนวณคือ: ROIC = Net Income / (Total Debt + Stockholders Equity) เพื่อให้สอดคล้องกับมาตรฐาน TradingView")

        except Exception as e:
            st.error(f"Error fetching/calculating ROIC history: {e}")

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

# Check if pbv_band query parameter is set to show valuation bands
if "pbv_band" in st.query_params:
    symbol = st.query_params["pbv_band"]
    show_pbv_band_page(symbol)
    st.stop()

# Check if div_band query parameter is set to show valuation bands
if "div_band" in st.query_params:
    symbol = st.query_params["div_band"]
    show_div_band_page(symbol)
    st.stop()

# Check if roic query parameter is set to show ROIC details
if "roic" in st.query_params:
    symbol = st.query_params["roic"]
    show_roic_page(symbol)
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

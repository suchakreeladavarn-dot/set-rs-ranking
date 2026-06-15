import argparse
import os
import re
import sys
import time
import warnings
import webbrowser
import json
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# Configure console output encoding to support UTF-8 (emojis and Thai text)
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

warnings.filterwarnings('ignore')

CACHE_FILE = "market_caps_cache.json"
INDICES_CACHE_FILE = "indices_cache.json"

def clean_stock_list(file_path):
    """
    Reads the CSV and extracts a cleaned list of stock symbols.
    """
    if not os.path.exists(file_path):
        print(f"[ERROR] File not found at '{file_path}'")
        return []

    try:
        df_symbols = pd.read_csv(file_path)
        possible_cols = ['Symbol', 'Ticker', 'SYMBOL', 'TICKER', 'Stock', 'symbol']
        found_col = next((c for c in possible_cols if c in df_symbols.columns), df_symbols.columns[0])

        raw_stocks = df_symbols[found_col].dropna().astype(str).tolist()
        print(f"[INFO] Loaded {len(raw_stocks)} rows from column '{found_col}'")

        thai_stocks = []
        exclude_list = [
            'BANKING', 'FINANCIALS', 'INSURANCE', 'ENERG', 'FOOD', 'COMM', 'ICT',
            'PROP', 'CONMAT', 'AGRI', 'AUTO', 'HOME', 'PERSON', 'PETRO', 'PKG',
            'PROF', 'PAPER', 'MEDIA', 'MINE', 'STEEL', 'TOURISM', 'TRANS', 'ETRON', 'HELTH',
            'MCHAI', 'LE', 'MPAT', 'BWORK', 'FD', 'MSTOR', 'SJ', 'TUPF', 'SEED', 'QCON', 'FINANCIALS'
        ]

        for s in raw_stocks:
            clean_s = re.sub(r'[^a-zA-Z0-9]', '', s).strip()
            if not clean_s or clean_s.isdigit():
                continue
            if any(ex == clean_s.upper() for ex in exclude_list):
                continue
            if s.startswith('--') or s.startswith('.'):
                continue
            thai_stocks.append(clean_s)
        
        cleaned_stocks = sorted(list(set(thai_stocks)))
        print(f"[INFO] Cleaned list: Found {len(cleaned_stocks)} valid stock symbols")
        return cleaned_stocks
    except Exception as e:
        print(f"[ERROR] Error parsing CSV: {e}")
        return []

def load_mcap_cache():
    """
    Loads market capitalization cache from JSON file.
    """
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARNING] Could not load market cap cache: {e}")
    return {}

def save_mcap_cache(cache):
    """
    Saves market capitalization cache to JSON file.
    """
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[WARNING] Could not save market cap cache: {e}")

def load_indices_cache():
    if os.path.exists(INDICES_CACHE_FILE):
        try:
            with open(INDICES_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARNING] Could not load indices cache: {e}")
    return {}

def save_indices_cache(cache):
    try:
        with open(INDICES_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[WARNING] Could not save indices cache: {e}")

def fetch_indices_data(max_workers=12):
    cache = load_indices_cache()
    # Cache for 2 hours
    cache_expiry_time = datetime.now() - timedelta(hours=2)
    
    results = []
    tickers_to_fetch = []
    
    indices_info = [
        {"name": "S&P 500", "ticker": "^GSPC", "flag_code": "us"},
        {"name": "Dow Jones", "ticker": "^DJI", "flag_code": "us"},
        {"name": "NASDAQ", "ticker": "^IXIC", "flag_code": "us"},
        {"name": "SET Index", "ticker": "^SET.BK", "flag_code": "th"},
        {"name": "SET50", "ticker": "^SET50.BK", "flag_code": "th"},
        {"name": "mai Index", "ticker": "^MAI.BK", "flag_code": "th"},
        {"name": "NIKKEI 225", "ticker": "^N225", "flag_code": "jp"},
        {"name": "Hang Seng", "ticker": "^HSI", "flag_code": "hk"},
        {"name": "KOSPI", "ticker": "^KS11", "flag_code": "kr"},
        {"name": "Straits Times", "ticker": "^STI", "flag_code": "sg"},
        {"name": "DAX Index", "ticker": "^GDAXI", "flag_code": "de"},
        {"name": "FTSE 100", "ticker": "^FTSE", "flag_code": "gb"}
    ]
    
    for item in indices_info:
        ticker = item["ticker"]
        cached_item = cache.get(ticker)
        if cached_item:
            try:
                updated_at_str = cached_item.get("updated_at", "2000-01-01 00:00:00")
                updated_at = datetime.strptime(updated_at_str, "%Y-%m-%d %H:%M:%S")
                if updated_at >= cache_expiry_time and cached_item.get("price") is not None:
                    results.append({
                        "name": item["name"],
                        "ticker": ticker,
                        "flag_code": item["flag_code"],
                        "price": cached_item["price"],
                        "chg_pct": cached_item["chg_pct"]
                    })
                    continue
            except Exception:
                pass
        tickers_to_fetch.append(item)
        
    if not tickers_to_fetch:
        # Sort results to match original indices_info order
        ticker_order = {x["ticker"]: i for i, x in enumerate(indices_info)}
        results.sort(key=lambda x: ticker_order[x["ticker"]])
        return results
        
    print(f"[INFO] Need to fetch {len(tickers_to_fetch)} indices from Yahoo Finance...")
    
    new_data = {}
    
    def get_single_index(item):
        ticker = item["ticker"]
        try:
            t_obj = yf.Ticker(ticker)
            info = t_obj.info
            price = info.get("regularMarketPrice")
            chg_pct = info.get("regularMarketChangePercent")
            
            # Fallback to history if info does not provide the required fields
            if price is None or chg_pct is None:
                hist = t_obj.history(period="5d")
                if not hist.empty:
                    latest = hist.iloc[-1]
                    prev = hist.iloc[-2] if len(hist) >= 2 else latest
                    if price is None:
                        price = float(latest["Close"])
                    if chg_pct is None:
                        prev_price = float(prev["Close"])
                        if prev_price != 0:
                            chg_pct = float(((price - prev_price) / prev_price) * 100)
                        else:
                            chg_pct = 0.0
            
            if price is not None:
                return ticker, float(price), float(chg_pct) if chg_pct is not None else 0.0
            return ticker, None, None
        except Exception as e:
            print(f"[WARNING] Error fetching index {ticker}: {e}")
            return ticker, None, None

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(get_single_index, item): item for item in tickers_to_fetch}
        for future in as_completed(futures):
            ticker, price, chg_pct = future.result()
            if price is not None:
                new_data[ticker] = {
                    "price": price,
                    "chg_pct": chg_pct,
                    "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
    # Update cache
    for ticker, data in new_data.items():
        cache[ticker] = data
        
    save_indices_cache(cache)
    
    # Rebuild final list matching the original indices_info order
    final_results = []
    for item in indices_info:
        ticker = item["ticker"]
        data = cache.get(ticker)
        if data and data.get("price") is not None:
            final_results.append({
                "name": item["name"],
                "ticker": ticker,
                "flag_code": item["flag_code"],
                "price": data["price"],
                "chg_pct": data["chg_pct"]
            })
        else:
            final_results.append({
                "name": item["name"],
                "ticker": ticker,
                "flag_code": item["flag_code"],
                "price": None,
                "chg_pct": None
            })
            
    return final_results

def fetch_market_caps(tickers, max_workers=15):
    """
    Downloads market capitalization and IAA consensus mean price for tickers in parallel,
    utilizing a local cache to avoid Yahoo Finance rate limits.
    Returns:
        tuple: (mcaps_dict, consensus_dict)
    """
    cache = load_mcap_cache()
    today_str = datetime.now().strftime('%Y-%m-%d')
    cache_expiry_date = datetime.now() - timedelta(days=5)
    
    mcaps = {}
    consensus = {}
    tickers_to_fetch = []
    
    # 1. Identify which tickers need fetching
    for t in tickers:
        cached_data = cache.get(t)
        if cached_data:
            try:
                updated_date = datetime.strptime(cached_data.get("updated_at", "2000-01-01"), "%Y-%m-%d")
                # We also check that "target_mean_price" key is in the cached data (even if its value is None/null)
                # to trigger migration for old cache records that only have "market_cap_m"
                if updated_date >= cache_expiry_date and cached_data.get("market_cap_m") is not None and "target_mean_price" in cached_data:
                    mcaps[t] = cached_data.get("market_cap_m")
                    consensus[t] = cached_data.get("target_mean_price")
                    continue
            except Exception:
                pass
        tickers_to_fetch.append(t)

    if not tickers_to_fetch:
        print(f"[INFO] All {len(tickers)} market caps and consensus target prices loaded from local cache.")
        return mcaps, consensus

    print(f"[INFO] Cache status: {len(mcaps)} from cache, need to fetch {len(tickers_to_fetch)} from Yahoo Finance...")

    # 2. Fetch missing market caps and consensus prices in parallel with throttling
    formatted_tickers = [t + ".BK" if not t.endswith(".BK") and not t.startswith("^") else t for t in tickers_to_fetch]
    
    new_data = {}
    
    def get_single_stock_data(ticker):
        # Add a tiny delay between thread starts to avoid hitting Yahoo at the exact same millisecond
        time.sleep(0.05)
        clean_t = ticker.replace('.BK', '')
        try:
            t_obj = yf.Ticker(ticker)
            # Try to fetch info which has targetMeanPrice and marketCap
            info = t_obj.info
            mcap = info.get("marketCap")
            target_mean = info.get("targetMeanPrice")
            
            # Fallback to fast_info for market cap if not in info
            if mcap is None:
                mcap = t_obj.fast_info.market_cap
                
            if mcap is not None:
                mcap_m = mcap / 1e6
                return clean_t, mcap_m, target_mean
            return clean_t, None, target_mean
        except Exception:
            # Full fallback to fast_info for market cap
            try:
                t_obj = yf.Ticker(ticker)
                mcap = t_obj.fast_info.market_cap
                if mcap is not None:
                    return clean_t, mcap / 1e6, None
            except Exception:
                pass
            return clean_t, None, None

    # We use fewer workers (max_workers=15) to prevent API rate limiting
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(get_single_stock_data, t): t for t in formatted_tickers}
        for future in as_completed(futures):
            symbol, mcap_m, target_mean = future.result()
            new_data[symbol] = (mcap_m, target_mean)

    # 3. Update cache
    for symbol, (mcap_m, target_mean) in new_data.items():
        mcaps[symbol] = mcap_m
        consensus[symbol] = target_mean
        cache[symbol] = {
            "market_cap_m": mcap_m,
            "target_mean_price": target_mean,
            "updated_at": today_str
        }
        
    save_mcap_cache(cache)
    return mcaps, consensus

def calculate_rs_ranking(tickers, benchmark_symbol, ma_length):
    """
    Downloads historical data from yfinance and calculates the Mansfield RS ranking.
    """
    # Append suffix for yfinance (.BK) if not present
    formatted_tickers = [t + ".BK" if not t.endswith(".BK") and not t.startswith("^") else t for t in tickers]
    bench_ticker = benchmark_symbol + ".BK" if not benchmark_symbol.endswith(".BK") and not benchmark_symbol.startswith("^") else benchmark_symbol

    print(f"[INFO] Downloading historical data for {len(formatted_tickers)} stocks + benchmark ({bench_ticker})...")
    
    start_date = datetime.now() - timedelta(days=365 + ma_length + 50)
    all_tickers = formatted_tickers + [bench_ticker]
    
    # yf.download is called in bulk and handles rate limits internally with cookies/sessions
    try:
        data = yf.download(all_tickers, start=start_date, progress=True)['Close']
    except Exception as e:
        print(f"[ERROR] Error downloading data: {e}")
        return pd.DataFrame()

    data = data.dropna(axis=1, how='all')

    if bench_ticker not in data.columns:
        print(f"[ERROR] Benchmark '{bench_ticker}' data not available.")
        return pd.DataFrame()

    bench_data = data[bench_ticker].ffill()
    stock_data = data.drop(columns=[bench_ticker]).ffill()

    print("[INFO] Calculating Mansfield Relative Strength (RS)...")
    rs_ratio = stock_data.div(bench_data, axis=0)
    rs_sma = rs_ratio.rolling(window=ma_length).mean()
    mrs = ((rs_ratio / rs_sma) - 1) * 100

    latest_mrs = mrs.iloc[-1].dropna().sort_values(ascending=False)
    
    # Calculate Last Price and Change %
    latest_prices = stock_data.iloc[-1]
    if len(stock_data) >= 2:
        prev_prices = stock_data.iloc[-2]
        pct_changes = ((latest_prices - prev_prices) / prev_prices.replace(0, np.nan)) * 100
    else:
        pct_changes = pd.Series(0.0, index=stock_data.columns)

    ranking_df = latest_mrs.reset_index()
    ranking_df.columns = ['Symbol', 'Mansfield_RS']
    
    # Map metrics to the ranking dataframe
    ranking_df['Last_Price'] = ranking_df['Symbol'].map(latest_prices)
    ranking_df['Chg_Pct'] = ranking_df['Symbol'].map(pct_changes)
    
    ranking_df['Symbol'] = ranking_df['Symbol'].str.replace('.BK', '', regex=False)
    ranking_df.index = ranking_df.index + 1
    
    return ranking_df

def generate_color_map(df):
    """
    Maps Mansfield RS values to colors using matplotlib RdYlGn colormap.
    """
    if df.empty:
        return {}, {}
        
    cmap = plt.get_cmap('RdYlGn')
    actual_max = df['Mansfield_RS'].max()
    actual_min = df['Mansfield_RS'].min()
    
    norm_min = min(-10, actual_min - 5) if actual_min < 0 else -20
    norm_max = max(20, actual_max)
    if norm_max == norm_min:
        norm_max += 1.0
        
    norm = mcolors.TwoSlopeNorm(vcenter=0.0, vmin=norm_min, vmax=norm_max)
    
    bg_colors = {}
    text_colors = {}
    
    for _, row in df.iterrows():
        val = row['Mansfield_RS']
        try:
            rgba = cmap(norm(val))
            hex_color = mcolors.to_hex(rgba)
            bg_colors[row['Symbol']] = hex_color
            
            rgb = mcolors.to_rgb(hex_color)
            luminance = 0.299*rgb[0] + 0.587*rgb[1] + 0.114*rgb[2]
            text_colors[row['Symbol']] = '#ffffff' if luminance < 0.45 else '#0f172a'
        except Exception:
            bg_colors[row['Symbol']] = '#1e293b'
            text_colors[row['Symbol']] = '#ffffff'
            
    return bg_colors, text_colors

def build_html_report(ranking_df, benchmark, ma_length, output_path):
    """
    Creates a premium, responsive HTML report.
    """
    display_benchmark = "SET INDEX" if benchmark == "^SET.BK" else benchmark
    bg_colors, text_colors = generate_color_map(ranking_df)
    
    top_15 = ranking_df.head(15).to_dict('records')
    all_stocks = ranking_df.to_dict('records')
    
    def get_consensus_html(row):
        target = row.get('Target_Mean_Price')
        last = row.get('Last_Price')
        if pd.isna(target) or target <= 0 or pd.isna(last) or last <= 0:
            return '<div class="consensus-target">N/A</div>'
        
        # Round to 2 decimal places to be consistent with what is displayed on the screen
        target_rounded = round(float(target), 2)
        last_rounded = round(float(last), 2)
        
        diff_pct = ((target_rounded - last_rounded) / last_rounded) * 100
        if diff_pct > 0:
            return f'<div class="consensus-target">{target_rounded:.2f}</div><div class="consensus-upside upside-positive">Upside +{diff_pct:.2f}%</div>'
        elif diff_pct < 0:
            return f'<div class="consensus-target">{target_rounded:.2f}</div><div class="consensus-upside upside-negative">Downside {diff_pct:.2f}%</div>'
        else:
            return f'<div class="consensus-target">{target_rounded:.2f}</div><div class="consensus-upside upside-neutral">0.00%</div>'
    
    
    # Fetch indices data
    indices_data = fetch_indices_data()
    indices_html = []
    
    tv_symbol_map = {
        "^GSPC": "SP:SPX",
        "^DJI": "DJ:DJI",
        "^IXIC": "NASDAQ:IXIC",
        "^SET.BK": "SET:SET",
        "^SET50.BK": "SET:SET50",
        "^MAI.BK": "SET:MAI",
        "^N225": "TVC:NI225",
        "^HSI": "HSI:HSI",
        "^KS11": "KRX:KOSPI",
        "^STI": "TVC:STI",
        "^GDAXI": "XETR:DAX",
        "^FTSE": "FTSE:UKX"
    }
    
    for item in indices_data:
        name = item["name"]
        ticker = item["ticker"]
        flag = item["flag_code"]
        price = item["price"]
        chg = item["chg_pct"]
        
        tv_symbol = tv_symbol_map.get(ticker, ticker.replace("^", "").replace(".BK", ""))
        
        if price is None:
            price_str = "N/A"
            chg_str = "N/A"
            chg_class = "neutral"
        else:
            price_str = f"{price:,.2f}"
            chg_str = f"{'+' if chg > 0 else ''}{chg:.2f}%"
            chg_class = "positive" if chg > 0 else ("negative" if chg < 0 else "neutral")
            
        indices_html.append(f'''
        <div class="index-item">
            <div class="index-info">
                <img src="https://flagcdn.com/w40/{flag}.png" class="flag-icon" alt="{flag.upper()}">
                <div class="index-name-ticker">
                    <a href="https://www.tradingview.com/chart/?symbol={tv_symbol}" target="_blank" class="index-display-name">{name}</a>
                </div>
            </div>
            <span class="index-price">{price_str}</span>
            <span class="index-chg {chg_class}">{chg_str}</span>
        </div>
        ''')
    indices_list_html = "".join(indices_html)
    
    # Convert to Thailand time (UTC+7) since Streamlit Cloud servers run in UTC by default
    thailand_time = datetime.utcnow() + timedelta(hours=7)
    now_str = thailand_time.strftime('%Y-%m-%d %H:%M')
    
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stan Weinstein RS Ranking</title>
    
    <!-- Open Graph / Facebook Link Preview Meta Tags -->
    <meta property="og:type" content="website">
    <meta property="og:title" content="Stan Weinstein RS Ranking Leaderboard">
    <meta property="og:description" content="Stage 2 stock breakout scanner using Mansfield Relative Strength (RS) to track institutional flow.">
    <meta property="og:image" content="https://raw.githubusercontent.com/suchakreeladavarn-dot/set-rs-ranking/main/stock_scanner_icon.png">
    
    <!-- Twitter Link Preview Meta Tags -->
    <meta property="twitter:card" content="summary_large_image">
    <meta property="twitter:title" content="Stan Weinstein RS Ranking Leaderboard">
    <meta property="twitter:description" content="Stage 2 stock breakout scanner using Mansfield Relative Strength (RS) to track institutional flow.">
    <meta property="twitter:image" content="https://raw.githubusercontent.com/suchakreeladavarn-dot/set-rs-ranking/main/stock_scanner_icon.png">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-primary: #090d16;
            --bg-secondary: #111827;
            --bg-card: rgba(22, 30, 49, 0.6);
            --border-color: rgba(255, 255, 255, 0.08);
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
            --accent-glow: rgba(59, 130, 246, 0.15);
            --accent: #3b82f6;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-main);
            line-height: 1.5;
            padding: 2rem 1.5rem;
            min-height: 100vh;
            background-image: 
                radial-gradient(at 0% 0%, rgba(29, 78, 216, 0.15) 0px, transparent 50%),
                radial-gradient(at 50% 0%, rgba(76, 29, 149, 0.1) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(17, 24, 39, 0.8) 0px, transparent 50%);
            background-attachment: fixed;
        }}

        .container {{
            max-width: 1600px;
            margin: 0 auto;
            width: 95%;
        }}

        /* Header Styling */
        header {{
            text-align: center;
            margin-bottom: 3rem;
            position: relative;
        }}

        .logo-area {{
            display: inline-flex;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 0.5rem;
        }}

        .logo-icon {{
            background: linear-gradient(135deg, #3b82f6, #8b5cf6);
            width: 40px;
            height: 40px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
            font-size: 1.25rem;
            color: white;
            box-shadow: 0 0 20px rgba(59, 130, 246, 0.4);
            font-family: 'Outfit', sans-serif;
        }}

        h1 {{
            font-family: 'Outfit', sans-serif;
            font-size: 2.5rem;
            font-weight: 800;
            background: linear-gradient(135deg, #ffffff 30%, #a5b4fc 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.025em;
        }}

        .subtitle {{
            color: var(--text-muted);
            font-size: 1rem;
            margin-top: 0.5rem;
            display: flex;
            justify-content: center;
            gap: 1.5rem;
            flex-wrap: wrap;
        }}

        .badge {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-color);
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.85rem;
            font-weight: 500;
        }}

        .badge.highlight {{
            border-color: rgba(59, 130, 246, 0.3);
            color: #60a5fa;
            background: rgba(59, 130, 246, 0.05);
        }}

        /* Top Cards Layout */
        .section-title {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .section-title span {{
            color: #60a5fa;
        }}

        .top-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 1rem;
            margin-bottom: 3rem;
        }}

        .top-card {{
            background: var(--bg-card);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.25rem;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            height: 130px;
        }}

        .top-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 4px;
            background: var(--card-accent-color);
        }}

        .top-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 12px 24px -10px rgba(0, 0, 0, 0.5), 0 0 1px 1px var(--card-accent-color);
            border-color: rgba(255, 255, 255, 0.15);
        }}

        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
        }}

        .rank-badge {{
            font-size: 0.75rem;
            font-weight: 700;
            color: var(--text-muted);
            background: rgba(255, 255, 255, 0.05);
            width: 20px;
            height: 20px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        .ticker-name {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.4rem;
            font-weight: 800;
            color: #ffffff;
        }}

        .rs-badge {{
            align-self: flex-start;
            padding: 0.25rem 0.6rem;
            border-radius: 6px;
            font-size: 0.9rem;
            font-weight: 700;
            background-color: var(--card-accent-color);
            color: var(--card-text-color);
            box-shadow: 0 4px 10px -2px rgba(0, 0, 0, 0.3);
        }}

        .mcap-subtext {{
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-top: 0.25rem;
        }}

        /* Table Card & Controls */
        .table-container-card {{
            background: var(--bg-card);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            padding: 1.5rem;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        }}

        .controls-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
            gap: 1.5rem;
            flex-wrap: wrap;
        }}

        .search-wrapper {{
            position: relative;
            flex: 2;
            max-width: 400px;
            min-width: 200px;
        }}

        .search-input {{
            width: 100%;
            background: rgba(17, 24, 39, 0.6);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 0.75rem 1rem 0.75rem 2.5rem;
            color: white;
            font-size: 0.95rem;
            transition: all 0.2s;
        }}

        .search-input:focus {{
            outline: none;
            border-color: var(--accent);
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.25);
        }}

        .search-icon {{
            position: absolute;
            left: 0.85rem;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-muted);
            pointer-events: none;
            width: 16px;
            height: 16px;
        }}

        .mcap-filter-wrapper {{
            position: relative;
            flex: 1;
            max-width: 280px;
            min-width: 180px;
        }}

        .mcap-input {{
            width: 100%;
            background: rgba(17, 24, 39, 0.6);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 0.75rem 1rem;
            color: white;
            font-size: 0.95rem;
            transition: all 0.2s;
        }}

        .mcap-input:focus {{
            outline: none;
            border-color: var(--accent);
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.25);
        }}

        .stats-summary {{
            font-size: 0.9rem;
            color: var(--text-muted);
            white-space: nowrap;
        }}

        .stats-summary strong {{
            color: white;
        }}

        /* Table Design */
        .table-responsive {{
            overflow-x: auto;
            max-height: 600px;
            overflow-y: auto;
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }}

        th {{
            background: rgba(17, 24, 39, 0.85);
            padding: 1rem;
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            position: sticky;
            top: 0;
            z-index: 10;
            cursor: pointer;
            user-select: none;
            border-bottom: 1px solid var(--border-color);
            transition: color 0.2s;
            white-space: nowrap;
        }}

        th:hover {{
            color: #ffffff;
        }}

        td {{
            padding: 0.85rem 1rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.03);
            font-size: 0.95rem;
            vertical-align: middle;
        }}

        tr {{
            transition: background-color 0.15s;
        }}

        tr:hover td {{
            background: rgba(255, 255, 255, 0.02);
        }}

        .rank-cell {{
            font-weight: 600;
            color: var(--text-muted);
            width: 80px;
        }}

        .symbol-cell {{
            font-weight: 700;
            font-family: 'Outfit', sans-serif;
            font-size: 1.05rem;
            color: #ffffff;
        }}

        .tv-link {{
            color: #ffffff;
            text-decoration: none;
            transition: color 0.15s, border-bottom 0.15s;
            border-bottom: 1px dashed rgba(255, 255, 255, 0.25);
            padding-bottom: 1px;
            display: inline-block;
        }}

        .tv-link:hover {{
            color: #3b82f6;
            border-bottom-color: #3b82f6;
        }}

        .price-cell {{
            font-weight: 600;
            color: #ffffff;
            width: 120px;
        }}

        .chg-cell {{
            font-weight: 600;
            width: 120px;
        }}

        .chg-positive {{
            color: #34d399;
        }}

        .chg-negative {{
            color: #f87171;
        }}

        .chg-zero {{
            color: var(--text-muted);
        }}

        .rs-cell {{
            width: 160px;
        }}

        .rs-pill-value {{
            display: inline-block;
            padding: 0.35rem 0.75rem;
            border-radius: 8px;
            font-weight: 700;
            font-size: 0.9rem;
            text-align: center;
            min-width: 80px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }}

        .mcap-cell {{
            font-weight: 500;
            color: var(--text-main);
            width: 160px;
        }}

        .consensus-cell {{
            font-weight: 500;
            color: var(--text-main);
            width: 150px;
            vertical-align: middle;
        }}

        .consensus-target {{
            font-weight: 600;
            font-size: 1.05rem;
            color: #ffffff;
        }}

        .consensus-upside {{
            font-size: 0.78rem;
            font-weight: 600;
            margin-top: 0.2rem;
            display: inline-block;
        }}

        .upside-positive {{
            color: #34d399; /* Green */
        }}

        .upside-negative {{
            color: #f87171; /* Red */
        }}

        .upside-neutral {{
            color: var(--text-muted);
        }}

        .status-cell {{
            width: 140px;
        }}

        .status-badge {{
            padding: 0.25rem 0.6rem;
            border-radius: 6px;
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
        }}

        .status-bullish {{
            background: rgba(16, 185, 129, 0.1);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.2);
        }}

        .status-bearish {{
            background: rgba(239, 68, 68, 0.1);
            color: #f87171;
            border: 1px solid rgba(239, 68, 68, 0.2);
        }}

        .status-neutral {{
            background: rgba(245, 158, 11, 0.1);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.2);
        }}

        /* Scrollbar styles */
        .table-responsive::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}

        .table-responsive::-webkit-scrollbar-track {{
            background: rgba(0, 0, 0, 0.15);
        }}

        .table-responsive::-webkit-scrollbar-thumb {{
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
        }}

        .table-responsive::-webkit-scrollbar-thumb:hover {{
            background: rgba(255, 255, 255, 0.25);
        }}

        .scan-btn {{
            position: absolute;
            top: 0;
            right: 0;
            background: linear-gradient(135deg, #3b82f6, #8b5cf6);
            color: white;
            font-weight: 600;
            border: none;
            padding: 0.5rem 1.2rem;
            border-radius: 8px;
            box-shadow: 0 4px 15px rgba(59, 130, 246, 0.3);
            cursor: pointer;
            transition: all 0.2s;
            font-size: 0.85rem;
            font-family: 'Outfit', sans-serif;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            z-index: 100;
            text-decoration: none;
        }}

        .scan-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(59, 130, 246, 0.5);
        }}

        /* Responsive adjustments */
        @media (max-width: 768px) {{
            body {{
                padding: 1rem 0.5rem;
            }}
            h1 {{
                font-size: 1.8rem;
            }}
            .top-grid {{
                grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
            }}
            .table-container-card {{
                padding: 1rem 0.5rem;
                border-radius: 12px;
            }}
            .controls-row {{
                flex-direction: column;
                align-items: stretch;
            }}
            .search-wrapper, .mcap-filter-wrapper {{
                max-width: 100%;
            }}
        }}

        /* Main Layout Row (Content + Sidebar) */
        .main-layout-row {{
            display: flex;
            gap: 2rem;
            width: 100%;
            align-items: flex-start;
        }}

        .main-left-column {{
            flex: 2.5;
            min-width: 0;
            display: flex;
            flex-direction: column;
            gap: 2rem;
        }}

        .main-right-column {{
            flex: 1;
            min-width: 320px;
            position: -webkit-sticky;
            position: sticky;
            top: 2rem;
        }}

        @media (max-width: 1024px) {{
            .main-layout-row {{
                flex-direction: column;
                gap: 2rem;
            }}
            .main-left-column, .main-right-column {{
                width: 100%;
                flex: none;
            }}
            .main-right-column {{
                position: static;
            }}
        }}

        /* Indices Card Widget */
        .indices-card {{
            background: var(--bg-card);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            padding: 1.25rem;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }}

        .index-row-header {{
            display: flex;
            justify-content: space-between;
            font-size: 0.75rem;
            font-weight: 700;
            color: var(--text-muted);
            letter-spacing: 0.05em;
            padding: 0 0.5rem 0.5rem 0.5rem;
            border-bottom: 1px solid var(--border-color);
        }}

        .index-row-header span:nth-child(1) {{
            width: 50%;
        }}

        .index-row-header span:nth-child(2) {{
            width: 25%;
            text-align: right;
        }}

        .index-row-header span:nth-child(3) {{
            width: 25%;
            text-align: right;
        }}

        .indices-list {{
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }}

        .index-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.6rem 0.5rem;
            border-radius: 10px;
            transition: background 0.15s;
        }}

        .index-item:hover {{
            background: rgba(255, 255, 255, 0.03);
        }}

        .index-info {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            width: 50%;
        }}

        .flag-icon {{
            width: 24px;
            height: 16px;
            object-fit: cover;
            border-radius: 3px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.3);
        }}

        .index-name-ticker {{
            display: flex;
            flex-direction: column;
        }}

        .index-display-name {{
            font-weight: 600;
            font-size: 0.9rem;
            color: #ffffff;
            font-family: 'Outfit', sans-serif;
            text-decoration: none;
            transition: color 0.2s ease;
        }}

        a.index-display-name:hover {{
            color: #60a5fa;
            text-decoration: underline;
        }}

        .index-ticker-code {{
            font-size: 0.7rem;
            color: var(--text-muted);
        }}

        .index-price {{
            font-weight: 600;
            font-size: 0.9rem;
            color: #ffffff;
            width: 25%;
            text-align: right;
        }}

        .index-chg {{
            font-weight: 700;
            font-size: 0.85rem;
            width: 25%;
            text-align: right;
        }}

        .index-chg.positive {{
            color: #34d399;
        }}

        .index-chg.negative {{
            color: #f87171;
        }}

        .index-chg.neutral {{
            color: var(--text-muted);
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo-area">
                <div class="logo-icon">RS</div>
            </div>
            <h1>Stan Weinstein RS Ranking</h1>
            <div class="subtitle">
                <span class="badge">Benchmark: <strong style="color:white">{display_benchmark}</strong></span>
                <span class="badge highlight">Updated: {now_str}</span>
            </div>
            <button class="scan-btn" onclick="triggerParentScan()">🚀 Scan Now</button>
        </header>

        <!-- Main Layout Row (Left: Leaderboard + Table, Right: Market Indices Sidebar) -->
        <div class="main-layout-row">
            <!-- Left Column: Top Leaderboard and Table -->
            <div class="main-left-column">
                <!-- Top Leaderboard -->
                <div class="section-title">
                    <span>⚡</span> Top Leaderboard
                </div>
                <div class="top-grid">
                    {"".join([f'''
                    <div class="top-card" style="--card-accent-color: {bg_colors.get(x['Symbol'], '#1e293b')}; --card-text-color: {text_colors.get(x['Symbol'], '#ffffff')};">
                        <div class="card-header">
                            <span class="ticker-name">{x['Symbol']}</span>
                            <span class="rank-badge">{i+1}</span>
                        </div>
                        <div>
                            <div class="rs-badge">{x['Mansfield_RS']:.2f}</div>
                            <div class="mcap-subtext">{f"{x['Market_Cap_M']:,.0f}M Baht" if pd.notna(x['Market_Cap_M']) else 'N/A'}</div>
                        </div>
                    </div>
                    ''' for i, x in enumerate(top_15)])}
                </div>

                <!-- Full Interactive Table -->
                <div class="table-container-card">
                    <div class="controls-row">
                        <div class="search-wrapper">
                            <!-- SVG Search Icon -->
                            <svg class="search-icon" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                            </svg>
                            <input type="text" id="searchInput" class="search-input" onkeyup="filterTable()" placeholder="Search symbol...">
                        </div>
                        <div class="mcap-filter-wrapper">
                            <input type="number" id="mcapInput" class="mcap-input" onkeyup="filterTable()" onchange="filterTable()" placeholder="Min Market Cap (M Baht)...">
                        </div>
                        <div class="stats-summary">
                            Showing <strong id="visibleCount">{len(all_stocks)}</strong> of <strong>{len(all_stocks)}</strong> Stocks
                        </div>
                    </div>
                    <div class="table-responsive">
                        <table id="rankingTable">
                            <thead>
                                <tr>
                                    <th onclick="sortTable(0)">Rank ↕</th>
                                    <th onclick="sortTable(1)">Symbol ↕</th>
                                    <th onclick="sortTable(2)">Last Price ↕</th>
                                    <th onclick="sortTable(3)">Chg (%) ↕</th>
                                    <th onclick="sortTable(4)">Market Cap ↕</th>
                                    <th onclick="sortTable(5)">IAA Consensus ↕</th>
                                    <th onclick="sortTable(6)">Mansfield RS ↕</th>
                                    <th>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {"".join([f'''
                                <tr>
                                    <td class="rank-cell">{i+1}</td>
                                    <td class="symbol-cell"><a href="https://www.tradingview.com/chart/?symbol=SET:{x['Symbol']}" target="_blank" class="tv-link">{x['Symbol']}</a></td>
                                    <td class="price-cell">{f"{x['Last_Price']:.2f}" if pd.notna(x['Last_Price']) else 'N/A'}</td>
                                    <td class="chg-cell {('chg-positive' if x['Chg_Pct'] > 0 else ('chg-negative' if x['Chg_Pct'] < 0 else 'chg-zero')) if pd.notna(x['Chg_Pct']) else 'chg-zero'}">
                                        {f"{'+' if x['Chg_Pct'] > 0 else ''}{x['Chg_Pct']:.2f}%" if pd.notna(x['Chg_Pct']) else 'N/A'}
                                    </td>
                                    <td class="mcap-cell">
                                        {f"{x['Market_Cap_M']:,.0f}M" if pd.notna(x['Market_Cap_M']) else 'N/A'}
                                    </td>
                                    <td class="consensus-cell">
                                        {get_consensus_html(x)}
                                    </td>
                                    <td class="rs-cell">
                                        <span class="rs-pill-value" style="background-color: {bg_colors.get(x['Symbol'], '#1e293b')}; color: {text_colors.get(x['Symbol'], '#ffffff')};">
                                            {x['Mansfield_RS']:.2f}
                                        </span>
                                    </td>
                                    <td class="status-cell">
                                        <span class="status-badge {('status-bullish' if x['Mansfield_RS'] > 0 else ('status-bearish' if x['Mansfield_RS'] < -10 else 'status-neutral'))}">
                                            {('Bullish' if x['Mansfield_RS'] > 0 else ('Bearish' if x['Mansfield_RS'] < -10 else 'Neutral'))}
                                        </span>
                                    </td>
                                </tr>
                                ''' for i, x in enumerate(all_stocks)])}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- Right Column: Sidebar (Market Indices) -->
            <div class="main-right-column">
                <div class="section-title">
                    <span>🌍</span> Market Indices
                </div>
                <div class="indices-card">
                    <div class="index-row-header">
                        <span>INDEX</span>
                        <span>LAST</span>
                        <span>CHG</span>
                    </div>
                    <div class="indices-list">
                        {indices_list_html}
                    </div>
                </div>
            </div>
        </div>
    <script>
        function filterTable() {{
            let searchInput = document.getElementById("searchInput").value.toUpperCase();
            let mcapInput = parseFloat(document.getElementById("mcapInput").value) || 0;
            let table = document.getElementById("rankingTable");
            let tr = table.getElementsByTagName("tr");
            let count = 0;
            
            for (let i = 1; i < tr.length; i++) {{
                let symbolTd = tr[i].getElementsByTagName("td")[1]; // Symbol column
                let mcapTd = tr[i].getElementsByTagName("td")[4]; // Market Cap column is now index 4
                
                if (symbolTd && mcapTd) {{
                    let symbolText = symbolTd.textContent || symbolTd.innerText;
                    let mcapText = mcapTd.textContent.replace(/,/g, '').replace('M', '').trim();
                    let mcapValue = parseFloat(mcapText);
                    if (isNaN(mcapValue)) mcapValue = 0;
                    
                    let matchesSearch = symbolText.toUpperCase().indexOf(searchInput) > -1;
                    let matchesMcap = mcapValue >= mcapInput;
                    
                    if (matchesSearch && matchesMcap) {{
                        tr[i].style.display = "";
                        count++;
                    }} else {{
                        tr[i].style.display = "none";
                    }}
                }}
            }}
            document.getElementById("visibleCount").innerText = count;
        }}

        let sortDirections = [1, 1, 1, 1, 1, 1, 1, 1]; // Toggle direction for each column (8 columns total)
        
        function sortTable(columnIndex) {{
            let table = document.getElementById("rankingTable");
            let tbody = table.tBodies[0];
            let rows = Array.from(tbody.rows);
            let isNumeric = (columnIndex === 0 || columnIndex === 2 || columnIndex === 3 || columnIndex === 4 || columnIndex === 5 || columnIndex === 6); // Rank, Last Price, Chg %, Market Cap, IAA Consensus, or Mansfield RS
            
            let direction = sortDirections[columnIndex];
            
            rows.sort((rowA, rowB) => {{
                let cellA = rowA.cells[columnIndex].textContent.trim();
                let cellB = rowB.cells[columnIndex].textContent.trim();
                
                if (isNumeric) {{
                    let valA = parseFloat(cellA.replace(/,/g, '').replace('M', '').replace('%', '').replace('+', ''));
                    let valB = parseFloat(cellB.replace(/,/g, '').replace('M', '').replace('%', '').replace('+', ''));
                    if (isNaN(valA)) valA = -999999999;
                    if (isNaN(valB)) valB = -999999999;
                    return direction * (valA - valB);
                }} else {{
                    return direction * cellA.localeCompare(cellB);
                }}
            }});
            
            // Toggle direction
            sortDirections[columnIndex] = -direction;
            
            // Re-append to DOM
            rows.forEach(row => tbody.appendChild(row));
            
            // Reset headers visuals
            let ths = table.getElementsByTagName("th");
            for(let i=0; i<ths.length; i++) {{
                let baseText = ths[i].textContent.replace(/[▲▼↕]/g, "").trim();
                if(i === 7) {{
                    ths[i].innerHTML = baseText; // No arrow for Status (index 7)
                }} else if(i === columnIndex) {{
                    ths[i].innerHTML = baseText + (direction === 1 ? " ▲" : " ▼");
                }} else {{
                    ths[i].innerHTML = baseText + " ↕";
                }}
            }}
        }}

        // Hide scan button if inside iframe (Streamlit Cloud sandbox)
        if (window.self !== window.top) {{
            const scanBtn = document.querySelector('.scan-btn');
            if (scanBtn) {{
                scanBtn.style.display = 'none';
            }}
        }}

        function triggerParentScan() {{
            window.parent.location.href = window.location.origin + "/?scan=true";
        }}
    </script>
</body>
</html>
"""
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_template)
        print(f"[SUCCESS] Dashboard generated successfully at: '{output_path}'")
        return True
    except Exception as e:
        print(f"[ERROR] Error writing HTML report: {e}")
        return False

def run_scan(stock_source, benchmark, ma_length, min_mcap, output_path, progress_callback=None):
    """
    Runs the entire scan process programmatically.
    stock_source can be a file path (str), a list of symbols (list), or a pandas DataFrame.
    """
    if progress_callback:
        progress_callback("Processing stock list...", 0.1)
    
    if isinstance(stock_source, list):
        symbols = sorted(list(set(stock_source)))
    elif isinstance(stock_source, pd.DataFrame):
        possible_cols = ['Symbol', 'Ticker', 'SYMBOL', 'TICKER', 'Stock', 'symbol']
        found_col = next((c for c in possible_cols if c in stock_source.columns), stock_source.columns[0])
        raw_stocks = stock_source[found_col].dropna().astype(str).tolist()
        symbols = []
        exclude_list = [
            'BANKING', 'FINANCIALS', 'INSURANCE', 'ENERG', 'FOOD', 'COMM', 'ICT',
            'PROP', 'CONMAT', 'AGRI', 'AUTO', 'HOME', 'PERSON', 'PETRO', 'PKG',
            'PROF', 'PAPER', 'MEDIA', 'MINE', 'STEEL', 'TOURISM', 'TRANS', 'ETRON', 'HELTH',
            'MCHAI', 'LE', 'MPAT', 'BWORK', 'FD', 'MSTOR', 'SJ', 'TUPF', 'SEED', 'QCON'
        ]
        for s in raw_stocks:
            clean_s = re.sub(r'[^a-zA-Z0-9]', '', s).strip()
            if not clean_s or clean_s.isdigit():
                continue
            if any(ex == clean_s.upper() for ex in exclude_list):
                continue
            if s.startswith('--') or s.startswith('.'):
                continue
            symbols.append(clean_s)
        symbols = sorted(list(set(symbols)))
    else:
        symbols = clean_stock_list(stock_source)
        
    if not symbols:
        return False, "No valid stock symbols found for analysis."

    if progress_callback:
        progress_callback(f"Successfully loaded {len(symbols)} stocks. Downloading price data and calculating RS...", 0.3)
        
    ranking_df = calculate_rs_ranking(symbols, benchmark, ma_length)
    if ranking_df.empty:
        return False, "Failed to download price data or calculate RS."
        
    succeeded_symbols = ranking_df['Symbol'].tolist()
    
    if progress_callback:
        progress_callback(f"RS calculated for {len(succeeded_symbols)} stocks. Fetching market capitalization...", 0.6)
        
    mcaps, consensus = fetch_market_caps(succeeded_symbols)
    ranking_df['Market_Cap_M'] = ranking_df['Symbol'].map(mcaps)
    ranking_df['Target_Mean_Price'] = ranking_df['Symbol'].map(consensus)
    
    if min_mcap > 0:
        if progress_callback:
            progress_callback(f"Filtering stocks by Market Cap >= {min_mcap:,.0f}M Baht...", 0.8)
        ranking_df = ranking_df[
            (ranking_df['Market_Cap_M'].notna()) & 
            (ranking_df['Market_Cap_M'] >= min_mcap)
        ]
        ranking_df.reset_index(drop=True, inplace=True)
        ranking_df.index = ranking_df.index + 1
        
        if ranking_df.empty:
            return False, "No stocks passed the market cap filter."

    if progress_callback:
        progress_callback("Generating HTML dashboard...", 0.9)
        
    success = build_html_report(ranking_df, benchmark, ma_length, output_path)
    
    if progress_callback:
        progress_callback("Scan completed!", 1.0)
        
    if success:
        return True, ranking_df
    else:
        return False, "Error saving the HTML report."

def main():
    parser = argparse.ArgumentParser(description="Stan Weinstein Mansfield Relative Strength Ranking Tool")
    parser.add_argument("--csv", type=str, default=r"C:\Users\sucha\Downloads\set_stocks.csv.csv",
                        help="Path to the CSV file containing stock symbols")
    parser.add_argument("--benchmark", type=str, default="^SET.BK",
                        help="Benchmark ticker symbol (e.g. ^SET.BK)")
    parser.add_argument("--ma", type=int, default=200,
                        help="Moving Average period for Mansfield RS (default: 200)")
    parser.add_argument("--min-mcap", type=float, default=0.0,
                        help="Minimum market cap filter in Million Baht (e.g. 5000 for 5,000M Baht)")
    parser.add_argument("--output", type=str, default="rs_ranking_report.html",
                        help="Output path for the HTML dashboard")
    parser.add_argument("--no-open", action="store_true",
                        help="Prevent automatically opening the report in the default browser")
    
    args = parser.parse_args()
    
    print("="*60)
    print("STAN WEINSTEIN MANSFIELD RS RANKING TOOL")
    print("="*60)
    print(f"CSV Path:       {args.csv}")
    print(f"Benchmark:      {args.benchmark}")
    print(f"MA Period:      {args.ma} bars")
    if args.min_mcap > 0:
        print(f"Min Market Cap: {args.min_mcap:,.0f} Million Baht")
    print(f"Output File:     {args.output}")
    print("="*60)

    # Call run_scan
    success, result = run_scan(
        stock_source=args.csv,
        benchmark=args.benchmark,
        ma_length=args.ma,
        min_mcap=args.min_mcap,
        output_path=args.output
    )
    
    if not success:
        print(f"[ERROR] Scan failed: {result}")
        return

    # Output basic text stats to console
    print("\n=== TOP 15 STOCKS ===")
    print("-" * 70)
    console_df = result.head(15).copy()
    console_df['Market_Cap_M'] = console_df['Market_Cap_M'].apply(lambda val: f"{val:,.0f}M" if pd.notna(val) else 'N/A')
    print(console_df.to_string(index=True))
    print("-" * 70)
    
    # Open report in browser
    if success and not args.no_open:
        absolute_output_path = os.path.abspath(args.output)
        print(f"[INFO] Opening report: {absolute_output_path}")
        webbrowser.open(f"file:///{absolute_output_path}")

if __name__ == "__main__":
    main()

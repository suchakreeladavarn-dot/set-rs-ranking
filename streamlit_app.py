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

# Custom premium styling
st.markdown("""
<style>
    /* Styling for Title */
    .app-header {
        font-family: 'Outfit', sans-serif;
        background: linear-gradient(135deg, #090d16, #111827, #1e3a8a);
        padding: 2rem;
        border-radius: 20px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 10px 25px rgba(0,0,0,0.3);
        border: 1px solid rgba(255, 255, 255, 0.08);
        background-image: 
            radial-gradient(at 0% 0%, rgba(29, 78, 216, 0.25) 0px, transparent 50%),
            radial-gradient(at 100% 100%, rgba(17, 24, 39, 0.8) 0px, transparent 50%);
    }
    .app-header h1 {
        margin: 0;
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #ffffff 30%, #a5b4fc 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .app-header p {
        margin: 0.5rem 0 0 0;
        font-size: 1rem;
        color: #9ca3af;
    }
    /* Buttons styling */
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
</style>
""", unsafe_allow_html=True)

# App Title Area
st.markdown("""
<div class="app-header">
    <h1>📈 Stan Weinstein RS Ranking Dashboard</h1>
    <p>ระบบสแกนและจัดอันดับความแข็งแกร่งสัมพัทธ์ของหุ้นด้วย Mansfield Relative Strength (RS) คัดกรองหุ้นแนวโน้มขาขึ้นรอบใหญ่</p>
</div>
""", unsafe_allow_html=True)

# Sidebar Configuration
st.sidebar.markdown("### ⚙️ ตั้งค่าการสแกน")

benchmark = st.sidebar.text_input(
    "Benchmark Ticker (ดัชนีอ้างอิง)",
    value="^SET.BK",
    help="เช่น ^SET.BK (ดัชนี SET ของไทย), ^GSPC (ดัชนี S&P 500)"
).strip()

ma_length = st.sidebar.number_input(
    "Moving Average (สัปดาห์/วัน)",
    min_value=10,
    max_value=300,
    value=200,
    step=10,
    help="ช่วงเวลาที่ใช้คำนวณเส้นค่าเฉลี่ย Mansfield RS (ค่าปกติคือ 200 วัน/สัปดาห์ ในสูตรทั่วไปดั้งเดิมใช้ 30 สัปดาห์หรือ 200 วัน)"
)

min_mcap = st.sidebar.number_input(
    "ขั้นต่ำ Market Cap (ล้านบาท)",
    min_value=0.0,
    value=0.0,
    step=500.0,
    help="ใช้สำหรับกรองหุ้นที่มีมูลค่าหลักทรัพย์ตามราคาตลาดต่ำกว่าเกณฑ์ออก (ระบุ 0 หากไม่ต้องการกรอง)"
)

# Stock Source Selection
st.sidebar.markdown("### 📋 แหล่งข้อมูลรายชื่อหุ้น")
stock_source_type = st.sidebar.selectbox(
    "เลือกรายชื่อหุ้น:",
    ["ใช้รายชื่อหุ้นเริ่มต้น (709 หุ้น)", "อัปโหลดไฟล์ CSV ของตนเอง"]
)

stock_source = "set_stocks.csv"
uploaded_file = None

if stock_source_type == "อัปโหลดไฟล์ CSV ของตนเอง":
    uploaded_file = st.sidebar.file_uploader(
        "อัปโหลดไฟล์ CSV ที่มีคอลัมน์ symbol",
        type=["csv"],
        help="ไฟล์ต้องมีหัวคอลัมน์ชื่อ symbol, Ticker, หรือ SYMBOL ตัวอย่างเช่น symbol ในบรรทัดแรก และชื่อหุ้นในบรรทัดถัดไป"
    )
    if uploaded_file is not None:
        try:
            df_uploaded = pd.read_csv(uploaded_file)
            stock_source = df_uploaded
            st.sidebar.success(f"อัปโหลดสำเร็จ! พบข้อมูล {len(df_uploaded)} แถว")
        except Exception as e:
            st.sidebar.error(f"ไม่สามารถอ่านไฟล์ได้: {str(e)}")
            stock_source = None
    else:
        st.sidebar.warning("กรุณาอัปโหลดไฟล์ CSV หรือใช้รายชื่อเริ่มต้น")
        stock_source = None

# Action Area
st.markdown("### 🔍 ดำเนินการค้นหา")
col_btn, col_info = st.columns([1, 3])

with col_btn:
    analyze_button = st.button("🚀 เริ่มคำนวณและสแกนหุ้น")

output_filename = "rs_ranking_report.html"

# Run calculation if button is clicked
if analyze_button:
    if stock_source is None:
        st.error("กรุณาเตรียมแหล่งข้อมูลรายชื่อหุ้นที่ถูกต้องก่อนเริ่มสแกน")
    else:
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        
        def update_progress(message, percent):
            status_text.markdown(f"**สถานะการคำนวณ:** {message}")
            progress_bar.progress(percent)
            
        with st.spinner("ระบบกำลังแสกนและดาวน์โหลดข้อมูล..."):
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
                    st.success("คำนวณและสแกนเสร็จสิ้นเรียบร้อยแล้ว!")
                    st.balloons()
                else:
                    st.error(f"การสแกนล้มเหลว: {result}")
            except Exception as e:
                st.error(f"เกิดข้อผิดพลาดในการวิเคราะห์: {str(e)}")
                st.info("คำแนะนำ: กรุณาตรวจสอบว่าชื่อย่อของ Benchmark หรือไฟล์ CSV ถูกต้อง")

# Render Area: Load and show report if it exists
if os.path.exists(output_filename):
    st.markdown("---")
    st.markdown("### 📊 รายงานผลการจัดอันดับ RS Ranking ล่าสุด")
    
    # Download Button
    try:
        with open(output_filename, "r", encoding="utf-8") as f:
            html_content = f.read()
            
        st.download_button(
            label="📥 ดาวน์โหลดไฟล์รายงาน HTML",
            data=html_content,
            file_name="rs_ranking_report.html",
            mime="text/html"
        )
        
        # Embed the generated HTML
        components.html(html_content, height=1200, scrolling=True)
    except Exception as e:
        st.error(f"ไม่สามารถโหลดไฟล์รายงานมาแสดงผลได้: {str(e)}")
else:
    st.info("ยังไม่มีข้อมูลรายงานล่าสุด กรุณากดปุ่มด้านบนเพื่อเริ่มทำการสแกนหุ้นเป็นครั้งแรก")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #6b7280; font-size: 0.85rem; padding: 1rem 0;">
    Stan Weinstein Mansfield RS Web Dashboard • อ้างอิงข้อมูลเรียลไทม์จาก Yahoo Finance • ออกแบบมาเพื่อเปิดดูรายงานได้ทุกที่ ทุกเวลา
</div>
""", unsafe_allow_html=True)

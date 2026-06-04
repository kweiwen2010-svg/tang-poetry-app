import streamlit as st
import sqlite3
import os
import json
from gtts import gTTS

# ==========================================
# 0. 環境依賴導入（安全沙盒隔離）
# ==========================================
# 嘗試載入環境變數設定
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 嘗試載入新版 google-genai SDK
try:
    from google import genai
except ImportError:
    genai = None

# ==========================================
# 1. 系統環境設定與快取目錄初始化
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 確保路徑完全使用小寫相容 Linux 環境
DB_PATH = os.path.join(BASE_DIR, "data", "poetry.db")
AUDIO_DIR = os.path.join(BASE_DIR, "data", "audio_cache")
TXT_CACHE_DIR = os.path.join(BASE_DIR, "data", "storyboard_cache")

# 自動建立本機與雲端所需的快取資料夾
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(TXT_CACHE_DIR, exist_ok=True)

def get_db_connection():
    """建立穩定的資料庫連線"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  
    return conn

# 設定網頁標題與風格
st.set_page_config(page_title="唐詩全量深度素養伴學系統", page_icon="🏮", layout="centered")

# CSS 視覺美化（相容手機板瀏覽與防爆框設計）
st.markdown("""
<style>
    .poem-title { font-size: 24px; font-weight: bold; color: #2C3E50; margin-bottom: 5px; }
    .poem-author { font-size: 15px; color: #7F8C8D; margin-bottom: 15px; }
    .poem-content { font-size: 18px; line-height: 1.8; color: #34495E; background-color: #F8F9F9; padding: 15px; border-radius: 8px; border-left: 5px solid #1ABC9C; margin-bottom: 20px; white-space: pre-line; }
    .teacher-box { background-color: #EBF5FB; padding: 15px; border-radius: 8px; border-left: 5px solid #3498DB; margin-top: 15px; margin-bottom: 15px; }
    .story-box { background-color: #F4ECF7; padding: 15px; border-radius: 8px; border-left: 5px solid #9B59B6; margin-bottom: 15px; }
    .storyboard-box { background-color: #FDF2E9; padding: 15px; border-radius: 8px; border-left: 5px solid #E67E22; margin-top: 10px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

st.title("🏮 唐詩全量深度素養伴學系統")
st.write("精選名家資料庫已成功對接，全面支援動態演算法自動出題。")

# ==========================================
# 2. 核心資料庫讀取與文字轉語音機制
# ==========================================
if not os.path.exists(DB_PATH):
    st.error(f"❌ 系統找不到資料庫檔案！偵測路徑為: {DB_PATH}")
    st.info("💡 請確認您的專案中包含 `data/poetry.db` 且已確實推送到 GitHub 上。")
else:
    try:
        # 讀取全詩選單列表
        conn = get_db_connection()
        cursor = conn.cursor()
        # 使用嚴格全小寫 SQL 語法，確保 Linux 伺服器不會拋出 OperationalError
        cursor.execute("SELECT id, title, author, category FROM poems")
        poems_list = cursor.fetchall()
        conn.close()
        
        if not
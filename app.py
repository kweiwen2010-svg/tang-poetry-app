import streamlit as st
import sqlite3
import os

# ==========================================
# 1. 核心套件導入（內建安全降級沙盒防護）
# ==========================================
# 防禦 gTTS 遺失
try:
    from gtts import gTTS
except ImportError:
    gTTS = None

# 防禦 python-dotenv 遺失
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 防禦 google-genai 遺失
try:
    from google import genai
except ImportError:
    genai = None

# ==========================================
# 2. 系統環境與路徑初始化
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "poetry.db")
AUDIO_DIR = os.path.join(BASE_DIR, "data", "audio_cache")
TXT_CACHE_DIR = os.path.join(BASE_DIR, "data", "storyboard_cache")

# 自動建立快取資料夾
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(TXT_CACHE_DIR, exist_ok=True)

def get_db_connection():
    """建立穩定的資料庫連線"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  
    return conn

# 設定網頁基本配置與全域美化 CSS
st.set_page_config(page_title="唐詩全量深度素養伴學系統", page_icon="🏮", layout="centered")
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
# 3. 資料庫主邏輯與頁面渲染
# ==========================================
if not os.path.exists(DB_PATH):
    st.error(f"❌ 系統找不到資料庫檔案！偵測路徑為: {DB_PATH}")
    st.info("💡 請確認您的專案中包含 `data/poetry.db` 且已推送到 GitHub 上。")
else:
    try:
        # 1. 讀取全詩選單列表
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, author, category FROM poems")
        poems_list = cursor.fetchall()
        conn.close()
        
        if not poems_list:
            st.warning("⚠️ 資料庫中目前沒有詩詞資料。")
        else:
            # 2. 渲染動態下拉選單
            poem_options = [f"《{p['title']}》 - {p['author']} [{p['category'] or '未分類'}]" for p in poems_list]
            selected_index = st.selectbox("請選擇你想深度研讀的唐詩：", range(len(poem_options)), format_func=lambda x: poem_options[x])
            
            target_poem_id = poems_list[selected_index]["id"]
            
            # 3. 撈取該首詩的完整細節
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM poems WHERE id = ?", (target_poem_id,))
            poem = cursor.fetchone()
            conn.close()
            
            # 4. 顯示網頁主體內容
            st.markdown(f'<div class="poem-title">《{poem["title"]}》</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="poem-author">【唐】{poem["author"]}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="poem-content">{poem["content"]}</div>', unsafe_allow_html=True)
            
            # 🔊 功能一：詩詞語音美學朗讀
            st.subheader("🔊 詩詞語音美學朗讀")
            if gTTS is None:
                st.warning("⚠️ 系統偵測到目前環境缺少 `gTTS` 套件，語音播放功能暫時停用。")
            else:
                poem_audio_path = os.path.join(AUDIO_DIR, f"poem_{target_poem_id}.mp3")
                if not os.path.exists(poem_audio_path):
                    try:
                        tts_text = f"{poem['title']}。作者：{poem['author']}。{poem['content']}"
                        tts = gTTS(text=tts_text, lang='zh-TW', slow=False)
                        tts.save(poem_audio_path)
                    except Exception as tts_err:
                        st.error(f"語音產生失敗: {tts_err}")
                
                if os.path.exists(poem_audio_path):
                    with open(poem_audio_path, "rb") as audio_file:
                        st.audio(audio_file.read(), format="audio/mp3")
            
            # 5. 顯示背景與心靈導讀
            if poem["story"]:
                st.markdown(f'<div class="story-box"><strong>📖 詩詞背景與心靈導讀：</strong><br><br>{poem["story"]}</div>', unsafe_allow_html=True)

            # ==========================================
            # 🎬 功能二：AI 電影級五幕分鏡劇本
            # ==========================================
            st.write("---")
            st.subheader("🎬 詩詞意境 - AI 電影級五幕分鏡劇本")
            
            with st.expander("✨ 點擊解鎖：大導級視覺畫面重構與鏡頭美學描述", expanded=False):
                sb_txt_path = os.path.join(TXT_CACHE_DIR, f"sb_{target_poem_id}.txt")
                sb_audio_path = os.path.join(AUDIO_DIR, f"sb_{target_poem_id}.mp3")
                storyboard_text = ""
                
                # 優先檢查快取，防止重複消耗 API 流量與觸發 503 限流
                if os.path.exists(sb_txt_path):
                    with open(sb_txt_path, "r", encoding="utf-8") as f:
                        storyboard_text = f.read()
                else:
                    if genai is None:
                        st.warning("⚠️ 系統目前未能成功載入 `google-genai` 套件，無法
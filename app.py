import streamlit as st
import sqlite3
import os
import json
import requests  # Python 內建/Streamlit 自帶，百分之百相容
from gtts import gTTS

# ==========================================
# 1. 系統環境設定與資料庫路徑
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "poetry.db")
AUDIO_DIR = os.path.join(BASE_DIR, "data", "audio_cache")
TXT_CACHE_DIR = os.path.join(BASE_DIR, "data", "storyboard_cache")

os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(TXT_CACHE_DIR, exist_ok=True)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  
    return conn

st.set_page_config(page_title="唐詩全量深度素養伴學系統", page_icon="🏮", layout="centered")

# CSS 視覺美化 (手機最佳化版)
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
# 🌟 核心直連黑魔法：繞過 SDK 套件，直接發送 HTTP 請求
# ==========================================
def call_gemini_api(prompt_text):
    """使用原生 HTTP 請求呼叫 Gemini 2.5 Flash API"""
    # 優先從 Streamlit Secrets 讀取，其次讀取環境變數
    api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        return "ERROR_NO_KEY"
    
    # Gemini 官方標準 REST API 端點
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": prompt_text}]
        }]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            res_json = response.json()
            # 解析 Gemini 返回的標準 JSON 結構
            return res_json['candidates'][0]['content']['parts'][0]['text']
        elif response.status_code == 503:
            return "ERROR_503"
        else:
            return f"ERROR_API_FAIL: {response.status_code} - {response.text}"
    except Exception as e:
        return f"ERROR_CONNECTION: {str(e)}"

# ==========================================
# 2. 資料庫讀取與渲染
# ==========================================
if not os.path.exists(DB_PATH):
    st.error(f"❌ 雲端找不到資料庫檔案！偵測路徑為: {DB_PATH}")
else:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, author, category FROM poems")
        poems_list = cursor.fetchall()
        conn.close()
        
        if not poems_list:
            st.warning("⚠️ 資料庫中目前沒有詩詞資料。")
        else:
            poem_options = [f"《{p['title']}》 - {p['author']} [{p['category'] or '未分類'}]" for p in poems_list]
            selected_index = st.selectbox("請選擇你想深度研讀的唐詩：", range(len(poem_options)), format_func=lambda x: poem_options[x])
            
            target_poem_id = poems_list[selected_index]["id"]
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM poems WHERE id = ?", (target_poem_id,))
            poem = cursor.fetchone()
            conn.close()
            
            st.markdown(f'<div class="poem-title">《{poem["title"]}》</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="poem-author">【唐】{poem["author"]}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="poem-content">{poem["content"]}</div>', unsafe_allow_html=True)
            
            # 🔊 功能一：詩詞語音美學朗讀
            st.subheader("🔊 詩詞語音美學朗讀")
            poem_audio_path = os.path.join(AUDIO_DIR, f"poem_{target_poem_id}.mp3")
            tts_text = f"{poem['title']}。作者：{poem['author']}。{poem['content']}"
            
            if not os.path.exists(poem_audio_path):
                try:
                    tts = gTTS(text=tts_text, lang='zh-TW', slow=False)
                    tts.save(poem_audio_path)
                except:
                    pass
            
            if os.path.exists(poem_audio_path):
                with open(poem_audio_path, "rb") as audio_file:
                    st.audio(audio_file.read(), format="audio/mp3")
            
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
                
                if os.path.exists(sb_txt_path):
                    with open(sb_txt_path, "r", encoding="utf-8") as f:
                        storyboard_text = f.read()
                else:
                    with st.spinner("🎥 正在引導 AI 導演為這首詩重構視覺畫面..."):
                        prompt = f"請將《{poem['title']}》的意境設計成精美電影五幕分鏡劇本，包含鏡頭運動與光影色調。請直接輸出劇本內容。"
                        result = call_gemini_api(prompt)
                        
                        if result == "ERROR_NO_KEY":
                            st.error("❌ 尚未在 Streamlit Secrets 中設定 GEMINI_API_KEY。")
                        elif result == "ERROR_503":
                            st.error("🏮 AI 大導目前正在品茶尋找靈感（API 流量過載 503）。請稍候重試。")
                        elif result.startswith("ERROR"):
                            st.error(f"❌ 呼叫 AI 失敗：{result}")
                        else:
                            storyboard_text = result
                            with open(sb_txt_path, "w", encoding="utf-8") as f:
                                f.write(storyboard_text)
                
                if storyboard_text:
                    if not os.path.exists(sb_audio_path):
                        try:
                            clean_text = storyboard_text.replace("**", "").replace("*", "").replace("-", "")
                            sb_tts = gTTS(text=f"接下來為您導覽電影美學分鏡。{clean_text}", lang='zh-TW', slow=False)
                            sb_tts.save(sb_audio_path)
                        except:
                            pass
                    
                    if os.path.exists(sb_audio_path):
                        st.write("🎵 **聆聽大導級鏡頭美學語音導覽：**")
                        with open(sb_audio_path, "rb") as sb_audio_file:
                            st.audio(sb_audio_file.read(), format="audio/mp3")
                    st.markdown(f'<div class="storyboard-box">{storyboard_text.replace("\n", "<br>")}</div>', unsafe_allow_html=True)

            # ==========================================
            # 3. 伴學老師模組
            # ==========================================
            st.write("---")
            st.subheader("🤝 與伴學老師對話")
            user_thought = st.text_area("讀完這首詩，你感受到了什麼？", key=f"thought_{target_poem_id}")
            
            if st.button("發送想法給伴學老師", key=f"btn_{target_poem_id}"):
                if user_thought.strip():
                    with st.spinner("伴學老師正在細細品讀..."):
                        prompt = f"學生讀完《{poem['title']}》，感想是：{user_thought}。請以溫慢的文學素養角度，給予溫暖的引導與回饋。"
                        result = call_gemini_api(prompt)
                        
                        if result == "ERROR_NO_KEY":
                            st.error("❌ 尚未在 Streamlit Secrets 中設定 GEMINI_API_KEY。")
                        elif result == "ERROR_503":
                            st.error("🏮 老師正在批改其他同學的作業（API 流量過載 503）。請稍候重試。")
                        elif result.startswith("ERROR"):
                            st.error(f"❌ 呼叫 AI 失敗：{result}")
                        else:
                            st.markdown(f'<div class="teacher-box"><strong>🏮 伴學老師的心靈回饋：</strong><br><br>{result}</div>', unsafe_allow_html=True)

    except Exception as db_err:
        st.error(f"❌ 系統錯誤：{db_err}")
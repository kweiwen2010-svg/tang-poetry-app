import streamlit as st
import sqlite3
import os
import glob
import time
from gtts import gTTS
from google import genai
from google.genai import types
from dotenv import load_dotenv
from streamlit_mic_recorder import mic_recorder

# ==========================================
# 1. 基礎設定與環境初始化
# ==========================================
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "poetry.db")
AUDIO_DIR = os.path.join(BASE_DIR, "data", "audio_cache")

os.makedirs(AUDIO_DIR, exist_ok=True)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  
    return conn

st.title("🏮 唐詩全量深度素養伴學系統")

# ==========================================
# 2. 資料庫讀取邏輯
# ==========================================
if not os.path.exists(DB_PATH):
    st.error(f"❌ 找不到資料庫檔案！請檢查路徑：{DB_PATH}")
else:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, author, category FROM poems")
    poems_list = cursor.fetchall()
    
    if not poems_list:
        st.warning("⚠️ poetry.db 資料庫內無詩詞資料。")
        conn.close()
    else:
        # 詩詞選擇下拉選單
        poem_options = [f"《{p['title']}》 - {p['author']} [{p['category'] or '未分類'}]" for p in poems_list]
        selected_index = st.selectbox("🎯 請選擇你想深度研讀的唐詩：", range(len(poem_options)), format_func=lambda x: poem_options[x])
        
        target_poem_id = poems_list[selected_index]["id"]
        
        # 撈取單首詩詳細資料
        cursor.execute("SELECT * FROM poems WHERE id = ?", (target_poem_id,))
        poem = cursor.fetchone()
        conn.close()
        
        st.write("---")
        
        # ==========================================
        # 3. 詩詞呈現與語音朗讀區塊（標準單欄）
        # ==========================================
        st.subheader(f"《{poem['title']}》")
        st.text(f"作者：【唐】{poem['author']}")
        
        # 詩詞正文
        st.info(poem['content'])
        
        # 語音朗讀
        st.write("🔊 **詩詞語音美學朗讀：**")
        poem_audio_path = os.path.join(AUDIO_DIR, f"poem_{target_poem_id}.mp3")
        
        if not os.path.exists(poem_audio_path):
            try:
                tts_text = f"{poem['title']}。作者：{poem['author']}。{poem['content']}"
                tts = gTTS(text=tts_text, lang='zh-TW', slow=False)
                tts.save(poem_audio_path)
            except Exception as e:
                st.error(f"gTTS 本文語音生成失敗: {e}")
        
        if os.path.exists(poem_audio_path):
            with open(poem_audio_path, "rb") as audio_file:
                st.audio(audio_file.read(), format="audio/mp3")
                
        st.write("---")
        
        # ==========================================
        # 4. 經典導讀區塊（恢復預設紫框樣式）
        # ==========================================
        st.write("### 📖 詩詞背景與心靈導讀")
        
        api_key = os.environ.get("GEMINI_API_KEY")
        dynamic_story_text = ""
        
        # 透過 Gemini 生成動態故事
        if api_key:
            try:
                client = genai.Client(api_key=api_key)
                story_prompt = (
                    f"你是一位擅長將枯燥古文轉化為動人故事的資深文學導師。\n"
                    f"請根據以下這首詩的資料，為研讀的學生撰寫一份極具深度、有畫面感且充滿溫度的『心靈導讀』。\n\n"
                    f"詩名：《{poem['title']}》\n"
                    f"作者：{poem['author']}\n"
                    f"原文內容：\n{poem['content']}\n"
                    f"參考背景資料：{poem['story'] or '無額外歷史註記'}\n\n"
                    f"請遵循以下限制：\n"
                    f"1. 嚴禁使用罐頭、千篇一律的套話。\n"
                    f"2. 必須用講故事的口吻，深入白話地描繪出詩人寫下這首詩時的『內心糾結、時空背景與靈魂共鳴點』。\n"
                    f"3. 字數嚴格控制在 150 到 220 字之間，分為一個精簡的段落。"
                )
                with st.spinner("正在為您點亮這首詩的靈魂背景..."):
                    response = client.models.generate_content(
                        model='gemini-2.5-flash', 
                        contents=story_prompt
                    )
                    dynamic_story_text = response.text.strip()
            except Exception as e:
                dynamic_story_text = poem['story'] or "暫無背景導讀。"
        else:
            dynamic_story_text = poem['story'] or "暫無背景導讀。"
            
        # 經典導讀提示框
        st.success(f"【經典導讀】{dynamic_story_text}")
        
        st.write("---")

        # ==========================================
        # 🤝 5. 🤝 與伴學老師對話（對話流）
        # ==========================================
        st.write("### 🤝 與伴學老師對話")
        st.write(f"讀完這首詩，你感受到了什麼？（也可以在此回答老師下方的提問喔！）")
        
        if "speech_text" not in st.session_state:
            st.session_state.speech_text = ""

        # 錄音元件
        audio_input = mic_recorder(
            start_prompt="🎤 點我開始用語音說想法",
            stop_prompt="🛑 說完了，停止錄音",
            just_once=True,
            key="mic_input"
        )

        if audio_input and "bytes" in audio_input and api_key:
            with st.spinner("🎙️ 正在將您的語音轉換為精準文字..."):
                try:
                    client = genai.Client(api_key=api_key)
                    audio_bytes = audio_input["bytes"]
                    stt_prompt = "請幫我將這段錄音精準轉換為中文繁體文字，不要加入任何其他多餘的旁白說明。"
                    
                    stt_response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=[
                            types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
                            stt_prompt
                        ]
                    )
                    st.session_state.speech_text = stt_response.text.strip()
                except Exception as stt_err:
                    st.error(f"語音識別發生小錯誤：{stt_err}")

        # 對話表單
        with st.form(key=f"teacher_form_{target_poem_id}"):
            user_thought = st.text_area(
                "分享你的想法：",
                value=st.session_state.speech_text,
                placeholder="請在此輸入文字，或使用上方的語音按鈕錄音輸入..."
            )
            submit_button = st.form_submit_button("發送想法給伴學老師")
            
        if submit_button:
            if not user_thought.strip():
                st.warning("請先輸入你的感受、使用語音錄音或回答問題再送出喔！")
            else:
                st.write(f"🙋 **我的想法/回答：** {user_thought}")
                
                if not api_key:
                    st.error("❌ 本機環境未偵測到 GEMINI_API_KEY！")
                else:
                    with st.spinner("伴學老師正在細細品讀您的想法..."):
                        try:
                            client = genai.Client(api_key=api_key)
                            teacher_prompt = (
                                f"你是一位精通唐詩與文學教育的伴學老師。\n"
                                f"目前研讀的古詩是：《{poem['title']}》，作者：{poem['author']}。\n"
                                f"古詩原文內容：\n{poem['content']}\n\n"
                                f"學生的想法或回答是：『{user_thought}』。\n\n"
                                f"請遵循以下鋼鐵限制給予回饋：\n"
                                f"1. 必須以溫慢、充滿文學素養的溫慢口吻（例如稱呼學生為孩子或同學）回應並引導學生。\n"
                                f"2. 請精準抓取這首詩本身的『核心內涵、關鍵字詞或經典意象』，完美編織回填到你的回饋中。\n"
                                f"3. 關鍵任務：請在回應的最後，根據這首詩的靈魂，動態出一題『與現代生活情境結合的開放式素養思辨題（沒有標準答案）』，強迫學生思考並將古人智慧與現代生活連結。\n"
                                f"4. 字數控制：『全文字數（含出題）嚴格限制在 200 到 250 字之間』，精簡流暢，結構清晰，絕對不要長篇大論。"
                            )
                            
                            response = client.models.generate_content(
                                model='gemini-2.5-flash', 
                                contents=teacher_prompt
                            )
                            teacher_text = response.text.strip()
                            
                            # 呈現老師回饋
                            st.info(f"🏮 **伴學老師的心靈回饋與素養挑戰：**\n\n{teacher_text}")
                            st.caption("💡 *小提示：如果你想繼續回答老師，可以再次使用上方語音按鈕，或在對話框修改後發送。*")
                            
                            st.session_state.speech_text = ""
                            
                            # 伴學老師語音生成
                            try:
                                old_files = glob.glob(os.path.join(AUDIO_DIR, f"teacher_reply_{target_poem_id}_*.mp3"))
                                for fpath in old_files:
                                    try:
                                        os.remove(fpath)
                                    except Exception:
                                        pass
                                
                                timestamp = int(time.time())
                                teacher_audio_path = os.path.join(AUDIO_DIR, f"teacher_reply_{target_poem_id}_{timestamp}.mp3")
                                
                                teacher_tts = gTTS(text=teacher_text, lang='zh-TW', slow=False)
                                teacher_tts.save(teacher_audio_path)
                                
                                st.write("🎵 **聆聽老師的溫慢語音：**")
                                with open(teacher_audio_path, "rb") as teacher_audio_file:
                                    st.audio(teacher_audio_file.read(), format="audio/mp3")
                            except Exception as audio_err:
                                st.error(f"老師語音回饋生成失敗: {audio_err}")
                                
                        except Exception as e:
                            st.error(f"❌ 伴學老師連線失敗：{e}")
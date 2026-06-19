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
        # 4. 經典導讀區塊（引入快取優化，拒絕卡頓）
        # ==========================================
        st.write("### 📖 詩詞背景與心靈導讀")
        
        api_key = os.environ.get("GEMINI_API_KEY")
        
        # 檢查是否需要重新為這首詩生成導讀（切換詩詞時才更新）
        if "current_poem_id" not in st.session_state or st.session_state.current_poem_id != target_poem_id:
            st.session_state.current_poem_id = target_poem_id
            st.session_state.cached_story_text = ""  # 清空舊詩導讀
            
            # 清除上一首詩的對話狀態，避免錯亂
            st.session_state.speech_text = ""
            st.session_state.last_teacher_response = None
            st.session_state.last_user_thought = None
            st.session_state.show_chat_input = False
            if "teacher_audio_path" in st.session_state:
                del st.session_state.teacher_audio_path
        
        # 如果快取裡沒東西，才呼叫 Gemini API
        if not st.session_state.cached_story_text:
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
                        st.session_state.cached_story_text = response.text.strip()
                except Exception as e:
                    st.session_state.cached_story_text = poem['story'] or "暫無背景導讀。"
            else:
                st.session_state.cached_story_text = poem['story'] or "暫無背景導讀。"
            
        # 經典導讀提示框：直接秒讀快取資料
        st.success(f"【經典導讀】{st.session_state.cached_story_text}")
        
        st.write("---")

        # ==========================================
        # 🤝 5. 與伴學老師對話（焦點防禦手機優化版）
        # ==========================================
        st.write("### 🤝 與伴學老師對話")
        
        # 初始化 Session State 變數
        if "speech_text" not in st.session_state:
            st.session_state.speech_text = ""
        if "last_teacher_response" not in st.session_state:
            st.session_state.last_teacher_response = None
        if "last_user_thought" not in st.session_state:
            st.session_state.last_user_thought = None
        if "show_chat_input" not in st.session_state:
            st.session_state.show_chat_input = False

        # 如果上一次有對話紀錄，大方展示在畫面上
        if st.session_state.last_user_thought:
            st.write(f"🙋 **我的想法/回答：** {st.session_state.last_user_thought}")
        if st.session_state.last_teacher_response:
            st.info(f"🏮 **伴學老師的心靈回饋與素養挑戰：**\n\n{st.session_state.last_teacher_response}")
            
            # 如果老師有錄音，播放器放在這裡
            if "teacher_audio_path" in st.session_state and os.path.exists(st.session_state.teacher_audio_path):
                with open(st.session_state.teacher_audio_path, "rb") as teacher_audio_file:
                    st.audio(teacher_audio_file.read(), format="audio/mp3")

        st.write("讀完這首詩，你感受到了什麼？點擊下方按鈕開啟對話：")

        # 用兩個乾淨的按鈕來控制對話模式
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💬 打字輸入想法", use_container_width=True):
                st.session_state.show_chat_input = True
                st.rerun()  # 這次 rerun 將會瞬間完成，因為導讀有快取了！
        with col2:
            # 錄音元件保持在外層
            audio_input = mic_recorder(
                start_prompt="🎤 語音輸入想法",
                stop_prompt="🛑 說完了，停止錄音",
                just_once=True,
                key="mic_input"
            )

        # 處理語音輸入邏輯
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
                    st.session_state.show_chat_input = True # 辨識完後打開輸入框讓使用者確認
                    st.rerun()
                except Exception as stt_err:
                    st.error(f"語音識別發生小錯誤：{stt_err}")

        # 只有當使用者點了打字，或是語音輸入完畢後，才動態渲染這個表單區塊！
        if st.session_state.show_chat_input:
            st.write("---")
            with st.form(key=f"teacher_form_{target_poem_id}", clear_on_submit=True):
                user_thought = st.text_area(
                    "在此微調或輸入您的想法：",
                    value=st.session_state.speech_text,
                    placeholder="請輸入你的感受或回答老師的問題..."
                )
                
                c1, c2 = st.form_submit_button("發送給老師"), st.form_submit_button("取消關閉")
                
            if c2: # 使用者點選取消
                st.session_state.show_chat_input = False
                st.session_state.speech_text = ""
                st.rerun()
                
            if c1: # 使用者送出
                if not user_thought.strip():
                    st.warning("請先輸入文字再送出喔！")
                else:
                    st.session_state.last_user_thought = user_thought
                    
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
                                st.session_state.last_teacher_response = teacher_text
                                
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
                                    st.session_state.teacher_audio_path = teacher_audio_path
                                except Exception as audio_err:
                                    st.error(f"老師語音回饋生成失敗: {audio_err}")
                                
                                # 重要：送出完成後關閉輸入框、清空暫存文字，並重整頁面
                                st.session_state.show_chat_input = False
                                st.session_state.speech_text = ""
                                st.rerun()
                                    
                            except Exception as e:
                                st.error(f"❌ 伴學老師連線失敗：{e}")
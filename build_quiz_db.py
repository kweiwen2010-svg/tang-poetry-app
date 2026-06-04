import os
import sqlite3
import json
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

# ==========================================
# 0. 系統環境與 API 初始化
# ==========================================
DB_PATH = os.path.join("data", "poetry.db")
os.makedirs("data", exist_ok=True)

load_dotenv()

try:
    client = genai.Client()
    print("✅ [安全檢測] 成功由 .env 檔案安全載入 GEMINI_API_KEY！")
except Exception as e:
    print("⚠️ 警告：未偵測到預設環境變數 GEMINI_API_KEY，請確保 .env 設定正確。")
    print(f"錯誤詳情: {e}")

# ==========================================
# 1. 步驟一：建立/升級具備「完整測驗欄位」的資料庫
# ==========================================
def init_and_upgrade_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS poems (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL UNIQUE,
        author TEXT NOT NULL,
        category TEXT,
        tag TEXT,
        content TEXT NOT NULL,
        story TEXT,
        is_learned INTEGER DEFAULT 0,
        learned_date TEXT,
        quiz_score INTEGER DEFAULT 0,
        quiz_question TEXT,
        quiz_options TEXT,
        quiz_answer TEXT,
        quiz_explain TEXT
    )
    ''')
    
    cursor.execute("PRAGMA table_info(poems)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    needed_columns = {
        "story": "TEXT",
        "quiz_question": "TEXT",
        "quiz_options": "TEXT",
        "quiz_answer": "TEXT",
        "quiz_explain": "TEXT"
    }
    for col_name, col_type in needed_columns.items():
        if col_name not in existing_columns:
            cursor.execute(f"ALTER TABLE poems ADD COLUMN {col_name} {col_type}")
            print(f"✨ 自動補齊遺失欄位: [{col_name}]")
            
    conn.commit()
    conn.close()
    print("📋 資料庫結構初始化/升級檢測完成，所有測驗欄位就緒。")

# ==========================================
# 2. 步驟二：調用 Gemini 出題引擎 (修復引號對齊)
# ==========================================
def generate_soul_quiz_via_gemini(title, author, content):
    prompt = f"""
    你是一位精通中國古典文學與現代素養教育的專家。請針對以下唐詩，設計一套符合「靈魂與深度素養」的「五重天測驗題」。

    【詩詞基本資訊】
    標題：《{title}》
    作者：{author}
    正文：
    {content}

    【出題架構與嚴格規則】
    請設計 5 道題目。
    Q1:「字詞動態美學」選擇題。
    Q2:「時空畫面重構」選擇題。
    Q3:「歷史互本文學」選擇題。
    Q4:「當代生命共鳴」選擇題。
    Q5:「靈魂共鳴簡答題」（答案必須是一個精確的詞彙或短語）。

    【重要：請嚴格輸出符合以下結構的 JSON 格式字串，不要包含任何 ```json 標籤】
    {{
        "quiz_question": {{
            "q1_question": "Q1題目...",
            "q2_question": "Q2題目...",
            "q3_question": "Q3題目...",
            "q4_question": "Q4題目...",
            "q5_question": "Q5題目..."
        }},
        "quiz_options": {{
            "q1_options": ["A. 1", "B. 2", "C. 3", "D. 4"],
            "q2_options": ["A. 1", "B. 2", "C. 3", "D. 4"],
            "q3_options": ["A. 1", "B. 2", "C. 3", "D. 4"],
            "q4_options": ["A. 1", "B. 2", "C. 3", "D. 4"]
        }},
        "quiz_answer": {{
            "q1_answer": "A",
            "q2_answer": "B",
            "q3_answer": "C",
            "q4_answer": "D",
            "q5_answer": {{
                "ans": "標準答案"
            }}
        }},
        "quiz_explain": {{
            "q1_4_explain": "詳解...",
            "q5_explain": "評分標準..."
        }}
    }}
    """
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2
                ),
            )
            
            raw_text = response.text.strip()
            data = json.loads(raw_text)
            
            return {
                "quiz_question": json.dumps(data["quiz_question"], ensure_ascii=False),
                "quiz_options": json.dumps(data["quiz_options"], ensure_ascii=False),
                "quiz_answer": json.dumps(data["quiz_answer"], ensure_ascii=False),
                "quiz_explain": json.dumps(data["quiz_explain"], ensure_ascii=False)
            }
        except Exception as api_err:
            err_msg = str(api_err)
            if "503" in err_msg or "UNAVAILABLE" in err_msg:
                print(f" ⏳ [伺服器塞車中] Gemini 官方機房正忙（503），等待 10 秒後進行第 {attempt + 1}/{max_retries} 次重試...")
                time.sleep(10)
            else:
                # 🔥 這裡的字串與引號已完整封閉校正！
                print(f"❌ 調用 Gemini AI 出題失敗: {api_err}")
                return None
    return None

# ==========================================
# 3. 步驟三：批次對齊加工主程式
# ==========================================
def process_quiz_injection():
    print("🚀 啟動全量唐詩大庫考題注入程序...")
    init_and_upgrade_database()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, title, author, content, quiz_question FROM poems")
    all_poems = cursor.fetchall()
    
    if not all_poems:
        print("⚠️ 提示：資料庫目前是空的。請先執行 python import_all_poetry.py！")
        conn.close()
        return

    todo_poems = [p for p in all_poems if not p[4] or str(p[4]).strip() == "" or str(p[4]) == "None" or not str(p[4]).startswith("{")]
    total_all = len(all_poems)
    total_todo = len(todo_poems)
    
    print(f"📊 大庫總計: {total_all} 首 | 🟢 已有題庫: {total_all - total_todo} 首 | ⏳ 剩餘待補齊: {total_todo} 首")
    print("🚀 開始執行智慧中斷補齊與配額保護程序...")
    
    success_count = 0
    for poem_id, title, author, content, quiz_question in all_poems:
        
        if quiz_question and str(quiz_question).strip().startswith("{"):
            continue
            
        print(f"🎬 [發現斷點] 正在補齊... 《{title}》- {author}")
        quiz_json = generate_soul_quiz_via_gemini(title, author, content)
        
        if quiz_json:
            try:
                cursor.execute('''
                    UPDATE poems 
                    SET quiz_question = ?, quiz_options = ?, quiz_answer = ?, quiz_explain = ?
                    WHERE id = ?
                ''', (
                    quiz_json.get("quiz_question"),
                    quiz_json.get("quiz_options"),
                    quiz_json.get("quiz_answer"),
                    quiz_json.get("quiz_explain"),
                    poem_id
                ))
                conn.commit()
                print(f"   ✅ 《{title}》考題成功補齊並寫入資料庫！")
                success_count += 1
            except sqlite3.Error as se:
                print(f"   ❌ SQLite 寫入失敗: {se}")
        else:
            print(f"   ⏭️ 《{title}》出題異常，跳過留待下次補齊。")
            
        print("   ⏳ 保護 API 配額中，系統冷卻呼吸 4 秒鐘...")
        time.sleep(4)
            
    conn.close()
    print(f"\n🎉 補齊作業結束！本次成功幫你補上了 {success_count} 首詩詞的精美題庫！")

if __name__ == "__main__":
    process_quiz_injection()
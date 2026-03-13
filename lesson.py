import os
import json
import glob
import time
import markdown
import smtplib
from email.mime.text import MIMEText
import google.generativeai as genai

# --- Configuration & Secrets ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_PASS = os.environ.get("GMAIL_APP_PASSWORD")
TO_EMAIL = os.environ.get("TO_EMAIL")

genai.configure(api_key=GEMINI_API_KEY)

# --- File Paths ---
LESSONS_DIR = "lessons"
SYLLABUS_FILE = "syllabus.txt"
STATE_FILE = "last_lesson.json"

# Ensure lessons directory exists
os.makedirs(LESSONS_DIR, exist_ok=True)

def get_current_state():
    with open(STATE_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data[0]["last_day"]

def update_state(new_day):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump([{"last_day": new_day}], f, indent=4)

def get_todays_topic(day_number):
    with open(SYLLABUS_FILE, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    if day_number <= len(lines):
        return lines[day_number - 1]
    return "Advanced Conversational Practice and Review"

def get_past_context():
    past_lessons_content = ""
    files = sorted(glob.glob(f"{LESSONS_DIR}/MSA*.md"))
    # Keep context manageable: only read the last 15 lessons for vocabulary tracking
    for file in files[-15:]: 
        with open(file, 'r', encoding='utf-8') as f:
            past_lessons_content += f"\n\n--- Content from {file} ---\n\n"
            past_lessons_content += f.read()
    return past_lessons_content

def generate_lesson_with_retry(day_num, topic, past_context, retries=3):
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    You are 'Mudarris365', an expert Modern Standard Arabic teacher. You teach step-by-step, treating the student as a complete beginner (like a first-grader learning to read).
    Today is Day {day_num} of 365. 
    Today's Topic: {topic}
    
    Here are the recent lessons the student has learned:
    {past_context}
    
    CRITICAL INSTRUCTIONS:
    1. Generate today's lesson in strictly formatted Markdown.
    2. TEACH IN 100% ENGLISH. Do NOT translate your greetings, explanations, instructions, or meta-words into Arabic. 
    3. FULL SCOPE: Fully cover the day's topic. If the topic is "The Arabic Alphabet", you MUST introduce all 28 letters in the lesson. Do not stop at just a few.
    4. ZERO EXTRA VOCABULARY: Do NOT translate words like "Welcome", "Lesson", "Alphabet", or "Today" into Arabic. A beginner cannot read these yet! Only use Arabic for the specific target of the day (e.g., just the letters themselves).
    5. ONLY use Arabic vocabulary the student has already learned in past lessons. If it's Day 1 or 2, your Arabic output should be strictly limited to letters or short vowels.
    6. Include sections: # {topic}, ## Lesson, ## Examples, ## Practice.
    7. MUST DO: At the absolute end of the document, include these two exact sections:
       ## 📚 Core Vocabulary (ONLY list the exact letters or target words explicitly taught today. Do not add conversational words.)
       ## 🗣️ Key Sentences (ONLY list sentences if the student actually knows the letters/words to read them. If they are just learning the alphabet, write "None for today! Focus on the letters.")
    8. For any Arabic text, strictly use Harakat (تَشْكِيل) to aid pronunciation.
    """
    
    for attempt in range(retries):
        try:
            print(f"Calling Gemini API (Attempt {attempt + 1})...")
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"API Error: {e}")
            if attempt < retries - 1:
                time.sleep(10)
            else:
                raise Exception("Failed to generate lesson.")

def send_email(day_num, topic, html_content):
    styled_html = f"""
    <html>
    <head>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #2c3e50; max-width: 800px; margin: auto; padding: 20px; background-color: #fcfcfc; }}
        h1 {{ color: #1abc9c; border-bottom: 2px solid #1abc9c; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; background-color: #ecf0f1; padding: 10px; border-radius: 5px; }}
        code {{ background-color: #fdf6e3; padding: 2px 5px; border-radius: 4px; font-size: 1.1em; color: #d35400; }}
        ul {{ background-color: #ffffff; padding: 20px 40px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }}
    </style>
    </head>
    <body>{html_content}</body>
    </html>
    """
    
    msg = MIMEText(styled_html, 'html')
    msg['Subject'] = f"Mudarris 365 - {topic}"
    msg['From'] = GMAIL_USER
    msg['To'] = TO_EMAIL

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(GMAIL_USER, GMAIL_PASS)
        server.send_message(msg)

def main():
    last_day = get_current_state()
    today_num = last_day + 1
    
    topic = get_todays_topic(today_num)
    print(f"Preparing Day {today_num}: {topic}")
    
    past_context = get_past_context()
    md_lesson = generate_lesson_with_retry(today_num, topic, past_context)
    
    filename = f"MSA{today_num:03d}.md"
    filepath = os.path.join(LESSONS_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(md_lesson)
    
    html_lesson = markdown.markdown(md_lesson)
    send_email(today_num, topic, html_lesson)
    
    update_state(today_num)

if __name__ == "__main__":
    main()

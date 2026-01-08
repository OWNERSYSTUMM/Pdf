import os
import json
import asyncio
import pdfplumber
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import PollType
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
import openai

# ================= SETUP =================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
openai.api_key = os.getenv("OPENAI_API_KEY")

PDF_FILE = "temp.pdf"
sessions = {}

# ================= COMMANDS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 PDF Quiz Bot Ready!\n\n"
        "Group me /pdf likho"
    )

async def pdf_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ Group me use karo")
        return

    sessions[update.effective_chat.id] = "WAIT_PDF"
    await update.message.reply_text("📄 Quiz ke liye PDF bhejo")

# ================= PDF HANDLER =================

async def pdf_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if sessions.get(chat_id) != "WAIT_PDF":
        return

    file = await update.message.document.get_file()
    await file.download_to_drive(PDF_FILE)

    await update.message.reply_text("⏱️ Har question ke liye seconds bhejo (min 10)")
    sessions[chat_id] = "WAIT_TIME"

# ================= TIME HANDLER =================

async def time_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if sessions.get(chat_id) != "WAIT_TIME":
        return

    try:
        seconds = int(update.message.text)
        if seconds < 10:
            raise ValueError
    except:
        await update.message.reply_text("❌ Number >=10 bhejo")
        return

    sessions[chat_id] = seconds
    await update.message.reply_text("🧠 Quiz ban raha hai...")
    await start_quiz(chat_id, seconds, context)

# ================= CORE =================

def read_pdf():
    text = ""
    with pdfplumber.open(PDF_FILE) as pdf:
        for page in pdf.pages[:5]:
            text += page.extract_text() or ""
    return text[:3000]

def generate_questions(text):
    prompt = f"""
Is text se 5 MCQ banao (Hindi).
4 options ho.
Correct answer ka index do (0-3).
Sirf JSON return karo.

Format:
[
 {{
  "question": "",
  "options": ["","","",""],
  "answer": 0
 }}
]

Text:
{text}
"""
    res = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    return json.loads(res.choices[0].message.content)

async def start_quiz(chat_id, seconds, context):
    text = read_pdf()
    questions = generate_questions(text)

    for q in questions:
        await context.bot.send_poll(
            chat_id=chat_id,
            question=q["question"],
            options=q["options"],
            type=PollType.QUIZ,
            correct_option_id=q["answer"],
            open_period=seconds,
            is_anonymous=False
        )
        await asyncio.sleep(seconds + 2)

    await context.bot.send_message(chat_id, "🏁 Quiz khatam")
    sessions.pop(chat_id, None)
    if os.path.exists(PDF_FILE):
        os.remove(PDF_FILE)

# ================= MAIN =================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pdf", pdf_cmd))
    app.add_handler(MessageHandler(filters.Document.PDF, pdf_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, time_handler))

    print("🤖 Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()

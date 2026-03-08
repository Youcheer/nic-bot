import os
import json
import re
import cv2
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import PIL.Image
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# .env ගොනුවේ ඇති රහස්‍ය තොරතුරු ලබා ගැනීමට
from dotenv import load_dotenv

load_dotenv()

# ඔයාගේ Telegram Bot Token එක සහ අලුත් Gemini API Key එක
TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TOKEN or not GEMINI_API_KEY:
    print("Error: Please set TELEGRAM_TOKEN and GEMINI_API_KEY in the .env file")
    exit(1)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def extract_details_with_ai(image_path):
    try:
        img = PIL.Image.open(image_path)
        
        # AI එකට දෙන ප්‍රොම්ප්ට් එක
        prompt = """
        You are an expert OCR and data extraction system.
        Analyze this image carefully. Your task is to find the Seychelles National Identity Card details.
        
        1. NIC Number (It usually contains hyphens, follow the exact pattern you see on the card, e.g. 999-0310-1-1-75 or similar).
        2. Date of Expiry (Next to "Valid until". Read the date explicitly and format it EXACTLY like DD.MM.YYYY e.g., if it says "23 December 2034", output "23.12.2034").
        3. Full Name (Combine all name parts under the word "Name", e.g., "HARRISSON Rolly, Roger").
        
        If the text is readable but you are unsure, just try your best. DO NOT USE "Blurry" unless the image is literally unreadable.

        Provide ONLY a valid JSON object.
        {
            "nic": "extracted nic or Blurry",
            "expiry": "extracted expiry or Blurry",
            "name": "extracted full name or Blurry",
            "reason": "Explain briefly if you successfully read it or why you couldn't (e.g., 'Read successfully')."
        }
        """
        
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        response = model.generate_content([prompt, img], safety_settings=safety_settings)
        
        try:
            result_text = response.text.strip()
        except ValueError:
            return "Blocked by AI Safety", "Unknown", "Unknown", "AI Block"
            
        # JSON parsing
        match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if match:
             result_text = match.group(0)

        data = json.loads(result_text)
        nic = data.get("nic", "Unknown")
        expiry = data.get("expiry", "Unknown")
        name = data.get("name", "Unknown").replace(",", " ").replace("  ", " ").strip()
        reason = data.get("reason", "No reason provided")
        
        return nic, expiry, name, reason
            
    except Exception as e:
        print(f"AI Error: {e}")
        return "API Error", "Unknown", "Unknown", str(e)

async def process_image(update: Update, context: ContextTypes.DEFAULT_TYPE, file, image_path="nic.jpg"):
    try:
        await file.download_to_drive(image_path)

        nic, expiry, name, reason = extract_details_with_ai(image_path)
        
        # Caption එකක් දාලා තිබුණොත් ඒක Account Number විදිහට ගන්නවා. නැත්නම් default එකක් දානවා.
        account_number = update.message.caption if update.message.caption else "ACCOUNT_NUMBER"

        # AI එකට කියවන්න අමාරු වුණොත් (Blurry/Unknown නම්) Telegram එකට පැහැදිලි message එකක් යවන්න
        if "Blurry" in nic or "Unknown" in nic:
            message = f"⚠️ Image is not clear enough for AI to read.\n\n" \
                      f"*Results:*\nNIC: {nic}\nName: {name}\nExpiry: {expiry}\n\n" \
                      f"🤖 *AI Reason:* {reason}\n\n" \
                      f"💡 *Advice:* Telegram reduces photo quality. Please send the image as a **Document/File**, or take a closer photo directly of the ID card! (ID කාඩ් එක ලං කරලා පැහැදිලි ෆොටෝ එකක් ගහන්න)"
            
            await update.message.reply_photo(photo=open(image_path, "rb"), caption=message, parse_mode='Markdown')
            return

        if nic in ["Blocked by AI Safety", "Parse Error", "API Error"]:
            message = f"AI Error processing image.\nReason: {nic}\nDetails: {reason}"
        else:
            # message එකේ ACCOUNT_NUMBER කියන තැනට Caption එකෙන් ආපු අංකය දානවා 
            message = f"Verified by Suraj - NIC Expiry {expiry}\nNIC Number - {nic}\nRename: {name} {account_number} - NIC Expiry date {expiry}"

        await update.message.reply_photo(photo=open(image_path, "rb"))
        await update.message.reply_text(message)
        
    except Exception as e:
        await update.message.reply_text(f"Error processing image: {e}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()
    await process_image(update, context, file)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if document.mime_type and document.mime_type.startswith('image/'):
        file = await document.get_file()
        await process_image(update, context, file)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Photo විදිහට එවන ඒවාටයි, Document විදිහට එවන ඒවාටයි දෙකටම වැඩ කරන්න හදලා තියෙන්නේ
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))
    
    print("Bot running! Supports normal Photos AND High-Quality Documents...")
    app.run_polling()

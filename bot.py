import os
import json
import re
import cv2
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import PIL.Image
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# ඔයාගේ Telegram Bot Token එක සහ අලුත් Gemini API Key එක
TOKEN = "8001050042:AAGnZSZ_nW6PTLRCOOtttd4uO--J68WosXg"
GEMINI_API_KEY = "AIzaSyBMIXtjQHXrwM26xot7hY7OeR40bLv_Ps4"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def extract_details_with_ai(image_path):
    try:
        img = PIL.Image.open(image_path)
        
        # AI එකට දෙන ප්‍රොම්ප්ට් එක - මඳක් වෙනස් කර වඩාත් පැහැදිලි උපදෙස් ලබාදීම
        prompt = """
        You are an expert OCR and data extraction system.
        Analyze this document image (this is a Seychelles National Identity Card). Look completely carefully at the entire image.
        Extract the following information perfectly:
        1. NIC Number (This typically contains hyphens, look for patterns like 123-4567-8-901 or similar formats).
        2. Date of Expiry (Usually written with "Valid until". Read the date explicitly and format it EXACTLY like DD.MM.YYYY e.g., if it says "30 April 2029", output "30.04.2029").
        3. Full Name (Combine First Name and Surname properly. Pay attention to both First names and Surname fields near the top).
        
        CRITICAL: Provide ONLY a valid JSON object. No extra text, no markdown tags.
        {
            "nic": "extracted nic",
            "expiry": "extracted expiry",
            "name": "extracted full name"
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
            return "Blocked by AI Safety", "Unknown", "Unknown"
            
        # JSON parsing සඳහා වඩා හොඳ ක්‍රමයක්
        if result_text.startswith('```json'):
            result_text = result_text[7:]
        elif result_text.startswith('```'):
            result_text = result_text[3:]
            
        if result_text.endswith('```'):
            result_text = result_text[:-3]
            
        result_text = result_text.strip()
        
        # regex හරහාත් උත්සහ කිරීම (AI එක වෙනත් දේවල් type කරොත්)
        match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if match:
             result_text = match.group(0)

        data = json.loads(result_text)
        nic = data.get("nic", "Unknown")
        expiry = data.get("expiry", "Unknown")
        name = data.get("name", "Unknown")
        
        return nic, expiry, name
            
    except Exception as e:
        print(f"AI Error: {e}")
        return "API Error", "Unknown", "Unknown"

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        image_path = "nic.jpg"
        
        await file.download_to_drive(image_path)

        # OpenCV Cropping සම්පූර්ණයෙන්ම ඉවත් කර කෙලින්ම Full Image එක AI එකට යැවීම!
        # හේතුව: සමහර වෙලාවට ෆොටෝ එකේ background එක වටේට සුදු පාට ගොඩක් තිබුණාම OpenCV confusion එකකට එනවා
        # Gemini 1.5 Flash ආකෘතියට සම්පූර්ණ පින්තූරය තේරුම් ගැනීමේ හැකියාව ඉහළයි. Crop කිරීම අත්‍යාවශ්‍ය නොවේ.
        
        # Original Image එක කෙලින්ම AI එකට යැවීම
        nic, expiry, name = extract_details_with_ai(image_path)

        # AI එක fail වුණොත් ඒකෙ Error message එක යැවීම
        if nic in ["Blocked by AI Safety", "Parse Error", "API Error"]:
            message = f"AI Failed to read image.\nReason: {nic}\nPlease check if the image is clear."
        else:
             message = f"Verified by Suraj - NIC Expiry {expiry}\nNIC Number - {nic}\nRename: {name} ACCOUNT_NUMBER - NIC Expiry date {expiry}"

        # දැන් user ට යවන්නේත් Original ෆොටෝ එකමයි (කිසිම කට් කිරීමක් නෑ)
        await update.message.reply_photo(photo=open(image_path, "rb"))
        await update.message.reply_text(message)
        
    except Exception as e:
        await update.message.reply_text(f"Error processing image: {e}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("Bot running exclusively on Gemini AI without local OpenCV cropping...")
    app.run_polling()

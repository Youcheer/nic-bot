import os
import json
import cv2
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import PIL.Image

# ඔයාගේ Telegram Bot Token එක සහ අලුත් Gemini API Key එක
TOKEN = "8001050042:AAGnZSZ_nW6PTLRCOOtttd4uO--J68WosXg"
GEMINI_API_KEY = "AIzaSyBMIXtjQHXrwM26xot7hY7OeR40bLv_Ps4"

# Gemini API එක configure කිරීම
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def auto_crop(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if contours:
        c = max(contours, key=cv2.contourArea)
        if cv2.contourArea(c) > 5000:
            x, y, w, h = cv2.boundingRect(c)
            padding = 20
            startX = max(0, x - padding)
            startY = max(0, y - padding)
            endX = min(image.shape[1], x + w + padding)
            endY = min(image.shape[0], y + h + padding)
            return image[startY:endY, startX:endX]
    return image

def extract_details_with_ai(image_path):
    try:
        # Image එක load කිරීම
        img = PIL.Image.open(image_path)
        
        # AI එකට දෙන උපදෙස (Prompt)
        prompt = """
        Analyze this document image (Seychelles National Identity Card). Look very carefully at the text and numbers.
        Extract the following information perfectly:
        1. NIC Number (This typically contains hyphens, look for patterns like XXX-XXXX-X-XXX. Check carefully).
        2. Date of Expiry (Usually says "Valid until". Please format it EXACTLY like DD.MM.YYYY e.g., if it says 30 April 2029, output 30.04.2029).
        3. Full Name (Combine First Name and Surname properly. It might be in uppercase).
        
        If a specific field is completely invisible or unreadable due to cropping, use "Unknown" for that field.
        
        Return ONLY a raw JSON object in the following format, nothing else. Do not use markdown tags:
        {
            "nic": "extracted nic",
            "expiry": "extracted expiry",
            "name": "extracted full name"
        }
        """
        
        # Image එක සහ prompt එක Gemini එකට යැවීම
        response = model.generate_content([prompt, img])
        
        # AI එකෙන් එන JSON text එක කියවීම
        result_text = response.text.strip()
        if result_text.startswith('```json'):
            result_text = result_text[7:]
        elif result_text.startswith('```'):
            result_text = result_text[3:]
            
        if result_text.endswith('```'):
            result_text = result_text[:-3]
            
        result_text = result_text.strip()
        data = json.loads(result_text)
        
        nic = data.get("nic", "Unknown")
        expiry = data.get("expiry", "Unknown")
        name = data.get("name", "Unknown")
        
        return nic, expiry, name
        
    except Exception as e:
        print(f"AI Error: {e}")
        return "Unknown", "Unknown", "Unknown"

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Telegram එකෙන් එන photo එක download කරගැනීම
        photo = update.message.photo[-1]
        file = await photo.get_file()
        image_path = "nic.jpg"
        
        await file.download_to_drive(image_path)

        # පරණ තිබ්බ විදිහටම OpenCV වලින් crop කරගැනීම
        img = cv2.imread(image_path)
        if img is not None:
            crop = auto_crop(img)
            cropped_path = "cropped.jpg"
            cv2.imwrite(cropped_path, crop)
        else:
            cropped_path = image_path # backup if cv2 fails

        # Crop කරපු image එක AI එක හරහා details ගැනීම සඳහා යැවීම
        nic, expiry, name = extract_details_with_ai(cropped_path)

        # Message එක හැදීම
        message = f"Verified by Suraj - NIC Expiry {expiry}\nNIC Number - {nic}\nRename: {name} ACCOUNT_NUMBER - NIC Expiry date {expiry}"

        await update.message.reply_photo(photo=open(cropped_path, "rb"))
        await update.message.reply_text(message)
        
    except Exception as e:
        await update.message.reply_text(f"Error processing image: {e}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("Bot running with OpenCV Cropping and Gemini AI...")
    app.run_polling()

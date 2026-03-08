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
# We use gemini-1.5-flash for fast and accurate image details
model = genai.GenerativeModel('gemini-1.5-flash')

def auto_crop(image):
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # පින්තූරයේ තියෙන අකුරු, barcode සහ photo එක මොන පැහැයකින් තිබුණත් හොයාගන්න Adaptive Threshold පාවිච්චි කිරීම
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 21, 5)
        
        # ලඟින් තියෙන අකුරු ටික එකට එකතු කරන්න ඩයිලෙට් කිරීම
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 20))
        dilated = cv2.dilate(thresh, kernel, iterations=2)
        
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            # කුඩා ඩොට් වගේ දේවල් අයින් කරලා ලොකු කෑලි ටික (ID එකේ අකුරු, පින්තූරය) විතරක් තෝරගැනීම
            boxes = [cv2.boundingRect(c) for c in contours if cv2.contourArea(c) > 500]
            if boxes:
                # ඔක්කොම අකුරු සහ පින්තූර කවර් වෙන විදිහට එක ලොකු Bounding Box එකක් හැදීම
                min_x = min([x for x, y, w, h in boxes])
                min_y = min([y for x, y, w, h in boxes])
                max_x = max([x + w for x, y, w, h in boxes])
                max_y = max([y + h for x, y, w, h in boxes])
                
                # අවටින් පොඩි පරතරයක් (padding) තැබීම (අකුරු කැපෙන්නේ නැති වෙන්න)
                padding = 30
                startX = max(0, min_x - padding)
                startY = max(0, min_y - padding)
                endX = min(image.shape[1], max_x + padding)
                endY = min(image.shape[0], max_y + padding)
                
                return image[startY:endY, startX:endX]
    except Exception as e:
        print(f"Crop Error: {e}")
        
    return image

def extract_details_with_ai(image_path):
    try:
        img = PIL.Image.open(image_path)
        
        # AI එකට දෙන ප්‍රොම්ප්ට් එක
        prompt = """
        Analyze this document image (Seychelles National Identity Card). Look very carefully at the text and numbers.
        Extract the following information perfectly:
        1. NIC Number (This typically contains hyphens, look for patterns like XXX-XXXX-X-XXX).
        2. Date of Expiry (Usually says "Valid until". Please format it EXACTLY like DD.MM.YYYY e.g., if it says 30 April 2029, output 30.04.2029).
        3. Full Name (Combine First Name and Surname properly. It might be in uppercase).
        
        If a specific field is unreadable, use "Unknown" for that field.
        
        Return ONLY a JSON object in this format:
        {
            "nic": "extracted nic",
            "expiry": "extracted expiry",
            "name": "extracted full name"
        }
        """
        
        # Security Blocks අයින් කිරීම (ID Cards හඳුනා නොගන්නා එක නැති කිරීමට)
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        response = model.generate_content([prompt, img], safety_settings=safety_settings)
        
        try:
            result_text = response.text
        except ValueError:
            # AI එක photo එක ප්‍රතික්ෂේප කරොත්
            return "Blocked by AI Safety", "Unknown", "Unknown"
            
        # Regex පාවිච්චි කරලා JSON කොටස විතරක් තෝරගැනීම (AI එක වෙනත් දේවල් type කරලා තිබුණොත් අයින් කරන්න)
        match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            nic = data.get("nic", "Unknown")
            expiry = data.get("expiry", "Unknown")
            name = data.get("name", "Unknown")
            return nic, expiry, name
        else:
            return "Parse Error", "Unknown", "Unknown"
            
    except Exception as e:
        print(f"AI Error: {e}")
        return "API Error", "Unknown", "Unknown"

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        image_path = "nic.jpg"
        
        await file.download_to_drive(image_path)

        # අලුත් Crop function එකෙන් Photo එක Crop කිරීම
        img = cv2.imread(image_path)
        if img is not None:
            crop = auto_crop(img)
            cropped_path = "cropped.jpg"
            cv2.imwrite(cropped_path, crop)
        else:
             cropped_path = image_path

        nic, expiry, name = extract_details_with_ai(cropped_path)

        # AI එක fail වුණොත් ඒකෙ Error message එක යැවීම
        if nic in ["Blocked by AI Safety", "Parse Error", "API Error"]:
            message = f"AI Failed to read image.\nReason: {nic}\nPlease check if the image is clear."
        else:
            message = f"Verified by Suraj - NIC Expiry {expiry}\nNIC Number - {nic}\nRename: {name} ACCOUNT_NUMBER - NIC Expiry date {expiry}"

        await update.message.reply_photo(photo=open(cropped_path, "rb"))
        await update.message.reply_text(message)
        
    except Exception as e:
        await update.message.reply_text(f"Error processing image: {e}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("Bot running with Advanced Crop and Gemini AI...")
    app.run_polling()

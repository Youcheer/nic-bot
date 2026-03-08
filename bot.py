import cv2
import pytesseract
import re
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

if os.name == 'nt':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

TOKEN = "8001050042:AAGnZSZ_nW6PTLRCOOtttd4uO--J68WosXg"

def read_text(image):

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    thresh = cv2.threshold(gray,150,255,cv2.THRESH_BINARY)[1]

    text = pytesseract.image_to_string(thresh)

    return text


def extract_details(text):

    nic_match = re.search(r'\d{3}-\d{4}-\d-\d{1,3}', text)
    nic = nic_match.group() if nic_match else "Unknown"

    dates = re.findall(r'\d{2}\s[A-Za-z]+\s\d{4}', text)

    expiry="Unknown"

    if len(dates)>0:
        expiry=dates[-1]

    months={
    "January":"01","February":"02","March":"03","April":"04",
    "May":"05","June":"06","July":"07","August":"08",
    "September":"09","October":"10","November":"11","December":"12"
    }

    if expiry!="Unknown":

        d,m,y=expiry.split()
        expiry=f"{d}.{months.get(m,'00')}.{y}"

    lines=text.split("\n")

    surname=""
    firstname=""

    for line in lines:

        if "SEYCHELLES" in line:
            continue

        if line.isupper() and len(line)>3:
            surname=line

        if "," in line:
            firstname=line.replace(","," ")

    name=(firstname+" "+surname).strip()

    if name=="":
        name="Unknown"

    return nic,expiry,name
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


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        photo=update.message.photo[-1]
        file=await photo.get_file()

        await file.download_to_drive("nic.jpg")

        img=cv2.imread("nic.jpg")

        crop=auto_crop(img)

        cv2.imwrite("cropped.jpg",crop)

        text=read_text(crop)

        nic,expiry,name=extract_details(text)

        message=f"""Verified by Suraj - NIC Expiry {expiry}
NIC Number - {nic}
Rename: {name} ACCOUNT_NUMBER - NIC Expiry date {expiry}"""

        await update.message.reply_photo(photo=open("cropped.jpg","rb"))
        await update.message.reply_text(message)
    except Exception as e:
        await update.message.reply_text(f"Error processing image: {e}")


app=ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

print("Bot running...")

app.run_polling()

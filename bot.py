import cv2
import pytesseract
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# Telegram Bot Token
TOKEN = "8001050042:AAGnZSZ_nW6PTLRCOOtttd4uO--J68WosXg"

# OCR path (remove this if server environment)
pytesseract.pytesseract.tesseract_cmd = r"/usr/bin/tesseract"

# ---------- OCR ----------
def read_text(image):

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    thresh = cv2.threshold(gray,150,255,cv2.THRESH_BINARY)[1]

    text = pytesseract.image_to_string(thresh)

    return text


# ---------- EXTRACT DETAILS ----------
def extract_details(text):

    nic_match = re.search(r'\d{3}-\d{4}-\d-\d{1,3}', text)
    nic = nic_match.group() if nic_match else "Unknown"

    dates = re.findall(r'\d{2}\s[A-Za-z]+\s\d{4}', text)

    expiry = "Unknown"

    if len(dates) > 0:
        expiry = dates[-1]

    months = {
        "January":"01","February":"02","March":"03","April":"04",
        "May":"05","June":"06","July":"07","August":"08",
        "September":"09","October":"10","November":"11","December":"12"
    }

    if expiry != "Unknown":

        d,m,y = expiry.split()

        expiry = f"{d}.{months.get(m,'00')}.{y}"

    lines = text.split("\n")

    surname=""
    firstname=""

    for line in lines:

        line=line.strip()

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


# ---------- TELEGRAM HANDLER ----------
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    photo = update.message.photo[-1]

    file = await photo.get_file()

    await file.download_to_drive("nic.jpg")

    img = cv2.imread("nic.jpg")

    h,w,_ = img.shape

    crop = img[int(h*0.15):int(h*0.45), int(w*0.25):int(w*0.75)]

    cv2.imwrite("cropped.jpg", crop)

    text = read_text(crop)

    nic,expiry,name = extract_details(text)

    account="ACCOUNT_NUMBER"

    message=f"""Verified by Suraj - NIC Expiry {expiry}
NIC Number - {nic}
Rename: {name} {account} - NIC Expiry date {expiry}"""

    await update.message.reply_photo(photo=open("cropped.jpg","rb"))

    await update.message.reply_text(message)


print("NIC Verification Bot Running...")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

app.run_polling()

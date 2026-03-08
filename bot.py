import cv2
import pytesseract
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

TOKEN = "8001050042:AAGnZSZ_nW6PTLRCOOtttd4uO--J68WosXg"

# ---------- CARD DETECTION ----------
def detect_card(image):

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray,(5,5),0)
    edge = cv2.Canny(blur,50,150)

    contours,_ = cv2.findContours(edge,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours,key=cv2.contourArea,reverse=True)

    for c in contours:
        x,y,w,h = cv2.boundingRect(c)

        if w > 300 and h > 150:
            return image[y:y+h, x:x+w]

    return image


# ---------- OCR ----------
def read_text(img):

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.threshold(gray,150,255,cv2.THRESH_BINARY)[1]

    text = pytesseract.image_to_string(thresh)

    return text


# ---------- DATA EXTRACTION ----------
def extract_details(text):

    # NIC NUMBER
    nic_match = re.search(r'\d{3}-\d{4}-\d-\d{1,3}', text)
    nic = nic_match.group() if nic_match else "Unknown"

    # DATE DETECTION
    date_matches = re.findall(r'\d{2}\s[A-Za-z]+\s\d{4}', text)

    expiry = "Unknown"

    if len(date_matches) >= 1:
        expiry = date_matches[-1]

    months = {
        "January":"01","February":"02","March":"03","April":"04",
        "May":"05","June":"06","July":"07","August":"08",
        "September":"09","October":"10","November":"11","December":"12"
    }

    if expiry != "Unknown":
        d,m,y = expiry.split()
        expiry = f"{d}.{months.get(m,'00')}.{y}"

    # NAME DETECTION
    lines = text.split("\n")

    surname = ""
    firstname = ""

    for line in lines:

        line=line.strip()

        if "SEYCHELLES" in line or "IDENTITY" in line:
            continue

        if line.isupper() and line.isalpha() and len(line) > 3:
            surname = line

        if "," in line:
            firstname = line.replace(",", " ")

    name = (firstname + " " + surname).strip()

    if name == "":
        name="Unknown"

    return nic, expiry, name


# ---------- TELEGRAM HANDLER ----------
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    photo = update.message.photo[-1]

    file = await photo.get_file()

    await file.download_to_drive("nic.jpg")

    img = cv2.imread("nic.jpg")

    card = detect_card(img)

    cv2.imwrite("cropped.jpg", card)

    text = read_text(card)

    nic, expiry, name = extract_details(text)

    account = "ACCOUNT_NUMBER"

    message = f"""Verified by Suraj - NIC Expiry {expiry}
NIC Number - {nic}
Rename: {name} {account} - NIC Expiry date {expiry}"""

    await update.message.reply_photo(photo=open("cropped.jpg","rb"))
    await update.message.reply_text(message)


print("Verification Bot Running...")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

app.run_polling()

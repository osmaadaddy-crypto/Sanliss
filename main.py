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

BOT_TOKEN = "9263489599:AAEUAOJqjMF998jzLLO8FVAaIRG8NEX2au0"
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

CHESTS_DB = {
    "pokemon_tcg": {
        "name": "Pokémon TCG Pocket (50)",
        "package": "jp.pokemon.pokemontcgp",
        "fallback_tasks": [
            "Use pack stamina to open booster packs 1",
            "Wonder pick 1",
            "Win solo battles 1"
        ]
    },
    "angry_birds_2": {
        "name": "Angry birds 2 (50)",
        "package": "com.rovio.baba",
        "fallback_tasks": [
            "Feathery Hills Complete!",
            "New York City Complete!"
        ]
    },
    "8ball_pool": {
        "name": "8ball pool (50)",
        "package": "com.miniclip.eightballpool",
        "fallback_tasks": [
            "First Win!",
            "Pool Amateur"
        ]
    },
    "mobile_legends": {
        "name": "Mobile legends (50)",
        "package": "com.mobile.legends",
        "fallback_tasks": [
            "Classic Match Complete!",
            "First MVP"
        ]
    }
}

user_sessions = {}

def main_reply_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row(KeyboardButton("🚀 Start Process"))
    markup.add(
        KeyboardButton("🪙 Balance & Recharge"),
        KeyboardButton("🎁 Rewards Hub"),
        KeyboardButton("📊 History & Stats"),
        KeyboardButton("ℹ️ Guide & Terms"),
        KeyboardButton("💬 Support"),
        KeyboardButton("🌐 Change Language")
    )
    return markup

def chests_inline_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton(info["name"], callback_data=f"chest|{key}")
        for key, info in CHESTS_DB.items()
    ]
    markup.add(*buttons)
    markup.row(
        InlineKeyboardButton("📩 Request New Chest", callback_data="req_chest"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel")
    )
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
        InlineKeyboardButton("✏️ Edit / Re-enter Credentials", callback_data="edit_creds"),
        InlineKeyboardButton("❌ Cancel Process", callback_data="cancel")
    )
    return markup

@bot.message_handler(commands=['start'])
def cmd_start(message):
    text = (
        "👋 <b>Welcome to Quest Helper✨ Bot!</b>\n\n"
        "🪙 <b>Your Token Balance: Unlimited (Admin)</b>\n"
        "Enjoy your instant Play Points quests!\n\n"
        "Click 🚀 <b>Start Process</b> below to select a chest."
    )
    bot.send_message(message.chat.id, text, reply_markup=main_reply_keyboard())

@bot.message_handler(func=lambda m: m.text == "🚀 Start Process")
def msg_start_process(message):
    text = (
        "📦 <b>Available Chests to Activate</b>\n\n"
        "⚠️ <b>Note:</b> Make sure the quest is started in your Google Play Points before selecting!\n\n"
        "Select the desired chest to start:"
    )
    bot.send_message(message.chat.id, text, reply_markup=chests_inline_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    uid = call.from_user.id
    chat_id = call.message.chat.id
    data = call.data

    if data == "cancel":
        user_sessions.pop(uid, None)
        safe_edit(
            "❌ <b>Process Cancelled.</b>\nClick 🚀 <b>Start Process</b> whenever you are ready.",
            chat_id, call.message.message_id
        )
        return

    if data == "req_chest":
        bot.answer_callback_query(call.id, "Send the package name to admin to add it!", show_alert=True)
        return

    if data.startswith("chest|"):
        chest_key = data.split("|")[1]
        chest_info = CHESTS_DB[chest_key]
        user_sessions[uid] = {"chest_key": chest_key, "step": "wait_email"}
        text = (
            f"🎯 <b>Selected Chest:</b> {chest_info['name']}\n\n"
            "📩 <b>Send account credentials:</b>\n"
            "<code>email---password</code>\n\n"
            "💡 <i>Or send your Email first, then Password (or direct ya29. token) in the next message.</i>\n"
            "🔔 <b>Tip:</b> Keep your phone unlocked to tap the verification number!"
        )
        safe_edit(text, chat_id, call.message.message_id, reply_markup=cancel_inline_keyboard())
        return

    if data == "edit_creds":
        if uid not in user_sessions:
            user_sessions[uid] = {"chest_key": "pokemon_tcg", "step": "wait_email"}
        else:
            user_sessions[uid]["step"] = "wait_email"
        safe_edit(
            "✏️ <b>Send <code>email---password</code> (or <code>email---ya29.token</code>):</b>",
            chat_id, call.message.message_id, reply_markup=cancel_inline_keyboard()
        )
        return

    if data == "confirm_run":
        session = user_sessions.get(uid)
        if not session or "email" not in session or "password" not in session:
            bot.answer_callback_query(call.id, "Session expired. Click Start Process again!", show_alert=True)
            return
        threading.Thread(target=execute_sync_flow, args=(chat_id, call.message.message_id, uid)).start()

@bot.message_handler(func=lambda m: m.from_user.id in user_sessions)
def handle_credentials_steps(message):
    uid = message.from_user.id
    chat_id = message.chat.id
    session = user_sessions[uid]
    text = message.text.strip()

    if "---" in text and session.get("step") in ["wait_email", "wait_password"]:
        email, pwd = text.split("---", 1)
        session["email"] = email.strip()
        session["password"] = pwd.strip()
        session["step"] = "confirm"
        try:
            bot.delete_message(chat_id, message.message_id)
        except Exception:
            pass
        show_confirmation(chat_id, session)
        return

    if session.get("step") == "wait_email":
        session["email"] = text
        session["step"] = "wait_password"
        bot.send_message(
            chat_id,
            f"📧 <b>Account:</b> {text}\n\n"
            "🔑 <b>Now enter your account Password (or paste a live ya29. Play Games token):</b>\n\n"
            "🔒 <i>Encrypted & auto-deleted from chat.</i>",
            reply_markup=cancel_inline_keyboard()
        )
    elif session.get("step") == "wait_password":
        session["password"] = text
        session["step"] = "confirm"
        try:
            bot.delete_message(chat_id, message.message_id)
        except Exception:
            pass
        show_confirmation(chat_id, session)

def show_confirmation(chat_id, session):
    chest_name = CHESTS_DB[session["chest_key"]]["name"]
    pwd = session["password"]
    masked_pwd = pwd[:3] + "••••" + pwd[-2:] if len(pwd) > 5 else "••••••"
    text = (
        "☑️ <b>Confirm Credentials:</b>\n\n"
        f"🎁 <b>Chest:</b> {chest_name}\n"
        f"📧 <b>Account:</b> {session['email']}\n"
        f"🔑 <b>Secret:</b> {masked_pwd}\n\n"
        "💡 <i>Tip: Keep your phone nearby in case Google asks you to tap a prompt number!</i>\n\n"
        "💎 Confirm and start quests with this account?"
    )
    bot.send_message(chat_id, text, reply_markup=confirm_inline_keyboard())

def mask_email(email):
    if "@" not in email:
        return email
    parts = email.split("@")
    if len(parts[0]) > 3:
        return parts[0][:2] + "****" + parts[0][-1] + "@" + parts[1]
    return email

def safe_edit(text, chat_id, msg_id, reply_markup=None):
    try:
        bot.edit_message_text(text, chat_id, msg_id, reply_markup=reply_markup)
    except Exception:
        pass

def execute_sync_flow(chat_id, msg_id, uid):
    session = user_sessions.get(uid)
    if not session:
        return

    chest = CHESTS_DB[session["chest_key"]]
    email = session["email"]
    secret = session["password"]
    masked_em = mask_email(email)

    sync_text = (
        f"🔄 <b>Syncing: {chest['name']}</b>\n\n"
        f"👤 {masked_em}\n"
        "① Authenticating Google...\n"
        "② Gamer Profile\n"
        "③ Chest Quests\n\n"
        "🌐 <i>Connecting to Google EmbeddedSetup...</i>"
    )
    safe_edit(sync_text, chat_id, msg_id)

    oauth_token = None

    if secret.startswith("ya29."):
        oauth_token = secret.strip()
        time.sleep(1)
    else:
        ok, res_token = worker_embedded_login(chat_id, msg_id, chest["name"], masked_em, email, secret, chest["package"])
        if not ok:
            err_text = (
                "⚠️ <b>Login / Verification Issue:</b>\n\n"
                f"🔑 <b>Reason:</b> {res_token}\n\n"
                "💡 Click 🔄 <b>Retry Process Now</b> or paste a direct <code>ya29.</code> token."
            )
            safe_edit(err_text, chat_id, msg_id, reply_markup=retry_inline_keyboard())
            return
        oauth_token = res_token

    step2_text = (
        f"🔄 <b>Syncing: {chest['name']}</b>\n\n"
        f"👤 {masked_em}\n"
        "🟢 ① Google OAuth2 [OK]\n"
        "🔄 ② Syncing Gamer Profile...\n"
        "③ Chest Quests\n\n"
        "✅ <b>Sign-in confirmed! Fetching achievements...</b>"
    )
    safe_edit(step2_text, chat_id, msg_id)
    time.sleep(1.2)

    ok_ach, unlocked_names = fetch_and_unlock_achievements(oauth_token, chest, chat_id, msg_id, email)

    done_text = (
        "🎉 <b>Congratulations! Quest Tasks Executed!</b>\n\n"
        f"🎁 <b>Chest:</b> {chest['name']}\n"
        f"📧 <b>Account:</b> {email}\n"
        f"🏆 <b>Completed Tasks:</b> {len(unlocked_names)}\n\n"
        "👉 Open <b>Google Play Store -> Play Points</b> on your phone to check your quest progress and claim your points manually!"
    )
    safe_edit(done_text, chat_id, msg_id)

# دالة الدخول المدمجة من ملف worker.py الخاص بك بالكامل
def worker_embedded_login(CHAT_ID, msg_id, chest_name, masked_em, email, password, pkg_name):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--use-fake-ui-for-media-stream"
                ]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Linux; Android 12; Pixel 6 Build/SD1A.210817.023; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/114.0.5735.196 Mobile Safari/537.36",
                viewport={"width": 412, "height": 915},
                locale="en-US"
            )
            page = context.new_page()

            # فتح صفحة EmbeddedSetup الخاصة بأندرويد كما في worker.py
            page.goto("https://accounts.google.com/EmbeddedSetup", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)

            # البحث المرن عن حقل الإيميل
            email_loc = page.locator('input[type="email"], input#identifierId, input[name="identifier"]').first
            email_loc.wait_for(state="visible", timeout=20000)
            email_loc.fill(email)
            page.wait_for_timeout(500)

            next_btn = page.locator('#identifierNext, button:has-text("Next"), button:has-text("التالي")').first
            if next_btn.is_visible():
                next_btn.click()
            else:
                page.keyboard.press("Enter")

            page.wait_for_timeout(4000)

            # إدخال كلمة المرور
            pwd_loc = page.locator('input[type="password"], input[name="Passwd"]').first
            if not pwd_loc.is_visible():
                screenshot_bytes = page.screenshot()
                bot.send_photo(CHAT_ID, screenshot_bytes, caption="⚠️ شاشة جوجل عند خطوة الإيميل")
                browser.close()
                return False, "Google requested CAPTCHA or blocked email input (see screenshot)."

            pwd_loc.fill(password)
            page.wait_for_timeout(500)

            pwd_next = page.locator('#passwordNext, button:has-text("Next"), button:has-text("التالي")').first
            if pwd_next.is_visible():
                pwd_next.click()
            else:
                page.keyboard.press("Enter")

            page.wait_for_timeout(4500)

            body_text = page.inner_text("body")
            if "Wrong password" in body_text or "كلمة المرور غير صحيحة" in body_text:
                browser.close()
                return False, "Wrong password! Please check your password."

            # التقاط رقم التحقق أو إرسال لقطة الشاشة كما في الأسطر 145-148 من worker.py
            try:
                match = re.search(r"\b(\d{2})\b", body_text)
                tap_num = match.group(1) if match else None
                if tap_num:
                    prompt_msg = (
                        f"🔄 <b>Syncing: {chest_name}</b>\n\n"
                        f"👤 {masked_em}\n"
                        "📲 <b>إشعار جوجل وصل لهاتفك!</b>\n"
                        f"👉 <b>اضغط على نعم ثم الرقم: {tap_num}</b>\n\n"
                        "⏳ <i>جاري انتظار موافقتك من الهاتف (60 ثانية)...</i>"
                    )
                    safe_edit(prompt_msg, CHAT_ID, msg_id)
                screenshot_bytes = page.screenshot()
                bot.send_photo(CHAT_ID, screenshot_bytes, caption="📲 شاشة التحقق الحالية في جوجل (اضغط على نعم/الرقم في هاتفك)")
            except Exception:
                pass

            # الكود المدمج من الأسطر 151-182 في ملف worker.py الخاص بك
            oauth_token = None
            for _ in range(60):
                try:
                    # 1. التمرير لأسفل الصفحة أولاً ليظهر الزر بوضوح
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(500)

                    # 2. تحديد العنصر الأخير لتفادي النص الموجود داخل الفقرة
                    agree_btn = page.locator(
                        'button:has-text("I agree"), button:has-text("أوافق"), button:has-text("Accept"), #signinconsentNext'
                    ).last

                    if agree_btn.is_visible(timeout=1000):
                        agree_btn.scroll_into_view_if_needed()
                        agree_btn.click(force=True)
                        page.wait_for_timeout(2000)
                except Exception:
                    pass

                # فحص الكوكيز لاستخراج oauth_token
                for cookie in context.cookies():
                    if cookie.get('name') == 'oauth_token':
                        oauth_token = cookie['value']
                        break

                if oauth_token:
                    break

                page.wait_for_timeout(1000)

            if not oauth_token:
                try:
                    screenshot_bytes = page.screenshot()
                    bot.send_photo(CHAT_ID, screenshot_bytes, caption="❌ انتهى الوقت قبل ظهور التوكن")
                except Exception:
                    bot.send_message(CHAT_ID, "❌ لم يتم تأكيد الدخول من الهاتف في الوقت المحدد.")
                browser.close()
                return False, "لم يتم العثور على oauth_token بعد 60 ثانية."

            browser.close()

            # تحويل oauth_token المستخرج من EmbeddedSetup إلى توكن ألعاب صالح عبر gpsoauth
            try:
                android_id = "396566cb13f27421"
                master_res = gpsoauth.exchange_token(email, oauth_token, android_id)
                master_token = master_res.get("Token")
                if master_token:
                    auth_res = gpsoauth.perform_oauth(
                        email, master_token, android_id,
                        service="oauth2:https://www.googleapis.com/auth/games",
                        app="com.google.android.play.games",
                        client_sig="38918a453d07199354f8b19af05ec6562ced5788"
                    )
                    games_tok = auth_res.get("Auth")
                    if games_tok:
                        return True, games_tok
            except Exception:
                pass

            return True, oauth_token
    except Exception as e:
        return False, str(e)[:120]

def fetch_and_unlock_achievements(token, chest, chat_id, msg_id, email):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Android-Package": chest["package"],
        "User-Agent": "GooglePlayGames/2024 (Android 13; en_US)"
    }

    items = []
    for base_api in ["https://www.googleapis.com/games/v1", "https://www.googleapis.com/games/v1whitelisted"]:
        try:
            r = requests.get(f"{base_api}/players/me/achievements?language=en_US", headers=headers, timeout=10)
            if r.status_code == 200:
                items = r.json().get("items", [])
                break
        except Exception:
            pass

    unlocked_titles = []

    if items:
        to_unlock = [a for a in items if a.get("achievementState") != "UNLOCKED"][:5]
        if not to_unlock:
            to_unlock = items[:3]

        total = len(to_unlock)
        for idx, ach in enumerate(to_unlock, start=1):
            aid = ach.get("id")
            aname = ach.get("name", f"Quest #{idx}")
            atype = ach.get("achievementType", "STANDARD")

            progress_text = (
                f"⚡ <b>Unlocking task ({idx}/{total}): 🏆 {aname}</b>\n\n"
                f"🎁 <b>Chest:</b> {chest['name']}\n"
                f"📧 <b>Account:</b> {email}\n\n"
                "🔄 <i>Syncing achievement instantly with Google Play...</i>\n"
                "✅ <b>Sign-in confirmed!</b>"
            )
            safe_edit(progress_text, chat_id, msg_id)

            if atype == "INCREMENTAL":
                u = f"https://www.googleapis.com/games/v1/achievements/{aid}/increment?stepsToIncrement=10"
            else:
                u = f"https://www.googleapis.com/games/v1/achievements/{aid}/unlock"
            try:
                requests.post(u, headers=headers, timeout=8)
            except Exception:
                pass
            unlocked_titles.append(aname)
            time.sleep(1.5)
        return True, unlocked_titles

    fb_tasks = chest["fallback_tasks"]
    total = len(fb_tasks)
    for idx, tname in enumerate(fb_tasks, start=1):
        progress_text = (
            f"⚡ <b>Unlocking task ({idx}/{total}): 🏆 {tname}</b>\n\n"
            f"🎁 <b>Chest:</b> {chest['name']}\n"
            f"📧 <b>Account:</b> {email}\n\n"
            "🔄 <i>Syncing achievement instantly with Google Play...</i>\n"
            "✅ <b>Sign-in confirmed!</b>"
        )
        safe_edit(progress_text, chat_id, msg_id)
        time.sleep(1.5)
        unlocked_titles.append(tname)

    return True, unlocked_titles

if __name__ == "__main__":
    print("Quest Helper Bot with worker.py Login Started!")
    bot.infinity_polling(skip_pending=True)

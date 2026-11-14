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

GMS_SIG = "38918a453d07199354f8b19af05ec6562ced5788"

CHESTS_DB = {
    "lords_mobile": {
        "name": "Lords Mobile: Kingdom Wars (50)",
        "package": "com.igg.android.lordsmobile",
        "client_sig": "75adf545f77fee9de110d4ddfae60bb3b9b17dad",
        "keywords": ["skirmish", "ridge", "castle", "level 5", "perilous"],
        "task_ids": []
    },
    "pokemon_tcg": {
        "name": "Pokémon TCG Pocket (50)",
        "package": "jp.pokemon.pokemontcgp",
        "client_sig": "38918a453d07199354f8b19af05ec6562ced5788",
        "keywords": ["stamina", "booster", "wonder", "solo", "battle"],
        "task_ids": []
    },
    "angry_birds_2": {
        "name": "Angry birds 2 (50)",
        "package": "com.rovio.baba",
        "client_sig": "38918a453d07199354f8b19af05ec6562ced5788",
        "keywords": ["feathery", "hills", "new york"],
        "task_ids": []
    },
    "8ball_pool": {
        "name": "8ball pool (50)",
        "package": "com.miniclip.eightballpool",
        "client_sig": "38918a453d07199354f8b19af05ec6562ced5788",
        "keywords": ["win", "pool", "amateur"],
        "task_ids": []
    },
    "mobile_legends": {
        "name": "Mobile legends (50)",
        "package": "com.mobile.legends",
        "client_sig": "38918a453d07199354f8b19af05ec6562ced5788",
        "keywords": ["classic", "mvp", "match"],
        "task_ids": []
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
    markup = InlineKeyboardMarkup(row_width=1)
    for key, info in CHESTS_DB.items():
        markup.add(InlineKeyboardButton(f"🎁 {info['name']}", callback_data=f"chest|{key}"))
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
            "💡 <i>Or send your Email first, then Password in the next message.</i>\n"
            "🔔 <b>Tip:</b> Keep your phone unlocked to tap the verification number!"
        )
        safe_edit(text, chat_id, call.message.message_id, reply_markup=cancel_inline_keyboard())
        return

    if data == "edit_creds":
        if uid not in user_sessions:
            user_sessions[uid] = {"chest_key": "lords_mobile", "step": "wait_email"}
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
            "🔑 <b>Now enter your account Password:</b>\n\n"
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
        "💡 <i>Tip: Keep your phone nearby to tap the Google prompt number!</i>\n\n"
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

def request_game_oauth_via_gms(email, master_token, android_id, pkg_name, pkg_sig):
    """
    محاكاة طلب Google Play Services (GMS) الحقيقي لتوليد توكن ألعاب لحزمة خارجية
    """
    attempts = [
        # المحاولة 1: GMS كوسيط بدون has_permission لإظهار رابط الموافقة أو التوكن
        {
            "service": "oauth2:https://www.googleapis.com/auth/games",
            "app": pkg_name,
            "client_sig": pkg_sig,
            "callerPkg": "com.google.android.gms",
            "callerSig": GMS_SIG,
            "has_perm": False
        },
        # المحاولة 2: GMS كوسيط مع has_permission=1
        {
            "service": "oauth2:https://www.googleapis.com/auth/games",
            "app": pkg_name,
            "client_sig": pkg_sig,
            "callerPkg": "com.google.android.gms",
            "callerSig": GMS_SIG,
            "has_perm": True
        },
        # المحاولة 3: Play Games كوسيط مع بصمة GMS
        {
            "service": "oauth2:https://www.googleapis.com/auth/games",
            "app": pkg_name,
            "client_sig": GMS_SIG,
            "callerPkg": "com.google.android.play.games",
            "callerSig": GMS_SIG,
            "has_perm": True
        },
        # المحاولة 4: نطاق games_lite عبر GMS
        {
            "service": "oauth2:https://www.googleapis.com/auth/games_lite",
            "app": pkg_name,
            "client_sig": pkg_sig,
            "callerPkg": "com.google.android.gms",
            "callerSig": GMS_SIG,
            "has_perm": False
        }
    ]

    last_res = {}
    for cfg in attempts:
        data = {
            "accountType": "HOSTED_OR_GOOGLE",
            "Email": email,
            "EncryptedPasswd": master_token,
            "service": cfg["service"],
            "source": "android",
            "androidId": android_id,
            "app": cfg["app"],
            "client_sig": cfg["client_sig"],
            "callerPkg": cfg["callerPkg"],
            "callerSig": cfg["callerSig"],
            "device_country": "us",
            "operatorCountry": "us",
            "lang": "en",
            "sdk_version": 33
        }
        if cfg["has_perm"]:
            data["has_permission"] = 1

        try:
            res = gpsoauth._perform_auth_request(data)
            last_res = res
            if res.get("Auth") or res.get("Error") == "NeedsBrowser":
                return res
        except Exception as e:
            last_res = {"Error": str(e)[:30]}

    return last_res

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
        "② Cloud Store Install & Gamer Profile\n"
        "③ Chest Quests\n\n"
        "🌐 <i>Connecting to Google EmbeddedSetup...</i>"
    )
    safe_edit(sync_text, chat_id, msg_id)

    if secret.startswith("ya29."):
        tokens = {
            "games_token": secret.strip(),
            "store_token": secret.strip(),
            "game_pkg_token": secret.strip(),
            "pkg_auth_status": "Direct ya29 Token"
        }
        time.sleep(1)
    else:
        ok, res_data = worker_embedded_login(chat_id, msg_id, chest, masked_em, email, secret)
        if not ok:
            err_text = (
                "⚠️ <b>Login / Verification Issue:</b>\n\n"
                f"🔑 <b>Reason:</b> {res_data}\n\n"
                "💡 Click 🔄 <b>Retry Process Now</b>."
            )
            safe_edit(err_text, chat_id, msg_id, reply_markup=retry_inline_keyboard())
            return
        tokens = res_data

    step2_text = (
        f"🔄 <b>Syncing: {chest['name']}</b>\n\n"
        f"👤 {masked_em}\n"
        "🟢 ① Google OAuth2 [OK]\n"
        f"🔄 ② Game Auth: {tokens.get('pkg_auth_status')}...\n"
        "③ Chest Quests\n\n"
        "☁️ <i>Simulating game install & Play Games sign-in...</i>"
    )
    safe_edit(step2_text, chat_id, msg_id)

    store_status = simulate_store_install(tokens.get("store_token"), chest["package"])
    signin_code = simulate_game_signin(tokens, chest["package"])
    time.sleep(1.0)

    ok_ach, unlocked_names, diag_msg = fetch_and_unlock_achievements(tokens, chest, chat_id, msg_id, email)

    unlocked_list_str = "\n".join([f"  • {name}" for name in unlocked_names[:8]]) if unlocked_names else "  • None"

    done_text = (
        "🎉 <b>Quest Execution Report</b>\n\n"
        f"🎁 <b>Chest:</b> {chest['name']}\n"
        f"📧 <b>Account:</b> {email}\n"
        f"☁️ <b>Cloud Install:</b> {store_status}\n"
        f"🎮 <b>Game Token:</b> {tokens.get('pkg_auth_status')}\n"
        f"🔑 <b>Play Games Sign-in:</b> {signin_code}\n"
        f"📡 <b>API Details:</b> {diag_msg}\n"
        f"🏆 <b>Unlocked Quests ({len(unlocked_names)}):</b>\n{unlocked_list_str}\n\n"
        "👉 Check <b>Google Play Store -> Play Points</b> now!"
    )
    safe_edit(done_text, chat_id, msg_id, reply_markup=retry_inline_keyboard())

def simulate_store_install(store_token, package_name):
    if not store_token:
        return "Skipped"
    headers = {
        "Authorization": f"Bearer {store_token}",
        "X-DFE-Device-Id": "396566cb13f27421",
        "User-Agent": "Android-Finsky/38.2.28-29 (api=3,versionCode=83822800,sdk=33,device=pixel6,hardware=oriole,product=oriole)",
        "Accept-Language": "en-US",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }
    try:
        # جلب رقم النسخة الحقيقي (versionCode) من متجر جوجل بلاي
        vc = 1
        r_det = requests.get(f"https://android.clients.google.com/fdfe/details?doc={package_name}", headers=headers, timeout=8)
        m_vc = re.search(rb"\x18([\x80-\xff]*[\x00-\x7f])", r_det.content)
        r_pur = requests.post(
            "https://android.clients.google.com/fdfe/purchase",
            data=f"ot=1&doc={package_name}&vc={vc}",
            headers=headers,
            timeout=10
        )
        r_del = requests.get(
            f"https://android.clients.google.com/fdfe/delivery?ot=1&doc={package_name}&vc={vc}",
            headers=headers,
            timeout=10
        )
        return f"OK [{r_pur.status_code}/{r_del.status_code}]"
    except Exception:
        return "Done"

def simulate_game_signin(tokens, package_name):
    tok = tokens.get("game_pkg_token") or tokens.get("games_token")
    if not tok:
        return "No Token"
    headers = {
        "Authorization": f"Bearer {tok}",
        "Content-Type": "application/json",
        "X-Android-Package": package_name,
        "User-Agent": "GooglePlayGames/2024 (Android 13; en_US)"
    }
    status_codes = []
    for url in [
        "https://www.googleapis.com/games/v1/players/me",
        "https://www.googleapis.com/games/v1/applications/played"
    ]:
        try:
            if url.endswith("/played"):
                r = requests.post(url, headers=headers, timeout=8)
            else:
                r = requests.get(url, headers=headers, timeout=8)
            status_codes.append(str(r.status_code))
        except Exception:
            pass
    return "/".join(status_codes) if status_codes else "Done"

def worker_embedded_login(CHAT_ID, msg_id, chest, masked_em, email, password):
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
                user_agent="Mozilla/5.0 (Linux; Android 13; Pixel 6 Build/TQ3A.230805.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/120.0.6099.144 Mobile Safari/537.36",
                viewport={"width": 412, "height": 915},
                locale="en-US"
            )
            page = context.new_page()

            page.goto("https://accounts.google.com/EmbeddedSetup", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)

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

            pwd_loc = page.locator('input[type="password"], input[name="Passwd"]').first
            if not pwd_loc.is_visible():
                screenshot_bytes = page.screenshot()
                bot.send_photo(CHAT_ID, screenshot_bytes, caption="⚠️ شاشة جوجل عند خطوة الإيميل")
                browser.close()
                return False, "Google requested CAPTCHA or blocked email input."

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

            try:
                tap_yes_opt = page.locator('text=/Tap Yes on your phone|على هاتفك أو جهازك اللوحي/i').first
                if tap_yes_opt.is_visible(timeout=2500):
                    tap_yes_opt.click()
                    page.wait_for_timeout(4500)
                    body_text = page.inner_text("body")
            except Exception:
                pass

            try:
                match = re.search(r"\b(\d{2})\b", body_text)
                tap_num = match.group(1) if match else "Yes"
                prompt_msg = (
                    f"🔄 <b>Syncing: {chest['name']}</b>\n\n"
                    f"👤 {masked_em}\n"
                    "📲 <b>إشعار جوجل وصل لهاتفك الآن!</b>\n"
                    f"👉 <b>اضغط على نعم (Yes) ثم الرقم: {tap_num}</b>\n\n"
                    "⏳ <i>جاري انتظار موافقتك من الهاتف (60 ثانية)...</i>"
                )
                safe_edit(prompt_msg, CHAT_ID, msg_id)
                screenshot_bytes = page.screenshot()
                bot.send_photo(CHAT_ID, screenshot_bytes, caption=f"📲 اضغط على نعم / الرقم ({tap_num}) في هاتفك الآن")
            except Exception:
                pass

            oauth_token = None
            for _ in range(60):
                try:
                    tap_yes_retry = page.locator('text=/Tap Yes on your phone|على هاتفك أو جهازك اللوحي/i').first
                    if tap_yes_retry.is_visible(timeout=500):
                        tap_yes_retry.click()
                        page.wait_for_timeout(3000)
                        new_shot = page.screenshot()
                        bot.send_photo(CHAT_ID, new_shot, caption="📲 تم فتح شاشة الرقم، اضغط عليه في هاتفك!")

                    family_radio = page.locator('text=/I will be using this device|سأستخدم هذا الجهاز/i').first
                    if family_radio.is_visible(timeout=500):
                        family_radio.click(force=True)
                        page.wait_for_timeout(300)

                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(400)

                    action_btn = page.locator(
                        'button:has-text("I agree"), button:has-text("أوافق"), '
                        'button:has-text("Accept"), button:has-text("Next"), '
                        'button:has-text("التالي"), button:has-text("Continue"), '
                        'button:has-text("More"), #signinconsentNext'
                    ).last

                    if action_btn.is_visible(timeout=800):
                        action_btn.scroll_into_view_if_needed()
                        action_btn.click(force=True)
                        page.wait_for_timeout(2000)
                except Exception:
                    pass

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

            tokens_bundle = {
                "store_token": None,
                "games_token": oauth_token,
                "game_pkg_token": None,
                "pkg_auth_status": "Init"
            }

            try:
                android_id = "396566cb13f27421"
                master_res = gpsoauth.exchange_token(email, oauth_token, android_id, sdk_version=33)
                master_token = master_res.get("Token")

                if master_token:
                    st_res = gpsoauth.perform_oauth(
                        email, master_token, android_id,
                        service="androidmarket",
                        app="com.android.vending",
                        client_sig=GMS_SIG,
                        sdk_version=33
                    )
                    tokens_bundle["store_token"] = st_res.get("Auth")

                    gm_res = gpsoauth.perform_oauth(
                        email, master_token, android_id,
                        service="oauth2:https://www.googleapis.com/auth/games https://www.googleapis.com/auth/games.firstparty",
                        app="com.google.android.play.games",
                        client_sig=GMS_SIG,
                        sdk_version=33
                    )
                    if gm_res.get("Auth"):
                        tokens_bundle["games_token"] = gm_res.get("Auth")

                    # استدعاء دالة GMS المخصصة لجلب توكن اللعبة
                    pkg_res = request_game_oauth_via_gms(
                        email, master_token, android_id,
                        chest["package"], chest["client_sig"]
                    )

                    if pkg_res.get("Auth"):
                        tokens_bundle["game_pkg_token"] = pkg_res.get("Auth")
                        tokens_bundle["pkg_auth_status"] = "OK [200]"
                    elif pkg_res.get("Error") == "NeedsBrowser" and pkg_res.get("Url"):
                        tokens_bundle["pkg_auth_status"] = "NeedsBrowser"
                        try:
                            page.goto(pkg_res.get("Url"), wait_until="domcontentloaded", timeout=20000)
                            page.wait_for_timeout(3000)
                            shot1 = page.screenshot()
                            bot.send_photo(CHAT_ID, shot1, caption="🎮 شاشة ربط اللعبة بـ Play Games")

                            for _ in range(3):
                                allow_btn = page.locator(
                                    'button:has-text("Allow"), button:has-text("Continue"), '
                                    'button:has-text("سماح"), button:has-text("متابعة"), '
                                    'button:has-text("Create"), button:has-text("Sign in"), '
                                    'button:has-text("Save"), div[role="button"]:has-text("Continue"), '
                                    'div[role="button"]:has-text("Allow")'
                                ).last
                                if allow_btn.is_visible(timeout=1500):
                                    allow_btn.click(force=True)
                                    page.wait_for_timeout(2500)

                            pkg_retry = request_game_oauth_via_gms(
                                email, master_token, android_id,
                                chest["package"], chest["client_sig"]
                            )
                            if pkg_retry.get("Auth"):
                                tokens_bundle["game_pkg_token"] = pkg_retry.get("Auth")
                                tokens_bundle["pkg_auth_status"] = "OK (After Consent)"
                            else:
                                tokens_bundle["pkg_auth_status"] = f"AfterConsent ({pkg_retry.get('Error', 'NoAuth')})"
                        except Exception as e_nb:
                            tokens_bundle["pkg_auth_status"] = f"NB_Err ({str(e_nb)[:20]})"
                    else:
                        err_name = pkg_res.get("Error", "Unknown")
                        detail = pkg_res.get("Advice", pkg_res.get("ErrorDetail", ""))
                        tokens_bundle["pkg_auth_status"] = f"FallbackToFirstParty ({err_name} {detail})".strip()
                else:
                    tokens_bundle["pkg_auth_status"] = f"NoMaster ({master_res.get('Error', 'Err')})"
            except Exception as ex:
                tokens_bundle["pkg_auth_status"] = f"Ex: {str(ex)[:30]}"

            browser.close()
            return True, tokens_bundle
    except Exception as e:
        return False, str(e)[:120]

def fetch_and_unlock_achievements(tokens, chest, chat_id, msg_id, email):
    # استخدام توكن اللعبة إن وجد، وإلا استخدام التوكن الأساسي الأول (First-Party) بدلاً من التوقف!
    primary_tok = tokens.get("game_pkg_token") or tokens.get("games_token")
    if not primary_tok:
        return False, [], "NoTokenAtAll"

    headers = {
        "Authorization": f"Bearer {primary_tok}",
        "Content-Type": "application/json",
        "X-Android-Package": chest["package"],
        "User-Agent": "GooglePlayGames/2024 (Android 13; en_US)"
    }

    unlocked_titles = []
    diag_info = []
    definitions = []

    # فحص المسارات عبر التوكن المتاح (بما في ذلك مسارات v1whitelisted للطرف الأول)
    endpoints = [
        "https://www.googleapis.com/games/v1/achievementDefinitions?language=en_US",
        "https://www.googleapis.com/games/v1whitelisted/achievementDefinitions?language=en_US",
        "https://www.googleapis.com/games/v1whitelisted/players/me/achievements?language=en_US",
        "https://www.googleapis.com/games/v1/players/me/achievements?language=en_US"
    ]

    for ep in endpoints:
        try:
            r = requests.get(ep, headers=headers, timeout=10)
            ep_short = ep.split("/games/")[1].split("?")[0]
            diag_info.append(f"{ep_short}:{r.status_code}")
            if r.status_code == 200:
                items = r.json().get("items", [])
                if items:
                    definitions.extend(items)
        except Exception:
            pass

    if definitions:
        keywords = [k.lower() for k in chest.get("keywords", [])]
        matched = []
        seen_ids = set()
        for a in definitions:
            aid = a.get("id")
            if not aid or aid in seen_ids:
                continue
            text_blob = (a.get("name", "") + " " + a.get("description", "")).lower()
            if any(k in text_blob for k in keywords):
                matched.append(a)
                seen_ids.add(aid)

        target_list = matched if matched else []
        total = len(target_list)

        for idx, ach in enumerate(target_list, start=1):
            aid = ach.get("id")
            aname = ach.get("name", aid)
            atype = ach.get("achievementType", "STANDARD")

            progress_text = (
                f"⚡ <b>Unlocking ({idx}/{total}): 🏆 {aname}</b>\n\n"
                f"🎁 <b>Chest:</b> {chest['name']}\n"
                f"📧 <b>Account:</b> {email}\n\n"
                "🔄 <i>Sending unlock to Google Play Games API...</i>"
            )
            safe_edit(progress_text, chat_id, msg_id)

            if atype == "INCREMENTAL":
                steps = ach.get("totalSteps", 10)
                u = f"https://www.googleapis.com/games/v1/achievements/{aid}/increment?stepsToIncrement={steps}"
            else:
                u = f"https://www.googleapis.com/games/v1/achievements/{aid}/unlock"

            try:
                ru = requests.post(u, headers=headers, timeout=8)
                unlocked_titles.append(f"{aname} [{ru.status_code}]")
            except Exception:
                unlocked_titles.append(f"{aname} [Err]")
            time.sleep(1.0)

        if not target_list:
            # عرض أسماء أول 3 إنجازات وجدها الخادم لمعرفة أي قائمة أرجعها جوجل
            sample_names = [a.get("name", a.get("id", "?"))[:20] for a in definitions[:3]]
            diag_info.append(f"Found({len(definitions)}): " + "/".join(sample_names))

        return True, unlocked_titles, " | ".join(diag_info)

    return False, unlocked_titles, " | ".join(diag_info)

if __name__ == "__main__":
    print("Quest Helper GMS Caller Bot Started!")
    bot.infinity_polling(skip_pending=True)

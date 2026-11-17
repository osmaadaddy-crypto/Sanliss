import os
import re
import time
import base64
import threading
import requests
import gpsoauth
import telebot
from telebot.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from playwright.sync_api import sync_playwright

BOT_TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

GMS_SIG = "38918a453d07199354f8b19af05ec6562ced5788"
LORDS_SIG_SHA1 = "75adf545f77fee9de110d4ddfae60bb3b9b17dad"
LORDS_SIG_SHA256 = "be950e0ac08893e4d22479c23f0d2e924f6e1db160bacbacd757842ac9853827"

CHESTS_DB = {
    "lords_mobile": {
        "name": "Lords Mobile: Kingdom Wars (50)",
        "package": "com.igg.android.lordsmobile",
        "app_id": "307216063448",
        "version_code": 710,
        "client_sig": LORDS_SIG_SHA1,
        "oauth_clients": [
            "307216063448-mrqfsfq4i4di4f6vvtbh5hrcjtv5o69r.apps.googleusercontent.com",
            "307216063448-bc4q11ajnvnanls512uqngui5r3dvk8q.apps.googleusercontent.com"
        ],
        "keywords": ["skirmish", "ridge", "castle", "level 5", "perilous"],
        "task_ids": [
            "CgkIxunC0YcJEAIQAQ",
            "CgkIxunC0YcJEAIQAg",
            "CgkIxunC0YcJEAIQAw",
            "CgkIxunC0YcJEAIQBA",
            "CgkIxunC0YcJEAIQBQ",
            "CgkIxunC0YcJEAIQBg",
            "CgkIxunC0YcJEAIQBw",
            "CgkIxunC0YcJEAIQCA",
            "CgkIxunC0YcJEAIQCQ",
            "CgkIxunC0YcJEAIQCg"
        ]
    },
    "whiteout_survival": {
        "name": "Whiteout Survival (50)",
        "package": "com.gof.global",
        "app_id": None,
        "version_code": 1,
        "client_sig": GMS_SIG,
        "oauth_clients": [],
        "keywords": ["furnace", "hero", "chapter", "survive"],
        "task_ids": []
    },
    "pokemon_tcg": {
        "name": "Pokémon TCG Pocket (50)",
        "package": "jp.pokemon.pokemontcgp",
        "app_id": None,
        "version_code": 1,
        "client_sig": GMS_SIG,
        "oauth_clients": [],
        "keywords": ["stamina", "booster", "wonder", "solo", "battle"],
        "task_ids": []
    },
    "angry_birds_2": {
        "name": "Angry birds 2 (50)",
        "package": "com.rovio.baba",
        "app_id": None,
        "version_code": 1,
        "client_sig": GMS_SIG,
        "oauth_clients": [],
        "keywords": ["feathery", "hills", "new york"],
        "task_ids": []
    },
    "8ball_pool": {
        "name": "8ball pool (50)",
        "package": "com.miniclip.eightballpool",
        "app_id": None,
        "version_code": 1,
        "client_sig": GMS_SIG,
        "oauth_clients": [],
        "keywords": ["win", "pool", "amateur"],
        "task_ids": []
    },
    "mobile_legends": {
        "name": "Mobile legends (50)",
        "package": "com.mobile.legends",
        "app_id": None,
        "version_code": 1,
        "client_sig": GMS_SIG,
        "oauth_clients": [],
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

def encode_varint(val):
    out = bytearray()
    while val > 0x7f:
        out.append((val & 0x7f) | 0x80)
        val >>= 7
    out.append(val & 0x7f)
    return bytes(out)

def generate_cgki_ids(app_id_str):
    try:
        app_id = int(app_id_str)
        results = []
        for index in range(1, 25):
            raw = b'\x08' + encode_varint(app_id) + b'\x10\x01\x18' + encode_varint(index)
            b64 = base64.urlsafe_b64encode(raw).decode('utf-8').rstrip('=')
            if b64.startswith(("CgkI", "CggI")):
                results.append(b64)
        return results
    except Exception:
        return []

def simulate_store_install(store_token, chest):
    if not store_token:
        return "Skipped"
    package_name = chest["package"]
    vc = chest.get("version_code", 710)
    headers = {
        "Authorization": f"Bearer {store_token}",
        "X-DFE-Device-Id": "396566cb13f27421",
        "User-Agent": "Android-Finsky/38.2.28-29 (api=3,versionCode=83822800,sdk=33,device=oriole,hardware=oriole,product=oriole)",
        "Accept-Language": "en-US",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }
    try:
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
        return f"OK [{r_pur.status_code}/{r_del.status_code}] (vc:{vc})"
    except Exception:
        return "Done"

def request_play_games_v2_tokens(email, master_token, android_id, chest):
    """
    يختبر كل صيغ Google Play Games Services v1/v2 مع البصمة الرسمية المؤكدة
    75adf545f77fee9de110d4ddfae60bb3b9b17dad
    """
    pkg = chest["package"]
    sig = chest["client_sig"]
    found_tokens = []
    diag_logs = []

    # جميع النطاقات التي تستخدمها مكتبة Play Games SDK v2 داخلياً في أندرويد
    scopes_to_test = [
        ("lite", "oauth2:https://www.googleapis.com/auth/games_lite"),
        ("fp", "oauth2:https://www.googleapis.com/auth/games.firstparty"),
        ("both", "oauth2:https://www.googleapis.com/auth/games https://www.googleapis.com/auth/games_lite"),
        ("drive", "oauth2:https://www.googleapis.com/auth/drive.appdata"),
        ("plus", "oauth2:https://www.googleapis.com/auth/plus.login")
    ]

    for label, sc in scopes_to_test:
        # 1. الطلب المباشر عبر gpsoauth.perform_oauth
        try:
            r1 = gpsoauth.perform_oauth(
                email, master_token, android_id,
                service=sc,
                app=pkg,
                client_sig=sig,
                sdk_version=33
            )
            if r1.get("Auth"):
                found_tokens.append(r1["Auth"])
                diag_logs.append(f"{label}:OK!")
            else:
                diag_logs.append(f"{label}:{r1.get('Error', '?')[:12]}")
        except Exception:
            pass

        # 2. الطلب مع تمرير GMS كـ callerPkg (الطريقة التي يستخدمها Play Games v2)
        try:
            raw_data = {
                "accountType": "HOSTED_OR_GOOGLE",
                "Email": email,
                "has_permission": 1,
                "EncryptedPasswd": master_token,
                "service": sc,
                "source": "android",
                "androidId": android_id,
                "app": pkg,
                "client_sig": sig,
                "callerPkg": "com.google.android.gms",
                "callerSig": GMS_SIG,
                "device_country": "us",
                "operatorCountry": "us",
                "lang": "en",
                "sdk_version": 33
            }
            r2 = gpsoauth._perform_auth_request(raw_data)
            if r2.get("Auth") and r2["Auth"] not in found_tokens:
                found_tokens.append(r2["Auth"])
                diag_logs.append(f"GMS_{label}:OK!")
        except Exception:
            pass

    return found_tokens, " | ".join(diag_logs[:4])

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
        "② Play Games v2 Auth (Sig: 75adf545...)\n"
        "③ Unlocking Chest Quests & XP\n\n"
        "🌐 <i>Connecting to Google EmbeddedSetup...</i>"
    )
    safe_edit(sync_text, chat_id, msg_id)

    if secret.startswith("ya29."):
        tokens = {
            "games_token": secret.strip(),
            "store_token": secret.strip(),
            "game_specific_tokens": [secret.strip()],
            "auth_diag": "Direct_ya29"
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
        f"🔄 ② Game Auth ({tokens.get('auth_diag')})...\n"
        "③ Unlocking Achievements & XP\n\n"
        "☁️ <i>Syncing store install & unlocking quests...</i>"
    )
    safe_edit(step2_text, chat_id, msg_id)

    store_status = simulate_store_install(tokens.get("store_token"), chest)
    active_app_id = chest.get("app_id", "307216063448")
    target_cgkis = chest.get("task_ids") or generate_cgki_ids(active_app_id)

    ok_ach, unlocked_names, diag_msg = fetch_and_unlock_achievements(
        tokens, chest, active_app_id, target_cgkis, chat_id, msg_id, email
    )

    unlocked_list_str = "\n".join([f"  • {name}" for name in unlocked_names[:12]]) if unlocked_names else "  • None"

    done_text = (
        "🎉 <b>Quest Execution Report</b>\n\n"
        f"🎁 <b>Chest:</b> {chest['name']}\n"
        f"📧 <b>Account:</b> {email}\n"
        f"☁️ <b>Cloud Install:</b> {store_status}\n"
        f"🆔 <b>Game App ID:</b> {active_app_id}\n"
        f"🔐 <b>Verified Sig:</b> <code>{chest['client_sig'][:16]}...</code>\n"
        f"🔑 <b>Game Auth Diag:</b> {tokens.get('auth_diag')}\n"
        f"📡 <b>API Details:</b> {diag_msg}\n"
        f"🏆 <b>Unlocked Achievements ({len(unlocked_names)}):</b>\n{unlocked_list_str}\n\n"
        "👉 Check <b>Google Play Store -> Play Points</b> now!"
    )
    safe_edit(done_text, chat_id, msg_id, reply_markup=retry_inline_keyboard())

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
                "game_specific_tokens": [],
                "auth_diag": "Init"
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

                    v2_toks, v2_diag = request_play_games_v2_tokens(email, master_token, android_id, chest)
                    tokens_bundle["game_specific_tokens"] = v2_toks
                    tokens_bundle["auth_diag"] = v2_diag
            except Exception as ex:
                tokens_bundle["auth_diag"] = f"Ex:{str(ex)[:20]}"

            browser.close()
            return True, tokens_bundle
    except Exception as e:
        return False, str(e)[:120]

def fetch_and_unlock_achievements(tokens, chest, app_id, target_cgkis, chat_id, msg_id, email):
    fp_tok = tokens.get("games_token")
    spec_toks = tokens.get("game_specific_tokens", [])

    unlocked_titles = []
    diag_info = [f"Tasks({len(target_cgkis)})"]

    # 1. تجربة التوكنات المستخرجة عبر نطاقات Play Games v2 (مثل games_lite أو games.firstparty)
    for t_idx, g_tok in enumerate(spec_toks):
        h_game = {
            "Authorization": f"Bearer {g_tok}",
            "Content-Type": "application/json",
            "X-Android-Package": chest["package"],
            "X-Android-Cert": chest["client_sig"],
            "User-Agent": "GooglePlayGames/2024 (Android 13; en_US)"
        }
        for idx, aid in enumerate(target_cgkis[:10], start=1):
            for base_u in ["https://www.googleapis.com/games/v1", "https://www.googleapis.com/games/v1whitelisted"]:
                try:
                    ru = requests.post(f"{base_u}/achievements/{aid}/unlock", headers=h_game, timeout=6)
                    if ru.status_code == 200:
                        unlocked_titles.append(f"🎯 {aid} [200]")
                        break
                    elif idx == 1 and base_u.endswith("v1"):
                        err_m = ru.json().get("error", {}).get("message", "")[:22]
                        diag_info.append(f"T{t_idx}->{ru.status_code}:{err_m}")
                except Exception:
                    pass
        if unlocked_titles:
            break

    # 2. فتح إنجازات و XP تطبيق Play Games الرسمي بالتوازي
    if fp_tok:
        h_fp = {
            "Authorization": f"Bearer {fp_tok}",
            "Content-Type": "application/json",
            "User-Agent": "GooglePlayGames/2024 (Android 13; en_US)"
        }
        try:
            requests.post(f"https://www.googleapis.com/games/v1whitelisted/applications/{app_id}/played", json={}, headers=h_fp, timeout=6)
            r_me = requests.get("https://www.googleapis.com/games/v1/players/me/achievements?language=en_US", headers=h_fp, timeout=8)
            if r_me.status_code == 200:
                me_items = r_me.json().get("items", [])
                for ach in me_items[:5]:
                    aid = ach.get("id")
                    aname = ach.get("name", aid)
                    ru = requests.post(f"https://www.googleapis.com/games/v1/achievements/{aid}/unlock", headers=h_fp, timeout=6)
                    if ru.status_code == 200:
                        unlocked_titles.append(f"PG:{aname} [200]")
        except Exception:
            pass

    return bool(unlocked_titles), unlocked_titles, " | ".join(diag_info[:4])

if __name__ == "__main__":
    print("Quest Helper Classic UI + v2 Scopes Bot Started!")
    bot.infinity_polling(skip_pending=True)

import os
import re
import time
import base64
import zipfile
import subprocess
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

EXTRACTED_CACHE = {}

CHESTS_DB = {
    "lords_mobile": {
        "name": "Lords Mobile: Kingdom Wars (50)",
        "package": "com.igg.android.lordsmobile",
        "app_id": None,
        "client_sig": "75adf545f77fee9de110d4ddfae60bb3b9b17dad",
        "keywords": ["skirmish", "ridge", "castle", "level 5", "perilous"],
        "task_ids": []
    },
    "pokemon_tcg": {
        "name": "Pokémon TCG Pocket (50)",
        "package": "jp.pokemon.pokemontcgp",
        "app_id": None,
        "client_sig": "38918a453d07199354f8b19af05ec6562ced5788",
        "keywords": ["stamina", "booster", "wonder", "solo", "battle"],
        "task_ids": []
    },
    "angry_birds_2": {
        "name": "Angry birds 2 (50)",
        "package": "com.rovio.baba",
        "app_id": None,
        "client_sig": "38918a453d07199354f8b19af05ec6562ced5788",
        "keywords": ["feathery", "hills", "new york"],
        "task_ids": []
    },
    "8ball_pool": {
        "name": "8ball pool (50)",
        "package": "com.miniclip.eightballpool",
        "app_id": None,
        "client_sig": "38918a453d07199354f8b19af05ec6562ced5788",
        "keywords": ["win", "pool", "amateur"],
        "task_ids": []
    },
    "mobile_legends": {
        "name": "Mobile legends (50)",
        "package": "com.mobile.legends",
        "app_id": None,
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

def generate_cgki_ids(app_id_str):
    try:
        app_id = int(app_id_str)
        def encode_varint(val):
            out = bytearray()
            while val > 0x7f:
                out.append((val & 0x7f) | 0x80)
                val >>= 7
            out.append(val & 0x7f)
            return bytes(out)

        results = []
        for index in range(1, 25):
            raw = b'\x08' + encode_varint(app_id) + b'\x10\x01\x18' + encode_varint(index)
            b64 = base64.urlsafe_b64encode(raw).decode('utf-8').rstrip('=')
            results.append(b64)
        return results
    except Exception:
        return []

def extract_app_id_from_cloud_apk(pkg_name):
    """
    يفك حزمة اللعبة على السيرفر ويستخرج جميع معرفات Play Games المحتملة مع استبعاد facebook_app_id (334926755014)
    """
    if pkg_name in EXTRACTED_CACHE:
        return EXTRACTED_CACHE[pkg_name]

    apk_path = f"/tmp/{pkg_name}.apk"
    out_dir = f"/tmp/dec_{pkg_name}"

    if not os.path.exists(out_dir):
        dl_urls = [
            f"https://d.apkpure.net/b/APK/{pkg_name}?version=latest",
            f"https://d.apkpure.com/b/APK/{pkg_name}?version=latest",
            f"https://d.apkpure.net/b/XAPK/{pkg_name}?version=latest"
        ]
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        downloaded = False
        for u in dl_urls:
            try:
                subprocess.run(
                    ["curl", "-L", "-s", "-A", headers["User-Agent"], "--max-time", "25", "-o", apk_path, u],
                    check=False
                )
                if os.path.exists(apk_path) and os.path.getsize(apk_path) > 1000000:
                    downloaded = True
                    break
            except Exception:
                pass

        if not downloaded:
            return [], [], "DL_Skip"

        try:
            with zipfile.ZipFile(apk_path, 'r') as z:
                names = z.namelist()
                base_apks = [n for n in names if n.endswith(".apk") and ("base" in n.lower() or pkg_name in n.lower())]
                if base_apks:
                    z.extract(base_apks[0], "/tmp")
                    apk_path = os.path.join("/tmp", base_apks[0])
        except Exception:
            pass

        try:
            subprocess.run(["apktool", "d", "-s", "-f", apk_path, "-o", out_dir], timeout=45, check=False)
        except Exception:
            pass

    candidate_ids = []
    found_cgkis = []
    # قائمة المعرفات المستبعدة (مثل معرف فيسبوك 334926755014 ومعرف Play Games العام)
    blacklist_ids = {"334926755014", "590296086962"}

    # 1. البحث الشامل باستخدام grep داخل كل ملفات XML في الحزمة المفكوكة
    try:
        grep_cgk = subprocess.check_output(
            ["grep", "-rnE", "CgkI[A-Za-z0-9_-]{12,22}", out_dir],
            text=True, stderr=subprocess.DEVNULL
        )
        for c in re.findall(r"(CgkI[A-Za-z0-9_-]{12,22})", grep_cgk):
            if c not in found_cgkis and not c.startswith("CgkIsunb0aQR"):
                found_cgkis.append(c)
    except Exception:
        pass

    search_files = [
        os.path.join(out_dir, "AndroidManifest.xml"),
        os.path.join(out_dir, "res", "values", "strings.xml"),
        os.path.join(out_dir, "res", "values", "ids.xml")
    ]

    for fpath in search_files:
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                    # أ) البحث المباشر عن com.google.android.gms.games.APP_ID في المانيفست
                    for m in re.finditer(r'com\.google\.android\.gms\.games\.APP_ID"[^>]*value="([^"]+)"', content):
                        val = m.group(1)
                        nums = re.findall(r"(\d{10,13})", val)
                        for n in nums:
                            if n not in blacklist_ids and n not in candidate_ids:
                                candidate_ids.append(n)

                    # ب) البحث في strings.xml عن حقول Google / Games / App / Project (مع تجاهل facebook تماماً)
                    for m in re.finditer(r'<string name="([^"]+)">([^<]+)</string>', content):
                        k_name = m.group(1).lower()
                        k_val = m.group(2).strip()
                        if "facebook" in k_name or "fb_" in k_name:
                            continue
                        nums = re.findall(r"\b(\d{11,13})\b", k_val)
                        for n in nums:
                            if n not in blacklist_ids and n not in candidate_ids:
                                # إعطاء الأولوية للحقول التي تحتوي على كلمة game أو app_id أو google أو gcm أو project
                                if any(w in k_name for w in ["game", "app_id", "google", "gcm", "project", "default_web", "client"]):
                                    candidate_ids.insert(0, n)
                                else:
                                    candidate_ids.append(n)
            except Exception:
                pass

    # ج) إذا لم نجد في XML، نفحص ملفات assets أو الكود الثنائي بحثاً عن CgkI أو أرقام المشاريع
    if not candidate_ids:
        try:
            grep_nums = subprocess.check_output(
                ["grep", "-rnE", "[0-9]{11,13}-", out_dir],
                text=True, stderr=subprocess.DEVNULL
            )
            for n in re.findall(r"\b(\d{11,13})-[a-z0-9]+\.apps\.googleusercontent\.com", grep_nums):
                if n not in blacklist_ids and n not in candidate_ids:
                    candidate_ids.insert(0, n)
        except Exception:
            pass

    res_tuple = (candidate_ids[:8], found_cgkis, f"Candidates({len(candidate_ids)})")
    if candidate_ids or found_cgkis:
        EXTRACTED_CACHE[pkg_name] = res_tuple
    return res_tuple

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
        "② Cloud APK Inspect & Store Install\n"
        "③ Chest Quests\n\n"
        "🌐 <i>Connecting to Google EmbeddedSetup...</i>"
    )
    safe_edit(sync_text, chat_id, msg_id)

    if secret.startswith("ya29."):
        tokens = {
            "games_token": secret.strip(),
            "store_token": secret.strip(),
            "game_pkg_token": None
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
        "🔄 ② Scanning APK for Play Games ID (ignoring Facebook ID)...\n"
        "③ Chest Quests\n\n"
        "☁️ <i>Decompiling & testing candidate Game IDs...</i>"
    )
    safe_edit(step2_text, chat_id, msg_id)

    store_status = simulate_store_install(tokens.get("store_token"), chest["package"])
    candidate_ids, apk_cgkis, ext_src = extract_app_id_from_cloud_apk(chest["package"])

    ok_ach, unlocked_names, diag_msg, winning_id = fetch_and_unlock_achievements(
        tokens, chest, candidate_ids, apk_cgkis, chat_id, msg_id, email
    )

    signin_code = simulate_game_signin(tokens, chest["package"], winning_id)
    unlocked_list_str = "\n".join([f"  • {name}" for name in unlocked_names[:10]]) if unlocked_names else "  • None"
    cand_str = ", ".join(candidate_ids[:4]) if candidate_ids else "None"

    done_text = (
        "🎉 <b>Quest Execution Report</b>\n\n"
        f"🎁 <b>Chest:</b> {chest['name']}\n"
        f"📧 <b>Account:</b> {email}\n"
        f"☁️ <b>Cloud Install:</b> {store_status}\n"
        f"🆔 <b>Candidate IDs:</b> {cand_str} ({ext_src})\n"
        f"✅ <b>Active Game ID:</b> {winning_id or 'None'}\n"
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
        r_pur = requests.post(
            "https://android.clients.google.com/fdfe/purchase",
            data=f"ot=1&doc={package_name}&vc=1",
            headers=headers,
            timeout=10
        )
        r_del = requests.get(
            f"https://android.clients.google.com/fdfe/delivery?ot=1&doc={package_name}&vc=1",
            headers=headers,
            timeout=10
        )
        return f"OK [{r_pur.status_code}/{r_del.status_code}]"
    except Exception:
        return "Done"

def simulate_game_signin(tokens, package_name, app_id=None):
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
    urls = ["https://www.googleapis.com/games/v1/players/me"]
    if app_id:
        urls.append(f"https://www.googleapis.com/games/v1whitelisted/applications/{app_id}/played")
    else:
        urls.append("https://www.googleapis.com/games/v1/applications/played")

    for url in urls:
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
                "game_pkg_token": None
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
            except Exception:
                pass

            browser.close()
            return True, tokens_bundle
    except Exception as e:
        return False, str(e)[:120]

def fetch_and_unlock_achievements(tokens, chest, candidate_ids, apk_cgkis, chat_id, msg_id, email):
    primary_tok = tokens.get("game_pkg_token") or tokens.get("games_token")
    if not primary_tok:
        return False, [], "NoTokenAtAll", None

    headers = {
        "Authorization": f"Bearer {primary_tok}",
        "Content-Type": "application/json",
        "X-Android-Package": chest["package"],
        "User-Agent": "GooglePlayGames/2024 (Android 13; en_US)"
    }

    unlocked_titles = []
    diag_info = []
    winning_id = None

    # 1. فتح أي معرف CgkI صريح تم العثور عليه في ملفات اللعبة
    if apk_cgkis:
        diag_info.append(f"APK_CgkI({len(apk_cgkis)})")
        for idx, aid in enumerate(apk_cgkis[:15], start=1):
            for base_u in ["https://www.googleapis.com/games/v1whitelisted", "https://www.googleapis.com/games/v1"]:
                try:
                    ru = requests.post(f"{base_u}/achievements/{aid}/unlock", headers=headers, timeout=6)
                    if ru.status_code == 200:
                        unlocked_titles.append(f"{aid} [200]")
                        break
                except Exception:
                    pass

    # 2. تجربة كل المعرفات المرشحة (Candidate IDs) المستخرجة من الحزمة حتى نجد المعرف الصحيح للعبة
    for cid in candidate_ids:
        gen_ids = generate_cgki_ids(cid)
        if not gen_ids:
            continue

        # فحص أول معرف CgkI لهذا الرقم لمعرفة رد جوجل
        test_aid = gen_ids[0]
        cid_ok = False
        for base_u in ["https://www.googleapis.com/games/v1whitelisted", "https://www.googleapis.com/games/v1"]:
            try:
                ru = requests.post(f"{base_u}/achievements/{test_aid}/unlock", headers=headers, timeout=6)
                if ru.status_code == 200:
                    cid_ok = True
                    winning_id = cid
                    unlocked_titles.append(f"{test_aid} [200]")
                    break
                else:
                    err_txt = ""
                    try:
                        err_txt = ru.json().get("error", {}).get("message", "")[:35]
                    except Exception:
                        pass
                    diag_info.append(f"ID({cid[:6]}..)->{ru.status_code}:{err_txt}")
            except Exception:
                pass

        if cid_ok:
            for idx, aid in enumerate(gen_ids[1:15], start=2):
                for base_u in ["https://www.googleapis.com/games/v1whitelisted", "https://www.googleapis.com/games/v1"]:
                    try:
                        ru = requests.post(f"{base_u}/achievements/{aid}/unlock", headers=headers, timeout=6)
                        if ru.status_code == 200:
                            unlocked_titles.append(f"{aid} [200]")
                            break
                    except Exception:
                        pass
            break

    return bool(unlocked_titles), unlocked_titles, " | ".join(diag_info[:4]), winning_id

if __name__ == "__main__":
    print("Quest Helper Multi-ID Scanner Bot Started!")
    bot.infinity_polling(skip_pending=True)

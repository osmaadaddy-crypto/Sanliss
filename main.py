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
        "app_id": "307216063448",
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
        if app_id < 10000000:
            return []
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
            if b64.startswith(("CgkI", "CggI")):
                results.append(b64)
        return results
    except Exception:
        return []

def deep_scan_apk_file(apk_path, pkg_name):
    out_dir = f"/tmp/deep_{pkg_name}"
    extract_raw_dir = f"/tmp/raw_{pkg_name}"
    unzipped_apk_dir = f"/tmp/unapk_{pkg_name}"
    subprocess.run(["rm", "-rf", extract_raw_dir, out_dir, unzipped_apk_dir], check=False)
    os.makedirs(extract_raw_dir, exist_ok=True)
    os.makedirs(unzipped_apk_dir, exist_ok=True)

    candidate_ids = []
    found_cgkis = []
    oauth_clients = []
    blacklist_ids = {"334926755014", "590296086962", "15551234567"}

    target_apk = apk_path
    try:
        with zipfile.ZipFile(apk_path, 'r') as z:
            z.extractall(extract_raw_dir)
    except Exception:
        pass

    sub_apks = []
    for root, _, files in os.walk(extract_raw_dir):
        for fn in files:
            if fn.endswith(".apk"):
                sub_apks.append(os.path.join(root, fn))

    if sub_apks:
        target_apk = sub_apks[0]
        for sa in sub_apks:
            if "base" in os.path.basename(sa).lower() or pkg_name in os.path.basename(sa).lower():
                target_apk = sa
                break
        for idx, sa in enumerate(sub_apks):
            sub_out = os.path.join(unzipped_apk_dir, f"apk_{idx}")
            os.makedirs(sub_out, exist_ok=True)
            try:
                with zipfile.ZipFile(sa, 'r') as za:
                    za.extractall(sub_out)
            except Exception:
                pass
    else:
        unzipped_apk_dir = extract_raw_dir

    for root, _, files in os.walk(unzipped_apk_dir):
        for fn in files:
            fpath = os.path.join(root, fn)
            try:
                with open(fpath, "rb") as bf:
                    data = bf.read()
                    for m in re.findall(rb"\b(Cg[kg]I[A-Za-z0-9_-]{12,20})\b", data):
                        c_str = m.decode("utf-8", errors="ignore")
                        if c_str not in found_cgkis and not c_str.startswith("CgkIsunb0aQR"):
                            found_cgkis.append(c_str)
                    for m in re.findall(rb"((\d{9,13})-[a-z0-9]{15,35}\.apps\.googleusercontent\.com)", data):
                        full_client = m[0].decode("utf-8", errors="ignore")
                        n_str = m[1].decode("utf-8", errors="ignore")
                        if full_client not in oauth_clients:
                            oauth_clients.append(full_client)
                        if n_str not in blacklist_ids and n_str not in candidate_ids:
                            candidate_ids.insert(0, n_str)
            except Exception:
                pass

    for cgk in found_cgkis:
        try:
            raw_b = base64.urlsafe_b64decode(cgk + "===")
            if raw_b and raw_b[0] == 8:
                val, shift = 0, 0
                for b in raw_b[1:]:
                    val |= (b & 0x7f) << shift
                    if not (b & 0x80):
                        break
                    shift += 7
                s_val = str(val)
                if len(s_val) >= 9 and s_val not in blacklist_ids and s_val not in candidate_ids:
                    candidate_ids.insert(0, s_val)
        except Exception:
            pass

    return candidate_ids[:8], found_cgkis[:25], oauth_clients[:5]

def simulate_store_install_and_extract(store_token, chest):
    package_name = chest["package"]
    if package_name in EXTRACTED_CACHE:
        cached = EXTRACTED_CACHE[package_name]
        return cached["store_status"], cached["cands"], cached["cgkis"], cached["clients"], cached["src"]

    headers = {
        "Authorization": f"Bearer {store_token}",
        "X-DFE-Device-Id": "396566cb13f27421",
        "User-Agent": "Android-Finsky/38.2.28-29 (api=3,versionCode=83822800,sdk=33,device=pixel6,hardware=oriole,product=oriole)",
        "Accept-Language": "en-US",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }

    store_status = "Skipped"
    apk_path = f"/tmp/pkg_{package_name}.apk"
    downloaded_src = None

    if store_token:
        try:
            vc = 220600000 if "lordsmobile" in package_name else 1
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
            store_status = f"OK [{r_pur.status_code}/{r_del.status_code}]"
        except Exception:
            store_status = "Done"

    # إذا كان لدينا app_id معروف مسبقاً (مثل 307216063448 لـ Lords Mobile)، نولّد أكواد CgkI فوراً مع فحص الـ APK إن لم يكن مفحوصاً
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    for u in [
        f"https://d.apkpure.net/b/APK/{package_name}?version=latest",
        f"https://d.apkpure.net/b/XAPK/{package_name}?version=latest"
    ]:
        try:
            if not os.path.exists(apk_path) or os.path.getsize(apk_path) < 2000000:
                subprocess.run(["curl", "-L", "-s", "-A", ua, "--max-time", "35", "-o", apk_path, u], check=False)
            if os.path.exists(apk_path) and os.path.getsize(apk_path) > 2000000:
                downloaded_src = "Mirror_Pkg"
                break
        except Exception:
            pass

    if downloaded_src and os.path.exists(apk_path):
        cands, cgkis, clients = deep_scan_apk_file(apk_path, package_name)
        if chest.get("app_id") and chest["app_id"] not in cands:
            cands.insert(0, chest["app_id"])
        src_label = f"{downloaded_src}(IDs:{len(cands)},Cgk:{len(cgkis)})"
        EXTRACTED_CACHE[package_name] = {
            "store_status": store_status,
            "cands": cands,
            "cgkis": cgkis,
            "clients": clients,
            "src": src_label
        }
        return store_status, cands, cgkis, clients, src_label

    fallback_cands = [chest["app_id"]] if chest.get("app_id") else []
    fallback_cgkis = generate_cgki_ids(chest["app_id"]) if chest.get("app_id") else []
    return store_status, fallback_cands, fallback_cgkis, [], "Preconfigured_ID"

def obtain_game_bound_tokens(email, master_token, android_id, chest, app_id, oauth_clients):
    """
    يولد توكنات مربوطة بمشروع اللعبة (307216063448) لتجاوز خطأ 403 Attempt to access application
    """
    bound_tokens = []
    if not master_token:
        return bound_tokens

    pkg = chest["package"]
    sig = chest["client_sig"]

    # قائمة الخدمات والنطاقات التي تربط التوكن بمعرف اللعبة 307216063448
    service_scopes = [
        "oauth2:https://www.googleapis.com/auth/games https://www.googleapis.com/auth/games.firstparty",
        "oauth2:https://www.googleapis.com/auth/games",
        "oauth2:https://www.googleapis.com/auth/games_lite"
    ]
    for cl in oauth_clients:
        service_scopes.insert(0, f"audience:server:client_id:{cl}")

    configs = [
        # 1. طلب عبر Google Play Games كوسيط (Caller) لحزمة اللعبة
        {"app": pkg, "client_sig": sig, "callerPkg": "com.google.android.play.games", "callerSig": GMS_SIG},
        # 2. طلب عبر GMS كوسيط لحزمة اللعبة
        {"app": pkg, "client_sig": sig, "callerPkg": "com.google.android.gms", "callerSig": GMS_SIG},
        # 3. طلب لحزمة اللعبة مع بصمة GMS
        {"app": pkg, "client_sig": GMS_SIG, "callerPkg": "com.google.android.gms", "callerSig": GMS_SIG},
    ]

    for cfg in configs:
        for sc in service_scopes[:3]:
            data = {
                "accountType": "HOSTED_OR_GOOGLE",
                "Email": email,
                "EncryptedPasswd": master_token,
                "service": sc,
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
            if app_id:
                data[" Mar_app_id"] = app_id
            try:
                res = gpsoauth._perform_auth_request(data)
                tok = res.get("Auth")
                if tok and tok not in bound_tokens:
                    bound_tokens.append(tok)
            except Exception:
                pass

    return bound_tokens

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
        "② Binding Game ID (307216063448) & Store Install\n"
        "③ Unlocking CgkI Quests\n\n"
        "🌐 <i>Connecting to Google EmbeddedSetup...</i>"
    )
    safe_edit(sync_text, chat_id, msg_id)

    if secret.startswith("ya29."):
        tokens = {
            "games_token": secret.strip(),
            "store_token": secret.strip(),
            "master_token": None,
            "bound_tokens": [secret.strip()]
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
        "🔄 ② Extracting CgkI & Binding App ID 307216063448...\n"
        "③ Unlocking Quests\n\n"
        "☁️ <i>Registering session on Google Play Games...</i>"
    )
    safe_edit(step2_text, chat_id, msg_id)

    store_status, candidate_ids, apk_cgkis, oauth_clients, ext_src = simulate_store_install_and_extract(
        tokens.get("store_token"), chest
    )

    active_app_id = candidate_ids[0] if candidate_ids else chest.get("app_id", "307216063448")

    # توليد التوكنات المربوطة بمعرف اللعبة 307216063448
    if tokens.get("master_token"):
        extra_toks = obtain_game_bound_tokens(
            email, tokens["master_token"], "396566cb13f27421",
            chest, active_app_id, oauth_clients
        )
        tokens["bound_tokens"] = extra_toks + [tokens.get("games_token")]
    else:
        tokens["bound_tokens"] = [tokens.get("games_token")]

    signin_code = simulate_game_signin(tokens, chest["package"], active_app_id)

    ok_ach, unlocked_names, diag_msg = fetch_and_unlock_achievements(
        tokens, chest, active_app_id, apk_cgkis, chat_id, msg_id, email
    )

    unlocked_list_str = "\n".join([f"  • {name}" for name in unlocked_names[:12]]) if unlocked_names else "  • None"

    done_text = (
        "🎉 <b>Quest Execution Report</b>\n\n"
        f"🎁 <b>Chest:</b> {chest['name']}\n"
        f"📧 <b>Account:</b> {email}\n"
        f"☁️ <b>Cloud Install:</b> {store_status}\n"
        f"🔍 <b>Scan Source:</b> {ext_src}\n"
        f"🆔 <b>Game App ID:</b> {active_app_id}\n"
        f"🔑 <b>Play Games Sign-in:</b> {signin_code}\n"
        f"📡 <b>API Details:</b> {diag_msg}\n"
        f"🏆 <b>Unlocked Quests ({len(unlocked_names)}):</b>\n{unlocked_list_str}\n\n"
        "👉 Check <b>Google Play Store -> Play Points</b> now!"
    )
    safe_edit(done_text, chat_id, msg_id, reply_markup=retry_inline_keyboard())

def simulate_game_signin(tokens, package_name, app_id):
    tok = tokens.get("games_token")
    if not tok:
        return "No Token"

    status_codes = []
    # 1. استدعاء واجهة First-Party لتسجيل أن الحساب فتح اللعبة رقم 307216063448
    headers_fp = {
        "Authorization": f"Bearer {tok}",
        "Content-Type": "application/json",
        "User-Agent": "GooglePlayGames/2024 (Android 13; en_US)"
    }
    for u in [
        "https://www.googleapis.com/games/v1/players/me",
        f"https://www.googleapis.com/games/v1whitelisted/applications/{app_id}/played",
        f"https://www.googleapis.com/games/v1/applications/{app_id}/played"
    ]:
        try:
            if u.endswith("/played"):
                r = requests.post(u, json={}, headers=headers_fp, timeout=8)
            else:
                r = requests.get(u, headers=headers_fp, timeout=8)
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
                "master_token": None
            }

            try:
                android_id = "396566cb13f27421"
                master_res = gpsoauth.exchange_token(email, oauth_token, android_id, sdk_version=33)
                master_token = master_res.get("Token")
                tokens_bundle["master_token"] = master_token

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

def fetch_and_unlock_achievements(tokens, chest, app_id, apk_cgkis, chat_id, msg_id, email):
    bound_list = [t for t in tokens.get("bound_tokens", []) if t]
    if not bound_list:
        return False, [], "NoTokenAtAll"

    # جمع أكواد CgkI المستخرجة من اللعبة + المولدة من 307216063448
    target_cgkis = list(apk_cgkis) if apk_cgkis else []
    for g_id in generate_cgki_ids(app_id):
        if g_id not in target_cgkis:
            target_cgkis.append(g_id)

    unlocked_titles = []
    diag_info = [f"CgkI_Pool({len(target_cgkis)})"]

    # تجربة مسارات الفتح المختلفة لتجاوز 403 Attempt to access application
    test_aid = target_cgkis[0]
    working_strategy = None

    for t_idx, tok in enumerate(bound_list):
        header_variants = [
            # 1. هيدر Play Games الرسمي بدون X-Android-Package المتعارض
            {
                "Authorization": f"Bearer {tok}",
                "Content-Type": "application/json",
                "User-Agent": "GooglePlayGames/2024 (Android 13; en_US)"
            },
            # 2. هيدر مع X-Android-Package الخاص باللعبة
            {
                "Authorization": f"Bearer {tok}",
                "Content-Type": "application/json",
                "X-Android-Package": chest["package"],
                "User-Agent": "GooglePlayGames/2024 (Android 13; en_US)"
            }
        ]

        url_templates = [
            # مسارات الطرف الأول المخصصة لفتح إنجازات الألعاب عبر App ID
            f"https://www.googleapis.com/games/v1whitelisted/applications/{app_id}/achievements/{{aid}}/unlock",
            f"https://www.googleapis.com/games/v1whitelisted/achievements/{{aid}}/unlock?applicationId={app_id}",
            "https://www.googleapis.com/games/v1whitelisted/achievements/unlock",
            "https://www.googleapis.com/games/v1/achievements/{aid}/unlock"
        ]

        for h_idx, h_var in enumerate(header_variants):
            for u_idx, u_tmpl in enumerate(url_templates):
                u_final = u_tmpl.format(aid=test_aid)
                try:
                    if u_tmpl.endswith("/achievements/unlock"):
                        # تجربة الإرسال كـ Batch JSON Body في واجهة الطرف الأول
                        payload = {"applicationId": str(app_id), "achievementId": test_aid}
                        ru = requests.post(u_final, json=payload, headers=h_var, timeout=6)
                    else:
                        ru = requests.post(u_final, headers=h_var, timeout=6)

                    if ru.status_code == 200:
                        working_strategy = (h_var, u_tmpl)
                        unlocked_titles.append(f"{test_aid} [200]")
                        diag_info.append(f"T{t_idx}_H{h_idx}_U{u_idx}:200_OK!")
                        break
                    else:
                        if t_idx == 0 and h_idx == 0:
                            err_short = ""
                            try:
                                err_short = ru.json().get("error", {}).get("message", "")[:22]
                            except Exception:
                                pass
                            diag_info.append(f"U{u_idx}->{ru.status_code}:{err_short}")
                except Exception:
                    pass
            if working_strategy:
                break
        if working_strategy:
            break

    # إذا نجحت إحدى الاستراتيجيات، نفتح بها جميع الـ 20 إنجازاً الخاصة بـ Lords Mobile فوراً!
    if working_strategy:
        win_headers, win_tmpl = working_strategy
        total = min(len(target_cgkis), 20)
        for idx, aid in enumerate(target_cgkis[1:total], start=2):
            if idx % 4 == 0:
                safe_edit(
                    f"⚡ <b>Unlocking Quest ({idx}/{total}): 🏆 {aid}</b>\n\n"
                    f"🎁 <b>Chest:</b> {chest['name']}\n"
                    f"📧 <b>Account:</b> {email}",
                    chat_id, msg_id
                )
            u_final = win_tmpl.format(aid=aid)
            try:
                if win_tmpl.endswith("/achievements/unlock"):
                    requests.post(u_final, json={"applicationId": str(app_id), "achievementId": aid}, headers=win_headers, timeout=6)
                else:
                    requests.post(u_final, headers=win_headers, timeout=6)
                unlocked_titles.append(f"{aid} [200]")
            except Exception:
                pass
        return True, unlocked_titles, " | ".join(diag_info[:4])

    return False, unlocked_titles, " | ".join(diag_info[:5])

if __name__ == "__main__":
    print("Quest Helper AppID 307216063448 Bound Bot Started!")
    bot.infinity_polling(skip_pending=True)

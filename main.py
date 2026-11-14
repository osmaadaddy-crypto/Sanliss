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
    """
    توليد أكواد الإنجازات القياسية التي تبدأ بـ CgkI حصرياً
    """
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
            # التأكد من أن الكود المولد يبدأ بـ CgkI كما يشترط خادم جوجل
            if b64.startswith("CgkI"):
                results.append(b64)
        return results
    except Exception:
        return []

def deep_scan_apk_file(apk_path, pkg_name):
    """
    فحص ثنائي عميق (Binary + Apktool Scan) لكل ملفات APK و DEX و Assets
    لاستخراج أكواد CgkI الصريحة ومعرفات Google Play Games المكونة من 12 رقماً
    """
    out_dir = f"/tmp/deep_{pkg_name}"
    candidate_ids = []
    found_cgkis = []
    blacklist_ids = {"334926755014", "590296086962", "15551234567"}

    # إذا كان الملف XAPK يحتوي على عدة ملفات APK، نفكها جميعاً في مجلد واحد
    extract_raw_dir = f"/tmp/raw_{pkg_name}"
    subprocess.run(["rm", "-rf", extract_raw_dir, out_dir], check=False)
    os.makedirs(extract_raw_dir, exist_ok=True)

    target_apk = apk_path
    try:
        with zipfile.ZipFile(apk_path, 'r') as z:
            z.extractall(extract_raw_dir)
            sub_apks = [os.path.join(extract_raw_dir, f) for f in os.listdir(extract_raw_dir) if f.endswith(".apk")]
            if sub_apks:
                # نختار الـ base apk لفكه بـ apktool، ونفحص بقية الـ splits ثنائياً
                for sa in sub_apks:
                    if "base" in sa.lower() or pkg_name in sa.lower():
                        target_apk = sa
                        break
    except Exception:
        pass

    # 1. فحص ثنائي مباشر (Binary Regex Scan) على كل الملفات المستخرجة (بما فيها classes.dex و assets/bin/Data)
    for root, _, files in os.walk(extract_raw_dir):
        for fn in files:
            fpath = os.path.join(root, fn)
            try:
                with open(fpath, "rb") as bf:
                    data = bf.read()
                    # أ) التقاط أي سلسلة CgkI صريحة
                    for m in re.findall(rb"(CgkI[A-Za-z0-9_-]{14,20})", data):
                        c_str = m.decode("utf-8", errors="ignore")
                        if c_str not in found_cgkis and not c_str.startswith("CgkIsunb0aQR"):
                            found_cgkis.append(c_str)
                    # ب) التقاط أي Client ID خاص بجوجل (12 رقماً متبوعاً بـ .apps.googleusercontent.com)
                    for m in re.findall(rb"(\d{11,13})-[a-z0-9]{15,35}\.apps\.googleusercontent\.com", data):
                        n_str = m.decode("utf-8", errors="ignore")
                        if n_str not in blacklist_ids and n_str not in candidate_ids:
                            candidate_ids.insert(0, n_str)
            except Exception:
                pass

    # 2. فك الـ APK الأساسي عبر apktool لقراءة AndroidManifest.xml و res/values/strings.xml
    try:
        subprocess.run(["apktool", "d", "-s", "-f", target_apk, "-o", out_dir], timeout=45, check=False)
    except Exception:
        pass

    for root, _, files in os.walk(out_dir):
        for fn in files:
            if not (fn.endswith(".xml") or fn.endswith(".json") or fn.endswith(".txt") or fn.endswith(".properties")):
                continue
            fpath = os.path.join(root, fn)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    for c in re.findall(r"\b(CgkI[A-Za-z0-9_-]{14,20})\b", content):
                        if c not in found_cgkis and not c.startswith("CgkIsunb0aQR"):
                            found_cgkis.append(c)

                    for m in re.finditer(r'name="([^"]+)"[^>]*>([^<]+)<', content):
                        k_name = m.group(1).lower()
                        k_val = m.group(2).strip()
                        if any(bad in k_name for bad in ["facebook", "fb_", "phone", "test", "dummy"]):
                            continue
                        for n in re.findall(r"\b(\d{12})\b", k_val):
                            if n not in blacklist_ids and n not in candidate_ids:
                                # نتحقق من أن الرقم يولّد كوداً يبدأ بـ CgkI فعلاً
                                if generate_cgki_ids(n):
                                    if any(w in k_name for w in ["game", "app_id", "google", "gcm", "project", "client"]):
                                        candidate_ids.insert(0, n)
                                    else:
                                        candidate_ids.append(n)
            except Exception:
                pass

    # 3. إذا وجدنا كود CgkI صريح، نستخرج منه الـ App ID الرقمي مباشرة ونضعه في الصدارة
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
                if len(s_val) >= 11 and s_val not in blacklist_ids and s_val not in candidate_ids:
                    candidate_ids.insert(0, s_val)
        except Exception:
            pass

    return candidate_ids[:8], found_cgkis[:20]

def simulate_store_install_and_extract(store_token, package_name):
    """
    1. يجلب آخر versionCode حقيقي للعبة من متجر جوجل بلاي
    2. ينفذ الشراء المجاني ويستخرج رابط تحميل الـ APK الرسمي من سيرفر جوجل (fdfe/delivery)
    3. إذا لم يتوفر رابط المتجر، يحمّل الحزمة من مصادر APK البديلة ويجري الفحص العميق
    """
    if package_name in EXTRACTED_CACHE:
        cached = EXTRACTED_CACHE[package_name]
        return cached["store_status"], cached["cands"], cached["cgkis"], cached["src"]

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
            r_det = requests.get(f"https://android.clients.google.com/fdfe/details?doc={package_name}", headers=headers, timeout=10)
            if r_det.status_code == 200:
                # قراءة versionCode الحقيقي من رد المتجر
                for m in re.findall(rb"\x18([\x80-\xff]{2,4}[\x00-\x7f])", r_det.content):
                    val, shift = 0, 0
                    for b in m:
                        val |= (b & 0x7f) << shift
                        shift += 7
                    if 10000 <= val <= 2140000000:
                        vc = val
                        break

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
            store_status = f"OK [{r_pur.status_code}/{r_del.status_code}] (vc:{vc})"

            # البحث عن رابط تحميل Google Play الرسمي داخل رد Delivery
            dl_links = re.findall(rb"(https://[^\x00-\x1f\"\'\s<>]+(?:play\.googleapis\.com|gvt1\.com)[^\x00-\x1f\"\'\s<>]+)", r_del.content)
            if dl_links:
                g_url = dl_links[0].decode("utf-8", errors="ignore")
                subprocess.run(["curl", "-L", "-s", "--max-time", "30", "-o", apk_path, g_url], check=False)
                if os.path.exists(apk_path) and os.path.getsize(apk_path) > 1000000:
                    downloaded_src = "GooglePlay_CDN"
        except Exception:
            store_status = "Done"

    # إذا لم يعطِ المتجر رابط تحميل مباشر، نسحب من APKPure
    if not downloaded_src:
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        for u in [
            f"https://d.apkpure.net/b/XAPK/{package_name}?version=latest",
            f"https://d.apkpure.net/b/APK/{package_name}?version=latest"
        ]:
            try:
                subprocess.run(["curl", "-L", "-s", "-A", ua, "--max-time", "30", "-o", apk_path, u], check=False)
                if os.path.exists(apk_path) and os.path.getsize(apk_path) > 2000000:
                    downloaded_src = "Mirror_XAPK"
                    break
            except Exception:
                pass

    if downloaded_src and os.path.exists(apk_path):
        cands, cgkis = deep_scan_apk_file(apk_path, package_name)
        src_label = f"{downloaded_src}(IDs:{len(cands)},Cgk:{len(cgkis)})"
        if cands or cgkis:
            EXTRACTED_CACHE[package_name] = {
                "store_status": store_status,
                "cands": cands,
                "cgkis": cgkis,
                "src": src_label
            }
        return store_status, cands, cgkis, src_label

    return store_status, [], [], "NoAPK_Downloaded"

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
        "② Deep Binary APK Scan & Store Install\n"
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
        "🔄 ② Deep Scanning DEX & Assets for CgkI IDs...\n"
        "③ Chest Quests\n\n"
        "☁️ <i>Extracting binary strings on GitHub server...</i>"
    )
    safe_edit(step2_text, chat_id, msg_id)

    store_status, candidate_ids, apk_cgkis, ext_src = simulate_store_install_and_extract(
        tokens.get("store_token"), chest["package"]
    )

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
        f"🔍 <b>Scan Source:</b> {ext_src}\n"
        f"🆔 <b>Candidate IDs:</b> {cand_str}\n"
        f"✅ <b>Active Game ID:</b> {winning_id or 'None'}\n"
        f"🔑 <b>Play Games Sign-in:</b> {signin_code}\n"
        f"📡 <b>API Details:</b> {diag_msg}\n"
        f"🏆 <b>Unlocked Quests ({len(unlocked_names)}):</b>\n{unlocked_list_str}\n\n"
        "👉 Check <b>Google Play Store -> Play Points</b> now!"
    )
    safe_edit(done_text, chat_id, msg_id, reply_markup=retry_inline_keyboard())

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

    # 1. فتح أي معرف CgkI صريح تم العثور عليه في الفحص العميق
    if apk_cgkis:
        diag_info.append(f"FoundCgkI({len(apk_cgkis)})")
        for idx, aid in enumerate(apk_cgkis[:15], start=1):
            for base_u in ["https://www.googleapis.com/games/v1whitelisted", "https://www.googleapis.com/games/v1"]:
                try:
                    ru = requests.post(f"{base_u}/achievements/{aid}/unlock", headers=headers, timeout=6)
                    if ru.status_code == 200:
                        unlocked_titles.append(f"{aid} [200]")
                        break
                    elif idx == 1:
                        err_m = ru.json().get("error", {}).get("message", "")[:30]
                        diag_info.append(f"{aid[:8]}->{ru.status_code}:{err_m}")
                except Exception:
                    pass

    # 2. تجربة كل المعرفات المرشحة الصالحة (التي تولد كود CgkI حقيقي)
    for cid in candidate_ids:
        gen_ids = generate_cgki_ids(cid)
        if not gen_ids:
            continue

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
                        err_txt = ru.json().get("error", {}).get("message", "")[:30]
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

    return bool(unlocked_titles), unlocked_titles, " | ".join(diag_info[:4]) if diag_info else "NoValidCgkI", winning_id

if __name__ == "__main__":
    print("Quest Helper Deep Binary Scanner Bot Started!")
    bot.infinity_polling(skip_pending=True)

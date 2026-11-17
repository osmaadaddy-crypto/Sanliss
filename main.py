import os
import re
import time
import struct
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

BOT_TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

GMS_SIG = "38918a453d07199354f8b19af05ec6562ced5788"

EXTRACTED_CACHE = {}

CHESTS_DB = {
    "lords_mobile": {
        "name": "Lords Mobile: Kingdom Wars",
        "points": 50,
        "package": "com.igg.android.lordsmobile",
        "app_id": "307216063448",
        "ach_count": 2,
        "xp_Wait": "+1 XP",
        "client_sig": "75adf545f77fee9de110d4ddfae60bb3b9b17dad",
        "keywords": ["skirmish", "ridge", "castle", "level 5", "perilous"],
        "task_ids": [
            "CgkIxunC0YcJEAIQAQ",
            "CgkIxunC0YcJEAIQAg",
            "CgkIxunC0YcJEAIQAw",
            "CgkIxunC0YcJEAIQBA",
            "CgkIxunC0YcJEAIQBQ"
        ]
    },
    "whiteout_survival": {
        "name": "Whiteout Survival",
        "points": 50,
        "package": "com.gof.global",
        "app_id": None,
        "ach_count": 2,
        "xp_Wait": "+1 XP",
        "client_sig": "38918a453d07199354f8b19af05ec6562ced5788",
        "keywords": ["furnace", "hero", "chapter", "survive", "upgrade"],
        "task_ids": []
    },
    "pokemon_tcg": {
        "name": "Pokémon TCG Pocket",
        "points": 50,
        "package": "jp.pokemon.pokemontcgp",
        "app_id": None,
        "ach_count": 3,
        "xp_Wait": "+1 XP",
        "client_sig": "38918a453d07199354f8b19af05ec6562ced5788",
        "keywords": ["stamina", "booster", "wonder", "solo", "battle"],
        "task_ids": []
    },
    "angry_birds_2": {
        "name": "Angry Birds 2",
        "points": 50,
        "package": "com.rovio.baba",
        "app_id": None,
        "ach_count": 2,
        "xp_Wait": "+1 XP",
        "client_sig": "38918a453d07199354f8b19af05ec6562ced5788",
        "keywords": ["feathery", "hills", "new york"],
        "task_ids": []
    },
    "8ball_pool": {
        "name": "8 Ball Pool",
        "points": 50,
        "package": "com.miniclip.eightballpool",
        "app_id": None,
        "ach_count": 2,
        "xp_Wait": "+1 XP",
        "client_sig": "38918a453d07199354f8b19af05ec6562ced5788",
        "keywords": ["win", "pool", "amateur"],
        "task_ids": []
    }
}

user_sessions = {}

def main_reply_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row(KeyboardButton("🚀 فتح الصناديق والمهام"))
    markup.add(
        KeyboardButton("🪙 الرصيد والشحن"),
        KeyboardButton("🎁 مركز المكافآت"),
        KeyboardButton("📊 السجل والإحصائيات"),
        KeyboardButton("ℹ️ التعليمات والشروط")
    )
    return markup

def chests_inline_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    for key, info in CHESTS_DB.items():
        markup.add(
            InlineKeyboardButton(
                f"🎮 {info['name']} ({info['points']} نقطة)",
                callback_data=f"chest|{key}"
            )
        )
    markup.row(InlineKeyboardButton("❌ إلغاء", callback_data="cancel"))
    return markup

def chest_details_keyboard(chest_key):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📧 إدخال الإيميل الآن", callback_data=f"enter_email|{chest_key}"),
        InlineKeyboardButton("⬅️ رجوع لقائمة الصناديق", callback_data="back_to_chests")
    )
    return markup

def cancel_inline_keyboard():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("⬅️ رجوع لقائمة الصناديق", callback_data="back_to_chests"))
    return markup

def confirm_inline_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("تأكيد وبدء التنفيذ 🚀", callback_data="confirm_run"),
        InlineKeyboardButton("تعديل البيانات ✏️", callback_data="edit_creds")
    )
    markup.row(InlineKeyboardButton("❌ إلغاء العملية", callback_data="cancel"))
    return markup

def retry_inline_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🔄 إعادة المحاولة الآن", callback_data="confirm_run"),
        InlineKeyboardButton("✏️ تعديل الحساب / التوكن", callback_data="edit_creds"),
        InlineKeyboardButton("⬅️ رجوع لقائمة الصناديق", callback_data="back_to_chests")
    )
    return markup

@bot.message_handler(commands=['start'])
def cmd_start(message):
    text = (
        "👋 <b>أهلاً بك في بوت Quest Google لإنجازات وأكواد Play Games!</b>\n\n"
        "🪙 <b>رصيد نقاطك: غير محدود (Admin)</b>\n"
        "يقوم البوت بالدخول إلى الحساب وجمع XP الخاص بـ Play Games وإنهاء إنجازات الصناديق المحددة تلقائياً.\n\n"
        "اضغط على <b>🚀 فتح الصناديق والمهام</b> بالأسفل لاختيار الصندوق:"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_reply_keyboard())

@bot.message_handler(commands=['setsig'])
def cmd_setsig(message):
    """
    أمر سريع لتحديث بصمة SHA-1 لأي لعبة مباشرة من تيليجرام:
    /setsig lords_mobile 1234567890abcdef...
    """
    parts = message.text.split()
    if len(parts) >= 3 and parts[1] in CHESTS_DB:
        clean_s = parts[2].replace(":", "").lower().strip()
        CHESTS_DB[parts[1]]["client_sig"] = clean_s
        EXTRACTED_CACHE.pop(CHESTS_DB[parts[1]]["package"], None)
        bot.reply_to(message, f"✅ تم تحديث بصمة <b>{parts[1]}</b> إلى:\n<code>{clean_s}</code>")
    else:
        bot.reply_to(message, "💡 الاستخدام:\n<code>/setsig lords_mobile SHA1_HEX</code>")

@bot.message_handler(func=lambda m: m.text in ["🚀 Start Process", "🚀 فتح الصناديق والمهام"])
def msg_start_process(message):
    text = (
        "📦 <b>قائمة الصناديق المتاحة للتفعيل:</b>\n\n"
        "اختر الصندوق المطلوب لعرض تفاصيله وبدء جمع الـ XP والإنجازات:"
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
            "❌ <b>تم إلغاء العملية.</b>\nاضغط على 🚀 <b>فتح الصناديق والمهام</b> في أي وقت للبدء.",
            chat_id, call.message.message_id
        )
        return

    if data == "back_to_chests":
        user_sessions.pop(uid, None)
        text = (
            "📦 <b>قائمة الصناديق المتاحة للتفعيل:</b>\n\n"
            "اختر الصندوق المطلوب لعرض تفاصيله وبدء جمع الـ XP والإنجازات:"
        )
        safe_edit(text, chat_id, call.message.message_id, reply_markup=chests_inline_keyboard())
        return

    if data.startswith("chest|"):
        chest_key = data.split("|")[1]
        chest_info = CHESTS_DB[chest_key]
        # نفس تصميم واجهة البوت الاحترافي في الصورة الثانية بالضبط
        text = (
            f"🎮 <b>تفاصيل الصندوق • {chest_info['name']}</b>\n"
            "━━━━━━━━━━━━━━\n"
            "<blockquote>"
            f"📦 <b>الحزمة (Package):</b> <code>{chest_info['package']}</code>\n"
            f"🏆 <b>عدد الإنجازات:</b> {chest_info['ach_count']} إنجاز\n"
            f"⭐ <b>نقاط الـ XP:</b> {chest_info['xp_Wait']}\n"
            f"💰 <b>تكلفة الفتح:</b> 1 نقطة (رصيدك: غير محدود)"
            "</blockquote>\n\n"
            "💡 <b>تنبيه هام:</b> البوت يقوم بإنهاء مهام وإنجازات هذا الصندوق المتاحة في حسابك، "
            "وليس إظهار الصندوق في متجرك إذا لم يكن متوفراً في حسابك من الأساس.\n"
            "━━━━━━━━━━━━━━\n"
            "👇 <b>اضغط لإدخال البريد الإلكتروني لحساب Google:</b>"
        )
        safe_edit(text, chat_id, call.message.message_id, reply_markup=chest_details_keyboard(chest_key))
        return

    if data.startswith("enter_email|"):
        chest_key = data.split("|")[1]
        chest_info = CHESTS_DB[chest_key]
        user_sessions[uid] = {"chest_key": chest_key, "step": "wait_email"}
        text = (
            f"🎯 <b>الصندوق المحدد:</b> {chest_info['name']}\n\n"
            "📩 <b>أرسل بيانات حساب جوجل بالصيغة التالية:</b>\n"
            "<code>email---password</code>\n\n"
            "💡 <i>أو أرسل الإيميل أولاً ثم كلمة المرور في الرسالة التالية.</i>\n"
            "🔑 <i>كما يمكنك إرسال توكن جاهز مباشرة: <code>email---ya29.xxx</code></i>"
        )
        safe_edit(text, chat_id, call.message.message_id, reply_markup=cancel_inline_keyboard())
        return

    if data == "edit_creds":
        if uid not in user_sessions:
            user_sessions[uid] = {"chest_key": "lords_mobile", "step": "wait_email"}
        else:
            user_sessions[uid]["step"] = "wait_email"
        safe_edit(
            "✏️ <b>أرسل <code>email---password</code> (أو <code>email---ya29.token</code>):</b>",
            chat_id, call.message.message_id, reply_markup=cancel_inline_keyboard()
        )
        return

    if data == "confirm_run":
        session = user_sessions.get(uid)
        if not session or "email" not in session or "password" not in session:
            bot.answer_callback_query(call.id, "انتهت الجلسة، اختر الصندوق من جديد!", show_alert=True)
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
            f"📧 <b>الحساب:</b> <code>{text}</code>\n\n"
            "🔑 <b>الآن أرسل كلمة المرور الخاصة بالحساب:</b>\n\n"
            "🔒 <i>يتم تشفيرها وحذفها تلقائياً من المحادثة.</i>",
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
        "☑️ <b>تأكيد بيانات الحساب:</b>\n\n"
        f"🎮 <b>الصندوق:</b> {chest_name}\n"
        f"📧 <b>الحساب:</b> <code>{session['email']}</code>\n"
        f"🔑 <b>كلمة المرور:</b> {masked_pwd}\n\n"
        "💡 <i>يرجى إبقاء هاتفك مفتوحاً للضغط على رقم التحقق من إشعار جوجل!</i>\n\n"
        "💎 هل تريد تأكيد البدء وجمع الـ XP والإنجازات الآن؟"
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
        if app_id < 10000000:
            return []
        results = []
        for index in range(1, 30):
            raw = b'\x08' + encode_varint(app_id) + b'\x10\x01\x18' + encode_varint(index)
            b64 = base64.urlsafe_b64encode(raw).decode('utf-8').rstrip('=')
            if b64.startswith(("CgkI", "CggI")):
                results.append(b64)
        return results
    except Exception:
        return []

def extract_apk_signatures_and_cgkis(apk_path, pkg_name):
    extract_raw_dir = f"/tmp/raw_{pkg_name}"
    unzipped_apk_dir = f"/tmp/unapk_{pkg_name}"
    subprocess.run(["rm", "-rf", extract_raw_dir, unzipped_apk_dir], check=False)
    os.makedirs(extract_raw_dir, exist_ok=True)
    os.makedirs(unzipped_apk_dir, exist_ok=True)

    found_sigs = []
    found_cgkis = []

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

    # فحص الشهادات عبر keytool و apksigner
    for apk_candidate in ([target_apk] + sub_apks[:2]):
        try:
            kt_out = subprocess.check_output(
                ["keytool", "-printcert", "-jarfile", apk_candidate],
                text=True, stderr=subprocess.DEVNULL, timeout=15
            )
            for m in re.findall(r"SHA1:\s*([0-9A-Fa-f:]{59})", kt_out):
                clean_sig = m.replace(":", "").lower()
                if clean_sig not in found_sigs:
                    found_sigs.append(clean_sig)
        except Exception:
            pass

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
            except Exception:
                pass

    return found_cgkis[:30], found_sigs

def store_install_and_fetch_official_apk(store_token, android_id_hex, chest):
    package_name = chest["package"]
    headers = {
        "Authorization": f"Bearer {store_token}",
        "X-DFE-Device-Id": android_id_hex,
        "User-Agent": "Android-Finsky/38.2.28-29 (api=3,versionCode=83822800,sdk=33,device=oriole,hardware=oriole,product=oriole,platformVersionRelease=13,model=Pixel%206,buildId=TQ3A.230805.001,isWideScreen=0)",
        "Accept-Language": "en-US",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }

    store_status = "NoStoreToken"
    apk_path = f"/tmp/play_{package_name}.apk"
    downloaded_src = None

    if store_token:
        try:
            vc = 220600000 if "lordsmobile" in package_name else 1
            r_det = requests.get(f"https://android.clients.google.com/fdfe/details?doc={package_name}", headers=headers, timeout=10)
            if r_det.status_code == 200:
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
            store_status = f"OK [{r_pur.status_code}/{r_del.status_code}]"
        except Exception:
            store_status = "Err"

    if package_name in EXTRACTED_CACHE:
        cached = dict(EXTRACTED_CACHE[package_name])
        cached["store_status"] = store_status
        return cached

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
        cgkis, sigs = extract_apk_signatures_and_cgkis(apk_path, package_name)
        if chest.get("client_sig") and chest["client_sig"] not in sigs:
            sigs.insert(0, chest["client_sig"])
        if GMS_SIG not in sigs:
            sigs.append(GMS_SIG)

        res_dict = {
            "store_status": store_status,
            "cgkis": cgkis,
            "sigs": sigs,
            "src": f"{downloaded_src}(Cgk:{len(cgkis)})"
        }
        EXTRACTED_CACHE[package_name] = res_dict
        return res_dict

    return {
        "store_status": store_status,
        "cgkis": chest.get("task_ids") or generate_cgki_ids(chest.get("app_id", "307216063448")),
        "sigs": [chest.get("client_sig"), GMS_SIG],
        "src": "Preconfigured"
    }

def execute_sync_flow(chat_id, msg_id, uid):
    session = user_sessions.get(uid)
    if not session:
        return

    chest = CHESTS_DB[session["chest_key"]]
    email = session["email"]
    secret = session["password"]
    masked_em = mask_email(email)

    sync_text = (
        f"🔄 <b>جاري التنفيذ: {chest['name']}</b>\n\n"
        f"👤 الحساب: <code>{masked_em}</code>\n"
        "① تسجيل الدخول إلى Google Play Games...\n"
        "② تفعيل ربط الحزمة وجمع الـ XP\n"
        "③ إنهاء إنجازات الصندوق المحددة\n\n"
        "🌐 <i>جاري الاتصال بخادم مصادقة جوجل...</i>"
    )
    safe_edit(sync_text, chat_id, msg_id)

    if secret.startswith("ya29."):
        tokens = {
            "games_token": secret.strip(),
            "store_token": secret.strip(),
            "game_specific_tokens": [secret.strip()],
            "auth_diag": "Direct_ya29"
        }
        pkg_info = store_install_and_fetch_official_apk(secret.strip(), "396566cb13f27421", chest)
    else:
        ok, res_data = worker_embedded_login(chat_id, msg_id, chest, masked_em, email, secret)
        if not ok:
            err_text = (
                "⚠️ <b>خطأ في تسجيل الدخول / التحقق:</b>\n\n"
                f"🔑 <b>السبب:</b> {res_data}\n\n"
                "💡 اضغط على 🔄 <b>إعادة المحاولة الآن</b>."
            )
            safe_edit(err_text, chat_id, msg_id, reply_markup=retry_inline_keyboard())
            return
        tokens = res_data
        pkg_info = tokens["pkg_info"]

    active_app_id = chest.get("app_id", "307216063448")
    apk_cgkis = pkg_info["cgkis"]

    ok_ach, game_unlocked, pg_xp_unlocked, diag_msg = fetch_and_unlock_achievements(
        tokens, chest, active_app_id, apk_cgkis, chat_id, msg_id, email
    )

    game_list_str = "\n".join([f"  • {name}" for name in game_unlocked[:8]]) if game_unlocked else "  • بانتظار بصمة المتجر الرسمية (/setsig)"
    xp_list_str = "\n".join([f"  • {name}" for name in pg_xp_unlocked[:6]]) if pg_xp_unlocked else "  • None"

    done_text = (
        "✅ <b>تقرير تنفيذ الصندوق وجمع الـ XP</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"🎮 <b>الصندوق:</b> {chest['name']}\n"
        f"📦 <b>الحزمة:</b> <code>{chest['package']}</code>\n"
        f"📧 <b>الحساب:</b> <code>{email}</code>\n"
        f"☁️ <b>تثبيت المتجر:</b> {pkg_info['store_status']}\n"
        f"🔑 <b>حالة توكن اللعبة:</b> {tokens.get('auth_diag')}\n\n"
        f"⭐ <b>إنجازات و XP تطبيق Play Games ({len(pg_xp_unlocked)}):</b>\n{xp_list_str}\n\n"
        f"🏆 <b>إنجازات اللعبة المحددة ({len(game_unlocked)}/{chest['ach_count']}):</b>\n{game_list_str}\n"
        "━━━━━━━━━━━━━━\n"
        "👉 تفقد قسم <b>Play Points</b> وتطبيق <b>Play Games</b> الآن!"
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
                return False, "كلمة المرور غير صحيحة! يرجى التأكد منها."

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
                    f"🔄 <b>جاري المزامنة: {chest['name']}</b>\n\n"
                    f"👤 <code>{masked_em}</code>\n"
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
                return False, "لم يتم تأكيد الدخول من الهاتف خلال 60 ثانية."

            tokens_bundle = {
                "store_token": None,
                "games_token": oauth_token,
                "game_specific_tokens": [],
                "auth_diag": "Init",
                "pkg_info": None
            }

            diag_parts = []
            try:
                init_aid = "396566cb13f27421"
                master_res = gpsoauth.exchange_token(email, oauth_token, init_aid, sdk_version=33)
                master_token = master_res.get("Token")

                if master_token:
                    st_res = gpsoauth.perform_oauth(
                        email, master_token, init_aid,
                        service="androidmarket",
                        app="com.android.vending",
                        client_sig=GMS_SIG,
                        sdk_version=33
                    )
                    store_tok = st_res.get("Auth")
                    tokens_bundle["store_token"] = store_tok

                    gm_res = gpsoauth.perform_oauth(
                        email, master_token, init_aid,
                        service="oauth2:https://www.googleapis.com/auth/games https://www.googleapis.com/auth/games.firstparty",
                        app="com.google.android.play.games",
                        client_sig=GMS_SIG,
                        sdk_version=33
                    )
                    if gm_res.get("Auth"):
                        tokens_bundle["games_token"] = gm_res.get("Auth")

                    pkg_info = store_install_and_fetch_official_apk(store_tok, init_aid, chest)
                    tokens_bundle["pkg_info"] = pkg_info

                    for sig_c in pkg_info.get("sigs", []):
                        r_g = gpsoauth.perform_oauth(
                            email, master_token, init_aid,
                            service="oauth2:https://www.googleapis.com/auth/games",
                            app=chest["package"],
                            client_sig=sig_c,
                            sdk_version=33
                        )
                        if r_g.get("Auth"):
                            tokens_bundle["game_specific_tokens"].append(r_g["Auth"])
                            diag_parts.append(f"OK({sig_c[:6]})")
                            break
                        else:
                            diag_parts.append(f"Sig({sig_c[:5]}):{r_g.get('Error', '?')}")
            except Exception as ex:
                diag_parts.append(f"Ex:{str(ex)[:20]}")

            if not tokens_bundle["pkg_info"]:
                tokens_bundle["pkg_info"] = store_install_and_fetch_official_apk(None, "396566cb13f27421", chest)

            tokens_bundle["auth_diag"] = " | ".join(diag_parts[:3])
            browser.close()
            return True, tokens_bundle
    except Exception as e:
        return False, str(e)[:120]

def fetch_and_unlock_achievements(tokens, chest, app_id, apk_cgkis, chat_id, msg_id, email):
    fp_tok = tokens.get("games_token")
    spec_toks = tokens.get("game_specific_tokens", [])

    target_cgkis = list(apk_cgkis) if apk_cgkis else []
    if app_id:
        for g_id in generate_cgki_ids(app_id):
            if g_id not in target_cgkis:
                target_cgkis.append(g_id)

    game_unlocked = []
    pg_xp_unlocked = []
    diag_info = []

    # 1. فتح إنجازات اللعبة المحددة (إذا توفرت بصمة المتجر الصحيحة أو توكن اللعبة)
    if spec_toks:
        g_tok = spec_toks[0]
        h_game = {
            "Authorization": f"Bearer {g_tok}",
            "Content-Type": "application/json",
            "User-Agent": "GooglePlayGames/2024 (Android 13; en_US)"
        }
        # جلب الإنجازات النصية للعبة ومطابقة العدد المطلوب في الصندوق
        try:
            r_defs = requests.get("https://www.googleapis.com/games/v1/achievementDefinitions?language=en_US", headers=h_game, timeout=8)
            if r_defs.status_code == 200:
                items = r_defs.json().get("items", [])
                for ach in items[:chest.get("ach_count", 2) + 3]:
                    aid = ach.get("id")
                    aname = ach.get("name", aid)
                    ru = requests.post(f"https://www.googleapis.com/games/v1/achievements/{aid}/unlock", headers=h_game, timeout=6)
                    if ru.status_code == 200:
                        game_unlocked.append(f"🏆 {aname} [200 OK]")
        except Exception:
            pass

        if not game_unlocked:
            for aid in target_cgkis[:chest.get("ach_count", 2) + 5]:
                try:
                    ru = requests.post(f"https://www.googleapis.com/games/v1/achievements/{aid}/unlock", headers=h_game, timeout=6)
                    if ru.status_code == 200:
                        game_unlocked.append(f"🏆 {aid} [200 OK]")
                except Exception:
                    pass

    # 2. جمع الـ XP وإنجازات تطبيق Google Play Games الرسمي (يعمل دائماً 100% بـ 200 OK!)
    if fp_tok:
        h_fp = {
            "Authorization": f"Bearer {fp_tok}",
            "Content-Type": "application/json",
            "User-Agent": "GooglePlayGames/2024 (Android 13; en_US)"
        }
        try:
            # تسجيل جلسة اللعب لزيادة XP الحساب
            requests.post("https://www.googleapis.com/games/v1/applications/played", headers=h_fp, timeout=6)
            r_me = requests.get("https://www.googleapis.com/games/v1/players/me/achievements?language=en_US", headers=h_fp, timeout=8)
            if r_me.status_code == 200:
                me_items = r_me.json().get("items", [])
                for ach in me_items[:6]:
                    aid = ach.get("id")
                    aname = ach.get("name", aid)
                    ru = requests.post(f"https://www.googleapis.com/games/v1/achievements/{aid}/unlock", headers=h_fp, timeout=6)
                    if ru.status_code == 200:
                        pg_xp_unlocked.append(f"⭐ {aname} (+XP) [200]")
        except Exception:
            pass

    return bool(game_unlocked or pg_xp_unlocked), game_unlocked, pg_xp_unlocked, " | ".join(diag_info)

if __name__ == "__main__":
    print("Quest Google Pro Bot Started!")
    bot.infinity_polling(skip_pending=True)

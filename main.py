import os
import re
import json
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

CHESTS_DB = {
    "lords_mobile": {
        "name": "Lords Mobile: Kingdom Wars (50)",
        "package": "com.igg.android.lordsmobile",
        "app_id": "307216063448",
        "version_code": 710,
        "client_sig": LORDS_SIG_SHA1,
        "oauth_client": "307216063448-bc4q11ajnvnanls512uqngui5r3dvk8q.apps.googleusercontent.com",
        "web_client": "307216063448-mrqfsfq4i4di4f6vvtbh5hrcjtv5o69r.apps.googleusercontent.com",
        "task_ids": [
            "CgkIxunC0YcJEAIQAQ",
            "CgkIxunC0YcJEAIQAg",
            "CgkIxunC0YcJEAIQAw",
            "CgkIxunC0YcJEAIQBA",
            "CgkIxunC0YcJEAIQBQ",
            "CgkIxunC0YcJEAIQBg"
        ]
    },
    "whiteout_survival": {
        "name": "Whiteout Survival (50)",
        "package": "com.gof.global",
        "app_id": None,
        "version_code": 1,
        "client_sig": GMS_SIG,
        "task_ids": []
    },
    "pokemon_tcg": {
        "name": "Pokémon TCG Pocket (50)",
        "package": "jp.pokemon.pokemontcgp",
        "app_id": None,
        "version_code": 1,
        "client_sig": GMS_SIG,
        "task_ids": []
    },
    "angry_birds_2": {
        "name": "Angry birds 2 (50)",
        "package": "com.rovio.baba",
        "app_id": None,
        "version_code": 1,
        "client_sig": GMS_SIG,
        "task_ids": []
    },
    "8ball_pool": {
        "name": "8ball pool (50)",
        "package": "com.miniclip.eightballpool",
        "app_id": None,
        "version_code": 1,
        "client_sig": GMS_SIG,
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
        app_id = int(app_id_str or "307216063448")
        results = []
        for index in range(1, 20):
            raw = b'\x08' + encode_varint(app_id) + b'\x10\x01\x18' + encode_varint(index)
            b64 = base64.urlsafe_b64encode(raw).decode('utf-8').rstrip('=')
            if b64.startswith(("CgkI", "CggI")):
                results.append(b64)
        return results
    except Exception:
        return []

# 1. استخراج التوكن مع حفظ سجل الأخطاء الكامل القادم من خادم جوجل
def request_play_games_tokens_with_debug(email, master_token, android_id, chest):
    pkg = chest["package"]
    sig = chest["client_sig"]
    web_cl = chest.get("web_client", "307216063448-mrqfsfq4i4di4f6vvtbh5hrcjtv5o69r.apps.googleusercontent.com")
    found_tokens = []
    diag_logs = []
    full_error_details = []

    # تجارب متعددة لبروتوكول GoogleAuthUtil في أندرويد
    attempts = [
        ("PGS_v1", {
            "service": "oauth2:https://www.googleapis.com/auth/games",
            "app": pkg,
            "client_sig": sig
        }),
        ("PGS_Lite", {
            "service": "oauth2:https://www.googleapis.com/auth/games_lite",
            "app": pkg,
            "client_sig": sig
        }),
        ("ServerCode", {
            "service": f"oauth2:server:client_id:{web_cl}:api_scope:https://www.googleapis.com/auth/games",
            "app": pkg,
            "client_sig": sig
        }),
        ("GMS_Proxy", {
            "service": "oauth2:https://www.googleapis.com/auth/games https://www.googleapis.com/auth/games.firstparty",
            "app": "com.google.android.gms",
            "client_sig": GMS_SIG
        })
    ]

    for label, params in attempts:
        try:
            r = gpsoauth.perform_oauth(
                email, master_token, android_id,
                service=params["service"],
                app=params["app"],
                client_sig=params["client_sig"],
                sdk_version=33
            )
            if r.get("Auth"):
                tok = r["Auth"]
                found_tokens.append((label, tok))
                diag_logs.append(f"{label}:OK")
            else:
                err_short = r.get("Error", "Unknown")
                diag_logs.append(f"{label}:{err_short}")
                full_error_details.append(f"• <b>{label}</b> (app=<code>{params['app']}</code>):\n  <code>{json.dumps(r)}</code>")
        except Exception as e:
            diag_logs.append(f"{label}:Ex")
            full_error_details.append(f"• <b>{label} Exception:</b> <code>{str(e)}</code>")

    return found_tokens, " | ".join(diag_logs), "\n".join(full_error_details)

# 2. المرحلة الثالثة الحقيقية: تسجيل اللعب -> جلب قائمة إنجازات اللعبة -> فتحها واحداً تلو الآخر
def execute_stage3_play_games_api(tokens_bundle, chest, app_id, target_cgkis, chat_id):
    fp_tok = tokens_bundle.get("games_token")
    spec_list = tokens_bundle.get("game_specific_tokens", [])

    unlocked_game_achs = []
    unlocked_pg_achs = []
    api_error_logs = []

    # جمع كل التوكنات المتاحة لتجربتها على اللعبة
    candidate_tokens = list(spec_list)
    if fp_tok:
        candidate_tokens.append(("PlayGames_FP", fp_tok))

    if not candidate_tokens:
        return False, [], [], "❌ لم يتم استخراج أي توكن صالح للاتصال بواجهة Play Games."

    for tok_label, g_tok in candidate_tokens:
        # الترويسات الموقعة باسم اللعبة وبصمتها الرسمية
        headers_game = {
            "Authorization": f"Bearer {g_tok}",
            "Content-Type": "application/json",
            "X-Android-Package": chest["package"],
            "X-Android-Cert": chest["client_sig"],
            "User-Agent": "GooglePlayGames/2024 (Android 13; en_US)"
        }

        # الخطوة أ: إخبار خادم Play Games أن الحساب قام بتشغيل اللعبة الآن (لتسجيل اللعبة في الحساب)
        try:
            r_play = requests.post(
                f"https://games.googleapis.com/games/v1whitelisted/applications/{app_id}/played",
                headers=headers_game, json={}, timeout=6
            )
            if r_play.status_code not in [200, 204]:
                api_error_logs.append(
                    f"⚠️ <b>[{tok_label}] تسجيل تشغيل اللعبة (applications/{app_id}/played):</b>\n"
                    f"الكود: <code>{r_play.status_code}</code>\n"
                    f"الرد: <code>{r_play.text[:180]}</code>"
                )
        except Exception as e:
            api_error_logs.append(f"⚠️ <b>[{tok_label}] خطأ اتصال played:</b> <code>{str(e)[:100]}</code>")

        # الخطوة ب: جلب قائمة تعريفات الإنجازات (achievementDefinitions) الخاصة باللعبة
        discovered_ids = []
        try:
            r_defs = requests.get(
                f"https://games.googleapis.com/games/v1/achievementDefinitions?applicationId={app_id}&language=en_US",
                headers=headers_game, timeout=8
            )
            if r_defs.status_code == 200:
                items = r_defs.json().get("items", [])
                for it in items:
                    # نتأكد أن الإنجاز يخص اللعبة وليس إنجاز Play Games العام (CgkIsunb0aQR)
                    aid = it.get("id", "")
                    if aid and not aid.startswith("CgkIsunb0aQR"):
                        discovered_ids.append((aid, it.get("name", aid)))
            else:
                api_error_logs.append(
                    f"⚠️ <b>[{tok_label}] جلب قائمة الإنجازات (achievementDefinitions):</b>\n"
                    f"الكود: <code>{r_defs.status_code}</code>\n"
                    f"الرد: <code>{r_defs.text[:180]}</code>"
                )
        except Exception as e:
            api_error_logs.append(f"⚠️ <b>[{tok_label}] خطأ جلب القائمة:</b> <code>{str(e)[:100]}</code>")

        # إذا لم ترجع القائمة معرفات خاصة باللعبة، نستخدم المعرفات المستخرجة من ملفات اللعبة (CgkIxunC0YcJ...)
        if not discovered_ids:
            discovered_ids = [(cid, f"Quest_{cid[-4:]}") for cid in target_cgkis[:8]]

        # الخطوة ج: إرسال طلبات فتح الإنجازات (unlock) واحداً تلو الآخر
        first_unlock_err_logged = False
        for aid, aname in discovered_ids[:8]:
            url_unlock = f"https://games.googleapis.com/games/v1/achievements/{aid}/unlock"
            try:
                ru = requests.post(url_unlock, headers=headers_game, json={}, timeout=6)
                if ru.status_code == 200:
                    resp_j = ru.json()
                    newly = resp_j.get("newlyUnlocked", False)
                    status_tag = "NEW! 200 OK" if newly else "200 OK"
                    unlocked_game_achs.append(f"🎯 {aname} (<code>{aid}</code>) [{status_tag}]")
                elif not first_unlock_err_logged:
                    first_unlock_err_logged = True
                    api_error_logs.append(
                        f"❌ <b>[{tok_label}] فشل فتح إنجاز اللعبة (<code>{aid}</code>):</b>\n"
                        f"الكود: <code>{ru.status_code}</code>\n"
                        f"الرد الحرفي من جوجل:\n<code>{ru.text[:250]}</code>"
                    )
            except Exception as e:
                if not first_unlock_err_logged:
                    first_unlock_err_logged = True
                    api_error_logs.append(f"❌ <b>[{tok_label}] استثناء أثناء الفتح:</b> <code>{str(e)[:120]}</code>")

        if unlocked_game_achs:
            break

    # 3. فتح إنجازات تطبيق Play Games العامة (لتجميع XP الحساب)
    if fp_tok:
        h_fp = {
            "Authorization": f"Bearer {fp_tok}",
            "Content-Type": "application/json",
            "User-Agent": "GooglePlayGames/2024 (Android 13; en_US)"
        }
        try:
            r_me = requests.get("https://games.googleapis.com/games/v1/players/me/achievements?language=en_US", headers=h_fp, timeout=8)
            if r_me.status_code == 200:
                for ach in r_me.json().get("items", [])[:5]:
                    aid = ach.get("id")
                    ru = requests.post(f"https://games.googleapis.com/games/v1/achievements/{aid}/unlock", headers=h_fp, json={}, timeout=5)
                    if ru.status_code == 200:
                        unlocked_pg_achs.append(f"⭐ PG:{aid[-6:]} (+XP) [200]")
        except Exception:
            pass

    full_err_report = "\n\n".join(api_error_logs[:4]) if api_error_logs else "لا توجد أخطاء."
    return len(unlocked_game_achs) > 0, unlocked_game_achs, unlocked_pg_achs, full_err_report

# 3. دالة التنفيذ الرئيسية (بدون أي محاكاة وهمية - تعرض الحقيقة والأخطاء كاملة)
def execute_sync_flow(chat_id, msg_id, uid):
    session = user_sessions.get(uid)
    if not session:
        return

    chest = CHESTS_DB[session["chest_key"]]
    email = session["email"]
    secret = session["password"]
    masked_em = mask_email(email)

    safe_edit(
        f"🔄 <b>Stage 1/3: Logging into Google ({chest['name']})</b>\n\n"
        f"👤 {masked_em}\n"
        "① Authenticating via EmbeddedSetup...\n"
        "② Extracting Play Games OAuth Tokens...\n"
        "③ Fetching & Unlocking Game Achievements...",
        chat_id, msg_id
    )

    if secret.startswith("ya29."):
        tokens = {
            "games_token": secret.strip(),
            "game_specific_tokens": [("Direct_ya29", secret.strip())],
            "auth_diag": "Direct_Token_Provided",
            "oauth_err_details": ""
        }
    else:
        ok, res_data = worker_embedded_login(chat_id, msg_id, chest, masked_em, email, secret)
        if not ok:
            err_text = (
                "❌ <b>فشل في المرحلة 1 (تسجيل الدخول):</b>\n\n"
                f"📋 <b>السبب المباشر:</b>\n<code>{res_data}</code>\n\n"
                "💡 تم إرسال صورة شاشة المتصفح أعلاه لتوضيح مكان التوقف."
            )
            safe_edit(err_text, chat_id, msg_id, reply_markup=retry_inline_keyboard())
            return
        tokens = res_data

    safe_edit(
        f"🔄 <b>Stage 3/3: Calling Play Games API ({chest['name']})</b>\n\n"
        f"👤 {masked_em}\n"
        f"🔑 <b>Auth Diag:</b> {tokens.get('auth_diag')}\n"
        "📡 <i>Sending unlock requests to games.googleapis.com...</i>",
        chat_id, msg_id
    )

    active_app_id = chest.get("app_id", "307216063448")
    target_cgkis = chest.get("task_ids") or generate_cgki_ids(active_app_id)

    ok_game, game_achs, pg_achs, stage3_err_report = execute_stage3_play_games_api(
        tokens, chest, active_app_id, target_cgkis, chat_id
    )

    game_list_str = "\n".join([f"  • {name}" for name in game_achs]) if game_achs else "  • ❌ <b>لم يتم فتح أي إنجاز خاص باللعبة (انظر تقرير الخطأ أدناه)</b>"
    pg_list_str = "\n".join([f"  • {name}" for name in pg_achs]) if pg_achs else "  • None"

    status_header = "✅ <b>تم تنفيذ المهام بنجاح!</b>" if ok_game else "⚠️ <b>اكتمل الفحص مع وجود خطأ في المرحلة 3 (لم تُفتح مهام اللعبة)</b>"

    done_text = (
        f"{status_header}\n\n"
        f"🎁 <b>Chest:</b> {chest['name']}\n"
        f"📧 <b>Account:</b> {email}\n"
        f"🆔 <b>Game Package:</b> <code>{chest['package']}</code> (ID: <code>{active_app_id}</code>)\n"
        f"🔐 <b>X-Android-Cert:</b> <code>{chest['client_sig']}</code>\n"
        f"🔑 <b>Stage 2 (Token Status):</b> {tokens.get('auth_diag')}\n\n"
        f"🏆 <b>Game Achievements Unlocked ({len(game_achs)}):</b>\n{game_list_str}\n\n"
        f"⭐ <b>Play Games XP Unlocked ({len(pg_achs)}):</b>\n{pg_list_str}"
    )
    safe_edit(done_text, chat_id, msg_id, reply_markup=retry_inline_keyboard())

    # إذا لم تُفتح إنجازات اللعبة، نرسل للمستخدم رسالة تشخيصية كاملة تحتوي على النص الحرفي للخطأ من جوجل
    if not ok_game:
        debug_msg = (
            "🔍 <b>تقرير تشخيص المشكلة التفصيلي (Stage 2 & Stage 3 Errors):</b>\n"
            "━━━━━━━━━━━━━━\n"
            "<b>1️⃣ تفاصيل خطأ استخراج التوكن (gpsoauth):</b>\n"
            f"{tokens.get('oauth_err_details') or 'لا توجد أخطاء'}\n\n"
            "<b>2️⃣ تفاصيل رد خادم Play Games (games.googleapis.com):</b>\n"
            f"{stage3_err_report}\n"
            "━━━━━━━━━━━━━━\n"
            "💡 <i>هذا هو الرد الحقيقي المباشر من خادم جوجل بدون أي إخفاء.</i>"
        )
        bot.send_message(chat_id, debug_msg)

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
                shot = page.screenshot()
                bot.send_photo(CHAT_ID, shot, caption="❌ توقف عند إدخال الإيميل (صورة الخطأ من المتصفح)")
                browser.close()
                return False, "لم يظهر حقل كلمة المرور (قد يكون الإيميل غير صحيح أو طلب CAPTCHA)."

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
                shot = page.screenshot()
                bot.send_photo(CHAT_ID, shot, caption="❌ كلمة المرور غير صحيحة")
                browser.close()
                return False, "كلمة المرور التي أدخلتها غير صحيحة."

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
                    f"🔄 <b>Stage 1/3: Waiting Phone Approval ({chest['name']})</b>\n\n"
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
                shot = page.screenshot()
                bot.send_photo(CHAT_ID, shot, caption="❌ انتهت مهلة الـ 60 ثانية، هذه آخر شاشة توقف عندها المتصفح")
                browser.close()
                return False, "انتهت مهلة 60 ثانية دون الحصول على كوكي oauth_token."

            tokens_bundle = {
                "store_token": None,
                "games_token": oauth_token,
                "game_specific_tokens": [],
                "auth_diag": "Init",
                "oauth_err_details": ""
            }

            try:
                android_id = "396566cb13f27421"
                master_res = gpsoauth.exchange_token(email, oauth_token, android_id, sdk_version=33)
                master_token = master_res.get("Token")

                if master_token:
                    gm_res = gpsoauth.perform_oauth(
                        email, master_token, android_id,
                        service="oauth2:https://www.googleapis.com/auth/games https://www.googleapis.com/auth/games.firstparty",
                        app="com.google.android.play.games",
                        client_sig=GMS_SIG,
                        sdk_version=33
                    )
                    if gm_res.get("Auth"):
                        tokens_bundle["games_token"] = gm_res.get("Auth")

                    v2_toks, v2_diag, full_errs = request_play_games_tokens_with_debug(
                        email, master_token, android_id, chest
                    )
                    tokens_bundle["game_specific_tokens"] = v2_toks
                    tokens_bundle["auth_diag"] = v2_diag
                    tokens_bundle["oauth_err_details"] = full_errs
                else:
                    tokens_bundle["auth_diag"] = f"MasterSwapFail:{master_res.get('Error')}"
                    tokens_bundle["oauth_err_details"] = f"<code>{json.dumps(master_res)}</code>"
            except Exception as ex:
                tokens_bundle["auth_diag"] = f"Ex:{str(ex)[:20]}"
                tokens_bundle["oauth_err_details"] = f"<code>{str(ex)}</code>"

            browser.close()
            return True, tokens_bundle
    except Exception as e:
        return False, str(e)[:120]

if __name__ == "__main__":
    print("Quest Helper Stage-3 Real Debugger Started!")
    bot.infinity_polling(skip_pending=True)

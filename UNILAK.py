import os
import threading
import shutil
import uuid
import mimetypes
from flask import Flask, request, redirect, url_for, render_template_string, session, send_file
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
)

# ====== إعدادات =======
TOKEN = "8346787985:AAFItd5JZoz4PGiIROvwz1t-LOYez_zy0uo"  # <-- ضع توكن البوت هنا
ADMINS = [7770767498]  # <-- ضع id الأدمن هنا

# مجلد التخزين (عدّله لمسارك)
FILES_DIR = r"C:\Users\XPRISTO\Desktop\Unilack"  # مثال لويندوز
# FILES_DIR = "/home/pi/files"  # مثال للـ Raspberry Pi / لينكس

os.makedirs(FILES_DIR, exist_ok=True)

# بيانات دخول لوحة التحكم
USERNAME = "admin"
PASSWORD = "admin123"

# خريطة عامة لتخزين token -> مسار/نوع
# (in-memory). كل token صغير (hex uuid) لذا callback_data قصيرة.
GLOBAL_TOKEN_MAP = {}

# Store user reports
USER_REPORTS = {}

# ========== قوالب HTML ==========

LOGIN_PAGE = '''<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>واجهة إدارة الملفات</title>
    <style>
        :root {
            --bg-color: #f0f4f8;
            --container-bg: #ffffff;
            --text-color: #000000;
            --accent-color: #0288d1;
            --accent-hover: #0277bd;
            --error-color: #d32f2f;
        }
        [data-theme="dark"] {
            --bg-color: #121212;
            --container-bg: #1e1e1e;
            --text-color: #e0e0e0;
            --accent-color: #64b5f6;
            --accent-hover: #42a5f5;
            --error-color: #ef5350;
        }
        * {margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', sans-serif;}
        body {
            background-color: var(--bg-color);
            display: flex; justify-content: center; align-items: center;
            min-height: 100vh; transition: background-color 0.3s ease;
        }
        .login-container {
            background: var(--container-bg);
            padding: 2rem; border-radius: 20px;
            box-shadow: 0 6px 20px rgba(0,0,0,0.15);
            width: 100%; max-width: 400px; text-align: center;
            transition: background 0.3s ease;
        }
        h2 {color: var(--text-color); font-size: 1.8rem; margin-bottom: 1.5rem;}
        input[type="text"], input[type="password"] {
            width: 100%; padding: 14px; border: none;
            border-radius: 30px; font-size: 1rem;
            background: var(--bg-color); color: var(--text-color);
            margin-bottom: 1rem; outline: none;
            box-shadow: inset 0 2px 5px rgba(0,0,0,0.1);
        }
        input[type="submit"] {
            background: var(--accent-color); color: white;
            padding: 14px; border: none; width: 100%;
            border-radius: 30px; font-size: 1rem;
            cursor: pointer; font-weight: bold;
            box-shadow: 0 3px 10px rgba(0,0,0,0.2);
            transition: background 0.3s ease;
        }
        input[type="submit"]:hover {background: var(--accent-hover);}
        .error {color: var(--error-color); margin-top: 1rem;}
        .theme-toggle {
            margin-top: 1rem; cursor: pointer;
            color: var(--accent-color); font-weight: bold;
            display: inline-block; padding: 8px 16px;
            border-radius: 30px; background: var(--bg-color);
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: background 0.3s ease;
        }
        .theme-toggle:hover {background: var(--accent-hover); color: #fff;}
    </style>
</head>
<body data-theme="light">
    <div class="login-container">
        <h2>واجهة إدارة الملفات</h2>
        <form method="post">
            <input type="text" name="username" placeholder="اسم المستخدم" required>
            <input type="password" name="password" placeholder="كلمة المرور" required>
            <input type="submit" value="دخول">
        </form>
        {% if error %}<p class="error">{{ error }}</p>{% endif %}
        <div class="theme-toggle" onclick="toggleTheme()">🌓 تبديل الوضع</div>
    </div>
    <script>
        function toggleTheme(){
            const b=document.body;
            b.setAttribute('data-theme', b.getAttribute('data-theme')==='dark'?'light':'dark');
        }
    </script>
</body>
</html>
'''

HOME_PAGE = '''<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>لوحة التحكم</title>
    <style>
        :root {
            --bg-color: #fdfdfd;
            --container-bg: #ffffff;
            --text-color: #000000;
            --accent-color: #0288d1;
            --accent-hover: #0277bd;
            --danger-color: #d32f2f;
            --danger-hover: #b71c1c;
        }
        [data-theme="dark"] {
            --bg-color: #121212;
            --container-bg: #1e1e1e;
            --text-color: #e0e0e0;
            --accent-color: #64b5f6;
            --accent-hover: #42a5f5;
            --danger-color: #ef5350;
            --danger-hover: #c62828;
        }
        * {margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', sans-serif;}
        body {
            background-color: var(--bg-color);
            color: var(--text-color); min-height: 100vh; padding: 20px;
            transition: background 0.3s ease, color 0.3s ease;
        }
        .topbar {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 2rem;
        }
        h2 {font-size: 1.8rem; font-weight: bold;}
        .actions {display: flex; gap: 10px;}
        .btn {
            padding: 10px 18px; border: none; border-radius: 30px;
            font-size: 0.95rem; font-weight: bold; cursor: pointer;
            box-shadow: 0 3px 10px rgba(0,0,0,0.15);
            transition: background 0.3s ease, color 0.3s ease;
        }
        .btn-logout {background: var(--danger-color); color: #fff;}
        .btn-logout:hover {background: var(--danger-hover);}
        .btn-theme {background: var(--accent-color); color: #fff;}
        .btn-theme:hover {background: var(--accent-hover);}
        .path-display {margin-bottom: 1.5rem; color: var(--accent-hover);}
        form {
            background: var(--container-bg);
            padding: 1.2rem; border-radius: 16px;
            margin-bottom: 1.5rem; max-width: 600px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        label {font-weight: bold; margin-bottom: 0.5rem; display: block;}
        input[type="text"], input[type="file"] {
            width: 100%; padding: 12px; border: none; border-radius: 25px;
            background: var(--bg-color); color: var(--text-color);
            margin-bottom: 1rem; box-shadow: inset 0 2px 5px rgba(0,0,0,0.1);
        }
        input[type="submit"] {
            width: 100%; padding: 12px; border: none;
            border-radius: 30px; background: var(--accent-color); color: #fff;
            font-weight: bold; cursor: pointer;
            box-shadow: 0 3px 10px rgba(0,0,0,0.2);
        }
        input[type="submit"]:hover {background: var(--accent-hover);}
        ul {list-style: none; padding: 0; max-width: 600px;}
        li {
            background: var(--container-bg); padding: 15px; margin-bottom: 10px;
            border-radius: 16px; display: flex; justify-content: space-between; align-items: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .file-link {text-decoration: none; color: var(--text-color);}
        .file-link:hover {color: var(--accent-color);}
        .delete-button {
            background: var(--danger-color); border: none; color: white;
            padding: 8px 14px; border-radius: 25px; cursor: pointer;
            font-size: 0.9rem; box-shadow: 0 2px 6px rgba(0,0,0,0.15);
        }
        .delete-button:hover {background: var(--danger-hover);}
    </style>
</head>
<body data-theme="light">
    <div class="topbar">
        <h2>📂 واجهة إدارة الملفات</h2>
        <div class="actions">
            <a href="{{ url_for('logout') }}"><button class="btn btn-logout">🚪 خروج</button></a>
            <button class="btn btn-theme" onclick="toggleTheme()">🌓 تبديل الوضع</button>
        </div>
    </div>
    <p class="path-display">المسار الحالي: {{ current_path or '/' }}</p>

    <form method="post" action="{{ url_for('create_folder') }}">
        <label>📁 إنشاء مجلد جديد:</label>
        <input type="text" name="folder_name" placeholder="اسم المجلد" required>
        <input type="hidden" name="current_path" value="{{ current_path }}">
        <input type="submit" value="➕ إنشاء">
    </form>

    <form method="post" action="{{ url_for('upload_file') }}" enctype="multipart/form-data">
        <label>⬆️ رفع ملفات متعددة:</label>
        <input type="file" name="files" multiple required>
        <input type="hidden" name="current_path" value="{{ current_path }}">
        <input type="submit" value="📤 رفع">
    </form>

    <ul>
        {% for name, is_dir in contents %}
        <li>
            {% if is_dir %}
            <a class="file-link" href="{{ url_for('home', path=(current_path + '/' + name).lstrip('/')) }}">📁 {{ name }}</a>
            {% else %}
            <span class="file-link">📄 {{ name }}</span>
            {% endif %}
            <form method="post" action="{{ url_for('delete_item') }}" onsubmit="return confirm('هل أنت متأكد من الحذف؟')">
                <input type="hidden" name="item_path" value="{{ (current_path + '/' + name).lstrip('/') }}">
                <button type="submit" class="delete-button">🗑 حذف</button>
            </form>
        </li>
        {% endfor %}
    </ul>

    <script>
        function toggleTheme(){
            const b=document.body;
            b.setAttribute('data-theme', b.getAttribute('data-theme')==='dark'?'light':'dark');
        }
    </script>
</body>
</html>
'''


# ========== مساعدة الأذونات و الحماية ==========
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated


def secure_path_join(base, *paths):
    new_path = os.path.abspath(os.path.join(base, *paths))
    if not new_path.startswith(os.path.abspath(base)):
        raise Exception("غير مسموح بالخروج من المجلد الأساسي!")
    return new_path


def list_files_safe(path):
    try:
        return sorted([(name, os.path.isdir(os.path.join(path, name)))
                       for name in os.listdir(path)],
                      key=lambda x: (not x[1], x[0].lower()))
    except Exception:
        return []


# ========== Flask routes ==========
app = Flask(__name__)
app.secret_key = app.secret_key or "change-me-secret"


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        u = request.form.get("username", "")
        p = request.form.get("password", "")
        if u == USERNAME and p == PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("home"))
        else:
            error = "بيانات الدخول غير صحيحة."
    return render_template_string(LOGIN_PAGE, error=error)


@app.route("/logout")
@login_required
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
@login_required
def home(path):
    try:
        base_path = secure_path_join(FILES_DIR, path)
    except Exception:
        return "غير مسموح بالوصول لهذا المسار.", 403

    if not os.path.exists(base_path):
        base_path = FILES_DIR
        path = ""

    contents = list_files_safe(base_path)
    return render_template_string(HOME_PAGE, contents=contents, current_path=path)


@app.route("/create_folder", methods=["POST"])
@login_required
def create_folder():
    folder_name = request.form.get("folder_name", "").strip()
    current_path = request.form.get("current_path", "")
    if not folder_name:
        return redirect(url_for("home", path=current_path))
    try:
        base_path = secure_path_join(FILES_DIR, current_path)
        os.makedirs(os.path.join(base_path, folder_name), exist_ok=True)
    except Exception as e:
        return f"حدث خطأ: {e}", 400
    return redirect(url_for("home", path=current_path))


@app.route("/upload_file", methods=["POST"])
@login_required
def upload_file():
    current_path = request.form.get("current_path", "")
    try:
        base_path = secure_path_join(FILES_DIR, current_path)
    except Exception:
        return "غير مسموح بالوصول لهذا المسار.", 403

    if "files" not in request.files:
        return "لم يتم اختيار ملفات.", 400

    files = request.files.getlist("files")
    for f in files:
        if not f or f.filename == "":
            continue
        save_path = os.path.join(base_path, f.filename)
        f.save(save_path)
    return redirect(url_for("home", path=current_path))


@app.route("/delete_item", methods=["POST"])
@login_required
def delete_item():
    item_path = request.form.get("item_path", "")
    try:
        full = secure_path_join(FILES_DIR, item_path)
    except Exception:
        return "غير مسموح بالوصول.", 403
    if not os.path.exists(full):
        return "العنصر غير موجود.", 404
    try:
        if os.path.isdir(full):
            shutil.rmtree(full)
        else:
            os.remove(full)
    except Exception as e:
        return f"خطأ أثناء الحذف: {e}", 500
    parent = os.path.dirname(item_path)
    return redirect(url_for("home", path=parent))


# رابط تحميل من الويب (يعطي MIME type صحيح)
@app.route("/download/<path:filename>")
@login_required
def download_file(filename):
    try:
        full = secure_path_join(FILES_DIR, filename)
    except Exception:
        return "غير مسموح.", 403
    if not os.path.exists(full):
        return "الملف غير موجود.", 404
    mime_type, _ = mimetypes.guess_type(full)
    if mime_type is None:
        mime_type = "application/octet-stream"
    return send_file(full, mimetype=mime_type, as_attachment=True, download_name=os.path.basename(full))


# ========== Telegram bot logic ==========
# helper: build keyboard for a directory (returns InlineKeyboardMarkup)
def build_nav_keyboard_for_path(rel_path=""):
    """
    rel_path: مسار نسبي بالنسبة لـ FILES_DIR, '' يعني الجذر
    سنُنشئ أزرارًا للمجلدات والملفات داخل هذا المسار
    نُنشئ token قصير لكل زر ونخزّن mapping في GLOBAL_TOKEN_MAP
    """
    abs_path = os.path.join(FILES_DIR, rel_path) if rel_path else FILES_DIR
    items = list_files_safe(abs_path)

    keyboard = []
    # زر للصعود للمجلد الأب إن لم نكن في الجذر
    if rel_path:
        parent = os.path.dirname(rel_path)
        token = "D" + uuid.uuid4().hex  # D => dir nav token
        GLOBAL_TOKEN_MAP[token] = {"type": "dir", "path": parent}
        keyboard.append([InlineKeyboardButton("⬆️ رجوع", callback_data=token)])

    # أولًا المجلدات
    for name, is_dir in items:
        token = ("D" if is_dir else "F") + uuid.uuid4().hex
        entry_rel = os.path.join(rel_path, name) if rel_path else name
        GLOBAL_TOKEN_MAP[token] = {"type": "dir" if is_dir else "file", "path": entry_rel}
        text = f"📁 {name}" if is_dir else f"📄 {name}"
        keyboard.append([InlineKeyboardButton(text, callback_data=token)])

    # إضافة زر للوصول إلى الواجهة عبر الويب (اختياري)
    # keyboard.append([InlineKeyboardButton("🌐 افتح لوحة التحكم", url="http://your-host:5000/")])

    return InlineKeyboardMarkup(keyboard)


# send initial root nav to user
async def send_root_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    markup = build_nav_keyboard_for_path("")  # root
    await update.message.reply_text("📂 اختر مجلد أو ملف:", reply_markup=markup)


# ========== REPORT: أمر /report لإرسال بلاغ للأدمن ==========
async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_text = " ".join(context.args) if context.args else ""

    if not message_text:
        await update.message.reply_text(
            "Please provide a message for the admins. Usage: /report your message here"
        )
        return

    report_id = str(uuid.uuid4())[:8]
    USER_REPORTS[report_id] = {
        "user_id": user.id,
        "username": user.username or user.first_name,
        "message": message_text,
        "timestamp": update.message.date
    }

    for admin_id in ADMINS:
        try:
            keyboard = [[InlineKeyboardButton("Answer", callback_data=f"ANSWER_{report_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(
                chat_id=admin_id,
                text=f"NEW REPORT from {user.username or user.first_name} (ID: {user.id})\n\nReport ID: {report_id}\nMessage: {message_text}",
                reply_markup=reply_markup
            )
        except Exception as e:
            print(f"Failed to notify admin {admin_id}: {e}")

    await update.message.reply_text("Your message has been sent to admins! They will contact you soon.")


# handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    buttons = [[InlineKeyboardButton("📥 تصفح الملفات", callback_data="NAV_ROOT")]]
    if user_id in ADMINS:
        buttons.insert(0, [InlineKeyboardButton("🌐 لوحة التحكم", callback_data="ADMIN_PANEL")])
    else:
        buttons.append([InlineKeyboardButton("Contact Admin", callback_data="REPORT_HELP")])
    markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("مرحبًا بك في بوت Unilak PDF 📚", reply_markup=markup)


async def upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS:
        await update.message.reply_text("❌ أنت لست مشرفًا.")
        return
    # عيّن هنا ال IP أو الدومين الصحيح الخاص بجهازك
    link = "http://192.168.1.70:5000"
    await update.message.reply_text(f"🌐 للدخول إلى لوحة التحكم: {link}\nاستخدم اسم المستخدم وكلمة المرور للدخول.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
Available commands:
/start - Start the bot
/report - Contact admins
/help - Show this help

Use /report your_message to contact administrators.
"""
    await update.message.reply_text(help_text)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        data = query.data
        user_id = query.from_user.id

        # خاصية: زر يبدأ التصفح من الجذر
        if data == "NAV_ROOT":
            markup = build_nav_keyboard_for_path("")
            # أرسل الرسالة سواء وُجد query.message أم لا
            if query.message:
                await query.message.reply_text("📂 اختر مجلد أو ملف:", reply_markup=markup)
            else:
                # fallback في حال كانت الرسالة inline ولا يوجد query.message
                await context.bot.send_message(chat_id=user_id, text="📂 اختر مجلد أو ملف:", reply_markup=markup)
            return

        # زر فتح لوحة التحكم (للمشرفين)
        if data == "ADMIN_PANEL":
            if user_id not in ADMINS:
                await query.message.reply_text("❌ أنت لست مشرفًا.")
                return
            link = "http://192.168.1.70:5000"
            await query.message.reply_text(
                f"🌐 للدخول إلى لوحة التحكم: {link}\nاستخدم اسم المستخدم وكلمة المرور للدخول.")
            return

        # مساعدة الإبلاغ للمستخدمين
        if data == "REPORT_HELP":
            await query.message.reply_text(
                "To contact admins, use: /report your_message_here\nExample: /report I need help with a file"
            )
            return

        # الأدمن يختار الرد على بلاغ
        if data.startswith("ANSWER_"):
            report_id = data.replace("ANSWER_", "")
            if report_id not in USER_REPORTS:
                await query.message.reply_text("Report not found.")
                return
            report = USER_REPORTS[report_id]
            context.user_data["current_report"] = report_id
            context.user_data["report_user_id"] = report["user_id"]
            await query.message.reply_text(
                f"Replying to report from {report['username']}:\n{report['message']}\n\nPlease type your response:"
            )
            return

        # تعامل مع التوكن المسجّلة
        entry = GLOBAL_TOKEN_MAP.get(data)
        if not entry:
            await query.message.reply_text("⚠️ هذا الزر غير صالح أو انتهى صلاحيته. حاول مجددًا.")
            return

        if entry["type"] == "dir":
            rel = entry["path"] or ""
            markup = build_nav_keyboard_for_path(rel)
            text = f"📂 محتويات: /{rel}" if rel else "📂 الجذر:"
            if query.message:
                await query.message.reply_text(text, reply_markup=markup)
            else:
                await context.bot.send_message(chat_id=user_id, text=text, reply_markup=markup)
            return

        if entry["type"] == "file":
            rel = entry["path"]
            full = os.path.join(FILES_DIR, rel)
            if not os.path.exists(full):
                await query.message.reply_text("❌ الملف غير موجود.")
                return

            # Guess MIME type and set a fallback
            mime_type, _ = mimetypes.guess_type(full)
            if mime_type is None:
                mime_type = "application/octet-stream"  # Fallback MIME type
                # Optionally map common extensions to MIME types
                extension = os.path.splitext(full)[1].lower()
                mime_map = {
                    '.pdf': 'application/pdf',
                    '.txt': 'text/plain',
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.png': 'image/png',
                    '.doc': 'application/msword',
                    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                }
                mime_type = mime_map.get(extension, mime_type)

            # Get the filename for Telegram
            filename = os.path.basename(full)

            try:
                # Send the file with explicit filename and MIME type
                with open(full, 'rb') as file:
                    await query.message.reply_document(
                        document=InputFile(file, filename=filename),
                        filename=filename,
                        caption=f"📄 {filename}"
                    )
            except Exception as e:
                await query.message.reply_text(f"حدث خطأ أثناء إرسال الملف , رجاء اختيار ملفك مجدداً : {e}")
            return
    except Exception as e:
        # سجل أي خطأ في ال callback لسهولة التشخيص
        print(f"[callback_handler error] {e}")
        try:
            await update.effective_chat.send_message(f"حدث خطأ غير متوقع: {e}")
        except Exception:
            pass


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # رد الأدمن على البلاغ
    if "current_report" in context.user_data:
        report_id = context.user_data["current_report"]
        user_id = context.user_data["report_user_id"]
        response_text = update.message.text

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"Admin response to your report:\n\n{response_text}"
            )
            await update.message.reply_text("Response sent successfully!")

            # Clean up
            del context.user_data["current_report"]
            del context.user_data["report_user_id"]

            # Optional: mark report as answered
            if report_id in USER_REPORTS:
                USER_REPORTS[report_id]["answered"] = True

        except Exception as e:
            await update.message.reply_text(f"Failed to send response: {e}")
        return

    # دردشة عادية
    txt = (update.message.text or "").lower()
    if "hello" in txt or "hi" in txt:
        await update.message.reply_text("welcome!")
    elif "good morning" in txt:
        await update.message.reply_text("Good morning! Hope you have a great day ahead.")
    elif "how are you" in txt:
        await update.message.reply_text("I'm doing well, thanks! How about you?")
    elif "what's up" in txt or "whats up" in txt:
        await update.message.reply_text("Not much, just here to give you what you want 😉")
    elif "who are you" in txt:
        await update.message.reply_text("I'm Unilak Bot Assistant, here to Give you the documents that you need😄")
    elif "good" in txt or "that's good" in txt or "awesome" in txt:
        await update.message.reply_text("thank you! i really appreciate it!🥰")
    elif "help" in txt:
        await update.message.reply_text("Sure! What do you need help with?")
    elif "bye" in txt or "see you" in txt:
        await update.message.reply_text("Bye! Feel free to come back anytime.")
    elif "thank you" in txt or "thanks" in txt:
        await update.message.reply_text("You're welcome! Happy to assist you❤️")
    elif "what can you do" in txt:
        await update.message.reply_text("I can chat with you, answer questions, or keep you company. Just ask!")
    elif "i need a book" in txt or "give me a book" in txt:
        await update.message.reply_text("just click here /start  and get your document")
    else:
        await update.message.reply_text("i can not understand 😥")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"Error: {context.error}")


def run_flask():
    # لا تشغّل debug=True عندما تشغل Flask في thread
    app.run(host="0.0.0.0", port=5000, debug=False)


# ========== Main ==========
if __name__ == "__main__":
    # شغّل Flask في thread منفصل
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    app_tel = Application.builder().token(TOKEN).build()
    app_tel.add_handler(CommandHandler("start", start_command))
    app_tel.add_handler(CommandHandler("upload", upload_command))
    app_tel.add_handler(CommandHandler("help", help_command))
    app_tel.add_handler(CommandHandler("report", report_command))
    app_tel.add_handler(CallbackQueryHandler(callback_handler))
    app_tel.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app_tel.add_error_handler(error_handler)

    print("✅ Bot and Flask server are running...")
    app_tel.run_polling()

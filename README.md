# مشروع مدراستي - Madrasti Project

## 📋 محتويات المجلد (ملفات النشر على Heroku)

هذا المجلد يحتوي على جميع الملفات الضرورية لنشر التطبيق على **Heroku** أو أي سيرفر آخر.

---

## 📁 المجلدات

### 1️⃣ `backend/` 
- **الغرض**: الواجهة الخلفية (FastAPI)
- **الملفات الرئيسية**:
  - `app.py` - تطبيق FastAPI الرئيسي
  - `models.py` - نماذج قاعدة البيانات
  - `schemas.py` - نماذج البيانات المرسلة والمستقبلة
  - `database.py` - إعدادات قاعدة البيانات
  - `chat_routes.py` - مسارات الدردشة والرسائل

### 2️⃣ `frontend/`
- **الغرض**: الواجهة الأمامية (HTML/CSS/JavaScript)
- **الملفات الرئيسية**:
  - `index.html` - الصفحة الرئيسية
  - `dashboard.html` - لوحة التحكم
  - `chat.html` - صفحة الدردشة
  - `*.js` - ملفات JavaScript للتفاعل
  - `*.css` - ملفات تنسيق CSS

---

## 📄 الملفات الرئيسية

### `requirements.txt`
- قائمة المكتبات Python المطلوبة
- تُستخدم لتثبيت جميع الحزم على السيرفر

### `Procfile`
- ملف تكوين Heroku
- يحتوي على الأمر لتشغيل التطبيق

### `.env`
- ملف متغيرات البيئة الحساسة
- ⚠️ **تأكد من تغيير البيانات الحساسة قبل الرفع**:
  - `SECRET_KEY` - مفتاح سري عشوائي قوي
  - `SMTP_USER` و `SMTP_PASSWORD` - بيانات البريد الإلكتروني
  - `LAUNCH_SUPER_ADMIN_EMAIL` و `LAUNCH_SUPER_ADMIN_PASSWORD`

---

## 🚀 خطوات النشر على Heroku

### 1. تثبيت Heroku CLI
```
https://devcenter.heroku.com/articles/heroku-cli
```

### 2. تسجيل الدخول إلى Heroku
```bash
heroku login
```

### 3. إنشاء تطبيق جديد على Heroku
```bash
heroku create your-app-name
```

### 4. تكوين متغيرات البيئة
```bash
heroku config:set SECRET_KEY="your-secret-key"
heroku config:set SMTP_HOST="smtp.gmail.com"
heroku config:set SMTP_PORT="587"
heroku config:set SMTP_USER="your-email@gmail.com"
heroku config:set SMTP_PASSWORD="your-app-password"
```

### 5. دفع الملفات إلى Heroku
```bash
git init
git add .
git commit -m "Initial commit"
git push heroku master
```

### 6. عرض السجلات
```bash
heroku logs --tail
```

---

## ⚙️ ملاحظات مهمة

- ✅ قاعدة البيانات ستُنشأ تلقائياً عند أول تشغيل
- ✅ جميع صور وملفات Frontend موجودة
- ☑️ تأكد من تحديث `.env` ببيانات صحيحة قبل النشر
- ⚠️ لا تضع بيانات حساسة في الكود - استخدم متغيرات البيئة

---

## 📞 الدعم
للمساعدة، تحقق من ملفات التطبيق في مجلد `backend/`.


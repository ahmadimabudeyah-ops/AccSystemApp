# Accounting Platform — Backend (Flask 3 + SQLAlchemy 2 + PG18)

## التشغيل المحلي (بدون Docker)

### 1. قاعدة البيانات (منفذ 5433 — نسخة خاصة بالمشروع)
```powershell
# بدء خادم المشروع
Start-Process -FilePath "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe" `
  -ArgumentList "-D C:\AccSystem\.pgdata -l C:\AccSystem\.pgdata.log -o ""-p 5433"" start"
# تطبيق المخطط (المراحل 1-7) + صلاحيات المحرك
$env:PGPASSWORD="accounting123"
psql -U accounting -h 127.0.0.1 -p 5433 -d accounting_db -f ..\db\sql\phase1_foundation.sql
# ... phase2 .. phase7 بنفس الطريقة ...
psql -U accounting -h 127.0.0.1 -p 5433 -d accounting_db -f ..\db\sql\seed_engine_permissions.sql
```

### 2. البذور
```powershell
cd backend
python scripts\seed_base.py     # مستأجر DEMO + مدير + كيان + سنة 2026 + دليل IFRS + دفاتر
python scripts\mkchecker.py     # مستخدم فاحص ثانٍ (للترحيل)
```

### 3. التشغيل والتحقق
```powershell
python wsgi.py                                   # http://127.0.0.1:5000/health
python scripts\cycle_test.py                     # دورة كاملة: إنشاء→ازدواج→فصل مهام→ترحيل→ميزان→عكس
python -m pytest tests\ -q                       # 8 اختبارات
python scripts\check_pages.py                    # 116 صفحة ويب تُصيَّر
```

### 4. الدخول
- المتصفح: http://127.0.0.1:5000/ (رمز المؤسسة DEMO)
- `admin@demo.local / Admin@123` (صانع) — `checker@demo.local / Checker@123` (مرحّل)
- الـ API يتطلب هيدر `X-Tenant-ID` + JWT.

## ملاحظات تكامل موثقة
- أسماء أعمدة القاعدة (phase SQL) تختلف عن الأسماء المنطقية — المواءمة عبر
  `mapped_column("...", ...)` في `app/models/journal.py` (مثال: `period_id` ← `fiscal_period_id`).
- `metadata` اسم محجوز في SQLAlchemy — الخاصية اسمها `extra` (العمود `metadata`).
- سياق RLS بجلسة `SET` + تصفير عند نهاية الطلب (لا `SET LOCAL` — يضيع بعد أول commit).
- مشغّل `fn_forbid_posted` يسمح بالانتقال الوحيد `posted→reversed` (تغيير الحالة فقط).

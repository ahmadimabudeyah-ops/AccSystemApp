# المخرج 4: وثيقة الواجهات الأمامية (79 قالبًا + 10 ملفات ستاتيك)

## 1. الفلسفة: عربي أولًا لا مترجمًا

`lang="ar" dir="rtl"` إجباري؛ خصائص CSS منطقية فقط (`margin-inline` لا `margin-left` —
مفحوص آليًا)؛ خطوط Cairo (عناوين 700-900) وTajawal (نصوص) وIBM Plex Sans Arabic
(أرقام الجداول) وNoto Kufi (الشعار)؛ `line-height` 1.7-1.9 للعربية؛ ممنوع
`letter-spacing` مع العربية؛ الأرقام المالية غربية والمجاميع مشرقية حسب السياق؛
التواريخ والعملات عربية (د.أ)؛ الأيقونات الاتجاهية تنعكس تلقائيًا.

## 2. الهوية (بني القهوة + ذهبي + عاجي)

Brown-500 `#A67B5B` أساسي، Brown-900 `#2B1D13` للعمق، Gold-500 `#C9A961` للتمييز؛
دلالية هادئة (زيتون/طوب/سماء)؛ تدرجات luxury/f Gold/subtle؛ ظلال دافئة
`rgba(43,29,19,·)`؛ زوايا 6-24px؛ نظام مسافات 4px؛ وضع ليلي دافئ
(`#1C1917`) بمفتاح محفوظ في `localStorage` وانتقال 300ms.

## 3. البنية (تطابق المنفذ)

`base.html` (خطوط CDN + CSS الخمسة + HTMX/Alpine/Chart.js) ← `layouts/`:
`auth.html` (منقسمة تسويقية)، `dashboard.html` (sidebar+header+toasts+confirm)،
`print.html` (A4 بلا زخارف) ← `partials/` (13: head/header/sidebar/footer/
breadcrumbs/notifications/user_menu/pagination/search_bar/theme_toggle/loading/
empty_state/confirm_modal/flash_messages) ← `shared/` (أجسام عامة:
`_list_body` بفلاتر وتصدير CSV، `_form_body` بتحقق عربي، `_detail_body`
بأزرار API مباشرة) ← صفحات الوحدات (auth 4، dashboard، accounts 4 + شجرة حية،
journals 3، entries 5 + نموذج أسطر ديناميكي، parties 4 + كشف، products 3،
inventory، sales 8، purchases 6، treasury 8، assets 3، taxes 3، reports 2 +
عارض حي، settings 6، errors 3).

## 4. التفاعل والبيانات الحية

`main.js` (ثيم/تنبيهات/Ctrl+K/هيدرز API) + `data.js` (جلب الكيانات/الجداول/
التفاصيل/الشجرة/التقارير/اللوحة من الـ API بالتوكن المخزن + عارض عام بالأعمدة)
+ `forms.js` (تحقق عربي + إرسال القيد بمفتاح عدم تكرار + دخول) +
`tables.js` (تصدير CSV + طي الشجرة) + `charts.js` (RTL: عكس X، أساطير عربية،
تحديث حي عند `dash:ready`). لا أسرار في القوالب — التوكن في `sessionStorage`.

## 5. الملاحة والتدفقات

قائمة مجمعة (محاسبة/مبيعات/مشتريات/مخزون/خزينة/أصول/أطراف/تقارير/موارد/تعليم/
مشاريع/إعدادات) بتمييز نشط وحد ذهبي؛ زر `+ جديد` سياقي (قيد/فاتورة/طرف/صنف)؛
Breadcrumbs `الرئيسية › القسم › الصفحة`؛ سلاسل مترابطة: عرض→أمر→تسليم→فاتورة→
تحصيل، وطلب→أمر→استلام→فاتورة→دفع؛ كل إجراء مدمر بتأكيد عربي لا `confirm()`.

## 6. الوصولية والتجاوب

تباين 4.5:1، `aria-label` عربية، تنقل كيبورد، `prefers-reduced-motion`،
Breakpoints (640/1024/1440، أقصى 1400px)، Drawer يميني للجوال، طباعة A4
بترويسة وسجل ضريبي. المعايير: WCAG 2.1 AA مستهدفة ومدققة يدويًا.

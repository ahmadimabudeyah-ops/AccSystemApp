# docs/ERD.md — مخطط العلاقات (نواة v1 — تُوسّع لكل مجموعة)

```mermaid
erDiagram
  tenants ||--o{ users : has
  tenants ||--o{ entities : has
  entities ||--o{ branches : has
  entities ||--o{ fiscal_years : has
  fiscal_years ||--o{ fiscal_periods : has
  entities ||--o{ accounts : chart
  accounts ||--o{ accounts : parent
  accounts ||--o{ account_report_mappings : maps
  journals ||--o{ journal_entries : books
  fiscal_periods ||--o{ journal_entries : in-period
  journal_entries ||--o{ journal_lines : contains
  accounts ||--o{ journal_lines : debited-credited
  journal_entries ||--o{ reversal_links : reversed-by
  fiscal_periods ||--o| closing_snapshots : snapshot
  dimensions ||--o{ dimension_values : values
```

**قاعدة قراءة:** كل سهم `}o--` يحمل `tenant_id` في الطرفين + FK مع `ON DELETE RESTRICT`
(عدا جداول الحركات `CASCADE` من الرأس إلى السطور فقط).
الأرصدة لا تُخزن — تُشتق عبر `fn_calculate_trial_balance` من `journal_lines↔entries WHERE status='posted'`.
```

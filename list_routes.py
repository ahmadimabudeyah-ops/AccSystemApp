import os, re
web_dir = r'C:\AccSystem\backend\app\web'
for f in sorted(os.listdir(web_dir)):
    if f.endswith('.py') and f not in ('__init__.py', '_helpers.py'):
        path = os.path.join(web_dir, f)
        with open(path, 'r', encoding='utf-8') as fp:
            content = fp.read()
        routes = re.findall(r"@bp\.(get|post|put|delete|patch)\(['\"]([^'\"]+)['\"]\)\s*\n\s*def (\w+)", content)
        print(f'=== {f} ===')
        for method, route, func in routes:
            print(f'  {method.upper()} {route} -> {func}')
        print()
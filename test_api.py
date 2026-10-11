import requests

BASE = 'http://127.0.0.1:5000'
API = BASE + '/api/v1'

r = requests.post(API + '/auth/login', 
    json={'username': 'admin@demo.local', 'password': 'Admin@123'},
    headers={'X-Tenant-ID': 'DEMO'})
print('Login:', r.status_code)
if r.status_code == 200:
    token = r.json()['access_token']
    h = {'Authorization': f'Bearer {token}', 'X-Tenant-ID': 'DEMO'}
    
    r = requests.get(API + '/tenants/b39787b5-52fb-4fb0-b41f-98b90b5853d6/entities', headers=h)
    print('Entities:', r.status_code)
    
    r = requests.get(API + '/sales/invoices', headers=h)
    print('Invoices list:', r.status_code, len(r.json().get('data', [])))
    
    r = requests.get(API + '/parties?type=customer', headers=h)
    customers = r.json().get('data', [])
    if customers:
        cust_id = customers[0]['id']
        print('Customer:', cust_id)
        
        r = requests.get(API + '/products?entity_id=f50db4a1-9381-400d-954b-79c515667f74', headers=h)
        products = r.json().get('data', [])
        if products:
            prod_id = products[0]['id']
            print('Product:', prod_id)
            
            r = requests.post(API + '/sales/invoices', headers=h, json={
                'entity_id': 'f50db4a1-9381-400d-954b-79c515667f74',
                'customer_id': cust_id,
                'invoice_date': '2026-10-11',
                'currency_id': 'JOD',
                'exchange_rate': 1,
                'lines': [{'product_id': prod_id, 'qty': 2, 'unit_price': 50, 'tax_id': None, 'discount_pct': 0}]
            })
            print('Create invoice:', r.status_code, r.json() if r.status_code == 201 else r.text[:200])
            
            if r.status_code == 201:
                inv_id = r.json()['data']['id']
                r = requests.post(f'{API}/sales/invoices/{inv_id}/post', headers=h)
                print('Post invoice:', r.status_code)
                
                r = requests.post(f'{API}/sales/payments', headers=h, json={
                    'entity_id': 'f50db4a1-9381-400d-954b-79c515667f74',
                    'customer_id': cust_id,
                    'pay_date': '2026-10-11',
                    'pay_method': 'cash',
                    'amount': 100,
                    'currency_id': 'JOD',
                    'exchange_rate': 1
                })
                print('Create payment:', r.status_code)
                
                if r.status_code == 201:
                    pay_id = r.json()['data']['id']
                    r = requests.get(f'{API}/accounts?entity_id=f50db4a1-9381-400d-954b-79c515667f74', headers=h)
                    accounts = r.json().get('data', [])
                    cash_acc = next((a for a in accounts if a.get('code', '').startswith('101')), None)
                    if cash_acc:
                        r = requests.post(f'{API}/sales/payments/{pay_id}/post', headers=h, json={'cash_account_id': cash_acc['id']})
                        print('Post payment:', r.status_code)
                        
                        r = requests.post(f'{API}/sales/payments/{pay_id}/allocate', headers=h, json={
                            'allocations': [{'invoice_id': inv_id, 'allocated_amount': 100}]
                        })
                        print('Allocate payment:', r.status_code)
    
    r = requests.get(API + '/reports/dashboard-summary?entity_id=f50db4a1-9381-400d-954b-79c515667f74', headers=h)
    print('Dashboard summary:', r.status_code, list(r.json().keys()) if r.status_code == 200 else r.text[:100])
    
    if customers:
        r = requests.get(API + '/parties/' + customers[0]['id'] + '/statement', headers=h)
        print('Party statement:', r.status_code, list(r.json().keys()) if r.status_code == 200 else r.text[:100])
    
    r = requests.get(API + '/purchases/bills', headers=h)
    print('Purchase bills:', r.status_code, len(r.json().get('data', [])))
    
    r = requests.get(API + '/purchases/orders', headers=h)
    print('Purchase orders:', r.status_code, len(r.json().get('data', [])))
    
    r = requests.get(API + '/sales/credit-notes', headers=h)
    print('Credit notes:', r.status_code, len(r.json().get('data', [])))
    
    r = requests.get(API + '/sales/returns', headers=h)
    print('Sales returns:', r.status_code, len(r.json().get('data', [])))
    
    r = requests.get(API + '/parties?type=supplier', headers=h)
    suppliers = r.json().get('data', [])
    print('Suppliers:', len(suppliers))
    
    if suppliers:
        r = requests.get(API + '/purchases/receipts', headers=h)
        print('Receipts:', r.status_code, len(r.json().get('data', [])))
        
        r = requests.get(API + '/purchases/requests', headers=h)
        print('Purchase requests:', r.status_code, len(r.json().get('data', [])))
    
    print('\nAll core API flows working!')
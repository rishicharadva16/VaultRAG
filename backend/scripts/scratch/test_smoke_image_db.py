import urllib.request
import urllib.error
import json
from urllib.parse import quote

def get_token(email):
    req = urllib.request.Request(
        'http://localhost:8000/auth/login',
        data=json.dumps({'email': email, 'password': 'changeme123'}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    return json.loads(urllib.request.urlopen(req).read())['access_token']

t_karan = get_token('karan.shah@northwind.example')
t_meera = get_token('meera.iyer@northwind.example')

# Image test
q_img = quote('img:invoice_01_apex_apr.png#0', safe='')
req_iv = urllib.request.Request(f'http://localhost:8000/source/{q_img}/view?hl=0-50', headers={'Authorization': f'Bearer {t_karan}'})
data_iv = json.loads(urllib.request.urlopen(req_iv).read())
print('Image view:', data_iv['kind'], 'match:', data_iv['match'], 'rects:', len(data_iv['rects']), 'pw:', data_iv['page_width'], 'ph:', data_iv['page_height'])

req_ip = urllib.request.Request(f'http://localhost:8000/source/{q_img}/pages', headers={'Authorization': f'Bearer {t_karan}'})
data_ip = json.loads(urllib.request.urlopen(req_ip).read())
print('Image pages:', data_ip)

req_im = urllib.request.Request(f'http://localhost:8000/source/{q_img}/page.png', headers={'Authorization': f'Bearer {t_karan}'})
res_im = urllib.request.urlopen(req_im)
print('Image page.png status:', res_im.status, 'type:', res_im.headers.get('content-type'))

# DB row test
q_db = quote('db:salaries#E1004:sensitive', safe='')
req_dv = urllib.request.Request(f'http://localhost:8000/source/{q_db}/view?hl=0-20', headers={'Authorization': f'Bearer {t_meera}'})
data_dv = json.loads(urllib.request.urlopen(req_dv).read())
print('DB view:', data_dv['kind'], 'row_id:', data_dv['row_id'], 'text len:', len(data_dv['text']))

try:
    urllib.request.urlopen(urllib.request.Request(f'http://localhost:8000/source/{q_db}/page.png', headers={'Authorization': f'Bearer {t_meera}'}))
    print('DB page.png ERROR: unexpected success')
except urllib.error.HTTPError as e:
    print('DB page.png expected status:', e.code)

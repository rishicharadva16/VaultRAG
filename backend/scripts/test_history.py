import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.db.models import User
from app.security.jwt import create_token

db = SessionLocal()
users = db.query(User).all()
for u in users:
    print(u.id, u.name, u.roles, u.active)

admin_u = next((u for u in users if 'admin' in (u.roles or []) and u.active), None)
normal_u = next((u for u in users if 'admin' not in (u.roles or []) and u.active), None)

client = TestClient(app)

if admin_u:
    token_admin = create_token(admin_u.id)
    res_admin = client.get('/history', headers={'Authorization': f'Bearer {token_admin}'})
    print('Admin GET /history status:', res_admin.status_code, 'len:', len(res_admin.json()) if res_admin.status_code == 200 else res_admin.text)

if normal_u:
    token_norm = create_token(normal_u.id)
    res_norm = client.get('/history', headers={'Authorization': f'Bearer {token_norm}'})
    print('Normal user:', normal_u.email, 'status:', res_norm.status_code, 'len:', len(res_norm.json()) if res_norm.status_code == 200 else res_norm.text)

db.close()

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.db.session import SessionLocal
from app.db.models import User

db = SessionLocal()
users = db.query(User).order_by(User.id).all()
print(f"{'User ID':<36} | {'Name':<18} | {'Email':<30} | {'Dept':<12} | {'EmpID':<6} | {'Roles':<12} | {'Active':<6} | {'Demo'}")
print("-" * 135)
for u in users:
    print(f"{u.id:<36} | {u.name:<18} | {u.email:<30} | {str(u.department):<12} | {str(u.employee_id):<6} | {str(u.roles):<12} | {str(u.active):<6} | {u.shown_in_demo}")

"""One-time script: fix PostgreSQL data."""
from sqlalchemy import create_engine, text
import bcrypt

eng = create_engine("postgresql+psycopg2://postgres:admin123@localhost:5432/energy_saver_ai")
admin_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()

with eng.connect() as c:
    # 1) Ensure admin user exists with valid password
    admin = c.execute(text("SELECT id FROM users WHERE username='admin'")).fetchone()
    if not admin:
        c.execute(text(
            "INSERT INTO users (username, email, hashed_password, role, is_active) "
            "VALUES ('admin', 'admin@energysaver.ai', :h, 'admin', true)"
        ), {"h": admin_hash})
        print("Created admin user (admin@energysaver.ai / admin123)")
    else:
        c.execute(text("UPDATE users SET hashed_password = :h WHERE username = 'admin'"), {"h": admin_hash})
        print("Updated admin password to admin123")

    # 2) Delete deactivated tenants permanently
    deleted = c.execute(text("DELETE FROM subscriptions WHERE tenant_id IN (SELECT id FROM tenants WHERE is_active = false)")).rowcount
    print(f"Deleted {deleted} subscriptions for inactive tenants")
    deleted = c.execute(text("DELETE FROM tenants WHERE is_active = false")).rowcount
    print(f"Deleted {deleted} inactive tenants from DB")

    c.commit()

    # 3) Show final state
    tenants = c.execute(text("SELECT id, name, unit_key, email, is_active FROM tenants ORDER BY id")).fetchall()
    print(f"\nPostgreSQL now has {len(tenants)} tenants:")
    for r in tenants:
        print(f"  id={r[0]}  name={r[1]}  unit={r[2]}  email={r[3]}  active={r[4]}")

    users = c.execute(text("SELECT id, username, email, role FROM users ORDER BY id")).fetchall()
    print(f"\nUsers ({len(users)}):")
    for r in users:
        print(f"  id={r[0]}  user={r[1]}  email={r[2]}  role={r[3]}")

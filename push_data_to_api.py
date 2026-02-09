import requests
import sqlite3
import json
import time

# Configuration
API_URL = "https://web-production-20dbc.up.railway.app" # Removing /api from base to clearer handling
LOCAL_DB = "instance/construction_tracker.db"

# Admin credentials to authenticate for migration
USERNAME = "admin"
PASSWORD = "admin123"

def get_token():
    full_url = f"{API_URL}/api/login"
    print(f"🔑 Logging in to {full_url} as {USERNAME}...")
    try:
        resp = requests.post(full_url, json={
            "username": USERNAME,
            "password": PASSWORD
        })
        if resp.status_code == 200:
            return resp.json()['token']
        else:
            print(f"❌ Login failed: {resp.text}")
            return None
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return None

def fetch_local_data():
    print(f"📂 Reading local database: {LOCAL_DB}")
    conn = sqlite3.connect(LOCAL_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    payload = {
        "users": [],
        "projetos": [],
        "relatorios": [],
        "visitas": []
    }

    # Fetch Users
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    for u in users:
        payload["users"].append(dict(u))
    print(f"   - Found {len(payload['users'])} users")

    # Fetch Projects
    cursor.execute("SELECT * FROM projetos")
    projects = cursor.fetchall()
    for p in projects:
        # Get responsavel email to map if needed
        resp_id = p['responsavel_id']
        cursor.execute("SELECT email FROM users WHERE id = ?", (resp_id,))
        resp = cursor.fetchone()
        
        proj_dict = dict(p)
        if resp:
            proj_dict['responsavel_email'] = resp['email']
            
        payload["projetos"].append(proj_dict)
    print(f"   - Found {len(payload['projetos'])} projects")

    # Fetch Reports
    print(f"   - Fetching reports...")
    cursor.execute("SELECT * FROM relatorios")
    reports = cursor.fetchall()
    for r in reports:
        report_dict = dict(r)
        
        # Get photos for this report
        cursor.execute("SELECT * FROM fotos_relatorio WHERE relatorio_id = ?", (r['id'],))
        photos = cursor.fetchall()
        report_dict['photos'] = [dict(ph) for ph in photos]
        
        payload["relatorios"].append(report_dict)
    print(f"   - Found {len(payload['relatorios'])} reports")

    # Fetch Visits
    cursor.execute("SELECT * FROM visitas")
    visitas = cursor.fetchall()
    for v in visitas:
        payload["visitas"].append(dict(v))
    print(f"   - Found {len(payload['visitas'])} visits")

    conn.close()
    return payload

def push_data(token, data):
    print("🚀 Pushing data to Railway via API...")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        url = f"{API_URL}/api/admin/import-legacy-data"
        print(f"➡️ POST {url}")
        resp = requests.post(url, json=data, headers=headers)
        if resp.status_code == 201:
            print("✅ Success!")
            print(json.dumps(resp.json(), indent=2))
        else:
            print(f"❌ Import failed ({resp.status_code}): {resp.text}")
    except Exception as e:
        print(f"❌ API Error: {e}")

if __name__ == "__main__":
    # 1. Get Token
    token = get_token()
    if not token:
        # Try waiting a bit if deployment is still finishing
        print("⚠️ Waiting 10s for deployment to settle...")
        time.sleep(10)
        token = get_token()

    if token:
        # 2. Get Data
        data = fetch_local_data()
        
        # 3. Push Data
        if data["users"] or data["projetos"]:
            push_data(token, data)
        else:
            print("⚠️ No data to migrate.")

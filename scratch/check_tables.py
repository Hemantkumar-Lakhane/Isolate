import os
import psycopg2

def load_env(path):
    env = {}
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.strip().strip('"\'')
    return env

root_env = load_env('.env')
db_url = root_env.get('DATABASE_URL').replace('postgresql+asyncpg://', 'postgresql://')

conn = psycopg2.connect(db_url)
cur = conn.cursor()

for tbl in ['workflow_instances', 'escalations', 'a2a_requests']:
    cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{tbl}';")
    cols = [r[0] for r in cur.fetchall()]
    print(f"Table '{tbl}' columns:", cols)

conn.close()

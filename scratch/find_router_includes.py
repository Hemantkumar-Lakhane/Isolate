with open('api/main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for idx, line in enumerate(lines, 1):
    if 'include_router' in line or 'connections' in line:
        print(f"Line {idx}: {line.strip()}")

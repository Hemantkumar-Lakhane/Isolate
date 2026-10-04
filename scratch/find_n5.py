with open('api/routers/meeting_intelligence.py', encoding='utf-8') as f:
    for idx, line in enumerate(f, 1):
        if 'n5' in line:
            print(f"{idx}: {line.strip()}")

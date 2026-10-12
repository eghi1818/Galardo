import json
ws = json.load(open('/tmp/galardo_workers.json'))
busy = [w for w in ws if w.get('status') == 'RUNNING']
print(f"{len(ws)} workers terdaftar | {len(busy)} RUNNING | {len(ws)-len(busy)} IDLE")
for w in ws:
    print(f"  {w['id']:16} {w.get('status',''):8} job={w.get('current_job_id') or '-'}")

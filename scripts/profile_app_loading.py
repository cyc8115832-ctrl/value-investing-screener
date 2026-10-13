"""量測App實際路由查詢與回應；只使用隔離DB，不升級正式庫。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from time import perf_counter

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--label',required=True)
args=parser.parse_args()
folder=ROOT/'data/收工備份/主程式載入驗證-20261013'
os.environ.update(DATABASE_URL='sqlite:///'+(folder/'isolated.db').as_posix(),DEMO_MODE='false',
                  ENABLE_SCHEDULER='false',ALLOW_LINE_SEND='false',LINE_CHANNEL_ACCESS_TOKEN='',LINE_CHANNEL_SECRET='')
from sqlalchemy import event
from src.database.session import engine,SessionLocal
from src.web.api.verified_routes import verified_radar,verified_screener,verified_stock,verified_history
count=0


def query(*unused):
    global count
    count+=1


event.listen(engine,'before_cursor_execute',query)
results={}
for name,call in [('radar',lambda db:verified_radar(db)),
                  ('screener',lambda db:verified_screener(db=db)),
                  ('stock-2330',lambda db:verified_stock('2330',db=db)),
                  ('history-2330',lambda db:verified_history('2330',db=db))]:
    count=0;start=perf_counter()
    with SessionLocal() as db:body=call(db)
    elapsed=perf_counter()-start
    encoded=json.dumps(body,ensure_ascii=False,sort_keys=True,allow_nan=False).encode()
    (folder/(args.label+'-'+name+'.json')).write_bytes(encoded)
    results[name]={'seconds':round(elapsed,3),'sql_queries':count,'payload_sha256':hashlib.sha256(encoded).hexdigest()}
    print(json.dumps({name:results[name]},ensure_ascii=False),flush=True)
engine.dispose()
report=ROOT/'reports/2026-10-13'
(report/('主程式載入量測-'+args.label+'.json')).write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')

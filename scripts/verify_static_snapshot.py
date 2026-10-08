"""唯讀核對正式API與已匯出Pages快照，不發布網站或匯出私人資料。"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import argparse
import json
from datetime import datetime,timezone
from urllib.parse import quote
from fastapi.testclient import TestClient
from config.settings import BASE_DIR,SETTINGS
from src.database.session import SessionLocal
from src.database.schema import StockMaster
from src.web.app import app
from src.services.market_evidence import taiwan_today


def private_keys(value,path=''):
    """只回報禁止欄位的路徑，不輸出可能的私人值。"""
    forbidden={'user_id','line_user_id','access_token','refresh_token','research_notes','watchlist','line_binding'}
    result=[]
    if isinstance(value,dict):
        for key,item in value.items():
            child=f'{path}/{key}'
            if key in forbidden:
                result.append(child)
            result.extend(private_keys(item,child))
    elif isinstance(value,list):
        for index,item in enumerate(value):
            result.extend(private_keys(item,f'{path}/{index}'))
    return result


def verify_assets(directory):
    """核對實際匯出的程式及版本網址，補足資料API比對之外的快取邊界。"""
    directory=Path(directory)
    manifest=json.loads((directory/'snapshot-manifest.json').read_text(encoding='utf-8'))
    version=quote(manifest['generated_at'],safe='')
    html=(directory/'index.html').read_text(encoding='utf-8')
    failures=[]
    for asset in ('static-adapter.js','value-ui.js','value-ui.css'):
        if (directory/asset).read_bytes()!=(BASE_DIR/'src/web/static'/asset).read_bytes():
            failures.append({'check':'靜態程式與來源不一致','asset':asset})
        if './'+asset+'?snapshot='+version+'"' not in html:
            failures.append({'check':'程式資源缺快照版本識別','asset':asset})
    if 'value-investing-evidence-v2-'+manifest['generated_at'] not in (directory/'sw.js').read_text(encoding='utf-8'):
        failures.append({'check':'離線快取版本不一致'})
    return {'generated_at':manifest['generated_at'],'checks_passed':not failures,'failures':failures}


def verify_static_snapshot(directory=BASE_DIR/'docs'):
    if SETTINGS.DEMO_MODE:
        raise RuntimeError('正式快照查核不可使用示範模式')
    directory=Path(directory)
    manifest=json.loads((directory/'snapshot-manifest.json').read_text(encoding='utf-8'))
    with SessionLocal() as db:
        tickers=sorted(s.ticker for s in db.query(StockMaster).all())
    failures=[];checked=0;history_points=0;private_paths=[]
    if manifest.get('tickers')!=tickers or manifest.get('mode')!='verified' or manifest.get('private_data_exported') is not False:
        failures.append({'check':'快照清單／正式模式／私人資料旗標'})
    global_data=json.loads((directory/'data/global.json').read_text(encoding='utf-8'))
    allowed={'/api/radar','/api/screener','/api/evidence/status','/api/data-quality/report'}
    if set(global_data['routes'])!=allowed:
        failures.append({'check':'全域匯出路徑不在明確公開清單'})
    with TestClient(app) as client:
        for endpoint,saved in global_data['routes'].items():
            if endpoint not in allowed:
                continue
            response=client.get(endpoint);response.raise_for_status()
            if response.json()!=saved:
                failures.append({'check':'全域API與靜態不一致','endpoint':endpoint})
            checked+=1
        private_paths.extend(private_keys(global_data,'global'))
        for index,ticker in enumerate(tickers,1):
            saved=json.loads((directory/'data'/f'stock-{ticker}.json').read_text(encoding='utf-8'))
            private_paths.extend(private_keys(saved,ticker))
            for metric in ('auto','pe','pb','ps'):
                stock_response=client.get(f'/api/stocks/{ticker}',params={'metric':metric,'scenario':'base'})
                history_response=client.get(f'/api/evidence/stocks/{ticker}/history',params={'metric':metric,'years':3})
                stock_response.raise_for_status();history_response.raise_for_status()
                if saved[metric]!=stock_response.json():
                    failures.append({'check':'個股API與靜態不一致','ticker':ticker,'metric':metric})
                if saved['history'][metric]!=history_response.json():
                    failures.append({'check':'歷史API與靜態不一致','ticker':ticker,'metric':metric})
                checked+=2;history_points+=len(saved['history'][metric]['rows'])
            if index%10==0:
                print(json.dumps({'已核對股票':index,'總股票':len(tickers),'失敗':len(failures)},ensure_ascii=False),flush=True)
    if private_paths:
        failures.append({'check':'快照含禁止私人欄位','paths':private_paths})
    asset_checks=verify_assets(directory)
    failures.extend(asset_checks['failures'])
    return {'verified_at':datetime.now(timezone.utc).isoformat(),'generated_at':manifest.get('generated_at'),
            'stocks':len(tickers),'endpoint_comparisons':checked,'history_points_compared':history_points,
            'private_field_paths':private_paths,'asset_checks':asset_checks,'failures':failures,'checks_passed':not failures,
            'boundary':'只驗證本機快照與正式API一致及明確私人欄位隔離，不代表雲端發布、實機或投資策略驗收。'}


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=BASE_DIR/'docs')
    parser.add_argument('--output',type=Path,default=BASE_DIR/'reports'/taiwan_today().isoformat()/'靜態快照查核.json')
    args=parser.parse_args()
    result=verify_static_snapshot(args.directory)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'報告':str(args.output),'股票':result['stocks'],'比對端點':result['endpoint_comparisons'],'失敗':len(result['failures'])},ensure_ascii=False))
    sys.exit(0 if result['checks_passed'] else 1)

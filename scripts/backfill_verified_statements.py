"""歷史損益與資產負債全批預檢；正式匯入先備份，原上傳時間不回填可得日。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import argparse
import hashlib
import json
from datetime import datetime, timezone, timedelta
from src.data.historical_statements import normalize_statement
from src.data.historical_cash_flow import normalize_cash_flow
from scripts.capture_statement_books import IndexParser
from scripts.backfill_verified_cash_flow import run_batch


def checked_file(folder, item):
    path=(folder/item['path']).resolve()
    if not path.is_relative_to(folder): raise ValueError('來源路徑超出批次目錄')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=item['sha256']: raise ValueError('來源hash不符：'+path.name)
    return raw


def attach_book(record, book, folder):
    metadata=json.loads(checked_file(folder,book['metadata']))
    index=checked_file(folder,book['index']); pdf=checked_file(folder,book['pdf'])
    if metadata['ticker']!=record['ticker'] or metadata['period']!=record['period']:
        raise ValueError('電子書公司／季度不符')
    if (hashlib.sha256(index).hexdigest()!=metadata['index_sha256']
        or hashlib.sha256(pdf).hexdigest()!=metadata['pdf_sha256']
        or not pdf.startswith(b'%PDF-') or len(pdf)!=metadata['bytes']
        or Path(book['pdf']['path']).name!=metadata['filename']):
        raise ValueError('電子書原檔或目錄與版本紀錄不符')
    parser=IndexParser();parser.feed(index.decode('big5'))
    matches=[r for r in parser.rows if r==metadata['raw_index_row']]
    if len(matches)!=1 or len(matches[0])!=11 or matches[0][5]!='IFRSs合併財報':
        raise ValueError('電子書索引列未匹配')
    year,quarter=int(record['period'][:4]),int(record['period'][-1])
    if matches[0][0]!=record['ticker'] or matches[0][1]!=f"{year-1911} 年 {('第一季','第二季','第三季','第四季')[quarter-1]}":
        raise ValueError('電子書索引期間／公司未匹配')
    if (matches[0][7]!=metadata['filename'] or matches[0][9]!=metadata['uploaded_at_roc']
        or matches[0][10]!=metadata['latest_correction_marker'] or int(matches[0][8].replace(',',''))!=len(pdf)
        or metadata['filename']!=f"{year}0{quarter}_{record['ticker']}_AI1.pdf"):
        raise ValueError('電子書索引上傳及更正欄不符')
    roc=metadata['uploaded_at_roc']; uploaded=datetime.strptime(str(int(roc[:3])+1911)+roc[3:],'%Y/%m/%d %H:%M:%S').replace(tzinfo=timezone(timedelta(hours=8)))
    captured=datetime.fromisoformat(metadata['fetched_at'].replace('Z','+00:00'))
    import calendar
    end=datetime(year,quarter*3,calendar.monthrange(year,quarter*3)[1],tzinfo=uploaded.tzinfo)
    if captured.tzinfo is None or captured>datetime.now(timezone.utc) or uploaded>captured or uploaded<end:
        raise ValueError('電子書時間未核對')
    observed=max(captured,datetime.fromisoformat(record['observed_at']))
    day=observed.astimezone(timezone(timedelta(hours=8))).date().isoformat()
    record['observed_at']=observed.isoformat();record['available_date']=day
    if 'standalone_eps_available_date' in record['payload']:record['payload']['standalone_eps_available_date']=day
    record['payload']['statement_book']={
        'filename':metadata['filename'],'pdf_sha256':metadata['pdf_sha256'],
        'index_sha256':metadata['index_sha256'],'index_url':metadata['index_url'],
        'uploaded_at':uploaded.isoformat(),'latest_correction_marker':metadata['latest_correction_marker'],
        'captured_at':captured.isoformat(),'original_version_verified':False,
        'boundary':'目前電子書索引及檔案已匹配；最早公告與歷次更正鏈未核實。'}


def prepare_batch(manifest_path):
    path=Path(manifest_path).resolve();folder=path.parent
    manifest=json.loads(path.read_text(encoding='utf-8'))
    expected={tuple(x) for x in manifest['expected']}
    if not expected or len(expected)!=len(manifest['expected']) or any(len(k)!=3 for k in expected):
        raise ValueError('批次目標空白、重複或鍵不完整')
    records=[];files=[];keys=set()
    for item in manifest['files']:
        raw=checked_file(folder,item);source=json.loads(raw)
        record=(normalize_cash_flow if source['statement']=='合併現金流量表' else normalize_statement)(source)
        key=(record['dataset'],record['ticker'],record['period'])
        if key in keys or key not in expected:raise ValueError('批次重複或清單外報表')
        keys.add(key);record['payload']['source_capture_sha256']=item['sha256']
        attach_book(record,item['book'],folder)
        records.append(record);files.append(item)
    if keys!=expected:raise ValueError('批次缺少指定公司／季度／報表')
    return records,files


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('manifest',type=Path);parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    run_batch(args.manifest,args.apply,prepare=prepare_batch,prefix='歷史三表',
              boundary='本期及比較期金額勾稽，EPS只用官方直接單季欄；電子書上傳時間不代表最早可得日，原公告版本及策略仍未驗收。')

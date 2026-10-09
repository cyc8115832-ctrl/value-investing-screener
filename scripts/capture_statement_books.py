"""沿官方電子書目錄與公開下載介面保存原檔；不猜測PDF網址，不繞過流量防護。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin
import requests

BASE = 'https://doc.twse.com.tw'
ENDPOINT = BASE + '/server-java/t57sb01'


class IndexParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.links, self.inputs = [], [], {}
        self.row = self.cell = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'tr': self.row = []
        if tag in ('td', 'th') and self.row is not None: self.cell = ''
        if tag == 'a': self.links.append(attrs.get('href', ''))
        if tag == 'input' and attrs.get('type') == 'hidden':
            self.inputs[attrs.get('name')] = attrs.get('value', '')

    def handle_data(self, data):
        if self.cell is not None: self.cell += data

    def handle_endtag(self, tag):
        if tag in ('td','th') and self.cell is not None:
            self.row.append(self.cell.strip()); self.cell = None
        if tag == 'tr' and self.row is not None:
            self.rows.append(self.row); self.row = None


def checked(response):
    if response.status_code in (403,428,429):
        raise RuntimeError('官方流量防護，立即停止本批')
    response.raise_for_status()
    if 'text/html' in response.headers.get('Content-Type', ''):
        text = response.content.decode('big5', errors='replace')
        if any(x in text for x in ('查詢過於頻繁','驗證碼','存取遭拒')):
            raise RuntimeError('官方查詢防護，立即停止本批')
    return response


def capture_book(ticker, period, folder):
    if not re.fullmatch(r'\d{4}', ticker) or not re.fullmatch(r'20\d{2}-Q[1-4]', period):
        raise ValueError('公司或季度格式不符')
    metadata_path = folder / f'電子書版本-{ticker}-{period}.json'
    if metadata_path.exists():
        raise ValueError('已保存此版本；重新擷取須指定新目錄，避免覆寫觀察時間及原索引')
    captures = {}
    year, quarter = int(period[:4]), int(period[-1])
    url = f'{ENDPOINT}?step=1&colorchg=1&co_id={ticker}&year={year-1911}&mtype=A'
    response = checked(requests.get(url, timeout=25))
    parser = IndexParser(); parser.feed(response.content.decode('big5'))
    post = None
    # 金控的正常母公司選擇表單；只重送頁面實際列出的公開欄位。
    if parser.inputs.get('check2858') == 'Y':
        if parser.inputs.get('co_id') != ticker or parser.inputs.get('year') != str(year-1911):
            raise ValueError('金控選擇表單公司／年度不符')
        captures[folder / f'電子書公司選擇-{ticker}-{period}.html'] = response.content
        post = parser.inputs
        response = checked(requests.post(ENDPOINT, data=post, timeout=25))
        parser = IndexParser(); parser.feed(response.content.decode('big5'))
    captures[folder / f'電子書索引-{ticker}-{period}.html'] = response.content
    quarter_text = ('第一季','第二季','第三季','第四季')[quarter-1]
    rows = [r for r in parser.rows if len(r)==11 and r[0]==ticker
            and r[1]==f'{year-1911} 年 {quarter_text}' and r[5]=='IFRSs合併財報']
    if len(rows) != 1: raise ValueError('原檔索引缺少或重複，不能任意選取')
    row = rows[0]; filename = row[7]
    if not re.fullmatch(fr'{year}0{quarter}_{ticker}_AI1\.pdf', filename):
        raise ValueError('電子書檔名／報表類別不符')
    if not any(filename in link for link in parser.links): raise ValueError('缺少索引下載連結')
    download_response = checked(requests.post(ENDPOINT, data={'colorchg':'1','step':'9','kind':'A',
                                  'co_id':ticker,'filename':filename,'DEBUG':''}, timeout=25))
    captures[folder / f'電子書下載回應-{ticker}-{period}.html'] = download_response.content
    links = re.findall(r"href=['\"]([^'\"]+)['\"]", download_response.content.decode('big5'))
    links = [x for x in links if x.startswith('/pdf/') and x.endswith('.pdf')]
    if len(links) != 1: raise ValueError('官方回應沒有唯一PDF連結')
    download_url = urljoin(BASE, links[0])
    pdf = checked(requests.get(download_url, timeout=40))
    if not pdf.content.startswith(b'%PDF-') or len(pdf.content)!=int(row[8].replace(',','')):
        raise ValueError('PDF格式或原始位元組大小與索引不符')
    path = folder / filename
    if path.exists() and path.read_bytes()!=pdf.content:
        raise ValueError('已保存同名檔內容改變，須先核對更正版本，不覆寫原檔')
    captures[path] = pdf.content
    record = {'ticker':ticker,'period':period,'index_url':url,'index_post':post,'download_url':download_url,
              'filename':filename,'bytes':len(pdf.content),'pdf_sha256':hashlib.sha256(pdf.content).hexdigest(),
              'index_sha256':hashlib.sha256(response.content).hexdigest(),'uploaded_at_roc':row[9],
              'latest_correction_marker':row[10],'fetched_at':datetime.now(timezone.utc).isoformat(),
              'raw_index_row':row,'boundary':'上傳索引與目前電子檔；最早公告及歷次更正鏈未核實。'}
    captures[metadata_path] = json.dumps(record,ensure_ascii=False,indent=2).encode('utf-8')
    # 原索引、回應與原PDF全驗完才保存；任何既有同名差異先停止整組。
    for destination, content in captures.items():
        if destination.exists() and destination.read_bytes()!=content:
            raise ValueError('已保存同名來源內容不同，請用新目錄保留新觀察版本')
    for destination, content in captures.items():
        destination.write_bytes(content)
    return record


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tickers',nargs='+',required=True)
    p.add_argument('--period',required=True)
    p.add_argument('--output',type=Path,required=True)
    args = p.parse_args(); args.output.mkdir(parents=True,exist_ok=True)
    for ticker in args.tickers:
        r=capture_book(ticker,args.period,args.output)
        print(json.dumps({'ticker':ticker,'bytes':r['bytes'],'uploaded_at':r['uploaded_at_roc']},ensure_ascii=False),flush=True)
        time.sleep(3)

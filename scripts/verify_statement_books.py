"""重算已逐頁視讀的PDF核心科目與MOPS原表比對；不宣稱全部附註或更正鏈驗收。"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import hashlib,json
from datetime import datetime,timezone
from src.data.historical_statements import normalize_statement
from src.data.historical_cash_flow import normalize_cash_flow

# 人工依原檔完整頁面抄錄：累計EPS、官方單季EPS、母公司累計淨利、
# 本期資產／負債／權益、營業／投資／籌資現金、匯率、淨變動、期初／期末現金。
TRANSCRIBED={
 ('2330','2025-Q2'):[29.31,15.36,759837230,7006349549,2389717699,4616631850,1122637757,-518680733,-204366193,-162693534,236897297,2127627043,2364524340],
 ('2881','2025-Q2'):[3.49,0.49,51383519,11902138662,11071813653,830325009,36787898,-9876215,-13323269,-13060979,527435,625596925,626124360],
 ('5876','2025-Q2'):[1.61,0.65,7804075,2363102091,2111660072,251442019,-25621536,2709092,-1442328,-32146072,-56500844,369412598,312911754],
 ('2207','2025-Q2'):[14.83,7.10,8264307,504687597,398685281,106002316,27889642,-13498442,-9963522,-1118593,3309085,18968725,22277810],
 ('3105','2025-Q2'):[-0.96,-0.99,-405338,61131507,23799577,37331930,1743785,-234470,-1300839,-167896,40580,5419305,5459885],
 ('2330','2024-Q2'):[18.25,9.56,473330405,5982364014,2162215809,3820148205,813979318,-357414321,-161930200,39064801,333699598,1465427753,1799127351],
 ('2317','2025-Q2'):[6.23,3.19,86468612,4138942274,2507334694,1631607580,21875585,-39355799,39477225,-88585178,-66588167,937108093,870519926]}
PAGES={('2330','2025-Q2'):[4,5,6,8,9,10],('2330','2024-Q2'):[4,5,6,8,9,10],
       ('2881','2025-Q2'):[7,8,10,11],('5876','2025-Q2'):[8,9,10,11,13],
       ('2207','2025-Q2'):[6,7,8,9,11,12],('3105','2025-Q2'):[4,5,7],('2317','2025-Q2'):[6,7,8,9,11,12]}


def verify(folder):
    folder=Path(folder);results=[];failures=[]
    fields=['eps','standalone_eps','net_income','total_assets','total_liabilities','total_equity',
            'operating_cash_flow','investing_cash_flow','financing_cash_flow','fx_effect',
            'cash_change','opening_cash','closing_cash']
    for (ticker,period),expected in TRANSCRIBED.items():
        prefix=f'MOPS-{ticker}-{period.replace("-","")}-'
        income=normalize_statement(json.loads((folder/(prefix+'合併綜合損益表.json')).read_text(encoding='utf-8')))['payload']
        balance=normalize_statement(json.loads((folder/(prefix+'合併資產負債表.json')).read_text(encoding='utf-8')))['payload']
        cfpath=folder/(prefix+'合併現金流量表.json')
        if not cfpath.exists(): cfpath=folder.parent.parent/'2026-10-08/財報來源'/f'MOPS-{ticker}-2025Q2-現金流來源.json'
        cash=normalize_cash_flow(json.loads(cfpath.read_text(encoding='utf-8')))['payload']
        values={**income,**balance,**cash}
        # 三表共同中繼欄位不影響核對，但科目名稱需與資料層契約一致。
        rowchecks=[]
        for field,number in zip(fields,expected):
            actual=values.get(field);passed=actual==number
            rowchecks.append({'field':field,'pdf_transcribed':number,'mops_value':actual,'matched':passed})
            if not passed:failures.append({'ticker':ticker,'period':period,'field':field})
        pdf=folder/f'{period[:4]}02_{ticker}_AI1.pdf'
        results.append({'ticker':ticker,'period':period,'pdf':str(pdf.resolve()),
                        'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),
                        'pages_visually_read':PAGES[(ticker,period)],'checks':rowchecks})
    return {'generated_at':datetime.now(timezone.utc).isoformat(),'reports':results,
            'core_field_checks':sum(len(r['checks']) for r in results),'failures':failures,'checks_passed':not failures,
            'method':'原檔完整相關頁面視讀、人工核心科目抄錄，重新解析MOPS來源逐科目比對。金額仟元、EPS元。',
            'boundary':'只核對本期13個核心科目；比較期等式由解析器另核對，未逐一核對所有原檔科目、附註、最早公告或歷次更正鏈。'}


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    folder=Path(__file__).resolve().parents[1]/'reports/2026-10-09/財報來源'
    report=verify(folder);output=folder.parent/'電子書三表核心核對.json'
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'checks':report['core_field_checks'],'failures':report['failures']},ensure_ascii=False))
    sys.exit(0 if report['checks_passed'] else 1)

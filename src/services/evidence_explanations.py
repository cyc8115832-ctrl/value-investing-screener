"""依公司實際已核實資料解釋缺項；不增加投資判定或猜測公告日期。"""
import re


def recent_periods(financials):
    periods = [row['period'] for row in financials if re.fullmatch(r'\d{4}-Q[1-4]', row['period'])]
    if not periods:
        return []
    latest = max(int(p[:4]) * 4 + int(p[-1]) - 1 for p in periods)
    return [f'{n // 4}-Q{n % 4 + 1}' for n in range(latest - 3, latest + 1)]


def explain_stock_evidence(prices, revenues, financials, balances, cashflows, realized, valuation):
    """已有單季與累計來源分開列示；不將比較期冒充舊申報。"""
    targets = recent_periods(financials)
    gaps = []

    def add(label, status, reason, periods=None):
        gaps.append({'label': label, 'status': status, 'reason': reason, 'periods': periods or []})

    quarters = {row['period']: row for row in realized.get('quarters', [])}
    missing_eps = [period for period in targets if not quarters.get(period, {}).get('available')]
    if not realized.get('available'):
        add('連續四季單季 EPS', '驗證未通過' if financials else '資料未取得',
            realized['reason'], missing_eps)
    for label, rows in [('歷年資產負債表', balances), ('累計現金流報表', cashflows)]:
        present = {r['period'] for r in rows}
        missing = [p for p in targets if p not in present]
        if missing or not targets or not rows:
            add(label, '資料未取得', '已取得的本期資料保留；缺少連續期間，不以報表比較欄補成舊申報。', missing)
    add('官方流通／加權股數', '資料未取得', '缺已核實的有效股數與日期；股本金額不能直接換算股數。')
    add('公司體質完整判定', '功能未實作', '正式六面向判定尚未完成資料驗收；不把營收成長或低價位直接列為好公司。')
    add('股利可持續性判定', '功能未實作', '尚無完整官方股利、公司事件與可持續性查核。')
    available = []
    for label, rows in [('收盤行情', prices), ('月營收', revenues), ('累計損益', financials), ('資產負債表', balances), ('累計現金流', cashflows)]:
        if rows:
            latest = rows[-1]
            available.append({'label': label, 'period': latest['period'], 'period_count': len(rows),
                              'available_date': latest.get('available_date'), 'source_url': latest.get('source_url')})
    common = {'available_data': available, 'target_periods': targets,
              'period_basis': '以此公司最新已核實損益期別向前列四季，並非聲稱原始公告日已核實。'}
    company = {**common, 'status': 'insufficient', 'reason': '公司體質的連續財報、股數與完整判定證據仍不足。',
               'missing_items': gaps, 'impact': '不能列為已確認好公司，不能產生正式投資排名。',
               'next_step': '由電腦端取得官方原檔、核對期別與單位、驗證後分批回補；使用者可先研究已取得資料。'}
    value = {**common, 'status': 'available' if valuation.get('available') else 'insufficient',
             'reason': valuation.get('method') if valuation.get('available') else valuation.get('reason', '估值資料不足。'),
             'missing_items': [] if valuation.get('available') else [{'label': '同日有效倍數與歷史樣本', 'status': '資料不足',
                 'reason': valuation.get('reason', '尚無足夠可比較倍數'), 'periods': []}],
             'impact': '僅供歷史倍數研究，不能取代公司體質判定。' if valuation.get('available') else '暫無此指標價格區間。',
             'next_step': '可查看官方倍數與計算口徑；缺樣本時由系統補齊來源，不以模擬值填補。'}
    return {'company': company, 'valuation': value,
            'eps': {**common, 'status': 'available' if realized.get('available') else 'insufficient',
                    'reason': realized['reason'], 'missing_items': [g for g in gaps if g['label'] in ('連續四季單季 EPS', '官方流通／加權股數')],
                    'impact': '已實現與未來 EPS 分開；未來 EPS 預估尚未完成。', 'next_step': company['next_step']},
            'chips': {'status': 'insufficient', 'reason': '尚無已核實法人交易與持股來源。',
                      'missing_items': [{'label': '法人交易／持股', 'status': '資料未取得', 'reason': '需官方來源與資料日期。', 'periods': []}],
                      'available_data': [], 'impact': '不能顯示買超、持股變化或交叉訊號。',
                      'next_step': '由系統取得合法來源並核對；不是使用者需要自行補數字。'}}

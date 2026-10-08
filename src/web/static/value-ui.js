/* 正式介面：把價值證據、公司風險與價格位階放在使用者第一眼的位置。 */
(() => {
  if (document.body.dataset.evidenceMode !== 'verified') return;
  const state = { ticker: '2330', request: 0, metric: 'auto', stock: null, watch: [], years:3, page:'conclusion' };
  const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const money = value => value == null ? '待核實' : Number(value).toLocaleString('zh-TW', {maximumFractionDigits:2});
  const colorNames = {green:'✓ 價值支持', yellow:'△ 留意變化', red:'! 風險訊號', gray:'○ 證據不足'};
  const zones = {special:'特價', cheap:'便宜', fair:'合理', expensive:'昂貴', crazy:'過熱', unknown:'位階待核實'};
  const pages = [['conclusion','結論'],['fundamentals','基本面'],['river','價位'],['eps','EPS'],['chips','籌碼'],['ai','研究']];
  const paths = [
    '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><path d="M12 12l7-7"/>',
    '<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
    '<path d="M4 19V5m0 14h16M7 14l4-4 4 2 5-7"/>',
    '<path d="m12 3 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1z"/>',
    '<path d="M4 7h16M4 12h16M4 17h16"/><circle cx="8" cy="7" r="2"/><circle cx="16" cy="12" r="2"/><circle cx="10" cy="17" r="2"/>'
  ];
  document.querySelectorAll('.nav-tab-btn').forEach((button, index) => {
    const name = ['雷達','選股','個股','觀察','設定'][index];
    button.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true">${paths[index]}</svg><span class="nav-label">${name}</span>`;
    button.setAttribute('aria-label', name);
  });
  document.querySelector('.nav-tabs').setAttribute('aria-label', '主要功能');
  const controls = document.querySelector('.header-actions');
  controls.querySelector('#sandboxModeBtn').remove();
  const legend = () => `<div class="value-legend" aria-label="價值證據色彩說明">${Object.entries(colorNames).map(([color, label]) => `<span class="value-status tone-${color}">${label}</span>`).join('')}</div>`;
  const priceLegend = () => `<div class="value-legend" aria-label="價格位階色彩說明">${Object.entries(zones).map(([zone, label]) => `<span class="value-price price-${zone}">${label}</span>`).join('')}</div><p class="value-note">價格的綠色表示估值便宜；公司仍需通過獲利與現金流檢查。灰色表示尚無足夠資料。</p>`;
  const quote = stock => `<div class="value-quote" data-quote-ticker="${escape(stock.ticker)}"><span>現價參考・已核實收盤</span><br><strong>NT$ ${money(stock.quote?.close)}</strong><div class="value-note">${escape(stock.ticker)} ${escape(stock.company_name)} ｜ ${escape(stock.quote?.period || '無已核實行情')}<br>收盤價依資料日期，並非盤中即時價格${window.STATIC_BUILD_TIME ? '；靜態快照' : ''}</div></div>`;
  const source = data => data ? `<a class="value-source" href="${escape(data.source_url)}" target="_blank" rel="noopener">查看官方來源 ↗</a><p class="value-note">資料期：${escape(data.period)} ｜可用日期：${escape(data.available_date)}<br>擷取：${escape(data.fetched_at)}${data.availability_basis ? '<br>' + escape(data.availability_basis) : ''}</p>` : '';
  const factorCards = stock => `<div class="value-grid">${stock.value_factors.map(f => `<article class="value-card value-factor tone-${f.color}"><h3>${escape(f.label)}</h3><span class="value-status">${colorNames[f.color]}</span><div class="value-number">${escape(f.value)}</div><div class="value-muted">${escape(f.reason)}</div><div class="value-note">${escape(f.period || '')}</div></article>`).join('')}</div>`;
  const unavailable = reason => `<div class="value-empty"><span class="value-status tone-gray">○ 待核實</span><p>${escape(reason)}</p></div>`;
  async function api(path, options) {
    const response = await fetch('/api' + path, options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.reason || data.detail || '資料暫時無法取得');
    return data;
  }
  function activate(name) {
    document.querySelectorAll('.tab-content').forEach(panel => panel.classList.toggle('active', panel.id === 'tab-' + name));
    document.querySelectorAll('.nav-tab-btn').forEach(button => {
      const selected = button.getAttribute('onclick').includes("'" + name + "'");
      button.classList.toggle('active', selected);
      if (selected) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
    });
  }
  window.switchTab = name => {
    activate(name);
    if (name === 'radar') loadRadarData();
    if (name === 'screener') loadScreenerData();
    if (name === 'detail') loadStockDetail(state.ticker, state.metric);
    if (name === 'watchlist') loadWatchlistData();
    window.scrollTo({top:0});
  };
  window.viewStock = ticker => { state.page = 'conclusion'; activate('detail'); window.scrollTo({top:0}); return loadStockDetail(ticker, state.metric); };
  window.loadRadarData = async () => {
    const panel = document.getElementById('tab-radar');
    panel.innerHTML = unavailable('正在核對資料來源…');
    try {
      const data = await api('/radar');
      panel.innerHTML = `<section class="value-hero"><p class="value-kicker">VALUE FIRST · 價值優先</p><h1 class="value-heading">先選好公司，再等好價格</h1><p class="value-muted">${escape(data.message)}</p><p class="value-note">最新已核實行情 ${escape(data.quote_date || '待核實')} ｜ 既有研究股池 ${data.quality.stocks} 檔（ETF 成分待重新查核）</p></section>${legend()}<div class="value-grid"><article class="value-card"><h3>✓ 成長線索</h3><div class="value-number tone-green">${data.growth_signals} 檔</div><p class="value-note">官方營收有正成長；仍需獲利、現金流與持續性證據。</p><button class="btn" data-action="growth">找成長線索</button></article><article class="value-card"><h3>△ 困難訊號</h3><div class="value-number tone-yellow">${data.risk_signals} 檔</div><p class="value-note">營收衰退或累計虧損，優先檢查是否為景氣循環或持續退化。</p><button class="btn" data-action="risk">檢查風險公司</button></article><article class="value-card"><h3>○ 今日價值精選</h3><div class="value-number tone-gray">等待證據</div><p class="value-note">完整體質與價位資料不足，暫不產生買進排名。</p><button class="btn" data-action="stock" data-ticker="2330">研究台積電</button></article></div><section class="value-card"><h2 class="value-heading">價格是入口，價值是理由</h2><p class="value-muted">關注四件事：獲利能否延續、現金流是否跟上、財務能否承受逆風，以及現價有沒有安全邊際。</p>${priceLegend()}</section>`;
    } catch (error) { panel.innerHTML = unavailable(error.message); }
  };
  document.getElementById('tab-screener').innerHTML = `<h1 class="value-heading">股票總表</h1><p class="value-note">價值因素 × 價格位階；成長不等於便宜。</p><div id="valueOverview"></div>${legend()}<div class="value-toolbar"><input id="valueSearch" aria-label="股票代號或名稱" placeholder="搜尋代號或公司名稱"><select id="valueFilter" aria-label="價值證據篩選"><option value="all">全部公司</option><option value="growth">✓ 有成長線索</option><option value="risk">△ 有困難訊號</option><option value="unknown">○ 體質待核實</option></select><button class="btn" data-action="search">篩選</button></div><div id="valueResults"></div>`;
  function overviewRow(stock) {
    const growth = stock.value_factors.find(f => f.label === '月營收成長');
    return `<div class="stock-overview-row"><button data-action="stock" data-ticker="${escape(stock.ticker)}"><b>${escape(stock.company_name)}</b><div class="value-note">${escape(stock.ticker)} ｜ ${escape(stock.industry)}</div></button><div><strong>NT$ ${money(stock.quote?.close)}</strong><div class="value-note">${escape(stock.quote?.period || '價格待核實')}</div></div><div class="overview-factors"><span class="tone-${growth?.color || 'gray'}">${growth ? colorNames[growth.color] + '・營收 ' + escape(growth.value) : '○ 營收待核實'}</span><div class="factor-strip" aria-label="價值因素燈號">${stock.value_factors.map(f => `<span class="tone-${f.color}" title="${escape(f.label + '：' + f.reason)}"></span>`).join('')}</div><div class="value-note">累計 EPS ${money(stock.income_ytd?.eps)}${stock.income_ytd ? '（' + escape(stock.income_ytd.period) + '）' : ''}</div></div><div class="overview-multiples">P/E ${money(stock.quote?.pe)}<br>P/B ${money(stock.quote?.pb)}</div><div class="overview-status"><span class="value-price price-${stock.current_zone}">${zones[stock.current_zone]}</span><div class="value-note tone-${stock.risk_color}">${stock.risks.length ? '△ 困難訊號' : '○ 體質待核實'}</div></div></div>`;
  }
  function stockCard(stock, extra = '') {
    const green = stock.value_factors.filter(f => f.color === 'green');
    const red = stock.value_factors.filter(f => f.color === 'red');
    return `<article class="value-card"><div class="value-stock-row"><div><div class="value-stock-title">${escape(stock.ticker)} ${escape(stock.company_name)}</div><div class="value-note">${escape(stock.industry)}</div></div><button class="btn" data-action="stock" data-ticker="${escape(stock.ticker)}">查看個股</button></div>${quote(stock)}<div class="value-legend"><span class="value-price price-${stock.current_zone}">${zones[stock.current_zone]}</span><span class="value-status tone-${stock.risk_color}">${escape(stock.risks.length ? '△ 需檢查困難原因' : stock.company_label)}</span></div>${green.map(f => `<p class="tone-green">✓ ${escape(f.label)} ${escape(f.value)}</p>`).join('')}${red.map(f => `<p class="tone-red">! ${escape(f.label)} ${escape(f.value)}</p>`).join('')}${extra}</article>`;
  }
  window.loadScreenerData = async () => {
    const results = document.getElementById('valueResults');
    results.innerHTML = unavailable('正在載入官方證據…');
    try {
      const list = await api('/screener?search=' + encodeURIComponent(document.getElementById('valueSearch').value));
      const filter = document.getElementById('valueFilter').value;
      const selected = list.filter(stock => filter === 'all' || filter === 'unknown' && stock.company_status === 'insufficient' || filter === 'growth' && stock.value_factors.some(f => f.color === 'green') || filter === 'risk' && stock.risks.length);
      document.getElementById('valueOverview').innerHTML = `<div class="value-summary"><div><span class="value-note">已核實收盤</span><strong>${list.filter(s => s.quote).length} 檔</strong></div><div><span class="value-note">成長線索</span><strong class="tone-green">${list.filter(s => s.value_factors.some(f => f.color === 'green')).length} 檔</strong></div><div><span class="value-note">困難訊號</span><strong class="tone-yellow">${list.filter(s => s.risks.length).length} 檔</strong></div><div><span class="value-note">估值待核實</span><strong class="tone-gray">${list.filter(s => !s.valuation.available).length} 檔</strong></div></div><p class="value-note">摘要依搜尋結果；成長與困難可同時存在。</p>`;
      results.innerHTML = `<p class="value-note">符合 ${selected.length} 檔・點公司名稱開啟研究</p>` + (selected.length ? `<div class="value-card stock-overview"><div class="stock-overview-row stock-overview-head"><span>公司／代號</span><span>收盤／日期</span><span>價值因素</span><span>官方倍數</span><span>公司／價位</span></div>${selected.map(overviewRow).join('')}</div>` : unavailable('沒有符合條件的公司。'));
    } catch (error) { results.innerHTML = unavailable(error.message); }
  };
  document.getElementById('tab-detail').innerHTML = '<div id="valueDetail"></div>';
  function historyTable(history) {
    if (!history.rows.length) return unavailable('尚無已核實歷史行情。');
    return `<h3>歷史收盤與價值指標</h3><p class="value-note">共 ${history.rows.length} 筆真實行情；不足的期間不以種子補足。可左右滑動比較。</p><div class="history-wrap" tabindex="0" role="region" aria-label="歷史收盤與價值指標"><table class="value-history"><thead><tr><th scope="col">日期</th><th scope="col">收盤（元）</th><th scope="col">P/E</th><th scope="col">P/B</th><th scope="col">當時 TTM EPS</th></tr></thead><tbody>${[...history.rows].reverse().map(row=>`<tr><td>${escape(row.date)}</td><td>${money(row.close)}</td><td>${row.pe == null ? '—' : money(row.pe)}</td><td>${row.pb == null ? '—' : money(row.pb)}</td><td>${row.eps_ttm == null ? '—' : money(row.eps_ttm)}</td></tr>`).join('')}</tbody></table></div><p class="value-note">— 表示當時證據不足。ROE／PEG 未有完整歷史來源，不把今天的數字倒填以前。</p>`;
  }
  function riverChart(history) {
    const rows = history.rows;
    if (!rows.length) return unavailable('沒有已核實行情可以畫時間圖。');
    const width=480, height=320, left=64, right=406, top=25, bottom=265;
    const values=rows.flatMap(row=>[row.close,...(row.bands || [])]);
    const minimum=Math.min(...values), maximum=Math.max(...values);
    const pad=Math.max((maximum-minimum)*.15, maximum*.03,1);
    const low=Math.max(0,minimum-pad), high=maximum+pad;
    const first=Date.parse(rows[0].date), last=Date.parse(rows.at(-1).date);
    const x=row=>first === last ? (left+right)/2 : left+(Date.parse(row.date)-first)/(last-first)*(right-left);
    const y=value=>bottom-(value-low)/(high-low)*(bottom-top);
    const points=rows.map(row=>`${x(row)},${y(row.close)}`).join(' ');
    const groups=[]; let group=[];
    for (const row of rows) {
      if (row.bands) group.push(row); else if (group.length) { groups.push(group); group=[]; }
    }
    if (group.length) groups.push(group);
    const bands=groups.map(group=>{
      if (group.length<2) return '';
      const fill=(upper,lower,color)=>`<polygon points="${group.map(row=>`${x(row)},${y(upper(row))}`).join(' ')} ${[...group].reverse().map(row=>`${x(row)},${y(lower(row))}`).join(' ')}" fill="${color}" opacity=".28"/>`;
      return fill(row=>row.bands[0],()=>low,'#86EFAC')+fill(row=>row.bands[1],row=>row.bands[0],'#BBF7D0')+fill(row=>row.bands[4],row=>row.bands[1],'#7DD3FC')+fill(row=>row.bands[5],row=>row.bands[4],'#FDE68A')+fill(()=>high,row=>row.bands[5],'#FDA4AF')+Array.from({length:6},(_,index)=>`<polyline points="${group.map(row=>`${x(row)},${y(row.bands[index])}`).join(' ')}" stroke="#CBD5E1" opacity=".6" fill="none"/>`).join('');
    }).join('');
    const current=rows.at(-1);
    return `<figure style="margin:16px 0"><svg class="value-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escape(history.ticker)} 按日期的收盤與估值河流圖"><title>依官方各日歷史資料重建；不是當時已留存預估</title>${Array.from({length:4},(_,i)=>{const value=low+(high-low)*i/3; return `<line x1="${left}" x2="${right}" y1="${y(value)}" y2="${y(value)}" stroke="#2D3748"/><text x="${left-7}" y="${y(value)+6}" text-anchor="end" fill="#CBD5E1" font-size="17">${Math.round(value)}</text>`;}).join('')}${bands}${rows.length>1 ? `<polyline points="${points}" fill="none" stroke="#FDBA74" stroke-width="2.5"/>` : ''}<circle cx="${x(current)}" cy="${y(current.close)}" r="4" fill="#FDBA74"/><text x="${Math.min(right-75,x(current)+10)}" y="${Math.max(top+20,y(current.close)-10)}" fill="#FDBA74" font-size="19">${money(current.close)}</text><text x="${left}" y="${bottom+30}" fill="#CBD5E1" font-size="17">${escape(rows[0].date)}</text>${rows.length>1 ? `<text x="${right}" y="${bottom+30}" fill="#CBD5E1" text-anchor="end" font-size="17">${escape(current.date)}</text>` : ''}</svg><figcaption class="value-note">橘線／圓點：已核實收盤。${rows.length===1 ? '目前只有一筆，僅繪點，未生成歷史線。' : ''}<br>具估值資料 ${history.river_points}/${rows.length} 日；各日需 ${history.required_observations} 筆有效樣本。${escape(history.method)}</figcaption></figure>${history.river_points ? '' : unavailable('目前沒有足夠已核實歷史倍數可形成河流色帶；取得資料後才顯示隨時間變動的六條線。')}`;
  }
  window.loadStockDetail = async (ticker, metric = 'auto') => {
    state.ticker = ticker; state.metric = metric;
    const request = ++state.request;
    const detail = document.getElementById('valueDetail');
    detail.innerHTML = `<h1 class="value-heading">${escape(ticker)} 個股研究</h1>${unavailable('正在取得已核實價格與證據…')}`;
    try {
      const [stock,history] = await Promise.all([api(`/stocks/${encodeURIComponent(ticker)}?metric=${encodeURIComponent(metric)}&scenario=base`),api(`/evidence/stocks/${encodeURIComponent(ticker)}/history?metric=${encodeURIComponent(metric)}&years=${state.years}`)]);
      if (request !== state.request) return;
      state.stock = stock;
      const value = stock.valuation;
      const basics = factorCards(stock) + source(stock.revenue) + source(stock.income_ytd);
      const periodControl = `<div class="value-toolbar"><label for="valueYears">時間範圍</label><select id="valueYears"><option value="1">近 1 年</option><option value="2">近 2 年</option><option value="3">近 3 年</option></select></div>`;
      const priceBody = `<h2 class="value-heading">現價與價值之間</h2>${priceLegend()}<div class="value-toolbar"><label for="valueMetric">估值指標</label><select id="valueMetric"><option value="auto">依公司類型</option><option value="pe">P/E 本益比</option><option value="pb">P/B 股價淨值比</option><option value="ps">P/S 股價營收比</option></select></div>${value.available ? `<div class="value-grid">${value.levels.map((level, index) => `<div class="value-card"><div class="value-note">P${index+1}</div><strong>NT$ ${money(level)}</strong></div>`).join('')}</div><p class="value-note">${escape(value.method)}<br>樣本 ${value.sample_count} 日；歷史平均倍數 ${value.center_multiple.toFixed(2)}。相對 P4 估值參考線的價格差距 ${value.margin_to_fair_pct}%（不等於保證報酬）。</p>` : unavailable(value.reason)}<div class="value-card"><h3>官方當日倍數</h3><p>P/E ${money(stock.quote?.pe)} 倍 ｜ P/B ${money(stock.quote?.pb)} 倍</p><p class="value-note">倍數本身不能證明便宜。循環股與金融股優先檢查 P/B；虧損時 P/E 不適用。</p></div>${source(stock.quote)}`;
      const epsBody = `<h2 class="value-heading">已實現獲利與未來分開看</h2>${stock.income_ytd ? `<div class="value-card"><h3>${escape(stock.income_ytd.period)} 年初至當季累計 EPS</h3><div class="value-number ${stock.income_ytd.eps < 0 ? 'tone-red' : 'tone-yellow'}">${money(stock.income_ytd.eps)} 元</div><p class="value-note">${escape(stock.income_ytd.basis)}。不能乘二當成年預估，也不能冒充單季 EPS。</p>${source(stock.income_ytd)}</div>` : unavailable('此公司的累計損益來源尚未完成查核。')}${unavailable('未來 EPS 需連續單季財報、同期營收與股數；目前不填入固定成長率。')}`;
      const conclusions = `<h2 class="value-heading">${escape(stock.conclusion)}</h2><div class="value-legend"><span class="value-status tone-${stock.risk_color}">${escape(stock.risks.length ? '△ 發現困難訊號' : stock.company_label)}</span><span class="value-price price-${stock.current_zone}">${zones[stock.current_zone]}</span></div>${stock.risks.map(risk => `<p class="tone-red">! ${escape(risk)}</p>`).join('')}${basics}`;
      const research = `<h2 class="value-heading">價值研究清單</h2><p class="value-muted">${escape(stock.research.reason)}</p><div class="value-card"><h3>還需要回答的問題</h3><ol><li>收入成長能否轉為可持續獲利？</li><li>營業現金流與自由現金流是否支撐盈餘？</li><li>負債、存貨及應收帳款有沒有增加壓力？</li><li>利潤是否來自一次性業外收益？</li><li>現價相對可持續獲利是否有安全邊際？</li></ol><p class="value-note">待補資料：${stock.missing.map(escape).join('、')}</p></div>${source(stock.revenue)}${source(stock.income_ytd)}`;
      const market = `<div class="quote-market"><div>開盤<strong>${money(stock.quote?.open)}</strong></div><div>最高<strong>${money(stock.quote?.high)}</strong></div><div>最低<strong>${money(stock.quote?.low)}</strong></div><div>成交股數<strong>${money(stock.quote?.volume)}</strong></div></div>`;
      const bodies = {conclusion:conclusions, fundamentals:'<h2 class="value-heading">歷史行情與價值因素</h2>' + market + historyTable(history) + basics, river:periodControl + riverChart(history) + priceBody, eps:epsBody, chips:'<h2 class="value-heading">籌碼是輔助訊號</h2>' + unavailable('尚未取得已核實法人交易與持股資料；不顯示固定買超或黃金交叉。') + '<p class="value-muted">先確認公司價值與價格，再用籌碼輔助判讀。</p>', ai:research};
      detail.innerHTML = `<h1 class="value-heading">${escape(stock.ticker)} ${escape(stock.company_name)}</h1><p class="value-note">${escape(stock.industry)} ｜ ${escape(stock.company_label)}</p><div class="value-sticky">${quote(stock)}</div><div class="value-toolbar"><button class="btn" data-action="watch-add">☆ 加入觀察</button><span id="valueSaveStatus" role="status"></span></div><div class="value-subtabs" role="tablist" aria-label="個股分析分頁">${pages.map(([id,label], i) => `<button role="tab" id="value-tab-${id}" aria-controls="dsub-${id}" aria-selected="${i === 0}" class="${i === 0 ? 'active' : ''}" data-action="subtab" data-page="${id}">${label}</button>`).join('')}</div>${pages.map(([id], i) => `<section id="dsub-${id}" role="tabpanel" aria-labelledby="value-tab-${id}" class="value-panel ${i === 0 ? 'active' : ''}">${quote(stock)}${bodies[id]}</section>`).join('')}`;
      document.getElementById('valueMetric').value = metric;
      document.getElementById('valueYears').value = String(state.years);
      switchDetailSubTab(state.page);
    } catch (error) {
      if (request === state.request) detail.innerHTML = unavailable(error.message);
    }
  };
  window.switchDetailSubTab = id => {
    state.page = id;
    pages.forEach(([page]) => {
      document.getElementById('dsub-' + page)?.classList.toggle('active', page === id);
      const button = document.getElementById('value-tab-' + page);
      button?.classList.toggle('active', page === id);
      button?.setAttribute('aria-selected', String(page === id));
    });
  };
  window.loadWatchlistData = async () => {
    const panel = document.getElementById('tab-watchlist');
    panel.innerHTML = '<h1 class="value-heading">我的價值觀察</h1>' + unavailable('正在載入觀察清單…');
    try {
      state.watch = await api('/evidence/watchlist');
      panel.innerHTML = `<h1 class="value-heading">我的價值觀察</h1><p class="value-note">${window.STATIC_BUILD_TIME ? '此裝置儲存；不會回寫伺服器。' : '分組與筆記儲存在本機服務資料庫。'}記下價值理由與仍需驗證的風險。</p><div class="value-stock-list">${state.watch.length ? state.watch.map((stock, index) => stockCard(stock, `<p class="value-note">分組：${escape(stock.group_name)}</p><label for="value-note-${index}">研究筆記</label><textarea id="value-note-${index}">${escape(stock.note)}</textarea><div class="value-toolbar"><button class="btn" data-action="note-save" data-index="${index}">儲存筆記</button><button class="btn" data-action="watch-delete" data-index="${index}">移出此組</button><span role="status" id="note-status-${index}"></span></div>`)).join('') : unavailable('尚無觀察公司。先從選股頁選一家公司，檢查價值因素後加入觀察。')}</div>`;
    } catch (error) { panel.innerHTML = unavailable(error.message); }
  };
  const settings = document.getElementById('tab-settings');
  settings.innerHTML = `<h1 class="value-heading">閱讀與資料設定</h1><div class="value-card" id="valueReading"><h3>字級與長輩友善模式</h3></div><div class="value-card"><h3>色彩怎麼看</h3>${legend()}${priceLegend()}<p class="value-muted">淺綠顯示已證實的成長線索；琥珀提醒衰退待觀察；珊瑚紅提示虧損或風險；灰色代表缺證據。各色皆搭配文字，不需只靠數字判讀。</p></div><div class="value-card"><h3>資料查核狀態</h3><div id="valueQuality">正在查核…</div><p class="value-note">完整財報、ETF 成分、美債及多數公司的歷史行情仍待核實。原始種子保留供查核，但不提供正式投資分析。</p><button class="btn" data-action="quality">重新查核</button></div><div class="value-card"><h3>分析功能資料需求</h3><p class="value-muted">EPS 預估、體質評分、河流圖、籌碼、部位配置與歷史回測需要完整來源。未達條件的項目顯示「待核實」，恢復前不使用舊模擬結果。</p><p class="value-note">${window.STATIC_BUILD_TIME ? '快照產生：' + escape(window.STATIC_BUILD_TIME) + '；不是即時更新。' : '正式模式不自動寫入模擬種子；背景排程預設關閉。'}</p><a href="https://www.sie.com.tw/Luckylong/article.do?id=A20240411748546VR1" target="_blank" rel="noopener">閱讀孫慶龍公開估值理念 ↗</a></div>`;
  document.getElementById('valueReading').appendChild(controls);
  async function quality() {
    try {
      const data = await api('/evidence/status');
      document.getElementById('valueQuality').innerHTML = `<p class="value-muted">${escape(data.reason)}</p><p>已核實：行情 ${data.verified_coverage.price}/${data.stocks}、月營收 ${data.verified_coverage.revenue}/${data.stocks}、累計損益 ${data.verified_coverage.income_ytd}/${data.stocks}</p><span class="value-status tone-gray">○ 投資判定資料尚未齊備</span>`;
    } catch (error) { document.getElementById('valueQuality').innerHTML = unavailable(error.message); }
  }
  document.addEventListener('click', async event => {
    const button = event.target.closest('[data-action]');
    if (!button) return;
    const action = button.dataset.action;
    if (action === 'stock') return viewStock(button.dataset.ticker);
    if (action === 'subtab') return switchDetailSubTab(button.dataset.page);
    if (action === 'search') return loadScreenerData();
    if (action === 'growth' || action === 'risk') {
      activate('screener'); document.getElementById('valueFilter').value = action;
      return loadScreenerData();
    }
    if (action === 'quality') return quality();
    if (['watch-add','note-save','watch-delete'].includes(action)) {
      button.disabled = true;
      let status;
      try {
        const stock = action === 'watch-add' ? state.stock : state.watch[Number(button.dataset.index)];
        status = document.getElementById(action === 'watch-add' ? 'valueSaveStatus' : 'note-status-' + button.dataset.index);
        if (action === 'watch-delete') {
          await api('/evidence/watchlist/' + stock.ticker + '?group_id=' + encodeURIComponent(stock.group_id), {method:'DELETE'});
          return loadWatchlistData();
        }
        const payload = action === 'watch-add' ? {} : {note:document.getElementById('value-note-' + button.dataset.index).value, group_id:stock.group_id, group_name:stock.group_name};
        await api('/evidence/watchlist/' + stock.ticker, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
        status.textContent = '✓ 已儲存';
      } catch (error) { if (status) status.textContent = error.message; }
      finally { button.disabled = false; }
    }
  });
  document.addEventListener('change', event => {
    if (event.target.id === 'valueMetric') loadStockDetail(state.ticker, event.target.value).then(() => switchDetailSubTab('river'));
    if (event.target.id === 'valueYears') { state.years = Number(event.target.value); loadStockDetail(state.ticker,state.metric); }
    if (event.target.id === 'valueFilter') loadScreenerData();
  });
  document.getElementById('valueSearch').addEventListener('keydown', event => { if (event.key === 'Enter') loadScreenerData(); });
  window.onload = () => { initAccessibilityPreferences(); loadRadarData(); quality(); };
})();

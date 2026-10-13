/* 正式介面：把價值證據、公司風險與價格位階放在使用者第一眼的位置。 */
(() => {
  if (document.body.dataset.evidenceMode !== 'verified') return;
  const state = { ticker: '2330', request: 0, screenerRequest:0, radarRequest:0, metric: 'auto', stock: null, watch: [], years:3, page:'conclusion', catalogue:null, manageOpen:false };
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
  const legend = () => `<h3>資料訊號顏色說明</h3><div class="value-legend value-help-legend">${Object.entries(colorNames).map(([color, label]) => `<span class="tone-${color}">● ${label}</span>`).join('')}</div><p class="value-note">這是說明圖例，不是操作按鈕。正向資料線索不等於整家公司已確認為好公司。</p>`;
  const priceLegend = () => `<h3>價格位階顏色說明</h3><div class="value-legend value-help-legend">${Object.entries(zones).map(([zone, label]) => `<span class="value-price price-${zone}">${label}</span>`).join('')}</div><p class="value-note">圖例僅供閱讀；價位篩選在選股頁。便宜是歷史倍數研究結果，仍需檢查公司體質。</p>`;
  const companyStates = {good:['已確認好公司','good'],watch:['持續觀察','watch'],deteriorating:['基本面退化','risk'],insufficient:['資料不足','unknown']};
  const companyKey = stock => Object.hasOwn(companyStates,stock.company_status) ? stock.company_status : 'insufficient';
  const companyLabel = stock => companyStates[companyKey(stock)][0];
  const companyBadge = stock => `<span class="company-badge company-${companyStates[companyKey(stock)][1]}">${escape(companyLabel(stock))}</span>`;
  const metricNames = {pe:'P/E 本益比',pb:'P/B 股價淨值比',ps:'P/S 股價營收比'};
  let pool;
  try { pool = window.ResearchPool.create(window.localStorage,'value-research-pool-v1:'+new URL('.',document.baseURI).pathname); }
  catch (_) { pool = window.ResearchPool.create({getItem(){throw new Error('儲存被停用');},setItem(){throw new Error('儲存被停用');}},'unavailable'); }
  function poolRows() { try { state.poolError=''; return pool.read(); } catch(error) {state.poolError=error.message; return [];} }
  const isVisible = (stock,rows) => pool.visible(stock.ticker,rows);
  async function catalogue() {
    if (!state.catalogue) state.catalogue=api('/screener').catch(error=>{state.catalogue=null;throw error;});
    return state.catalogue;
  }
  function explanation(details, title='查看資料缺項與原因') {
    if (!details) return '';
    return `<details class="value-explanation"><summary>${escape(title)}</summary><p><b>原因：</b>${escape(details.reason)}</p>${details.missing_items?.length ? `<h4>缺項與狀態</h4><ul>${details.missing_items.map(g=>`<li><span class="value-gap-status">${escape(g.status)}</span> ${escape(g.label)}${g.periods?.length?'：'+g.periods.map(escape).join('、'):''}<p class="value-note">${escape(g.reason)}</p></li>`).join('')}</ul>` : '<p>此研究指標的樣本條件已達成，仍不代表公司體質驗收完成。</p>'}${details.available_data?.length ? `<h4>已取得資料</h4><ul>${details.available_data.map(d=>`<li>${escape(d.label)}：${escape(d.period)}，共 ${Number(d.period_count)} 期${d.available_date?'；可用日期 '+escape(d.available_date):''}</li>`).join('')}</ul>` : '<p>尚無此項已核實資料。</p>'}<p><b>影響：</b>${escape(details.impact)}</p><p><b>下一步：</b>${escape(details.next_step)}</p>${details.period_basis?'<p class="value-note">'+escape(details.period_basis)+'</p>':''}</details>`;
  }
  const quote = stock => `<div class="value-quote" data-quote-ticker="${escape(stock.ticker)}"><span>現價參考・已核實收盤</span><br><strong>NT$ ${money(stock.quote?.close)}</strong><div class="value-note">${escape(stock.ticker)} ${escape(stock.company_name)} ｜ ${escape(stock.quote?.period || '無已核實行情')}<br>收盤價依資料日期，並非盤中即時價格${window.STATIC_BUILD_TIME ? '；靜態快照' : ''}</div></div>`;
  const source = data => data ? `<a class="value-source" href="${escape(data.source_url)}" target="_blank" rel="noopener">查看官方來源 ↗</a><p class="value-note">資料期：${escape(data.period)} ｜可用日期：${escape(data.available_date)}<br>擷取：${escape(data.fetched_at)}${data.availability_basis ? '<br>' + escape(data.availability_basis) : ''}</p>` : '';
  const factorCards = stock => {
    const available=stock.value_factors.filter(f=>f.color!=='gray');
    const pending=stock.value_factors.filter(f=>f.color==='gray');
    return `<div class="value-grid">${available.map(f=>`<article class="value-card value-factor tone-${f.color}"><h3>${escape(f.label)}</h3><span class="value-status">${colorNames[f.color]}</span><div class="value-number">${escape(f.value)}</div><div class="value-muted">${escape(f.reason)}</div><div class="value-note">${escape(f.period||'')}</div></article>`).join('')}</div>${pending.length?`<details class="value-explanation" data-pending-factors><summary>尚未完成的體質項目（${pending.length}項）</summary><ul>${pending.map(f=>`<li><b>${escape(f.label)}：待核實</b><p>${escape(f.reason)}</p></li>`).join('')}</ul></details>`:''}`;
  };
  const balanceCard = stock => stock.balance_sheet ? `<article class="value-card"><h3>${escape(stock.balance_sheet.period)} 資產負債快照</h3><p>資產總額：${money(stock.balance_sheet.total_assets)}<br>負債總額：${money(stock.balance_sheet.total_liabilities)}<br>權益總額：${money(stock.balance_sheet.total_equity)}</p><p class="value-note">金額依官方來源原值，未跨報表換算單位。這是季末存量；仍需歷年趨勢與現金流，才能判斷財務韌性。股本金額不當作流通股數。</p>${source(stock.balance_sheet)}</article>` : unavailable('最新資產負債表尚未核實。');
  const unavailable = (reason,details) => `<div class="value-empty"><span class="value-status tone-gray">○ 待核實</span><p>${escape(reason)}</p>${explanation(details)}</div>`;
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
  window.viewStock = ticker => { state.page = 'conclusion'; state.metric='auto'; activate('detail'); window.scrollTo({top:0}); return loadStockDetail(ticker, 'auto'); };
  window.loadRadarData = async () => {
    const request=++state.radarRequest;
    const panel = document.getElementById('tab-radar');
    panel.innerHTML = unavailable('正在核對資料來源…');
    try {
      let data,list;
      if (window.STATIC_BUILD_TIME) {
        [data,list] = await Promise.all([api('/radar'),catalogue()]);
      } else {
        const overview=api('/overview');
        if (!state.catalogue) {
          state.catalogue=overview.then(result=>result.stocks);
          state.catalogue.catch(()=>{state.catalogue=null;});
        }
        const result=await overview;
        data=result.radar;list=result.stocks;
      }
      if(request!==state.radarRequest)return;
      state.catalogue=Promise.resolve(list);
      quality(data.quality);
      const rows=poolRows(),active=list.filter(s=>isVisible(s,rows));
      const growth=active.filter(s=>s.value_factors.some(f=>f.color==='green')).length,risk=active.filter(s=>s.risks.length).length;
      panel.innerHTML = `<section class="value-hero"><p class="value-kicker">VALUE FIRST · 價值優先</p><h1 class="value-heading">先選好公司，再等好價格</h1><p class="value-muted">${escape(data.message)}</p><p class="value-note">最新已核實行情 ${escape(data.quote_date || '待核實')} ｜ 本裝置追蹤 ${active.length} 檔／基礎資料 ${data.quality.stocks} 檔<br>ETF 是初始股池來源，不是公司准入條件；新公司需另核對與回補。</p></section><div class="value-grid"><article class="value-card value-company-section"><h3>✓ 成長線索</h3><div class="value-number tone-green">${growth} 檔</div><p class="value-muted">官方營收有正成長；仍需獲利、現金流與持續性證據。</p><button class="btn value-primary-action" data-action="growth">查看 ${growth} 檔成長公司 →</button><p class="value-note">前往選股頁套用線索篩選；不是買進名單。</p></article><article class="value-card value-risk-section"><h3>△ 需留意公司</h3><div class="value-number tone-yellow">${risk} 檔</div><p class="value-muted">營收衰退或累計虧損，先核對原因。</p><button class="btn value-primary-action" data-action="risk">查看 ${risk} 檔需留意公司 →</button></article><article class="value-card value-price-section"><h3>○ 今日價值精選</h3><div class="value-number tone-gray">等待證據</div><p class="value-muted">公司體質尚未完整核實；不能產生正式排名。</p><button class="btn value-primary-action" data-action="all-stocks">前往股票總表 →</button></article></div><div class="value-toolbar"><button class="btn" data-action="manage-link">管理研究股池 →</button></div><details class="value-explanation"><summary>如何閱讀雷達</summary>${legend()}${priceLegend()}</details>${state.poolError?unavailable(state.poolError):''}`;
    } catch (error) { if(request===state.radarRequest)panel.innerHTML = unavailable(error.message); }
  };
  document.getElementById('tab-screener').innerHTML = `<h1 class="value-heading">我的研究股池</h1><p class="value-muted">先選公司體質 → 再看價格 → 查看個股依據 → 加入觀察</p><div class="value-toolbar"><label for="valueSearch">搜尋公司</label><input id="valueSearch" aria-label="股票代號或名稱" placeholder="輸入代號或公司名稱"><button class="btn" data-action="search">搜尋</button></div><div id="valueOverview"></div><section class="value-card value-company-section"><h2>① 先選公司體質</h2><div class="value-filter-row" id="valueCompanyFilters"></div><p class="value-note">營收成長不等於好公司；資料不足與基本面退化分開顯示。</p></section><section class="value-card value-price-section"><h2>② 再選價格位階</h2><div class="value-filter-row" id="valuePriceFilters"></div><details class="value-explanation"><summary>查看營收與風險線索（輔助）</summary><label for="valueFilter">線索篩選</label><select id="valueFilter"><option value="all">不限線索</option><option value="growth">有成長線索</option><option value="risk">有困難訊號</option></select></details></section><section class="value-card value-pool-section"><div class="value-stock-row"><h2>研究股池管理</h2><button class="btn" data-action="pool-toggle" aria-expanded="false" aria-controls="valuePoolManager">＋ 加入公司／管理股池</button></div><p class="value-note">本裝置偏好；加入股池與加入觀察分開。ETF 身分不作為准入門檻。</p><div id="valuePoolManager" hidden></div><p id="valuePoolStatus" role="status"></p></section><div id="valueResults" aria-live="polite"></div>`;
  state.companyFilter='all';state.zoneFilter='all';
  function priceRanges(stock, compact=false) {
    const value=stock.valuation;
    if (!value?.available || !Array.isArray(value.levels) || value.levels.length!==6) return unavailable(value?.reason || '尚無此指標的價格區間。',compact?null:stock.evidence_details?.valuation);
    const p=value.levels;
    const labels={special:`特價上限：NT$ ${money(p[0])}`,cheap:`便宜區間：NT$ ${money(p[0])}～${money(p[1])}`,fair:`合理區間：NT$ ${money(p[1])}～${money(p[4])}`,expensive:`昂貴區間：NT$ ${money(p[4])}～${money(p[5])}`,crazy:`過熱起點：NT$ ${money(p[5])}`};
    if(compact)return `<p>${escape(labels[stock.current_zone]||'價位待核實')}</p>`;
    return `<div class="value-range-list">${Object.entries(labels).map(([zone,label])=>`<div class="value-range range-${zone} ${stock.current_zone===zone?'range-current':''}"><span class="value-price price-${zone}">${zones[zone]}</span><strong>${escape(label)}</strong>${stock.current_zone===zone?'<span class="value-current">✓ 現價所在</span>':''}</div>`).join('')}</div><details class="value-explanation"><summary>計算方式、參考線與區間邊界</summary><p>${escape(value.method)}</p><p>特價 ≤ P1；便宜 > P1 且 ≤ P2；合理 > P2 且 < P5；昂貴 ≥ P5 且 < P6；過熱 ≥ P6。顯示金額四捨五入不改變程式判定。</p><p>P3、P4 是合理區內的中間參考線。</p><ul>${p.map((n,i)=>`<li>P${i+1}：NT$ ${money(n)}</li>`).join('')}</ul><p>樣本 ${value.sample_count} 日；歷史平均倍數 ${money(value.center_multiple)}。相對 P4 價格差距 ${money(value.margin_to_fair_pct)}%，不等於保證報酬。</p></details>`;
  }
  function selectionCard(stock) {
    return `<article class="value-card"><div class="value-stock-row"><h3>${escape(stock.company_name)} <span class="value-note">${escape(stock.ticker)}</span></h3><span class="value-note">${escape(stock.industry)}</span></div><section class="value-company-box"><h4>① 公司體質</h4>${companyBadge(stock)}<p>${escape(stock.evidence_details?.company.reason||stock.company_label)}</p>${explanation(stock.evidence_details?.company)}</section><section class="value-price-box"><h4>② 價格位階</h4><span class="value-price price-${stock.current_zone}">${zones[stock.current_zone]||zones.unknown}</span>${quote(stock)}${stock.valuation?.available?priceRanges(stock,true):`<p class="value-note">${escape(stock.valuation?.reason||'資料不足，暫無價格區間。')}</p>`}</section><div class="value-toolbar"><button class="btn value-primary-action" data-action="stock" data-ticker="${escape(stock.ticker)}">查看個股依據 →</button><button class="btn" data-action="watch-add-list" data-ticker="${escape(stock.ticker)}">☆ 加入觀察</button><button class="btn value-secondary-action" data-action="pool-pause" data-ticker="${escape(stock.ticker)}">暫停追蹤</button></div><p id="value-list-save-${escape(stock.ticker)}" role="status"></p></article>`;
  }
  function renderPoolManager(all,rows) {
    const known=new Map(all.map(s=>[s.ticker,s]));
    const pending=rows.filter(r=>r.custom&&r.status==='pending'&&!known.has(r.ticker));
    const custom=rows.filter(r=>r.custom&&known.has(r.ticker)&&!['paused','removed'].includes(r.status));
    const suspended=rows.filter(r=>r.status==='paused');
    const removed=rows.filter(r=>r.status==='removed');
    const row=(r,action,label)=>`<div class="value-management-row"><span>${escape(r.ticker)} ${escape(known.get(r.ticker)?.company_name||r.name)}</span><button class="btn" data-action="${action}" data-ticker="${escape(r.ticker)}">${label}</button></div>`;
    const manager=document.getElementById('valuePoolManager');
    manager.hidden=!state.manageOpen;
    document.querySelector('[data-action="pool-toggle"]').setAttribute('aria-expanded',String(state.manageOpen));
    manager.innerHTML=`<section class="value-management-section"><h3>＋ 加入研究公司</h3><label for="valueAddTicker">四碼公司代號</label><input id="valueAddTicker" maxlength="4" inputmode="numeric" placeholder="例如 2330" autocomplete="off"><label for="valueAddName">公司名稱（股池外公司必填，待官方核對）</label><input id="valueAddName" maxlength="80" placeholder="輸入要研究的公司名稱"><button class="btn value-primary-action" data-action="pool-add">加入研究股池／建立回補需求</button><p class="value-note">既有公司直接納入本裝置追蹤。新公司先保存待核對需求；不會直接下載行情或財報，也不能立即參與好公司判定。</p></section><section class="value-management-section"><h3>待核對／待回補 ${pending.length} 家</h3>${pending.length?pending.map(r=>`<div class="value-pending"><strong>${escape(r.ticker)} ${escape(r.name)}</strong><p>需求已保存在此裝置，尚未送到伺服器；公司身分、行情、營收、財報與股數待核對。</p><button class="btn" data-action="pool-remove" data-ticker="${escape(r.ticker)}">移除自選需求</button></div>`).join(''):'<p>目前沒有股池外的待回補需求。</p>'}<button class="btn" data-action="pool-export" ${pending.length?'':'disabled'}>匯出回補需求給電腦端</button><p class="value-note">匯出只含代號、使用者輸入的公司名稱與需求時間，不含觀察筆記。電腦端核對與回補後，再更新 App 公開資料。</p></section><section class="value-management-section"><h3>我的自選追蹤 ${custom.length} 家</h3>${custom.map(r=>row(r,'pool-remove','移除自選')).join('')||'<p>可先加入既有公司，或在公司卡片暫停追蹤。</p>'}</section><details class="value-explanation" ${suspended.length?'open':''}><summary>已暫停 ${suspended.length} 家</summary>${suspended.map(r=>row(r,'pool-restore','恢復追蹤')).join('')||'<p>目前沒有暫停追蹤的公司。</p>'}</details><details class="value-explanation" ${removed.length?'open':''}><summary>已移除自選 ${removed.length} 家</summary><p>移除的是個人追蹤關係；行情、財報、版本、觀察筆記及官方 ETF 記錄均保留。</p>${removed.map(r=>row(r,'pool-restore','重新加入')).join('')||'<p>目前沒有移除紀錄。</p>'}</details>`;
  }
  function metricPanel(stock,history,metric) {
    const recommendation=stock.metric_recommendation;
    const recommended=recommendation?.metric||history?.metric;
    const selected=recommendation?.selected_metric||history?.metric;
    return `<section class="value-card value-price-section"><h3>估值指標｜${metric==='auto'?'系統建議，已自動呈現':'自行選取'}</h3><div class="value-number">${escape(metricNames[selected]||'待核實')}</div><p>${escape(metric==='auto'?(recommendation?.reason||'依目前分類的研究規則選擇指標。'):'目前查看自行選取的指標；系統建議為 '+(metricNames[recommended]||'待核實')+'。')}</p><p class="value-note">${escape(recommendation?.basis||'公司分類與指標適用性需核實。')}</p><div class="value-metric-help">${metricHelp(selected)}</div><details class="value-explanation" ${metric!=='auto'?'open':''}><summary>查看其他估值指標</summary><div class="value-toolbar"><label for="valueMetric">自行比較</label><select id="valueMetric"><option value="auto">使用系統建議</option><option value="pe">P/E 本益比</option><option value="pb">P/B 股價淨值比</option><option value="ps">P/S 股價營收比</option></select></div></details>${metric!=='auto'?'<button class="btn" data-action="metric-reset">回到系統建議</button>':''}<p class="value-note">指標選擇不代表公司已通過體質判定；低倍數也不能直接當作買進理由。</p></section>`;
  }
  function metricHelp(metric) {
    const helps={pe:'P/E 本益比＝股價 ÷ 每股盈餘。觀察正盈餘與獲利持續性，注意 EPS 期間及一次性收益；虧損或盈餘接近零時不宜直接比較。',pb:'P/B 股價淨值比＝股價 ÷ 每股淨值。搭配獲利能力、資產品質與負債；低於淨值不必然便宜。',ps:'P/S 股價營收比＝市值 ÷ 營收。搭配毛利率、費用與現金流；營收成長不等於獲利成長。'};
    return `<p>${escape(helps[metric]||'資料不足，無法確認適用指標。')}</p><p class="value-note">本頁價位使用已核實同日官方倍數與歷史分位數研究，並非未來 EPS 預估。基本值依當日收盤 ÷ 倍數推導，不與不同期間 EPS／淨值混搭；沒有正值倍數與足夠樣本時保持未知。</p>`;
  }
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
    const request=++state.screenerRequest;
    const results = document.getElementById('valueResults');
    results.innerHTML = unavailable('正在載入官方證據…');
    try {
      const all = await catalogue();
      if(request!==state.screenerRequest)return;
      const preferences=poolRows();
      const search=document.getElementById('valueSearch').value.trim().toLowerCase();
      const list=all.filter(stock=>isVisible(stock,preferences)&&(stock.ticker+stock.company_name).toLowerCase().includes(search));
      const filter = document.getElementById('valueFilter').value;
      const companyList=list.filter(stock=>state.companyFilter==='all'||companyKey(stock)===state.companyFilter);
      const selected = companyList.filter(stock => (state.zoneFilter==='all'||stock.current_zone===state.zoneFilter)&&(filter === 'all' || filter === 'growth' && stock.value_factors.some(f => f.color === 'green') || filter === 'risk' && stock.risks.length));
      document.getElementById('valueCompanyFilters').innerHTML=['all',...Object.keys(companyStates)].map(key=>`<button class="btn company-filter company-${key==='all'?'all':companyStates[key][1]}" data-action="company-filter" data-filter="${key}" aria-pressed="${state.companyFilter===key}">${key==='all'?'全部體質':companyStates[key][0]} ${key==='all'?list.length:list.filter(s=>companyKey(s)===key).length}</button>`).join('');
      document.getElementById('valuePriceFilters').innerHTML=['all',...Object.keys(zones)].map(key=>`<button class="btn zone-filter zone-${key}" data-action="zone-filter" data-filter="${key}" aria-pressed="${state.zoneFilter===key}">${key==='all'?'全部價位':zones[key]} ${key==='all'?companyList.length:companyList.filter(s=>s.current_zone===key).length}</button>`).join('');
      document.getElementById('valueOverview').innerHTML = `<div class="value-summary"><div><span class="value-note">已核實收盤</span><strong>${list.filter(s => s.quote).length} 檔</strong></div><div><span class="value-note">成長線索</span><strong class="tone-green">${list.filter(s => s.value_factors.some(f => f.color === 'green')).length} 檔</strong></div><div><span class="value-note">困難訊號</span><strong class="tone-yellow">${list.filter(s => s.risks.length).length} 檔</strong></div><div><span class="value-note">估值待核實</span><strong class="tone-gray">${list.filter(s => !s.valuation.available).length} 檔</strong></div></div><p class="value-note">摘要依搜尋結果；成長與困難可同時存在。</p>`;
      results.innerHTML = `<h2>③ 查看個股依據與加入觀察</h2><p class="value-note">符合 ${selected.length} 檔；價格便宜不代表公司已通過體質判定。</p>` + (selected.length ? `<div class="value-stock-list">${selected.map(selectionCard).join('')}</div>` : unavailable('沒有符合公司體質與價格交集的公司；可調整條件或查看資料不足。'))+(state.poolError?unavailable(state.poolError):'');
      renderPoolManager(all,preferences);
    } catch (error) { if(request===state.screenerRequest)results.innerHTML = unavailable(error.message); }
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
    state.stock = null; state.history = null; state.historyPromise = null;
    const detail = document.getElementById('valueDetail');
    detail.innerHTML = `<h1 class="value-heading">${escape(ticker)} 個股研究</h1>${unavailable('正在取得已核實價格與證據…')}`;
    try {
      const stock = await api(`/stocks/${encodeURIComponent(ticker)}?metric=${encodeURIComponent(metric)}&scenario=base`);
      if (request !== state.request) return;
      state.stock = stock;
      const basics = factorCards(stock) + explanation(stock.evidence_details?.company,'查看公司體質缺項與已取得資料') + `<details class="value-explanation" data-financial-details><summary>查看財報原值與官方來源</summary>${balanceCard(stock)}${source(stock.revenue)}${source(stock.income_ytd)}</details>`;
      const epsBody = `<h2 class="value-heading">已實現獲利與未來分開看</h2>${stock.income_ytd ? `<div class="value-card"><h3>${escape(stock.income_ytd.period)} 年初至當季累計 EPS</h3><div class="value-number ${stock.income_ytd.eps < 0 ? 'tone-red' : 'tone-yellow'}">${money(stock.income_ytd.eps)} 元</div><p class="value-note">${escape(stock.income_ytd.basis)}。不能乘二當成年預估，也不能冒充單季 EPS。</p>${source(stock.income_ytd)}</div>` : unavailable('此公司的累計損益來源尚未完成查核。')}${unavailable('未來 EPS 需連續單季財報、同期營收與股數；目前不填入固定成長率。',stock.evidence_details?.eps)}`;
      const conclusions = `<h2 class="value-heading">${escape(stock.conclusion)}</h2><section class="value-company-box"><h3>① 公司體質</h3>${companyBadge(stock)}<p>${escape(stock.evidence_details?.company.reason||stock.company_label)}</p>${stock.risks.map(risk => `<p class="tone-red">! ${escape(risk)}</p>`).join('')}</section><section class="value-price-box"><h3>② 系統建議估值與價格</h3><p>${escape(metricNames[stock.metric_recommendation?.selected_metric]||'待核實')} ｜ ${metric==='auto'?'系統建議':'自行選取'}</p><p class="value-note">${escape(stock.metric_recommendation?.reason||'依公司分類的研究規則，適用性仍需核實。')}</p><span class="value-price price-${stock.current_zone}">${zones[stock.current_zone]}</span>${priceRanges(stock,true)}<button class="btn value-primary-action" data-action="subtab" data-page="river">查看估值與價格依據 →</button></section>${basics}`;
      const research = `<h2 class="value-heading">價值研究清單</h2><p class="value-muted">${escape(stock.research.reason)}</p><div class="value-card"><h3>還需要回答的問題</h3><ol><li>收入成長能否轉為可持續獲利？</li><li>營業現金流與自由現金流是否支撐盈餘？</li><li>負債、存貨及應收帳款有沒有增加壓力？</li><li>利潤是否來自一次性業外收益？</li><li>現價相對可持續獲利是否有安全邊際？</li></ol><p class="value-note">待補資料：${stock.missing.map(escape).join('、')}</p></div>${source(stock.revenue)}${source(stock.income_ytd)}`;
      const bodies = {conclusion:conclusions, fundamentals:'<h2 class="value-heading">公司體質摘要</h2>' + basics + `<details class="value-explanation" data-history-details><summary>查看行情明細與完整歷史表</summary><div data-history-content>${unavailable('展開後才載入歷史資料。')}</div></details>`, river:'<h2 class="value-heading">現價與價值之間</h2><div data-river-content>進入價位頁後載入歷史研究圖…</div>', eps:epsBody, chips:'<h2 class="value-heading">籌碼是輔助訊號</h2>' + unavailable('尚未取得已核實法人交易與持股資料；不顯示固定買超或黃金交叉。',stock.evidence_details?.chips) + '<p class="value-muted">先確認公司價值與價格，再用籌碼輔助判讀。</p>', ai:research};
      detail.innerHTML = `<h1 class="value-heading">${escape(stock.ticker)} ${escape(stock.company_name)}</h1><p class="value-note">${escape(stock.industry)} ｜ ${escape(stock.company_label)}</p><div class="value-sticky">${quote(stock)}</div><div class="value-toolbar"><button class="btn" data-action="watch-add">☆ 加入觀察</button><span id="valueSaveStatus" role="status"></span></div><div class="value-subtabs" role="tablist" aria-label="個股分析分頁">${pages.map(([id,label], i) => `<button role="tab" id="value-tab-${id}" aria-controls="dsub-${id}" aria-selected="${i === 0}" class="${i === 0 ? 'active' : ''}" data-action="subtab" data-page="${id}">${label}</button>`).join('')}</div>${pages.map(([id], i) => `<section id="dsub-${id}" role="tabpanel" aria-labelledby="value-tab-${id}" class="value-panel ${i === 0 ? 'active' : ''}">${quote(stock)}${bodies[id]}</section>`).join('')}`;
      switchDetailSubTab(state.page);
    } catch (error) {
      if (request === state.request) detail.innerHTML = unavailable(error.message);
    }
  };
  async function loadHistoricalDetail() {
    if (!state.stock || state.historyPromise || state.history) return;
    const request = state.request, ticker = state.ticker, metric = state.metric, years = state.years;
    const pending = api(`/evidence/stocks/${encodeURIComponent(ticker)}/history?metric=${encodeURIComponent(metric)}&years=${years}`);
    state.historyPromise = pending;
    try {
      const history = await pending;
      if (request !== state.request || years !== state.years) return;
      state.history = history;
      const stock = state.stock;
      const market = `<div class="quote-market"><div>開盤<strong>${money(stock.quote?.open)}</strong></div><div>最高<strong>${money(stock.quote?.high)}</strong></div><div>最低<strong>${money(stock.quote?.low)}</strong></div><div>成交股數<strong>${money(stock.quote?.volume)}</strong></div></div>`;
      const historyContent = document.querySelector('#dsub-fundamentals [data-history-content]');
      if (historyContent) historyContent.innerHTML = market + historyTable(history);
      const periodControl = `<div class="value-toolbar"><label for="valueYears">時間範圍</label><select id="valueYears"><option value="1">近 1 年</option><option value="2">近 2 年</option><option value="3">近 3 年</option></select></div>`;
      const priceBody = `${metricPanel(stock,history,metric)}${priceRanges(stock)}<div class="value-card"><h3>官方當日倍數</h3><p>P/E ${money(stock.quote?.pe)} 倍 ｜ P/B ${money(stock.quote?.pb)} 倍</p><p class="value-note">${escape(stock.quote?.period||'無已核實行情')} 的同日倍數，不能單憑數值判定便宜。</p></div>${source(stock.quote)}`;
      const riverContent = document.querySelector('#dsub-river [data-river-content]');
      if (riverContent) riverContent.innerHTML = priceBody + periodControl + riverChart(history);
      document.getElementById('valueMetric').value = metric;
      document.getElementById('valueYears').value = String(years);
    } catch (error) {
      if (request === state.request && years === state.years) {
        const retry = `${unavailable(error.message)}<button class="btn" data-action="history-retry">重新載入歷史資料</button>`;
        for (const content of document.querySelectorAll('[data-history-content], [data-river-content]')) content.innerHTML = retry;
      }
    } finally {
      if (state.historyPromise === pending) state.historyPromise = null;
    }
  }
  window.switchDetailSubTab = id => {
    state.page = id;
    pages.forEach(([page]) => {
      document.getElementById('dsub-' + page)?.classList.toggle('active', page === id);
      const button = document.getElementById('value-tab-' + page);
      button?.classList.toggle('active', page === id);
      button?.setAttribute('aria-selected', String(page === id));
    });
    if (id === 'river') loadHistoricalDetail();
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
  settings.innerHTML = `<h1 class="value-heading">閱讀與資料設定</h1><div class="value-card" id="valueReading"><h3>字級與長輩友善模式</h3></div><div class="value-card"><h3>色彩怎麼看</h3>${legend()}${priceLegend()}<p class="value-muted">淺綠顯示已證實的成長線索；琥珀提醒衰退待觀察；珊瑚紅提示虧損或風險；灰色代表缺證據。各色皆搭配文字，不需只靠數字判讀。</p></div><div class="value-card"><h3>資料查核狀態</h3><div id="valueQuality">正在查核…</div><p class="value-note">歷年財報、ETF 有效成分、美債及行情差集的公司事件仍待核實。原始種子保留供查核，但不提供正式投資分析。</p><button class="btn" data-action="quality">重新查核</button></div><div class="value-card"><h3>分析功能資料需求</h3><p class="value-muted">EPS 預估、體質評分、河流圖、籌碼、部位配置與歷史回測需要完整來源。未達條件的項目顯示「待核實」，恢復前不使用舊模擬結果。</p><p class="value-note">${window.STATIC_BUILD_TIME ? '快照產生：' + escape(window.STATIC_BUILD_TIME) + '；不是即時更新。' : '正式模式不自動寫入模擬種子；背景排程預設關閉。'}</p><a href="https://www.sie.com.tw/Luckylong/article.do?id=A20240411748546VR1" target="_blank" rel="noopener">閱讀孫慶龍公開估值理念 ↗</a></div>`;
  document.getElementById('valueReading').appendChild(controls);
  document.getElementById('valueReading').insertAdjacentHTML('afterend',`<section class="value-card value-company-section"><h2>快速操作說明</h2><ol class="value-instructions"><li><b>雷達：</b>查看成長與需留意線索，按明顯的查看按鈕進入清單。</li><li><b>選股：</b>搜尋公司；先篩公司體質，再篩價格位階，查看兩者交集。</li><li><b>個股：</b>進入時直接顯示系統建議指標；查看六個子頁的來源、價格與日期。</li><li><b>估值：</b>想比較時才展開「查看其他估值指標」，可一鍵回到系統建議。</li><li><b>觀察：</b>加入公司、儲存筆記。${window.STATIC_BUILD_TIME?'筆記保存在此装置。':'筆記保存在本機服務資料庫。'}</li><li><b>股池管理：</b>加入既有公司，或建立新公司待核對需求；暫停／恢復及移除自選只更改本裝置追蹤。</li><li><b>待核實：</b>展開原因、缺項、已取得資料與下一步。收盤參考不是即時行情。</li></ol></section><section class="value-card value-price-section"><h2>估值指標怎麼選？</h2><details class="value-explanation" open><summary>系統建議（自動呈現）</summary><p>依目前主檔分類：金融／循環類型採 P/B，其餘採 P/E。會顯示實際選擇與原因；分類及適用性仍需核實，資料不足不補值。</p></details>${Object.entries(metricNames).map(([metric,label])=>`<details class="value-explanation"><summary>${label}</summary>${metricHelp(metric)}</details>`).join('')}</section>`);
  async function quality(existing) {
    try {
      const data = existing || await api('/evidence/status');
      document.getElementById('valueQuality').innerHTML = `<p class="value-muted">${escape(data.reason)}</p><p>已核實：行情 ${data.verified_coverage.price}/${data.stocks}、月營收 ${data.verified_coverage.revenue}/${data.stocks}、累計損益 ${data.verified_coverage.income_ytd}/${data.stocks}、最新資產負債 ${data.verified_coverage.balance_sheet ?? 0}/${data.stocks}</p><span class="value-status tone-gray">○ 投資判定資料尚未齊備</span>`;
    } catch (error) { document.getElementById('valueQuality').innerHTML = unavailable(error.message); }
  }
  document.addEventListener('click', async event => {
    const button = event.target.closest('[data-action]');
    if (!button) return;
    const action = button.dataset.action;
    if (action === 'stock') return viewStock(button.dataset.ticker);
    if (action === 'subtab') return switchDetailSubTab(button.dataset.page);
    if (action === 'history-retry') return loadHistoricalDetail();
    if (action === 'search') return loadScreenerData();
    if (action === 'company-filter') {state.companyFilter=button.dataset.filter;return loadScreenerData();}
    if (action === 'zone-filter') {state.zoneFilter=button.dataset.filter;return loadScreenerData();}
    if (action === 'metric-reset') return loadStockDetail(state.ticker,'auto');
    if (action === 'all-stocks'||action==='manage-link') {
      activate('screener');state.companyFilter='all';state.zoneFilter='all';document.getElementById('valueFilter').value='all';document.getElementById('valueSearch').value='';
      if(action==='manage-link')state.manageOpen=true;
      await loadScreenerData();if(action==='manage-link')document.getElementById('valuePoolManager').closest('section').scrollIntoView({block:'start'});return;
    }
    if (action==='pool-toggle') {state.manageOpen=!state.manageOpen;document.getElementById('valuePoolManager').hidden=!state.manageOpen;button.setAttribute('aria-expanded',String(state.manageOpen));return;}
    if (['pool-add','pool-pause','pool-restore','pool-remove','pool-export'].includes(action)) {
      button.disabled=true;
      const status=document.getElementById('valuePoolStatus');
      try {
        const all=await catalogue();
        let message;
        if(action==='pool-export') {
          const data=pool.requests(all.map(s=>s.ticker));
          if(!data.requests.length)throw new Error('目前沒有待核對回補需求。');
          const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json;charset=utf-8'}));
          const link=document.createElement('a');link.href=url;link.download='研究股池回補需求.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
          message='需求檔已匯出，請交給電腦端核對；尚未送到伺服器或執行回補。';
        } else {
          const ticker=action==='pool-add'?document.getElementById('valueAddTicker').value.trim():button.dataset.ticker;
          const known=all.find(s=>s.ticker===ticker);
          if(action==='pool-add') {pool.add(ticker,document.getElementById('valueAddName').value,known);message=known?'✓ 已加入本裝置自選追蹤；公司體質仍依實際資料判定。':'✓ 待核對需求已儲存在此裝置；尚未送到伺服器或回補資料。';}
          else {pool.setStatus(ticker,action==='pool-pause'?'paused':action==='pool-remove'?'removed':'active',known);message=action==='pool-pause'?'✓ 已暫停本裝置追蹤，可從已暫停清單恢復。':action==='pool-remove'?'✓ 已移除自選關係；資料與觀察筆記保留。':known?'✓ 已恢復本裝置追蹤。':'✓ 已恢復待核對需求，資料仍待回補。';}
          state.manageOpen=true;
          await loadScreenerData();
        }
        status.textContent=message;status.setAttribute('role','status');
      } catch(error) {status.textContent=error.message;status.setAttribute('role','alert');}
      finally {button.disabled=false;}
      return;
    }
    if (action === 'growth' || action === 'risk') {
      activate('screener'); state.companyFilter='all';state.zoneFilter='all';document.getElementById('valueSearch').value='';document.getElementById('valueFilter').value = action;
      return loadScreenerData();
    }
    if (action === 'quality') return quality();
    if (['watch-add','watch-add-list','note-save','watch-delete'].includes(action)) {
      button.disabled = true;
      let status;
      try {
        const adding=['watch-add','watch-add-list'].includes(action);
        const stock = action === 'watch-add-list' ? (await catalogue()).find(s=>s.ticker===button.dataset.ticker) : action === 'watch-add' ? state.stock : state.watch[Number(button.dataset.index)];
        status = document.getElementById(action==='watch-add-list'?'value-list-save-'+button.dataset.ticker:action === 'watch-add' ? 'valueSaveStatus' : 'note-status-' + button.dataset.index);
        if (action === 'watch-delete') {
          await api('/evidence/watchlist/' + stock.ticker + '?group_id=' + encodeURIComponent(stock.group_id), {method:'DELETE'});
          return loadWatchlistData();
        }
        const payload = adding ? {} : {note:document.getElementById('value-note-' + button.dataset.index).value, group_id:stock.group_id, group_name:stock.group_name};
        await api('/evidence/watchlist/' + stock.ticker, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
        status.textContent = '✓ 已儲存';
      } catch (error) { if (status) status.textContent = error.message; }
      finally { button.disabled = false; }
    }
  });
  document.addEventListener('change', event => {
    if (event.target.id === 'valueMetric') loadStockDetail(state.ticker, event.target.value).then(() => switchDetailSubTab('river'));
    if (event.target.id === 'valueYears') { state.years = Number(event.target.value); state.history = null; state.historyPromise = null; const river=document.querySelector('[data-river-content]'); if(river) river.textContent='正在更新歷史研究圖…'; const history=document.querySelector('[data-history-content]'); if(history) history.textContent='正在更新歷史表…'; loadHistoricalDetail(); }
    if (event.target.id === 'valueFilter') loadScreenerData();
  });
  document.addEventListener('toggle', event => {
    if (event.target.matches('[data-history-details]') && event.target.open) loadHistoricalDetail();
  }, true);
  document.getElementById('valueSearch').addEventListener('keydown', event => { if (event.key === 'Enter') loadScreenerData(); });
  window.addEventListener('storage',event=>{if(event.key?.startsWith('value-research-pool-v1:')){if(document.getElementById('tab-screener').classList.contains('active'))loadScreenerData();if(document.getElementById('tab-radar').classList.contains('active'))loadRadarData();}});
  window.onload = () => { initAccessibilityPreferences(); loadRadarData(); };
})();

/* 靜態快照只回傳明確支援的參數；觀察筆記實際寫入此裝置。 */
(() => {
  if (!window.STATIC_BUILD_TIME) return;
  const nativeFetch = window.fetch.bind(window);
  const base = new URL('.', document.baseURI);
  // 公開資料依快照版本識別，避免 HTTP 快取混用不同批次的總表與個股。
  const snapshotUrl = path => {
    const url = new URL(path, base);
    url.searchParams.set('snapshot', window.STATIC_BUILD_TIME);
    return url;
  };
  const json = (data, status=200) => new Response(JSON.stringify(data), {status, headers:{'Content-Type':'application/json'}});
  const unavailable = reason => json({available:false,status:'insufficient',reason},409);
  let globalData;
  const stockCache = new Map();
  const key = 'value-observations-evidence-v2';
  const stockData = async ticker => {
    if (!stockCache.has(ticker)) {
      stockCache.set(ticker, nativeFetch(snapshotUrl(`data/stock-${ticker}.json`)).then(response => {
        if (!response.ok) throw new Error('快照沒有此個股');
        return response.json();
      }));
    }
    return stockCache.get(ticker);
  };
  const readWatch = () => {
    const data = JSON.parse(localStorage.getItem(key) || '[]');
    if (!Array.isArray(data)) throw new Error('此裝置觀察資料格式損壞');
    return data;
  };
  const allowed = (params, names) => [...params.keys()].every(name => names.includes(name));
  window.fetch = async (input, options={}) => {
    const url = new URL(typeof input === 'string' ? input : input.url,base);
    if (url.origin !== base.origin || !url.pathname.startsWith('/api/')) return nativeFetch(input,options);
    const path = url.pathname;
    const method = (options.method || input.method || 'GET').toUpperCase();
    const params = url.searchParams;
    try {
      if (!globalData) globalData = nativeFetch(snapshotUrl('data/global.json')).then(response => {
        if (!response.ok) throw new Error('資料快照載入失敗');
        return response.json();
      });
      const database = await globalData;
      if (path === '/api/evidence/watchlist' && method === 'GET') {
        if (!allowed(params,[])) return unavailable('不支援此觀察參數');
        return json(await Promise.all(readWatch().map(async row => ({...(await stockData(row.ticker)).auto,...row}))));
      }
      const watch = path.match(/^\/api\/evidence\/watchlist\/(\d{4})$/);
      if (watch && ['POST','DELETE'].includes(method)) {
        if (!allowed(params,['group_id'])) return unavailable('不支援此觀察參數');
        const ticker = watch[1];
        await stockData(ticker);
        let rows = readWatch();
        if (method === 'DELETE') rows = rows.filter(row => !(row.ticker === ticker && row.group_id === (params.get('group_id') || 'value')));
        else {
          const payload = JSON.parse(options.body || '{}');
          const group_id = String(payload.group_id || 'value').slice(0,50);
          const previous = rows.find(row => row.ticker === ticker && row.group_id === group_id);
          const row = {ticker,group_id,group_name:String(payload.group_name || previous?.group_name || '價值研究').slice(0,50),note:payload.note === undefined ? previous?.note || '' : String(payload.note).slice(0,10000)};
          rows = rows.filter(item => !(item.ticker === ticker && item.group_id === group_id));
          rows.push(row);
        }
        localStorage.setItem(key,JSON.stringify(rows));
        return json({success:true,storage:'device',message:'已儲存在此裝置'});
      }
      if (method !== 'GET') return unavailable('靜態站不支援此寫入；未送出，也未模擬成功。');
      if (path === '/api/screener') {
        if (!allowed(params,['scope','quadrant','zone','search'])) return unavailable('不支援的選股参数');
        if (params.has('scope') && params.get('scope') !== 'all') return unavailable('靜態快照僅提供已核對的研究股池；ETF 成分與自選同步待完成。');
        const search = (params.get('search') || '').toLowerCase();
        const zone = params.get('zone') || 'all';
        const quadrant = params.get('quadrant') || 'all';
        return json(database.routes['/api/screener'].filter(stock => (stock.ticker + stock.company_name).toLowerCase().includes(search) && (zone === 'all' || stock.current_zone === zone) && ['all','insufficient'].includes(quadrant)));
      }
      const match = path.match(/^\/api\/stocks\/(\d{4})$/);
      const history = path.match(/^\/api\/evidence\/stocks\/(\d{4})\/history$/);
      if (history) {
        if (!allowed(params,['metric','years'])) return unavailable('不支援的歷史參數');
        const metric = params.get('metric') || 'auto';
        const years = Number(params.get('years') || 3);
        if (![1,2,3].includes(years)) return unavailable('時間範圍限 1／2／3 年');
        const data = (await stockData(history[1])).history?.[metric];
        if (!data) return unavailable('快照不支援此歷史指標');
        const cutoff = new Date(data.as_of_date + 'T00:00:00Z');
        cutoff.setUTCFullYear(cutoff.getUTCFullYear()-years);
        cutoff.setUTCDate(Math.min(cutoff.getUTCDate(),28));
        const rows = data.rows.filter(row=>row.date >= cutoff.toISOString().slice(0,10));
        return json({...data,years,rows,verified_price_points:rows.length,river_points:rows.filter(row=>row.model_available).length});
      }
      if (match) {
        if (!allowed(params,['metric','scenario'])) return unavailable('不支援的個股參數');
        const metric = params.get('metric') || 'auto';
        const scenario = params.get('scenario') || 'base';
        const stock = (await stockData(match[1]))[metric];
        if (!stock) return unavailable('快照不支援此估值指標');
        if (scenario !== 'base') return json({...stock,current_zone:'unknown',valuation:{available:false,status:'insufficient',reason:'尚無可查證的預估 EPS 情境，不能以固定成長率冒充未來獲利。'}});
        return json(stock);
      }
      if (!allowed(params,[])) return unavailable('快照不支援此查詢參數');
      if (Object.hasOwn(database.routes,path)) return json(database.routes[path]);
      return unavailable('此功能尚無完整已核實快照。');
    } catch (error) { return unavailable(error.message); }
  };
})();

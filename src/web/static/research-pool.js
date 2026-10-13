/* 本裝置研究股池：私人追蹤偏好與待回補需求，與官方公司資料及觀察筆記分開。 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.ResearchPool = factory();
})(typeof window === 'object' ? window : globalThis, function () {
  'use strict';
  const statuses = ['active', 'pending', 'paused', 'removed'];
  function create(storage, key, clock = () => new Date().toISOString()) {
    function read() {
      let raw;
      try { raw = storage.getItem(key); } catch (_) { throw new Error('此裝置無法讀取研究股池；請檢查瀏覽器儲存權限。'); }
      if (raw === null) return [];
      let data;
      try { data = JSON.parse(raw); } catch (_) { throw new Error('研究股池儲存格式損壞；原紀錄保留，停止覆寫。'); }
      if (data?.version !== 1 || !Array.isArray(data.records) || data.records.length > 5000) throw new Error('研究股池版本或格式不支援；原紀錄保留。');
      const seen = new Set();
      for (const r of data.records) {
        if (!r || typeof r.ticker !== 'string' || !/^\d{4}$/.test(r.ticker) || seen.has(r.ticker) || typeof r.name !== 'string' || r.name.length > 80 ||
            !statuses.includes(r.status) || typeof r.custom !== 'boolean' || typeof r.created_at !== 'string' || typeof r.updated_at !== 'string') {
          throw new Error('研究股池紀錄不合法；停止覆寫，請先保留原資料。');
        }
        seen.add(r.ticker);
      }
      return data.records;
    }
    function write(rows) {
      try { storage.setItem(key, JSON.stringify({version: 1, records: rows})); }
      catch (_) { throw new Error('儲存失敗；可能已滿或瀏覽器禁止儲存。此次操作未保存。'); }
      return rows;
    }
    function change(ticker, transform) {
      if (!/^\d{4}$/.test(ticker)) throw new Error('請輸入四碼上市／上櫃公司代號；公司身分仍須官方核對。');
      const rows = read(), index = rows.findIndex(r => r.ticker === ticker);
      if (index < 0 && rows.length >= 5000) throw new Error('本裝置追蹤紀錄已達儲存上限；請先保存資料再整理。');
      const old = index < 0 ? null : rows[index];
      const next = transform(old, clock());
      if (index < 0) rows.push(next); else rows[index] = next;
      return write(rows);
    }
    function add(ticker, name, known) {
      name = String(name || '').trim();
      if (!known && (!name || name.length > 80)) throw new Error('請填寫公司名稱（最多 80 字），作為待核對需求。');
      return change(ticker, (old, time) => {
        if (old && !['paused', 'removed'].includes(old.status)) throw new Error('此公司已在研究股池或待回補清單，請勿重複加入。');
        return {ticker, name: known?.company_name || name || old?.name || ticker,
          custom: true, status: known ? 'active' : 'pending', created_at: old?.created_at || time, updated_at: time};
      });
    }
    function setStatus(ticker, status, known) {
      if (!['paused', 'removed', 'active'].includes(status)) throw new Error('不支援的追蹤狀態。');
      return change(ticker, (old, time) => {
        if (!old && !known) throw new Error('找不到此公司紀錄。');
        if (status === 'removed' && !old?.custom) throw new Error('基礎股池可暫停追蹤，不能刪除官方來源關係。');
        return {ticker, name: known?.company_name || old.name, custom: old?.custom || false,
          status: status === 'active' && !known ? 'pending' : status, created_at: old?.created_at || time, updated_at: time};
      });
    }
    function visible(ticker, rows = read()) {
      const r = rows.find(item => item.ticker === ticker);
      return !r || !['paused', 'removed'].includes(r.status);
    }
    function requests(knownTickers = []) {
      const known = new Set(knownTickers);
      return {version: 1, purpose: '公司資料待核對與回補需求，不是已驗證股票資料', exported_at: clock(),
        requests: read().filter(r => r.custom && !known.has(r.ticker) && r.status === 'pending')
          .map(r => ({ticker: r.ticker, supplied_company_name: r.name, requested_at: r.created_at}))};
    }
    return {read, add, setStatus, visible, requests};
  }
  return {create};
});

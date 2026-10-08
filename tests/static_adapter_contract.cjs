/* 靜態傳輸契約驗證：參數、失敗狀態、裝置筆記確實持久化。 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('src/web/static/static-adapter.js','utf8');
const storage = new Map();
const requestedSnapshots = [];
const globalData = {routes:{'/api/screener':[{ticker:'2330',company_name:'台積電',current_zone:'unknown'}],'/api/radar':{evidence_version:1}}};
const stocks = {auto:{ticker:'2330',metric:'auto'},pe:{ticker:'2330',metric:'pe'},pb:{ticker:'2330',metric:'pb'},ps:{ticker:'2330',metric:'ps'},history:{auto:{as_of_date:'2026-10-07',rows:[{date:'2026-10-06',model_available:false}],years:3}}};
function create(buildTime='2026-10-07T10:00:00Z') {
  const window={STATIC_BUILD_TIME:buildTime,fetch:async url=>{
    const request=new URL(url);
    const path=request.pathname;
    assert.ok(path.startsWith('/site/data/'));
    assert.equal(request.searchParams.get('snapshot'),buildTime);
    requestedSnapshots.push(request.href);
    return new Response(JSON.stringify(path.endsWith('global.json') ? globalData : stocks));
  }};
  vm.runInNewContext(source,{window,document:{baseURI:'https://example.test/site/index.html'},URL,Response,Date,Map,Object,JSON,localStorage:{getItem:key=>storage.get(key),setItem:(key,value)=>storage.set(key,value)}});
  return window;
}
(async()=>{
  let app=create();
  const pb=await (await app.fetch('/api/stocks/2330?scenario=base&metric=pb')).json();
  assert.equal(pb.metric,'pb');
  assert.equal((await app.fetch('/api/stocks/2330?unexpected=1')).status,409);
  const optimistic=await (await app.fetch('/api/stocks/2330?scenario=optimistic')).json();
  assert.equal(optimistic.valuation.available,false);
  assert.equal((await app.fetch('/api/push/preview',{method:'POST'})).status,409);
  assert.equal((await app.fetch('/api/evidence/watchlist/2330',{method:'POST',body:JSON.stringify({note:'來源待查核'})})).status,200);
  app=create();
  const observations=await (await app.fetch('/api/evidence/watchlist')).json();
  assert.equal(observations[0].note,'來源待查核');
  assert.equal((await app.fetch('/api/evidence/stocks/2330/history?years=4')).status,409);
  const history=await (await app.fetch('/api/evidence/stocks/2330/history?years=1')).json();
  assert.equal(history.rows.length,1);
  assert.equal((await app.fetch('/api/screener?search=%E5%8F%B0%E7%A9%8D')).status,200);
  app=create('2026-10-08T10:00:00Z');
  await app.fetch('/api/stocks/2330');
  // 同一公開資料路徑在新快照使用不同 URL，避免總表與個股沿用舊批次快取。
  for (const filename of ['global.json','stock-2330.json']) {
    const versions=new Set(requestedSnapshots.filter(url=>new URL(url).pathname.endsWith(filename)));
    assert.equal(versions.size,2);
  }
  console.log('靜態傳輸契約全部通過');
})().catch(error=>{console.error(error);process.exit(1)});

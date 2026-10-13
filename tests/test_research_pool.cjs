/* 本裝置私人追蹤的保存、恢復與失敗邊界；不接正式資料庫。 */
const test=require('node:test');
const assert=require('node:assert/strict');
const {create}=require('../src/web/static/research-pool.js');
const memory=()=>{const map=new Map();return {getItem:k=>map.has(k)?map.get(k):null,setItem:(k,v)=>map.set(k,v)};};
const known={ticker:'2330',company_name:'來源公司'};
test('新公司先保存待核對需求，不當作已驗證股票',()=>{
 const p=create(memory(),'pool',()=> '2026-10-12T08:00:00Z');p.add('1234','待核對公司',null);
 assert.equal(p.read()[0].status,'pending');assert.equal(p.requests().requests[0].supplied_company_name,'待核對公司');
 assert.equal(p.requests(['1234']).requests.length,0);
});
test('既有公司暫停後可恢复，不刪除來源關係',()=>{
 const p=create(memory(),'pool');p.setStatus('2330','paused',known);assert.equal(p.visible('2330'),false);
 p.setStatus('2330','active',known);assert.equal(p.visible('2330'),true);assert.equal(p.read()[0].custom,false);
 assert.throws(()=>p.setStatus('2330','removed',known),/不能刪除/);
});
test('自選移除保留紀錄，恢復時沒有官方資料則仍待回補',()=>{
 const p=create(memory(),'pool');p.add('1234','需求',null);const created=p.read()[0].created_at;
 p.setStatus('1234','removed',null);assert.equal(p.requests().requests.length,0);assert.equal(p.visible('1234'),false);
 p.setStatus('1234','active',null);assert.equal(p.read()[0].status,'pending');assert.equal(p.read()[0].created_at,created);
});
test('加入已知公司使用來源名称，重複操作被拒絕',()=>{
 const p=create(memory(),'pool');p.add('2330','任意名稱',known);assert.equal(p.read()[0].name,'來源公司');
 assert.throws(()=>p.add('2330','',known),/重複/);assert.equal(p.read().length,1);
});
test('不同分頁更新合併最新保存狀態',()=>{
 const s=memory(),a=create(s,'pool'),b=create(s,'pool');a.add('1234','甲',null);b.add('5678','乙',null);
 assert.equal(a.read().length,2);a.setStatus('1234','paused',null);assert.equal(b.read()[1].ticker,'5678');
});
test('損壞紀錄保留，不以空清單覆寫',()=>{
 const s=memory();s.setItem('pool','{bad');const p=create(s,'pool');
 assert.throws(()=>p.add('1234','甲',null),/損壞/);assert.equal(s.getItem('pool'),'{bad');
});
test('儲存失敗回報錯誤，沒有假成功',()=>{
 const s=memory(),p=create({...s,setItem(){throw new Error('quota');}},'pool');
 assert.throws(()=>p.add('1234','甲',null),/儲存失敗/);assert.deepEqual(p.read(),[]);
});
test('不合法代號、狀態與重複紀錄停止寫入',()=>{
 const s=memory(),p=create(s,'pool');assert.throws(()=>p.add('2330<script>','甲',null),/四碼/);
 p.add('1234','甲',null);const data=JSON.parse(s.getItem('pool'));data.records.push(data.records[0]);s.setItem('pool',JSON.stringify(data));
 assert.throws(()=>p.read(),/不合法/);
 data.records=[{...data.records[0],ticker:1234}];s.setItem('pool',JSON.stringify(data));assert.throws(()=>p.read(),/不合法/);
});
test('專案／來源儲存鍵互相隔離',()=>{
 const s=memory(),a=create(s,'/project-a/'),b=create(s,'/project-b/');a.add('1234','甲',null);assert.deepEqual(b.read(),[]);
});

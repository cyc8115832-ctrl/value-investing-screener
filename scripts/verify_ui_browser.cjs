/* 真實頁面操作與手機尺寸回歸；使用隔離 DB 或本機靜態預覽，非真機验收。 */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const base=process.argv[2]||'http://127.0.0.1:8779';
const mode=process.argv[3]||'local';
const folder=path.resolve(process.argv[4]||'reports/2026-10-12/UI畫面');fs.mkdirSync(folder,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:390,height:844},serviceWorkers:'block',acceptDownloads:true});
 context.setDefaultTimeout(120000);
 const page=await context.newPage(),errors=[],initialRequests=[];
 const started=Date.now();let initialLoading=true;
 page.on('request',request=>{if(initialLoading&&new URL(request.url()).pathname.startsWith('/api/'))initialRequests.push(new URL(request.url()).pathname);});
 page.on('pageerror',e=>errors.push(e.message));
 async function nav(index){await page.locator('.nav-tab-btn').nth(index).click();}
 async function overflow(label){const result=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));assert(result.scroll<=result.width+1,`${label} 橫向溢出 ${JSON.stringify(result)}`);}
 await page.goto(base,{waitUntil:'domcontentloaded'});await page.locator('[data-action="growth"]').waitFor();
 const initialLoadSeconds=(Date.now()-started)/1000;initialLoading=false;
 assert.equal(await page.locator('[data-action="stock"][data-ticker="2330"]').count(),0,'雷達不應固定推薦台積電');
 await overflow('雷達');await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(folder,mode+'-雷達-390.png'),fullPage:true});
 await page.locator('[data-action="growth"]').click();
 await page.locator('[data-action="company-filter"]').first().waitFor();
 assert.equal(await page.locator('#valueFilter').inputValue(),'growth');
 await page.locator('[data-action="company-filter"][data-filter="good"]').click();
 await page.locator('#valueResults').getByText('沒有符合公司體質與價格交集').waitFor();
 await page.locator('[data-action="company-filter"][data-filter="all"]').click();
 await page.locator('#tab-screener summary').filter({hasText:'查看營收與風險線索'}).click();await page.selectOption('#valueFilter','all');
 await page.locator('#valueSearch').fill('2330');await page.locator('#valueSearch').press('Enter');
 await page.locator('#valueResults [data-action="stock"][data-ticker="2330"]').waitFor();
 assert.equal(await page.locator('#valueResults [data-action="stock"]').count(),1);
 await overflow('選股');await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(folder,mode+'-選股-390.png'),fullPage:true});
 await page.locator('[data-action="watch-add-list"][data-ticker="2330"]').click();
 await page.locator('#value-list-save-2330').getByText('已儲存').waitFor();
 await page.locator('[data-action="pool-toggle"]').click();
 await page.fill('#valueAddTicker','2330');await page.locator('[data-action="pool-add"]').click();
 await page.locator('#valuePoolStatus').getByText('已加入本裝置自選追蹤').waitFor();
 await page.locator('#valueResults [data-action="pool-pause"]').click();
 await page.locator('#valuePoolStatus').getByText('已暫停').waitFor();assert.equal(await page.locator('#valueResults [data-action="stock"]').count(),0);
 await page.locator('[data-action="pool-restore"][data-ticker="2330"]').click();
 await page.locator('#valueResults [data-action="stock"]').waitFor();
 await page.locator('[data-action="pool-remove"][data-ticker="2330"]').click();
 await page.locator('#valuePoolStatus').getByText('已移除自選關係').waitFor();
 await nav(3);await page.locator('textarea[id^="value-note-"]').first().waitFor();
 assert((await page.locator('#tab-watchlist').innerText()).includes('2330'),'移除追蹤不應刪觀察');
 await page.locator('textarea[id^="value-note-"]').first().fill('測試筆記 <文字> & 保留');
 await page.locator('[data-action="note-save"]').first().click();await page.locator('[id^="note-status-"]').first().getByText('已儲存').waitFor();
 await nav(1);await page.locator('[data-action="pool-restore"][data-ticker="2330"]').waitFor();
 await page.locator('[data-action="pool-restore"][data-ticker="2330"]').click();
 await page.fill('#valueAddTicker','9999');await page.fill('#valueAddName','<img src=x onerror="window.uiInjected=true">');
 await page.locator('[data-action="pool-add"]').click();await page.locator('#valuePoolStatus').getByText('待核對需求已儲存').waitFor();
 assert.equal(await page.evaluate(()=>window.uiInjected),undefined,'名稱須以文字呈現');
 const downloadPromise=page.waitForEvent('download');await page.locator('[data-action="pool-export"]').click();
 const download=await downloadPromise,exported=JSON.parse(fs.readFileSync(await download.path(),'utf8'));
 assert.equal(exported.requests[0].ticker,'9999');assert(!JSON.stringify(exported).includes('測試筆記'));
 await page.reload({waitUntil:'domcontentloaded'});await nav(1);await page.locator('[data-action="pool-toggle"]').click();
 await page.locator('.value-pending').waitFor();assert((await page.locator('.value-pending').innerText()).includes('9999'));
 await page.locator('[data-action="pool-remove"][data-ticker="9999"]').click();await page.locator('#valuePoolStatus').getByText('已移除').waitFor();
 await page.locator('[data-action="pool-restore"][data-ticker="9999"]').click();await page.locator('.value-pending').waitFor();
 await page.fill('#valueSearch','2330');await page.locator('#valueSearch').press('Enter');await page.locator('#valueResults [data-action="stock"]').click();
 await page.locator('[data-action="subtab"][data-page="river"]').first().click();
 await page.locator('#valueMetric').waitFor({state:'attached'});
 const suggested=await page.locator('#dsub-river .value-number').first().innerText();
 assert(suggested.includes('P/E'),'2330 既有規則應建議 P/E');
 assert.equal(await page.locator('#valueMetric').isVisible(),false,'初次進入不要求選指標');
 await page.locator('#dsub-river summary').filter({hasText:'查看其他估值指標'}).click();
 await page.selectOption('#valueMetric','ps');await page.locator('#dsub-river .value-number').getByText('P/S').waitFor();
 assert.equal(await page.locator('#dsub-river .value-range').count(),0,'PS 缺資料不能沿用 PE 區間');
 await page.locator('[data-action="metric-reset"]').click();await page.locator('#dsub-river .value-number').getByText('P/E').waitFor();
 await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(folder,mode+'-估值-390.png'),fullPage:true});
 for(const stock of ['3105','2330']){
  await page.evaluate(t=>window.viewStock(t),stock);await page.locator('.value-sticky [data-quote-ticker="'+stock+'"]').waitFor();
  const quoteText=await page.locator('.value-sticky .value-quote').innerText();
  for(const sub of ['conclusion','fundamentals','river','eps','chips','ai']){
   await page.locator('.value-subtabs [data-action="subtab"][data-page="'+sub+'"]').click();
   assert.equal((await page.locator('#dsub-'+sub+' > .value-quote').innerText()).replace(/\s+/g,''),quoteText.replace(/\s+/g,''));
   await overflow(stock+' '+sub);
  }
 }
 await nav(4);await page.getByText('快速操作說明',{exact:true}).waitFor();await overflow('設定');
 await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(folder,mode+'-設定-390.png'),fullPage:true});
 await page.evaluate(()=>{document.body.classList.add('elder-mode');document.documentElement.style.fontSize='22px';});
 for(const width of [320,390,430]){
  await page.setViewportSize({width,height:844});
  for(let i=0;i<5;i++){await nav(i);await page.waitForTimeout(200);await overflow('大字模式 '+width+' 頁'+i);}
 }
 assert.deepEqual(errors,[],'瀏覽器不可有執行錯誤');
 await context.close();
 const blocked=await browser.newContext({viewport:{width:390,height:844},serviceWorkers:'block'});
 await blocked.addInitScript(()=>{Storage.prototype.setItem=function(){throw new Error('quota');};});
 blocked.setDefaultTimeout(120000);
 const blockedPage=await blocked.newPage();await blockedPage.goto(base,{waitUntil:'domcontentloaded'});
 await blockedPage.locator('.nav-tab-btn').nth(1).click();await blockedPage.locator('[data-action="pool-toggle"]').click();
 await blockedPage.fill('#valueAddTicker','9999');await blockedPage.fill('#valueAddName','儲存失敗測試');
 await blockedPage.locator('[data-action="pool-add"]').click();await blockedPage.locator('#valuePoolStatus').getByText('儲存失敗').waitFor();
 assert.equal(await blockedPage.locator('.value-pending').count(),0);
 await blocked.close();await browser.close();
 const report={mode,passed:true,initial_load_seconds:initialLoadSeconds,initial_api_requests:initialRequests,browser:'Playwright Chromium',widths:[320,390,430],checks:['雷達入口','體質與價格交集','搜尋','觀察與筆記保留','股池加入／暫停／恢復／移除','需求持久保存與匯出','名稱跳脫','預設估值／切換／恢復','缺PS資料不沿用PE','六頁同價日期與換股','大字無溢出','儲存失敗無假成功'],runtime_errors:errors,boundary:'隔離資料庫或本機静態快照瀏覽器驗證，非手機真機與線上部署驗收'};
 fs.writeFileSync(path.join(folder,mode+'-瀏覽器查核.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exit(1);});

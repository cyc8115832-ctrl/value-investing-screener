/* 核對摘要與明細分層；完整數字與未知原因仍可展開。 */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base=process.argv[2]||'http://127.0.0.1:8879';
(async()=>{
 const browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:390,height:844},serviceWorkers:'block'});
 const page=await context.newPage(),errors=[],requests=[];
 page.on('pageerror',error=>errors.push(error.message));
 page.on('request',request=>requests.push(new URL(request.url()).pathname));
 await page.goto(base,{waitUntil:'domcontentloaded'});
 await page.locator('[data-action="growth"]').waitFor({timeout:30000});
 await page.evaluate(()=>window.viewStock('2330'));
 await page.locator('.value-sticky [data-quote-ticker="2330"]').waitFor();
 assert.equal(requests.some(path=>path.endsWith('history-2330.json')||path.endsWith('/stocks/2330/history')),false,'結論頁不應下載完整歷史');
 const quote=await page.locator('.value-sticky .value-quote').innerText();
 await page.locator('.value-subtabs [data-page="fundamentals"]').click();
 const panel=page.locator('#dsub-fundamentals');
 await panel.getByRole('heading',{name:'公司體質摘要',exact:true}).waitFor();
 assert.equal(requests.some(path=>path.endsWith('history-2330.json')||path.endsWith('/stocks/2330/history')),false,'基本面摘要不應下載完整歷史');
 const financial=panel.locator('[data-financial-details]'),history=panel.locator('[data-history-details]'),pending=panel.locator('[data-pending-factors]');
 for(const details of [financial,history,pending])assert.equal(await details.evaluate(node=>node.open),false);
 assert.equal(await history.locator('table').isVisible(),false);
 await history.locator('summary').click();await history.locator('table').waitFor();assert.equal(await history.locator('table').isVisible(),true);
 assert(requests.some(path=>path.endsWith('history-2330.json')||path.endsWith('/stocks/2330/history')),'展開歷史後應載入完整資料');
 assert(await history.locator('tbody tr').count()>20);
 await history.locator('summary').click();
 await financial.locator('summary').click();await financial.getByRole('heading',{name:/資產負債快照/}).waitFor();
 assert(await financial.locator('a').count()>=1);await financial.locator('summary').click();
 await pending.locator('summary').click();assert(await pending.locator('li').count()>=1);await pending.locator('summary').click();
 assert.equal((await panel.locator('> .value-quote').innerText()).replace(/\s+/g,''),quote.replace(/\s+/g,''));
 for(const width of [320,390,430]){
  await page.setViewportSize({width,height:844});
  await page.evaluate(()=>{document.body.classList.add('elder-mode');document.documentElement.style.fontSize='22px';});
  const dimensions=await page.evaluate(()=>({viewport:innerWidth,content:document.documentElement.scrollWidth}));
  assert(dimensions.content<=dimensions.viewport+1);
 }
 await page.setViewportSize({width:390,height:844});await page.evaluate(()=>window.scrollTo(0,0));
 const folder='reports/2026-10-13/App濃縮畫面';fs.mkdirSync(folder,{recursive:true});
 await page.screenshot({path:folder+'/基本面摘要-390.png',fullPage:true});
 assert.deepEqual(errors,[]);
 fs.writeFileSync(folder+'/濃縮操作查核.json',JSON.stringify({passed:true,checks:['結論與基本面摘要不預載歷史','展開歷史後才下載','公司摘要優先','灰色項目預設收合且原因保留','財報原值與來源可展開','歷史表預設收合且完整列保留','現價與日期不變','320／390／430大字無溢出'],runtime_errors:errors},null,2));
 await browser.close();console.log('摘要、財報來源與歷史明細展開查核通過');
})().catch(error=>{console.error(error);process.exit(1);});

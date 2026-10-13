/* 首頁請求失敗後可重試；不讓清單Promise產生未處理拒絕。 */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:390,height:844},serviceWorkers:'block'});
 const page=await context.newPage(),errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/api/overview',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'測試：資料暫時無法取得'})}));
 await page.goto('http://127.0.0.1:8879',{waitUntil:'domcontentloaded'});
 await page.locator('#tab-radar').getByText('測試：資料暫時無法取得').waitFor();
 await page.unroute('**/api/overview');
 await page.locator('.nav-tab-btn').nth(0).click();
 await page.locator('[data-action="growth"]').waitFor({timeout:20000});
 await page.locator('.nav-tab-btn').nth(1).click();
 await page.locator('#valueResults [data-action="stock"]').first().waitFor();
 assert.deepEqual(errors,[]);
 fs.writeFileSync('reports/2026-10-13/App主程式畫面/首頁失敗重試.json',JSON.stringify({passed:true,runtime_errors:errors,checks:['503失敗可見','重新進入雷達可重試','公司清單恢復','無未處理Promise錯誤']},null,2));
 await browser.close();console.log('首頁失敗與重試通過');
})().catch(error=>{console.error(error);process.exit(1);});

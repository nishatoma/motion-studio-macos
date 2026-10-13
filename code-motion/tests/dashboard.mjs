/** Browser test of the actual local UI. Job responses mocked; backend HTTP has Python tests. */
import {chromium} from 'playwright';import assert from 'node:assert/strict';import {spawn} from 'node:child_process';import fs from 'node:fs';import path from 'node:path';
const app=spawn(process.env.PYTHON||'python',['-c',"from pathlib import Path; import app; app.PORT=8768; app.JOBS_DIR=Path('/tmp/motion-studio-ui-test'); app.main()"],{cwd:path.resolve('..'),stdio:'ignore'});
let browser;
try {
 const executablePath=process.env.REMOTION_BROWSER_EXECUTABLE || path.resolve('node_modules/.remotion/chrome-headless-shell/linux64/chrome-headless-shell-linux64/chrome-headless-shell');
 browser=await chromium.launch({...(process.env.PLAYWRIGHT_USE_DEFAULT?{}:{executablePath}),headless:true,args:['--no-sandbox']});const page=await browser.newPage({viewport:{width:1440,height:1100}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 for(let i=0;i<50;i++){try{await fetch('http://127.0.0.1:8768');break}catch{await new Promise(r=>setTimeout(r,100))}}
 await page.goto('http://127.0.0.1:8768');await page.click('#codeTab');await page.waitForFunction(()=>document.getElementById('cmReadiness').textContent.includes('Docker'));
 assert.equal(await page.locator('#graphicsFields').isVisible(),false);assert.equal(await page.locator('#codeFields').isVisible(),true);
 await page.fill('#cmModel','test-model');await page.selectOption('#cmStyle','overlay');assert.equal(await page.locator('#cmTransparent').isChecked(),true);assert.equal(await page.locator('#cmFormat').inputValue(),'prores');
 await page.locator('#codeFields details').first().locator('summary').click();await page.fill('#cmStyleName','Browser test');await page.fill('#cmStyleDirection','Dark editorial typography');await page.click('#cmSaveStyle');await page.waitForFunction(()=>document.getElementById('status').textContent==='Style saved.');
 await page.route('**/api/code-motion/jobs',async route=>{assert.equal(JSON.parse(route.request().postData()).model,'test-model');await route.fulfill({json:{id:'aaaaaaaaaaaa'}})},{times:1});
 const preview={id:'aaaaaaaaaaaa',action:'generate',status:'complete',progress:1,message:'Preview ready',video:'/example.mp4',design_source:'/Scene.tsx',history:[],design_notes:'Readable alpha overlay',created:1};
 await page.route('**/api/code-motion/jobs/aaaaaaaaaaaa',route=>route.fulfill({json:preview}));
 await page.click('#cmGenerate');await page.waitForSelector('#cmResultControls:not([hidden])');await page.click('#cmExport');assert.match(await page.locator('#status').textContent(),/tick approval/);
 await page.check('#cmApproved');await page.route('**/api/code-motion/jobs/aaaaaaaaaaaa/export',async route=>{assert.equal(JSON.parse(route.request().postData()).approved,true);await route.fulfill({json:{id:'bbbbbbbbbbbb'}})});
 await page.route('**/api/code-motion/jobs/bbbbbbbbbbbb',route=>route.fulfill({json:{...preview,id:'bbbbbbbbbbbb',action:'export',download:'/animation.mov',format:'prores',metadata:{width:1920,height:1080,fps:24,duration:8,pixel_format:'yuva444p12le'}}}));
 await page.click('#cmExport');await page.waitForFunction(()=>document.getElementById('resultActions').textContent.includes('Download prores'));
 await page.click('#graphicsTab');assert.equal(await page.locator('#graphicsFields').isVisible(),true);await page.click('#abstractTab');assert.equal(await page.locator('#abstractFields').isVisible(),true);await page.click('#codeTab');
 fs.mkdirSync('smoke-output',{recursive:true});await page.screenshot({path:'smoke-output/dashboard.png',fullPage:true});assert.deepEqual(errors,[]);console.log('PASS: dashboard tabs, settings, saved styles, preview, approval gate, export link. Render jobs mocked.');
} finally {if(browser)await browser.close();app.kill('SIGTERM')}

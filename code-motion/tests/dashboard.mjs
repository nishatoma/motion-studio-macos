/** Actual local UI and HTTP auth routes; account and render providers are mocked. */
import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
const launcher=`
from pathlib import Path
import time
import app
app.PORT=8768
app.JOBS_DIR=Path('/tmp/motion-studio-ui-test')
studio=app.code_studio()
connected=[False]
studio.subscription.status=lambda:{'installed':True,'signed_in':connected[0],'message':'ChatGPT account connected.' if connected[0] else 'Sign in to connect.'}
def login():
    connected[0]=True
    studio.subscription.login_state={'status':'complete','message':'ChatGPT account connected.'}
    return dict(studio.subscription.login_state)
studio.subscription.sign_in=login
studio.subscription._list_models=lambda:[{'id':'gpt-5.6-sol','name':'GPT-5.6 Sol (account)'},{'id':'gpt-6.1-sol','name':'GPT-6.1 Sol (account)'}]
prepared=[False]
studio.health=lambda:{'ready':prepared[0],'can_setup':True,'auto_prepare':not prepared[0],'message':'Renderer ready.' if prepared[0] else 'Docker is connected. Prepare the renderer once.','docker_connection':'desktop-linux','checks':{'docker_running':True,'linux_containers':True,'renderer_image':prepared[0],'ffprobe':True,'ffmpeg':True},'subscription':studio.subscription.status(),'login':studio.subscription.login_status(),'styles':studio.styles(),'model':'','codex_model':''}
def prepare(root,emit,cancel_event,install_codex=True):
    emit({'stage':'Building renderer','message':'Building the renderer for first use','progress':0.35})
    time.sleep(0.2)
    prepared[0]=True
    emit({'stage':'Ready','message':'Renderer ready','progress':1})
app.code_motion_setup.prepare=prepare
app.main()
`;
const app=spawn(process.env.PYTHON||'python',['-c',launcher],{cwd:path.resolve('..'),stdio:'ignore',env:{...process.env,CODEX_MODEL:'',OPENAI_MODEL:''}});
let browser;
try {
 const executablePath=process.env.REMOTION_BROWSER_EXECUTABLE || path.resolve('node_modules/.remotion/chrome-headless-shell/linux64/chrome-headless-shell-linux64/chrome-headless-shell');
 browser=await chromium.launch({...(process.env.PLAYWRIGHT_USE_DEFAULT?{}:{executablePath}),headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1100}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 for(let i=0;i<50;i++){try{await fetch('http://127.0.0.1:8768');break}catch{await new Promise(r=>setTimeout(r,100))}}
 let releaseHealth;const healthGate=new Promise(resolve=>{releaseHealth=resolve});
 await page.route('**/api/code-motion/health',async route=>{await healthGate;await route.continue()},{times:1});
 await page.goto('http://127.0.0.1:8768');await page.click('#codeTab');
 assert.equal(await page.locator('#cmSignIn').isDisabled(),true);assert.equal(await page.locator('#cmGenerate').isDisabled(),true);
 releaseHealth();
 await page.waitForFunction(()=>document.querySelector('#cmModel option[value="gpt-5.6-sol"]') && !document.getElementById('cmSignIn').disabled);
 assert.equal(await page.locator('#cmProvider').inputValue(),'codex');assert.equal(await page.locator('#cmAccount').isVisible(),true);
 assert.equal(await page.locator('#cmModel').inputValue(),'');
 // The button uses the real token-protected Python endpoint; only the CLI is stubbed.
 const loginResponse=page.waitForResponse(r=>r.url().endsWith('/account/login') && r.request().method()==='POST');
 await page.click('#cmSignIn');assert.equal((await loginResponse).status(),202);
 await page.waitForFunction(()=>document.getElementById('cmModelHint').textContent.includes('signed-in Codex account'));
 assert.match(await page.locator('#cmAccountStatus').textContent(),/connected/);
 assert.equal(await page.locator('#cmModel option[value="gpt-5.6-sol"]').textContent(),'GPT-5.6 Sol (account)');
 assert.equal(await page.locator('#graphicsFields').isVisible(),false);assert.equal(await page.locator('#codeFields').isVisible(),true);
 await page.selectOption('#cmProvider','openai');await page.selectOption('#cmModel','__custom');
 await page.fill('#cmCustomModel','test-model');assert.equal(await page.locator('#cmCustomModel').isVisible(),true);
 await page.selectOption('#cmProvider','codex');await page.selectOption('#cmModel','gpt-5.6-sol');
 assert.equal(await page.locator('#cmCustomModel').isVisible(),false);
 await page.selectOption('#cmStyle','overlay');assert.equal(await page.locator('#cmTransparent').isChecked(),true);assert.equal(await page.locator('#cmFormat').inputValue(),'prores');
 await page.getByText('Save a reusable style',{exact:true}).click();await page.fill('#cmStyleName','Browser test');await page.fill('#cmStyleDirection','Dark editorial typography');await page.click('#cmSaveStyle');
 await page.waitForFunction(()=>document.getElementById('status').textContent==='Style saved.');
 assert.equal(await page.locator('#cmModel').inputValue(),'gpt-5.6-sol');
 await page.route('**/api/code-motion/jobs',async route=>{
   const body=JSON.parse(route.request().postData());assert.equal(body.model,'gpt-5.6-sol');assert.equal(body.provider,'codex');
   await route.fulfill({json:{id:'aaaaaaaaaaaa'}});
 },{times:1});
 const preview={id:'aaaaaaaaaaaa',action:'generate',status:'complete',progress:1,message:'Preview ready',video:'/example.mp4',design_source:'/Scene.tsx',history:[],design_notes:'Readable alpha overlay',created:1};
 await page.route('**/api/code-motion/jobs/aaaaaaaaaaaa',route=>route.fulfill({json:preview}));
 const setupResponse=page.waitForResponse(r=>r.url().endsWith('/code-motion/setup') && r.request().method()==='POST');
 await page.click('#cmGenerate');assert.equal((await setupResponse).status(),202);
 await page.waitForSelector('#cmResultControls:not([hidden])');
 assert.match(await page.locator('#cmSetupLog').textContent(),/first use/);
 assert.match(await page.locator('#cmReadiness').textContent(),/ready/);
 await page.waitForFunction(()=>!document.getElementById('cmRevise').disabled);
 await page.selectOption('#cmModel','gpt-6.1-sol');await page.fill('#cmRevision','Make the counter bigger');
 await page.route('**/api/code-motion/jobs/aaaaaaaaaaaa/revise',async route=>{
   const body=JSON.parse(route.request().postData());assert.equal(body.model,'gpt-6.1-sol');assert.equal(body.provider,'codex');
   await route.fulfill({json:{id:'cccccccccccc'}});
 });
 await page.route('**/api/code-motion/jobs/cccccccccccc',route=>route.fulfill({json:{...preview,id:'cccccccccccc',action:'revise'}}));
 await page.click('#cmRevise');await page.waitForFunction(()=>document.getElementById('resultActions').textContent.includes('Download editable TSX') && !document.getElementById('cmExport').disabled);
 await page.click('#cmExport');assert.match(await page.locator('#status').textContent(),/tick approval/);
 await page.check('#cmApproved');
 await page.route('**/api/code-motion/jobs/cccccccccccc/export',async route=>{
   assert.equal(JSON.parse(route.request().postData()).approved,true);await route.fulfill({json:{id:'bbbbbbbbbbbb'}});
 });
 await page.route('**/api/code-motion/jobs/bbbbbbbbbbbb',route=>route.fulfill({json:{...preview,id:'bbbbbbbbbbbb',action:'export',download:'/animation.mov',format:'prores',metadata:{width:1920,height:1080,fps:24,duration:8,pixel_format:'yuva444p12le'}}}));
 await page.click('#cmExport');await page.waitForFunction(()=>document.getElementById('resultActions').textContent.includes('Download prores'));
 await page.click('#graphicsTab');assert.equal(await page.locator('#graphicsFields').isVisible(),true);
 await page.click('#abstractTab');assert.equal(await page.locator('#abstractFields').isVisible(),true);await page.click('#codeTab');
 const preparedHealth=await (await fetch('http://127.0.0.1:8768/api/code-motion/health')).json();
 let failedSetupJobCalls=0;
 await page.route('**/api/code-motion/health',route=>route.fulfill({json:{...preparedHealth,ready:false,auto_prepare:true}}));
 await page.route('**/api/code-motion/setup',route=>route.fulfill({json:route.request().method()==='POST'?{status:'running'}:{status:'error',message:'Installing dependencies failed (exit 7): download blocked',log:'Exact dependency error: download blocked'}}));
 await page.route('**/api/code-motion/jobs',route=>{failedSetupJobCalls++;return route.fulfill({status:400,json:{error:'Generation must not start after failed setup'}})});
 await page.click('#cmGenerate');await page.waitForFunction(()=>document.getElementById('status').textContent.includes('download blocked'));
 assert.equal(failedSetupJobCalls,0);assert.match(await page.locator('#cmSetupLog').textContent(),/Exact dependency error/);
 await page.unroute('**/api/code-motion/health');await page.unroute('**/api/code-motion/setup');await page.unroute('**/api/code-motion/jobs');
 // A missing route now gives instructions; it no longer surfaces a bare Not found.
 await page.route('**/api/code-motion/account/login',route=>route.fulfill({status:404,json:{error:'Not found'}}));
 await page.click('#cmSignIn');await page.waitForFunction(()=>document.getElementById('cmAccountStatus').textContent.includes('restart start_windows.bat'));
 await page.unroute('**/api/code-motion/account/login');
 const health=await (await fetch('http://127.0.0.1:8768/api/code-motion/health')).json();
 await page.route('**/api/code-motion/health',route=>route.fulfill({json:{...health,api_version:undefined,capabilities:undefined}}));
 await page.click('#cmRefresh');await page.waitForFunction(()=>document.getElementById('cmReadiness').textContent.includes('running Motion Studio server is older'));
 assert.equal(await page.locator('#cmSignIn').isDisabled(),true);assert.equal(await page.locator('#cmGenerate').isDisabled(),true);
 assert.match(await page.locator('#status').textContent(),/restart start_windows.bat/);
 await page.unroute('**/api/code-motion/health');await page.click('#cmRefresh');
 await page.waitForFunction(()=>!document.getElementById('cmSignIn').disabled);
 fs.mkdirSync('smoke-output',{recursive:true});await page.screenshot({path:'smoke-output/dashboard.png',fullPage:true});
 assert.deepEqual(errors,[]);
 console.log('PASS: automatic first-use preparation through real HTTP routes (setup process mocked), setup failure stops generation with exact log, sign-in/model picker, revision models, stale-server checks, tabs, styles, approval and export. Render jobs mocked.');
} finally {if(browser)await browser.close();app.kill('SIGTERM')}

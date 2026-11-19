// Run after a NON-demo Studio build. Uses the same Chromium setup as studio-smoke.cjs.
const fs=require('node:fs'), p=require('puppeteer-core'), chrome=require('@sparticuz/chromium');
(async()=>{
 const browser=await p.launch({args:chrome.args,executablePath:await chrome.executablePath(),headless:true});
 try {
 const page=await browser.newPage(), base='https://studio.test', root='docs/qa/second-pass';
 const evidence={requests:[],screens:{},errors:[]}; let live=false;
 page.on('pageerror',e=>evidence.errors.push(e.message)); await page.setRequestInterception(true);
 page.on('request',r=>{
  if(r.isNavigationRequest() && r.url().startsWith(base+'/'))return r.respond({contentType:'text/html',body:fs.readFileSync('apps/studio/dist/index.html')});
  const path=new URL(r.url()).pathname.replace('/api/v1',''); if(!r.url().startsWith(base+'/api/') || !live)return r.abort();
  evidence.requests.push([r.method(),path,r.postData()||'']);
  if(path==='/agent/chat')return r.respond({contentType:'text/event-stream',body:'event: message\ndata: {"text":"Fixture reply [88]"}\n\n'});
  const data={'/health':{workspace:{status:'open'},llm:{key_configured:true}},'/workspace':{settings:{llm_provider:'api',llm_api_base_url:'https://fixture.invalid/v1',llm_model_id:'qa'}},'/models/versions':{versions:[{key:['rice','north'],version:2,timestamp:'2026-01-01T12:00:00Z',n_samples:32,sha256:'fixture'}]},'/rois':{rois:[]},'/feedback/candidates':[{id:'qa',content:'{"crop_type":"rice","region":"north","label":0,"confidence":0.94}',state:'rejected'}],'/agent/playbooks':{playbooks:[]},'/search':{hits:[]},'/ask':{error:{message:'fixture upstream failure'}}};
  return r.respond({status:path==='/ask'?502:200,contentType:'application/json',body:JSON.stringify(data[path]??[])});
 });
 async function open(view){await page.goto(base+'/?run='+view+'#/'+view);await page.waitForSelector('main');}
 async function snap(name){await page.screenshot({path:`${root}/${name}.jpg`,quality:78});evidence.screens[name]=await page.evaluate(()=>({mainWidth:document.querySelector('main').getBoundingClientRect().width,viewport:innerWidth,text:document.body.innerText.slice(0,6000)}));}
 await page.setViewport({width:390,height:844});await open('settings');await snap('mobile');
 await page.setViewport({width:1440,height:900});await open('training');await snap('offline-training');await open('ops');await snap('offline-ops');await open('settings');await snap('offline-settings');
 live=true;await open('training');await page.waitForFunction(()=>document.body.innerText.includes('rice-north'));await snap('live-training');
 await page.type('aside textarea','Synthetic user question');await page.click('aside button[type=submit]');await page.waitForFunction(()=>document.body.innerText.includes('Fixture reply'));await snap('chat');
 await open('knowledge');const box=await page.$('main textarea')||await page.$('main input');await box.type('Synthetic ask');await page.click('main button');await new Promise(r=>setTimeout(r,300));await snap('failed-ask');
 await open('unknown');await snap('unknown-route');await page.keyboard.down('Control');await page.keyboard.press('k');await page.keyboard.up('Control');await page.waitForSelector('input[autofocus], .fixed input');await page.keyboard.press('Tab');await page.keyboard.press('Escape');await snap('palette-escape');
 fs.writeFileSync(`${root}/observations.json`,JSON.stringify(evidence,null,2)+'\n');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

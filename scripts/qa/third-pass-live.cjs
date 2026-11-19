// Run with NODE_PATH and LD_LIBRARY_PATH as in third-pass.cjs; optional STUDIO_HTML for baseline.
const fs = require('node:fs');
const assert = require('node:assert/strict');
const puppeteer = require('puppeteer-core');
const chromium = require('@sparticuz/chromium');
(async () => {
  const phase = process.argv[2];
  assert(['before','after'].includes(phase));
  const dir = `docs/qa/third-pass/${phase}`;
  const html = fs.readFileSync(process.env.STUDIO_HTML || 'apps/studio/dist/index.html');
  const browser = await puppeteer.launch({args: chromium.args, executablePath: await chromium.executablePath(), headless:true});
  try {
    const page = await browser.newPage();
    await page.setViewport({width:1440,height:900});
    const base='https://studio.test';
    const metrics = {}, errors=[];
    let downloads=0, chatPosts=0, searchFailure=false;
    const rois=['A','B'].map((name,i)=>({id:name,name:`Test parcel ${name}`, kind:'bbox', coords:[[i,0],[i+1,0],[i+1,1],[i,0]],areaHa:10,centroid:[i+.5,.5],createdAt:0}));
    page.on('pageerror',e=>errors.push(e.message));
    await page.setRequestInterception(true);
    page.on('request',async r=>{
      if(r.isNavigationRequest())return r.respond({contentType:'text/html',body:html});
      if(!r.url().startsWith(base+'/api/'))return r.abort();
      const path=new URL(r.url()).pathname.replace('/api/v1','');
      const response=(data,status=200)=>r.respond({status,contentType:'application/json',body:JSON.stringify(data)});
      if(path==='/agent/chat'){chatPosts++;return r.respond({contentType:'text/event-stream',body:'event: message\ndata: {"text":"Lead "}\n\nevent: message\ndata: {"text":"Lead complete","final":true}\n\nevent: done\ndata: {}\n\n'});}
      if(path==='/data/search')return searchFailure?response({error:{message:'fixture failure'}},502):response({scenes:[{scene_id:'LC_QA',datetime:'2024-06-01T16:24:35Z',cloud_cover:5,platform:'landsat-9',bbox:[0,0,2,1]}]});
      if(path==='/data/download'){const id=++downloads;await new Promise(resolve=>setTimeout(resolve,150));return response({job_id:`job-${id}`},202);}
      if(path==='/events')return r.respond({contentType:'text/event-stream',body:': ping\n\n'});
      if(path.startsWith('/jobs/'))return response({id:path.slice(6),status:'completed',percent:100,result:{band_files:{}}});
      return response(({'/health':{workspace:{status:'open'},llm:{key_configured:true}},'/workspace':{path:'/qa/ws',settings:{name:'ws'}},'/workspace/suggestions':{suggestions:[]},'/rois':{rois},'/agent/playbooks':{playbooks:[]},'/models/versions':{versions:[]}})[path]??[]);
    });
    await page.goto(base+'/#/acquire');await page.waitForFunction(()=>document.querySelector('main')?.innerText.includes('Test parcel A'));
    const search=()=>page.locator('button::-p-text(Search scenes)').click();
    const findDownload=()=>page.evaluate(()=>Array.from(document.querySelectorAll('main button')).some(b=>b.textContent.trim()==='Download'));
    await search();await page.waitForFunction(()=>document.querySelector('main').innerText.includes('LC_QA'));
    await page.evaluate(()=>{const btn=Array.from(document.querySelectorAll('main button')).find(b=>b.textContent.trim()==='Download');btn.click();btn.click();});
    await page.waitForFunction(()=>document.body.innerText.includes('202 Accepted'));
    metrics.doubleClickPosts=downloads;
    await page.select('main select','B');await search();await page.waitForFunction(()=>document.querySelector('main').innerText.includes('LC_QA'));
    metrics.sameSceneNewRoiDownload=await findDownload();
    metrics.dateFieldNames=await page.$$eval('main input[type=date]',els=>els.map(e=>e.getAttribute('aria-label')));
    await page.screenshot({path:`${dir}/second-roi.jpg`});
    searchFailure=true;await search();await page.waitForFunction(()=>document.body.innerText.includes('fixture failure'));
    metrics.staleScenes=await page.$eval('main',el=>el.innerText.includes('LC_QA'));
    await page.type('aside textarea','Synthetic fixture question');
    await page.$eval('aside textarea',el=>el.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,isComposing:true})));
    await new Promise(resolve=>setTimeout(resolve,100));metrics.compositionPosts=chatPosts;
    if(!chatPosts)await page.click('aside button[type=submit]');await page.waitForFunction(()=>document.querySelector('aside').innerText.includes('complete'));
    metrics.duplicateFinal=await page.$eval('aside',el=>el.innerText.includes('Lead Lead complete'));
    await page.screenshot({path:`${dir}/stream-complete.jpg`});
    metrics.errors=errors;fs.writeFileSync(`${dir}/live-observations.json`,JSON.stringify(metrics,null,2)+'\n');
    if(phase==='after'){assert.equal(downloads,1);assert(metrics.sameSceneNewRoiDownload);assert(metrics.dateFieldNames.every(Boolean));assert(!metrics.staleScenes);assert.equal(metrics.compositionPosts,0);assert(!metrics.duplicateFinal);assert.deepEqual(errors,[]);}
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});

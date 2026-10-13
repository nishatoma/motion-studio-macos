/** Node rendering service, one isolated job per process. NDJSON progress over stdout. */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {renderMedia, renderFrames, renderStill, selectComposition, openBrowser, makeCancelSignal} from '@remotion/renderer';
import {validate, typecheck} from './validate.mjs';
import {writeEntry} from './project.mjs';
export async function render(project, mode, notify=()=>{}) {
  const config = JSON.parse(fs.readFileSync(path.join(project,'job.json'),'utf8'));
  validate(fs.readFileSync(path.join(project,'Scene.tsx'),'utf8'),config.assets.map(a=>a.file));
  typecheck(project);writeEntry(project, config);
  const moduleRoot=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../node_modules');
  const serveUrl=await bundle({entryPoint:path.join(project,'index.tsx'),publicDir:path.join(project,'public'),outDir:path.join(project,'bundle'),webpackOverride: c=>({...c,resolve:{...c.resolve,modules:[moduleRoot,'node_modules']}})});
  notify({stage:'bundled',progress:0.1});
  const browserExecutable=process.env.REMOTION_BROWSER_EXECUTABLE || undefined;
  const browser=await openBrowser('chrome',{browserExecutable,chromiumOptions:{gl:'swangle'}});
  const {cancelSignal,cancel}=makeCancelSignal();
  const stop=()=>cancel();process.once('SIGTERM',stop);process.once('SIGINT',stop);
  try {
    const composition=await selectComposition({serveUrl,id:'CodeMotion',puppeteerInstance:browser});
    const common={serveUrl,composition,puppeteerInstance:browser,concurrency:2,timeoutInMilliseconds:30000,cancelSignal,chromiumOptions:{gl:'swangle'}};
    if(mode==='preview') {
      const scale=Math.min(1,640/config.width,640/config.height);
      await renderMedia({...common,codec:'h264',pixelFormat:'yuv420p',scale,crf:25,outputLocation:path.join(project,'preview.mp4'),onProgress:p=>notify({stage:'preview',progress:0.1+p.progress*0.8})});
      // Exact-frame sampling includes start/end, beat boundaries, neighboring transition frames.
      const frames=new Set([0,Math.floor(config.durationInFrames*0.1),Math.floor(config.durationInFrames*0.25),Math.floor(config.durationInFrames*0.5),Math.floor(config.durationInFrames*0.75),config.durationInFrames-1,...config.reviewFrames,...config.beats.flatMap(b=>[b.frame-1,b.frame,b.frame+1])]);
      const allFrames=[...frames].filter(f=>f>=0&&f<config.durationInFrames).sort((a,b)=>a-b);
      const chosen=allFrames.length<=24?allFrames:Array.from({length:24},(_,i)=>allFrames[Math.round(i*(allFrames.length-1)/23)]);
      fs.rmSync(path.join(project,'frames'),{recursive:true,force:true});
      fs.mkdirSync(path.join(project,'frames'),{recursive:true});
      for(const frame of chosen) await renderStill({...common,frame,scale,imageFormat:'png',output:path.join(project,'frames',`${frame}.png`)});
      fs.writeFileSync(path.join(project,'frames.json'),JSON.stringify(chosen));
    } else if (mode==='png') {
      await renderFrames({...common,imageFormat:'png',outputDir:path.join(project,'sequence'),onFrameUpdate:(rendered)=>notify({stage:'export',progress:rendered/config.durationInFrames})});
    } else {
      const alpha=mode==='prores';
      await renderMedia({...common,codec:alpha?'prores':'h264',pixelFormat:alpha?'yuva444p10le':'yuv420p',imageFormat:alpha?'png':'jpeg',...(alpha?{proResProfile:'4444',audioCodec:'pcm-16'}:{crf:mode==='hq'?16:20,audioCodec:'aac'}),outputLocation:path.join(project,alpha?'animation.mov':'animation.mp4'),onProgress:p=>notify({stage:'export',progress:p.progress})});
    }
    notify({stage:'complete',progress:1});
  } finally {process.removeListener('SIGTERM',stop);process.removeListener('SIGINT',stop);await browser.close({silent:true});}
}
if(process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  render(path.resolve(process.argv[2]),process.argv[3],v=>console.log(JSON.stringify(v))).catch(e=>{console.error(e.stack);process.exitCode=1});
}

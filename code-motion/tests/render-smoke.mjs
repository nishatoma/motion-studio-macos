/** Runs ONLY checked-in trusted fixtures on the host. Never an app fallback. */
import os from 'node:os';
// Some hosted test runners deny interface enumeration. This is a fixture-only shim.
try { os.networkInterfaces(); } catch(e) {
 if(e.code!=='ERR_SYSTEM_ERROR')throw e;
 console.log('Test environment: using loopback interface metadata; OS interface enumeration is unavailable.');
 os.networkInterfaces=()=>({lo:[{address:'127.0.0.1',netmask:'255.0.0.0',family:'IPv4',mac:'00:00:00:00:00:00',internal:true,cidr:'127.0.0.1/8'}]});
}
import fs from 'node:fs';import path from 'node:path';import {spawnSync} from 'node:child_process';import assert from 'node:assert/strict';
import {render} from '../src/worker.mjs';
const root=path.resolve('smoke-output');fs.mkdirSync(root,{recursive:true});
function probe(file){const p=spawnSync('ffprobe',['-v','error','-show_streams','-show_format','-of','json',file],{encoding:'utf8'});assert.equal(p.status,0,p.stderr);return JSON.parse(p.stdout)}
const cases=[{name:'financial',seconds:8,width:1280,height:720,mode:'mp4'},{name:'kinetic',seconds:6,width:1920,height:1080,mode:'hq'},{name:'overlay',seconds:3,width:1280,height:720,mode:'prores',transparent:true},{name:'audio',seconds:5,width:1280,height:720,mode:'mp4',audio:'track.wav'}];
cases.push({name:'4k',fixture:'kinetic',seconds:1,width:3840,height:2160,mode:'mp4'},{name:'vertical',fixture:'kinetic',seconds:1,width:1080,height:1920,mode:'mp4'});
const results=[];
for(const c of cases){
 const project=path.join(root,c.name);fs.mkdirSync(path.join(project,'public'),{recursive:true});
 fs.copyFileSync(new URL(`../examples/${c.fixture||c.name}.tsx`,import.meta.url),path.join(project,'Scene.tsx'));
 const assets=c.audio?[{file:c.audio,kind:'audio'}]:[];
 const beats=c.name==='audio'?[{frame:12,time:.5,label:'TITLE'},{frame:48,time:2,label:'IMPACT'},{frame:96,time:4,label:'REVEAL'}]:[];
 if(c.audio){
  const rate=44100,samples=rate*5,data=Buffer.alloc(44+samples*2);data.write('RIFF');data.writeUInt32LE(data.length-8,4);data.write('WAVEfmt ',8);data.writeUInt32LE(16,16);data.writeUInt16LE(1,20);data.writeUInt16LE(1,22);data.writeUInt32LE(rate,24);data.writeUInt32LE(rate*2,28);data.writeUInt16LE(2,32);data.writeUInt16LE(16,34);data.write('data',36);data.writeUInt32LE(samples*2,40);
  for(let i=0;i<samples;i++){const t=i/rate;let sample=0;for(const b of beats){const dt=t-b.time;if(dt>=0&&dt<.14)sample+=Math.sin(2*Math.PI*110*dt)*Math.exp(-dt*28)*.6}data.writeInt16LE(Math.round(sample*32767),44+i*2)}fs.writeFileSync(path.join(project,'public',c.audio),data);
 }
 const config={...c,fps:24,durationInFrames:c.seconds*24,assets,beats,reviewFrames:[12,24],transparent:!!c.transparent};fs.writeFileSync(path.join(project,'job.json'),JSON.stringify(config));
 console.log('Rendering',c.name);await render(project,'preview');await render(project,c.mode);
 const output=path.join(project,c.mode==='prores'?'animation.mov':'animation.mp4'),info=probe(output),video=info.streams.find(s=>s.codec_type==='video');
 assert.equal(video.width,c.width);assert.equal(video.height,c.height);assert.equal(video.r_frame_rate,'24/1');assert.ok(Math.abs(Number(info.format.duration)-c.seconds)<.05);
 if(c.transparent){assert.equal(video.codec_name,'prores');assert.match(video.pix_fmt,/a/);const alpha=spawnSync('ffmpeg',['-v','error','-i',output,'-vf','alphaextract,signalstats,metadata=print:file=-','-frames:v','1','-f','null','-'],{encoding:'utf8'});assert.equal(alpha.status,0,alpha.stderr);assert.match(alpha.stdout,/YMIN=0/);}
 if(c.audio){
  assert.ok(info.streams.some(s=>s.codec_type==='audio'));
  const decoded=spawnSync('ffmpeg',['-v','error','-i',output,'-f','s16le','-ac','1','-ar','44100','pipe:1']);assert.equal(decoded.status,0);
  function rms(t){let sum=0;for(let i=Math.round(t*44100);i<Math.round((t+.1)*44100);i++)sum+=decoded.stdout.readInt16LE(i*2)**2;return Math.sqrt(sum/4410)}
  for(const b of beats)assert.ok(rms(b.time)>rms(b.time+.3)*20+100,`Audio hit at ${b.time}s`);
 }
 results.push({name:c.name,status:'passed',output,...video,duration:info.format.duration});
}
// Also validate transparent PNG sequence for the overlay.
await render(path.join(root,'overlay'),'png');const files=fs.readdirSync(path.join(root,'overlay','sequence')).filter(f=>f.endsWith('.png'));assert.equal(files.length,72);
fs.writeFileSync(path.join(root,'results.json'),JSON.stringify(results,null,2));console.log('PASS: A–D metadata, audio stream, ProRes alpha, PNG frame count.');

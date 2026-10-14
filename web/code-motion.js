/* Extends the existing dashboard; generated code is never evaluated in this page. */
(() => {
  let token='', currentJob=null, previewJob=null, assets=[], audio=null, cmHealth=null, compatible=false, modelCatalog=null, preparing=false;
  const expectedApi=Number(document.querySelector('meta[name="motion-studio-api-version"]').content);
  const restartMessage='The dashboard was updated, but the running Motion Studio server is older. Close its command window, restart start_windows.bat (or start.command), then reload this page.';
  const controls=['cmGenerate','cmRevise','cmRegenerate','cmExport'];
  controls.forEach(id=>$(id).disabled=true);
  async function request(url,body,headers={}) {
    const response=await fetch(url,{method:'POST',headers:{'X-Code-Motion-Token':token,'Content-Type':'application/json',...headers},body:body instanceof File?body:JSON.stringify(body)});
    const data=await response.json();if(!response.ok)throw Error(response.status===404 && (url.includes('/account/')||url.includes('/setup'))?restartMessage:data.error||'Code Motion request failed');return data;
  }
  async function refresh() {
    const r=await fetch('/api/code-motion/health');if(!r.ok)throw Error('Code Motion backend unavailable');cmHealth=await r.json();token=cmHealth.token;
    compatible=cmHealth.api_version>=expectedApi && ['subscription-login','model-picker','renderer-prepare'].every(c=>cmHealth.capabilities?.includes(c));
    $('cmSignIn').disabled=!compatible;
    controls.forEach(id=>$(id).disabled=!compatible||busy);
    if(!compatible){$('cmAccountStatus').textContent=restartMessage;$('cmReadiness').textContent=restartMessage;showStatus(restartMessage,'err');return false}
    $('cmReadiness').textContent=cmHealth.message;
    diagnostics();
    $('cmAccountStatus').textContent=cmHealth.subscription?.message||'Sign in with ChatGPT.';
    $('cmSignIn').disabled=cmHealth.login?.status==='running';
    providerHint();
    await loadModels();
    const old=$('cmStyle').value;$('cmStyle').replaceChildren();
    for(const [id,style] of Object.entries(cmHealth.styles)) {const option=document.createElement('option');option.value=id;option.textContent=style.name;$('cmStyle').append(option)}
    if([...$('cmStyle').options].some(o=>o.value===old))$('cmStyle').value=old;
    await history();return true;
  }
  function diagnostics(){
    $('cmReadiness').textContent=cmHealth.message;
    $('cmDiagnostics').textContent=`Connection: ${cmHealth.docker_connection||'default'}\n`+Object.entries(cmHealth.checks||{}).map(([name,ready])=>`${ready?'✓':'✗'} ${name.replaceAll('_',' ')}`).join('\n')+(cmHealth.diagnostics?'\n\n'+cmHealth.diagnostics:'');
  }
  async function checkRenderer(){
    const response=await fetch('/api/code-motion/health');if(!response.ok)throw Error('Could not check the renderer connection.');
    cmHealth=await response.json();token=cmHealth.token;diagnostics();
    if(cmHealth.api_version<expectedApi||!cmHealth.capabilities?.includes('renderer-prepare'))throw Error(restartMessage);
  }
  async function prepareRenderer(){
    if(!compatible)throw Error(restartMessage);
    preparing=true;$('cmSetup').disabled=true;$('cmSetupCancel').hidden=false;$('cmSetupDetails').open=true;
    showStatus('Preparing the animation renderer. Docker is already connected; first use can take several minutes.');
    try{
      await request('/api/code-motion/setup',{provider:$('cmProvider').value});
      while(true){
        const response=await fetch('/api/code-motion/setup');if(!response.ok)throw Error('Could not read renderer preparation progress.');
        const setup=await response.json();$('cmSetupLog').textContent=setup.log||setup.message;$('cmProgress').value=setup.progress||0;showStatus(setup.message,setup.status==='error'?'err':'');
        if(setup.status==='error'||setup.status==='cancelled')throw Error(setup.message);
        if(setup.status==='complete')break;
        await new Promise(resolve=>setTimeout(resolve,1000));
      }
      await checkRenderer();
    }finally{preparing=false;$('cmSetup').disabled=false;$('cmSetupCancel').hidden=true}
  }
  async function history() {
    const r=await fetch('/api/code-motion/jobs'),data=await r.json();const select=$('cmHistory'),old=select.value;select.replaceChildren(new Option('Choose a saved job',''));
    for(const job of data.jobs||[])select.append(new Option(`${new Date(job.created*1000).toLocaleString()} · ${job.action} · ${job.status}`,job.id));select.value=old;
  }
  function input() {
    return {auto_metadata:$('cmAutoMetadata').checked,prompt:$('cmPrompt').value.trim(),provider:$('cmProvider').value,model:selectedModel(),duration:Number($('cmDuration').value),fps:Number($('cmFps').value),resolution:$('cmResolution').value,aspect:$('cmAspect').value,style:$('cmStyle').value,transparent:$('cmTransparent').checked,auto_review:$('cmAutoReview').checked,max_revisions:Number($('cmAttempts').value),beats:JSON.parse($('cmBeats').value||'[]'),assets:assets.map(a=>a.id),audio:audio?.id||null};
  }
  function locked(value){setBusy(value);controls.forEach(id=>$(id).disabled=value||!compatible);$('cmAssets').disabled=value;$('cmAudio').disabled=value;$('cmCancel').hidden=!value;$('cmProgress').hidden=!value;}
  async function upload(file){return request('/api/code-motion/assets',file,{'Content-Type':'application/octet-stream','X-Filename':encodeURIComponent(file.name)})}
  $('cmAssets').addEventListener('change',async()=>{
    if(busy)return;locked(true);showStatus('Validating reference assets…');
    try{const files=[...$('cmAssets').files];if(files.length>12)throw Error('Choose up to 12 references.');const uploaded=[];for(const f of files)uploaded.push(await upload(f));assets=uploaded;$('cmAssetList').textContent=assets.map(a=>a.name).join(', ');showStatus('Reference assets ready.','ok')}catch(e){showStatus(e.message,'err')}finally{locked(false)}
  });
  $('cmAudio').addEventListener('change',async()=>{if(busy)return;locked(true);try{audio=$('cmAudio').files[0]?await upload($('cmAudio').files[0]):null;showStatus(audio?'Audio ready: '+audio.name:'Audio removed.','ok')}catch(e){audio=null;showStatus(e.message,'err')}finally{locked(false)}});
  $('codeTab').addEventListener('click',()=>showMode('code'));
  $('cmAutoMetadata').addEventListener('change',()=>{for(const id of ['cmDuration','cmFps','cmResolution','cmAspect'])$(id).disabled=$('cmAutoMetadata').checked});
  function providerHint(){
    const provider=$('cmProvider').value,ollama=provider==='ollama',codex=provider==='codex';
    $('cmAccount').hidden=!codex;
    $('cmAutoReview').disabled=ollama;if(ollama)$('cmAutoReview').checked=false;
    $('cmProviderHint').textContent=codex?'Uses your ChatGPT subscription through Codex. No API key; subscription limits apply. References and Auto Review use the same account. Sign in once using the button above.':ollama?'Ollama runs locally. Choose an installed coding model; image references require vision support.':'OpenAI API requires OPENAI_API_KEY on the backend and is billed separately from ChatGPT. References and review frames are sent to OpenAI.';
  }
  function selectedModel(){return $('cmModel').value==='__custom'?$('cmCustomModel').value.trim():$('cmModel').value}
  function customField(){ $('cmCustomModel').hidden=$('cmModel').value!=='__custom'; }
  function populateModels(preferred=null){
    const provider=$('cmProvider').value;
    const previous=preferred===null?selectedModel():preferred;
    const models=provider==='ollama'?(health?.models||[]).map(id=>({id,name:id})):(modelCatalog?.models||[]);
    $('cmModel').replaceChildren(new Option(provider==='codex'?'Automatic · Codex default':'Choose a model',''));
    for(const model of models)$('cmModel').append(new Option(model.name,model.id));
    $('cmModel').append(new Option('Custom model ID…','__custom'));
    if(previous && !models.some(m=>m.id===previous)){$('cmCustomModel').value=previous;$('cmModel').value='__custom'}else $('cmModel').value=previous||'';
    $('cmModelHint').textContent=provider==='ollama'?'Installed Ollama models.':provider==='codex'?(modelCatalog?.message||'Model availability depends on your account.'):'Presets are shown; API model availability may differ. Use Custom model ID for other API models.';
    customField();
  }
  async function loadModels(){
    const r=await fetch('/api/code-motion/models');
    if(!r.ok)throw Error(r.status===404?restartMessage:'Could not load model choices.');
    modelCatalog=await r.json();
    populateModels(selectedModel()||($('cmProvider').value==='codex'?cmHealth?.codex_model:$('cmProvider').value==='openai'?cmHealth?.model:null)||'');
  }
  $('cmModel').addEventListener('change',customField);
  $('cmProvider').addEventListener('change',()=>{
    const provider=$('cmProvider').value;
    populateModels(provider==='ollama'?(health?.models?.[0]||''):provider==='codex'?(cmHealth?.codex_model||''):(cmHealth?.model||''));providerHint();
  });
  $('cmRefresh').addEventListener('click',async()=>{try{if(await refresh())showStatus(cmHealth.message,cmHealth.ready?'ok':'')}catch(e){showStatus(e.message,'err')}});
  $('cmSignIn').addEventListener('click',async()=>{
    if(busy)return;
    if(!compatible){$('cmAccountStatus').textContent=restartMessage;return}
    $('cmSignIn').disabled=true;
    try{
      if(!cmHealth?.subscription?.installed){locked(true);await prepareRenderer()}
      const start=await request('/api/code-motion/account/login',{});$('cmAccountStatus').textContent=start.message;
      while(true){const r=await fetch('/api/code-motion/account');if(!r.ok)throw Error(r.status===404?restartMessage:'Could not check sign-in status.');const account=await r.json();$('cmAccountStatus').textContent=account.message;if(account.status!=='running')break;await new Promise(resolve=>setTimeout(resolve,1500))}
      await refresh();
    }catch(e){$('cmAccountStatus').textContent=e.message}finally{$('cmSignIn').disabled=!compatible;if(busy)locked(false)}
  });
  $('cmSetup').addEventListener('click',async()=>{
    if(busy)return;locked(true);
    try{await prepareRenderer();await refresh();showStatus(cmHealth.message,cmHealth.ready?'ok':'')}
    catch(e){showStatus(e.message,'err');$('cmSetupDetails').open=true}finally{locked(false)}
  });
  $('cmSetupCancel').addEventListener('click',async()=>{try{await request('/api/code-motion/setup/cancel',{});showStatus('Cancelling renderer preparation…')}catch(e){showStatus(e.message,'err')}});
  $('cmResolution').addEventListener('change',()=>{$('cmAspect').value=$('cmResolution').value==='vertical'?'9:16':'16:9'});
  $('cmStyle').addEventListener('change',()=>{if($('cmStyle').value==='vertical'){$('cmResolution').value='vertical';$('cmAspect').value='9:16'}if($('cmStyle').value==='overlay'){$('cmTransparent').checked=true;$('cmFormat').value='prores'}});
  $('cmTransparent').addEventListener('change',()=>{if($('cmTransparent').checked)$('cmFormat').value='prores'});
  function player(container,url){const video=document.createElement('video');video.controls=true;video.playsInline=true;video.src=url;container.replaceChildren(video)}
  async function display(job) {
    $('cmProgress').value=job.progress||0;showStatus(job.message||job.status,job.status==='error'?'err':job.status==='complete'?'ok':'');
    await showDetails(job);
    if(job.status!=='complete')return;
    const result=$('resultActions');result.replaceChildren();
    $('cmReview').textContent=(job.design_notes?job.design_notes+'\n\n':'')+(job.history||[]).map(h=>`Inspection ${h.attempt+1}:\n${h.feedback.join('\n')}`).join('\n\n');if(!job.history?.length)$('cmReview').textContent+='Auto Review disabled. Approve this scene manually.';
    if(job.warnings?.length)$('cmReview').textContent+='\n\nObjective checks:\n'+job.warnings.join('\n');
    if(job.action==='export') {
      const link=document.createElement('a');link.className='linkbtn';link.href=job.download;link.download='';link.textContent='Download '+job.format;result.append(link);
      if(['mp4','hq'].includes(job.format))player($('preview'),job.download);
      if(job.metadata){const details=document.createElement('span');details.className='hint';details.textContent=`${job.metadata.width} × ${job.metadata.height} · ${job.metadata.fps} fps · ${job.metadata.duration.toFixed(2)} s · ${job.metadata.pixel_format}`;result.append(details)}
    } else {
      previewJob=job.id;$('cmResultControls').hidden=false;$('cmApproved').checked=false;$('rerender').hidden=true;
      player($('preview'),job.video);
      const link=document.createElement('a');link.href=job.design_source;link.className='linkbtn';link.textContent='Download editable TSX';link.download='Scene.tsx';result.append(link);
      const previewLink=document.createElement('a');previewLink.href=job.video;previewLink.className='linkbtn';previewLink.textContent='Download preview';previewLink.download='preview.mp4';result.append(previewLink);
      $('cmComparison').hidden=!job.before;if(job.before){$('cmBefore').src=job.before;$('cmAfter').src=job.video}else{$('cmBefore').removeAttribute('src')}
    }
  }
  async function run(url,body) {
    if(busy)return;locked(true);$('cmProgress').value=0;showStatus('Starting Code Motion…');
    try {
      if(body.format!=='project'){
        await checkRenderer();
        if(!cmHealth.ready && cmHealth.auto_prepare)await prepareRenderer();
        if(!cmHealth.ready)throw Error(cmHealth.message);
      }
      const {id}=await request(url,body);currentJob=id;
      while(true){const r=await fetch('/api/code-motion/jobs/'+id),job=await r.json();if(!r.ok)throw Error(job.error);await display(job);if(['complete','error','cancelled'].includes(job.status))break;await new Promise(resolve=>setTimeout(resolve,1000));}
      await history();
    }catch(e){showStatus(e.message,'err')}finally{currentJob=null;locked(false)}
  }
  $('cmGenerate').addEventListener('click',()=>{try{run('/api/code-motion/jobs',input())}catch(e){showStatus(e.message,'err')}});
  $('cmRegenerate').addEventListener('click',()=>{try{run('/api/code-motion/jobs',input())}catch(e){showStatus(e.message,'err')}});
  $('cmRevise').addEventListener('click',()=>{if(!previewJob)return;const prompt=$('cmRevision').value.trim();if(!prompt){showStatus('Describe the revision.','err');return}run(`/api/code-motion/jobs/${previewJob}/revise`,{prompt,provider:$('cmProvider').value,model:selectedModel(),auto_review:$('cmAutoReview').checked,max_revisions:Number($('cmAttempts').value)})});
  $('cmExport').addEventListener('click',()=>{if(!previewJob)return;if(!$('cmApproved').checked){showStatus('Review the preview and tick approval before exporting.','err');return}run(`/api/code-motion/jobs/${previewJob}/export`,{format:$('cmFormat').value,approved:true})});
  $('cmCancel').addEventListener('click',async()=>{if(preparing){$('cmSetupCancel').click();return}if(!currentJob)return;try{await request(`/api/code-motion/jobs/${currentJob}/cancel`,{});showStatus('Cancellation requested.')}catch(e){showStatus(e.message,'err')}});
  $('cmSaveStyle').addEventListener('click',async()=>{try{const result=await request('/api/code-motion/styles',{name:$('cmStyleName').value,direction:$('cmStyleDirection').value});await refresh();$('cmStyle').value=result.id;showStatus('Style saved.','ok')}catch(e){showStatus(e.message,'err')}});
  $('cmHistory').addEventListener('change',async()=>{if(busy||!$('cmHistory').value)return;try{const r=await fetch('/api/code-motion/jobs/'+$('cmHistory').value),job=await r.json();await display(job)}catch(e){showStatus(e.message,'err')}});
  refresh().catch(e=>{$('cmReadiness').textContent=e.message;$('cmAccountStatus').textContent=e.message});
})();

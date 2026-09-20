'use strict';
const $=id=>document.getElementById(id);let saved=null,sources=[],lastSourceSignature='',dirty=false;
const rows=[];
for(let i=0;i<6;i++){
 const tr=document.createElement('tr');const num=document.createElement('td');num.textContent=i+1;tr.append(num);
 const source=document.createElement('select'),channel=document.createElement('select');source.setAttribute('aria-label',`Source vumètre ${i+1}`);channel.setAttribute('aria-label',`Canal vumètre ${i+1}`);
 for(const el of [source,channel]){const td=document.createElement('td');td.append(el);tr.append(td)}
 const td=document.createElement('td'),bar=document.createElement('div'),fill=document.createElement('div'),note=document.createElement('div');bar.className='bar';fill.className='bar-fill';note.className='meter-note';bar.append(fill);td.append(bar,note);tr.append(td);$('meters').append(tr);rows.push({source,channel,fill,note});
 source.addEventListener('change',()=>{dirty=true;setChannels(rows[i],0)});channel.addEventListener('change',()=>dirty=true);
}
function option(text,value){const o=document.createElement('option');o.textContent=text;o.value=String(value);return o}
function setChannels(row,desired){
 const found=sources.find(s=>s.source===row.source.value);row.channel.replaceChildren();
 if(!row.source.value){row.channel.append(option('—',0));row.channel.disabled=true;return}
 row.channel.disabled=false;const count=found?.channels??Math.max(Number(desired)+1,2);
 for(let j=0;j<count;j++)row.channel.append(option(count===1?'Mono':j===0?'Gauche':j===1?'Droite':`Canal ${j+1}`,j));
 row.channel.value=String(Math.min(Number(desired),count-1));
}
function setSources(){
 rows.forEach((row,i)=>{const source=row.source.value,channel=row.channel.value;
 row.source.replaceChildren(option('Désactivé',''));
 sources.forEach(s=>row.source.append(option(s.name,s.source)));
 if(source&&!sources.some(s=>s.source===source))row.source.append(option(source==='master'?'Master — en attente':'Source indisponible',source));
 row.source.value=source;setChannels(row,channel);
 });
}
function status(id,ok,good,bad){$(id).textContent=ok?good:bad;$(id).classList.toggle('ok',!!ok)}
function loadValues(s){saved=s;for(const [slider,number,key]of[['mouse','mouseNumber','pointer_gain'],['jog','jogNumber','jog_gain']]){$(slider).value=s[key];$(number).value=s[key]}rows.forEach((r,i)=>{r.source.replaceChildren(option(s.meter_assignments[i].source,s.meter_assignments[i].source));r.channel.replaceChildren(option('',s.meter_assignments[i].channel))});setSources();dirty=false}
for(const [slider,number]of[['mouse','mouseNumber'],['jog','jogNumber']]){
 $(slider).addEventListener('input',()=>{$(number).value=$(slider).value;dirty=true});$(number).addEventListener('input',()=>{$(slider).value=$(number).value;dirty=true});
}
async function refresh(){try{const res=await fetch('/api/state');if(!res.ok)throw Error('Serveur indisponible');const state=await res.json();
 const d=state.daemon;status('console',d.running&&d.console==='online','Console Online','Console en attente');status('ardour',d.running&&d.ardour==='responding','Ardour connecté','Ardour en attente');status('stereo',d.running&&d.stereo?.active&&d.stereo?.routes_ready,'Stéréo active','Stéréo en attente');
 status('feedback',d.running&&d.console==='online'&&!d.surface?.output_error,'Retours actifs',d.surface?.output_error?'Reprise des retours':'Retours en attente');
 sources=state.sources;const sig=JSON.stringify(sources);if(!saved)loadValues(state.saved);else if(sig!==lastSourceSignature)setSources();lastSourceSignature=sig;
 const large=d.stereo?.large??[];rows.forEach((r,i)=>{const level=large[i],db=level?.db??-193;r.fill.style.width=`${Math.max(0,Math.min(100,(db+60)/60*100))}%`;r.note.textContent=!r.source.value?'':!level?.available?'Source en attente':db<=-193?'Silence':`${db.toFixed(1)} dBFS`;r.fill.parentElement.setAttribute('aria-label',r.note.textContent)});
 const uncal=state.saved.meter_addresses.map((v,i)=>v===null?i+1:null).filter(Boolean);$('calibration').textContent=uncal.length?`Colonnes à identifier sur la console : ${uncal.join(', ')}.`:'';
 if(!dirty&&saved.revision!==state.saved.revision)loadValues(state.saved);
 }catch(e){status('console',false,'','Serveur déconnecté');status('ardour',false,'','Ardour inconnu');status('stereo',false,'','Stéréo inconnue');status('feedback',false,'','Retours inconnus')}}
$('settings').addEventListener('submit',async e=>{e.preventDefault();if(!saved)return;$('apply').disabled=true;$('result').className='';try{
 const data={revision:saved.revision,pointer_gain:Number($('mouseNumber').value),jog_gain:Number($('jogNumber').value),meter_assignments:rows.map(r=>({source:r.source.value,channel:Number(r.channel.value)}))};
 const res=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const result=await res.json();if(!res.ok)throw Error(result.error);
 loadValues(result.saved);const complete=Object.values(result.applied).every(x=>x.ok);$('result').textContent=complete?'Réglages enregistrés et appliqués.':'Réglages enregistrés. Application en attente sur un service arrêté.';
 }catch(e){$('result').textContent=e.message;$('result').className='error'}finally{$('apply').disabled=false}});
refresh();setInterval(refresh,1000);

let testedAddress=null;
for(const a of [8,40,9,41,10,42,11,43,12,44,13,45,...Array.from({length:18},(_,i)=>i+14),...Array.from({length:18},(_,i)=>i+46)])$('candidate').append(option(a,a));
$('candidate').addEventListener('change',()=>{testedAddress=null;$('confirmMeter').disabled=true;$('observed').value=''});
async function calibrationRequest(path,body){const res=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const result=await res.json();if(!res.ok)throw Error(result.error);return result}
$('testMeter').addEventListener('click',async()=>{testedAddress=null;$('confirmMeter').disabled=true;$('testMeter').disabled=true;$('observed').value='';const address=Number($('candidate').value);try{await calibrationRequest('/api/meter-test',{address});testedAddress=address;$('calibrationResult').textContent=`Test envoyé pour l’adresse ${address}. Indique la colonne observée.`;$('confirmMeter').disabled=false}catch(e){$('calibrationResult').textContent=e.message}finally{$('testMeter').disabled=false}});
$('confirmMeter').addEventListener('click',async()=>{if(testedAddress===null||$('observed').value===''){ $('calibrationResult').textContent='Choisis la colonne que tu as vue s’allumer.';return}if(dirty){$('calibrationResult').textContent='Enregistre tes réglages en cours avant de confirmer la colonne.';return}
$('confirmMeter').disabled=true;try{const result=await calibrationRequest('/api/calibration',{revision:saved.revision,column:Number($('observed').value),address:testedAddress,confirmed:true});loadValues(result.saved);$('calibrationResult').textContent=Object.values(result.applied).every(x=>x.ok)?'Colonne enregistrée et appliquée.':'Colonne enregistrée ; application en attente.';testedAddress=null;await refresh()}catch(e){$('calibrationResult').textContent=e.message;$('confirmMeter').disabled=false}});

let studioState=null,studioRequestPending=false,studioLoading=false;
const studioStates={ok:'Vérifié',warning:'À vérifier',error:'Indisponible',unknown:'Inconnu'};
function renderStudio(s){
 studioState=s;const busy=['queued','running'].includes(s.job?.state);const stale=s.stale||!s.supervising;
 const bad=(s.components??[]).filter(c=>c.state!=='ok');
 $('studioSummary').textContent=stale?'État en attente':busy?'Remise en service en cours':bad.length?`${bad.length} point(s) à vérifier`:'Connexions vérifiées';
 $('studioSummary').className=`studio-summary ${stale?'unknown':busy?'warning':bad.length?'warning':'ok'}`;
 $('studioHint').textContent=stale?'Le diagnostic est en attente ou trop ancien. Les derniers voyants ne prouvent pas l’état actuel.':!s.configured?'Le backend du studio doit être configuré sur ce PC.':s.pcm_running===false?'Sur la MPC : Preferences → Audio Device → UAC2_Gadget 0. La sélection sur son écran reste nécessaire après un redémarrage.':'Les voyants vérifient les connexions et l’ouverture audio. La qualité sonore se confirme à l’écoute.';
 $('studioRecover').disabled=studioRequestPending||busy||!s.configured||!s.supervising;
 $('studioRoute').disabled=studioRequestPending||busy||!s.route_allowed||stale;
 $('studioCheck').disabled=studioRequestPending||busy||!s.supervising;
 $('studioAutomatic').disabled=studioRequestPending||!s.configured||!s.supervising;
 if(!studioRequestPending)$('studioAutomatic').checked=!!s.automatic;
 const names={queued:'En attente',running:'En cours',succeeded:'Terminée',failed:'Échec',interrupted:'Interrompue'};
 const action=s.job?.action==='route'?'Routage':'Remise en service';
 $('studioJob').textContent=s.job?.state?`${action}${s.job.automatic?' automatique':''} : ${names[s.job.state]??s.job.state}${s.job.error?' — '+s.job.error:''}`:'';
 $('studioJob').className=['failed','interrupted'].includes(s.job?.state)?'error':'';
 $('studioComponents').replaceChildren(...(s.components??[]).map(c=>{
  const row=document.createElement('div');row.className='studio-component';
  const title=document.createElement('strong');title.textContent=c.label;
  const badge=document.createElement('span');badge.className='studio-badge '+(stale?'unknown':c.state);badge.textContent=stale?'État ancien':studioStates[c.state]??c.state;
  const detail=document.createElement('p');detail.textContent=c.detail;row.append(title,badge,detail);return row;
 }));
 const monitoring=(s.monitoring??[]).map(t=>`Voie ${t.slot} : ${t.pending?'en attente':t.mode??'inconnu'}`).join(' · ');
 $('studioAudioNote').textContent=`Reprises PCM observées : ${s.pcm_restarts??0}. Les sélections manuelles peuvent aussi modifier ce compteur ; ce n’est pas un total de coupures. ${monitoring} Pour entendre la MPC, vérifier IN et le bouton MUTE de la piste dans Ardour.`;
 $('studioChecked').textContent=s.checked_at?`Dernière vérification : ${new Date(s.checked_at*1000).toLocaleTimeString('fr-FR')}. Surveillance toutes les 10 secondes.${s.error?' Diagnostic : '+s.error:''}`:'Premier diagnostic en cours…';
}
async function refreshStudio(){
 if(studioLoading)return;studioLoading=true;
 try{const res=await fetch('/api/studio');if(!res.ok)throw Error('Supervision indisponible');renderStudio(await res.json());}
 catch(e){if(studioState)renderStudio({...studioState,stale:true,supervising:false});$('studioSummary').textContent='Gateway déconnectée';}
 finally{studioLoading=false;}
}
async function studioAction(action,extra={}){
 studioRequestPending=true;if(studioState)renderStudio(studioState);$('studioMessage').textContent='';
 try{const res=await fetch('/api/studio/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,...extra})});const s=await res.json();if(!res.ok)throw Error(s.error);renderStudio(s);if(action==='check')$('studioMessage').textContent='Vérification demandée.';}
 catch(e){$('studioMessage').textContent=e.message;}
 finally{studioRequestPending=false;await refreshStudio();}
}
async function studioLogs(){const res=await fetch('/api/studio/logs');if(!res.ok)throw Error('Journaux indisponibles');return await res.json();}
async function refreshStudioLogs(){try{const logs=await studioLogs();$('studioLogText').textContent=Object.entries(logs).map(([name,text])=>`── ${name} ──\n${text}`).join('\n\n');}catch(e){$('studioLogText').textContent=e.message;}}
$('studioRecover').addEventListener('click',()=>studioAction('recover'));
$('studioRoute').addEventListener('click',()=>studioAction('route'));
$('studioCheck').addEventListener('click',()=>studioAction('check'));
$('studioAutomatic').addEventListener('change',()=>studioAction('automatic',{enabled:$('studioAutomatic').checked}));
$('studioLogs').addEventListener('toggle',()=>{if($('studioLogs').open)refreshStudioLogs();});
$('studioRefreshLogs').addEventListener('click',refreshStudioLogs);
$('studioDownload').addEventListener('click',async()=>{try{const logs=await studioLogs();const data=JSON.stringify({exported_at:new Date().toISOString(),studio:studioState,logs},null,2);const url=URL.createObjectURL(new Blob([data],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='procontrol-studio-diagnostic.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){$('studioMessage').textContent=e.message;}});
refreshStudio();setInterval(refreshStudio,2000);

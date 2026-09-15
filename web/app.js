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

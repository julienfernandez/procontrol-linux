/* Raw levels arrive independently from settings and console configuration. */
'use strict';
(() => {
 const normalize = db => Number.isFinite(db)?Math.max(0,Math.min(1,(db+60)/60)):0;
 function advance(current,target,elapsed,reduced=false){
  if(reduced)return target;
  return target+(current-target)*Math.exp(-Math.max(0,Math.min(100,elapsed))/(target>current?18:180));
 }
 if(typeof module!=='undefined')module.exports={normalize,advance};
 if(typeof window==='undefined')return;
 let source=null,raf=0,received=0,last=0,frame={active:false},targets={},levels={},peaks={},holds={};
 for(let i=1;i<=8;i++)for(const side of ['L','R'])targets[`strip.${i}.meter.${side}`]=0;
 for(let i=1;i<=6;i++)targets[`master.meter.${i}`]=0;
 const reduced=matchMedia('(prefers-reduced-motion: reduce)');
 function paint(now){
  const stale=now-received>800||!frame.active;
  const elapsed=last?now-last:16;last=now;
  for(const key of Object.keys(targets)){
   const target=stale?0:targets[key];levels[key]=stale?0:advance(levels[key]||0,target,elapsed,reduced.matches);
   if(stale){peaks[key]=0;holds[key]=0;}
   else if(target>=(peaks[key]||0)){peaks[key]=target;holds[key]=now+650;}
   else if(now>holds[key])peaks[key]=Math.max(target,peaks[key]-elapsed/1400);
  }
  const indicator=document.getElementById('meterStreamStatus');
  const status=stale?'Flux audio · en attente':'Flux audio · direct';
  if(indicator&&indicator.textContent!==status)indicator.textContent=status;
  window.dispatchEvent(new CustomEvent('procontrol-meters',{detail:{frame:stale?{active:false}:frame,levels,peaks}}));
  raf=requestAnimationFrame(paint);
 }
 function open(){
  if(document.hidden||source)return;
  source=new EventSource('/api/meters/events');
  source.onmessage=e=>{try{
   frame=JSON.parse(e.data);received=performance.now();
   for(let i=0;i<8;i++)for(let side=0;side<2;side++)targets[`strip.${i+1}.meter.${side?'R':'L'}`]=normalize(frame.strips?.[i]?.[side]);
   for(let i=0;i<6;i++)targets[`master.meter.${i+1}`]=normalize(frame.large?.[i]?.db);
  }catch{frame={active:false};}};
  // Bounded SSE rollover reconnects in 100 ms. The freshness watchdog, not
  // a transient close, decides when the last audio frame is too old.
  source.onerror=()=>{};
  last=0;raf=requestAnimationFrame(paint);
 }
 function close(){source?.close();source=null;cancelAnimationFrame(raf);frame={active:false};received=0;}
 document.addEventListener('visibilitychange',()=>document.hidden?close():open());
 window.addEventListener('pagehide',close);window.addEventListener('pageshow',open);open();
})();

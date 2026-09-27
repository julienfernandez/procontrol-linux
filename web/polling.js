// Read-only requests are bounded; mutations keep their explicit result handling.
async function readJson(url) {
 const controller=new AbortController();
 const timer=setTimeout(()=>controller.abort(),5000);
 try {
  const response=await fetch(url,{signal:controller.signal});
  if(!response.ok)throw Error('Serveur indisponible');
  return await response.json();
 } finally {clearTimeout(timer);}
}

function pollVisible(refresh,interval) {
 let busy=false;
 async function tick() {
  if(busy||document.hidden)return;
  busy=true;
  try {await refresh();} finally {busy=false;}
 }
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)tick();});
 tick();setInterval(tick,interval);
}

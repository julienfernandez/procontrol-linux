// node tests/test_web_polling.js — deterministic browser scheduling/timeout contracts.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');

(async()=>{
 let interval,visible,release,calls=0,timeout,cleared=0;
 const document={hidden:false,addEventListener:(name,fn)=>{visible=fn;}};
 const context=vm.createContext({document,AbortController,
  setInterval:fn=>{interval=fn;},setTimeout:fn=>{timeout=fn;return 1;},clearTimeout:()=>{cleared++;}});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../web/polling.js'),'utf8'),context);
 context.refresh=()=>{calls++;return new Promise(resolve=>{release=resolve;});};
 vm.runInContext('pollVisible(refresh,1000)',context);
 assert.equal(calls,1);
 for(let i=0;i<10;i++)await interval();
 assert.equal(calls,1,'One slow GET must not accumulate scheduled requests');
 release();await Promise.resolve();await Promise.resolve();
 document.hidden=true;await interval();assert.equal(calls,1);
 document.hidden=false;visible();assert.equal(calls,2,'Returning to the tab refreshes immediately');
 release();await Promise.resolve();
 context.fetch=(url,{signal})=>new Promise((resolve,reject)=>{
  signal.addEventListener('abort',()=>reject(new Error('aborted')));
 });
 const pending=vm.runInContext('readJson("/api/state")',context);
 timeout();await assert.rejects(pending,/aborted/);assert.equal(cleared,1);
 context.fetch=async()=>({ok:true,json:async()=>({running:false})});
 assert.deepEqual(await vm.runInContext('readJson("/api/state")',context),{running:false});
 assert.equal(cleared,2);
 console.log('PASS: serialized polling, hidden tab pause, immediate resume, timeout and recovery');
})().catch(error=>{console.error(error);process.exitCode=1;});

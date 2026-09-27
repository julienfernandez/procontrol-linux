const assert=require('node:assert/strict');
const {advance,normalize}=require('../web/meters.js');
assert.equal(normalize(-193),0);assert.equal(normalize(12),1);assert.equal(normalize(NaN),0);
assert.equal(normalize(-30),.5);
let x=0;for(let i=0;i<5;i++){x=advance(x,1,16);assert(x<=1&&x>=0);}assert(x>.98);
let y=1;for(let i=0;i<5;i++)y=advance(y,0,16);assert(y>.6&&y<.7);
assert.equal(advance(.5,.2,16,true),.2);
console.log('Meter scale, attack, release and reduced motion: OK');
// Exercise rollover, stale data, hidden-page cleanup and resume in a fake DOM.
const vm=require('node:vm'),fs=require('node:fs');
let now=1000,events=[],frames=[],listeners={},sources=[];
const document={hidden:false,getElementById:()=>null,addEventListener:(name,fn)=>listeners[name]=fn};
const window={addEventListener:(name,fn)=>listeners[name]=fn,dispatchEvent:e=>events.push(JSON.parse(JSON.stringify(e.detail)))};
class Source{constructor(){sources.push(this);}close(){this.closed=true;}}
vm.runInNewContext(fs.readFileSync(require.resolve('../web/meters.js'),'utf8'),{
 window,document,EventSource:Source,performance:{now:()=>now},matchMedia:()=>({matches:false}),
 requestAnimationFrame:fn=>{frames=[fn];return 1;},cancelAnimationFrame:()=>{frames=[];},
 CustomEvent:class{constructor(name,data){this.detail=data.detail;}}
});
function tick(){const fn=frames.shift();if(fn)fn(now);}
sources[0].onmessage({data:JSON.stringify({active:true,strips:[[-3,-18]],large:[]})});tick();
assert(events.at(-1).levels['strip.1.meter.L']>0);
sources[0].onerror();now+=100;tick();assert(events.at(-1).frame.active,'rollover must not blank fresh audio');
now+=801;tick();assert.equal(events.at(-1).levels['strip.1.meter.L'],0);
document.hidden=true;listeners.visibilitychange();assert(sources[0].closed);assert.equal(frames.length,0);
document.hidden=false;listeners.visibilitychange();assert.equal(sources.length,2);
listeners.pageshow();assert.equal(sources.length,2,'only one connection per visible page');
console.log('SSE rollover, stale silence, hidden-page cleanup and resume: OK');

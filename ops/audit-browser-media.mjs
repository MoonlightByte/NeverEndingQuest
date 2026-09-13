/** Actual React component media/URL canaries in Chromium; all network mocked. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
const root = fileURLToPath(new URL('..', import.meta.url));
const frontend = path.join(root, 'web/frontend');
const require = createRequire(path.join(frontend, 'package.json'));
const { chromium } = require('@playwright/test');
const { build } = await import(pathToFileURL(require.resolve('vite')).href);
const temporary = fs.mkdtempSync(path.join(frontend, '.neq-media-audit-'));
const entry = path.join(temporary, 'entry.tsx');
const hasMobile=fs.existsSync(path.join(frontend,'src/components/mobile/chat.tsx'));
const caddyPath=path.join(root,'ops/Caddyfile');
if(fs.existsSync(caddyPath)) assert(hasMobile,'Hosted mobile renderer must be tested');
fs.writeFileSync(entry, `
import React from 'react';
import {createRoot} from 'react-dom/client';
import {flushSync} from 'react-dom';
import {MessageCard} from '../src/components/log/MessageCard';
import {MediaPopup} from '../src/components/party/MediaPopup';
import {CharacterChip} from '../src/components/party/CharacterChip';
${hasMobile ? "import {MqNpcCard} from '../src/components/mobile/chat';" : ''}
import {EmberPresentation} from '../src/components/layout/EmberPresentation';
const root=createRoot(document.getElementById('root')!); let serial=0;
window.neqInjected=0;
window.neqAudit={render(kind,value,ember){
 const key=++serial;
 const child=${hasMobile ? "kind==='mobile-card' ? <MqNpcCard key={key} name={value.text} content={value.text} portraitUrl={value.url} /> :" : ''}
 kind==='scene' ? <MessageCard key={key} message={{id:'audit',type:'narration',content:value.text,timestamp:0}} images={[{image_url:value.url,prompt:value.text}]} /> :
 kind==='chip' ? <CharacterChip key={key} name={value.text} displayName={value.text} variant="init-npc" stats={{hp:10,max_hp:10,level:2}} thumbCandidates={[value.url]} onOpenMedia={()=>{}} /> :
 <MediaPopup key={key} media={{kind:kind==='video'?'video':'image',src:value.url}} onClose={()=>{}} />;
 flushSync(()=>root.render(<EmberPresentation.Provider value={ember}>{child}</EmberPresentation.Provider>));
}};
`);
let result;
try {
  result = await build({root: frontend, configFile: path.join(frontend, 'vite.config.ts'), logLevel:'silent',define:{'process.env.NODE_ENV':'"production"'},
    build:{write:false,minify:false,lib:{entry,formats:['iife'],name:'MediaAudit'}}});
} finally {
  assert.equal(path.dirname(path.resolve(temporary)),path.resolve(frontend));
  assert(!fs.lstatSync(temporary).isSymbolicLink());
  fs.rmSync(temporary, {recursive:true,force:true});
}
const outputs = (Array.isArray(result) ? result : [result]).flatMap(r=>r.output);
const scripts = outputs.filter(item=>item.type==='chunk');
assert.equal(scripts.length,1);
// Public builds have no hosting config: use an explicitly labelled test policy.
const cspSource=fs.existsSync(caddyPath)?'ops/Caddyfile':'test fixture (no deployment claim)';
const caddy=fs.existsSync(caddyPath)?fs.readFileSync(caddyPath,'utf8'):'';
const match=caddy.match(/header Content-Security-Policy "(default-src 'self'; script-src 'self';[^"\r\n]+)"/);
if(caddy) assert(match,'actual game CSP must be present');
const csp=match?.[1]??"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' data: blob:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'; form-action 'self'; upgrade-insecure-requests";
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aChsAAAAASUVORK5CYII=','base64');
const svg = `<svg xmlns="http://www.w3.org/2000/svg" onload="window.neqInjected++"><script>window.neqInjected++</script></svg>`;
const cases = [
  {name:'ordinary',text:'Ranger Elen',url:'/media/npcs/elen_thumb.jpg'},
  {name:'apostrophe',text:"Ranger O'Brien",url:"/media/npcs/ranger_o'brien_thumb.jpg"},
  {name:'double-quote',text:'Ranger "Elen"',url:'/media/npcs/ranger_"elen"_thumb.jpg'},
  {name:'parentheses',text:'Ranger (elder)',url:'/media/npcs/ranger_(elder)_thumb.jpg'},
  {name:'backslash',text:'Backslash',url:'/media/npcs/ranger\\_thumb.jpg'},
  {name:'newline',text:'Newline',url:'/media/npcs/ranger\n_thumb.jpg'},
  {name:'markup',text:'<img src=x onerror="window.neqInjected++">',url:'/media/npcs/x\" onerror=\"window.neqInjected++'},
  {name:'javascript',text:'Script URL',url:'javascript:window.neqInjected++'},
  {name:'svg-data',text:'SVG image',url:'data:image/svg+xml,'+encodeURIComponent(svg)},
  {name:'html-data',text:'HTML disguised as media',url:'data:text/html,'+encodeURIComponent('<script>window.neqInjected++</script>')},
  {name:'png-data',text:'Inline image',url:'data:image/png;base64,'+png.toString('base64')},
  {name:'foreign',text:'Foreign image',url:'https://blocked.invalid/collect'},
  {name:'protocol-relative',text:'Foreign image',url:'//blocked.invalid/collect'},
  {name:'foreign-redirect',text:'Same-origin redirect to foreign media',url:'/redirect-image'},
  {name:'css-list',text:'CSS URL list',url:"/media/npcs/x'),url('http:blocked.invalid/collect')/*_thumb.jpg"},
  {name:'css-list-unquoted',text:'CSS URL list',url:'/media/npcs/x),url(http:blocked.invalid/collect)/*_thumb.jpg'},
];
const browser = await chromium.launch({headless:true,...(process.env.NEQ_CHROMIUM_PATH ? {executablePath:process.env.NEQ_CHROMIUM_PATH}:{})});
const browserVersion=browser.version();
const rows=[];
try {
  for (const hosted of [false,true]) {
    const context=await browser.newContext({serviceWorkers:'block'});
    let foreign=[];
    await context.route('**/*', async route=>{
      const url=new URL(route.request().url());
      if(url.origin!=='https://neq-media.invalid') foreign.push(url.origin);
      if(url.origin==='https://neq-media.invalid' && url.pathname==='/audit') {
        await route.fulfill({contentType:'text/html',headers:hosted?{'Content-Security-Policy':csp}:{},
          body:'<!doctype html><html><head><style>.neq-character-chip,.ember-chip-portrait,.mq-npc-ava{display:block;width:120px;height:120px}</style></head><body><div id="root"></div><script src="/audit.js"></script></body></html>'});
      } else if(url.origin==='https://neq-media.invalid' && url.pathname==='/audit.js') {
        await route.fulfill({contentType:'text/javascript',body:scripts[0].code});
      } else if(url.origin==='https://neq-media.invalid' && url.pathname==='/redirect-image') {
        await route.fulfill({status:302,headers:{'Location':'https://blocked-redirect.invalid/collect','Cache-Control':'no-store'},body:''});
      } else { await route.fulfill({contentType:'image/png',headers:{'Cache-Control':'no-store'},body:png}); }
    });
    const page=await context.newPage();
    const errors=[]; page.on('pageerror',error=>errors.push(error.message));
    await page.goto('https://neq-media.invalid/audit');
    await page.waitForFunction(()=>Boolean(window.neqAudit),undefined,{timeout:5000}).catch(error=>{throw new Error(`Fixture did not initialize: ${errors.join('; ')}; ${error.message}`)});
    for(const ember of [false,true]) for(const kind of ['scene','image','video','chip',...(hasMobile?['mobile-card']:[])]) for(const original of cases) {
      const value={...original,url:original.url.replaceAll('blocked.invalid',`blocked-${rows.length}.invalid`)};
      foreign=[]; errors.length=0;
      await page.evaluate(({kind,value,ember})=>window.neqAudit.render(kind,value,ember),{kind,value,ember});
      await page.waitForTimeout(40);
      await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
      const observed=await page.evaluate(()=>({injected:window.neqInjected,
        injectedNodes:document.querySelectorAll('[onerror],[onload],svg script').length,
        sceneText:document.querySelector('.neq-message')?.textContent,
        mobileText:document.querySelector('.mq-npc-msg')?.textContent,
        dialog:!!document.querySelector('[role="dialog"]'),
        background:[...document.querySelectorAll('.neq-character-chip,.ember-chip-portrait,.mq-npc-ava')].filter(e=>!e.querySelector('.ember-chip-portrait')).map(e=>getComputedStyle(e).backgroundImage),
        broken:document.body.textContent.includes('could not be loaded')}));
      assert.equal(observed.injected,0,JSON.stringify({hosted,ember,kind,value:value.name,observed}));
      assert.equal(observed.injectedNodes,0);
      if(kind==='scene') assert(observed.sceneText?.includes(value.text),'Narration did not render the test text');
      if(kind==='chip'||kind==='mobile-card') assert(observed.background.length>0,'Portrait component did not render');
      if(kind==='mobile-card') assert(observed.mobileText?.includes(value.text),'Mobile text did not render');
      if(kind==='image'||kind==='video') assert(observed.dialog,'Media dialog did not render');
      assert.deepEqual(errors,[],JSON.stringify({hosted,ember,kind,value:value.name}));
      if(hosted) assert.deepEqual(foreign,[],`CSP permitted an external request: ${kind}/${value.name}`);
      if(kind==='chip'||kind==='mobile-card') {
        if(['ordinary','apostrophe','double-quote','parentheses','backslash','newline'].includes(value.name)||value.name.startsWith('css-list')) {
          assert(observed.background.every(b=>b!=='none'),`Portrait filename broke CSS: ${kind}/${value.name}`);
        }
        assert(!observed.background.some(b=>b.includes('), url(')),`Extra CSS image layer: ${kind}/${value.name}`);
        if(value.name.startsWith('css-list')) assert.deepEqual(foreign,[],`CSS injection requested external media without CSP: ${kind}/${value.name}`);
      }
      rows.push({hosted,ember,kind,input:value.name,...observed,foreignRequests:foreign.length});
    }
    await context.close();
  }
} finally { await browser.close(); }
const output=process.env.NEQ_MEDIA_AUDIT_OUTPUT;
const sourcePaths=['web/frontend/src/components/log/MessageCard.tsx','web/frontend/src/components/party/CharacterChip.tsx',
  'web/frontend/src/components/party/MediaPopup.tsx',...(hasMobile?['web/frontend/src/components/mobile/chat.tsx']:[]),'web/frontend/src/components/party/cssImageUrl.ts','web/frontend/package-lock.json'];
const sourceHashes=Object.fromEntries(sourcePaths.map(name=>[name,createHash('sha256').update(fs.readFileSync(path.join(root,name))).digest('hex')]));
const report={browserVersion,sourceHashes,hasMobile,cspSource,hostedCsp:csp,allNetworkIntercepted:true,cases:rows.length,scriptExecution:rows.some(r=>r.injected),
  hostedExternalRequests:rows.filter(r=>r.hosted).reduce((n,r)=>n+r.foreignRequests,0),
  portraitFormatting:rows.filter(r=>r.kind==='chip'&&['ordinary','apostrophe','double-quote','css-list'].includes(r.input)),rows};
if(output) fs.writeFileSync(output,JSON.stringify(report,null,2));
console.log(JSON.stringify({browserVersion,cases:report.cases,scriptExecution:report.scriptExecution,hostedExternalRequests:report.hostedExternalRequests,
  quotedPortraitFailures:rows.filter(r=>['chip','mobile-card'].includes(r.kind)&&['apostrophe','double-quote','parentheses'].includes(r.input)&&r.background.every(b=>b==='none')).length,
  cssLayerInjections:rows.filter(r=>r.background.some(b=>b.includes('), url('))).length,
  unprotectedCssRequests:rows.filter(r=>!r.hosted&&r.input.startsWith('css-list')).reduce((n,r)=>n+r.foreignRequests,0)},null,2));

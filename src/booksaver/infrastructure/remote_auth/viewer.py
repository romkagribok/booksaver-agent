from __future__ import annotations

import json

_VIEWER_DOCUMENT = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport"
 content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<title>Connect Booking.com</title>
<script src="https://telegram.org/js/telegram-web-app.js?63"></script>
<style nonce="__NONCE__">
:root{--app-height:100dvh;--safe-bottom:env(safe-area-inset-bottom,0px)}
*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;overflow:hidden}
body{height:var(--app-height);display:flex;flex-direction:column;background:#101820;color:#fff;
 font:15px system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
#status{padding:8px 12px;background:#182633;line-height:1.3;min-height:38px}
#help{margin:0;padding:7px 12px;background:#22384a;color:#e6f2fa;font-size:13px}
#viewer{flex:1;min-height:0;position:relative;overflow:auto;background:#000;overscroll-behavior:none}
#screen{width:100%;height:100%;min-height:100%;touch-action:none}
body.keyboard-open #screen{height:auto;min-height:max(100%,200vw)}
#dock{display:flex;gap:6px;padding:7px 8px calc(7px + var(--safe-bottom));background:#182633}
button{min-width:44px;min-height:44px;margin:0;padding:8px 10px;border:1px solid #58728a;
 border-radius:8px;background:#26455f;color:#fff;font:inherit;font-weight:600}
button:disabled{opacity:.45}#keyboard{flex:1}#cancel{background:#71383d;border-color:#a85a61}
#capture{position:fixed;left:-10000px;bottom:0;width:2px;height:2px;opacity:.01;
 pointer-events:none;border:0;padding:0}
body.keyboard-open #keyboard{background:#0878d1;border-color:#6cb9f1}
body:not(.touch-first) #help,body:not(.touch-first) #help-button{display:none}
@media (orientation:landscape) and (max-height:520px){
 #status{padding:5px 10px;min-height:30px;font-size:13px}#help{padding:4px 10px}
 #dock{padding-top:4px;padding-bottom:calc(4px + var(--safe-bottom))}
}
</style></head><body>
<div id="status" role="status" aria-live="polite">Authorizing this connection…</div>
<p id="help">Tap a Booking.com field, then tap Keyboard. Use Next or Enter to continue.</p>
<div id="viewer"><div id="screen" aria-label="Remote Booking.com browser"></div></div>
<div id="dock" aria-label="Remote browser controls">
 <button id="keyboard" type="button" disabled aria-pressed="false">Keyboard</button>
 <button id="next" type="button" disabled>Next</button>
 <button id="enter" type="button" disabled>Enter</button>
 <button id="help-button" type="button" aria-controls="help" aria-expanded="true">Help</button>
 <button id="cancel" type="button">Cancel</button>
</div>
<input id="capture" type="password" inputmode="text" autocomplete="off" autocapitalize="none"
 autocorrect="off" spellcheck="false" tabindex="-1" aria-label="Remote browser keyboard input">
<script nonce="__NONCE__">
const launchToken=__LAUNCH_TOKEN__;
const terminalStatuses=new Set(['succeeded','failed','expired','cancelled']);
const statusNode=document.getElementById('status');
const helpNode=document.getElementById('help');
const viewerNode=document.getElementById('viewer');
const screenNode=document.getElementById('screen');
const dockNode=document.getElementById('dock');
const captureNode=document.getElementById('capture');
const keyboardButton=document.getElementById('keyboard');
const nextButton=document.getElementById('next');
const enterButton=document.getElementById('enter');
const helpButton=document.getElementById('help-button');
const cancelButton=document.getElementById('cancel');
const tg=window.Telegram&&window.Telegram.WebApp;
const platform=(tg&&tg.platform)||'unknown';
const touchFirst=['android','android_x','ios'].includes(platform)||
 ('ontouchstart' in window)||navigator.maxTouchPoints>0||
 (window.matchMedia&&window.matchMedia('(pointer:coarse)').matches);
document.body.classList.toggle('touch-first',touchFirst);
let rfb=null;
let touchKeyboard=null;
let KeyTable=null;
let keysyms=null;
let terminalState=false;
let viewerError=false;
let viewerAuthorized=false;
let closeRequested=false;
let reconnectAttempted=false;
let reconnectExhausted=false;
let rfbConnecting=false;
let pollTimer=null;
let composing=false;
let lastKeyboardInput=null;
let lastRemoteTouchY=0;
const defaultKeyboardInputLen=100;
if(tg){tg.ready();tg.expand();}

function setStatus(message){statusNode.textContent=message;}
function setViewerError(message){
 if(terminalState)return;
 viewerError=true;
 setStatus(message);
}
function setControlsEnabled(enabled){
 keyboardButton.disabled=!enabled;
 nextButton.disabled=!enabled;
 enterButton.disabled=!enabled;
}
function resetKeyboardInput(){
 captureNode.value=new Array(defaultKeyboardInputLen).join('_');
 lastKeyboardInput=captureNode.value;
}
function positionTouchedRegion(){
 if(!document.body.classList.contains('keyboard-open'))return;
 const desired=Math.max(0,lastRemoteTouchY-viewerNode.clientHeight*0.32);
 viewerNode.scrollTop=desired;
}
function updateViewport(){
 const viewport=tg&&Number(tg.viewportStableHeight||tg.viewportHeight);
 const visual=window.visualViewport&&window.visualViewport.height;
 const height=Math.max(240,Math.floor(visual||viewport||window.innerHeight));
 document.documentElement.style.setProperty('--app-height',`${height}px`);
 requestAnimationFrame(positionTouchedRegion);
}
function setKeyboardOpen(open){
 if(!rfb||terminalState)return;
 document.body.classList.toggle('keyboard-open',open);
 keyboardButton.textContent=open?'Hide keyboard':'Keyboard';
 keyboardButton.setAttribute('aria-pressed',String(open));
 rfb.focusOnClick=!open;
 if(open){
  resetKeyboardInput();
  captureNode.focus({preventScroll:true});
  try{captureNode.setSelectionRange(captureNode.value.length,captureNode.value.length);}catch(_){}
  requestAnimationFrame(positionTouchedRegion);
 }else{
  captureNode.blur();
  resetKeyboardInput();
  viewerNode.scrollTop=0;
 }
}
function teardownInput(){
 setControlsEnabled(false);
 document.body.classList.remove('keyboard-open');
 keyboardButton.textContent='Keyboard';
 keyboardButton.setAttribute('aria-pressed','false');
 captureNode.blur();
 resetKeyboardInput();
 if(touchKeyboard){touchKeyboard.ungrab();touchKeyboard=null;}
}
function sendShortcut(keysym,code){
 if(rfb&&!terminalState&&!keyboardButton.disabled)rfb.sendKey(keysym,code);
}
function keyInput(event){
 if(!rfb||terminalState||composing)return;
 const newValue=event.target.value;
 if(!lastKeyboardInput)resetKeyboardInput();
 const oldValue=lastKeyboardInput;
 let newLen;
 try{newLen=Math.max(event.target.selectionStart,newValue.length);}
 catch(_){newLen=newValue.length;}
 const oldLen=oldValue.length;
 let inputs=newLen-oldLen;
 let backspaces=inputs<0?-inputs:0;
 for(let i=0;i<Math.min(oldLen,newLen);i++){
  if(newValue.charAt(i)!==oldValue.charAt(i)){
   inputs=newLen-i;
   backspaces=oldLen-i;
   break;
  }
 }
 for(let i=0;i<backspaces;i++)rfb.sendKey(KeyTable.XK_BackSpace,'Backspace');
 for(let i=newLen-inputs;i<newLen;i++)rfb.sendKey(keysyms.lookup(newValue.charCodeAt(i)));
 resetKeyboardInput();
 if(newLen<1){
  event.target.blur();
  setTimeout(()=>event.target.focus({preventScroll:true}),0);
 }else{
  try{event.target.setSelectionRange(event.target.value.length,event.target.value.length);}
  catch(_){}
 }
}
async function jsonRequest(url,options={}){
 const response=await fetch(url,{credentials:'same-origin',...options});
 const data=await response.json().catch(()=>({message:'Connection unavailable.'}));
 if(!response.ok)throw new Error(data.message||'Connection unavailable.');
 return data;
}
async function loadViewerModules(){
 const modules=await Promise.all([
  import('/novnc/core/rfb.js'),
  import('/novnc/core/input/keyboard.js'),
  import('/novnc/core/input/keysym.js'),
  import('/novnc/core/input/keysymdef.js')
 ]);
 return {RFB:modules[0].default,Keyboard:modules[1].default,
  keys:modules[2].default,definitions:modules[3].default};
}
async function connectViewer(state){
 if(rfb||rfbConnecting)return;
 rfbConnecting=true;
 try{
 const modules=await loadViewerModules();
 KeyTable=modules.keys;
 keysyms=modules.definitions;
 const scheme=location.protocol==='https:'?'wss':'ws';
 const ws=`${scheme}://${location.host}${state.websocket_path}?token=${encodeURIComponent(state.websocket_token)}`;
 const current=new modules.RFB(screenNode,ws);
 rfb=current;
 current.scaleViewport=true;
 current.clipViewport=false;
 current.resizeSession=false;
 current.showDotCursor=!touchFirst;
 current.addEventListener('connect',()=>{
  if(rfb!==current||terminalState)return;
  viewerError=false;
  setStatus('Remote browser connected. Sign in with your Booking.com email and password.');
  setControlsEnabled(true);
  touchKeyboard=new modules.Keyboard(captureNode);
  touchKeyboard.onkeyevent=(keysym,code,down)=>current.sendKey(keysym,code,down);
  touchKeyboard.grab();
 });
 current.addEventListener('securityfailure',()=>{
  if(rfb===current){
   teardownInput();
   setViewerError('The remote browser connection failed. '+
    'Return to Telegram and try /connect again.');
  }
 });
 current.addEventListener('disconnect',event=>{
  if(rfb!==current)return;
  teardownInput();
  rfb=null;
  if(terminalState)return;
  if(event.detail&&event.detail.clean===false&&!reconnectAttempted){
   reconnectAttempted=true;
   setViewerError('Remote browser disconnected. Reconnecting once…');
   schedulePoll(750);
  }else{
   reconnectExhausted=true;
   setViewerError('The remote browser connection was lost. '+
    'Return to Telegram and try /connect again.');
  }
 });
 }finally{
  rfbConnecting=false;
 }
}
function schedulePoll(delay=1000){
 if(pollTimer!==null||terminalState)return;
 pollTimer=setTimeout(()=>{
  pollTimer=null;
  void poll();
 },delay);
}
async function poll(){
 try{
  const state=await jsonRequest('/api/connect/session');
  terminalState=terminalStatuses.has(state.status);
  const finalizing=state.status==='finalizing';
  if(!viewerError||terminalState||finalizing)setStatus(state.message);
  if(finalizing){
   closeRequested=true;
   teardownInput();
   cancelButton.disabled=true;
   if(rfb){const current=rfb;rfb=null;current.disconnect();}
   schedulePoll(250);
   return;
  }
  if((state.status==='ready'||state.status==='connected')&&!rfb&&!reconnectExhausted){
   await connectViewer(state);
  }
  if(terminalState){
   closeRequested=true;
   teardownInput();
   cancelButton.disabled=true;
   if(rfb){const current=rfb;rfb=null;current.disconnect();}
   if(state.status==='succeeded'&&tg&&typeof tg.close==='function')tg.close();
   return;
  }
  cancelButton.disabled=false;
  schedulePoll();
 }catch(error){
  teardownInput();
  setStatus(error.message);
 }
}
async function start(){
 if(!tg||!tg.initData)throw new Error(
  'Open this page from the button in your private Telegram chat.');
 await jsonRequest('/api/connect/exchange',{method:'POST',
  headers:{'Content-Type':'application/json'},
  body:JSON.stringify({launch_token:launchToken,init_data:tg.initData})});
 viewerAuthorized=true;
 await poll();
}
function cancelOnClose(event){
 if(event&&event.persisted)return;
 if(!viewerAuthorized||terminalState||closeRequested)return;
 closeRequested=true;
 void fetch('/api/connect/cancel',{
  method:'POST',credentials:'same-origin',keepalive:true
 }).catch(()=>{});
}

keyboardButton.addEventListener('click',()=>{
 setKeyboardOpen(!document.body.classList.contains('keyboard-open'));
});
nextButton.addEventListener('click',()=>sendShortcut(KeyTable.XK_Tab,'Tab'));
enterButton.addEventListener('click',()=>sendShortcut(KeyTable.XK_Return,'Enter'));
helpButton.addEventListener('click',()=>{
 const hidden=helpNode.hidden;
 helpNode.hidden=!hidden;
 helpButton.setAttribute('aria-expanded',String(hidden));
});
cancelButton.addEventListener('click',async()=>{
 closeRequested=true;
 teardownInput();
 try{await jsonRequest('/api/connect/cancel',{method:'POST'});}catch(_){}
 if(tg)tg.close();
});
captureNode.addEventListener('input',keyInput);
captureNode.addEventListener('compositionstart',()=>{composing=true;});
captureNode.addEventListener('compositionend',event=>{
 composing=false;
 keyInput(event);
});
captureNode.addEventListener('blur',()=>{
 if(document.body.classList.contains('keyboard-open'))setKeyboardOpen(false);
});
viewerNode.addEventListener('pointerdown',event=>{
 lastRemoteTouchY=event.clientY-viewerNode.getBoundingClientRect().top+viewerNode.scrollTop;
},{passive:true});
viewerNode.addEventListener('mousedown',event=>{
 if(document.body.classList.contains('keyboard-open'))event.preventDefault();
},true);
dockNode.addEventListener('mousedown',event=>{
 if(document.body.classList.contains('keyboard-open')&&
    event.target.id!=='cancel')event.preventDefault();
},true);
window.addEventListener('pagehide',cancelOnClose);
window.addEventListener('resize',updateViewport);
if(window.visualViewport)window.visualViewport.addEventListener('resize',updateViewport);
if(tg&&tg.onEvent)tg.onEvent('viewportChanged',updateViewport);
resetKeyboardInput();
updateViewport();
start().catch(error=>setStatus(error.message));
</script></body></html>"""


def build_viewer_document(launch_token: str, nonce: str) -> bytes:
    """Render the credential-blind, same-origin remote-auth viewer."""

    return (
        _VIEWER_DOCUMENT.replace("__NONCE__", nonce)
        .replace("__LAUNCH_TOKEN__", json.dumps(launch_token))
        .encode()
    )

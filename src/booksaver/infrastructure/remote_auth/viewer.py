from __future__ import annotations

import json

_VIEWER_DOCUMENT = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport"
 content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<title>Connect Booking.com</title>
<script src="https://telegram.org/js/telegram-web-app.js?63"></script>
<style nonce="__NONCE__">
:root{--app-height:100dvh;
 --safe-top:calc(max(env(safe-area-inset-top,0px),var(--host-safe-top,0px)) +
  var(--content-safe-top,0px));
 --safe-bottom:calc(max(env(safe-area-inset-bottom,0px),var(--host-safe-bottom,0px)) +
  var(--content-safe-bottom,0px));
 --safe-left:calc(max(env(safe-area-inset-left,0px),var(--host-safe-left,0px)) +
  var(--content-safe-left,0px));
 --safe-right:calc(max(env(safe-area-inset-right,0px),var(--host-safe-right,0px)) +
  var(--content-safe-right,0px))}
*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;overflow:hidden}
body{height:var(--app-height);display:flex;flex-direction:column;background:#101820;color:#fff;
 padding:var(--safe-top) var(--safe-right) 0 var(--safe-left);
 font:15px system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
#header{display:flex;align-items:center;flex-shrink:0;background:#182633}
#status{padding:8px 12px;background:#182633;line-height:1.3;min-height:38px}
#status{flex:1;min-width:0}#fullscreen{flex-shrink:0;margin:4px 8px 4px 0}
#size-hint{margin:0;padding:5px 12px;background:#22384a;font-size:13px;flex-shrink:0}
#help{margin:0;padding:7px 12px;background:#22384a;color:#e6f2fa;font-size:13px}
#viewer{flex:1;min-height:0;position:relative;overflow:auto;background:#000;overscroll-behavior:none}
#screen{width:100%;height:100%;min-height:100%;touch-action:none}
body.keyboard-open #screen{height:auto;min-height:max(100%,200vw)}
body.desktop-login.keyboard-open #screen{min-height:max(100%,62.5vw)}
#dock{display:flex;flex-shrink:0;flex-wrap:wrap;gap:6px;
 padding:7px 8px calc(7px + var(--safe-bottom));background:#182633}
button{min-width:44px;min-height:44px;margin:0;padding:8px 10px;border:1px solid #58728a;
 border-radius:8px;background:#26455f;color:#fff;font:inherit;font-weight:600}
button:disabled{opacity:.45}#keyboard{flex:1 0 auto}#cancel{background:#71383d;border-color:#a85a61}
#capture{position:fixed;left:-10000px;bottom:0;width:2px;height:2px;opacity:.01;
 pointer-events:none;border:0;padding:0}
#paste-panel{padding:8px 12px;background:#22384a;flex-shrink:0}
#paste-value{width:100%;min-height:44px;margin:6px 0;font:inherit}
#paste-panel[hidden]{display:none}
body.keyboard-open #keyboard{background:#0878d1;border-color:#6cb9f1}
body.keyboard-open #fullscreen{display:none}
body:not(.touch-first) #help,body:not(.touch-first) #help-button{display:none}
@media (orientation:landscape) and (max-height:520px){
 #status{padding:5px 10px;min-height:30px;font-size:13px}#help{padding:4px 10px}
 #dock{padding-top:4px;padding-bottom:calc(4px + var(--safe-bottom))}
}
</style></head><body>
<div id="header">
 <div id="status" role="status" aria-live="polite">Authorizing this connection…</div>
 <button id="fullscreen" type="button" hidden aria-pressed="false">Full screen</button>
</div>
<p id="size-hint" role="status" hidden></p>
<p id="help">Tap a Booking.com field, then tap Keyboard or Paste. A code suggested above the
 keyboard is typed for you. Use Next or Enter to continue.</p>
<div id="viewer"><div id="screen" aria-label="Remote Booking.com browser"></div></div>
<div id="paste-panel" hidden>
 <label for="paste-value">Paste here; it goes straight to the selected Booking.com field.</label>
 <input id="paste-value" type="password" autocomplete="one-time-code" autocapitalize="none"
  autocorrect="off" spellcheck="false" aria-label="Text to paste into the remote field">
 <button id="paste-insert" type="button" disabled>Insert</button>
 <button id="paste-close" type="button">Close</button>
</div>
<div id="dock" aria-label="Remote browser controls">
 <button id="keyboard" type="button" disabled aria-pressed="false">Keyboard</button>
 <button id="paste" type="button" disabled>Paste</button>
 <button id="next" type="button" disabled>Next</button>
 <button id="enter" type="button" disabled>Enter</button>
 <button id="help-button" type="button" aria-controls="help" aria-expanded="true">Help</button>
 <button id="cancel" type="button">Cancel</button>
</div>
<input id="capture" type="password" inputmode="text" autocomplete="one-time-code"
 autocapitalize="none"
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
const pasteButton=document.getElementById('paste');
const pastePanel=document.getElementById('paste-panel');
const pasteValue=document.getElementById('paste-value');
const pasteInsert=document.getElementById('paste-insert');
const pasteClose=document.getElementById('paste-close');
const nextButton=document.getElementById('next');
const enterButton=document.getElementById('enter');
const helpButton=document.getElementById('help-button');
const cancelButton=document.getElementById('cancel');
const fullscreenButton=document.getElementById('fullscreen');
const sizeHintNode=document.getElementById('size-hint');
const tg=window.Telegram&&window.Telegram.WebApp;
const platform=(tg&&tg.platform)||'unknown';
const touchFirst=['android','android_x','ios'].includes(platform)||
 ('ontouchstart' in window)||navigator.maxTouchPoints>0||
 (window.matchMedia&&window.matchMedia('(pointer:coarse)').matches);
document.body.classList.toggle('touch-first',touchFirst);
// This is a presentation hint, never identity evidence or a browser fingerprint.
const nativeDesktop=['tdesktop','macos','unigram'].includes(platform);
const knownWeb=['web','webk','weba'].includes(platform);
const finePointer=window.matchMedia&&window.matchMedia('(pointer:fine)').matches;
const loginDevice=nativeDesktop||(knownWeb&&finePointer&&!touchFirst)?'desktop':'mobile';
document.body.classList.toggle('desktop-login',loginDevice==='desktop');
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
let fullscreenSupported=false;
let inputGeneration=0;
let pasteAttempt=null;
const maxPasteCodepoints=1024;
const pasteKeyIntervalMs=50;
const hostClipboardTimeoutMs=800;
let pasteValueLength=0;

function updateFullscreen(){
 const active=Boolean(tg&&tg.isFullscreen);
 fullscreenButton.hidden=!fullscreenSupported;
 fullscreenButton.textContent=active?'Exit full screen':'Full screen';
 fullscreenButton.setAttribute('aria-pressed',String(active));
 updateViewport();
}
function fullscreenFailed(event){
 if(event&&event.error==='ALREADY_FULLSCREEN'){updateFullscreen();return;}
 if(event&&event.error==='UNSUPPORTED')fullscreenSupported=false;
 sizeHintNode.textContent='Full screen is unavailable. You can continue signing in here.';
 sizeHintNode.hidden=false;
 updateFullscreen();
}
function toggleFullscreen(){
 if(!fullscreenSupported)return;
 sizeHintNode.hidden=true;
 try{
  if(tg.isFullscreen)tg.exitFullscreen();
  else tg.requestFullscreen();
 }catch(_){fullscreenFailed();}
}
function initializePresentation(){
 if(!tg)return;
 // Window sizing is optional: host errors must never block the signed login exchange.
 try{tg.ready();}catch(_){}
 try{tg.expand();}catch(_){}
 try{
  fullscreenSupported=typeof tg.isVersionAtLeast==='function'&&tg.isVersionAtLeast('8.0')&&
   typeof tg.requestFullscreen==='function'&&typeof tg.exitFullscreen==='function'&&
   typeof tg.onEvent==='function';
 }catch(_){}
 if(fullscreenSupported){
  tg.onEvent('fullscreenChanged',()=>{sizeHintNode.hidden=true;updateFullscreen();});
  tg.onEvent('fullscreenFailed',fullscreenFailed);
 }
 updateFullscreen();
 const desktop=['tdesktop','macos','unigram'].includes(platform)||!touchFirst;
 if(desktop&&fullscreenSupported&&!tg.isFullscreen)toggleFullscreen();
}

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
 pasteButton.disabled=!enabled;
 pasteInsert.disabled=!enabled;
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
 for(const side of ['top','right','bottom','left']){
  for(const [prefix,insets] of [['host',tg&&tg.safeAreaInset],
                               ['content',tg&&tg.contentSafeAreaInset]]){
   const value=Number(insets&&insets[side]);
   const pixels=Number.isFinite(value)?Math.max(0,value):0;
   document.documentElement.style.setProperty(`--${prefix}-safe-${side}`,`${pixels}px`);
  }
 }
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
 invalidatePaste();
 setControlsEnabled(false);
 document.body.classList.remove('keyboard-open');
 keyboardButton.textContent='Keyboard';
 keyboardButton.setAttribute('aria-pressed','false');
 captureNode.blur();
 resetKeyboardInput();
 if(touchKeyboard){touchKeyboard.ungrab();touchKeyboard=null;}
}
function invalidatePaste(){
 inputGeneration++;
 if(pasteAttempt)pasteAttempt.characters=[];
 pasteAttempt=null;
 pasteValue.value='';
 pasteValueLength=0;
 pastePanel.hidden=true;
}
function pasteReady(){
 return rfb&&viewerAuthorized&&!terminalState&&!closeRequested&&!viewerError&&
  !keyboardButton.disabled;
}
function ownsPaste(attempt){
 return pasteReady()&&pasteAttempt===attempt&&rfb===attempt.connection&&
  inputGeneration===attempt.generation;
}
function beginPaste(){
 if(!pasteReady()||pasteAttempt)return null;
 const attempt={connection:rfb,generation:inputGeneration,characters:[],offset:0};
 pasteAttempt=attempt;
 return attempt;
}
function finishPaste(attempt){
 if(pasteAttempt!==attempt)return;
 attempt.characters=[];
 pasteAttempt=null;
 pasteValue.value='';
 pasteValueLength=0;
 resetKeyboardInput();
}
function pasteCharacters(text){
 if(typeof text!=='string'||text.length>maxPasteCodepoints)return null;
 const characters=Array.from(text);
 if(!characters.length||characters.length>maxPasteCodepoints)return null;
 if(characters.some(char=>{
  const point=char.codePointAt(0);
  return point<32||point>126;
 }))return null;
 return characters;
}
function pasteError(text){
 if(typeof text==='string'&&text.length<=maxPasteCodepoints&&
    Array.from(text).some(character=>character.codePointAt(0)>126))
  return 'Paste supports English letters, numbers, spaces and punctuation only. '+
   'Nothing was inserted.';
 return 'Use 1–1,024 characters on one line. Nothing was inserted.';
}
function showPasteFallback(){
 if(!pasteReady())return;
 pastePanel.hidden=false;
 pasteValue.focus({preventScroll:true});
 setStatus(touchFirst?
  'Long-press the box and choose Paste, or tap a code suggested above the keyboard. '+
  'It is sent right away.':
  'Paste into the box with Ctrl+V or Cmd+V. It is sent right away.');
}
function insertFromPanel(text){
 const attempt=beginPaste();
 if(attempt)insertPaste(attempt,text);
}
function insertPaste(attempt,text){
 if(!ownsPaste(attempt))return;
 attempt.characters=pasteCharacters(text);
 const invalidMessage=attempt.characters?'':pasteError(text);
 text='';
 if(!attempt.characters){
  finishPaste(attempt);
  setStatus(invalidMessage);
  return;
 }
 // blur clears noVNC's held-key bookkeeping without changing the remote field.
 // Release both sides explicitly, including a modifier captured before this shortcut.
 try{
  attempt.connection.blur();
  for(const [symbol,code] of [[0xffe3,'ControlLeft'],[0xffe4,'ControlRight'],
      [0xffeb,'MetaLeft'],[0xffec,'MetaRight'],[0xffe7,'MetaLeft'],[0xffe8,'MetaRight'],
      [0xffe1,'ShiftLeft'],[0xffe2,'ShiftRight'],[0xffe9,'AltLeft'],[0xffea,'AltRight']]){
   if(!ownsPaste(attempt))return;
   attempt.connection.sendKey(symbol,code,false);
  }
 }catch(_){finishPaste(attempt);setStatus('Could not insert text. Try Paste again.');return;}
 // One character per tick, paced so a page that moves focus asynchronously after each
 // input (for example a six-box verification code) advances before the next key arrives.
 const sendChunk=()=>{
  if(!ownsPaste(attempt))return;
  try{
   const character=attempt.characters[attempt.offset++];
   attempt.connection.sendKey(keysyms.lookup(character.codePointAt(0)));
   // A disconnect or cancel raised by the send itself must not report success.
   if(!ownsPaste(attempt))return;
   if(attempt.offset<attempt.characters.length){setTimeout(sendChunk,pasteKeyIntervalMs);return;}
   finishPaste(attempt);
   pastePanel.hidden=true;
   if(attempt.restoreFocus!==false)attempt.connection.focus();
   setStatus('Text sent to the selected field.');
  }catch(_){finishPaste(attempt);setStatus('Could not insert text. Try Paste again.');}
 };
 sendChunk();
}
function readHostClipboard(){
 // Telegram's Mini App clipboard read. It answers null when the host does not permit it,
 // and a silent host is treated the same after a short wait.
 return new Promise(resolve=>{
  let settled=false;
  const settle=value=>{if(!settled){settled=true;resolve(typeof value==='string'?value:null);}};
  try{
   if(!tg||typeof tg.readTextFromClipboard!=='function'||
      typeof tg.isVersionAtLeast!=='function'||!tg.isVersionAtLeast('6.4')){settle(null);return;}
   setTimeout(()=>settle(null),hostClipboardTimeoutMs);
   tg.readTextFromClipboard(settle);
  }catch(_){settle(null);}
 });
}
async function readPaste(event){
 if(!event.isTrusted)return;
 const attempt=beginPaste();
 if(!attempt)return;
 let text=null;
 try{
  if(navigator.clipboard&&typeof navigator.clipboard.readText==='function')
   text=await navigator.clipboard.readText();
 }catch(_){text=null;}
 if(!ownsPaste(attempt))return;
 if(typeof text!=='string')text=await readHostClipboard();
 if(!ownsPaste(attempt))return;
 if(typeof text==='string'){insertPaste(attempt,text);text='';return;}
 finishPaste(attempt);
 showPasteFallback();
}
function remoteInputTarget(target){
 return target===captureNode||viewerNode.contains(target);
}
window.addEventListener('keydown',event=>{
 if(pasteAttempt&&remoteInputTarget(event.target)){
  event.preventDefault();event.stopImmediatePropagation();return;
 }
 if(!(event.ctrlKey||event.metaKey)||event.altKey||event.key.toLowerCase()!=='v'||
    !remoteInputTarget(event.target))return;
 event.preventDefault();
 event.stopImmediatePropagation();
 if(!event.repeat)void readPaste(event);
},true);
// Keep the selected remote field stable while a read or queued insertion is pending.
for(const kind of ['pointerdown','pointerup','pointermove','mousedown','mouseup',
                   'mousemove','touchstart','touchmove','touchend','wheel']){
 window.addEventListener(kind,event=>{
  if(pasteAttempt&&remoteInputTarget(event.target)){
   event.preventDefault();event.stopImmediatePropagation();
  }
 },{capture:true,passive:false});
}
window.addEventListener('paste',event=>{
 if(!event.isTrusted||(!remoteInputTarget(event.target)&&event.target!==pasteValue))return;
 event.preventDefault();
 event.stopImmediatePropagation();
 if(!pasteReady()||pasteAttempt)return;
 let text=event.clipboardData&&event.clipboardData.getData('text/plain');
 if(event.target===pasteValue){
  pasteValue.value='';
  pasteValueLength=0;
  insertFromPanel(text);
 }else{
  const attempt=beginPaste();
  if(attempt)insertPaste(attempt,text);
 }
 text='';
},true);
function sendShortcut(keysym,code){
 if(rfb&&!terminalState&&!keyboardButton.disabled&&!pasteAttempt)rfb.sendKey(keysym,code);
}
function keyInput(event){
 if(!rfb||terminalState||composing||pasteAttempt)return;
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
 // A suggested one-time code or clipboard chip arrives as one multi-character input.
 // Pace it like a paste so auto-advancing fields keep up, and keep the keyboard open.
 const inserted=inputs>0?newValue.slice(newLen-inputs,newLen):'';
 const paced=inputs>=2&&pasteCharacters(inserted)?beginPaste():null;
 if(paced)paced.restoreFocus=false;
 else for(let i=newLen-inputs;i<newLen;i++)rfb.sendKey(keysyms.lookup(newValue.charCodeAt(i)));
 resetKeyboardInput();
 if(paced)insertPaste(paced,inserted);
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
  touchKeyboard.onkeyevent=(keysym,code,down)=>{
   if(rfb===current&&!terminalState&&!closeRequested&&(!pasteAttempt||!down))
    current.sendKey(keysym,code,down);
  };
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
  body:JSON.stringify({launch_token:launchToken,init_data:tg.initData,login_device:loginDevice})});
 viewerAuthorized=true;
 await poll();
}
function cancelOnClose(event){
 invalidatePaste();
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
pasteButton.addEventListener('click',event=>{
 if(!pastePanel.hidden){
  if(!pasteAttempt)showPasteFallback();
  return;
 }
 void readPaste(event);
});
pasteInsert.addEventListener('click',event=>{
 if(!event.isTrusted)return;
 insertFromPanel(pasteValue.value);
});
pasteValue.addEventListener('input',event=>{
 const value=pasteValue.value;
 const added=value.length-pasteValueLength;
 pasteValueLength=value.length;
 const suggested=['insertFromPaste','insertReplacementText','insertFromDrop']
  .includes(event.inputType);
 if(!pasteAttempt&&(suggested||added>=2)&&pasteCharacters(value)){
  pasteValue.value='';
  pasteValueLength=0;
  insertFromPanel(value);
 }
});
pasteClose.addEventListener('click',()=>{invalidatePaste();if(pasteReady())rfb.focus();});
fullscreenButton.addEventListener('click',toggleFullscreen);
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
if(tg&&tg.onEvent){
 tg.onEvent('viewportChanged',updateViewport);
 tg.onEvent('safeAreaChanged',updateViewport);
 tg.onEvent('contentSafeAreaChanged',updateViewport);
}
resetKeyboardInput();
updateViewport();
initializePresentation();
start().catch(error=>setStatus(error.message));
</script></body></html>"""


def build_viewer_document(launch_token: str, nonce: str) -> bytes:
    """Render the credential-blind, same-origin remote-auth viewer."""

    return (
        _VIEWER_DOCUMENT.replace("__NONCE__", nonce)
        .replace("__LAUNCH_TOKEN__", json.dumps(launch_token))
        .encode()
    )

const test=require('node:test'), assert=require('node:assert/strict'), fs=require('node:fs'), vm=require('node:vm');
const dashboard=fs.readFileSync('static/js/dashboard.js','utf8');
const portal=fs.readFileSync('core/templates/core/employee_portal.html','utf8');
function deferred(){let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};}
function picker(id){return {id,files:[],set value(v){if(v==='')this.files=[];}};}
function hr(){
  const pending=deferred(),posted=[],appended=[],reads=[];
  const input={value:'message A'},file=picker('chatFileInput'),image=picker('chatImageInput');
  const elements={chatTextInput:input,chatFileInput:file,chatImageInput:image,chatStreamMessages:{},hrChatAttachmentPreview:{style:{}},hrChatAttachmentName:{}};
  const ctx=vm.createContext({document:{getElementById:id=>elements[id]},activeConversationKey:'A',messagesLoadVersion:0,hrChatComposerRevision:0,hrChatSendInFlight:false,
    FormData:function(){this.append=(key,value)=>posted.push([key,value]);},apiFetch:()=>pending.promise,showToast(){},
    appendPersistedMessage:(_s,m)=>appended.push(m),markConversationRead:(key,id)=>reads.push([key,id]),refreshHrChatUnreadDots(){}});
  vm.runInContext(dashboard.slice(dashboard.indexOf('function removeHrChatAttachment('),dashboard.indexOf('function escapeHtml(',dashboard.indexOf('async function handleSendChatMessage('))),ctx);
  return {ctx,pending,posted,appended,reads,input,file,image,elements,send:()=>ctx.handleSendChatMessage({preventDefault(){}}),finish:()=>pending.resolve({ok:true,json:async()=>({id:'m-A',conversation_key:'A'})})};
}
test('HR attachment selection replaces the alternate picker and invalid selections clear preview',()=>{
  const t=hr();t.file.files=[{name:'old.pdf',size:10}];t.image.files=[{name:'new.png',size:10}];
  t.ctx.handleChatFileSelected(t.image);assert.equal(t.file.files.length,0);assert.equal(t.elements.hrChatAttachmentName.textContent,'new.png');
  t.file.files=[{name:'bad.exe',size:10}];t.ctx.handleChatFileSelected(t.file);
  assert.equal(t.image.files.length,0);assert.equal(t.file.files.length,0);assert.equal(t.elements.hrChatAttachmentPreview.style.display,'none');
});
test('HR completion does not append, clear or mark read in another conversation',async()=>{
  const t=hr(),sending=t.send();t.ctx.activeConversationKey='B';t.input.value='new draft B';t.finish();await sending;
  assert.equal(t.posted.find(([k])=>k==='conversation_key')[1],'A');assert.equal(t.input.value,'new draft B');assert.equal(t.appended.length,0);assert.equal(t.reads.length,0);
});
test('HR preserves edits while sending and suppresses overlapping sends',async()=>{
  const t=hr(),sending=t.send();await t.send();t.input.value='new draft A';t.ctx.hrChatComposerRevision++;t.finish();await sending;
  assert.equal(t.posted.filter(([k])=>k==='conversation_key').length,1);assert.equal(t.input.value,'new draft A');assert.equal(t.appended.length,1);
});
test('unchanged HR composer clears after confirmed success',async()=>{
  const t=hr(),sending=t.send();t.finish();await sending;assert.equal(t.input.value,'');assert.equal(t.reads[0][0],'A');
});
for(const switched of [true,false])test(`employee preserves newer draft ${switched?'after switching':'in same chat'}`,async()=>{
  const pending=deferred(),button={disabled:false},posted=[];
  const input={value:'employee A',form:{querySelector:()=>button}};
  const ctx=vm.createContext({document:{getElementById:id=>id==='chatComposerInput'?input:null},currentConvKey:'A',employeeChatSendInFlight:false,employeeChatComposerRevision:0,
    FormData:function(){this.append=(k,v)=>posted.push([k,v]);},portalFetch:()=>pending.promise,payload:r=>r.json(),removeChatAttachment(){},apiErrorMessage(){},showStatus(){},loadChatMessages(){}});
  vm.runInContext(portal.slice(portal.indexOf('async function sendChatMessage('),portal.indexOf('function handleChatKeyDown(',portal.indexOf('async function sendChatMessage('))),ctx);
  const sending=ctx.sendChatMessage();await ctx.sendChatMessage();if(switched)ctx.currentConvKey='B';ctx.employeeChatComposerRevision++;input.value='new draft';
  pending.resolve({ok:true,json:async()=>({id:'m-A'})});await sending;
  assert.equal(input.value,'new draft');assert.equal(button.disabled,false);assert.equal(posted.filter(([k])=>k==='conversation_key').length,1);
});

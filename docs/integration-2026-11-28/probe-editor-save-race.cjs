const fs=require('node:fs');
const vm=require('node:vm');
const crypto=require('node:crypto');

async function examine(filename){
  class Element {
    constructor(){this.listeners={};this.children=[];this.value='';this.textContent='';this.hidden=false;this.disabled=false;this.classList={add(){},remove(){}};}
    addEventListener(event,callback){this.listeners[event]=callback;}
    setAttribute(){}
    append(...nodes){this.children.push(...nodes);}
    appendChild(node){this.children.push(node);return node;}
    replaceChildren(...nodes){this.children=[...nodes];}
    scrollIntoView(){}
  }
  const elements=new Map();
  const get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
  const original={id:'a'.repeat(32),title:'Owned source',language:'en',method:'owned',segments:[{start:0,end:3,text:'Original text.'}],translations:{},summary:null,highlights:null};
  let saved=structuredClone(original),finish;
  const context={document:{getElementById:get,createElement:()=>new Element()},confirm:()=>true,
    fakeApi:async(url,options={})=>{
      if(options.method==='PUT'){
        const payload=JSON.parse(options.body);
        saved={...saved,title:payload.title,segments:payload.segments.map((s,i)=>({...saved.segments[i],...s}))};
        return await new Promise(resolve=>{finish=resolve;});
      }
      return structuredClone(saved);
    }};
  const html=fs.readFileSync(filename,'utf8');
  let script=html.match(/<script>([\s\S]*)<\/script>/)[1];
  // Expose actual closure functions and replace transport only. No editor logic is rewritten.
  script=script.replace(/\}\)\(\);\s*$/,'api=globalThis.fakeApi;globalThis.probe={openEditor};})();');
  vm.runInNewContext(script,context,{filename});
  await context.probe.openEditor(original.id);
  let input=get('editor-rows').children[0].children[2];
  input.value='Earlier saved text.';input.listeners.input();
  const saving=get('editor-save').listeners.click();
  if(!finish)throw new Error('Actual save did not reach controlled pending transport');
  input.value='Newer unsaved correction.';input.listeners.input();
  finish({ok:true});await saving;
  const shown=get('editor-rows').children[0].children[2].value;
  return {file:filename,sha256:crypto.createHash('sha256').update(html).digest('hex'),
    saved_text:saved.segments[0].text,displayed_text:shown,notice:get('editor-message').textContent,
    newer_edit_preserved:shown==='Newer unsaved correction.',scope:'Actual inline editor logic; controlled DOM and delayed transport; not a browser or database test.'};
}
(async()=>{for(const file of process.argv.slice(2))console.log(JSON.stringify(await examine(file)));})().catch(error=>{console.error(error);process.exitCode=1;});

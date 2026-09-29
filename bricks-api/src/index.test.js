import test from 'node:test';
import assert from 'node:assert/strict';
import worker, {parseInventory,validateImage} from './index.js';

const origin='https://pllato.github.io';
const image={mime:'image/png',image:'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jJ1kAAAAASUVORK5CYII='};
const output=items=>({choices:[{finish_reason:'stop',message:{content:JSON.stringify({items})}}]});
function setup(result=output([{color:'red',size:'2x4',count:2}])) {
  let calls=0;
  return { env:{ALLOWED_ORIGIN:origin,PHOTO_LIMIT:{limit:async()=>({success:true})},TOTAL_LIMIT:{limit:async()=>({success:true})},AI:{run:async(model,input)=>{
    calls++;
    assert.equal(input.messages[0].content[1].image_url.url,`data:image/png;base64,${image.image}`);
    return result;
  }}}, calls:()=>calls };
}
function request(body=image,headers={}){return new Request('https://example.test/recognize',{method:'POST',headers:{Origin:origin,'Content-Type':'application/json',...headers},body:JSON.stringify(body)});}
test('image is passed to vision and only normalized inventory is returned',async()=>{
  const s=setup(); const r=await worker.fetch(request(),s.env);
  assert.equal(r.status,200);assert.equal(s.calls(),1);
  assert.equal(r.headers.get('Access-Control-Allow-Origin'),origin);
  assert.deepEqual((await r.json()).items,[{color:'red',size:'2x4',count:2}]);
});
test('empty inventory is a valid recognition outcome',()=>assert.deepEqual(parseInventory(output([])).items,[]));
test('duplicate entries are combined',()=>assert.equal(parseInventory(output([{color:'red',size:'2x4',count:2},{color:'red',size:'2x4',count:3}])).items[0].count,5));
test('invalid AI output never reaches inventory',()=>{
  for(const item of [{color:'red',size:'2x4',count:-2},{color:'red',size:'2x4',count:1.2},{color:'red',size:'2x4',count:'2'},{color:'red',size:'4x4',count:1},{color:'<img>',size:'2x4',count:1}]) assert.throws(()=>parseInventory(output([item])));
  assert.throws(()=>parseInventory({choices:[{finish_reason:'length',message:{content:'{"items":[]}'}}]}));
  assert.throws(()=>parseInventory(output([{color:'red',size:'2x4',count:99},{color:'red',size:'2x4',count:1}])));
});
test('foreign and missing origins cannot invoke AI',async()=>{
  for(const o of ['https://evil.example','null','']){const s=setup();assert.equal((await worker.fetch(request(image,{Origin:o}),s.env)).status,403);assert.equal(s.calls(),0);}
});
test('preflight does not invoke AI',async()=>{
  const s=setup();const r=await worker.fetch(new Request('https://example.test/recognize',{method:'OPTIONS',headers:{Origin:origin}}),s.env);assert.equal(r.status,204);assert.equal(s.calls(),0);
});
test('rate limit prevents model invocation',async()=>{
  for(const key of ['PHOTO_LIMIT','TOTAL_LIMIT']){const s=setup();s.env[key].limit=async()=>({success:false});assert.equal((await worker.fetch(request(),s.env)).status,429);assert.equal(s.calls(),0);}
});
test('invalid, oversized and disguised images are rejected',async()=>{
  assert.throws(()=>validateImage({mime:'image/jpeg',image:image.image}));
  for(const body of [{...image,image:'not base64'},null,{...image,image:'a'.repeat(4_000_001)}]){const s=setup();const r=await worker.fetch(request(body),s.env);assert.ok([400,413].includes(r.status));assert.equal(s.calls(),0);}
});
test('provider errors do not leak details',async()=>{
  const s=setup();s.env.AI.run=async()=>{throw Error('secret and image data');};const r=await worker.fetch(request(),s.env);assert.equal(r.status,503);assert.deepEqual(await r.json(),{error:'ai_unavailable'});
});

'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {createClock,ease,interpolate,timeline}=require('../casepath/assets/autonomous-presentation-v1.js');
function fixture(start=0,options={}) {
  let at=start,id=0;const queued=new Map();
  const runtime={performance:{now:()=>at},requestAnimationFrame:fn=>{queued.set(++id,fn);return id;},cancelAnimationFrame:id=>queued.delete(id)};
  const clock=createClock(runtime,options),element={isConnected:true,style:{},animate(){throw new Error('Native animation is forbidden.');}};
  return {clock,element,queued,advance(ms){at+=ms;const work=[...queued.values()];queued.clear();for(const fn of work)fn(at);clock.sample();}};
}
test('pause freezes motion and reading holds, including a long interruption',async()=>{
  const f=fixture(),motion=f.clock.animate(f.element,[{opacity:0},{opacity:1}],500);
  f.advance(200);const opacity=f.element.style.opacity;assert.ok(Number(opacity)>0&&Number(opacity)<1);
  f.clock.pause();f.advance(60000);assert.equal(f.element.style.opacity,opacity);assert.equal(f.clock.now(),200);
  f.clock.resume();f.advance(300);assert.equal(await motion,true);assert.equal(f.element.style.opacity,'1');
  let held=false;const hold=f.clock.hold(900).then(done=>{held=done;});f.advance(899);await Promise.resolve();assert.equal(held,false);f.advance(1);await hold;assert.equal(held,true);
});
test('capture seeks an absolute timeline at exact n times 1000/60, independent of host origin',()=>{
  const a=fixture(0),b=fixture(987654321),frames=[];
  a.clock.onFrame(at=>frames.push(at));
  for(let n=0;n<120;n++){const at=n*1000/60;assert.equal(a.clock.seek(at),at);assert.equal(b.clock.seek(at),at);assert.equal(a.clock.now(),b.clock.now());}
  assert.deepEqual(frames,Array.from({length:120},(_,n)=>n*1000/60));
  assert.equal(a.queued.size,0);assert.equal(b.queued.size,0);
});
test('reduced motion keeps reading holds and changes states instantly',async()=>{
  const f=fixture(0,{reducedMotion:true});assert.equal(await f.clock.animate(f.element,[{opacity:0},{opacity:1}],700),true);assert.equal(f.clock.activeEffects,0);assert.equal(f.element.style.opacity,'1');
  let settled=false;const hold=f.clock.hold(900).then(()=>settled=true);f.advance(899);await Promise.resolve();assert.equal(settled,false);f.advance(1);await hold;assert.equal(settled,true);
});
test('a second visual change, layout properties and incompatible transforms are rejected',async()=>{
  const f=fixture(),first=f.clock.animate(f.element,[{opacity:0},{opacity:1}],250);
  assert.throws(()=>f.clock.animate(f.element,[{opacity:0},{opacity:1}],250),/active visual change/);f.advance(250);await first;
  assert.throws(()=>f.clock.animate(f.element,[{width:'0px'},{width:'10px'}],300),/transform and opacity only/);
  assert.throws(()=>f.clock.animate(f.element,[{opacity:0},{opacity:1}],50),/250–700/);
  assert.throws(()=>interpolate('translateX(0px)','scale(1)',.5),/matching/);
});
test('navigation or a removed element settles pending work without completion',async()=>{
  const f=fixture(),motion=f.clock.animate(f.element,[{opacity:0},{opacity:1}],500),hold=f.clock.hold(900);f.clock.cancel();assert.deepEqual(await Promise.all([motion,hold]),[false,false]);assert.equal(f.queued.size,0);assert.equal(f.element.style.opacity,'0');
  const g=fixture(),removed=g.clock.animate(g.element,[{opacity:0},{opacity:1}],500);g.element.isConnected=false;g.advance(20);assert.equal(await removed,false);assert.equal(g.clock.activeEffects,0);
});
test('recorded payload cannot override presentation timestamps or event kinds',()=>{
  const f=fixture();f.advance(123);const event=f.clock.mark('fact',{operation:'op-12',at:0,kind:'invented'});assert.equal(event.at,123);assert.equal(event.kind,'fact');assert.equal(event.operation,'op-12');assert.equal(Object.isFrozen(event),true);
});
test('timeline boundaries are deterministic and never borrow time from reading holds',()=>{
  const t=timeline([{act:'customer',duration:250,phase:'cursor'},{act:'customer',duration:900,phase:'reading-hold'},{act:'reading',duration:700,phase:'camera'}]);
  assert.equal(t.duration,1850);assert.equal(t.at(249).beat.phase,'cursor');assert.equal(t.at(250).beat.phase,'reading-hold');assert.equal(t.at(1149).beat.phase,'reading-hold');assert.equal(t.at(1150).beat.phase,'camera');assert.equal(t.at(2000).progress,1);
  assert.equal(ease(0),0);assert.equal(ease(1),1);assert.ok(ease(.5)>.8);assert.equal(interpolate('translate(0px, 10px) scale(1)','translate(20px, 0px) scale(1.08)',.5),'translate(10px, 5px) scale(1.04)');
});


test('external frame stepping freezes wall time without changing the user playing state',()=>{
  const f=fixture(125000),samples=[];f.clock.onFrame(at=>samples.push(at));
  f.clock.stepTo(1000/60);assert.equal(f.clock.now(),1000/60);assert.equal(f.clock.paused,false);assert.equal(f.clock.externallyDriven,true);assert.equal(f.queued.size,0);
  f.advance(60000);assert.equal(f.clock.now(),1000/60);f.clock.stepTo(2000/60);assert.equal(f.clock.now(),2000/60);
  f.clock.pause();assert.equal(f.clock.paused,true);f.clock.resume();f.advance(100);assert.ok(Math.abs(f.clock.now()-(2000/60+100))<1e-7);assert.equal(f.clock.externallyDriven,false);f.clock.stepTo(200);f.clock.resume();f.advance(100);assert.equal(f.clock.now(),300);
});

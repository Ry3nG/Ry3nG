import * as THREE from 'three';
import {EffectComposer} from 'three/addons/postprocessing/EffectComposer.js';
import {RenderPass} from 'three/addons/postprocessing/RenderPass.js';
import {UnrealBloomPass} from 'three/addons/postprocessing/UnrealBloomPass.js';
import {OutputPass} from 'three/addons/postprocessing/OutputPass.js';
import {RoundedBoxGeometry} from 'three/addons/geometries/RoundedBoxGeometry.js';

const Q=new URLSearchParams(location.search);const THEME=Q.get('theme')||'dark',DARK=THEME==='dark';
const OW=Number(Q.get('w')||1170),OH=Number(Q.get('h')||520),SS=2,RW=OW*SS,RH=OH*SS,FPS=15,DUR=24,N=FPS*DUR;
const P=DARK?{bg:0x0d1117,tile:0x1c2430,tileHot:0x2a3442,lv:[0x0e4429,0x006d32,0x26a641,0x56d364],hemi:[0x9fb4d0,0x0b0f15,.55],key:1.15,txt:'#8b949e'}
            :{bg:0xffffff,tile:0xe6eaef,tileHot:0xd5dbe3,lv:[0x9be9a8,0x40c463,0x30a14e,0x216e39],hemi:[0xffffff,0xdfe5ec,1.0],key:1.6,txt:'#57606a'};
const ease=x=>x*x*(3-2*x),clamp=(x,a=0,b=1)=>Math.min(b,Math.max(a,x));
const backOut=p=>{const c1=1.55,c3=c1+1;return 1+c3*Math.pow(p-1,3)+c1*Math.pow(p-1,2)};

/* ---------- data ---------- */
const days=(await (await fetch('data.json')).json()).days;           // last year of the contribution graph
const clock=await (await fetch('clock.json')).json();           // [7 weekdays][24 hours], all years aggregated
const quart=a=>{const s=a.filter(v=>v>0).sort((x,y)=>x-y);return [.25,.5,.75].map(f=>s[Math.floor(s.length*f)])};
const mk=q=>c=>c<=0?-1:c<=q[0]?0:c<=q[1]?1:c<=q[2]?2:3;

/* ---------- layout: two blocks of the same kind of object ---------- */
const ZA=8.0,ZB=-8.6,PB=1.3;
const qa=quart(days.map(d=>d[2])),la=mk(qa),MXA=Math.max(...days.map(d=>d[2]));
const qb=quart(clock.flat()),lb=mk(qb),MXB=Math.max(...clock.flat());
const cells=[];
days.forEach((d,i)=>{const c=Math.floor(i/7),r=i%7;cells.push({blk:0,x:c-26,z:ZA+(r-3),n:d[2],lv:la(d[2]),h:d[2]>0?.45+Math.pow(d[2]/MXA,.6)*9.5:0,fp:.84,c,r,date:d[0]})});
const bx0=-(23*PB)/2;
for(let d=0;d<7;d++)for(let h=0;h<24;h++){const n=clock[d][h];cells.push({blk:1,x:bx0+h*PB,z:ZB+(d-3)*PB,n,lv:lb(n),h:n>0?.5+Math.pow(n/MXB,.7)*10.5:0,fp:PB*.84,c:h,r:d})}

/* ---------- drone choreography ---------- */
const SEG=[{t0:1.0,t1:9.6,x0:-30,x1:30,z:ZA,half:4.5},{t0:12.0,t1:19.0,x0:-19,x1:19,z:ZB,half:5.4}];
const T_END=19.0;
function dpos(t){
  const A=SEG[0],B=SEG[1];
  if(t<A.t0){const u=ease(clamp(t/A.t0));return {x:A.x0-10*(1-u),z:A.z,y:0,on:0,half:A.half,seg:-1}}
  if(t<=A.t1){const u=(t-A.t0)/(A.t1-A.t0);return {x:A.x0+(A.x1-A.x0)*u,z:A.z,y:0,on:1,half:A.half,seg:0}}
  if(t<B.t0){const u=ease((t-A.t1)/(B.t0-A.t1));return {x:A.x1+(B.x0-A.x1)*u,z:A.z+(B.z-A.z)*u,y:Math.sin(u*Math.PI)*4,on:Math.max(0,1-(t-A.t1)/.35),half:A.half+(B.half-A.half)*u,seg:-1}}
  if(t<=B.t1){const u=(t-B.t0)/(B.t1-B.t0);return {x:B.x0+(B.x1-B.x0)*u,z:B.z,y:0,on:1,half:B.half,seg:1}}
  return {x:B.x1,z:B.z,y:0,on:0,half:B.half,seg:-1}}
const tab=[[],[]];
for(let i=0;i<=N*20;i++){const t=i/(FPS*20),p=dpos(t);if(p.seg>=0&&p.on>.99)tab[p.seg].push([t,p.x])}
function tCross(x,s){for(const [t,xx] of tab[s])if(xx>=x)return t;return 99}
cells.forEach(k=>{k.tr=tCross(k.x-.25,k.blk)+(k.r-3)*.04});

/* ---------- renderer ---------- */
const renderer=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});
renderer.setSize(RW,RH,false);renderer.setClearColor(P.bg,1);
renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFShadowMap;renderer.toneMapping=THREE.NoToneMapping;
const scene=new THREE.Scene();scene.background=new THREE.Color(P.bg);
const cam=new THREE.PerspectiveCamera(30,RW/RH,1,500);
scene.add(new THREE.HemisphereLight(P.hemi[0],P.hemi[1],P.hemi[2]));
const key=new THREE.DirectionalLight(0xffffff,P.key);key.position.set(-22,40,26);key.castShadow=true;
key.shadow.mapSize.set(4096,2048);const sc=key.shadow.camera;sc.left=-42;sc.right=42;sc.top=26;sc.bottom=-26;sc.near=5;sc.far=140;key.shadow.bias=-.0004;scene.add(key);
const rim=new THREE.DirectionalLight(DARK?0x7fc6ff:0xffffff,DARK?.45:0);rim.position.set(30,18,-30);scene.add(rim);

/* floor: page colour + one soft pool of light + real shadows */
if(DARK){
  const cv=document.createElement('canvas');cv.width=cv.height=512;const g=cv.getContext('2d');const gr=g.createRadialGradient(256,256,0,256,256,256);
  gr.addColorStop(0,'rgb(25,33,44)');gr.addColorStop(.5,'rgb(19,26,35)');gr.addColorStop(1,'rgb(13,17,23)');g.fillStyle=gr;g.fillRect(0,0,512,512);
  const tex=new THREE.CanvasTexture(cv);tex.colorSpace=THREE.SRGBColorSpace;
  const pool=new THREE.Mesh(new THREE.PlaneGeometry(180,80),new THREE.MeshBasicMaterial({map:tex,toneMapped:false}));pool.rotation.x=-Math.PI/2;pool.position.set(0,-.01,-1);scene.add(pool);
  const bgp=new THREE.Mesh(new THREE.PlaneGeometry(1200,1200),new THREE.MeshBasicMaterial({color:P.bg,toneMapped:false}));bgp.rotation.x=-Math.PI/2;bgp.position.y=-.02;scene.add(bgp);
}
{const f=new THREE.Mesh(new THREE.PlaneGeometry(400,400),new THREE.ShadowMaterial({opacity:DARK?.55:.16}));f.rotation.x=-Math.PI/2;f.position.y=.003;f.receiveShadow=true;scene.add(f);}

/* ---------- tiles & bars ---------- */
const tileG=new RoundedBoxGeometry(1,1,1,2,.12),barG=new RoundedBoxGeometry(1,1,1,3,.14);
const tiles=new THREE.InstancedMesh(tileG,new THREE.MeshStandardMaterial({roughness:.7,metalness:0}),cells.length);tiles.receiveShadow=true;scene.add(tiles);
const active=cells.filter(k=>k.n>0);
const bars=new THREE.InstancedMesh(barG,new THREE.MeshStandardMaterial({roughness:.38,metalness:.05}),active.length);bars.castShadow=true;bars.receiveShadow=true;scene.add(bars);
const glowM=new THREE.InstancedMesh(barG,new THREE.MeshBasicMaterial({transparent:true,blending:THREE.AdditiveBlending,depthWrite:false,toneMapped:false}),active.length);scene.add(glowM);
const col=new THREE.Color(),tmp=new THREE.Matrix4(),q0=new THREE.Quaternion(),v3=new THREE.Vector3(),s3=new THREE.Vector3();
const base=new THREE.Color(P.tile),hot=new THREE.Color(P.tileHot);
active.forEach((k,i)=>bars.setColorAt(i,col.set(P.lv[k.lv])));


/* ---------- axis labels lying on the floor (appear when scanned) ---------- */
const labels=[];
function label(text,x,z,align,tr,size=1.8){
  const c=document.createElement('canvas');c.width=512;c.height=128;const g=c.getContext('2d');g.font='600 76px -apple-system,"Helvetica Neue",Arial,sans-serif';g.fillStyle=P.txt;g.textBaseline='middle';
  g.textAlign=align;g.fillText(text,align==='left'?10:align==='right'?502:256,66);
  const tex=new THREE.CanvasTexture(c);tex.colorSpace=THREE.SRGBColorSpace;tex.anisotropy=8;
  const w=size*4,m=new THREE.Mesh(new THREE.PlaneGeometry(w,size),new THREE.MeshBasicMaterial({map:tex,transparent:true,opacity:0,depthWrite:false,toneMapped:false}));
  m.rotation.x=-Math.PI/2;const off=align==='left'?w/2:align==='right'?-w/2:0;m.position.set(x+off,.03,z);scene.add(m);labels.push({m,tr});}
const MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
let lastM=-1;days.forEach((d,i)=>{if(i%7)return;const c=i/7,dt=new Date(d[0]+'T00:00:00Z'),m=dt.getUTCMonth();if(m!==lastM&&dt.getUTCDate()<=7){lastM=m;if(c<50)label(MON[m],c-26-.4,ZA+3.6+1.3,'left',tCross(c-26-.25,0)+.3)}});
for(let h=0;h<24;h+=3)label(String(h).padStart(2,'0'),bx0+h*PB-.3,ZB+3*PB+PB*.5+1.0,'left',tCross(bx0+h*PB-.25,1)+.3);
[['Mon',1],['Wed',3],['Fri',5]].forEach(([t,r])=>label(t,bx0-PB*.9,ZB+(r-3)*PB+.1,'right',tCross(bx0-.25,1)+.3,1.5));

/* ---------- drone ---------- */
const drone=new THREE.Group();scene.add(drone);
const dm=new THREE.MeshStandardMaterial({color:DARK?0xd8dee8:0x2a313b,metalness:.5,roughness:.32});
const dk=new THREE.MeshStandardMaterial({color:DARK?0x2a313b:0xe8ecf1,metalness:.6,roughness:.3});
const body=new THREE.Mesh(new RoundedBoxGeometry(1.15,.3,.95,4,.13),dm);body.castShadow=true;drone.add(body);
const top=new THREE.Mesh(new RoundedBoxGeometry(.62,.16,.56,3,.07),dk);top.position.y=.2;drone.add(top);
const led=new THREE.Mesh(new THREE.BoxGeometry(.18,.05,.06),new THREE.MeshBasicMaterial({color:0x56d364,toneMapped:false}));led.position.set(.62,.04,0);drone.add(led);
const rotors=[];
[[1,1],[1,-1],[-1,1],[-1,-1]].forEach(([sx,sz])=>{
  const arm=new THREE.Mesh(new THREE.BoxGeometry(1.05,.07,.12),dm);arm.position.set(sx*.62,.02,sz*.62);arm.rotation.y=Math.atan2(-sz,sx);arm.castShadow=true;drone.add(arm);
  const mt=new THREE.Mesh(new THREE.CylinderGeometry(.14,.16,.14,20),dk);mt.position.set(sx*1.02,.1,sz*1.02);mt.castShadow=true;drone.add(mt);
  const disc=new THREE.Mesh(new THREE.CircleGeometry(.7,40),new THREE.MeshBasicMaterial({color:DARK?0xffffff:0x2a313b,transparent:true,opacity:.1,side:THREE.DoubleSide,depthWrite:false}));disc.rotation.x=-Math.PI/2;disc.position.set(sx*1.02,.2,sz*1.02);drone.add(disc);
  const ring=new THREE.Mesh(new THREE.TorusGeometry(.7,.012,6,48),new THREE.MeshBasicMaterial({color:DARK?0xffffff:0x2a313b,transparent:true,opacity:.35}));ring.rotation.x=Math.PI/2;ring.position.copy(disc.position);drone.add(ring);rotors.push(disc)});
const dome=new THREE.Mesh(new THREE.SphereGeometry(.2,24,16,0,Math.PI*2,Math.PI/2,Math.PI/2),new THREE.MeshStandardMaterial({color:0x0a0d12,metalness:.9,roughness:.15}));dome.position.y=-.14;drone.add(dome);
const lring=new THREE.Mesh(new THREE.TorusGeometry(.22,.025,8,32),new THREE.MeshBasicMaterial({color:0x7ee787,toneMapped:false}));lring.rotation.x=Math.PI/2;lring.position.y=-.13;drone.add(lring);
drone.scale.setScalar(2.3);
const fanG=new THREE.BufferGeometry();const fanPos=new Float32Array(9),fanCol=new Float32Array(9);fanG.setAttribute('position',new THREE.BufferAttribute(fanPos,3));fanG.setAttribute('color',new THREE.BufferAttribute(fanCol,3));
const fan=new THREE.Mesh(fanG,new THREE.MeshBasicMaterial({vertexColors:true,transparent:true,blending:THREE.AdditiveBlending,depthWrite:false,side:THREE.DoubleSide,toneMapped:false}));fan.frustumCulled=false;scene.add(fan);
const lineM=new THREE.Mesh(new THREE.BoxGeometry(.07,.04,2),new THREE.MeshBasicMaterial({color:DARK?0xc9ffd8:0x1a7f37,toneMapped:false}));scene.add(lineM);
const glowLine=new THREE.Mesh(new THREE.BoxGeometry(.9,.02,2),new THREE.MeshBasicMaterial({color:DARK?0x56d364:0x2da44e,transparent:true,opacity:DARK?.16:.12,blending:DARK?THREE.AdditiveBlending:THREE.NormalBlending,depthWrite:false,toneMapped:false}));scene.add(glowLine);
const FAN=DARK?[.07,.30,.17]:[.05,.24,.11];

/* ---------- post ---------- */
const composer=new EffectComposer(renderer);composer.setSize(RW,RH);composer.addPass(new RenderPass(scene,cam));
if(DARK)composer.addPass(new UnrealBloomPass(new THREE.Vector2(RW,RH),.26,.5,.7));
composer.addPass(new OutputPass());
const out=document.getElementById('out');out.width=OW;out.height=OH;const o2=out.getContext('2d');

window.setup=()=>({frames:N});
window.frame=async(i)=>{
  const t=i/FPS,after=t>T_END,dp=dpos(t);
  cells.forEach((k,idx)=>{const s=t>=k.tr?1:0;col.copy(base).lerp(hot,s);
    tmp.compose(v3.set(k.x,.04,k.z),q0,s3.set(k.fp,.08,k.fp));tiles.setMatrixAt(idx,tmp);tiles.setColorAt(idx,col)});
  tiles.instanceMatrix.needsUpdate=true;tiles.instanceColor.needsUpdate=true;
  active.forEach((k,i)=>{
    const p=clamp((t-k.tr)/.85),e=p<=0?0:backOut(p),H=k.h*e,vis=p>0?1:0,fp=k.fp;
    tmp.compose(v3.set(k.x,H/2+.08,k.z),q0,s3.set(fp*vis,Math.max(.001,H)*vis,fp*vis));bars.setMatrixAt(i,tmp);
    const age=t-k.tr,fl=age<0?0:Math.exp(-age*2.6)*.9;
    tmp.compose(v3.set(k.x,H/2+.08,k.z),q0,s3.set(fp*1.04*vis,Math.max(.001,H)*1.01*vis,fp*1.04*vis));glowM.setMatrixAt(i,tmp);
    glowM.setColorAt(i,col.set(P.lv[k.lv]).multiplyScalar(DARK?fl*1.6:0))});
  bars.instanceMatrix.needsUpdate=true;bars.instanceColor.needsUpdate=true;glowM.instanceMatrix.needsUpdate=true;glowM.instanceColor.needsUpdate=true;
  labels.forEach(L=>{L.m.material.opacity=clamp((t-L.tr)/.6)*.95});
  // drone
  const dy=14.2+dp.y+Math.sin(t*1.7)*.2;
  let dxx=dp.x,dyy=dy;
  if(after){const u=ease(clamp((t-T_END)/2.6));dxx=dp.x+u*24;dyy=dy+u*10}
  const vx=(dpos(t+.05).x-dpos(t-.05).x)/.1;
  drone.position.set(dxx,dyy,dp.z+Math.sin(t*.9)*.3);
  drone.rotation.z=-clamp(vx,-8,8)*.014;drone.rotation.x=Math.sin(t*1.3)*.015;
  rotors.forEach((r,ix)=>{r.material.opacity=.07+.04*Math.abs(Math.sin(t*40+ix))});
  const on=(after?Math.max(0,1-(t-T_END)/.4):1)*dp.on,h=dp.half;
  fanPos.set([dxx,dyy-.2,drone.position.z, dxx,.1,dp.z-h, dxx,.1,dp.z+h]);
  const c1=FAN.map(v=>v*.9*on);fanCol.set([0,0,0,...c1,...c1]);fanG.attributes.position.needsUpdate=true;fanG.attributes.color.needsUpdate=true;
  lineM.position.set(dxx,.12,dp.z);lineM.scale.set(1,1,h);glowLine.position.set(dxx,.1,dp.z);glowLine.scale.set(1,1,h);
  lineM.visible=glowLine.visible=fan.visible=on>.01;
  // camera: one wide, calm shot over both blocks
  const u=ease(clamp(t/DUR));
  const yaw=THREE.MathUtils.degToRad(THREE.MathUtils.lerp(13,8,u)),el=THREE.MathUtils.degToRad(THREE.MathUtils.lerp(36,32,u)),D=THREE.MathUtils.lerp(Number(Q.get('d0')||72),Number(Q.get('d1')||67),u);
  const LA=new THREE.Vector3(THREE.MathUtils.lerp(1,0,u),THREE.MathUtils.lerp(2.4,3.2,u),-1.4);
  cam.position.set(LA.x-D*Math.sin(yaw)*Math.cos(el),LA.y+D*Math.sin(el),LA.z+D*Math.cos(yaw)*Math.cos(el));cam.lookAt(LA);
  composer.render();
  o2.imageSmoothingEnabled=true;o2.imageSmoothingQuality='high';o2.drawImage(renderer.domElement,0,0,OW,OH);
  return out.toDataURL('image/png')};

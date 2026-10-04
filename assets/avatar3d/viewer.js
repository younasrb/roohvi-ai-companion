/*
 * 3D avatar stage.
 *
 * Loads a rigged GLB/VRM avatar and drives it from the pose the Python lip-sync
 * engine sends (mouth open / lip spread / eyelid closure / brow / gaze / head
 * motion). It understands the common facial rigs without configuration:
 *
 *   ARKit blendshapes     jawOpen, mouthFunnel, eyeBlinkLeft / eyeBlink_L ...
 *   Oculus visemes        viseme_aa, viseme_PP, ... (+ eyeBlink*)
 *   VRoid / VRM 0.x       Fcl_MTH_A/I/U/E/O, Fcl_EYE_Close
 *   VRM 1.0 expressions   aa / ih / ou / ee / oh / blink
 *   anything else         one "mouth open" morph, or a jaw bone
 *
 * Full body: a humanoid skeleton (Mixamo / Ready Player Me / VRM / Unreal / Blender /
 * Character Creator / Daz naming, see rig_names.js) gets its T-pose arms lowered, and
 * -- unless the file ships its own idle animation -- a procedural idle: breathing,
 * weight shift, arm sway and small speech gestures driven by the voice level.
 *
 * Messages to the host are console lines starting with "@@tag {json}".
 */
import * as THREE from 'three';
import { GLTFLoader } from './vendor/jsm/loaders/GLTFLoader.js';
import { DRACOLoader } from './vendor/jsm/loaders/DRACOLoader.js';
import { KTX2Loader } from './vendor/jsm/loaders/KTX2Loader.js';
import { MeshoptDecoder } from './vendor/jsm/libs/meshopt_decoder.module.js';
import { RoomEnvironment } from './vendor/jsm/environments/RoomEnvironment.js';
import { classify } from './rig_names.js';
import { buildCharacter } from './characters.js';

const params = new URLSearchParams(location.search);
const LOW = params.get('quality') === 'low';
const NOCLIPS = params.get('noclips') === '1';     // ignore the file's own animation clips (tests)
const send = (tag, obj) => console.log('@@' + tag + ' ' + JSON.stringify(obj ?? {}));
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const norm = (n) => String(n).toLowerCase().replace(/[^a-z0-9]/g, '').replace(/left$/, 'l').replace(/right$/, 'r');

/* ── renderer / scene ──────────────────────────────────────────────────── */
const canvas = document.getElementById('c');
let renderer;
try {
  renderer = new THREE.WebGLRenderer({ canvas, antialias: !LOW, alpha: true, powerPreference: 'high-performance' });
} catch (e) {
  send('fatal', { msg: 'WebGL is not available: ' + (e && e.message) });
  throw e;
}
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, LOW ? 1 : 1.75));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.setClearColor(0x000000, 0);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(24, 1, 0.01, 200);
scene.add(camera);
const target = new THREE.Object3D();
scene.add(target);

const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = 0.55;

const key = new THREE.DirectionalLight(0xfff1e2, 2.1);
key.position.set(-1.4, 1.5, 2.2);
const fill = new THREE.DirectionalLight(0xdfe8ff, 0.55);
fill.position.set(2.0, 0.3, 1.6);
const rim = new THREE.DirectionalLight(0x4f8cff, 1.6);
rim.position.set(1.6, 1.3, -2.4);
for (const l of [key, fill, rim]) { l.target = target; camera.add(l); }

/* ── loaders ───────────────────────────────────────────────────────────── */
const gltfLoader = new GLTFLoader();
gltfLoader.setDRACOLoader(new DRACOLoader().setDecoderPath('./vendor/jsm/libs/draco-gltf/'));
gltfLoader.setKTX2Loader(new KTX2Loader().setTranscoderPath('./vendor/jsm/libs/basis/').detectSupport(renderer));
gltfLoader.setMeshoptDecoder(MeshoptDecoder);

/* ── pose (targets come from the host, P is the smoothed value) ─────────── */
const KEYS = ['o', 'w', 'c', 'br', 'gx', 'gy', 'yaw', 'pitch', 'roll', 'lv'];
const RATE = { o: 40, w: 22, c: 50, br: 9, gx: 16, gy: 16, yaw: 6, pitch: 6, roll: 6, lv: 14 };
const P = Object.fromEntries(KEYS.map((k) => [k, 0]));
const T = Object.fromEntries(KEYS.map((k) => [k, 0]));
let demoOn = false;
let elapsed = 0;

/* ── framing (user adjustable: wheel = zoom, drag = move up/down) ────────── */
const view = { zoom: 1, offsetY: 0, mode: 'auto' };     // mode: auto | full | bust | head
let frames = null;
let frameInfo = null;

/* ── rig ───────────────────────────────────────────────────────────────── */
let holder = null;      // group we rotate when the model has no usable head bone
let model = null;
let rig = null;
let mixer = null;
let floorMesh = null;
let procChar = null;          // built-in character (no model file)
let accentNow = '#2f7bff';
let charName = '';
const drive = {};
let prevKeys = new Set();

const MOUTH_GENERIC = ['mouthopen', 'openmouth', 'open', 'mouthaa', 'mthopen'];
const VISEMES = ['visemepp', 'visemeff', 'visemeth', 'visemedd', 'visemekk', 'visemech',
                 'visemess', 'visemenn', 'visemerr', 'visemeaa', 'visemee', 'visemei', 'visemeo', 'visemeu'];

function findObj(root, test) {
  let hit = null;
  root.traverse((o) => { if (!hit && test(o)) hit = o; });
  return hit;
}

/* ── skeleton helpers ──────────────────────────────────────────────────── */
const _q1 = new THREE.Quaternion(), _q2 = new THREE.Quaternion(), _q3 = new THREE.Quaternion();
const _v1 = new THREE.Vector3(), _v2 = new THREE.Vector3(), _v3 = new THREE.Vector3();
const _eu = new THREE.Euler(0, 0, 0, 'YXZ');
const depthOf = (o) => { let d = 0; for (let p = o.parent; p; p = p.parent) d++; return d; };

function findBones(root) {
  const B = { hips: null, spines: [], chest: null, neck: null, head: null,
              L: { clavicle: null, upper: null, fore: null, hand: null },
              R: { clavicle: null, upper: null, fore: null, hand: null } };
  const slot = { clavicle: 'clavicle', upperarm: 'upper', forearm: 'fore', hand: 'hand' };
  root.traverse((o) => {
    if (!o.isBone) return;
    const { part, side } = classify((o.userData && o.userData.name) || o.name);
    if (!part) return;
    if (part === 'hips') { if (!B.hips) B.hips = o; }
    else if (part === 'spine') B.spines.push(o);
    else if (part === 'neck') { if (!B.neck) B.neck = o; }
    else if (part === 'head') { if (!B.head) B.head = o; }
    else if (side && !B[side][slot[part]]) B[side][slot[part]] = o;
  });
  if (B.spines.length) B.chest = B.spines.reduce((a, b) => (depthOf(b) > depthOf(a) ? b : a));
  return B;
}

/* Rotate `bone` (relative to its stored rest pose) by a rotation D given in WORLD axes.
 * new_local = P^-1 * D * P * rest  -- works whatever the bone's own local axes are. */
function applyWorldDelta(bone, D) {
  const rest = rig.restQ.get(bone) || bone.quaternion;
  bone.parent.updateWorldMatrix(true, false);
  bone.parent.getWorldQuaternion(_q1);
  _q2.copy(_q1).invert();
  bone.quaternion.copy(_q2).multiply(D).multiply(_q1).multiply(rest);
  bone.updateMatrixWorld(true);
}
const eulerQ = (x, y, z) => _q3.setFromEuler(_eu.set(x, y, z, 'YXZ'));

/* Turn `bone` so that the direction bone -> child moves to (current + offset). */
function aimBone(bone, child, offset) {
  bone.updateWorldMatrix(true, false);
  child.updateWorldMatrix(true, false);
  bone.getWorldPosition(_v1);
  child.getWorldPosition(_v2);
  _v2.sub(_v1).normalize();
  _v3.copy(_v2).add(offset).normalize();
  applyWorldDelta(bone, _q3.setFromUnitVectors(_v2, _v3));
}

/* Rotate a bone so bone -> child points along `dir` (used once, to relax T-pose arms). */
function aimBoneTo(bone, child, dir) {
  bone.updateWorldMatrix(true, false);
  child.updateWorldMatrix(true, false);
  bone.getWorldPosition(_v1);
  child.getWorldPosition(_v2);
  _v2.sub(_v1).normalize();
  rig.restQ.set(bone, bone.quaternion.clone());
  applyWorldDelta(bone, _q3.setFromUnitVectors(_v2, dir.clone().normalize()));
  rig.restQ.set(bone, bone.quaternion.clone());          // the relaxed pose is the new rest pose
}

const childBone = (b, pred) => { for (const c of b.children) if (c.isBone && (!pred || pred(c))) return c; return null; };

function relaxArms(B) {
  let lowered = 0;
  root_update();
  const hipsX = B.hips ? B.hips.getWorldPosition(_v3).x : 0;
  for (const side of ['L', 'R']) {
    const a = B[side];
    if (!a.upper) continue;
    const fore = a.fore || childBone(a.upper);
    if (!fore) continue;
    a.upper.updateWorldMatrix(true, false); fore.updateWorldMatrix(true, false);
    a.upper.getWorldPosition(_v1); fore.getWorldPosition(_v2);
    const d = _v2.clone().sub(_v1).normalize();
    const out = Math.sign(_v1.x - hipsX) || (side === 'L' ? 1 : -1);
    rig.out[side] = out;
    if (Math.acos(THREE.MathUtils.clamp(-d.y, -1, 1)) < 0.55) continue;       // already hanging (< ~31 deg)
    aimBoneTo(a.upper, fore, new THREE.Vector3(out * 0.16, -1, 0.02));
    const hand = a.hand || childBone(fore);
    if (hand) aimBoneTo(fore, hand, new THREE.Vector3(out * 0.05, -1, 0.42));   // relaxed elbow, forearm a little forward
    lowered++;
  }
  return lowered;
}
function root_update() { if (holder) holder.updateMatrixWorld(true); }

async function buildRig(gltf) {
  const root = gltf.scene;
  const morphs = new Map();
  root.traverse((o) => {
    if (o.isMesh) {
      o.frustumCulled = false;
      if (o.morphTargetDictionary && o.morphTargetInfluences) {
        for (const [name, idx] of Object.entries(o.morphTargetDictionary)) {
          const k = norm(name);
          if (!morphs.has(k)) morphs.set(k, []);
          morphs.get(k).push({ mesh: o, idx, w: 1 });
        }
      }
    }
  });

  // VRM 1.0 expression presets (name-based lookup above already covers VRoid)
  let vrm1 = false;
  const ext = gltf.userData && gltf.userData.gltfExtensions && gltf.userData.gltfExtensions.VRMC_vrm;
  if (ext && ext.expressions && ext.expressions.preset) {
    for (const [pname, def] of Object.entries(ext.expressions.preset)) {
      const binds = def && def.morphTargetBinds;
      if (!binds || !binds.length) continue;
      const list = [];
      for (const b of binds) {
        try {
          const node = await gltf.parser.getDependency('node', b.node);
          node.traverse((m) => {
            if (m.isMesh && m.morphTargetInfluences) list.push({ mesh: m, idx: b.index, w: b.weight ?? 1 });
          });
        } catch (_) { /* skip bad bind */ }
      }
      if (list.length) { morphs.set('vrm1:' + pname, list); vrm1 = true; }
    }
  }

  const has = (k) => morphs.has(k);
  const bones = findBones(root);
  const headBone = bones.head;
  const neckBone = bones.neck;
  const jawBone  = findObj(root, (o) => o.isBone === true && /jaw$/i.test(o.name || ''));

  const visemeCount = VISEMES.filter(has).length;
  let mode = 'none';
  if (visemeCount >= 8) mode = 'viseme';
  else if (has('jawopen')) mode = 'arkit';
  else if (has('fclmtha') || has('fclmthe')) mode = 'vrm0';
  else if (vrm1 && has('vrm1:aa')) mode = 'vrm1';
  else if (MOUTH_GENERIC.some(has)) mode = 'generic';
  else if (jawBone) mode = 'bone';

  const eyeMorphs = has('eyeblinkl') || has('eyeblink') || has('fcleyeclose') || has('vrm1:blink');
  return {
    morphs, mode, vrm1, visemeCount, eyeMorphs,
    generic: MOUTH_GENERIC.find(has) || null,
    bones, head: headBone, neck: neckBone, jaw: jawBone,
    jawRest: jawBone ? jawBone.rotation.clone() : null,
    restQ: new Map(), ctrl: [], animated: new Set(), out: { L: 1, R: -1 },
    bodyMode: 'none', fullBody: false, size: 1, baseY: 0,
  };
}

/* ── mapping: pose -> morph weights ────────────────────────────────────── */
function put(k, v) { if (v > (drive[k] || 0)) drive[k] = clamp(v, 0, 1); }

function computeDrive() {
  for (const k of Object.keys(drive)) delete drive[k];
  const o = clamp(P.o, 0, 1), w = clamp(P.w, -1, 1), c = clamp(P.c, 0, 1);
  const sm = Math.max(0, w), rd = Math.max(0, -w);
  const narrow = 1 - Math.abs(w) * 0.75;

  switch (rig.mode) {
    case 'arkit':
      put('jawopen', o * 0.85);
      put('mouthfunnel', rd * o * 0.75);
      put('mouthpucker', rd * o * 0.45);
      put('mouthsmilel', sm * (0.22 + 0.4 * o)); put('mouthsmiler', sm * (0.22 + 0.4 * o));
      put('mouthstretchl', sm * o * 0.32);       put('mouthstretchr', sm * o * 0.32);
      put('mouthlowerdownl', o * 0.24);          put('mouthlowerdownr', o * 0.24);
      put('mouthupperupl', o * 0.12);            put('mouthupperupr', o * 0.12);
      break;
    case 'viseme':
      put('visemeaa', o * narrow * 0.9);
      put('visemee', o * sm * 0.8);
      put('visemei', o * sm * 0.5);
      put('visemeo', o * rd * 0.9);
      put('visemeu', o * rd * 0.6);
      if (o < 0.05) put('visemepp', (1 - o / 0.05) * 0.55);
      put('jawopen', o * 0.2);
      put('mouthopen', o * 0.15);
      break;
    case 'vrm0':
      put('fclmtha', o * narrow * 0.9);
      put('fclmthe', o * sm * 0.7);
      put('fclmthi', o * sm * 0.4);
      put('fclmtho', o * rd * 0.9);
      put('fclmthu', o * rd * 0.6);
      break;
    case 'vrm1':
      put('vrm1:aa', o * narrow * 0.9);
      put('vrm1:ee', o * sm * 0.7);
      put('vrm1:ih', o * sm * 0.4);
      put('vrm1:oh', o * rd * 0.9);
      put('vrm1:ou', o * rd * 0.6);
      break;
    case 'generic':
      put(rig.generic, o * 0.9);
      break;
    default:
      break;
  }

  // eyes: blink / lids
  put('eyeblinkl', c); put('eyeblinkr', c); put('eyeblink', c);
  put('eyesquintl', c * 0.18); put('eyesquintr', c * 0.18);
  put('fcleyeclose', c);
  put('vrm1:blink', c);

  // brows
  if (P.br > 0) {
    put('browinnerup', P.br * 0.6);
    put('browouterupl', P.br * 0.4); put('browouterupr', P.br * 0.4);
  } else if (P.br < 0) {
    put('browdownl', -P.br * 0.6); put('browdownr', -P.br * 0.6);
  }

  // gaze (x > 0 = towards the viewer's right)
  const gx = clamp(P.gx, -1, 1), gy = clamp(P.gy, -1, 1);
  if (gx > 0) { put('eyelookoutl', gx * 0.6); put('eyelookinr', gx * 0.6); }
  else        { put('eyelookinl', -gx * 0.6); put('eyelookoutr', -gx * 0.6); }
  if (gy > 0) { put('eyelookupl', gy * 0.5);   put('eyelookupr', gy * 0.5); }
  else        { put('eyelookdownl', -gy * 0.5); put('eyelookdownr', -gy * 0.5); }
}

function setMorph(k, v) {
  const list = rig.morphs.get(k);
  if (!list) return;
  for (const t of list) t.mesh.morphTargetInfluences[t.idx] = v * t.w;
}

function applyMorphs() {
  for (const k of prevKeys) if (!(k in drive)) setMorph(k, 0);
  for (const k of Object.keys(drive)) setMorph(k, drive[k]);
  prevKeys = new Set(Object.keys(drive));
  if (rig.mode === 'bone' && rig.jaw) {
    rig.jaw.rotation.x = rig.jawRest.x + clamp(P.o, 0, 1) * 0.28;
  }
}

function applyHead() {
  const yaw = clamp(P.yaw, -0.6, 0.6), pitch = clamp(P.pitch, -0.5, 0.5), roll = clamp(P.roll, -0.3, 0.3);
  const B = rig.bones;
  if (rig.head && rig.head.isBone) {
    // where a clip animates the bone, ride on top of the clip; otherwise start from the stored rest pose
    for (const b of [B.neck, rig.head]) {
      if (b && rig.animated.has(b.name)) rig.restQ.set(b, b.quaternion.clone());
    }
    if (B.neck) applyWorldDelta(B.neck, eulerQ(pitch * 0.25, yaw * 0.25, roll * 0.15).clone());
    applyWorldDelta(rig.head, eulerQ(pitch * 0.7, yaw * 0.7, roll * 0.5).clone());
  } else if (holder) {
    holder.rotation.set(pitch * 0.55, yaw * 0.7, roll * 0.45);
  }
  if (model && rig.bodyMode !== 'procedural') model.position.y = rig.baseY + Math.sin(elapsed * 1.55) * 0.0022 * rig.size;
}

/* Procedural body: breathing, weight shift, arm sway and speech gestures. */
let gestureE = 0;
const _off = new THREE.Vector3();
function animateBody(dt) {
  const B = rig.bones, t = elapsed;
  for (const b of rig.ctrl) b.quaternion.copy(rig.restQ.get(b));            // back to the relaxed rest pose
  if (B.hips)  applyWorldDelta(B.hips, eulerQ(0, Math.sin(t * 0.31) * 0.02, Math.sin(t * 0.47) * 0.015).clone());
  if (B.chest) applyWorldDelta(B.chest, eulerQ(Math.sin(t * 1.6) * 0.010 + gestureE * 0.02, 0, 0).clone());
  for (const side of ['L', 'R']) {
    const a = B[side];
    if (!a.upper) continue;
    const out = rig.out[side], ph = side === 'L' ? 0 : 1.9;
    const g = gestureE * (0.5 + 0.5 * Math.sin(t * 2.1 + ph));
    const fore = a.fore || childBone(a.upper);
    if (a.clavicle) applyWorldDelta(a.clavicle, eulerQ(0, 0, out * Math.sin(t * 1.6) * 0.01).clone());
    aimBone(a.upper, fore || a.upper.children[0],
            _off.set(out * (0.02 * Math.sin(t * 0.9 + ph)), 0.05 * Math.sin(t * 1.3 + ph) + 0.16 * g, 0.10 * g));
    if (fore && (a.hand || childBone(fore))) {
      const g2 = gestureE * (0.5 + 0.5 * Math.sin(t * 2.6 + ph * 1.7));
      aimBone(fore, a.hand || childBone(fore),
              _off.set(-out * 0.06 * gestureE, 0.34 * g2, 0.5 * g2 * (0.7 + 0.3 * Math.sin(t * 1.9 + ph))));
    }
  }
}

/* ── framing ───────────────────────────────────────────────────────────── */
const insets = { top: 0, bottom: 0, left: 0, right: 0 };   // px covered by floating UI (set by the host)

function pickFrame() {
  if (!frames) return null;
  const m = view.mode === 'auto' ? 'full' : view.mode;
  return frames[m] || frames.full;
}

function frame() {
  if (!model || !frames) return;
  const f = (frameInfo = pickFrame());
  const W = Math.max(200, window.innerWidth);
  const H = Math.max(200, window.innerHeight);
  const freeH = Math.max(160, H - insets.top - insets.bottom);   // vertical band the character may use
  const freeW = Math.max(160, W - insets.left - insets.right);   // horizontal band
  const base = f.visH / view.zoom;
  // fit the character's actual height AND its actual width into the free band -- whichever
  // needs more zoom-out wins (using the model's own world width, not the canvas' full FOV width)
  const byHeight = base * (H / freeH);
  const charWidth = f.width || base * camera.aspect * 0.55;
  const byWidth = charWidth * (H / freeW);
  const visH = Math.max(byHeight, byWidth);
  const cy = f.cy + view.offsetY * base;
  const dist = (visH / 2) / Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
  camera.position.set(f.cx, cy, f.cz + dist);
  camera.lookAt(f.cx, cy, f.cz);
  target.position.set(f.cx, cy, f.cz);
  camera.updateMatrixWorld();
  // Centre the model within the free band (not the whole canvas), without distorting
  // perspective: render as an off-centre crop of a same-size virtual frame.
  const dx = (insets.right - insets.left) / 2;
  const dy = (insets.bottom - insets.top) / 2;
  if (dx || dy) camera.setViewOffset(W, H, dx, dy, W, H);
  else camera.clearViewOffset();
}

function computeFrame(forceFull = false) {
  holder.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(holder);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const H = Math.max(size.y, 1e-3);
  let headY = null;
  if (rig.head && rig.head.isBone) headY = rig.head.getWorldPosition(new THREE.Vector3()).y;
  const ratio = headY === null ? 0 : (headY - box.min.y) / H;
  rig.fullBody = forceFull || ratio > 0.8;                           // head near the top of a tall model = whole body
  rig.size = H;
  const at = (visH, cy, width) => ({ visH, cy, cx: center.x, cz: center.z, width });
  if (rig.fullBody) {
    frames = {
      full: at(H * 1.06, box.min.y + 0.5 * H, size.x * 1.05),         // head to toe
      bust: at(0.30 * H, box.min.y + 0.875 * H, size.x * 0.95),       // head, shoulders, chest
      head: at(0.19 * H, box.min.y + 0.925 * H, size.x * 0.42),       // face close-up
    };
  } else {                                              // head / bust model: show all of it
    const whole = at(H * 1.04, center.y + 0.01 * H, size.x * 1.1);
    frames = { full: whole, bust: whole, head: whole };
  }
  return { size: [size.x, size.y, size.z], ratio, box };
}

function makeFloor(box, size) {
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const g = c.getContext('2d');
  const grad = g.createRadialGradient(64, 64, 4, 64, 64, 62);
  grad.addColorStop(0, 'rgba(255,255,255,0.85)');
  grad.addColorStop(0.55, 'rgba(255,255,255,0.22)');
  grad.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = grad; g.fillRect(0, 0, 128, 128);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  const mat = new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false, opacity: 0.5,
                                            color: new THREE.Color(getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#4f8cff') });
  const r = Math.max(size.x, size.z, size.y * 0.30) * 0.9;
  const m = new THREE.Mesh(new THREE.PlaneGeometry(r * 2, r * 2), mat);
  m.rotation.x = -Math.PI / 2;
  m.position.set((box.min.x + box.max.x) / 2, box.min.y + 0.0015 * size.y, (box.min.z + box.max.z) / 2);
  return m;
}

/* ── avatar loading ────────────────────────────────────────────────────── */
function clearCurrent() {
  if (holder) { scene.remove(holder); holder = null; }
  if (floorMesh) { scene.remove(floorMesh); floorMesh = null; }
  mixer = null; rig = null; prevKeys = new Set(); frames = null; procChar = null; model = null;
}

/* Built-in character: no file needed. gender = 'male' | 'female'. */
async function loadProcedural(gender) {
  try {
    clearCurrent();
    procChar = buildCharacter(gender === 'female' ? 'female' : 'male', accentNow);
    procChar.setName(charName);
    model = procChar.group;
    holder = new THREE.Group();
    holder.add(model);
    scene.add(holder);
    rig = { procedural: true, mode: 'humanoid', morphs: new Map(), bones: { head: null, neck: null, L: {}, R: {} },
            head: null, neck: null, jaw: null, restQ: new Map(), ctrl: [], animated: new Set(), out: { L: 1, R: -1 },
            bodyMode: 'procedural', fullBody: true, size: 1, baseY: 0, visemeCount: 0, eyeMorphs: true, vrm1: false };
    const fr = computeFrame(true);
    floorMesh = makeFloor(fr.box, new THREE.Vector3(...fr.size));
    scene.add(floorMesh);
    frame();
    send('loaded', { mode: 'humanoid', morphs: 0, visemes: 0, blink: true, head: true, jaw: true, vrm1: false,
                     size: fr.size, idle: null, fullBody: true, body: 'procedural', lowered: 0,
                     builtIn: true, gender: gender === 'female' ? 'female' : 'male' });
  } catch (e) {
    send('error', { msg: 'built-in character: ' + String((e && e.message) || e) });
  }
}

async function loadAvatar(url) {
  try {
    const gltf = await new Promise((res, rej) => gltfLoader.load(url, res, undefined, rej));
    clearCurrent();

    model = gltf.scene;
    holder = new THREE.Group();
    holder.add(model);
    scene.add(holder);
    rig = await buildRig(gltf);
    rig.baseY = model.position.y;
    holder.updateMatrixWorld(true);

    // ── body: the file's own idle clip, else a procedural idle for humanoid skeletons ──
    const B = rig.bones;
    const clips = NOCLIPS ? [] : (gltf.animations || []);
    const idle = clips.find((a) => /idle|breath/i.test(a.name));
    let lowered = 0;
    if (idle) {
      rig.bodyMode = 'clip';
      mixer = new THREE.AnimationMixer(model);
      mixer.clipAction(idle).play();
      rig.animated = new Set(idle.tracks.map((t) => t.name.split('.')[0]));
    } else if (B.hips && (B.L.upper || B.R.upper)) {
      rig.bodyMode = 'procedural';
      lowered = relaxArms(B);
    }
    for (const b of [B.neck, B.head]) if (b && !rig.restQ.has(b)) rig.restQ.set(b, b.quaternion.clone());
    if (rig.bodyMode === 'procedural') {
      const list = [B.hips, B.chest, B.L.clavicle, B.R.clavicle, B.L.upper, B.R.upper, B.L.fore, B.R.fore].filter(Boolean);
      for (const b of list) if (!rig.restQ.has(b)) rig.restQ.set(b, b.quaternion.clone());
      rig.ctrl = [...new Set(list)].sort((a, b) => depthOf(a) - depthOf(b));
    }

    if (!rig.head || !rig.head.isBone) {     // bone-less model: rotate it about a neck-height pivot
      const b = new THREE.Box3().setFromObject(model);
      const c = b.getCenter(new THREE.Vector3());
      const pivot = new THREE.Vector3(c.x, b.min.y + 0.2 * (b.max.y - b.min.y), c.z);
      holder.position.copy(pivot);
      model.position.sub(pivot);
      rig.baseY = model.position.y;
    }

    const fr = computeFrame();
    if (rig.fullBody) { floorMesh = makeFloor(fr.box, new THREE.Vector3(...fr.size)); scene.add(floorMesh); }
    frame();
    send('loaded', {
      mode: rig.mode, morphs: rig.morphs.size, visemes: rig.visemeCount,
      blink: rig.eyeMorphs, head: !!rig.head, jaw: !!rig.jaw, vrm1: rig.vrm1,
      size: fr.size, idle: idle ? idle.name : null,
      fullBody: rig.fullBody, body: rig.bodyMode, lowered,
    });
  } catch (e) {
    send('error', { msg: String((e && e.message) || e) });
  }
}

/* ── demo animation (for testing the stage without the host) ────────────── */
function runDemo(t) {
  const syl = Math.max(0, Math.sin(t * 7.3)) ** 0.8;
  const talking = (Math.floor(t / 1.6) % 3) !== 2;
  T.o = talking ? syl * 0.9 : 0;
  T.w = Math.sin(t * 2.4) * 0.8;
  T.c = (t % 3.4) < 0.14 ? 1 : 0;
  T.yaw = Math.sin(t * 0.6) * 0.16;
  T.pitch = Math.sin(t * 0.45) * 0.05;
  T.lv = talking ? syl : 0;
}

/* ── public API ────────────────────────────────────────────────────────── */
window.stage = {
  loadAvatar,
  loadProcedural,
  setName(n) { charName = String(n || ''); if (procChar) procChar.setName(charName); },
  setPose(p) {
    for (const k of KEYS) if (typeof p[k] === 'number') T[k] = p[k];
    if ('mu' in p) document.body.classList.toggle('muted', !!p.mu);
    if (p.ac && p.ac !== window.stage._ac) { window.stage._ac = p.ac; window.stage.setTheme({ accent: p.ac }); }
  },
  setTheme(o) {
    const s = document.documentElement.style;
    if (o.accent) {
      accentNow = o.accent;
      s.setProperty('--accent', o.accent); rim.color.set(o.accent);
      if (floorMesh) floorMesh.material.color.set(o.accent);
      if (procChar) procChar.setAccent(o.accent);
    }
    if (o.bg0) s.setProperty('--bg0', o.bg0);
    if (o.bg1) s.setProperty('--bg1', o.bg1);
  },
  setFrame(o) {
    if (typeof o.zoom === 'number') view.zoom = clamp(o.zoom, 0.4, 3);
    if (typeof o.offsetY === 'number') view.offsetY = clamp(o.offsetY, -1.5, 1.5);
    if (typeof o.mode === 'string' && ['auto', 'full', 'bust', 'head'].includes(o.mode)) view.mode = o.mode;
    frame();
  },
  setInsets(o) {
    insets.top = clamp(+o.top || 0, 0, 4000);
    insets.bottom = clamp(+o.bottom || 0, 0, 4000);
    insets.left = clamp(+o.left || 0, 0, 4000);
    insets.right = clamp(+o.right || 0, 0, 4000);
    frame();
  },
  demo(on) { demoOn = !!on; },
  debug() {                                   // used by the self-tests
    if (!rig) return null;
    const common = { insets: { ...insets }, iw: window.innerWidth, ih: window.innerHeight,
                     aspect: camera.aspect, frameInfo, zoom: view.zoom };
    if (rig.procedural) return { mode: 'humanoid', procedural: true, fullBody: true, view: { ...view }, ...common };
    const inf = {};
    for (const [k, list] of rig.morphs) inf[k] = +(list[0].mesh.morphTargetInfluences[list[0].idx] || 0).toFixed(3);
    const B = rig.bones, arm = {};
    for (const side of ['L', 'R']) {
      const a = B[side];
      if (a.upper) {
        const kid = a.fore || childBone(a.upper);
        if (kid) { a.upper.getWorldPosition(_v1); kid.getWorldPosition(_v2); const d = _v2.clone().sub(_v1).normalize(); arm[side] = +d.y.toFixed(3); }
      }
    }
    return { mode: rig.mode, inf, body: rig.bodyMode, fullBody: rig.fullBody, armDirY: arm,
             ctrl: rig.ctrl.map((b) => b.name), view: { ...view }, frame: frameInfo,
             insets: { ...insets }, iw: window.innerWidth, ih: window.innerHeight, aspect: camera.aspect };
  },
};

/* ── interaction: wheel = zoom, drag = move up/down, double-click = reset ─ */
let dragging = false, lastY = 0, reportTimer = null;
const reportFrame = () => {
  clearTimeout(reportTimer);
  reportTimer = setTimeout(() => send('frame', { zoom: +view.zoom.toFixed(3), offsetY: +view.offsetY.toFixed(3) }), 400);
};
canvas.addEventListener('wheel', (e) => {
  e.preventDefault();
  view.zoom = clamp(view.zoom * (e.deltaY < 0 ? 1.07 : 1 / 1.07), 0.4, 3);
  frame(); reportFrame();
}, { passive: false });
canvas.addEventListener('pointerdown', (e) => { dragging = true; lastY = e.clientY; canvas.setPointerCapture(e.pointerId); });
canvas.addEventListener('pointerup', (e) => { dragging = false; try { canvas.releasePointerCapture(e.pointerId); } catch (_) {} });
canvas.addEventListener('pointermove', (e) => {
  if (!dragging) return;
  view.offsetY = clamp(view.offsetY + (e.clientY - lastY) / Math.max(200, window.innerHeight) * 0.8, -1.5, 1.5);
  lastY = e.clientY; frame(); reportFrame();
});
canvas.addEventListener('dblclick', () => { view.zoom = 1; view.offsetY = 0; frame(); reportFrame(); });

/* ── resize + loop ─────────────────────────────────────────────────────── */
function resize() {
  const w = Math.max(2, window.innerWidth), h = Math.max(2, window.innerHeight);
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  frame();
}
window.addEventListener('resize', resize);
resize();

let lastT = performance.now();
let skip = false, errored = false;
function tick() {
  requestAnimationFrame(tick);
  if (LOW) { skip = !skip; if (skip) return; }
  const now = performance.now();
  const dt = Math.min((now - lastT) / 1000, 0.1);
  lastT = now;
  elapsed += dt;
  if (demoOn) runDemo(elapsed);
  for (const k of KEYS) P[k] += (T[k] - P[k]) * (1 - Math.exp(-dt * RATE[k]));
  document.documentElement.style.setProperty('--glow', P.lv.toFixed(3));
  if (rig) {
    try {
      gestureE += (clamp(P.lv * 1.25, 0, 1) - gestureE) * (1 - Math.exp(-dt * 3.5));
      if (rig.procedural) {
        procChar.update(dt, elapsed, P, gestureE);
      } else {
        if (mixer) mixer.update(dt);
        if (rig.bodyMode === 'procedural') animateBody(dt);
        computeDrive(); applyMorphs(); applyHead();
      }
    } catch (e) {
      if (!errored) { errored = true; send('error', { msg: 'animate: ' + e.message }); }
    }
  }
  renderer.render(scene, camera);
}
tick();

send('ready', { renderer: renderer.getContext().getParameter(renderer.getContext().RENDERER), low: LOW });
charName = params.get('name') || '';
const auto = params.get('avatar');
if (auto) loadAvatar(auto);
else if (params.get('gender')) loadProcedural(params.get('gender'));
if (params.get('demo') === '1') demoOn = true;

/*
 * Built-in characters -- a stylised full-body male and female figure in a white coat
 * (approachable styling only: the badge on the coat always says AI companion, not a doctor), assembled from primitives so the app has a working 3D character
 * with no model file and no licensing question. Load your own GLB/VRM for a
 * different look (see README); these are the defaults.
 *
 *   buildCharacter('male' | 'female', accentHex) -> {
 *       group,                    // add to the scene; feet at y = 0, facing +Z
 *       update(dt, t, P, energy), // P = pose from the host (same fields as the GLB path)
 *       setAccent(hex), setName(text)
 *   }
 */
import * as THREE from 'three';
import { RoundedBoxGeometry } from './vendor/jsm/geometries/RoundedBoxGeometry.js';

const clamp = (v, a, b) => Math.min(b, Math.max(a, v));

export function buildCharacter(gender = 'male', accentHex = '#2f7bff') {
  const F = gender === 'female';
  const D = F
    ? { shoulder: 0.190, chestW: 0.335, chestD: 0.205, waistW: 0.245, hipW: 0.335, leg: 0.068, thigh: 0.415, shin: 0.415, arm: 0.046, headS: 1.10 }
    : { shoulder: 0.228, chestW: 0.405, chestD: 0.238, waistW: 0.325, hipW: 0.320, leg: 0.077, thigh: 0.450, shin: 0.450, arm: 0.052, headS: 1.14 };

  const mat = {
    white: new THREE.MeshPhysicalMaterial({ color: '#f4f7fc', roughness: 0.27, metalness: 0.06, clearcoat: 0.75, clearcoatRoughness: 0.22 }),
    dark:  new THREE.MeshPhysicalMaterial({ color: '#0d1526', roughness: 0.62, metalness: 0.05 }),
    glow:  new THREE.MeshBasicMaterial({ color: accentHex, toneMapped: false }),
    coat:  new THREE.MeshPhysicalMaterial({ color: '#fcfcfe', roughness: 0.74, metalness: 0.0, sheen: 0.7, sheenColor: '#e6edfb', sheenRoughness: 0.55 }),
    shirt: new THREE.MeshPhysicalMaterial({ color: '#cfdcf0', roughness: 0.6, metalness: 0.0 }),
    badgeFrame: new THREE.MeshPhysicalMaterial({ color: '#ffffff', roughness: 0.35, clearcoat: 0.6 }),
    skin:  new THREE.MeshPhysicalMaterial({ color: F ? '#ebb996' : '#e0aa80', roughness: 0.55, sheen: 0.4, sheenColor: '#ffd9c2' }),
    hair:  new THREE.MeshPhysicalMaterial({ color: '#17110e', roughness: 0.42, sheen: 1.0, sheenColor: '#7a655a', clearcoat: 0.2 }),
    lip:   new THREE.MeshStandardMaterial({ color: F ? '#b8515e' : '#ad6a5c', roughness: 0.45 }),
    mouth: new THREE.MeshBasicMaterial({ color: '#2a0c11' }),
    teeth: new THREE.MeshBasicMaterial({ color: '#f2eee8' }),
    eye:   new THREE.MeshStandardMaterial({ color: '#f6f7f9', roughness: 0.2 }),
    iris:  new THREE.MeshStandardMaterial({ color: F ? '#3d2717' : '#2d1c12', roughness: 0.3 }),
    brow:  new THREE.MeshStandardMaterial({ color: '#17110e', roughness: 0.6 }),
  };

  const grp = (name) => { const g = new THREE.Group(); g.name = name; return g; };
  const mesh = (geo, m, name) => { const o = new THREE.Mesh(geo, m); if (name) o.name = name; return o; };
  const sphere = (r, m, sx = 1, sy = 1, sz = 1) => { const o = mesh(new THREE.SphereGeometry(r, 28, 20), m); o.scale.set(sx, sy, sz); return o; };
  const rbox = (w, h, d, r, m) => mesh(new RoundedBoxGeometry(w, h, d, 4, r), m);
  // a limb segment hanging from a joint at y = 0
  const limb = (r, len, m) => { const o = mesh(new THREE.CapsuleGeometry(r, len, 8, 20), m); o.position.y = -(len / 2 + r); return o; };
  const strip = (w, h, d) => mesh(new THREE.BoxGeometry(w, h, d), mat.glow);

  const root = grp('character');
  const groundY = 0.095;                                  // ankle height above the floor
  const hips = grp('hips');
  hips.position.y = groundY + D.shin + D.thigh;
  root.add(hips);

  // ── pelvis + legs ──────────────────────────────────────────────────────────
  const pelvis = rbox(D.hipW, 0.20, 0.215, 0.05, mat.dark);
  hips.add(pelvis);
  const belt = rbox(D.hipW + 0.012, 0.045, 0.225, 0.02, mat.white); belt.position.y = 0.085; hips.add(belt);
  const legs = {};
  for (const s of [-1, 1]) {
    const hip = grp(s < 0 ? 'legL' : 'legR');
    hip.position.set(s * D.hipW * 0.30, -0.06, 0);
    hips.add(hip);
    const thigh = limb(D.leg, D.thigh - D.leg * 2, mat.white); hip.add(thigh);
    const ts = strip(0.006, D.thigh * 0.55, 0.006); ts.position.set(s * (D.leg + 0.001), -D.thigh * 0.5, 0.012); hip.add(ts);
    const knee = grp('knee'); knee.position.y = -D.thigh + 0.06; hip.add(knee);
    const kneeCap = sphere(D.leg * 0.92, mat.dark); knee.add(kneeCap);
    const shin = limb(D.leg * 0.86, D.shin - D.leg * 1.7, mat.white); shin.position.y = -0.01 + shin.position.y; knee.add(shin);
    const ss = strip(0.006, D.shin * 0.6, 0.006); ss.position.set(s * (D.leg * 0.86 + 0.001), -D.shin * 0.55, 0.012); knee.add(ss);
    const foot = rbox(0.098, 0.07, 0.275, 0.028, mat.white); foot.position.set(0, -D.shin - 0.045 + 0.06, 0.055); knee.add(foot);
    const sole = rbox(0.1, 0.02, 0.28, 0.008, mat.dark); sole.position.set(0, -D.shin - 0.078 + 0.06, 0.055); knee.add(sole);
    legs[s < 0 ? 'L' : 'R'] = { hip, knee };
  }

  // ── spine / chest ─────────────────────────────────────────────────────────
  const spine = grp('spine'); spine.position.y = 0.10; hips.add(spine);
  const abdomen = rbox(D.waistW, 0.17, D.chestD * 0.80, 0.06, mat.dark); abdomen.position.y = 0.085; spine.add(abdomen);
  const chest = grp('chest'); chest.position.y = 0.20; spine.add(chest);
  const torso = rbox(D.chestW, 0.315, D.chestD, 0.07, mat.white); torso.position.y = 0.115; chest.add(torso);
  const collar = rbox(D.chestW * 0.5, 0.06, D.chestD * 0.9, 0.03, mat.dark); collar.position.y = 0.285; chest.add(collar);
  for (const s of [-1, 1]) {                              // glowing seams down the front
    const st = strip(0.007, 0.20, 0.006); st.position.set(s * D.chestW * 0.26, 0.11, D.chestD / 2 + 0.002); st.rotation.z = s * -0.18; chest.add(st);
  }
  // Name badge on the coat. The disclosure is part of the picture and cannot be turned off.
  const logoCanvas = document.createElement('canvas'); logoCanvas.width = 512; logoCanvas.height = 300;
  const logoTex = new THREE.CanvasTexture(logoCanvas); logoTex.colorSpace = THREE.SRGBColorSpace; logoTex.anisotropy = 4;
  const logo = mesh(new THREE.PlaneGeometry(0.17, 0.0996), new THREE.MeshBasicMaterial({ map: logoTex, transparent: true, toneMapped: false }));
  logo.name = 'badge';
  function rr(g, x, y, w, h, r) { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }
  function drawLogo(name, accent) {
    const g = logoCanvas.getContext('2d');
    g.clearRect(0, 0, 512, 300);
    g.fillStyle = '#ffffff'; rr(g, 6, 6, 500, 288, 34); g.fill();
    g.lineWidth = 10; g.strokeStyle = accent; rr(g, 6, 6, 500, 288, 34); g.stroke();
    g.fillStyle = accent; g.fillRect(40, 22, 432, 14);
    g.textAlign = 'center'; g.textBaseline = 'alphabetic';
    g.font = '800 82px "Segoe UI", Arial, sans-serif'; g.fillStyle = '#16233d';
    g.fillText(String(name || 'ROOHVI').toUpperCase().slice(0, 12), 256, 118);
    g.font = '700 52px "Segoe UI", Arial, sans-serif'; g.fillStyle = '#3a4a68';
    g.fillText('AI COMPANION', 256, 184);
    g.fillStyle = '#b3402f'; rr(g, 40, 208, 432, 66, 33); g.fill();
    g.font = '800 50px "Segoe UI", Arial, sans-serif'; g.fillStyle = '#ffffff';
    g.fillText('NOT A DOCTOR', 256, 259);
    logoTex.needsUpdate = true;
  }
  drawLogo('', accentHex);

  // ---- white coat (styling only; see the badge) -----------------------------
  const coatTorso = rbox(D.chestW + 0.022, 0.58, D.chestD + 0.016, 0.075, mat.coat); coatTorso.position.set(0, 0.02, 0); chest.add(coatTorso);
  const coatCollar = rbox(D.chestW * 0.66, 0.055, D.chestD * 0.94, 0.03, mat.coat); coatCollar.position.set(0, 0.30, -0.012); chest.add(coatCollar);
  const shirt = rbox(0.105, 0.21, 0.004, 0.002, mat.shirt); shirt.position.set(0, 0.185, D.chestD / 2 + 0.0095); chest.add(shirt);
  for (const s of [-1, 1]) {                                          // lapels, V-shaped
    const lap = rbox(0.072, 0.215, 0.012, 0.005, mat.coat);
    lap.position.set(s * 0.066, 0.185, D.chestD / 2 + 0.0135); lap.rotation.z = -s * 0.30; chest.add(lap);
  }
  const seamLine = rbox(0.004, 0.36, 0.004, 0.001, mat.shirt); seamLine.position.set(0, -0.06, D.chestD / 2 + 0.0095); chest.add(seamLine);
  logo.position.set(-0.095, 0.035, D.chestD / 2 + 0.0125); chest.add(logo);       // badge on the wearer's right chest

  const coatSkirt = grp('coatSkirt'); hips.add(coatSkirt);               // moves with the hips
  const skH = 0.60, skY = -0.21, skT = 0.026, skZ = 0.108;
  const pw = (D.hipW + 0.07) / 2 - 0.008;
  for (const s of [-1, 1]) {
    const front = rbox(pw, skH, skT, 0.012, mat.coat); front.position.set(s * (pw / 2 + 0.006), skY, skZ); coatSkirt.add(front);
    const side = rbox(0.02, skH, skZ * 2, 0.008, mat.coat); side.position.set(s * (D.hipW / 2 + 0.036), skY, 0); coatSkirt.add(side);
  }
  const backP = rbox(D.hipW + 0.09, skH, skT, 0.012, mat.coat); backP.position.set(0, skY, -skZ); coatSkirt.add(backP);
  const hem = rbox(D.hipW + 0.095, 0.012, skZ * 2 + 0.03, 0.005, mat.shirt); hem.position.set(0, skY - skH / 2, 0); hem.visible = false; coatSkirt.add(hem);
  logo.visible = true;

  // ── neck + head ────────────────────────────────────────────────────────────
  const neck = grp('neck'); neck.position.y = 0.31; chest.add(neck);
  const neckMesh = mesh(new THREE.CylinderGeometry(0.040, 0.046, 0.10, 20), mat.skin); neckMesh.position.y = 0.02; neck.add(neckMesh);
  const head = grp('head'); head.position.y = 0.155; neck.add(head);
  const hs = D.headS;
  const cranium = sphere(1, mat.skin, 0.086 * hs, 0.100 * hs, 0.096 * hs); head.add(cranium);
  const chin = sphere(1, mat.skin, F ? 0.056 * hs : 0.063 * hs, 0.052 * hs, 0.070 * hs); chin.position.set(0, -0.056 * hs, 0.030 * hs); head.add(chin);
  for (const s of [-1, 1]) { const ear = sphere(0.02, mat.skin, 0.55, 1, 0.85); ear.position.set(s * 0.086 * hs, -0.004, -0.004); head.add(ear); }
  const nose = sphere(0.012 * hs, mat.skin, 0.9, 1.25, 1.2); nose.position.set(0, -0.012 * hs, 0.097 * hs); head.add(nose);

  const eyes = {};
  for (const s of [-1, 1]) {
    const eg = grp('eye'); eg.position.set(s * 0.034 * hs, 0.016 * hs, 0.083 * hs); head.add(eg);
    const ball = sphere(0.0108 * hs, mat.eye, 1.18, 1, 0.9); eg.add(ball);
    const gaze = grp('gaze'); eg.add(gaze);
    const iris = sphere(0.0060 * hs, mat.iris, 1, 1, 0.5); iris.position.z = 0.0080 * hs; gaze.add(iris);
    const lidLine = rbox(0.030 * hs, 0.0035 * hs, 0.004, 0.0015, mat.brow); lidLine.position.z = 0.011 * hs; lidLine.visible = false; eg.add(lidLine);
    const brow = rbox(0.038 * hs, F ? 0.0048 : 0.0068, 0.006, 0.0024, mat.brow);
    brow.position.set(s * 0.034 * hs, 0.046 * hs, 0.089 * hs); brow.rotation.z = s * (F ? -0.10 : -0.05); head.add(brow);
    let lash = null;
    if (F) { lash = rbox(0.034 * hs, 0.0035, 0.006, 0.0015, mat.brow); lash.position.set(s * 0.034 * hs, 0.0295 * hs, 0.089 * hs); head.add(lash); }
    eyes[s < 0 ? 'L' : 'R'] = { eg, gaze, lidLine, brow, lash, baseBrowY: 0.046 * hs };
  }

  const mouth = grp('mouth'); mouth.position.set(0, -0.049 * hs, 0.0965 * hs); head.add(mouth);
  const cavity = sphere(0.022 * hs, mat.mouth, 1, 0.02, 0.35); cavity.position.z = -0.002; mouth.add(cavity);
  const teeth = mesh(new THREE.BoxGeometry(0.030 * hs, 0.005, 0.004), mat.teeth); teeth.position.set(0, 0.004, 0.0015); mouth.add(teeth);
  const upperLip = sphere(0.0215 * hs, mat.lip, 1, F ? 0.24 : 0.19, 0.30); upperLip.position.set(0, 0.0035, 0.002); mouth.add(upperLip);
  const lowerLip = sphere(0.0205 * hs, mat.lip, 1, F ? 0.28 : 0.22, 0.30); lowerLip.position.set(0, -0.0035, 0.002); mouth.add(lowerLip);

  // hair: a cap tilted back so the hairline sits on the forehead and the hair falls low at the back
  const hairCap = new THREE.Mesh(new THREE.SphereGeometry(1, 36, 22, 0, Math.PI * 2, 0, 1.28), mat.hair);
  hairCap.scale.set(0.094 * hs, 0.106 * hs, 0.102 * hs); hairCap.position.set(0, 0.004 * hs, -0.006 * hs); hairCap.rotation.x = -0.32; head.add(hairCap);
  const hairBack = sphere(1, mat.hair, 0.090 * hs, 0.084 * hs, 0.078 * hs); hairBack.position.set(0, -0.012 * hs, -0.036 * hs); head.add(hairBack);
  if (F) {
    const back = mesh(new THREE.CylinderGeometry(0.094 * hs, 0.060 * hs, 0.42, 24, 1, true), mat.hair);
    back.position.set(0, -0.17, -0.058 * hs); back.scale.z = 0.70; head.add(back);
    for (const s of [-1, 1]) {
      const lock = mesh(new THREE.CapsuleGeometry(0.013 * hs, 0.17, 6, 12), mat.hair);
      lock.position.set(s * 0.085 * hs, -0.07 * hs, 0.006 * hs); lock.rotation.z = s * 0.05; head.add(lock);
    }
  } else {
    const sweep = sphere(1, mat.hair, 0.052 * hs, 0.016 * hs, 0.040 * hs); sweep.position.set(0.018 * hs, 0.074 * hs, 0.070 * hs); sweep.rotation.set(-0.7, 0, -0.18); head.add(sweep);
  }

  // ── arms ───────────────────────────────────────────────────────────────────
  const arms = {};
  for (const s of [-1, 1]) {
    const sh = grp(s < 0 ? 'shoulderL' : 'shoulderR'); sh.position.set(s * D.shoulder, 0.245, 0); chest.add(sh);
    const pauldron = sphere(D.arm * 1.55, mat.white); sh.add(pauldron);
    sh.add(sphere(D.arm * 1.86, mat.coat));                            // coat shoulder
    const ring = mesh(new THREE.TorusGeometry(D.arm * 1.32, 0.0045, 8, 32), mat.glow); ring.rotation.y = Math.PI / 2; ring.position.y = -0.03; sh.add(ring);
    const upper = grp('upperArm'); sh.add(upper);
    upper.add(limb(D.arm, 0.245 - D.arm * 2, mat.white));
    upper.add(limb(D.arm * 1.34, 0.245 - D.arm * 2 + 0.03, mat.coat));          // sleeve
    const elbow = grp('elbow'); elbow.position.y = -0.285; upper.add(elbow);
    elbow.add(sphere(D.arm * 0.95, mat.dark));
    const fore = grp('foreArm'); elbow.add(fore);
    fore.add(limb(D.arm * 0.84, 0.235 - D.arm * 1.7, mat.white));
    fore.add(limb(D.arm * 0.84 * 1.36, 0.235 - D.arm * 1.7 - 0.035, mat.coat));  // sleeve, hand stays visible
    const fs = strip(0.005, 0.15, 0.005); fs.position.set(0, -0.13, D.arm * 0.84 + 0.001); fore.add(fs);
    const wrist = grp('wrist'); wrist.position.y = -0.265; fore.add(wrist);
    wrist.add(sphere(D.arm * 0.75, mat.dark));
    const hand = sphere(0.043, mat.skin, 0.9, 1.25, 0.6); hand.position.y = -0.055; wrist.add(hand);
    const thumb = sphere(0.014, mat.skin, 1, 1.6, 1); thumb.position.set(-s * 0.03, -0.035, 0.012); wrist.add(thumb);
    arms[s < 0 ? 'L' : 'R'] = { sh, upper, elbow, fore, wrist, out: s };
  }

  // ── animation ──────────────────────────────────────────────────────────────
  let lookX = 0, lookY = 0;
  function update(dt, t, P, energy) {
    const g = clamp(energy, 0, 1);
    // breathing + weight shift
    const br = Math.sin(t * 1.6);
    spine.rotation.x = br * 0.010 + g * 0.02;
    chest.scale.set(1 + br * 0.004, 1 + br * 0.006, 1 + br * 0.004);
    hips.rotation.z = Math.sin(t * 0.47) * 0.014;
    hips.rotation.y = Math.sin(t * 0.31) * 0.02;
    hips.position.x = Math.sin(t * 0.47) * 0.008;
    legs.L.hip.rotation.z = -hips.rotation.z * 0.8; legs.R.hip.rotation.z = -hips.rotation.z * 0.8;

    // head & neck follow the pose from the host
    const yaw = clamp(P.yaw, -0.6, 0.6), pitch = clamp(P.pitch, -0.5, 0.5);
    neck.rotation.set(pitch * 0.25, yaw * 0.25, 0);
    head.rotation.set(pitch * 0.7, yaw * 0.7, clamp(P.roll, -0.3, 0.3) * 0.5);

    // arms: relaxed at the sides, small gestures while speaking
    for (const key of ['L', 'R']) {
      const a = arms[key], ph = key === 'L' ? 0 : 1.9, o = a.out;
      const gA = g * (0.5 + 0.5 * Math.sin(t * 2.1 + ph));
      const gB = g * (0.5 + 0.5 * Math.sin(t * 2.6 + ph * 1.7));
      a.sh.rotation.z = o * (0.05 + Math.sin(t * 1.6) * 0.008);
      a.upper.rotation.z = o * (0.07 + 0.03 * Math.sin(t * 0.9 + ph));
      a.upper.rotation.x = -(0.05 * Math.sin(t * 1.3 + ph) + 0.20 * gA);
      a.elbow.rotation.x = -(0.22 + 0.95 * gB);
      a.wrist.rotation.x = -0.10 * gB;
    }

    // face
    const c = clamp(P.c, 0, 1);
    for (const k of ['L', 'R']) {
      const e = eyes[k];
      e.eg.scale.y = 1 - 0.93 * c;
      e.lidLine.visible = c > 0.55;
      e.gaze.position.set(clamp(P.gx, -1, 1) * 0.0045 * hs, clamp(P.gy, -1, 1) * 0.0035 * hs, 0);
      e.brow.position.y = e.baseBrowY + clamp(P.br, -0.4, 1) * 0.008;
      if (e.lash) e.lash.position.y = 0.0295 * hs - 0.0055 * c;
    }
    const o = clamp(P.o, 0, 1), w = clamp(P.w, -1, 1);
    const sp = Math.max(0, w), rd = Math.max(0, -w);
    mouth.scale.x = 1 + 0.32 * sp - 0.28 * rd;
    const open = o * 0.030 * hs;
    lowerLip.position.y = -0.0035 - open;
    upperLip.position.y = 0.0035 + o * 0.002;
    cavity.scale.y = 0.02 + open / (0.022 * hs) * 0.9;
    cavity.position.y = -open * 0.5;
    teeth.visible = o > 0.14;
    teeth.position.y = 0.0035 + o * 0.002 - 0.0035;
    lowerLip.scale.y = (F ? 0.28 : 0.22) * (1 - 0.25 * o);
    upperLip.scale.x = 1 - 0.18 * rd;
    lowerLip.scale.x = 1 - 0.18 * rd;
  }

  return {
    group: root,
    update,
    setAccent(hex) { mat.glow.color.set(hex); drawLogo(this._name || '', hex); this._accent = hex; },
    setName(txt) { this._name = txt; drawLogo(txt, this._accent || accentHex); },
    _name: '', _accent: accentHex,
  };
}

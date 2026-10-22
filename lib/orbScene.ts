// The ORIGINAL Nemiii orb (from the nemin-s-FRIDAY repo), same look, rebuilt to run light.
//
// What is the same: outer wire shell with the bright "+" bands and equator, grid panels,
// second broken shell, spiral inner core, glowing icosahedron centre, scrolling code text,
// orbiting debris, dust, scanning rings, bloom and the slight colour fringe.
//
// What changed (this is why it no longer lags):
//   * hundreds of separate Line objects  -> a few merged LineSegments
//   * 1,700 text sprites (1,700 textures) -> ONE Points object with one text atlas
//   * 250 debris meshes (250 materials)   -> 6 InstancedMeshes
//   * motion is time-based, so it is smooth at any frame rate
//   * it watches its own frame time and lowers resolution / effects if the PC struggles
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { ShaderPass } from "three/addons/postprocessing/ShaderPass.js";
import type { AvatarState } from "@/lib/types";

export interface OrbSceneApi {
  setState(s: AvatarState): void;
  rotateBy(deltaTheta: number, deltaPhi: number): void;
  zoomBy(factor: number): void;
  zoomIn(): void;
  zoomOut(): void;
  resetView(): void;
  dispose(): void;
}

const HOME_POSITION = new THREE.Vector3(0, 0.5, 5.5);
const MIN_DISTANCE = 0.6;
const MAX_DISTANCE = 40;

// ---- tweak these if you like -------------------------------------------------
const MAX_PIXEL_RATIO = 1.5; // 1 = lightest, 2 = sharpest
const TEXT_OUTER = 1200;
const TEXT_INNER = 100;
const TEXT_AMBIENT = 400;
const DEBRIS = 250;
const DUST = 2000;
// -----------------------------------------------------------------------------

// How each state changes the orb. 1 = the original calm look.
const STATE_LOOK: Record<AvatarState, { spin: number; bloom: number; talk: number; breathe: number }> = {
  idle: { spin: 1, bloom: 0, talk: 0, breathe: 0 },
  listening: { spin: 1.5, bloom: 0.15, talk: 0, breathe: 1 },
  thinking: { spin: 4, bloom: 0.25, talk: 0, breathe: 0 },
  speaking: { spin: 1.8, bloom: 0.35, talk: 1, breathe: 0 },
};

const C_BRIGHT = 0x14e0c0;
const C_MID = 0x0d9488;
const C_DIM = 0x0f5e56;
const C_FAINT = 0x0a3a35;
const C_HOT = 0x7dfff0;

const CODE = [
  "sys.init()", "0xFF3A", "malloc()", ">> SCAN", "void*", "ACK",
  "SYNC OK", "ptr_ref", "exec()", "hash256", "::bind", "core.0",
  "01101001", "10110100", ">>> RDY", "HEAP 4K", "TCP/SYN",
  "mutex.lk", "IRQ 0x7", "DMA xfer", "REG EAX", "FAULT 0",
  "kernel.d", "pipe |>", "chmod +x", "fork()", "SIGTERM",
  "eth0: UP", "AES-256", "RSA 4096", "TLS 1.3", "HTTP/2",
  "latency", "200 OK", "PATCH /", "fn main", "use std",
  "impl Orb", "async {}", "spawn()", "arc::new", ".unwrap",
];

/** Collects many polylines into ONE LineSegments (one draw call). Opacity is baked into the colour,
 *  which is identical to the original under additive blending. */
class LineBatch {
  private pos: number[] = [];
  private col: number[] = [];
  private c = new THREE.Color();
  poly(pts: THREE.Vector3[], color: number, opacity: number) {
    this.c.setHex(color).multiplyScalar(opacity);
    for (let i = 0; i < pts.length - 1; i++) {
      const a = pts[i], b = pts[i + 1];
      this.pos.push(a.x, a.y, a.z, b.x, b.y, b.z);
      this.col.push(this.c.r, this.c.g, this.c.b, this.c.r, this.c.g, this.c.b);
    }
  }
  loop(pts: THREE.Vector3[], color: number, opacity: number) {
    this.poly([...pts, pts[0]], color, opacity);
  }
  build(material?: THREE.LineBasicMaterial) {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(this.pos, 3));
    g.setAttribute("color", new THREE.Float32BufferAttribute(this.col, 3));
    return new THREE.LineSegments(g, material ?? batchMaterial());
  }
}

function batchMaterial() {
  return new THREE.LineBasicMaterial({
    vertexColors: true,
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    depthTest: false,
  });
}

const latPts = (radius: number, lat: number, segs = 120) => {
  const r = radius * Math.cos(lat);
  const y = radius * Math.sin(lat);
  const pts: THREE.Vector3[] = [];
  for (let i = 0; i <= segs; i++) {
    const a = (i / segs) * Math.PI * 2;
    pts.push(new THREE.Vector3(r * Math.cos(a), y, r * Math.sin(a)));
  }
  return pts;
};

const sph = (R: number, lat: number, lon: number) =>
  new THREE.Vector3(R * Math.cos(lat) * Math.cos(lon), R * Math.sin(lat), R * Math.cos(lat) * Math.sin(lon));

const meridianPts = (radius: number, lon: number, segs = 120) => {
  const pts: THREE.Vector3[] = [];
  for (let i = 0; i <= segs; i++) pts.push(sph(radius, (i / segs) * Math.PI - Math.PI / 2, lon));
  return pts;
};

export function createOrbScene(container: HTMLElement): OrbSceneApi {
  let width = container.clientWidth || 1;
  let height = container.clientHeight || 1;

  // ——— SCENE ———
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(55, width / height, 0.1, 500);
  camera.position.copy(HOME_POSITION);

  const renderer = new THREE.WebGLRenderer({ antialias: false, powerPreference: "high-performance" });
  let pixelRatio = Math.min(window.devicePixelRatio || 1, MAX_PIXEL_RATIO);
  renderer.setPixelRatio(pixelRatio);
  renderer.setSize(width, height);
  renderer.domElement.style.cssText = "display:block;width:100%;height:100%;touch-action:none";
  container.appendChild(renderer.domElement);

  // ——— POST PROCESSING (bloom + slight colour fringe) ———
  const composer = new EffectComposer(renderer);
  composer.setPixelRatio(pixelRatio);
  composer.setSize(width, height);
  composer.addPass(new RenderPass(scene, camera));
  const bloom = new UnrealBloomPass(new THREE.Vector2(width, height), 1.8, 0.4, 0.2);
  composer.addPass(bloom);

  const chromaticPass = new ShaderPass({
    uniforms: { tDiffuse: { value: null }, uTime: { value: 0 }, uIntensity: { value: 0.003 } },
    vertexShader: `
      varying vec2 vUv;
      void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: `
      uniform sampler2D tDiffuse; uniform float uTime; uniform float uIntensity; varying vec2 vUv;
      void main() {
        vec2 dir = vUv - vec2(0.5);
        float offset = uIntensity * length(dir);
        float flicker = 1.0 + 0.02 * sin(uTime * 30.0) * sin(uTime * 7.3);
        vec4 cr = texture2D(tDiffuse, vUv + dir * offset);
        vec4 cg = texture2D(tDiffuse, vUv);
        vec4 cb = texture2D(tDiffuse, vUv - dir * offset * 0.5);
        gl_FragColor = vec4(cr.r, cg.g * 1.05, cb.b * 0.6, 1.0) * flicker;
        gl_FragColor.rgb = mix(gl_FragColor.rgb, gl_FragColor.rgb * vec3(1.15, 0.85, 0.55), 0.3);
      }`,
  });
  composer.addPass(chromaticPass);

  // ——— CONTROLS (drag to spin, scroll to zoom) ———
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.04;
  controls.minDistance = MIN_DISTANCE;
  controls.maxDistance = MAX_DISTANCE;
  controls.zoomSpeed = 1.4;
  controls.enablePan = false;

  const orbGroup = new THREE.Group();
  scene.add(orbGroup);

  // ═══ LAYER 1: OUTER SHELL (one draw call) ═══
  const R1 = 2.0;
  const outerBatch = new LineBatch();
  for (let i = -15; i <= 15; i++) {
    const lat = (i / 15) * (Math.PI / 2) * 0.95;
    outerBatch.poly(latPts(R1, lat), i % 3 === 0 ? C_MID : C_FAINT, i % 3 === 0 ? 0.5 : 0.12);
  }
  for (let i = 0; i < 24; i++) {
    const major = i % 6 === 0;
    outerBatch.poly(meridianPts(R1, (i / 24) * Math.PI * 2), major ? C_MID : C_FAINT, major ? 0.6 : 0.1);
  }
  const CROSS_LINES = 18, CROSS_SPREAD = 0.25;
  for (let i = 0; i < 4; i++) {
    const lon = (i / 4) * Math.PI * 2;
    for (let j = 0; j < CROSS_LINES; j++) {
      const t = (j / (CROSS_LINES - 1)) * 2 - 1;
      outerBatch.poly(
        meridianPts(R1, lon + (t * CROSS_SPREAD) / 2, 200),
        Math.abs(t) < 0.3 ? C_BRIGHT : C_MID,
        0.85 * (1 - Math.abs(t) * 0.7),
      );
    }
  }
  const EQ_LINES = 20, EQ_SPREAD = 0.35;
  for (let j = 0; j < EQ_LINES; j++) {
    const t = (j / (EQ_LINES - 1)) * 2 - 1;
    outerBatch.poly(
      latPts(R1, (t * EQ_SPREAD) / 2, 200),
      Math.abs(t) < 0.3 ? C_BRIGHT : C_MID,
      0.8 * (1 - Math.abs(t) * 0.65),
    );
  }
  // small hexagon nodes on the surface
  const hexHelper = new THREE.Object3D();
  for (let i = 0; i < 15; i++) {
    const phi = Math.acos(2 * Math.random() - 1);
    const theta = Math.random() * Math.PI * 2;
    const r = R1 + 0.02;
    const hr = 0.03 + Math.random() * 0.02;
    hexHelper.position.set(r * Math.sin(phi) * Math.cos(theta), r * Math.cos(phi), r * Math.sin(phi) * Math.sin(theta));
    hexHelper.lookAt(0, 0, 0);
    hexHelper.updateMatrix();
    const hex: THREE.Vector3[] = [];
    for (let k = 0; k < 6; k++) {
      const a = (k / 6) * Math.PI * 2;
      hex.push(new THREE.Vector3(hr * Math.cos(a), hr * Math.sin(a), 0).applyMatrix4(hexHelper.matrix));
    }
    outerBatch.loop(hex, C_MID, 0.5);
  }
  const outerShell = outerBatch.build();
  orbGroup.add(outerShell);

  // ═══ LAYER 2: GRID PANELS (30 small objects, so they can flicker) ═══
  const panelGroup = new THREE.Group();
  const panelMat = batchMaterial();
  for (let i = 0; i < 30; i++) {
    const latC = (Math.random() - 0.5) * Math.PI * 0.8;
    const lonC = Math.random() * Math.PI * 2;
    const size = 0.15 + Math.random() * 0.25;
    const div = 3 + Math.floor(Math.random() * 3);
    const b = new LineBatch();
    for (let a = 0; a <= div; a++) {
      const lat = latC - size / 2 + (a / div) * size;
      const pts: THREE.Vector3[] = [];
      for (let j = 0; j <= div * 4; j++) pts.push(sph(R1 + 0.01, lat, lonC - size / 2 + (j / (div * 4)) * size));
      b.poly(pts, C_DIM, 0.25);
    }
    for (let a = 0; a <= div; a++) {
      const lon = lonC - size / 2 + (a / div) * size;
      const pts: THREE.Vector3[] = [];
      for (let j = 0; j <= div * 4; j++) pts.push(sph(R1 + 0.01, latC - size / 2 + (j / (div * 4)) * size, lon));
      b.poly(pts, C_DIM, 0.25);
    }
    panelGroup.add(b.build(panelMat));
  }
  orbGroup.add(panelGroup);

  // ═══ LAYER 3: SECOND SHELL, broken arcs ═══
  const R2 = 2.12;
  const shell2Batch = new LineBatch();
  for (let i = 0; i < 16; i++) {
    const lat = (Math.random() - 0.5) * Math.PI * 0.85;
    const start = Math.random() * Math.PI * 2;
    const len = 0.3 + Math.random() * 1.2;
    const r = R2 * Math.cos(lat), y = R2 * Math.sin(lat);
    const pts: THREE.Vector3[] = [];
    for (let j = 0; j <= 60; j++) {
      const a = start + (j / 60) * len;
      pts.push(new THREE.Vector3(r * Math.cos(a), y, r * Math.sin(a)));
    }
    shell2Batch.poly(pts, C_MID, 0.2 + Math.random() * 0.3);
  }
  for (let i = 0; i < 12; i++) {
    const lon = Math.random() * Math.PI * 2;
    const start = (Math.random() - 0.5) * Math.PI * 0.8;
    const len = 0.3 + Math.random() * 0.8;
    const pts: THREE.Vector3[] = [];
    for (let j = 0; j <= 40; j++) pts.push(sph(R2, start + (j / 40) * len, lon));
    shell2Batch.poly(pts, C_DIM, 0.15 + Math.random() * 0.2);
  }
  const shell2 = shell2Batch.build();
  orbGroup.add(shell2);

  // ═══ LAYER 4: INNER CORE, spiral geodesic ═══
  const R3 = 0.9;
  const coreBatch = new LineBatch();
  for (let s = 0; s < 8; s++) {
    const turns = 3 + Math.random() * 2;
    const phase = (s / 8) * Math.PI * 2;
    const pts: THREE.Vector3[] = [];
    for (let i = 0; i <= 300; i++) {
      const t = i / 300;
      pts.push(sph(R3, t * Math.PI - Math.PI / 2, t * turns * Math.PI * 2 + phase));
    }
    coreBatch.poly(pts, C_BRIGHT, 0.3 + Math.random() * 0.2);
  }
  for (let i = -6; i <= 6; i++) coreBatch.poly(latPts(R3, (i / 6) * (Math.PI / 2) * 0.9, 80), C_DIM, 0.2);
  for (let i = 0; i < 12; i++) coreBatch.poly(meridianPts(R3, (i / 12) * Math.PI * 2, 80), C_DIM, 0.15);
  const innerCore = coreBatch.build();
  orbGroup.add(innerCore);

  // ═══ LAYER 5: bright hot centre ═══
  const icoWireMat = new THREE.LineBasicMaterial({
    color: C_HOT, transparent: true, opacity: 0.9, blending: THREE.AdditiveBlending, depthWrite: false, depthTest: false,
  });
  const icoWire = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.IcosahedronGeometry(0.25, 1)), icoWireMat);
  orbGroup.add(icoWire);

  const coreSphereMat = new THREE.MeshBasicMaterial({
    color: C_HOT, transparent: true, opacity: 0.15, blending: THREE.AdditiveBlending, depthWrite: false, depthTest: false,
  });
  const coreSphere = new THREE.Mesh(new THREE.SphereGeometry(0.15, 16, 16), coreSphereMat);
  orbGroup.add(coreSphere);

  const glowSphereMat = new THREE.MeshBasicMaterial({
    color: C_MID, transparent: true, opacity: 0.04, blending: THREE.AdditiveBlending, depthWrite: false, depthTest: false,
  });
  const glowSphere = new THREE.Mesh(new THREE.SphereGeometry(0.5, 16, 16), glowSphereMat);
  orbGroup.add(glowSphere);

  // ═══ CODE TEXT: one Points object, one atlas texture ═══
  const CELL_W = 256, CELL_H = 32;
  const atlas = document.createElement("canvas");
  atlas.width = CELL_W;
  atlas.height = CELL_H * CODE.length;
  const actx = atlas.getContext("2d")!;
  actx.font = "bold 14px 'Courier New', monospace";
  actx.fillStyle = "#fff";
  actx.textAlign = "center";
  actx.textBaseline = "middle";
  CODE.forEach((s, i) => actx.fillText(s, CELL_W / 2, CELL_H * i + CELL_H / 2));
  const atlasTex = new THREE.CanvasTexture(atlas);
  atlasTex.minFilter = THREE.LinearFilter;
  atlasTex.generateMipmaps = false;

  const TEXT_N = TEXT_OUTER + TEXT_INNER + TEXT_AMBIENT;
  const tPos = new Float32Array(TEXT_N * 3);
  const tPhi = new Float32Array(TEXT_N);
  const tTheta = new Float32Array(TEXT_N);
  const tR = new Float32Array(TEXT_N);
  const tSpeed = new Float32Array(TEXT_N);
  const tSize = new Float32Array(TEXT_N);
  const tCell = new Float32Array(TEXT_N);
  const tCol = new Float32Array(TEXT_N * 4);
  const fillText = (from: number, count: number, sizeFn: () => number, rFn: () => number, sp: [number, number], mult: number) => {
    for (let i = from; i < from + count; i++) {
      tPhi[i] = Math.acos(2 * Math.random() - 1);
      tTheta[i] = Math.random() * Math.PI * 2;
      tR[i] = rFn();
      tSpeed[i] = (sp[0] + Math.random() * sp[1]) * (Math.random() > 0.5 ? 1 : -1) * mult;
      tSize[i] = sizeFn() * 5; // world width of the label
      tCell[i] = Math.floor(Math.random() * CODE.length);
      tCol.set([1, (130 + Math.random() * 80) / 255, (20 + Math.random() * 30) / 255, 0.35 + Math.random() * 0.55], i * 4);
    }
  };
  fillText(0, TEXT_OUTER, () => 0.04 + Math.random() * 0.04, () => R1 + 0.03 + Math.random() * 0.08, [0.0002, 0.0008], 1);
  fillText(TEXT_OUTER, TEXT_INNER, () => 0.03 + Math.random() * 0.03, () => R3 + 0.02, [0.0005, 0.001], 2);
  fillText(TEXT_OUTER + TEXT_INNER, TEXT_AMBIENT, () => 0.03, () => R3 + 0.2 + Math.random() * (R1 - R3 - 0.3), [0.0003, 0.0006], 1.2);

  const textGeo = new THREE.BufferGeometry();
  textGeo.setAttribute("position", new THREE.BufferAttribute(tPos, 3));
  textGeo.setAttribute("aPhi", new THREE.BufferAttribute(tPhi, 1));
  textGeo.setAttribute("aTheta", new THREE.BufferAttribute(tTheta, 1));
  textGeo.setAttribute("aR", new THREE.BufferAttribute(tR, 1));
  textGeo.setAttribute("aSpeed", new THREE.BufferAttribute(tSpeed, 1));
  textGeo.setAttribute("aSize", new THREE.BufferAttribute(tSize, 1));
  textGeo.setAttribute("aCell", new THREE.BufferAttribute(tCell, 1));
  textGeo.setAttribute("aCol", new THREE.BufferAttribute(tCol, 4));
  const textMat = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    depthTest: false,
    blending: THREE.AdditiveBlending,
    uniforms: {
      uAtlas: { value: atlasTex },
      uCells: { value: CODE.length },
      uFrames: { value: 0 },
      uScale: { value: 800 },
    },
    vertexShader: `
      uniform float uFrames; uniform float uScale;
      attribute float aPhi; attribute float aTheta; attribute float aR; attribute float aSpeed;
      attribute float aSize; attribute float aCell; attribute vec4 aCol;
      varying float vCell; varying vec4 vCol;
      void main() {
        float th = aTheta + aSpeed * uFrames;
        vec3 p = aR * vec3(sin(aPhi) * cos(th), cos(aPhi), sin(aPhi) * sin(th));
        vec4 mv = modelViewMatrix * vec4(p, 1.0);
        gl_PointSize = clamp(aSize * uScale / max(0.05, -mv.z), 1.0, 256.0);
        gl_Position = projectionMatrix * mv;
        vCell = aCell; vCol = aCol;
      }`,
    fragmentShader: `
      uniform sampler2D uAtlas; uniform float uCells;
      varying float vCell; varying vec4 vCol;
      void main() {
        // the label is a thin strip across the middle of the square point
        float t = (gl_PointCoord.y - 0.5) / 0.14 + 0.5;
        if (t < 0.0 || t > 1.0) discard;
        float a = texture2D(uAtlas, vec2(gl_PointCoord.x, 1.0 - (vCell + t) / uCells)).a;
        if (a < 0.02) discard;
        gl_FragColor = vec4(vCol.rgb, a * vCol.a);
      }`,
  });
  const textPoints = new THREE.Points(textGeo, textMat);
  textPoints.frustumCulled = false;
  orbGroup.add(textPoints);

  // ═══ ORBITING DEBRIS: 6 instanced meshes ═══
  const debrisGeos = [
    new THREE.IcosahedronGeometry(0.012, 0),
    new THREE.IcosahedronGeometry(0.02, 0),
    new THREE.IcosahedronGeometry(0.03, 1),
    new THREE.IcosahedronGeometry(0.008, 0),
    new THREE.TetrahedronGeometry(0.015, 0),
    new THREE.OctahedronGeometry(0.018, 0),
  ];
  const debrisMat = new THREE.MeshBasicMaterial({
    color: 0xffffff, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, depthTest: false,
  });
  interface Piece { orbitR: number; speed: number; tiltX: number; tiltZ: number; phase: number; rx: number; rz: number; slot: number }
  const groups: Piece[][] = debrisGeos.map(() => []);
  for (let i = 0; i < DEBRIS; i++) {
    groups[Math.floor(Math.random() * debrisGeos.length)].push({
      orbitR: 1.2 + Math.random() * 4.0,
      speed: (0.08 + Math.random() * 0.6) * (Math.random() > 0.5 ? 1 : -1),
      tiltX: (Math.random() - 0.5) * Math.PI * 0.9,
      tiltZ: (Math.random() - 0.5) * Math.PI * 0.5,
      phase: Math.random() * Math.PI * 2,
      rx: 0, rz: 0, slot: 0,
    });
  }
  const debrisMeshes = debrisGeos.map((geo, gi) => {
    const mesh = new THREE.InstancedMesh(geo, debrisMat, Math.max(1, groups[gi].length));
    mesh.count = groups[gi].length;
    mesh.frustumCulled = false;
    const col = new THREE.Color();
    groups[gi].forEach((p, k) => {
      col.setHex(Math.random() > 0.7 ? C_BRIGHT : C_MID).multiplyScalar(0.3 + Math.random() * 0.6);
      mesh.setColorAt(k, col);
      p.slot = k;
    });
    mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    orbGroup.add(mesh);
    return mesh;
  });
  const dummy = new THREE.Object3D();

  // ═══ DUST ═══
  const dustPos = new Float32Array(DUST * 3);
  for (let i = 0; i < DUST; i++) {
    const rr = 0.5 + Math.pow(Math.random(), 0.6) * 7;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    dustPos[i * 3] = rr * Math.sin(phi) * Math.cos(theta);
    dustPos[i * 3 + 1] = rr * Math.cos(phi);
    dustPos[i * 3 + 2] = rr * Math.sin(phi) * Math.sin(theta);
  }
  const dustGeo = new THREE.BufferGeometry();
  dustGeo.setAttribute("position", new THREE.Float32BufferAttribute(dustPos, 3));
  const dotC = document.createElement("canvas");
  dotC.width = dotC.height = 64;
  const dctx = dotC.getContext("2d")!;
  const dg = dctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  dg.addColorStop(0, "rgba(255,170,48,1)");
  dg.addColorStop(0.2, "rgba(255,120,20,0.6)");
  dg.addColorStop(0.5, "rgba(200,80,0,0.15)");
  dg.addColorStop(1, "rgba(100,40,0,0)");
  dctx.fillStyle = dg;
  dctx.fillRect(0, 0, 64, 64);
  const dustMat = new THREE.PointsMaterial({
    map: new THREE.CanvasTexture(dotC),
    size: 0.04,
    transparent: true,
    opacity: 0.5,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    depthTest: false,
    sizeAttenuation: true,
    color: C_BRIGHT,
  });
  const dustPoints = new THREE.Points(dustGeo, dustMat);
  orbGroup.add(dustPoints);

  // ═══ SCANNING RINGS ═══
  const makeScanRing = (radius: number, thickness: number) => {
    const mesh = new THREE.Mesh(
      new THREE.RingGeometry(radius - thickness, radius + thickness, 120),
      new THREE.MeshBasicMaterial({
        color: C_BRIGHT, transparent: true, opacity: 0, blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide, depthWrite: false, depthTest: false,
      }),
    );
    mesh.rotation.x = Math.PI / 2;
    return mesh;
  };
  const scanRing1 = makeScanRing(R1, 0.01);
  const scanRing2 = makeScanRing(R1 * 0.7, 0.008);
  orbGroup.add(scanRing1, scanRing2);

  // ═══ CAMERA HELPERS (used by keys / buttons) ═══
  const sphericalScratch = new THREE.Spherical();
  const offsetScratch = new THREE.Vector3();
  const rotateBy = (dTheta: number, dPhi: number) => {
    offsetScratch.copy(camera.position).sub(controls.target);
    sphericalScratch.setFromVector3(offsetScratch);
    sphericalScratch.theta -= dTheta;
    sphericalScratch.phi = THREE.MathUtils.clamp(sphericalScratch.phi - dPhi, 0.05, Math.PI - 0.05);
    sphericalScratch.makeSafe();
    offsetScratch.setFromSpherical(sphericalScratch);
    camera.position.copy(controls.target).add(offsetScratch);
    camera.lookAt(controls.target);
  };
  const zoomBy = (factor: number) => {
    offsetScratch.copy(camera.position).sub(controls.target);
    offsetScratch.setLength(THREE.MathUtils.clamp(offsetScratch.length() * factor, MIN_DISTANCE, MAX_DISTANCE));
    camera.position.copy(controls.target).add(offsetScratch);
  };
  const resetView = () => {
    camera.position.copy(HOME_POSITION);
    controls.target.set(0, 0, 0);
    camera.lookAt(controls.target);
    controls.update();
  };

  // ═══ SIZE ═══
  const updateScale = () => {
    const fovTan = 2 * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2);
    textMat.uniforms.uScale.value = (height * pixelRatio) / fovTan;
    dustMat.size = 0.04;
  };
  const applySize = () => {
    renderer.setPixelRatio(pixelRatio);
    renderer.setSize(width, height, false);
    composer.setPixelRatio(pixelRatio);
    composer.setSize(width, height);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    updateScale();
  };
  applySize();
  const ro = new ResizeObserver(() => {
    const w = container.clientWidth || 1, h = container.clientHeight || 1;
    if (w === width && h === height) return;
    width = w;
    height = h;
    applySize();
  });
  ro.observe(container);

  // ═══ STATE ═══
  let look = STATE_LOOK.idle;
  let spinMul = 1, bloomAdd = 0, talkAmt = 0, breatheAmt = 0;

  // ═══ ANIMATION ═══
  let last = performance.now();
  let t = 0;          // seconds
  let frames = 0;     // 60 per second, used for text drift
  let flickerTimer = 0;
  let rafId = 0;
  let disposed = false;

  // quality watchdog
  let slowFor = 0, level = 0;
  const lowerQuality = () => {
    level++;
    if (level === 1) pixelRatio = Math.min(pixelRatio, 1);
    else if (level === 2) {
      pixelRatio = Math.min(pixelRatio, 0.8);
      chromaticPass.enabled = false;
    } else if (level === 3) {
      bloom.enabled = false;
    } else return;
    applySize();
  };

  const animate = () => {
    if (disposed) return;
    rafId = requestAnimationFrame(animate);
    const now = performance.now();
    const rawDt = (now - last) / 1000;
    last = now;
    const dt = Math.min(0.1, rawDt);
    const f = dt * 60; // 1.0 at 60 fps: all the original per-frame speeds are multiplied by this
    t += dt;
    frames += f;

    if (rawDt < 0.5) {
      slowFor = rawDt > 0.03 ? slowFor + rawDt : Math.max(0, slowFor - rawDt * 2);
      if (slowFor > 2.5) {
        slowFor = 0;
        lowerQuality();
      }
    }

    // ease towards the current state
    const k = Math.min(1, dt * 3);
    spinMul += (look.spin - spinMul) * k;
    bloomAdd += (look.bloom - bloomAdd) * k;
    talkAmt += (look.talk - talkAmt) * k;
    breatheAmt += (look.breathe - breatheAmt) * k;
    const sm = spinMul * f;

    outerShell.rotation.y += 0.0015 * sm;
    outerShell.rotation.x = Math.sin(t * 0.08) * 0.05;
    panelGroup.rotation.y += 0.0018 * sm;
    panelGroup.rotation.x = Math.sin(t * 0.08 + 0.5) * 0.04;
    shell2.rotation.y -= 0.001 * sm;
    shell2.rotation.z = Math.sin(t * 0.12) * 0.03;
    innerCore.rotation.y -= 0.005 * sm;
    innerCore.rotation.z += 0.002 * sm;
    innerCore.rotation.x = Math.cos(t * 0.1) * 0.08;
    icoWire.rotation.x += 0.008 * sm;
    icoWire.rotation.y += 0.012 * sm;

    // centre pulse (the original surges), plus a fake talking rhythm while she speaks
    const wave1 = Math.sin(t * 1.2);
    const wave3 = Math.pow(Math.max(0, Math.sin(t * 0.4)), 5);
    const wave4 = Math.pow(Math.max(0, Math.sin(t * 0.7 + 2)), 8);
    const fadeOut = Math.pow(Math.max(0, Math.sin(t * 0.25)), 3);
    const talk = talkAmt * (0.5 + 0.5 * Math.sin(t * 5.5) * Math.sin(t * 2.03 + 1.3));
    const breathe = breatheAmt * (0.5 + 0.5 * Math.sin(t * 2.2));
    const surge = wave3 * 1.5 + wave4 * 2.0 + talk * 1.1 + breathe * 0.5;
    const fade = fadeOut * (1 - Math.min(1, talkAmt + breatheAmt));
    coreSphere.scale.setScalar(1 + surge + Math.sin(t * 5) * 0.05);
    coreSphereMat.opacity = Math.min(0.6, Math.max(0, (0.08 + wave1 * 0.05 + surge * 0.2) * (1 - fade * 0.95)));
    glowSphere.scale.setScalar(1 + surge * 0.8);
    glowSphereMat.opacity = Math.max(0, (0.03 + surge * 0.08) * (1 - fade * 0.9));
    icoWire.scale.setScalar(1 + surge * 0.6);
    icoWireMat.opacity = Math.min(1, 0.5 + surge * 0.4);

    // debris
    for (let gi = 0; gi < groups.length; gi++) {
      const list = groups[gi];
      const mesh = debrisMeshes[gi];
      for (let i = 0; i < list.length; i++) {
        const u = list[i];
        const a = t * u.speed + u.phase;
        u.rx += 0.015 * f;
        u.rz += 0.01 * f;
        dummy.position.set(
          u.orbitR * Math.cos(a) * Math.cos(u.tiltX),
          u.orbitR * Math.sin(u.tiltX) * Math.sin(a * 0.8) + Math.sin(a * 0.3 + u.tiltZ) * 0.2,
          u.orbitR * Math.sin(a) * Math.cos(u.tiltZ),
        );
        dummy.rotation.set(u.rx, 0, u.rz);
        dummy.updateMatrix();
        mesh.setMatrixAt(u.slot, dummy.matrix);
      }
      mesh.instanceMatrix.needsUpdate = true;
    }

    // code text drift happens on the GPU
    textMat.uniforms.uFrames.value = frames;

    // scanning rings (faster while thinking)
    const ts = t * (1 + (spinMul - 1) * 0.4);
    const y1 = Math.sin(ts * 0.4) * R1;
    const s1 = Math.sqrt(Math.max(0, R1 * R1 - y1 * y1)) / R1;
    scanRing1.position.y = y1;
    scanRing1.scale.set(s1, s1, 1);
    (scanRing1.material as THREE.MeshBasicMaterial).opacity = 0.2 * s1;
    const y2 = Math.sin(ts * 0.6 + 2) * R3;
    const s2 = Math.sqrt(Math.max(0, R3 * R3 - y2 * y2)) / R3;
    scanRing2.position.y = y2;
    scanRing2.scale.set(s2, s2, 1);
    (scanRing2.material as THREE.MeshBasicMaterial).opacity = 0.15 * s2;

    dustPoints.rotation.y += 0.0002 * sm;

    // random flicker on a few panels
    flickerTimer += dt;
    if (flickerTimer > 0.1) {
      flickerTimer = 0;
      for (const p of panelGroup.children) if (Math.random() > 0.95) p.visible = !p.visible;
    }

    bloom.strength = 1.6 + Math.sin(t * 0.8) * 0.3 + bloomAdd + talk * 0.3;
    chromaticPass.uniforms.uTime.value = t;

    controls.update();
    composer.render();
  };
  animate();

  const dispose = () => {
    disposed = true;
    cancelAnimationFrame(rafId);
    ro.disconnect();
    controls.dispose();
    scene.traverse((obj) => {
      const o = obj as THREE.Mesh;
      o.geometry?.dispose();
      const mats = Array.isArray(o.material) ? o.material : o.material ? [o.material] : [];
      for (const m of mats) {
        (m as THREE.Material & { map?: THREE.Texture }).map?.dispose();
        m.dispose();
      }
    });
    atlasTex.dispose();
    composer.dispose();
    renderer.dispose();
    renderer.forceContextLoss();
    renderer.domElement.remove();
  };

  return {
    setState: (s) => {
      look = STATE_LOOK[s];
    },
    rotateBy,
    zoomBy,
    zoomIn: () => zoomBy(0.65),
    zoomOut: () => zoomBy(1.55),
    resetView,
    dispose,
  };
}

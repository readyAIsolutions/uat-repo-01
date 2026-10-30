// VESYNTRA Module 10 — image-to-3D workflow controller (new page, additive).
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const $ = (id) => document.getElementById(id);
const state = { files: [], jobId: null, pollTimer: null, model: null };

// ---- Three.js viewer ---------------------------------------------------
const canvas = $("viewer");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

const scene = new THREE.Scene();
scene.add(new THREE.HemisphereLight(0xffffff, 0x334455, 1.2));
const key = new THREE.DirectionalLight(0xffffff, 1.6);
key.position.set(5, 8, 6);
scene.add(key);
scene.add(new THREE.AxesHelper(1));

const camera = new THREE.PerspectiveCamera(50, 1, 0.01, 1000);
camera.position.set(5, 3, 7);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;

function resize() {
  const w = canvas.clientWidth || 600;
  const h = canvas.clientHeight || 560;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(canvas);
resize();

function frame() {
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(frame);
}
frame();

function fitCamera(object) {
  const box = new THREE.Box3().setFromObject(object);
  if (box.isEmpty()) return;
  const sphere = box.getBoundingSphere();
  camera.position.copy(sphere.center).add(new THREE.Vector3(
    sphere.radius * 1.4, sphere.radius * 0.9, sphere.radius * 1.6));
  controls.target.copy(sphere.center);
  const dist = camera.position.distanceTo(controls.target);
  camera.near = Math.max(dist / 1000, 0.001);
  camera.far = Math.max(dist * 20, 100);
  camera.updateProjectionMatrix();
  controls.update();
}

$("btn-reset").onclick = () => state.model && fitCamera(state.model);
$("btn-zoom-in").onclick = () => controls.dollyIn(1.2);
$("btn-zoom-out").onclick = () => controls.dollyOut(1.2);

// ---- uploads ------------------------------------------------------------
const drop = $("drop");
drop.onclick = () => $("file-input").click();
$("file-input").onchange = (e) => addFiles([...e.target.files]);
drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("over"); };
drop.ondragleave = () => drop.classList.remove("over");
drop.ondrop = (e) => {
  e.preventDefault();
  drop.classList.remove("over");
  addFiles([...e.dataTransfer.files]);
};

function addFiles(files) {
  const allowed = /\.(jpe?g|png|webp)$/i;
  const fresh = files.filter((f) => {
    if (!allowed.test(f.name)) {
      setBanner(`err`, `Rejected ${f.name}: not a JPEG/PNG/WebP file`);
      return false;
    }
    if (f.size > 10 * 1024 * 1024) {
      setBanner(`err`, `Rejected ${f.name}: over 10 MB`);
      return false;
    }
    return true;
  });
  const merged = [...state.files, ...fresh].slice(0, 10);
  state.files = merged;
  renderThumbs();
  if (fresh.length + state.files.length > 10) {
    setBanner(`err`, `At most 10 photographs per job — older files dropped.`);
  }
  $("btn-submit").disabled = state.files.length === 0;
}

function renderThumbs() {
  const wrap = $("thumbs");
  wrap.innerHTML = "";
  state.files.forEach((f, i) => {
    const fig = document.createElement("figure");
    const img = document.createElement("img");
    img.src = URL.createObjectURL(f);
    const cap = document.createElement("figcaption");
    cap.textContent = `${i + 1} · ${f.name.slice(0, 18)}`;
    cap.onclick = () => {
      state.files.splice(i, 1);
      renderThumbs();
      $("btn-submit").disabled = state.files.length === 0;
    };
    fig.append(img, cap);
    wrap.append(fig);
  });
}

function setBanner(kind, text) {
  const b = $("banner");
  b.className = kind;
  b.textContent = text;
}

// ---- provider capability check ------------------------------------------
async function checkCapabilities() {
  try {
    const r = await fetch("/api/reconstruct/capabilities");
    const data = await r.json();
    const pill = $("provider-pill");
    if (data.configured) {
      pill.textContent = `● ${data.provider} READY (${data.environment})`;
      pill.className = "ok";
    } else {
      pill.textContent = `● ${data.provider} NOT READY`;
      pill.className = "bad";
      pill.title = data.problem || "";
    }
  } catch { /* keep pill states */ }
}

// ---- submit --------------------------------------------------------------
$("btn-submit").onclick = async () => {
  const fd = new FormData();
  state.files.forEach((f) => fd.append("images", f, f.name));
  const len = parseFloat($("vessel-length").value);
  const beam = parseFloat($("vessel-beam").value);
  if (!Number.isNaN(len)) fd.append("vessel_length_m", String(len));
  if (!Number.isNaN(beam)) fd.append("vessel_beam_m", String(beam));
  const note = $("reference-note").value.trim();
  if (note) fd.append("reference_note", note);

  setBanner("", "");
  $("job-status").textContent = "Submitting…";
  try {
    const r = await fetch("/api/reconstruct/jobs", { method: "POST", body: fd });
    const body = await r.json();
    if (!r.ok) {
      const err = body.error || {};
      const detail = (err.details || []).join(" · ") || err.message || "request failed";
      setBanner("err", `Submission rejected: ${detail}`);
      $("job-status").textContent = "";
      return;
    }
    state.jobId = body.id;
    $("out-job").textContent = body.id;
    $("btn-submit").disabled = true;
    pollJob();
  } catch (e) {
    setBanner("err", `Network error: ${e.message}`);
  }
};

function pollJob() {
  clearInterval(state.pollTimer);
  state.pollTimer = setInterval(async () => {
    if (!state.jobId) return;
    try {
      const r = await fetch(`/api/reconstruct/jobs/${state.jobId}`);
      const job = await r.json();
      renderJob(job);
      if (job.status === "succeeded" || job.status === "failed" || job.status === "canceled") {
        clearInterval(state.pollTimer);
        $("btn-submit").disabled = state.files.length === 0;
      }
    } catch { /* transient — keep polling */ }
  }, 1500);
}

function renderJob(job) {
  $("out-status").textContent = job.status.toUpperCase();
  $("out-engine").textContent =
    `${job.provider || "—"}${job.simulated ? " [SIMULATED]" : ""}` +
    (job.provider_model ? ` (${job.provider_model})` : "");
  $("out-mesh").textContent = job.vertex_count != null
    ? `${job.vertex_count.toLocaleString()} verts · ${job.triangle_count.toLocaleString()} tris`
    : "—";

  $("out-warnings").innerHTML = job.warnings.length
    ? job.warnings.map((w) => `<li>${w}</li>`).join("")
    : "<li>—</li>";
  $("out-errors").innerHTML = job.error
    ? `<li>${job.error}</li>` : "<li>—</li>";

  if (job.simulated) {
    setBanner("sim", "SIMULATED — this job used the labelled development mock, not AI reconstruction.");
  } else if (job.status === "failed") {
    setBanner("err", "Reconstruction failed — see Errors.");
  }

  const ready = job.status === "succeeded";
  $("btn-dl-glb").disabled = !ready;
  $("btn-dl-obj").disabled = !ready;
  $("btn-dl-orig").disabled = !ready;
  if (ready && !state.model) loadModel(job.id);
}

function loadModel(jobId) {
  const loader = new GLTFLoader();
  loader.load(`/api/reconstruct/jobs/${jobId}/export?format=glb`,
    (gltf) => {
      // Drop any previously loaded boat.
      [...scene.children].forEach((c) => {
        if (c.userData.marlinModel) scene.remove(c);
      });
      const root = gltf.scene;
      root.userData.marlinModel = true;
      scene.add(root);
      state.model = root;
      fitCamera(root);
      $("job-status").textContent = "Model loaded — inspect, rotate, download.";
    },
    undefined,
    (err) => setBanner("err", `Viewer load failed: ${err.message}`));
}

// ---- downloads -----------------------------------------------------------
$("btn-dl-glb").onclick = () => download(`/api/reconstruct/jobs/${state.jobId}/export?format=glb`);
$("btn-dl-obj").onclick = () => download(`/api/reconstruct/jobs/${state.jobId}/export?format=obj`);
$("btn-dl-orig").onclick = () => download(`/api/reconstruct/jobs/${state.jobId}/model`);

function download(url) {
  const a = document.createElement("a");
  a.href = url;
  a.download = "";
  document.body.append(a);
  a.click();
  a.remove();
}

checkCapabilities();

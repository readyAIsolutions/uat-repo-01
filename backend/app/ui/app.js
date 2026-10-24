// MARLIN Section 7 UI — function-first, same-origin, no secrets in the browser.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const $ = (id) => document.getElementById(id);
const API_TIMEOUT_MS = 15000;

const state = {
  rhino: "NOT_CHECKED",       // CHECKING | CONNECTED | DISCONNECTED | ERROR
  validation: "NOT_STARTED",  // VALIDATING | VALID | INVALID
  stations: null,
  hull: null,
  busy: false,
};

async function api(path, { method = "GET", body = null, timeout = API_TIMEOUT_MS } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    return await fetch(path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch (err) {
    if (err.name === "AbortError") throw new Error("API timeout");
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

function payload() {
  const m = (id) => ({ value: Number($(id).value), unit: "m", source: "USER_SPECIFIED", locked: true });
  return {
    project_id: $("project-name").value,
    units: "meters",
    loa: m("loa"), lwl: m("lwl"), beam: m("beam"), draft: m("draft"), depth: m("depth"),
    hull_family: $("hull-family").value,
    station_count: Number($("station-count").value),
  };
}

function setRhino(status) { state.rhino = status; const p = $("rhino-pill");
  p.dataset.state = status; p.className = "pill " + status.toLowerCase().replace("_", "-");
  const label = { CHECKING:"CHECKING", CONNECTED:"CONNECTED", DISCONNECTED:"DISCONNECTED", ERROR:"ERROR", NOT_CHECKED:"NOT CHECKED" }[status];
  p.textContent = "● " + label; $("out-rhino").textContent = label; $("out-rhino").dataset.state = status; }

function setValidation(status, details) { state.validation = status;
  $("out-validation").textContent = status; $("out-validation").dataset.state = status;
  $("out-errors").innerHTML = "";
  if (details && details.length) {
    $("out-errors").innerHTML = details.map((d) => `<li>${d.field}: ${d.message}</li>`).join("");
  } else { $("out-errors").innerHTML = "<li>—</li>"; }
  refreshButtons(); }

function setBusy(busy, note = "") { state.busy = busy; $("job-status").textContent = note; refreshButtons(); }

function refreshButtons() {
  const valid = state.validation === "VALID" && !state.busy;
  $("btn-rhino").disabled = state.busy;
  $("btn-validate").disabled = state.busy;
  $("btn-stations").disabled = !valid;
  $("btn-hull").disabled = !valid;
  $("btn-view").disabled = state.busy || !state.stations;
  $("btn-open").disabled = !(state.hull && state.hull.file_reference);
}

async function checkRhino() {
  setBusy(true, "Checking Rhino.Compute…"); setRhino("CHECKING");
  try {
    const res = await api("/api/rhino/status");
    const data = await res.json();
    setRhino(data.reachable ? "CONNECTED" : "DISCONNECTED");
  } catch (err) { setRhino("ERROR"); }
  finally { setBusy(false, ""); }
}

async function validate() {
  setBusy(true, "Validating…"); setValidation("VALIDATING");
  try {
    const res = await api("/api/vessel/validate", { method: "POST", body: payload() });
    const data = await res.json();
    if (res.status === 200) { $("out-project").textContent = data.project_id; setValidation("VALID"); }
    else { setValidation("INVALID", data.error ? data.error.details : []); }
  } catch (err) { setValidation("INVALID", [{ field: "network", message: err.message }]); }
  finally { setBusy(false, ""); }
}

function renderDims(body) {
  const t = body.tolerances || {};
  const names = { loa: "LOA", beam: "Beam", draft: "Draft" };
  $("dims-body").innerHTML = Object.keys(names).map((k) => {
    const c = t[k]; if (!c) return "";
    return `<tr><td>${names[k]}</td><td>${c.requested_m}</td><td>${c.actual_m}</td>` +
           `<td>${c.error_percent}%</td><td>${c.within_tolerance ? "yes" : "NO"}</td></tr>`;
  }).join("") || "<tr><td colspan=\"5\">—</td></tr>";
}

async function generateStations() {
  setBusy(true, "Generating stations…"); $("out-stations").textContent = "GENERATING…";
  try {
    const res = await api("/api/vessel/stations", { method: "POST", body: payload() });
    const data = await res.json();
    if (res.status === 200) {
      state.stations = data;
      $("out-stations").textContent = data.station_count + " created";
      $("out-version").textContent = data.geometry_version;
      $("out-project").textContent = data.project_id;
      refreshButtons();
    } else {
      $("out-stations").textContent = "FAILED";
      $("out-errors").innerHTML = `<li>${errorMessage(data)}</li>`;
    }
  } catch (err) { $("out-stations").textContent = "FAILED"; $("out-errors").innerHTML = `<li>${err.message}</li>`; }
  finally { setBusy(false, ""); }
}

async function generateHull() {
  setBusy(true, "Generating hull…"); $("out-hull").textContent = "GENERATING…"; $("out-hull").dataset.state = "GENERATING";
  try {
    const res = await api("/api/vessel/hull", { method: "POST", body: payload() });
    const data = await res.json();
    if (res.status !== 200) {
      $("out-hull").textContent = "FAILED"; $("out-hull").dataset.state = "FAILED";
      $("out-errors").innerHTML = `<li>${errorMessage(data)}</li>`;
    } else {
      state.hull = data;
      const ok = data.status === "SUCCESS" || data.status === "success";
      $("out-hull").textContent = data.status; $("out-hull").dataset.state = ok ? "SUCCESS" : "FAILED";
      $("out-version").textContent = data.geometry_version;
      $("out-stations").textContent = data.station_count + " created";
      $("out-project").textContent = data.project_id;
      renderDims(data);
      const w = data.warnings || [];
      $("out-warnings").innerHTML = w.length ? w.map((x) => `<li>${x}</li>`).join("") : "<li>—</li>";
      $("out-errors").innerHTML = "<li>—</li>";
      $("out-reference").textContent = data.file_reference || "—";
      refreshButtons();
      viewModel(data);
    }
  } catch (err) {
    $("out-hull").textContent = "FAILED"; $("out-hull").dataset.state = "FAILED";
    $("out-errors").innerHTML = `<li>${err.message}</li>`;
  } finally { setBusy(false, ""); }
}

function errorMessage(data) {
  const code = data && data.error && data.error.code;
  if (code === "RHINO_UNAVAILABLE" || code === "RHINO_NOT_CONFIGURED") return "Rhino.Compute unavailable";
  if (code === "VESSEL_VALIDATION_FAILED") return "Validation failed";
  return (data && data.error && data.error.message) || "Request failed";
}

// ---- 3D preview (derived from the station definitions MARLIN computed) ----
let renderer, scene, camera, controls;

function ensureViewer() {
  if (renderer) return;
  const canvas = $("viewer");
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio || 1);
  renderer.setSize(canvas.clientWidth, canvas.clientHeight, false);
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0b0f14);
  camera = new THREE.PerspectiveCamera(50, canvas.clientWidth / canvas.clientHeight, 0.1, 2000);
  camera.position.set(30, 18, 30);
  controls = new OrbitControls(camera, canvas);
  scene.add(new THREE.AmbientLight(0xffffff, 0.8));
}

function viewModel(body) {
  const stations = (body && body.stations) || (state.stations && state.stations.stations);
  if (!stations) { $("viewer-hint").textContent = "No station geometry available to preview."; return; }
  ensureViewer();
  scene.clear();
  scene.add(new THREE.AmbientLight(0xffffff, 0.8));
  const center = (body.bounding_box && body.bounding_box.max) ? null : null;
  const material = new THREE.LineBasicMaterial({ color: 0x3fb950 });
  let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
  stations.forEach((st) => {
    const pts = st.points.map((p) => new THREE.Vector3(p[0], p[2], p[1]));
    pts.forEach((v) => { minX = Math.min(minX, v.x); maxX = Math.max(maxX, v.x);
      minZ = Math.min(minZ, v.y); maxZ = Math.max(maxZ, v.y); });
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    scene.add(new THREE.Line(geo, material));
  });
  const cx = (minX + maxX) / 2, cz = (minZ + maxZ) / 2;
  const span = Math.max(maxX - minX, 1);
  camera.position.set(cx, span * 0.7, cz + span * 1.6);
  controls.target.set(cx, cz, 0);
  controls.update();
  renderer.render(scene, camera);
  $("viewer-hint").textContent = "Preview only — the Rhino .3dm result is the CAD source of truth.";
}

function animate() { requestAnimationFrame(animate); if (renderer && controls) { controls.update(); renderer.render(scene, camera); } }

$("btn-rhino").addEventListener("click", checkRhino);
$("btn-validate").addEventListener("click", validate);
$("btn-stations").addEventListener("click", generateStations);
$("btn-hull").addEventListener("click", generateHull);
$("btn-view").addEventListener("click", () => viewModel(state.hull || state.stations));
$("btn-open").addEventListener("click", () => {
  const ref = state.hull && state.hull.file_reference;
  if (ref && /^https?:\/\//.test(ref)) window.open(ref, "_blank");
});
window.addEventListener("resize", () => {
  if (!renderer) return; const c = $("viewer");
  camera.aspect = c.clientWidth / c.clientHeight; camera.updateProjectionMatrix();
  renderer.setSize(c.clientWidth, c.clientHeight, false);
});

refreshButtons();
animate();

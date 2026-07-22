/* The Bible Outdoor — Owner publishing app.
   Backend = the GitHub repo itself: reads bible/state/queue from raw URLs,
   writes the custom queue via the Contents API with a fine-grained token. */
const REPO = "scapesnovel/the-bible-outdoor";
const API = `https://api.github.com/repos/${REPO}/contents`;
const RAW = `https://raw.githubusercontent.com/${REPO}/main`;
const MIN_GAP_H = 4, MIN_LEAD_H = 3, MAX_PER_DAY = 2;

let BIBLE = null, QUEUE = { queue: [] }, QUEUE_SHA = null, STATE = { published: [] };
const $ = id => document.getElementById(id);
const token = () => localStorage.getItem("gh_token") || "";

/* ---------- GitHub helpers ---------- */
function hdrs() {
  const h = { "Accept": "application/vnd.github+json" };
  if (token()) h["Authorization"] = `Bearer ${token()}`;
  return h;
}
async function ghGet(path) {
  const r = await fetch(`${API}/${path}?ref=main`, { headers: hdrs() });
  if (!r.ok) throw new Error(`GET ${path}: ${r.status}`);
  return r.json();
}
function b64encode(str) {
  return btoa(String.fromCharCode(...new TextEncoder().encode(str)));
}
function b64decode(b64) {
  return new TextDecoder().decode(Uint8Array.from(atob(b64.replace(/\n/g, "")), c => c.charCodeAt(0)));
}

/* ---------- Load data ---------- */
async function loadBible() {
  const r = await fetch(`${RAW}/data/bible.json.gz`);
  let text;
  if (r.headers.get("content-type")?.includes("json") && !r.headers.get("content-encoding")) {
    // some CDNs auto-decompress; try both paths
    try { text = await r.clone().text(); JSON.parse(text); } catch (e) { text = null; }
  }
  if (!text) {
    const r2 = await fetch(`${RAW}/data/bible.json.gz`);
    const ds = new DecompressionStream("gzip");
    text = await new Response(r2.body.pipeThrough(ds)).text();
  }
  BIBLE = JSON.parse(text);
  fillBooks();
  fillChapters();
}
function fillBooks(filter) {
  const sel = $("sel-book");
  const prev = sel.value;
  let books = Object.keys(BIBLE);
  if (filter) {
    const f = filter.toLowerCase();
    const m = books.filter(b => b.toLowerCase().includes(f));
    if (m.length) books = m;
  }
  sel.innerHTML = books.map(b => `<option>${b}</option>`).join("");
  if (books.includes(prev)) sel.value = prev;
}
function fillChapters() {
  const book = $("sel-book").value;
  $("sel-chapter").innerHTML = Object.keys(BIBLE[book]).map(c => `<option>${c}</option>`).join("");
  fillVerses();
}
function fillVerses() {
  const book = $("sel-book").value, ch = $("sel-chapter").value;
  const vs = Object.keys(BIBLE[book][ch]);
  $("sel-v1").innerHTML = vs.map(v => `<option>${v}</option>`).join("");
  $("sel-v2").innerHTML = vs.map(v => `<option>${v}</option>`).join("");
  updatePreview();
}
function chosenVerse() {
  const book = $("sel-book").value, ch = $("sel-chapter").value;
  let v1 = +$("sel-v1").value, v2 = +$("sel-v2").value;
  if (v2 < v1) v2 = v1;
  const texts = [];
  for (let v = v1; v <= v2; v++) texts.push(BIBLE[book][ch][String(v)]);
  const ref = v1 === v2 ? `${book} ${ch}:${v1}` : `${book} ${ch}:${v1}-${v2}`;
  return { ref, text: texts.join(" ") };
}
function updatePreview() {
  if (!BIBLE) return;
  const { ref, text } = chosenVerse();
  const p = $("verse-preview");
  p.classList.remove("hidden");
  p.innerHTML = `\u201C${text}\u201D <b>— ${ref.replace("Psalms ", "Psalm ")}</b>` +
    (text.length > 480 ? `<span class="verse-warn"><i class="fa-solid fa-triangle-exclamation"></i> Long for a Short — consider fewer verses.</span>` : "");
  validate();
}

async function loadQueueAndState() {
  let ok = false;
  try {
    const q = await ghGet("data/custom_queue.json");
    QUEUE_SHA = q.sha;
    QUEUE = JSON.parse(b64decode(q.content));
    ok = true;
  } catch (e) { /* keep last known */ }
  try {
    const s = await fetch(`${RAW}/data/state.json?t=${Date.now()}`);
    STATE = await s.json();
  } catch (e) { /* keep last known */ }
  const dot = $("conn-dot");
  if (dot) { dot.className = "conn-dot " + (ok ? "on" : (token() ? "off" : "")); dot.title = ok ? "Connected" : "Not connected — set token in Settings"; }
  renderQueue(); renderToday(); renderSuggestions(); validate();
}

/* ---------- Schedule logic (mirrors pipeline/custom.py) ---------- */
function shortsOnDate(dateISO) {
  let n = 0; const times = [];
  for (const x of QUEUE.queue || [])
    if (["pending", "scheduled", "rendered"].includes(x.status) && x.publish_at.slice(0, 10) === dateISO) {
      n++; times.push(new Date(x.publish_at));
    }
  for (const p of STATE.published || [])
    if (p.date === dateISO) n += (p.short_ids || []).length || (p.short_id ? 1 : 0);
  return { n, times };
}
function botRanOn(dateISO) {
  return (STATE.published || []).some(p => p.date === dateISO && ((p.short_ids || []).length || p.short_id));
}
function validate() {
  const msg = $("validate-msg"), btn = $("btn-publish");
  const fail = t => { msg.innerHTML = `<span class="err"><i class="fa-solid fa-circle-xmark"></i> ${t}</span>`; btn.disabled = true; };
  const expl = $("inp-expl").value.trim();
  $("expl-count").textContent = `${expl.length} / 600`;
  if (!token()) return fail("Set your GitHub token in ⚙️ Settings first.");
  if (!BIBLE) return fail("Bible still loading…");
  if (expl.length < 20) return fail("Explanation needs at least 20 characters.");
  const d = $("inp-date").value, t = $("inp-time").value;
  if (!d || !t) return fail("Pick a publish date and time.");
  const when = new Date(`${d}T${t}`);
  if ((when - new Date()) / 36e5 < MIN_LEAD_H)
    return fail(`Needs ≥ ${MIN_LEAD_H}h from now (bot render time). Pick later.`);
  const dateISO = when.toISOString().slice(0, 10);
  const { n, times } = shortsOnDate(dateISO);
  if (botRanOn(dateISO))
    return fail(`The bot already published its Shorts for ${dateISO}. Earliest available day is tomorrow.`);
  if (n >= MAX_PER_DAY) return fail(`${dateISO} already has ${MAX_PER_DAY} Shorts (max).`);
  for (const x of times) {
    const gap = Math.abs(when - x) / 36e5;
    if (gap < MIN_GAP_H)
      return fail(`Only ${gap.toFixed(1)}h from another Short that day — minimum ${MIN_GAP_H}h.`);
  }
  msg.innerHTML = `<span class="ok"><i class="fa-solid fa-circle-check"></i> Slot is valid — premieres ${when.toLocaleString()}</span>`;
  btn.disabled = false;
}
function renderSuggestions() {
  const wrap = $("suggest-slots"); wrap.innerHTML = "";
  const now = new Date();
  outer:
  for (let addDays = 0; addDays < 4; addDays++) {
    for (const utcH of [13, 22]) {   // ⭐ the bot's proven prime slots
      const d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + addDays, utcH, 0));
      if ((d - now) / 36e5 < MIN_LEAD_H) continue;
      const dateISO = d.toISOString().slice(0, 10);
      if (botRanOn(dateISO) || shortsOnDate(dateISO).n >= MAX_PER_DAY) continue;
      const b = document.createElement("button");
      b.className = "chip";
      b.innerHTML = `<i class="fa-solid fa-star star"></i> ${d.toLocaleString([], { weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}`;
      b.onclick = () => {
        $("inp-date").value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
        $("inp-time").value = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
        document.querySelectorAll("#suggest-slots .chip").forEach(c => c.classList.remove("active"));
        b.classList.add("active");
        validate();
      };
      wrap.appendChild(b);
      if (wrap.children.length >= 4) break outer;
    }
  }
  if (!wrap.children.length)
    wrap.innerHTML = `<span class="text-xs">No free suggested slots in the next few days — pick manually.</span>`;
}
function renderToday() {
  const today = new Date().toISOString().slice(0, 10);
  const { n } = shortsOnDate(today);
  const slotA = new Date(); slotA.setUTCHours(13, 0, 0, 0);
  const slotB = new Date(); slotB.setUTCHours(22, 0, 0, 0);
  const fmt = d => d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  $("today-info").innerHTML =
    `<div class="today-row"><i class="fa-solid fa-clapperboard"></i>
       <span><span class="today-count">${n}</span> / ${MAX_PER_DAY} Shorts today ${botRanOn(today) ? ' · <span style="color:var(--green)">bot already ran ✓</span>' : ""}</span></div>
     <div class="today-row"><i class="fa-solid fa-star"></i>
       <span>Bot prime slots: <b>${fmt(slotA)}</b> &amp; <b>${fmt(slotB)}</b> (your time)</span></div>`;
}

/* ---------- Queue UI ---------- */
const BADGE = { pending: "PENDING", rendered: "RENDERED", scheduled: "SCHEDULED", cancelled: "CANCELLING", removed: "REMOVED", rejected: "REJECTED" };
function renderQueue() {
  const el = $("queue-list");
  const items = (QUEUE.queue || []).filter(x => x.status !== "removed").slice().reverse();
  if (!items.length) { el.innerHTML = `<div class="tiny muted" style="padding:.4rem 0">No custom Shorts yet — create your first one above.</div>`; return; }
  el.innerHTML = items.map(x => `
    <div class="q-item">
      <div class="q-top">
        <span class="q-ref"><i class="fa-solid fa-book-open" style="color:var(--gold);font-size:.75rem;margin-right:.35rem"></i>${x.display_ref}</span>
        <span class="q-badge ${x.status}">${BADGE[x.status] || x.status}</span>
      </div>
      <div class="q-when"><i class="fa-regular fa-clock"></i> Premieres ${new Date(x.publish_at).toLocaleString([], { weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</div>
      ${x.reason ? `<div class="q-reason">${x.reason}</div>` : ""}
      <div class="q-actions">
        ${x.video_id ? `<a class="q-link" href="https://youtu.be/${x.video_id}" target="_blank" rel="noopener"><i class="fa-brands fa-youtube"></i> watch</a>` : ""}
        ${["pending", "scheduled", "rendered"].includes(x.status) ? `<button data-id="${x.id}" class="q-cancel cancel-btn"><i class="fa-solid fa-xmark"></i> Cancel</button>` : ""}
      </div>
    </div>`).join("");
  el.querySelectorAll(".cancel-btn").forEach(b => b.onclick = () => cancelItem(b.dataset.id));
}

/* ---------- Commit actions ---------- */
async function commitQueue(message) {
  const body = { message, content: b64encode(JSON.stringify(QUEUE, null, 1)), branch: "main" };
  if (QUEUE_SHA) body.sha = QUEUE_SHA;
  const r = await fetch(`${API}/data/custom_queue.json`, {
    method: "PUT",
    headers: { ...hdrs(), "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!r.ok) throw new Error(`Commit failed: ${r.status} ${((await r.json()).message) || ""}`);
  QUEUE_SHA = (await r.json()).content.sha;
}
async function publish() {
  const btn = $("btn-publish");
  btn.disabled = true; btn.textContent = "Publishing…";
  try {
    await loadQueueAndState();      // race safety: re-validate with fresh data
    if (!$("validate-msg").textContent.includes("✔")) {
      alert("Slot became invalid (fresh data). Pick another time.");
    } else {
      const { ref, text } = chosenVerse();
      const when = new Date(`${$("inp-date").value}T${$("inp-time").value}`);
      const item = {
        id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
        display_ref: ref.replace("Psalms ", "Psalm "),
        text,
        explanation: $("inp-expl").value.trim(),
        hook: $("inp-hook").value.trim(),
        publish_at: when.toISOString().replace(/\.\d+Z$/, "Z"),
        status: "pending",
        created: new Date().toISOString()
      };
      QUEUE.queue.push(item);
      await commitQueue(`custom: queue ${item.display_ref} for ${item.publish_at}`);
      $("inp-expl").value = ""; $("inp-hook").value = "";
      alert(`✅ Queued! The bot will render "${item.display_ref}" (voice-over + music + visuals) and premiere it ${when.toLocaleString()}. Track it in the queue below.`);
      renderQueue(); renderToday(); renderSuggestions();
    }
  } catch (e) { alert("Error: " + e.message); }
  btn.textContent = "Publish → schedule";
  validate();
}
async function cancelItem(id) {
  if (!confirm("Cancel this custom Short? If already uploaded it will be deleted from YouTube, and the bot resumes normal service that day.")) return;
  try {
    await loadQueueAndState();
    const x = QUEUE.queue.find(q => q.id === id);
    if (x && x.status !== "removed") {
      x.status = "cancelled";
      await commitQueue(`custom: cancel ${x.display_ref}`);
    }
    renderQueue();
  } catch (e) { alert("Error: " + e.message); }
}

/* ---------- Settings ---------- */
$("btn-settings").onclick = () => { $("inp-token").value = token(); $("modal-settings").classList.remove("hidden"); };
$("btn-close-settings").onclick = () => $("modal-settings").classList.add("hidden");
$("btn-save-token").onclick = async () => {
  localStorage.setItem("gh_token", $("inp-token").value.trim());
  const st = $("token-status");
  st.textContent = "Checking…";
  try {
    await ghGet("data/custom_queue.json");
    st.innerHTML = `<span style="color:var(--green)"><i class="fa-solid fa-circle-check"></i> Token works — you're connected.</span>`;
    loadQueueAndState();
  } catch (e) {
    st.innerHTML = `<span style="color:var(--red)"><i class="fa-solid fa-circle-xmark"></i> ${e.message}</span>`;
  }
};

/* ---------- Wire up ---------- */
$("sel-book").onchange = fillChapters;
$("sel-chapter").onchange = fillVerses;
$("sel-v1").onchange = updatePreview;
$("sel-v2").onchange = updatePreview;
$("inp-expl").oninput = validate;
$("inp-date").onchange = validate;
$("inp-time").onchange = validate;
$("btn-publish").onclick = publish;
$("inp-book-search").oninput = e => { if (BIBLE) { fillBooks(e.target.value.trim()); fillChapters(); } };
const btnRefresh = $("btn-refresh");
if (btnRefresh) btnRefresh.onclick = () => { btnRefresh.firstElementChild.classList.add("fa-spin"); loadQueueAndState().finally(() => setTimeout(() => btnRefresh.firstElementChild.classList.remove("fa-spin"), 600)); };

loadBible().catch(e => { $("verse-preview").classList.remove("hidden"); $("verse-preview").textContent = "Could not load Bible: " + e.message; });
loadQueueAndState();
setInterval(loadQueueAndState, 60000);

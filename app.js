const PLAN_KEY = "ep26-plan-v1";
const TASTE_KEY = "ep26-taste-v1";
const THEME_KEY = "ep26-theme-v1";
const NOTIFY_KEY = "ep26-notify-v1";
const NOTIFIED_KEY = "ep26-notified-v1";
const ALERT_LEAD_MS = 15 * 60 * 1000;
const data = window.EP26;
const $ = (sel) => document.querySelector(sel);
const WALK_MIN = data.walkMins?.min ?? 15;
const WALK_MAX = data.walkMins?.max ?? 20;

const TASTE_ALIASES = {
  "lsd systems": "lcd soundsystem",
  "lsdsystems": "lcd soundsystem",
  "dave clark": "dave clarke",
  "adam bayer": "adam beyer",
  "londong grammar": "london grammar",
};

const TASTE_TAGS = {
  "massive attack": ["electronic", "trip-hop", "dark", "downtempo"],
  "underworld": ["electronic", "techno", "rave", "house"],
  "chemical brothers": ["electronic", "big-beat", "rave", "house"],
  "lcd soundsystem": ["electronic", "dance-punk", "house"],
  "dave clarke": ["electronic", "techno"],
  "adam beyer": ["electronic", "techno", "house"],
  "london grammar": ["electronic", "pop", "alt"],
  "fever ray": ["electronic", "art-pop", "dark"],
};

function loadTaste() {
  const stored = localStorage.getItem(TASTE_KEY);
  if (stored === null) {
    return "Massive Attack, Underworld, Chemical Brothers, LCD Soundsystem, Dave Clarke, Adam Beyer, London Grammar, Fever Ray";
  }
  return stored;
}

const state = {
  day: data.days[1]?.id || data.days[0]?.id,
  query: "",
  kind: "music",
  genre: "electronic",
  stage: "",
  plan: loadPlan(),
  taste: loadTaste(),
  view: "list",
  actId: "",
};

function loadPlan() {
  try {
    const ids = JSON.parse(localStorage.getItem(PLAN_KEY) || "[]");
    return ids.filter((id) => data.acts.some((a) => a.id === id));
  } catch {
    return [];
  }
}

function savePlan() {
  localStorage.setItem(PLAN_KEY, JSON.stringify(state.plan));
  scheduleAlerts();
}

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function toDate(ts) {
  return new Date(ts.replace(" ", "T"));
}

function fmtTime(ts) {
  return ts.slice(11, 16);
}

function actById(id) {
  return data.acts.find((a) => a.id === id);
}

function plannedActs() {
  return state.plan.map(actById).filter(Boolean)
    .sort((a, b) => a.start.localeCompare(b.start) || a.stage.localeCompare(b.stage));
}

function plannedOnDay(day) {
  return plannedActs().filter((a) => a.day === day);
}

function overlaps(a, b) {
  return toDate(a.start) < toDate(b.end) && toDate(b.start) < toDate(a.end);
}

function gapMins(fromAct, toAct) {
  return (toDate(toAct.start) - toDate(fromAct.end)) / 60000;
}

function clashFor(act) {
  const others = plannedOnDay(act.day).filter((p) => p.id !== act.id);
  let overlap = null;
  let miss = null;
  let tight = null;
  let missGap = Infinity;
  let tightGap = Infinity;
  for (const other of others) {
    if (overlaps(act, other)) {
      overlap = { kind: "clash", note: `Overlaps ${other.name}` };
      continue;
    }
    if (act.stage === other.stage) continue;
    const gaps = [gapMins(other, act), gapMins(act, other)].filter((g) => g >= 0);
    if (!gaps.length) continue;
    const g = Math.min(...gaps);
    if (g < WALK_MIN && g < missGap) {
      missGap = g;
      miss = {
        kind: "clash",
        note: `Only ${Math.round(g)} min to ${other.name} (need ${WALK_MIN}–${WALK_MAX})`,
      };
    } else if (g >= WALK_MIN && g < WALK_MAX && g < tightGap) {
      tightGap = g;
      tight = { kind: "tight", note: `${Math.round(g)} min to ${other.name} — tight walk` };
    }
  }
  return overlap || miss || tight;
}

function matchesFilters(act) {
  if (state.day && act.day !== state.day) return false;
  if (state.kind && act.kind !== state.kind) return false;
  if (state.kind === "music" && state.genre && !(act.genres || []).includes(state.genre)) return false;
  if (state.stage && act.stage !== state.stage) return false;
  const q = state.query.trim().toLowerCase();
  if (!q) return true;
  return act.name.toLowerCase().includes(q) || act.stage.toLowerCase().includes(q);
}

function filteredActs() {
  return data.acts.filter(matchesFilters);
}

function stagesForFilters() {
  const seen = new Set();
  const kindActs = data.acts.filter((a) => {
    if (state.day && a.day !== state.day) return false;
    if (state.kind && a.kind !== state.kind) return false;
    if (state.kind === "music" && state.genre && !(a.genres || []).includes(state.genre)) return false;
    return true;
  });
  for (const a of kindActs) seen.add(a.stage);
  return data.stages.filter((s) => seen.has(s));
}

function toggle(id) {
  if (state.plan.includes(id)) {
    state.plan = state.plan.filter((x) => x !== id);
    const notified = loadNotified();
    if (notified.delete(id)) saveNotified(notified);
  } else state.plan = [...state.plan, id];
  savePlan();
  render();
}

function openAct(id) {
  location.hash = `#/act/${encodeURIComponent(id)}`;
}

function closeAct() {
  location.hash = "#/";
}

function parseHash() {
  const m = location.hash.match(/^#\/act\/(.+)$/);
  if (m) {
    state.view = "act";
    state.actId = decodeURIComponent(m[1]);
  } else {
    state.view = "list";
    state.actId = "";
  }
}

function normName(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function parseTaste() {
  return state.taste.split(/[,;\n]+/).map((s) => s.trim()).filter(Boolean);
}

function canonicalTaste(name) {
  const n = normName(name);
  return TASTE_ALIASES[n] || n;
}

function tasteProfile() {
  const tags = new Set(["electronic"]);
  for (const raw of parseTaste()) {
    const key = canonicalTaste(raw);
    for (const t of TASTE_TAGS[key] || ["electronic"]) tags.add(t);
  }
  return tags;
}

function scoreAct(act, profile) {
  if (act.kind !== "music") return 0;
  if (state.plan.includes(act.id)) return 0;
  let score = 0;
  const reasons = [];
  const names = parseTaste().map(canonicalTaste);
  const actName = normName(act.name);
  if (names.some((n) => actName === n || actName.includes(n) || n.includes(actName))) {
    score += 20;
    reasons.push("name match with your list");
  }
  if ((act.genres || []).includes("electronic")) {
    score += 4;
    reasons.push("electronic");
  }
  const tagHits = (act.tags || []).filter((t) => profile.has(t));
  if (tagHits.length) {
    score += Math.min(4, tagHits.length);
    reasons.push(tagHits.slice(0, 2).join(", "));
  }
  const blurb = (act.blurb || "").toLowerCase();
  if (/(techno|underworld|rave|warehouse|chemical|trip-hop)/.test(blurb)) {
    score += 2;
    reasons.push("sounds like your lot");
  }
  return { score, reasons };
}

function suggestions() {
  const profile = tasteProfile();
  return data.acts
    .filter((a) => {
      if (a.day !== state.day || a.kind !== "music") return false;
      if (state.genre && !(a.genres || []).includes(state.genre)) return false;
      return true;
    })
    .map((a) => ({ act: a, ...scoreAct(a, profile) }))
    .filter((x) => x.score >= 4)
    .sort((a, b) => b.score - a.score || a.act.start.localeCompare(b.act.start))
    .slice(0, 8);
}

function wantButton(act) {
  const on = state.plan.includes(act.id);
  return `<button type="button" class="btn" data-state="${on ? "on" : "off"}" data-id="${esc(act.id)}">${on ? "Seeing this" : "I’d like to see"}</button>`;
}

function initials(name) {
  const clean = String(name || "")
    .replace(/^the\s+/i, "")
    .replace(/[^a-z0-9\s]/gi, " ")
    .trim();
  const parts = clean.split(/\s+/).filter(Boolean);
  if (!parts.length) return "EP";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

function mediaMarkup(act, className, src) {
  const label = initials(act.name);
  if (!src) {
    return `<div class="${className}" data-placeholder="true" aria-hidden="true">${esc(label)}</div>`;
  }
  return `<img class="${className}" src="${esc(src)}" alt="" loading="lazy" data-fallback="${esc(label)}">`;
}

function bindMediaFallbacks(root) {
  root.querySelectorAll("img.item-card__media, img.act-page__media").forEach((img) => {
    img.addEventListener(
      "error",
      () => {
        const div = document.createElement("div");
        div.className = img.className;
        div.dataset.placeholder = "true";
        div.setAttribute("aria-hidden", "true");
        div.textContent = img.dataset.fallback || "EP";
        img.replaceWith(div);
      },
      { once: true }
    );
  });
}

function actCard(act, extra = "") {
  const picked = state.plan.includes(act.id);
  const clash = picked ? clashFor(act) : null;
  const genres = (act.genres || [])
    .map((g) => `<span class="chip" data-genre="${esc(g)}">${esc(g)}</span>`)
    .join("");
  const status = clash ? ` data-status="${esc(clash.kind)}"` : "";
  const note = clash
    ? `<p class="item-card__note" data-status="${esc(clash.kind)}">${esc(clash.note)}</p>`
    : "";
  return `
    <article class="item-card"${status}>
      <button type="button" class="item-card__title" data-open="${esc(act.id)}">${esc(act.name)}</button>
      <p class="item-card__meta">${fmtTime(act.start)}–${fmtTime(act.end)} · ${esc(act.stage)}</p>
      <div class="item-card__tags chips">${genres}</div>
      ${note}
      ${extra ? `<p class="item-card__note">${extra}</p>` : ""}
      ${mediaMarkup(act, "item-card__media", act.thumb || act.image)}
      <button type="button" class="btn item-card__action" data-state="${picked ? "on" : "off"}" title="I’d like to see" data-id="${esc(act.id)}">${picked ? "★" : "☆"}</button>
    </article>`;
}

function renderHeader() {
  const music = data.acts.filter((a) => a.kind === "music").length;
  const elec = data.acts.filter((a) => (a.genres || []).includes("electronic")).length;
  $("#updated").textContent =
    `Updated ${data.modified} · ${data.acts.length} events · ${music} music · ${elec} tagged electronic`;
}

function renderDays() {
  const box = $("#days");
  box.innerHTML = "";
  for (const day of data.days) {
    const btn = document.createElement("button");
    btn.textContent = day.label;
    btn.className = "btn";
    btn.setAttribute("data-state", day.id === state.day ? "selected" : "off");
    btn.setAttribute("aria-pressed", day.id === state.day ? "true" : "false");
    btn.onclick = () => {
      state.day = day.id;
      render();
    };
    box.appendChild(btn);
  }
}

function fillSelect(sel, items, current, blank) {
  sel.innerHTML = "";
  if (blank != null) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = blank;
    sel.appendChild(opt);
  }
  for (const item of items) {
    const opt = document.createElement("option");
    opt.value = item.id ?? item;
    opt.textContent = item.label ?? item;
    if ((item.id ?? item) === current) opt.selected = true;
    sel.appendChild(opt);
  }
}

function renderFilters() {
  fillSelect($("#kind"), [{ id: "", label: "All event types" }, ...data.kinds], state.kind);
  const genreHidden = state.kind !== "music";
  $("#genre-field").classList.toggle("u-hidden", genreHidden);
  if (!genreHidden) {
    fillSelect($("#genre"), [{ id: "", label: "All music" }, ...data.genreOptions], state.genre);
  }
  const stages = stagesForFilters();
  fillSelect($("#stage"), stages, state.stage, "All stages");
  if (state.stage && !stages.includes(state.stage)) state.stage = "";
}

function bindCardClicks(root) {
  root.querySelectorAll("[data-id]").forEach((btn) => {
    btn.onclick = (e) => {
      e.stopPropagation();
      toggle(btn.dataset.id);
    };
  });
  root.querySelectorAll("[data-open]").forEach((btn) => {
    btn.onclick = () => openAct(btn.dataset.open);
  });
  bindMediaFallbacks(root);
}

function renderSuggest() {
  const items = suggestions();
  $("#suggest-count").textContent = items.length ? `${items.length}` : "";
  const box = $("#suggest");
  if (!parseTaste().length) {
    box.innerHTML = '<p class="empty">Add favourite artists above to get a shortlist for this day.</p>';
    return;
  }
  if (!items.length) {
    box.innerHTML = '<p class="empty">No strong matches on this day with the current filters.</p>';
    return;
  }
  box.innerHTML = items.map((x) =>
    actCard(x.act, `Why: ${esc(x.reasons.join(" · "))}`)
  ).join("");
  bindCardClicks(box);
}

function renderList() {
  const acts = filteredActs();
  $("#count").textContent = `${acts.length}`;
  const list = $("#list");
  if (!acts.length) {
    list.innerHTML = '<p class="empty">Nothing matches. Try All music, or another day.</p>';
    return;
  }
  list.innerHTML = acts.map((a) => actCard(a)).join("");
  bindCardClicks(list);
}

function renderPlan() {
  const all = plannedActs();
  $("#plan-stats").textContent = all.length
    ? `${all.length} picked · split by day · ${WALK_MIN}–${WALK_MAX} min walks`
    : "Nothing picked yet.";
  const box = $("#plan");
  if (!all.length) {
    box.innerHTML = '<p class="empty">Star a set, or open the artist and tap I’d like to see.</p>';
    return;
  }
  const days = data.days.filter((d) => all.some((a) => a.day === d.id));
  let html = "";
  for (const day of days) {
    const acts = plannedOnDay(day.id);
    html += `<div class="day-head"><h3 class="day-head__title">${esc(day.label)} route</h3><span class="day-head__meta">${acts.length} stops</span></div>`;
    let prev = null;
    for (const act of acts) {
      const clash = clashFor(act);
      if (prev && prev.stage !== act.stage) {
        const g = Math.round(gapMins(prev, act));
        const walkNote = Number.isFinite(g)
          ? (g < WALK_MIN
            ? `Only ${g} min to walk — likely miss`
            : g < WALK_MAX
              ? `${g} min walk — tight`
              : `${g} min gap, ~${WALK_MIN}–${WALK_MAX} min walk`)
          : "";
        html += `<p class="walk-note">↓ ${esc(walkNote)}</p>`;
      }
      html += `
        <article class="item-card"${clash ? ` data-status="${esc(clash.kind)}"` : ""}>
          <h3 class="item-card__title">${esc(act.name)}</h3>
          <p class="item-card__meta">${fmtTime(act.start)}–${fmtTime(act.end)} · ${esc(act.stage)}</p>
          ${clash ? `<p class="item-card__note" data-status="${esc(clash.kind)}">${esc(clash.note)}</p>` : ""}
          <button type="button" class="btn item-card__action" data-id="${esc(act.id)}">Remove</button>
        </article>`;
      prev = act;
    }
  }
  box.innerHTML = html;
  bindCardClicks(box);
}

function renderAct() {
  const act = actById(state.actId);
  const page = $("#act-detail");
  if (!act) {
    page.innerHTML = '<p class="empty">Set not found.</p>';
    return;
  }
  const others = data.acts.filter((a) => a.name === act.name && a.id !== act.id);
  const clash = state.plan.includes(act.id) ? clashFor(act) : null;
  const photo = act.image || act.thumb;
  page.innerHTML = `
    <p class="act-page__meta">${esc(act.dayLabel)} ${fmtTime(act.start)}–${fmtTime(act.end)} · ${esc(act.stage)}</p>
    <h2 class="act-page__title">${esc(act.name)}</h2>
    <div class="chips">${(act.genres || []).map((g) => `<span class="chip" data-genre="${esc(g)}">${esc(g)}</span>`).join("")}
      <span class="chip">${esc(act.kind)}</span></div>
    <p>${wantButton(act)}</p>
    ${clash ? `<p class="act-page__note" data-status="${esc(clash.kind)}">${esc(clash.note)}</p>` : ""}
    <div class="act-page__body">
      <div class="act-page__copy">
        ${act.bio ? `<div class="prose"><div class="prose__label">From Discogs</div>${esc(act.bio)}</div>` : ""}
        ${act.blurb ? `<div class="prose">${esc(act.blurb)}</div>` : (!act.bio ? "<p class='empty'>No notes for this set.</p>" : "")}
      </div>
      ${mediaMarkup(act, "act-page__media", photo)}
    </div>
    ${others.length ? `<h2 class="lineup__heading">Also playing</h2>${others.map((a) => actCard(a)).join("")}` : ""}
  `;
  bindCardClicks(page);
}

function icsEscape(value) {
  return String(value ?? "")
    .replaceAll("\\", "\\\\")
    .replaceAll(";", "\\;")
    .replaceAll(",", "\\,")
    .replaceAll("\r\n", "\\n")
    .replaceAll("\n", "\\n");
}

function icsStamp(ts) {
  const d = new Date(`${ts.replace(" ", "T")}:00+01:00`);
  if (Number.isNaN(d.getTime())) return "";
  return d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}

function icsFold(line) {
  const parts = [];
  let rest = line;
  while (rest.length > 75) {
    parts.push(rest.slice(0, 75));
    rest = ` ${rest.slice(75)}`;
  }
  parts.push(rest);
  return parts.join("\r\n");
}

function buildIcs(acts) {
  const now = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//EP26 planner//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "X-WR-CALNAME:Electric Picnic 2026",
    "X-WR-TIMEZONE:Europe/Dublin",
  ];
  for (const act of acts) {
    const start = icsStamp(act.start);
    const end = icsStamp(act.end);
    if (!start || !end) continue;
    lines.push(
      "BEGIN:VEVENT",
      `UID:ep26-${act.id}@sashareds.github.io`,
      `DTSTAMP:${now}`,
      `DTSTART:${start}`,
      `DTEND:${end}`,
      `SUMMARY:${icsEscape(act.name)}`,
      `LOCATION:${icsEscape(`${act.stage}, Stradbally Hall`)}`,
      `DESCRIPTION:${icsEscape(`${act.dayLabel} · ${act.stage}`)}`,
      "BEGIN:VALARM",
      "ACTION:DISPLAY",
      "DESCRIPTION:EP26 in 15 minutes",
      "TRIGGER:-PT15M",
      "END:VALARM",
      "END:VEVENT"
    );
  }
  lines.push("END:VCALENDAR");
  return `${lines.map(icsFold).join("\r\n")}\r\n`;
}

function actStartMs(act) {
  const d = new Date(`${act.start.replace(" ", "T")}:00+01:00`);
  return d.getTime();
}

function loadNotified() {
  try {
    return new Set(JSON.parse(localStorage.getItem(NOTIFIED_KEY) || "[]"));
  } catch {
    return new Set();
  }
}

function saveNotified(set) {
  localStorage.setItem(NOTIFIED_KEY, JSON.stringify([...set]));
}

let alertTimers = [];

function clearAlertTimers() {
  for (const id of alertTimers) clearTimeout(id);
  alertTimers = [];
}

function notificationsOn() {
  return (
    "Notification" in window &&
    localStorage.getItem(NOTIFY_KEY) === "1" &&
    Notification.permission === "granted"
  );
}

async function fireAlert(act) {
  if (!notificationsOn()) return;
  const notified = loadNotified();
  if (notified.has(act.id)) return;
  notified.add(act.id);
  saveNotified(notified);
  const title = act.name;
  const options = {
    body: `${act.stage} · starts ${fmtTime(act.start)}`,
    tag: `ep26-${act.id}`,
    icon: "./img/icon-192.png",
    badge: "./img/icon-192.png",
    data: { url: `./#/act/${encodeURIComponent(act.id)}` },
  };
  try {
    const reg = await navigator.serviceWorker?.ready;
    if (reg?.showNotification) {
      await reg.showNotification(title, options);
      return;
    }
  } catch {
    /* fall through */
  }
  new Notification(title, options);
}

function scheduleAlerts() {
  clearAlertTimers();
  if (!notificationsOn()) return;
  const now = Date.now();
  for (const act of plannedActs()) {
    const start = actStartMs(act);
    if (!Number.isFinite(start) || start <= now) continue;
    const delay = start - ALERT_LEAD_MS - now;
    if (delay <= 0) {
      fireAlert(act);
      continue;
    }
    if (delay > 2147483647) continue;
    alertTimers.push(setTimeout(() => fireAlert(act), delay));
  }
}

function syncNotifyUi() {
  const btn = $("#notify-toggle");
  const hint = $("#notify-hint");
  if (!btn) return;
  const supported = "Notification" in window;
  const on = notificationsOn();
  btn.disabled = !supported;
  btn.setAttribute("data-state", on ? "on" : "off");
  btn.textContent = on ? "Alerts on · 15 min before" : "Notify 15 min before";
  if (!hint) return;
  if (!supported) {
    hint.textContent = "This browser cannot show notifications. Add to calendar once instead.";
    return;
  }
  if (Notification.permission === "denied") {
    hint.textContent = "Notifications are blocked. Enable them in Settings, or Add to calendar once.";
    return;
  }
  hint.textContent = on
    ? "15 minutes before each starred set. On iPhone this needs the Home Screen app; iOS will not wake a killed PWA. For lock-screen alerts, Add to calendar once."
    : "PWA alerts 15 minutes before starred sets. On iPhone, add this page to the Home Screen first.";
}

async function toggleNotify() {
  if (!("Notification" in window)) {
    alert("This browser cannot show notifications.");
    return;
  }
  if (localStorage.getItem(NOTIFY_KEY) === "1") {
    localStorage.setItem(NOTIFY_KEY, "0");
    clearAlertTimers();
    syncNotifyUi();
    return;
  }
  let perm = Notification.permission;
  if (perm === "default") perm = await Notification.requestPermission();
  if (perm !== "granted") {
    alert("Allow notifications for this app in Settings. On iPhone, add it to the Home Screen first.");
    syncNotifyUi();
    return;
  }
  localStorage.setItem(NOTIFY_KEY, "1");
  scheduleAlerts();
  syncNotifyUi();
}

async function exportIcs() {
  const acts = plannedActs();
  const btn = $("#cal-export");
  if (!acts.length) {
    alert("Star some sets first.");
    return;
  }
  const file = new File([buildIcs(acts)], "ep26-route.ics", { type: "text/calendar" });
  try {
    if (navigator.canShare?.({ files: [file] })) {
      await navigator.share({ files: [file], title: "EP26 route" });
      btn.textContent = "Shared";
      setTimeout(() => (btn.textContent = "Add to calendar"), 1200);
      return;
    }
  } catch (err) {
    if (err && err.name === "AbortError") return;
  }
  const url = URL.createObjectURL(file);
  const link = document.createElement("a");
  link.href = url;
  link.download = file.name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
  btn.textContent = "Downloaded";
  setTimeout(() => (btn.textContent = "Add to calendar"), 1200);
}

function exportPlan() {
  const lines = [];
  for (const day of data.days) {
    const acts = plannedOnDay(day.id);
    if (!acts.length) continue;
    lines.push(day.label.toUpperCase());
    let prev = null;
    for (const a of acts) {
      if (prev && prev.stage !== a.stage) {
        const g = Math.round(gapMins(prev, a));
        lines.push(`  walk ~${WALK_MIN}–${WALK_MAX} min (${g} min gap)`);
      }
      lines.push(`  ${fmtTime(a.start)}–${fmtTime(a.end)}  ${a.name}  (${a.stage})`);
      prev = a;
    }
    lines.push("");
  }
  const text = lines.join("\n") || "No sets picked.";
  navigator.clipboard.writeText(text).then(
    () => {
      $("#export").textContent = "Copied";
      setTimeout(() => ($("#export").textContent = "Copy timetable"), 1200);
    },
    () => alert(text)
  );
}

function applyTheme(mode) {
  localStorage.setItem(THEME_KEY, mode);
  if (mode === "system") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.dataset.theme = mode;
  document.querySelectorAll(".theme-switch__btn").forEach((btn) => {
    const on = btn.dataset.theme === mode;
    btn.setAttribute("aria-pressed", on ? "true" : "false");
    btn.setAttribute("data-state", on ? "selected" : "off");
  });
}

function render() {
  parseHash();
  $("#list-view").classList.toggle("u-hidden", state.view !== "list");
  $("#act-view").classList.toggle("u-hidden", state.view !== "act");
  renderHeader();
  renderDays();
  renderFilters();
  if (state.view === "act") renderAct();
  else {
    $("#taste").value = state.taste;
    renderSuggest();
    renderList();
    renderPlan();
  }
}

$("#search").addEventListener("input", (e) => {
  state.query = e.target.value;
  renderList();
});
$("#kind").addEventListener("change", (e) => {
  state.kind = e.target.value;
  if (state.kind !== "music") state.genre = "";
  if (state.kind === "music" && !state.genre) state.genre = "electronic";
  state.stage = "";
  render();
});
$("#genre").addEventListener("change", (e) => {
  state.genre = e.target.value;
  state.stage = "";
  render();
});
$("#stage").addEventListener("change", (e) => {
  state.stage = e.target.value;
  renderList();
});
$("#taste").addEventListener("input", (e) => {
  state.taste = e.target.value;
  localStorage.setItem(TASTE_KEY, state.taste);
  renderSuggest();
});
$("#export").addEventListener("click", exportPlan);
$("#cal-export").addEventListener("click", exportIcs);
$("#notify-toggle").addEventListener("click", toggleNotify);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") scheduleAlerts();
});
$("#back").addEventListener("click", closeAct);
window.addEventListener("hashchange", render);
document.querySelectorAll(".theme-switch__btn").forEach((btn) => {
  btn.addEventListener("click", () => applyTheme(btn.dataset.theme));
});
applyTheme(localStorage.getItem(THEME_KEY) || "system");

if ("serviceWorker" in navigator && location.protocol.startsWith("http")) {
  navigator.serviceWorker.register("./sw.js").then(() => scheduleAlerts());
} else {
  scheduleAlerts();
}
syncNotifyUi();

render();

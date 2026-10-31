"use strict";

const TEXT = {
  en: {
    newChat: "New chat", send: "Send", attach: "Photo", placeholder: "Write a message...",
    admin: "Admin", back: "Back to chat", actAs: "Act as", myself: "Myself",
    actingAs: (n) => `You are acting as ${n}. Conversations belong to ${n}.`,
    notReady: "The assistant is not set up yet. An admin has to configure the agent environment.",
    notice: "Conversations can be read by the admin.",
    queued: (n) => `Waiting in the queue (position ${n})...`, thinking: "Working...",
    busy: "A reply is being generated...", toolLimit: "Tool limit reached; the reply was stopped.",
    empty: "The model returned an empty reply.", commitDone: "Saved", commitFailed: "Saving failed",
    pushed: "pushed", notPushed: "not pushed", tool: "Tool", result: "Result",
    settings: "Agent environment", repoUrl: "Repository URL (https)", branch: "Branch",
    token: "Access token", tokenSet: "A token is set. Leave empty to keep it.", tokenNone: "No token set.",
    allowCommits: "Commit Permission: the assistant may change files; each changed turn becomes a commit",
    allowPush: "Push Permission: publish commits to the remote automatically",
    aliases: "Aliases", save: "Save", saved: "Saved", sync: "Sync now", push: "Push now",
    status: "Status", head: "Latest commit", ahead: "Unpushed commits", behind: "Commits behind",
    pending: "Uncommitted changes", diverged: "Diverged from the remote", lastSync: "Last sync",
    lastError: "Last error", never: "never", yes: "yes", no: "no",
    ollama: "Ollama", model: "Model", reachable: "reachable", exists: "installed", tools: "tool calling",
    vision: "vision", unknown: "unknown", rules: "Rules from the repository (read-only)",
    hidden: "Hidden", readonly: "Read-only", enabledTools: "Enabled tools", none: "none", warnings: "Warnings",
    queue: "Queue", running: "running", waiting: "waiting", diagramError: "The diagram could not be rendered.",
    authMethod: "Access to the repository", authToken: "Access token", authGh: "GitHub CLI sign-in",
    ghLogin: "Sign in with GitHub", ghLogout: "Sign out", ghLoggedIn: (n) => `Signed in to GitHub as ${n}.`,
    ghStep1: "Open", ghStep2: "and enter this code:", ghMissing: "The GitHub CLI is not installed in this add-on.",
    ghScopeNote: "GitHub CLI sign-in grants access to all repositories of that GitHub account. For a single repository use a fine-grained access token instead.",
  },
  de: {
    newChat: "Neuer Chat", send: "Senden", attach: "Foto", placeholder: "Nachricht schreiben...",
    admin: "Admin", back: "Zurück zum Chat", actAs: "Handeln als", myself: "Ich selbst",
    actingAs: (n) => `Du handelst als ${n}. Die Unterhaltungen gehören ${n}.`,
    notReady: "Der Assistent ist noch nicht eingerichtet. Ein Admin muss die Agent-Umgebung konfigurieren.",
    notice: "Unterhaltungen können vom Admin gelesen werden.",
    queued: (n) => `In der Warteschlange (Platz ${n})...`, thinking: "Arbeitet...",
    busy: "Eine Antwort wird erzeugt...", toolLimit: "Werkzeuglimit erreicht; die Antwort wurde abgebrochen.",
    empty: "Das Modell hat eine leere Antwort geliefert.", commitDone: "Gespeichert", commitFailed: "Speichern fehlgeschlagen",
    pushed: "veröffentlicht", notPushed: "nicht veröffentlicht", tool: "Werkzeug", result: "Ergebnis",
    settings: "Agent-Umgebung", repoUrl: "Repository-URL (https)", branch: "Branch",
    token: "Zugriffstoken", tokenSet: "Ein Token ist gesetzt. Leer lassen, um es zu behalten.", tokenNone: "Kein Token gesetzt.",
    allowCommits: "Commit-Erlaubnis: der Assistent darf Dateien ändern; jeder Durchgang mit Änderungen wird ein Commit",
    allowPush: "Push-Erlaubnis: Commits automatisch ins Remote veröffentlichen",
    aliases: "Aliasnamen", save: "Speichern", saved: "Gespeichert", sync: "Jetzt synchronisieren", push: "Jetzt pushen",
    status: "Status", head: "Letzter Commit", ahead: "Unveröffentlichte Commits", behind: "Commits dahinter",
    pending: "Nicht gespeicherte Änderungen", diverged: "Vom Remote abgewichen", lastSync: "Letzte Synchronisation",
    lastError: "Letzter Fehler", never: "nie", yes: "ja", no: "nein",
    ollama: "Ollama", model: "Modell", reachable: "erreichbar", exists: "installiert", tools: "Werkzeugaufrufe",
    vision: "Bilder", unknown: "unbekannt", rules: "Regeln aus dem Repository (nur lesbar)",
    hidden: "Versteckt", readonly: "Schreibgeschützt", enabledTools: "Aktive Werkzeuge", none: "keine", warnings: "Warnungen",
    queue: "Warteschlange", running: "läuft", waiting: "wartet", diagramError: "Das Diagramm konnte nicht dargestellt werden.",
    authMethod: "Zugriff auf das Repository", authToken: "Zugriffstoken", authGh: "Anmeldung mit der GitHub CLI",
    ghLogin: "Bei GitHub anmelden", ghLogout: "Abmelden", ghLoggedIn: (n) => `Bei GitHub angemeldet als ${n}.`,
    ghStep1: "Öffne", ghStep2: "und gib diesen Code ein:", ghMissing: "Die GitHub CLI ist in diesem Add-on nicht installiert.",
    ghScopeNote: "Die Anmeldung mit der GitHub CLI gibt Zugriff auf alle Repositories dieses GitHub-Kontos. Für ein einzelnes Repository nimm stattdessen ein fein abgestuftes Zugriffstoken.",
  },
};

let lang = localStorage.getItem("fa-lang") || ((navigator.language || "en").startsWith("de") ? "de" : "en");
const t = (key, ...args) => {
  const v = TEXT[lang][key];
  return typeof v === "function" ? v(...args) : v;
};

let me = null;
let convs = [];
let current = null;
let actAs = sessionStorage.getItem("fa-act-as") || "";
let sending = false;
let pollTimer = null;
const appEl = document.getElementById("app");

// --- helpers ---------------------------------------------------------------

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) el.append(kid && kid.nodeType ? kid : document.createTextNode(kid == null || kid === false ? "" : kid));
  return el;
}

async function api(path, opts = {}) {
  const headers = { "X-Requested-With": "family-assist" };
  if (actAs) headers["X-Act-As"] = actAs;
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch("api/" + path, {
    method: opts.method || "GET", headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const d = (await res.json()).detail;
      msg = typeof d === "string" ? d : JSON.stringify(d);
    } catch (e) { /* keep status text */ }
    throw new Error(msg);
  }
  return res;
}

// --- safe Markdown (escape first, then format) ------------------------------

const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");

// Dollar math follows the pandoc rules so that prices like "$5 and $6" stay text.
const MATH_RE = /\$\$([\s\S]+?)\$\$|\\\(([\s\S]+?)\\\)|\\\[([\s\S]+?)\\\]|\$(?!\s)((?:\\.|[^$\\\n])+?)(?<!\s)\$(?!\d)/g;

function formatText(part) {
  let s = esc(part);
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>");
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  return s;
}

function inline(raw) {
  return raw.split(/(`[^`]+`)/).map((part) => {
    if (part.length > 1 && part.startsWith("`") && part.endsWith("`")) return "<code>" + esc(part.slice(1, -1)) + "</code>";
    let out = "";
    let last = 0;
    for (const m of part.matchAll(MATH_RE)) {
      const display = m[1] !== undefined || m[3] !== undefined;
      const tex = (m[1] ?? m[2] ?? m[3] ?? m[4]).trim();
      out += formatText(part.slice(last, m.index));
      out += `<span class="math" data-tex="${esc(tex)}"${display ? ' data-display="1"' : ""}>${esc(m[0])}</span>`;
      last = m.index + m[0].length;
    }
    return out + formatText(part.slice(last));
  }).join("");
}

function renderMarkdown(src) {
  const lines = src.replace(/\r\n/g, "\n").split("\n");
  const out = [];
  let i = 0;
  const isTableSep = (l) => /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/.test(l);
  const cells = (l) => l.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
  while (i < lines.length) {
    const line = lines[i];
    if (/^```/.test(line)) {
      const lang = line.slice(3).trim().toLowerCase();
      const code = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) code.push(lines[i++]);
      i++;
      const src = code.join("\n");
      if (lang === "mermaid") out.push(`<div class="mermaid-block" data-src="${esc(src)}"><pre><code>${esc(src)}</code></pre></div>`);
      else out.push("<pre><code>" + esc(src) + "</code></pre>");
    } else if (/^\s*(\$\$|\\\[)/.test(line)) {
      const open = line.trim().startsWith("$$") ? "$$" : "\\[";
      const close = open === "$$" ? "$$" : "\\]";
      const first = line.trim().slice(open.length);
      const buf = [];
      let tail = "";
      let end = first.indexOf(close);
      i++;
      if (end >= 0) {
        buf.push(first.slice(0, end));
        tail = first.slice(end + close.length);
      } else {
        if (first) buf.push(first);
        while (i < lines.length) {
          end = lines[i].indexOf(close);
          if (end >= 0) {
            buf.push(lines[i].slice(0, end));
            tail = lines[i].slice(end + close.length);
            i++;
            break;
          }
          buf.push(lines[i++]);
        }
      }
      const tex = buf.join("\n").trim();
      out.push(`<div class="math-block" data-tex="${esc(tex)}">${esc(open + tex + close)}</div>`);
      if (tail.trim()) out.push("<p>" + inline(tail) + "</p>");
    } else if (/^#{1,4}\s/.test(line)) {
      const level = line.match(/^#+/)[0].length;
      out.push(`<h${level + 1}>${inline(line.replace(/^#+\s*/, ""))}</h${level + 1}>`);
      i++;
    } else if (/^\s*\|/.test(line) && i + 1 < lines.length && isTableSep(lines[i + 1])) {
      const head = cells(line);
      i += 2;
      const rows = [];
      while (i < lines.length && /^\s*\|/.test(lines[i])) rows.push(cells(lines[i++]));
      out.push("<table><thead><tr>" + head.map((c) => `<th>${inline(c)}</th>`).join("") + "</tr></thead><tbody>" +
        rows.map((r) => "<tr>" + r.map((c) => `<td>${inline(c)}</td>`).join("") + "</tr>").join("") + "</tbody></table>");
    } else if (/^\s*([-*]|\d+\.)\s+/.test(line)) {
      const ordered = /^\s*\d+\./.test(line);
      const items = [];
      while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) items.push(lines[i++].replace(/^\s*([-*]|\d+\.)\s+/, ""));
      const tag = ordered ? "ol" : "ul";
      out.push(`<${tag}>` + items.map((x) => `<li>${inline(x)}</li>`).join("") + `</${tag}>`);
    } else if (/^>\s?/.test(line)) {
      const quote = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) quote.push(lines[i++].replace(/^>\s?/, ""));
      out.push("<blockquote>" + inline(quote.join(" ")) + "</blockquote>");
    } else if (!line.trim()) {
      i++;
    } else {
      const para = [];
      while (i < lines.length && lines[i].trim() && !/^(```|#{1,4}\s|>|\s*\$\$|\s*\\\[|\s*([-*]|\d+\.)\s+)/.test(lines[i])) para.push(lines[i++]);
      if (!para.length) para.push(lines[i++]);
      out.push("<p>" + para.map(inline).join("<br>") + "</p>");
    }
  }
  return out.join("");
}

// --- math and diagrams (vendored KaTeX and Mermaid, loaded on demand) ----------

const scripts = new Map();
function loadScript(src) {
  if (!scripts.has(src)) {
    scripts.set(src, new Promise((resolve, reject) => {
      const el = document.createElement("script");
      el.src = src;
      el.onload = resolve;
      el.onerror = () => { scripts.delete(src); reject(new Error(src)); };
      document.head.append(el);
    }));
  }
  return scripts.get(src);
}

let mermaidReady = false;
let mermaidQueue = Promise.resolve();
let mermaidSeq = 0;

// Diagrams are shown as <img> so that nothing inside the SVG can run or restyle the page.
function renderDiagram(el) {
  if (el.dataset.rendered) return;
  el.dataset.rendered = "1";
  mermaidQueue = mermaidQueue.then(async () => {
    const id = "fa-mermaid-" + (++mermaidSeq);
    try {
      await loadScript("static/vendor/mermaid/mermaid.min.js");
      if (!mermaidReady) {
        const dark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
        mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: dark ? "dark" : "default",
          htmlLabels: false, flowchart: { htmlLabels: false }, fontFamily: "sans-serif", maxTextSize: 20000 });
        mermaidReady = true;
      }
      const { svg } = await mermaid.render(id, el.dataset.src);
      const size = svg.match(/viewBox="[-\d.]+ [-\d.]+ ([\d.]+) ([\d.]+)"/);
      const img = h("img", { class: "diagram", alt: "diagram",
        src: "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg.replace(/style="max-width:[^"]*"/, "")) });
      if (size) { img.setAttribute("width", Math.ceil(size[1])); img.setAttribute("height", Math.ceil(size[2])); }
      img.addEventListener("error", () => el.append(h("div", { class: "meta err" }, t("diagramError"))));
      el.replaceChildren(img);
    } catch (e) {
      el.append(h("div", { class: "meta err" }, t("diagramError")));
    } finally {
      const leftover = document.getElementById("d" + id);
      if (leftover) leftover.remove();
    }
  });
}

async function typeset(root, withDiagrams) {
  const formulas = root.querySelectorAll(".math, .math-block");
  if (formulas.length) {
    try {
      await loadScript("static/vendor/katex/katex.min.js");
      for (const el of formulas) {
        const display = el.classList.contains("math-block") || el.dataset.display === "1";
        try {
          katex.render(el.dataset.tex, el, { displayMode: display, throwOnError: false, trust: false, strict: "ignore", maxSize: 50 });
        } catch (e) { /* keep the source text */ }
      }
    } catch (e) { /* keep the source text */ }
  }
  if (withDiagrams) root.querySelectorAll(".mermaid-block").forEach(renderDiagram);
}

function setMarkdown(el, text, final) {
  el.innerHTML = renderMarkdown(text);
  typeset(el, final);
}

// --- chat view ---------------------------------------------------------------

function toolBlock(entry) {
  const args = Object.entries(entry.args || {}).map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`).join("\n");
  return h("details", { class: "tool" },
    h("summary", { class: entry.ok ? "" : "err" }, `${t("tool")}: ${entry.name} ${entry.args && entry.args.path !== undefined ? entry.args.path : ""}`),
    h("pre", {}, args + "\n--- " + t("result") + " ---\n" + entry.result));
}

function commitLine(c) {
  if (!c) return null;
  if (c.error) return h("div", { class: "meta err" }, `${c.commit ? t("commitDone") : t("commitFailed")}: ${c.error}`);
  if (!c.commit) return null;
  return h("div", { class: "meta" }, `${t("commitDone")}: ${c.commit} ${c.message}` + (c.pushed === undefined ? "" : ` (${c.pushed ? t("pushed") : t("notPushed")})`));
}

function messageEl(m) {
  const el = h("div", { class: "msg " + m.role });
  if (m.role === "user") {
    el.append(h("div", {}, m.content));
    for (const src of m.images || []) el.append(h("img", { class: "thumb", src }));
    return el;
  }
  for (const entry of m.tools || []) el.append(toolBlock(entry));
  const body = h("div", {});
  setMarkdown(body, m.content || "", true);
  el.append(body);
  if (m.notice) el.append(h("div", { class: "meta warn" }, m.notice === "tool_limit" ? t("toolLimit") : t("empty")));
  if (m.error) el.append(h("div", { class: "err" }, m.error));
  const c = commitLine(m.commit);
  if (c) el.append(c);
  return el;
}

function renderMessages(box) {
  box.replaceChildren(...(current ? current.messages.map(messageEl) : []));
  box.scrollTop = box.scrollHeight;
}

async function sendMessage(text, files, box, setStatus, onDone) {
  const images = await Promise.all(files.map(shrinkImage));
  const live = h("div", { class: "msg assistant" });
  const body = h("div", {});
  live.append(body);
  box.append(messageEl({ role: "user", content: text, images }), live);
  box.scrollTop = box.scrollHeight;
  let raw = "";
  const handle = (ev) => {
    if (ev.type === "queued") setStatus(t("queued", ev.position));
    else if (ev.type === "start") setStatus(t("thinking"));
    else if (ev.type === "token") { raw += ev.text; setMarkdown(body, raw, false); }
    else if (ev.type === "tool") live.insertBefore(toolBlock(ev), body);
    else if (ev.type === "notice") live.append(h("div", { class: "meta warn" }, ev.text === "tool_limit" ? t("toolLimit") : t("empty")));
    else if (ev.type === "error") live.append(h("div", { class: "err" }, ev.text));
    else if (ev.type === "commit") { const c = commitLine(ev); if (c) live.append(c); }
    box.scrollTop = box.scrollHeight;
  };
  try {
    const res = await api(`conversations/${current.id}/messages`, { method: "POST", body: { text, images } });
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const chunk = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const line = chunk.split("\n").find((l) => l.startsWith("data: "));
        if (line) handle(JSON.parse(line.slice(6)));
      }
    }
  } catch (e) {
    live.append(h("div", { class: "err" }, e.message));
  }
  onDone();
}

function shrinkImage(file) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      const scale = Math.min(1, 1280 / Math.max(img.width, img.height));
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(img.width * scale);
      canvas.height = Math.round(img.height * scale);
      canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      resolve(canvas.toDataURL("image/jpeg", 0.85));
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("image")); };
    img.src = url;
  });
}

function chatView() {
  const box = h("div", { class: "messages" });
  const status = h("div", { class: "meta" });
  const input = h("textarea", { placeholder: t("placeholder"), rows: "2" });
  const fileInput = h("input", { type: "file", accept: "image/*", multiple: true, hidden: true });
  const previews = h("div", { class: "previews" });
  let files = [];
  const sendBtn = h("button", { type: "button" }, t("send"));
  const attachBtn = h("button", { type: "button", class: "secondary" }, t("attach"));

  const setBusy = (busy) => { sendBtn.disabled = busy || !me.ready; input.disabled = busy; };
  const refresh = async () => {
    await loadConvs();
    current = await (await api(`conversations/${current.id}`)).json();
    renderMessages(box);
    const side = document.querySelector("aside");
    if (side) side.replaceWith(sidebar());
    status.textContent = "";
    files = [];
    previews.replaceChildren();
    sending = false;
    setBusy(false);
  };

  fileInput.addEventListener("change", () => {
    files = [...fileInput.files].slice(0, 4);
    previews.replaceChildren(...files.map((f) => h("img", { src: URL.createObjectURL(f) })));
  });
  attachBtn.addEventListener("click", () => fileInput.click());
  sendBtn.addEventListener("click", async () => {
    const text = input.value.trim();
    if (!text || sending) return;
    if (!current) await newConversation();
    sending = true;
    setBusy(true);
    input.value = "";
    const toSend = files;
    await sendMessage(text, toSend, box, (s) => { status.textContent = s; }, refresh);
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendBtn.click(); }
  });

  if (current) renderMessages(box);
  if (!me.ready) status.textContent = t("notReady");
  else if (current && current.busy) {
    status.textContent = t("busy");
    setBusy(true);
    clearTimeout(pollTimer);
    const poll = async () => {
      const fresh = await (await api(`conversations/${current.id}`)).json();
      if (fresh.busy) { pollTimer = setTimeout(poll, 3000); return; }
      current = fresh; renderMessages(box); status.textContent = ""; setBusy(false);
    };
    pollTimer = setTimeout(poll, 3000);
  }
  setBusy(sending || !me.ready || (current && current.busy));
  return h("div", { id: "view" },
    box,
    h("div", { class: "composer" }, previews,
      h("div", { class: "row" }, input, attachBtn, sendBtn, fileInput),
      h("div", { class: "row" }, h("span", { class: "meta" }, t("notice")), status)));
}

// --- admin view --------------------------------------------------------------

function fmtTime(ts) { return ts ? new Date(ts * 1000).toLocaleString(lang) : t("never"); }
const yesNo = (v) => (v === null || v === undefined ? t("unknown") : v ? t("yes") : t("no"));

function githubPanel() {
  const box = h("div", { class: "gh" });
  let timer = null;
  const show = (err) => box.replaceChildren(h("div", { class: "meta err" }, err.message));
  const call = async (path, method) => (await api(path, method ? { method } : {})).json();
  const render = (s) => {
    clearTimeout(timer);
    const kids = [];
    if (!s.available) {
      kids.push(h("div", { class: "meta err" }, t("ghMissing")));
    } else if (s.logged_in) {
      kids.push(h("div", {}, t("ghLoggedIn", s.account || "?")),
        h("button", { type: "button", class: "secondary", onclick: () => call("admin/github/logout", "POST").then(render, show) }, t("ghLogout")));
    } else if (s.login.state === "pending" && s.login.code) {
      kids.push(h("div", {}, t("ghStep1"), " ", h("a", { href: s.login.url, target: "_blank", rel: "noopener noreferrer" }, s.login.url)),
        h("div", {}, t("ghStep2")), h("div", { class: "code" }, s.login.code));
      timer = setTimeout(refresh, 3000);
    } else {
      if (s.login.state === "failed") kids.push(h("div", { class: "meta err" }, s.login.error || ""));
      kids.push(h("button", { type: "button", onclick: () => call("admin/github/login", "POST").then(render, show) }, t("ghLogin")));
    }
    box.replaceChildren(...kids);
  };
  const refresh = () => (box.isConnected ? call("admin/github").then(render, show) : null);
  call("admin/github").then(render, show);
  return box;
}

async function adminView() {
  const [settings, status, family] = await Promise.all([
    api("admin/settings").then((r) => r.json()),
    api("admin/status").then((r) => r.json()),
    api("family").then((r) => r.json()),
  ]);
  const url = h("input", { type: "text", value: settings.repo_url, autocomplete: "off" });
  const branch = h("input", { type: "text", value: settings.branch });
  const token = h("input", { type: "password", autocomplete: "new-password" });
  const method = h("select", {},
    h("option", { value: "token", selected: settings.auth_method === "token" }, t("authToken")),
    h("option", { value: "github_cli", selected: settings.auth_method === "github_cli" }, t("authGh")));
  const tokenBox = h("div", {}, h("label", {}, t("token")), token,
    h("div", { class: "meta" }, settings.has_token ? t("tokenSet") : t("tokenNone")));
  const ghBox = h("div", {}, githubPanel(), h("div", { class: "meta warn" }, t("ghScopeNote")));
  const showMethod = () => { tokenBox.hidden = method.value !== "token"; ghBox.hidden = method.value !== "github_cli"; };
  method.addEventListener("change", showMethod);
  showMethod();
  const commits = h("input", { type: "checkbox", checked: settings.allow_commits });
  const push = h("input", { type: "checkbox", checked: settings.allow_push });
  const aliasInputs = family.map((u) => ({ u, input: h("input", { type: "text", value: u.alias }) }));
  const msg = h("span", { class: "meta" });
  const view = h("div", { class: "admin" });

  const reload = async () => { view.replaceWith(await adminView()); };
  const act = (fn) => async () => {
    try { msg.textContent = ""; await fn(); await reload(); } catch (e) { msg.textContent = e.message; msg.className = "meta err"; }
  };

  const env = status.env;
  const model = status.model || {};
  view.append(...[
    h("h2", {}, t("settings")),
    h("label", {}, t("repoUrl")), url,
    h("label", {}, t("branch")), branch,
    h("label", {}, t("authMethod")), method, tokenBox, ghBox,
    h("label", {}, commits, " ", t("allowCommits")),
    h("label", {}, push, " ", t("allowPush")),
    h("h2", {}, t("aliases")),
    h("table", {}, aliasInputs.map(({ u, input }) => h("tr", {}, h("td", {}, u.name + (u.is_admin ? " (admin)" : "")), h("td", {}, input)))),
    h("div", { class: "row-actions" },
      h("button", { type: "button", onclick: act(async () => {
        const aliases = {};
        for (const { u, input } of aliasInputs) if (input.value.trim() && input.value.trim() !== u.name) aliases[u.id] = input.value.trim();
        await api("admin/settings", { method: "PUT", body: {
          repo_url: url.value, branch: branch.value, allow_commits: commits.checked, allow_push: push.checked,
          aliases, auth_method: method.value, git_token: token.value ? token.value : null } });
      }) }, t("save")),
      h("button", { type: "button", class: "secondary", onclick: act(() => api("admin/sync", { method: "POST" })) }, t("sync")),
      h("button", { type: "button", class: "secondary", onclick: act(() => api("admin/push", { method: "POST" })) }, t("push")),
      msg),
    h("h2", {}, t("status")),
    h("ul", {},
      h("li", {}, `${t("head")}: ${env.head || "-"}`),
      h("li", {}, `${t("ahead")}: ${env.ahead}, ${t("behind")}: ${env.behind}, ${t("pending")}: ${env.pending}`),
      h("li", {}, `${t("diverged")}: ${yesNo(env.diverged)}`),
      h("li", {}, `${t("lastSync")}: ${fmtTime(env.last_sync)}`),
      env.last_error ? h("li", { class: "err" }, `${t("lastError")}: ${env.last_error}`) : null,
      h("li", {}, `${t("ollama")}: ${status.options.ollama_url} (${model.model}) - ${t("reachable")}: ${yesNo(model.reachable)}, ${t("exists")}: ${yesNo(model.exists)}, ${t("tools")}: ${yesNo(model.tools)}, ${t("vision")}: ${yesNo(model.vision)}`),
      h("li", {}, `${t("queue")}: ${status.queue.running} ${t("running")}, ${status.queue.waiting} ${t("waiting")}`)),
    status.warnings.length ? h("div", {}, h("h2", {}, t("warnings")), h("ul", { class: "warn" }, status.warnings.map((w) => h("li", {}, w)))) : null,
    status.rules ? h("div", {}, h("h2", {}, t("rules")),
      h("div", {}, h("strong", {}, t("hidden") + ": "), status.rules.hidden.join("  ") || t("none")),
      h("div", {}, h("strong", {}, t("readonly") + ": "), status.rules.readonly.join("  ") || t("none")),
      h("div", {}, h("strong", {}, t("enabledTools") + ": "), status.rules.tools.join(", ") || t("none"))) : null,
  ].filter(Boolean));
  return view;
}

// --- shell --------------------------------------------------------------------

async function loadConvs() {
  convs = await (await api("conversations")).json();
}

async function newConversation() {
  const { id } = await (await api("conversations", { method: "POST" })).json();
  await loadConvs();
  current = await (await api(`conversations/${id}`)).json();
}

async function openConversation(id) {
  clearTimeout(pollTimer);
  current = await (await api(`conversations/${id}`)).json();
  await showChat();
}

async function showChat() {
  document.getElementById("main").replaceChildren(sidebar(), chatView());
}

async function showAdmin() {
  clearTimeout(pollTimer);
  const main = document.getElementById("main");
  main.replaceChildren(h("div", { id: "view" }, h("div", { class: "meta" }, "...")));
  try {
    main.replaceChildren(h("div", { id: "view" }, await adminView()));
  } catch (e) {
    main.replaceChildren(h("div", { id: "view" }, h("div", { class: "admin err" }, e.message)));
  }
}

function sidebar() {
  return h("aside", {},
    h("button", { type: "button", onclick: async () => { await newConversation(); await showChat(); } }, t("newChat")),
    convs.map((c) => h("button", { type: "button", class: "conv" + (current && current.id === c.id ? " active" : ""),
      onclick: () => openConversation(c.id) }, c.title || "...")));
}

async function renderShell() {
  const header = h("header", {}, h("span", { class: "brand" }, "Family Assist"), h("span", { class: "meta" }, me.alias));
  if (me.is_admin) {
    const family = await (await api("family")).json();
    const select = h("select", { title: t("actAs") },
      h("option", { value: "" }, t("myself")),
      family.map((u) => h("option", { value: u.id, selected: u.id === actAs }, u.alias)));
    select.addEventListener("change", () => {
      actAs = select.value;
      if (actAs) sessionStorage.setItem("fa-act-as", actAs); else sessionStorage.removeItem("fa-act-as");
      current = null;
      boot();
    });
    header.append(select, h("button", { type: "button", class: "secondary", onclick: showAdmin }, t("admin")),
      h("button", { type: "button", class: "secondary", onclick: showChat }, t("back")));
  }
  const langSelect = h("select", {}, ["de", "en"].map((l) => h("option", { value: l, selected: l === lang }, l.toUpperCase())));
  langSelect.addEventListener("change", () => { lang = langSelect.value; localStorage.setItem("fa-lang", lang); boot(); });
  header.append(langSelect);
  appEl.replaceChildren(header);
  if (me.acting) appEl.append(h("div", { class: "banner" }, t("actingAs", me.alias)));
  appEl.append(h("main", { id: "main" }));
}

async function boot() {
  try {
    me = await (await api("me")).json();
    if (actAs && !me.acting) { actAs = ""; sessionStorage.removeItem("fa-act-as"); }
    await renderShell();
    await loadConvs();
    await showChat();
  } catch (e) {
    appEl.replaceChildren(h("div", { class: "admin err" }, e.message));
  }
}

boot();

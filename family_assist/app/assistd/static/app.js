"use strict";

const TEXT = window.FA_TEXT; // loaded from i18n/<lang>.js; add a language by adding a file and a script tag

let lang = localStorage.getItem("fa-lang") || ((navigator.language || "en").startsWith("de") ? "de" : "en");
if (!TEXT[lang]) lang = "en";
const t = (key, ...args) => {
  const v = TEXT[lang][key] ?? TEXT.en[key];
  return typeof v === "function" ? v(...args) : v;
};

let me = null;
let convs = [];
let current = null;
let envId = localStorage.getItem("fa-env") || "";
const currentEnv = () => (me && me.environments.find((e) => e.id === envId)) || null;
const envReady = () => !!(currentEnv() && currentEnv().ready);
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

async function saveFile(path, fallbackName) {
  try {
    const res = await api(path);
    const disposition = res.headers.get("Content-Disposition") || "";
    const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/);
    const name = encoded ? decodeURIComponent(encoded[1]) : fallbackName;
    const url = URL.createObjectURL(await res.blob());
    const link = h("a", { href: url, download: name });
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  } catch (e) {
    alert(e.message);
  }
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
  const files = [...new Set((m.tools || []).filter((e) => e.ok).flatMap((e) => e.changed || []))];
  if (files.length) {
    el.append(h("div", { class: "files" }, h("span", { class: "meta" }, t("filesChanged") + " "), files.map((p) =>
      h("button", { type: "button", class: "secondary small", title: p, onclick: () => saveFile(`conversations/${current.id}/files/${p.split("/").map(encodeURIComponent).join("/")}`, p.split("/").pop()) }, p.split("/").pop()))));
  }
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
    const res = await api(`conversations/${current.id}/messages`, { method: "POST", body: { text, images, lang } });
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

  const setBusy = (busy) => { sendBtn.disabled = busy || !envReady(); input.disabled = busy; };
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
  if (!currentEnv()) status.textContent = t("noEnv");
  else if (!envReady()) status.textContent = t("notReady");
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
  setBusy(sending || !envReady() || (current && current.busy));
  return h("div", { id: "view" },
    box,
    h("div", { class: "composer" }, previews,
      h("div", { class: "row" }, input, attachBtn, sendBtn, fileInput),
      h("div", { class: "row" }, h("span", { class: "meta" }, t("notice")), status,
        h("button", { type: "button", class: "secondary small", onclick: () => current && saveFile(`conversations/${current.id}/export`, "conversation.md") }, t("exportChat")))));
}

async function renameConv(c) {
  const title = (prompt(t("renamePrompt"), c.title || "") || "").trim();
  if (!title || title === c.title) return;
  try {
    const res = await (await api(`conversations/${c.id}`, { method: "PATCH", body: { title } })).json();
    if (current && current.id === c.id) current.title = res.title;
    await loadConvs();
    const side = document.querySelector("aside");
    if (side) side.replaceWith(sidebar());
  } catch (e) {
    alert(e.message);
  }
}

// --- admin view --------------------------------------------------------------

async function deleteConv(c) {
  if (!confirm(t("deleteConfirm"))) return;
  try {
    await api(`conversations/${c.id}`, { method: "DELETE" });
    clearTimeout(pollTimer);
    if (current && current.id === c.id) current = null;
    await loadConvs();
    await showChat();
  } catch (e) {
    alert(e.message);
  }
}

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
  const [settings, status, family, deleted] = await Promise.all([
    api("admin/settings").then((r) => r.json()),
    api("admin/status").then((r) => r.json()),
    api("family").then((r) => r.json()),
    api("admin/deleted").then((r) => r.json()),
  ]);
  const rows = settings.environments.map((e) => ({ id: e.id, name: e.name, url: e.repo_url, branch: e.branch }));
  const envList = h("div", { class: "envs" });
  const renderEnvs = () => envList.replaceChildren(...rows.map((row) => h("div", { class: "env-row" },
    h("label", {}, t("envName")), h("input", { type: "text", value: row.name, oninput: (e) => { row.name = e.target.value; } }),
    h("label", {}, t("repoUrl")), h("input", { type: "text", value: row.url, autocomplete: "off", oninput: (e) => { row.url = e.target.value; } }),
    h("label", {}, t("branch")), h("input", { type: "text", value: row.branch, oninput: (e) => { row.branch = e.target.value; } }),
    h("button", { type: "button", class: "secondary small", onclick: () => {
      if (!confirm(t("removeConfirm"))) return;
      rows.splice(rows.indexOf(row), 1);
      renderEnvs();
    } }, t("removeEnv")))));
  renderEnvs();
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

  const envStatuses = status.environments;
  const envStatus = ({ id, name, env, model, warnings, rules }) => h("div", {},
    h("h3", {}, name),
    h("div", { class: "row-actions" },
      h("button", { type: "button", class: "secondary", onclick: act(() => api(`admin/sync?env=${id}`, { method: "POST" })) }, t("sync")),
      h("button", { type: "button", class: "secondary", onclick: act(() => api(`admin/push?env=${id}`, { method: "POST" })) }, t("push"))),
    h("ul", {},
      h("li", {}, `${t("head")}: ${env.head || "-"}`),
      h("li", {}, `${t("ahead")}: ${env.ahead}, ${t("behind")}: ${env.behind}, ${t("pending")}: ${env.pending}`),
      h("li", {}, `${t("diverged")}: ${yesNo(env.diverged)}`),
      h("li", {}, `${t("lastSync")}: ${fmtTime(env.last_sync)}`),
      env.last_error ? h("li", { class: "err" }, `${t("lastError")}: ${env.last_error}`) : null,
      h("li", {}, `${t("model")}: ${model.model} - ${t("reachable")}: ${yesNo(model.reachable)}, ${t("exists")}: ${yesNo(model.exists)}, ${t("tools")}: ${yesNo(model.tools)}, ${t("vision")}: ${yesNo(model.vision)}`)),
    warnings.length ? h("div", {}, h("strong", {}, t("warnings")), h("ul", { class: "warn" }, warnings.map((w) => h("li", {}, w)))) : null,
    rules ? h("div", {}, h("strong", {}, t("rules")),
      h("div", {}, h("strong", {}, t("hidden") + ": "), rules.hidden.join("  ") || t("none")),
      h("div", {}, h("strong", {}, t("readonly") + ": "), rules.readonly.join("  ") || t("none")),
      h("div", {}, h("strong", {}, t("enabledTools") + ": "), rules.tools.join(", ") || t("none"))) : null);
  view.append(...[
    h("h2", {}, t("environments")),
    envList,
    h("button", { type: "button", class: "secondary", onclick: () => { rows.push({ id: null, name: "", url: "", branch: "main" }); renderEnvs(); } }, t("addEnv")),
    h("h2", {}, t("settings")),
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
          environments: rows.map((r) => ({ id: r.id, name: r.name, repo_url: r.url, branch: r.branch })),
          allow_commits: commits.checked, allow_push: push.checked,
          aliases, auth_method: method.value, git_token: token.value ? token.value : null } });
        me = await (await api("me")).json();
        if (!currentEnv()) { envId = me.environments.length ? me.environments[0].id : ""; current = null; }
        await loadConvs();
      }) }, t("save")),
      msg),
    h("h2", {}, t("status")),
    h("ul", {},
      h("li", {}, `${t("ollama")}: ${status.options.ollama_url}`),
      h("li", {}, `${t("queue")}: ${status.queue.running} ${t("running")}, ${status.queue.waiting} ${t("waiting")}`)),
    envStatuses.map(envStatus),
    h("h2", {}, t("deletedChats")),
    h("div", { class: "meta" }, t("deletedNote")),
    h("table", {}, deleted.map((d) => h("tr", {},
      h("td", {}, d.title || "..."),
      h("td", {}, (family.find((u) => u.id === d.user_id) || { alias: d.user_id }).alias),
      h("td", { class: "meta" }, `${d.messages} ${t("messagesCount")}, ${t("deletedOn")} ${fmtTime(d.deleted_at)}`),
      h("td", {}, h("button", { type: "button", class: "secondary small", onclick: act(async () => {
        await api(`admin/deleted/${encodeURIComponent(d.user_id)}/${d.id}/restore`, { method: "POST" });
        await loadConvs();
      }) }, t("restore")))))),
  ].filter(Boolean));
  return view;
}

// --- shell --------------------------------------------------------------------

async function loadConvs() {
  convs = currentEnv() ? await (await api(`conversations?env=${encodeURIComponent(envId)}`)).json() : [];
}

async function newConversation() {
  const { id } = await (await api(`conversations?env=${encodeURIComponent(envId)}`, { method: "POST" })).json();
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
  const envSelect = me.environments.length > 1 ? h("select", { title: t("environment"), "aria-label": t("environment") },
    me.environments.map((e) => h("option", { value: e.id, selected: e.id === envId }, e.name))) : null;
  if (envSelect) {
    envSelect.addEventListener("change", async () => {
      clearTimeout(pollTimer);
      envId = envSelect.value;
      localStorage.setItem("fa-env", envId);
      current = null;
      await loadConvs();
      await showChat();
    });
  }
  return h("aside", {},
    envSelect,
    h("button", { type: "button", disabled: !currentEnv(), onclick: async () => { await newConversation(); await showChat(); } }, t("newChat")),
    convs.map((c) => h("div", { class: "conv-row" },
      h("button", { type: "button", class: "conv" + (current && current.id === c.id ? " active" : ""),
        onclick: () => openConversation(c.id) }, c.title || "..."),
      h("button", { type: "button", class: "conv-edit conv-rename", title: t("renameChat"), "aria-label": t("renameChat"),
        onclick: (e) => { e.stopPropagation(); renameConv(c); } }, "✎"),
      h("button", { type: "button", class: "conv-edit", title: t("deleteChat"), "aria-label": t("deleteChat"),
        onclick: (e) => { e.stopPropagation(); deleteConv(c); } }, "🗑"))));
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
    if (!currentEnv()) envId = me.environments.length ? me.environments[0].id : "";
    await renderShell();
    await loadConvs();
    await showChat();
  } catch (e) {
    appEl.replaceChildren(h("div", { class: "admin err" }, e.message));
  }
}

boot();

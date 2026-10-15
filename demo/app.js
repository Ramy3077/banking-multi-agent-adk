(() => {
  "use strict";

  const LANES = ["root_agent", "complaints_handler", "navigator_agent", "bq_agent"];
  const LANE_SHORT = { root_agent: "R", complaints_handler: "C", navigator_agent: "N", bq_agent: "B" };
  const AGENT_TOOLS = new Set(LANES);

  const $ = (id) => document.getElementById(id);
  const el = (tag, attrs = {}, ...children) => {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null || v === false) continue;
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else if (k === "html") node.innerHTML = v;
      else node.setAttribute(k, v);
    }
    for (const c of children.flat()) if (c != null) node.append(c);
    return node;
  };

  const md = (text) => {
    if (window.marked && window.DOMPurify) {
      return window.DOMPurify.sanitize(window.marked.parse(text, { gfm: true, breaks: true }));
    }
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML.replace(/\n/g, "<br>");
  };

  const secs = (ms) => `+${(ms / 1000).toFixed(1)} s`;
  const fmtDate = (iso) =>
    new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });

  const state = { manifest: [], session: null, steps: [], shown: 0, cache: new Map() };

  // Turn the recorded events into replay steps.
  function buildSteps(events) {
    const steps = [];
    for (const ev of events) {
      if (ev.author === "user") {
        steps.push({ kind: "user", ev });
        continue;
      }
      if (ev.error) steps.push({ kind: "error", ev });
      for (const part of ev.parts) {
        if (part.type === "function_call" && part.name === "transfer_to_agent") {
          steps.push({ kind: "transfer", ev, to: part.args.agent_name || ev.transfer_to_agent });
        } else if (part.type === "function_call") {
          steps.push({ kind: "call", ev, part });
        } else if (part.type === "function_response" && part.name === "transfer_to_agent") {
          // the transfer step already shows this
        } else if (part.type === "function_response") {
          steps.push({ kind: "result", ev, part });
        } else if (part.type === "text") {
          steps.push({ kind: "text", ev, part });
        }
      }
    }
    return steps;
  }

  function railFor(step, active) {
    const rail = el("div", { class: "rail", "aria-hidden": "true" });
    for (const lane of LANES) {
      const span = el("span", { "data-lane": lane });
      if (active.has(lane)) span.classList.add("on");
      if (step.ev.author === lane) span.classList.add("here");
      rail.append(span);
    }
    return rail;
  }

  function prettyArgs(args) {
    if (args && typeof args.query === "string" && Object.keys(args).length === 1) return args.query;
    return JSON.stringify(args, null, 2);
  }

  function rowsTable(rows) {
    if (!Array.isArray(rows) || rows.length === 0 || typeof rows[0] !== "object") return null;
    const cols = Object.keys(rows[0]);
    return el("div", { class: "rows" },
      el("table", {},
        el("thead", {}, el("tr", {}, cols.map((c) => el("th", { text: c })))),
        el("tbody", {}, rows.map((r) => el("tr", {}, cols.map((c) => el("td", { text: r[c] == null ? "NULL" : String(r[c]) })))))));
  }

  function head(step, label) {
    return el("div", { class: "card-head" },
      el("span", {}, el("span", { class: "who", text: step.ev.author }), label ? ` ${label}` : ""),
      el("span", { class: "t", text: secs(step.ev.t_ms) }));
  }

  function renderStep(step, active) {
    const lane = step.ev.author;
    const li = el("li", { class: `step ${step.kind}`, "data-lane": lane });
    let card;

    if (step.kind === "user") {
      li.setAttribute("data-lane", "user");
      card = el("div", { class: "card", "data-lane": "user" },
        el("div", { class: "card-head" }, el("span", { text: `Customer, turn ${step.ev.turn}` }), el("span", { class: "t", text: secs(step.ev.t_ms) })),
        el("div", { class: "body", text: step.part ? step.part.text : step.ev.parts[0].text }));
    } else if (step.kind === "transfer") {
      card = el("div", { class: "card", "data-lane": step.to },
        el("div", { class: "card-head" }, el("span", { text: "Agent transfer" }), el("span", { class: "t", text: secs(step.ev.t_ms) })),
        el("div", { class: "body" }, el("code", { text: lane }), " hands the conversation to ", el("code", { text: step.to }),
          " (ADK ", el("code", { text: "transfer_to_agent" }), ")"));
    } else if (step.kind === "call") {
      const isAgent = AGENT_TOOLS.has(step.part.name);
      const args = step.part.args || {};
      const body = el("div", { class: "body" },
        el("div", { class: "tool" }, el("span", { class: "kind", text: isAgent ? "AgentTool → " : "tool call → " }), step.part.name));
      if (isAgent && typeof args.request === "string") {
        body.append(el("p", { class: "arg-preview", text: `"${args.request}"` }));
      } else {
        const open = Boolean(args.query) || JSON.stringify(args).length < 240;
        body.append(el("details", { open: open ? "" : null }, el("summary", { text: "Arguments" }), el("pre", { text: prettyArgs(args) })));
      }
      card = el("div", { class: "card" }, head(step, isAgent ? "asks another agent" : "calls a tool"), body);
    } else if (step.kind === "result") {
      const resp = step.part.response || {};
      const isAgent = AGENT_TOOLS.has(step.part.name);
      const failed = resp.status === "ERROR" || (typeof resp.result === "string" && resp.result.startsWith("Error"));
      const body = el("div", { class: "body" },
        el("div", { class: "tool" }, el("span", { class: "kind", text: "result ← " }), step.part.name,
          el("span", { class: `result-tag${failed ? " err" : ""}`, text: failed ? "error" : "ok" })));
      if (typeof resp.result === "string" && !isAgent) {
        body.append(el("p", { class: "arg-preview", text: resp.result }));
      } else if (Array.isArray(resp.rows)) {
        const d = el("details", { open: resp.rows.length <= 8 ? "" : null }, el("summary", { text: `${resp.rows.length} row${resp.rows.length === 1 ? "" : "s"}` }));
        const t = rowsTable(resp.rows);
        if (t) d.append(t);
        body.append(d);
      } else {
        body.append(el("details", {}, el("summary", { text: isAgent ? `Full answer from ${step.part.name}` : "Response" }),
          el("pre", { text: typeof resp.result === "string" ? resp.result : JSON.stringify(resp, null, 2) })));
      }
      card = el("div", { class: "card" }, head(step, "gets a result"), body);
    } else if (step.kind === "text") {
      const toCaller = lane === "bq_agent";
      card = el("div", { class: "card" }, head(step, toCaller ? "answers its caller" : "replies to the customer"),
        el("div", { class: "body", html: md(step.part.text) }));
    } else {
      card = el("div", { class: "card" }, head(step, "error"),
        el("pre", { text: JSON.stringify(step.ev.error, null, 2) }));
    }

    li.append(railFor(step, active), card);
    return li;
  }

  function activeLanesUpTo(n) {
    // Lanes that have spoken so far, so the rail shows who is in the conversation.
    const s = new Set(["root_agent"]);
    for (let i = 0; i < n; i++) {
      const st = state.steps[i];
      if (LANES.includes(st.ev.author)) s.add(st.ev.author);
      if (st.kind === "transfer") s.add(st.to);
      if (st.kind === "call" && AGENT_TOOLS.has(st.part.name)) s.add(st.part.name);
    }
    return s;
  }

  function render(scroll) {
    const tl = $("timeline");
    tl.replaceChildren();
    for (let i = 0; i < state.shown; i++) tl.append(renderStep(state.steps[i], activeLanesUpTo(i + 1)));

    const last = state.steps[state.shown - 1];
    document.querySelectorAll(".lane-head").forEach((h) => h.classList.toggle("active", Boolean(last) && h.dataset.lane === last.ev.author));

    $("prev").disabled = state.shown <= 1;
    $("next").disabled = state.shown >= state.steps.length;
    $("all").disabled = state.shown >= state.steps.length;
    $("progress").textContent = `Step ${state.shown} of ${state.steps.length}`;

    const done = state.shown >= state.steps.length;
    $("after").hidden = !done || !state.session.database_after.length;
    if (done) renderAfter();

    if (scroll && tl.lastElementChild) tl.lastElementChild.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function renderAfter() {
    const body = $("after-body");
    body.replaceChildren();
    for (const snap of state.session.database_after) {
      body.append(el("p", { text: snap.label }));
      body.append(rowsTable(snap.rows) || el("p", { class: "muted", text: "No rows." }));
    }
  }

  async function loadSession(id, push) {
    const meta = state.manifest.find((m) => m.id === id) || state.manifest[0];
    if (!state.cache.has(meta.id)) {
      const res = await fetch(meta.file);
      state.cache.set(meta.id, await res.json());
    }
    state.session = state.cache.get(meta.id);
    state.steps = buildSteps(state.session.events);
    state.shown = 1;
    $("scenario-title").textContent = state.session.title;
    $("scenario-summary").textContent = state.session.summary;
    $("scenario-meta").textContent = `Model ${state.session.model} · recorded ${state.session.recorded_at.replace("T", " ").replace("+00:00", " UTC")}`;
    document.querySelectorAll("#scenario-list button").forEach((b) => b.setAttribute("aria-current", String(b.dataset.id === meta.id)));
    if (push) history.replaceState(null, "", `#${meta.id}`);
    render(false);
  }

  async function init() {
    state.manifest = await (await fetch("sessions/index.json")).json();
    const models = [...new Set(state.manifest.map((m) => m.model))].join(", ");
    const dates = [...new Set(state.manifest.map((m) => fmtDate(m.recorded_at)))].join(", ");
    $("notice").textContent = `Recorded runs of the real agent on ${models}, ${dates}, against a fictional SQLite dataset. Replays, not live.`;
    if (!state.manifest.every((m) => m.model === "gemini-2.5-flash")) {
      $("model-note").textContent = `The project is built for gemini-2.5-flash. The API key used for these recordings could not use 2.5 Flash any more, so they were made with ${models} through the repo's BANK_MODEL setting (more than one model because the free tier allows 20 requests per model per day). Same agents, prompts and tools. Each scenario shows the model it ran on.`;
    }

    const list = $("scenario-list");
    state.manifest.forEach((m, i) => {
      list.append(el("li", {}, el("button", { type: "button", "data-id": m.id }, el("span", { class: "n", text: String(i + 1) }), m.title)));
    });
    list.addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (b) loadSession(b.dataset.id, true);
    });

    $("next").addEventListener("click", () => { if (state.shown < state.steps.length) { state.shown++; render(true); } });
    $("prev").addEventListener("click", () => { if (state.shown > 1) { state.shown--; render(false); } });
    $("all").addEventListener("click", () => { state.shown = state.steps.length; render(false); });
    document.addEventListener("keydown", (e) => {
      if (e.target.closest("input, textarea, select")) return;
      if (e.key === "ArrowRight" || e.key === "j") $("next").click();
      if (e.key === "ArrowLeft" || e.key === "k") $("prev").click();
    });

    const railHead = el("div", { class: "rail-head", "aria-hidden": "true" }, LANES.map((l) => el("span", { text: LANE_SHORT[l] })));
    $("timeline").before(railHead);

    await loadSession(location.hash.slice(1), false);
  }

  init().catch((err) => {
    $("scenario-title").textContent = "Could not load the recordings";
    $("scenario-summary").textContent = String(err);
  });
})();

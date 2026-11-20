"use strict";
/* 저널 출판 기간 & APC 지원 안내 — 정적 웹 (서버 불필요) */

const PAGE = 200;
const ISSN_RE = /^\d{4}-?\d{3}[\dXx]$/;
const $ = (s) => document.querySelector(s);

let DATA = [], META = {}, BY_ISSN = new Map();
let view = [], shown = PAGE, sortKey = null, sortAsc = true, inputOrder = false;

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const normIssn = (s) => { const t = s.replace(/[^0-9Xx]/g, "").toUpperCase(); return t.length === 8 ? `${t.slice(0, 4)}-${t.slice(4)}` : null; };
const norm = (s) => String(s || "").toLowerCase().replace(/\s+/g, " ").trim();

async function init() {
  try {
    const res = await fetch("data/journals.json", { cache: "no-cache" });
    const json = await res.json();
    META = json.meta || {}; DATA = json.journals || [];
  } catch (e) {
    $("#updated").textContent = "데이터를 불러오지 못했습니다.";
    return;
  }
  for (const j of DATA) {
    j._t = norm(j.title); j._a = norm(j.abbrev);
    for (const k of [j.issn, j.eissn]) if (k) BY_ISSN.set(k, j);
  }
  $("#updated").textContent = META.generated_at
    ? `업데이트 ${META.generated_at} · 저널 ${fmt(META.n_journals)}종 (출판 기간 산출 ${fmt(META.n_with_stats)}종)`
    : "아직 수집된 데이터가 없습니다.";
  document.querySelectorAll(".m-max").forEach((e) => (e.textContent = META.max_per_journal ?? "N"));
  document.querySelectorAll(".m-n").forEach((e) => (e.textContent = fmt(META.n_journals)));
  document.querySelectorAll(".m-days").forEach((e) => (e.textContent = META.lookback_days ?? "N"));

  let timer;
  $("#q").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(run, 200); });
  ["#f-apc", "#f-max", "#f-min", "#f-rel"].forEach((s) => $(s).addEventListener("input", run));
  $("#reset").onclick = () => { $("#q").value = ""; $("#f-apc").checked = false; $("#f-max").value = ""; $("#f-min").value = ""; $("#f-rel").value = ""; sortKey = null; run(); };
  $("#more").onclick = () => { shown += PAGE; render(); };
  document.querySelectorAll("th[data-k]").forEach((th) => th.addEventListener("click", () => {
    const k = th.dataset.k;
    if (sortKey === k) sortAsc = !sortAsc; else { sortKey = k; sortAsc = true; }
    inputOrder = false; sortView(); shown = PAGE; render();
  }));
  run();
}

const fmt = (n) => (n ?? 0).toLocaleString("ko-KR");

function search(q) {
  const missing = [];
  q = q.trim();
  $("#notice-abstract").classList.toggle("hidden", !(q.length > 400 && q.split(/\s+/).length > 50));
  if (!q || q.length > 400) return { list: DATA.slice(), missing, mode: "all" };

  const tokens = q.split(/[\s,;]+/).filter(Boolean);
  if (tokens.every((t) => ISSN_RE.test(t))) {           // ISSN만 입력
    const list = [], seen = new Set();
    for (const t of tokens) {
      const k = normIssn(t), j = BY_ISSN.get(k);
      if (j && !seen.has(j)) { list.push(j); seen.add(j); }
      else if (!j) missing.push(k);
    }
    return { list, missing, mode: "issn" };
  }
  // 저널명/약어 (쉼표·세미콜론·줄바꿈으로 여러 개)
  const parts = q.split(/[,;\n]+/).map(norm).filter(Boolean);
  const list = [], seen = new Set();
  for (const p of parts) {
    const k = ISSN_RE.test(p.replace(/\s/g, "")) ? normIssn(p) : null;
    if (k) { const j = BY_ISSN.get(k); if (j && !seen.has(j)) { list.push(j); seen.add(j); } else if (!j) missing.push(k); continue; }
    const exact = DATA.filter((j) => j._t === p || j._a === p);
    const partial = DATA.filter((j) => (j._t.includes(p) || j._a.includes(p)) && !exact.includes(j));
    if (!exact.length && !partial.length) missing.push(p);
    for (const j of [...exact, ...partial]) if (!seen.has(j)) { list.push(j); seen.add(j); }
  }
  return { list, missing, mode: parts.length > 1 ? "multi" : "name" };
}

function applyFilters(list) {
  const apc = $("#f-apc").checked, max = +$("#f-max").value || null, min = +$("#f-min").value || null, rel = $("#f-rel").value;
  return list.filter((j) => {
    const m = j.rec_acc?.median;
    if (apc && !j.apc) return false;
    if (max && !(m != null && m <= max)) return false;
    if (min && !(m != null && m >= min)) return false;
    if (rel === "보통" && !["보통", "높음"].includes(j.reliability)) return false;
    if (rel === "높음" && j.reliability !== "높음") return false;
    return true;
  });
}

const KEYS = {
  title: (j) => j._t, issn: (j) => j.issn || j.eissn, publisher: (j) => norm(j.publisher) || null,
  median: (j) => j.rec_acc?.median ?? null, pubmed: (j) => j.acc_pub?.median ?? null,
  n: (j) => j.rec_acc?.n ?? 0, latest: (j) => j.latest_accepted || null, apc: (j) => (j.apc ? 0 : 1),
};

function sortView() {
  if (inputOrder || !sortKey) return;
  const f = KEYS[sortKey], dir = sortAsc ? 1 : -1;
  view.sort((a, b) => {
    const x = f(a), y = f(b);
    if (x == null && y == null) return 0;
    if (x == null) return 1;            // 값 없는 항목은 항상 뒤로
    if (y == null) return -1;
    return (x < y ? -1 : x > y ? 1 : 0) * dir;
  });
}

function run() {
  const { list, missing, mode } = search($("#q").value);
  view = applyFilters(list);
  inputOrder = (mode === "issn" || mode === "multi") && !sortKey;
  if (mode === "all" && !sortKey) { sortKey = "median"; sortAsc = true; }
  sortView(); shown = PAGE;

  const conds = [];
  if ($("#q").value.trim()) conds.push(mode === "issn" ? `ISSN ${missing.length + view.length}건 조회` : `검색어 “${esc($("#q").value.trim().slice(0, 60))}”`);
  if ($("#f-apc").checked) conds.push("전남대 APC 지원 목록 일치");
  if ($("#f-max").value) conds.push(`투고→승인 중앙값 ${esc($("#f-max").value)}일 이내`);
  if ($("#f-min").value) conds.push(`${esc($("#f-min").value)}일 미만 제외`);
  if ($("#f-rel").value) conds.push(`신뢰도 ${esc($("#f-rel").value)} 이상`);
  const hidden = list.length - view.length;
  $("#summary").innerHTML = `${conds.length ? conds.join(" · ") + " → " : "전체 저널 → "}💡 <b>${fmt(view.length)}</b>개 저널` +
    (hidden > 0 && $("#q").value.trim() ? ` <span class="rel" style="display:inline">(검색되었지만 필터 조건으로 숨겨진 저널 ${fmt(hidden)}개)</span>` : "");
  $("#missing").innerHTML = missing.map((m) =>
    `<p class="warn">⚠️ ${esc(m)}은(는) 현재 출판 기간 데이터베이스에 등록되어 있지 않습니다.</p>`).join("");
  render();
}

function cellDays(s) { return s ? `${s.median}일` : '<span class="na">-</span>'; }

function render() {
  document.querySelectorAll("th[data-k]").forEach((th) => {
    th.classList.toggle("sorted", th.dataset.k === sortKey && !inputOrder);
    th.classList.toggle("asc", sortAsc);
  });
  const rows = view.slice(0, shown).map((j) => {
    const ra = j.rec_acc;
    const rel = ra ? `<span class="rel ${j.reliability === "낮음" ? "low" : ""}">신뢰도 ${j.reliability}${ra.short ? ` · 7일 미만 ${ra.short}편` : ""}</span>` : "";
    const issn = [j.issn, j.eissn].filter(Boolean).map(esc).join("<br>");
    const apc = j.apc ? '<span class="badge b-yes">💡 지원 목록 일치</span>'
                      : '<span class="badge b-no">목록에서 확인되지 않음</span>';
    const nCell = j.n_sampled
      ? `${ra ? ra.n : 0}<span class="rel">/ 수집 ${j.n_sampled}편</span>`
      : `<span class="na">${j.error ? "조회 오류" : "0"}</span>`;
    return `<tr>
      <td>${esc(j.title)}${j.abbrev ? `<span class="abbr">${esc(j.abbrev)}</span>` : ""}</td>
      <td>${issn || '<span class="na">-</span>'}</td>
      <td>${esc(j.publisher) || '<span class="na">-</span>'}</td>
      <td class="r"><b>${cellDays(ra)}</b>${rel}</td>
      <td class="r">${ra ? `${ra.q1}~${ra.q3}일` : '<span class="na">-</span>'}</td>
      <td class="r">${cellDays(j.acc_pub)}</td>
      <td class="r">${nCell}</td>
      <td>${esc(j.latest_accepted) || '<span class="na">-</span>'}</td>
      <td>${apc}</td></tr>`;
  });
  $("#tbl tbody").innerHTML = rows.join("") ||
    '<tr><td colspan="9" class="na" style="text-align:center;padding:24px">조건에 맞는 저널이 없습니다.</td></tr>';
  $("#more").classList.toggle("hidden", view.length <= shown);
  $("#more").textContent = `더 보기 (${fmt(Math.min(shown, view.length))} / ${fmt(view.length)})`;
}

init();

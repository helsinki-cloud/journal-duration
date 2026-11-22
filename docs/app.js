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
const fmt = (n) => (n ?? 0).toLocaleString("ko-KR");
 
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
    j._t = norm(j.title); j._a = norm(j.abbrev); j._p = norm(j.publisher);
    for (const k of [j.issn, j.eissn]) if (k && !BY_ISSN.has(k)) BY_ISSN.set(k, j);
  }
  if (META.generated_at) {
    $("#updated").textContent = `업데이트 ${META.generated_at}`;
    $("#coverage").textContent =
      `수록 저널 ${fmt(META.n_journals)}종 (PMC 참여 ${fmt(META.n_pmc)} · APC 지원 목록 전용 ${fmt(META.n_apc_only)}) · ` +
      `출판 기간 산출 ${fmt(META.n_with_stats)}종 · 전남대 APC 지원 일치 ${fmt(META.n_apc_matched)}종`;
    if (META.n_checked != null && META.n_checked < META.n_journals) {
      $("#partial").textContent = `⚠️ 아직 전체 수집 전입니다. PubMed 조회를 마친 저널은 ${fmt(META.n_checked)} / ${fmt(META.n_journals)}종이며, ` +
        `나머지 저널은 ‘수집 전’으로 표시됩니다. (APC 지원 여부는 수집과 관계없이 모두 표시됩니다)`;
      $("#partial").classList.remove("hidden");
    }
  } else {
    $("#updated").textContent = "아직 수집된 데이터가 없습니다.";
  }
  document.querySelectorAll(".m-max").forEach((e) => (e.textContent = META.max_per_journal ?? "N"));
  document.querySelectorAll(".m-days").forEach((e) => (e.textContent = META.lookback_days ?? "N"));
 
  let timer;
  $("#q").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(run, 200); });
  ["#f-apc", "#f-has", "#f-basis", "#f-max", "#f-min", "#f-rel"].forEach((s) => $(s).addEventListener("input", run));
  $("#reset").onclick = () => {
    $("#q").value = ""; ["#f-apc", "#f-has"].forEach((s) => ($(s).checked = false));
    ["#f-max", "#f-min", "#f-rel"].forEach((s) => ($(s).value = ""));
    $("#f-basis").value = "rec_acc";
    sortKey = null; run();
  };
  document.querySelectorAll(".ex").forEach((b) => b.addEventListener("click", () => {
    $("#q").value = b.dataset.q; $("#f-apc").checked = b.dataset.apc === "1"; sortKey = null; run();
  }));
  $("#more").onclick = () => { shown += PAGE; render(); };
  document.querySelectorAll(".tip").forEach((t) => t.addEventListener("click", (e) => e.stopPropagation()));
  document.querySelectorAll("th[data-k]").forEach((th) => th.addEventListener("click", () => {
    const k = th.dataset.k;
    if (sortKey === k) sortAsc = !sortAsc; else { sortKey = k; sortAsc = true; }
    inputOrder = false; sortView(); shown = PAGE; render();
  }));
  run();
}
 
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
  // 저널명·약어·출판사 (쉼표·세미콜론·줄바꿈으로 여러 개)
  const parts = q.split(/[,;\n]+/).map(norm).filter(Boolean);
  const list = [], seen = new Set();
  for (const p of parts) {
    const compact = p.replace(/\s/g, "");
    if (ISSN_RE.test(compact)) {
      const k = normIssn(compact), j = BY_ISSN.get(k);
      if (j && !seen.has(j)) { list.push(j); seen.add(j); } else if (!j) missing.push(k);
      continue;
    }
    // 우선순위: 저널명·약어 완전일치 → 저널명·약어 부분일치 → 출판사 일치
    const exact = [], partial = [], pub = [];
    for (const j of DATA) {
      if (j._t === p || j._a === p) exact.push(j);
      else if (j._t.includes(p) || j._a.includes(p)) partial.push(j);
      else if (j._p.includes(p)) pub.push(j);
    }
    if (!exact.length && !partial.length && !pub.length) missing.push(p);
    for (const j of [...exact, ...partial, ...pub]) if (!seen.has(j)) { list.push(j); seen.add(j); }
  }
  return { list, missing, mode: parts.length > 1 ? "multi" : "name" };
}
 
function applyFilters(list) {
  const apc = $("#f-apc").checked, has = $("#f-has").checked;
  const max = +$("#f-max").value || null, min = +$("#f-min").value || null, rel = $("#f-rel").value;
  const basis = $("#f-basis").value;               // 기간 필터 기준: rec_acc(투고→승인) / rec_pub(투고→게재)
  return list.filter((j) => {
    const m = j[basis]?.median;
    if (apc && !j.apc) return false;
    if (has && m == null) return false;
    if (max && !(m != null && m <= max)) return false;
    if (min && !(m != null && m >= min)) return false;
    if (rel === "보통" && !["보통", "높음"].includes(j.reliability)) return false;
    if (rel === "높음" && j.reliability !== "높음") return false;
    return true;
  });
}
 
const KEYS = {
  title: (j) => j._t, issn: (j) => j.issn || j.eissn || null, publisher: (j) => j._p || null,
  median: (j) => j.rec_acc?.median ?? null, pubmed: (j) => j.acc_pub?.median ?? null,
  total: (j) => j.rec_pub?.median ?? null,
  n: (j) => j.rec_acc?.n ?? null, latest: (j) => j.latest_accepted || null, apc: (j) => (j.apc ? 0 : 1),
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
  if ((mode === "all" || mode === "name") && !sortKey) { sortKey = "median"; sortAsc = true; }
  sortView(); shown = PAGE;
 
  const q = $("#q").value.trim();
  const conds = [];
  if (q) conds.push(mode === "issn" ? `ISSN ${missing.length + list.length}건 조회` : `검색어 “${esc(q.slice(0, 60))}”`);
  if ($("#f-apc").checked) conds.push("전남대 APC 지원 목록 일치");
  if ($("#f-has").checked) conds.push(`${basisLabel} 기간 있음`);
  const basisLabel = $("#f-basis").value === "rec_pub" ? "투고→게재(총)" : "투고→승인";
  if ($("#f-max").value) conds.push(`${basisLabel} 중앙값 ${esc($("#f-max").value)}일 이내`);
  if ($("#f-min").value) conds.push(`${basisLabel} ${esc($("#f-min").value)}일 미만 제외`);
  if ($("#f-rel").value) conds.push(`신뢰도 ${esc($("#f-rel").value)} 이상`);
  const withStats = view.filter((j) => j.rec_acc).length;
  const hidden = list.length - view.length;
  $("#summary").innerHTML = `${conds.length ? conds.join(" · ") + " → " : "전체 저널 → "}💡 <b>${fmt(view.length)}</b>개 저널` +
    ` <span class="muted">(이 중 출판 기간 있음 ${fmt(withStats)}개)</span>` +
    (hidden > 0 && q ? ` <span class="muted">· 검색되었지만 필터로 숨겨진 저널 ${fmt(hidden)}개</span>` : "");
  $("#missing").innerHTML = missing.map((m) =>
    `<p class="warn">⚠️ ${esc(m)}은(는) 현재 데이터베이스(PMC 참여 저널 + 전남대 APC 지원 저널)에 등록되어 있지 않습니다.</p>`).join("");
  render();
}
 
const NA = '<span class="na">-</span>';
 
function nCell(j) {
  const ra = j.rec_acc;
  if (j.error) return '<span class="na">조회 오류</span>';
  if (!j.checked) return '<span class="na">수집 전</span>';
  if (!j.n_sampled) return '<span class="na">PubMed 기록 없음</span>';
  if (!ra) return `0<span class="rel">/ 수집 ${j.n_sampled}편 · 날짜 미제공</span>`;
  return `${ra.n}<span class="rel">/ 수집 ${j.n_sampled}편</span>`;
}
 
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
    return `<tr>
      <td>${esc(j.title)}${j.abbrev ? `<span class="abbr">${esc(j.abbrev)}</span>` : ""}</td>
      <td>${issn || NA}</td>
      <td>${esc(j.publisher) || NA}</td>
      <td class="r">${ra ? `<b>${ra.median}일</b>` : NA}${rel}</td>
      <td class="r">${j.acc_pub ? `${j.acc_pub.median}일` : NA}</td>
      <td class="r">${j.rec_pub ? `<b>${j.rec_pub.median}일</b>` : NA}</td>
      <td class="r">${nCell(j)}</td>
      <td>${esc(j.latest_accepted) || NA}</td>
      <td>${apc}</td></tr>`;
  });
  $("#tbl tbody").innerHTML = rows.join("") ||
    '<tr><td colspan="9" class="na" style="text-align:center;padding:24px">조건에 맞는 저널이 없습니다.</td></tr>';
  $("#more").classList.toggle("hidden", view.length <= shown);
  $("#more").textContent = `더 보기 (${fmt(Math.min(shown, view.length))} / ${fmt(view.length)})`;
}
 
init();
 

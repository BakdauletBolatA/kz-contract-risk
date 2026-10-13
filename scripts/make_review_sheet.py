"""Страница ручной проверки эталона извлечения: docs/gold_review.html.

Показывает договор, эталонные значения полей и там, где сильные модели
(DeepSeek, Grok) с эталоном не согласились, — их ответы. Сначала берутся все
спорные документы, потом добираются случайные из test, чтобы покрыть типы.

    python scripts/make_review_sheet.py [--n 22]
"""

# ruff: noqa: E501
from __future__ import annotations

import argparse
import glob
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from contract_risk.extraction.eval import load_gold  # noqa: E402

OUT = ROOT / "docs/gold_review.html"
STRONG = ("deepseek", "grok")
FORUM = {
    "kz_courts": "суды РК (общая подсудность)",
    "counterparty_location_court": "суд по месту нахождения стороны/истца/ответчика",
    "aifc_court": "Суд МФЦА",
    "foreign_arbitration": "зарубежный арбитраж",
}
ROLE = {
    "landlord": "арендодатель",
    "tenant": "арендатор",
    "supplier": "поставщик",
    "buyer": "покупатель",
    "contractor": "подрядчик",
    "customer": "заказчик",
}
LABELS = {
    "contract_type": "Тип договора",
    "contract_number": "Номер",
    "contract_date": "Дата",
    "city": "Город",
    "parties": "Стороны и БИН",
    "term_months": "Срок договора, мес.",
    "auto_renewal": "Автопродление",
    "price_amount": "Цена, ₸",
    "price_period": "Период цены",
    "payment_deadline_days": "Срок оплаты, дней",
    "payment_penalty_rate_percent_per_day": "Пеня за просрочку оплаты, % в день",
    "payment_penalty_cap_percent": "Предел пени, %",
    "dispute_forum": "Подсудность",
    "termination_notice_days": "Уведомление об отказе от договора, дней",
}
RULES = {
    "term_months": "Только если срок договора назван числом месяцев/лет. Срок датами («до 31.12»), срок работ, гарантия — null.",
    "auto_renewal": "true, если договор продлевается сам при отсутствии возражений. «Может быть продлён по соглашению» — false.",
    "price_amount": "Сумма в тенге, названная в договоре. Цена «в Спецификации» или ставка за кв. м — null.",
    "payment_deadline_days": "Дней на оплату после события. «До 5 числа», предоплата — null. Несколько сроков — срок остатка.",
    "payment_penalty_rate_percent_per_day": "Пеня за просрочку ОПЛАТЫ плательщиком, % в день. Пеня другой стороны не считается. Ставка не в % за день — null.",
    "payment_penalty_cap_percent": "Потолок пени в % от долга; нет потолка — null.",
    "dispute_forum": "Суд по месту нахождения/регистрации стороны или истца — counterparty_location; общий суд РК — kz_courts.",
    "termination_notice_days": "Срок уведомления об одностороннем отказе. Месяц = 30. «Без уведомления» = 0. Разные сроки у сторон — null; право только у одной стороны — её срок; отказ за неуплату не считается.",
    "contract_date": "Дата заключения договора из шапки.",
    "parties": "Две стороны: роль, название как в тексте, БИН/ИИН из реквизитов.",
}
EVIDENCE = {
    "contract_type": r"^\s*$|ДОГОВОР|ШАРТ",
    "contract_number": r"№",
    "contract_date": r"\b20\d\d\b",
    "city": r"\bг\.|қ\.|город",
    "parties": r"БИН|ИИН|БСН|ЖСН|именуем|далее|бұдан әрі|\((Арендодатель|Арендатор|Поставщик|Покупатель|Подрядчик|Заказчик)\)",
    "term_months": r"срок|мерзім|месяц|\bай\b|\bайды\b|действует до",
    "auto_renewal": r"продл|пролонг|ұзарт|автомат",
    "price_amount": r"тенге|теңге|₸",
    "price_period": r"тенге|теңге|₸",
    "payment_deadline_days": r"оплат|расчет|платеж|перечисля|вносит|төле|ақысын",
    "payment_penalty_rate_percent_per_day": r"пен[юяи]|неустой|штраф|тұрақсыз|өсімпұл|айыппұл",
    "payment_penalty_cap_percent": r"пен[юяи]|неустой|штраф|тұрақсыз|өсімпұл|айыппұл",
    "dispute_forum": r"суд|арбитр|сот|төрелік|спор|даулар|МФЦА|разногласи",
    "termination_notice_days": r"расторг|отказ|уведом|предупре|бұз|ескерт|прекращ|вправе|құқылы",
}


def join_wrapped(text: str) -> list[str]:
    t = re.sub(r"\s*\n\s*(?=(?![а-я]\))[а-яёәғқңөұүһі])", " ", text)
    return [ln.rstrip() for ln in t.splitlines() if ln.strip()]


def fmt(field: str, v) -> str:  # noqa: ANN001
    if v is None:
        return "— (в тексте нет)"
    if field == "parties":
        return "\n".join(
            f"{ROLE[p['role']]}: {p['name']} — {p['bin'] or 'БИН не указан'}" for p in v
        )
    if field == "dispute_forum":
        return FORUM[v]
    if isinstance(v, bool):
        return "да" if v else "нет"
    if isinstance(v, float):
        return f"{v:,.0f}".replace(",", " ") if field == "price_amount" else f"{v:g}"
    return str(v)


def latest_runs() -> dict[tuple[str, str], dict]:
    runs: dict[tuple[str, str], dict] = {}
    for p in sorted(glob.glob(str(ROOT / "evals/extraction/*.json"))):
        r = json.loads(Path(p).read_text(encoding="utf-8"))
        runs[(r["model"].split(":", 1)[0], r["split"])] = r
    return runs


def build(n_total: int) -> list[dict]:
    runs = latest_runs()
    gold = {s: load_gold(s) for s in ("dev", "test", "hard")}
    disputes: dict[str, dict[str, dict[str, str]]] = {}
    for (model, split), r in runs.items():
        if model not in STRONG:
            continue
        gd = {d.doc_id: d.labels for d in gold[split]}
        for d in r["docs"]:
            for f, o in d["outcome"].items():
                if o in ("correct",):
                    continue
                pred = d["prediction"]
                v = pred.get(f) if pred and not f.startswith("parties.") else None
                key = "parties" if f.startswith("parties.") else f
                if key == "parties":
                    v = pred["parties"] if pred else None
                disputes.setdefault(d["doc_id"], {}).setdefault(key, {})[model] = fmt(key, v)
                gd[d["doc_id"]]  # noqa: B018 - проверка существования
    all_docs = {d.doc_id: d for s in gold.values() for d in s}
    order = {"test": 0, "hard": 1, "dev": 2}
    disputed = sorted(disputes, key=lambda i: (order[all_docs[i].split], i))
    chosen = list(disputed)
    rng = random.Random(5)
    by_kind: dict[str, list[str]] = {}
    for d in gold["test"]:
        if d.doc_id not in disputes:
            by_kind.setdefault(d.doc_id.rsplit("_test_", 1)[0], []).append(d.doc_id)
    for ids in by_kind.values():
        rng.shuffle(ids)
    # по кругу по типам договоров, чтобы в выборку попал казахский и каждый тип
    while len(chosen) < n_total and any(by_kind.values()):
        for kind in ("lease_kk", "supply_ru", "works_ru", "lease_ru"):
            if by_kind.get(kind) and len(chosen) < n_total:
                chosen.append(by_kind[kind].pop())
    cards = []
    for did in chosen[:n_total]:
        d = all_docs[did]
        lines = join_wrapped(d.text)
        fields = []
        for f, label in LABELS.items():
            pat = re.compile(EVIDENCE.get(f, r"$^"), re.IGNORECASE)
            hits = [
                i
                for i, ln in enumerate(lines)
                if pat.search(ln) and not re.match(r"^\d+\.\s+[А-ЯЁӘҒҚҢӨҰҮҺІ ,\-/]+$", ln)
            ]
            if f in ("contract_type", "contract_number", "contract_date", "city"):
                hits = [i for i in hits if i < 3]
            if f == "contract_type":
                hits = [0]
            fields.append(
                {
                    "key": f,
                    "label": label,
                    "gold": fmt(f, d.labels[f]),
                    "rule": RULES.get(f, ""),
                    "lines": hits,
                    "disputed": disputes.get(did, {}).get(f, {}),
                }
            )
        cards.append(
            {
                "id": did,
                "split": d.split,
                "lines": lines,
                "fields": fields,
                "n_disputed": len(disputes.get(did, {})),
            }
        )
    return cards


PAGE = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Проверка эталона</title>
<style>
:root{--bg:#fafaf8;--card:#fff;--ink:#1d1d1b;--mut:#6b6b66;--line:#e3e2dc;--acc:#2f5fd0;--ok:#1f7a45;--bad:#b3261e;--unsure:#8a6100;--hl:#fff3c2;--dis:#fdecea}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#161615;--card:#1f1f1d;--ink:#ecebe6;--mut:#a3a29a;--line:#34332f;--acc:#8fb0ff;--ok:#6fd49a;--bad:#ff9a92;--unsure:#e8c26a;--hl:#4a3f12;--dis:#4a2320}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 16px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
header h1{font-size:17px;margin:0}.prog{color:var(--mut);font-size:14px}
.bar{flex:1;min-width:120px;height:6px;background:var(--line);border-radius:3px;overflow:hidden}.bar i{display:block;height:100%;background:var(--acc);width:0}
button{font:inherit;cursor:pointer;border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:6px;padding:4px 10px}
button:hover{border-color:var(--acc)}button.primary{background:var(--acc);color:#fff;border-color:var(--acc)}
main{max-width:1180px;margin:0 auto;padding:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;margin:0 0 20px;overflow:hidden}
.card h2{margin:0;padding:10px 14px;font-size:15px;display:flex;gap:10px;align-items:center;border-bottom:1px solid var(--line);flex-wrap:wrap}
.tag{font-size:12px;border:1px solid var(--line);border-radius:10px;padding:0 8px;color:var(--mut)}.tag.d{color:var(--bad);border-color:var(--bad)}
.grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
@media (max-width:820px){.grid{grid-template-columns:1fr}}
.text{padding:10px 14px;border-right:1px solid var(--line);font-size:13.5px;max-height:620px;overflow:auto}
.line{padding:1px 4px;border-radius:3px;white-space:pre-wrap}.line.hl{background:var(--hl)}
.fields{padding:6px 10px}
.f{padding:8px 4px;border-bottom:1px solid var(--line);cursor:pointer}.f:last-child{border:0}
.f.dis{background:var(--dis);border-radius:6px}.f.sel{outline:2px solid var(--acc);border-radius:6px}
.fl{display:flex;justify-content:space-between;gap:8px;align-items:baseline}.fn{color:var(--mut);font-size:12.5px}
.fv{font-weight:600;white-space:pre-wrap}.mod{font-size:13px;color:var(--bad)}
.rule{font-size:12px;color:var(--mut);margin-top:2px}
.b{display:inline-flex;gap:4px}.b button{padding:0 8px;min-width:30px}
.b button.on.ok{background:var(--ok);color:#fff;border-color:var(--ok)}.b button.on.bad{background:var(--bad);color:#fff;border-color:var(--bad)}.b button.on.un{background:var(--unsure);color:#fff;border-color:var(--unsure)}
.fix{width:100%;margin-top:4px;font:inherit;padding:3px 6px;border:1px solid var(--bad);border-radius:5px;background:var(--card);color:var(--ink);display:none}
.fix.show{display:block}
dialog{border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink);width:min(760px,92vw)}
textarea{width:100%;height:320px;font:13px/1.4 ui-monospace,monospace;background:var(--bg);color:var(--ink);border:1px solid var(--line);border-radius:6px}
.hint{color:var(--mut);font-size:13px;margin:0 0 16px}
</style></head><body>
<header><h1>Проверка эталона извлечения</h1><span class="prog" id="prog"></span><div class="bar"><i id="bar"></i></div>
<button class="primary" id="export">Результат для отправки</button></header>
<main><p class="hint">В каждом договоре сверьте значения справа с текстом слева. ✓ — эталон верен, ✗ — ошибка (впишите, как правильно), ? — неясно, правило не покрывает.
Розовым выделены поля, где DeepSeek или Grok дали другой ответ — там ошибка разметки вероятнее. Клик по полю подсвечивает строки текста, на которых оно основано.
«Весь документ верен» ставит ✓ на все ещё не отмеченные поля. Отметки сохраняются в браузере.</p><div id="cards"></div></main>
<dialog id="dlg"><h3 style="margin-top:0">Скопируйте и отправьте в чат</h3><textarea id="out" readonly></textarea>
<p><button class="primary" id="copy">Скопировать</button> <button id="close">Закрыть</button> <span id="copied" class="prog"></span></p></dialog>
<script id="data" type="application/json">__DATA__</script>
<script>
const CARDS=JSON.parse(document.getElementById('data').textContent);
let S={};try{S=JSON.parse(localStorage.getItem('goldReview.v1')||'{}')}catch(e){}
const save=()=>{try{localStorage.setItem('goldReview.v1',JSON.stringify(S))}catch(e){}};
const el=(t,c,x)=>{const e=document.createElement(t);if(c)e.className=c;if(x!==undefined)e.textContent=x;return e};
const st=(id,f)=>(S[id]||{})[f]||{};
function set(id,f,patch){S[id]=S[id]||{};S[id][f]=Object.assign(S[id][f]||{},patch);save();paint()}
function docDone(c){return c.fields.every(f=>st(c.id,f.key).v)}
function paint(){
  const done=CARDS.filter(docDone).length;
  document.getElementById('prog').textContent=`проверено ${done} из ${CARDS.length}`;
  document.getElementById('bar').style.width=(100*done/CARDS.length)+'%';
  CARDS.forEach(c=>{
    c.fields.forEach(f=>{
      const s=st(c.id,f.key),row=document.getElementById(`f-${c.id}-${f.key}`);
      row.querySelectorAll('.b button').forEach(b=>b.classList.toggle('on',b.dataset.v===s.v));
      const fx=row.querySelector('.fix');fx.classList.toggle('show',s.v==='bad');
    });
    document.getElementById(`t-${c.id}`).classList.toggle('d',docDone(c));
  });
}
function mark(c,f,lines,row){
  const t=document.getElementById(`txt-${c.id}`);
  t.querySelectorAll('.line').forEach((l,i)=>l.classList.toggle('hl',lines.includes(i)));
  document.querySelectorAll(`#card-${c.id} .f`).forEach(r=>r.classList.toggle('sel',r===row));
  const first=t.querySelectorAll('.line')[lines[0]];if(first)first.scrollIntoView({block:'nearest'});
}
const root=document.getElementById('cards');
CARDS.forEach(c=>{
  const card=el('section','card');card.id='card-'+c.id;
  const h=el('h2');h.append(el('span','',c.id),el('span','tag',c.split));
  if(c.n_disputed)h.append(el('span','tag d',`спорных полей: ${c.n_disputed}`));
  const t=el('span','tag','проверен');t.id='t-'+c.id;t.style.display='none';h.append(t);
  const all=el('button','', 'Весь документ верен');all.style.marginLeft='auto';
  all.onclick=()=>{c.fields.forEach(f=>{if(!st(c.id,f.key).v){S[c.id]=S[c.id]||{};S[c.id][f.key]=Object.assign(S[c.id][f.key]||{},{v:'ok'})}});save();paint()};
  h.append(all);card.append(h);
  const g=el('div','grid'),tx=el('div','text');tx.id='txt-'+c.id;
  c.lines.forEach(l=>tx.append(el('div','line',l)));
  const fs=el('div','fields');
  c.fields.forEach(f=>{
    const r=el('div','f'+(Object.keys(f.disputed).length?' dis':''));r.id=`f-${c.id}-${f.key}`;
    const top=el('div','fl'),left=el('div');left.append(el('div','fn',f.label),el('div','fv',f.gold));
    const b=el('div','b');
    [['ok','✓'],['bad','✗'],['un','?']].forEach(([k,sym])=>{const bt=el('button',k,sym);bt.dataset.v=k;
      bt.onclick=e=>{e.stopPropagation();set(c.id,f.key,{v:st(c.id,f.key).v===k?undefined:k})};b.append(bt)});
    top.append(left,b);r.append(top);
    Object.entries(f.disputed).forEach(([m,v])=>r.append(el('div','mod',`${m}: ${v.replace(/\\n/g,' · ')}`)));
    if(f.rule)r.append(el('div','rule',f.rule));
    const fx=el('input','fix');fx.placeholder='как правильно / комментарий';fx.value=st(c.id,f.key).note||'';
    fx.onclick=e=>e.stopPropagation();fx.oninput=()=>{S[c.id]=S[c.id]||{};S[c.id][f.key]=Object.assign(S[c.id][f.key]||{},{note:fx.value});save()};
    r.append(fx);r.onclick=()=>mark(c,f,f.lines,r);fs.append(r);
  });
  g.append(tx,fs);card.append(g);root.append(card);
});
paint();
document.getElementById('export').onclick=()=>{
  const bad=[],un=[];let done=0;
  CARDS.forEach(c=>{if(docDone(c))done++;c.fields.forEach(f=>{const s=st(c.id,f.key);
    const line=`- ${c.id} | ${f.key} | эталон: ${f.gold.replace(/\\n/g,'; ')}`+(s.note?` | правильно: ${s.note}`:'');
    if(s.v==='bad')bad.push(line);if(s.v==='un')un.push(line)})});
  const touched=CARDS.filter(c=>c.fields.some(f=>st(c.id,f.key).v)).length;
  document.getElementById('out').value=`Проверка эталона: полностью проверено ${done} из ${CARDS.length}, затронуто ${touched}.\\n\\nОшибки эталона (${bad.length}):\\n${bad.join('\\n')||'—'}\\n\\nНеясно (${un.length}):\\n${un.join('\\n')||'—'}\\n`;
  document.getElementById('dlg').showModal();
};
document.getElementById('close').onclick=()=>document.getElementById('dlg').close();
document.getElementById('copy').onclick=async()=>{const o=document.getElementById('out');o.select();
  try{await navigator.clipboard.writeText(o.value);document.getElementById('copied').textContent='скопировано'}catch(e){document.execCommand('copy');document.getElementById('copied').textContent='выделено — нажмите Cmd+C'}};
</script></body></html>
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=22)
    args = ap.parse_args()
    cards = build(args.n)
    data = json.dumps(cards, ensure_ascii=False).replace("</", "<\\/")
    OUT.write_text(PAGE.replace("__DATA__", data), encoding="utf-8")
    print(
        f"{OUT.relative_to(ROOT)}: {len(cards)} договоров, спорных {sum(1 for c in cards if c['n_disputed'])}"
    )
    for c in cards:
        print(f"  {c['id']:<22}{c['split']:<6}{c['n_disputed']}")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""把 put_yield_ranking.py 的排行榜結果，產生成一個獨立網頁（本機預覽用，比照cbmon.pages.dev視覺風格）。
輸出到 public_put_yield/index.html，跟 public/(cbmon強贖監測表)是分開的資料夾，互不影響。

三層分類（沿用「過濾條件要明講排除了什麼」的教訓，不隱藏被過濾掉的候選）：
  1. 乾淨候選：今日有成交(volume>0) 且非KY股
  2. KY股候選：今日有成交，但為KY股（境外註冊查核力較弱，需額外注意）
  3. 零成交候選：volume=0，CB價格可能是舊價，數字僅供參考

用法：python build_put_yield_page.py
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from put_yield_ranking import load_rows, build_ranking, DEFAULT_CSV, BASE

OUT_DIR = BASE / "public_put_yield"
OUT_FILE = OUT_DIR / "index.html"

MIN_YTP = -999  # 不預先篩，全部有賣回日的都列出，交給頁面上的分層呈現


def row_to_js(r, rank):
    risk = "ky" if r["_is_ky"] else ""
    return (
        f'    [{rank},"{r["code"]}","{r["name"]}",{r["conv_price"]:.2f},{r["stock_price"]:.2f},'
        f'{r["conv_value"]:.2f},{r["cb_price"]:.2f},{r["_simple_return_pct"]:.2f},'
        f'{r["ytp_pct"]:.2f},"{r["next_put_date"]}",{r["next_put_price"]:.2f},'
        f'{r["_days_to_put"]},{(r["volume"] or 0):.0f},"{r["collateral"]}","{risk}"],'
    )


def build_tier_js(rows):
    return "\n".join(row_to_js(r, i + 1) for i, r in enumerate(rows))


HEADER_COLS = [
    ("#", 0), ("代碼", 1), ("名稱", 2), ("轉換價", 3), ("現股價", 4), ("CB理論價", 5),
    ("CB價格", 6), ("賣回報酬%", 7), ("賣回年化%", 8), ("最近賣回日", 9), ("賣回價", 10),
    ("距今天數", 11), ("今日量", 12), ("擔保", 13),
]


def build_header_row():
    return "".join(
        f'<th class="sortable" data-idx="{idx}">{label}<span class="arrow-sort">↕</span></th>'
        for label, idx in HEADER_COLS
    )


def main():
    rows = load_rows(DEFAULT_CSV)
    ranking = build_ranking(rows)

    clean = [r for r in ranking if (r["volume"] or 0) > 0 and not r["_is_ky"]]
    ky_only = [r for r in ranking if (r["volume"] or 0) > 0 and r["_is_ky"]]
    stale = [r for r in ranking if (r["volume"] or 0) == 0]

    OUT_DIR.mkdir(exist_ok=True)
    html = HTML_TEMPLATE.format(
        today=date.today().isoformat(),
        total=len(rows),
        computable=len(ranking),
        clean_count=len(clean),
        ky_count=len(ky_only),
        stale_count=len(stale),
        top_ytp=f"{ranking[0]['ytp_pct']:.1f}" if ranking else "—",
        clean_js=build_tier_js(clean),
        ky_js=build_tier_js(ky_only),
        stale_js=build_tier_js(stale),
        header_row=build_header_row(),
    )
    OUT_FILE.write_text(html, encoding="utf-8")
    print(f"已寫出：{OUT_FILE}")
    print(f"乾淨候選 {len(clean)} / KY股候選 {len(ky_only)} / 零成交候選 {len(stale)}（共 {len(ranking)} 檔可算）")


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>可轉債賣回報酬率排行榜</title>
<style>
  :root {{
    --paper: #F2F1EA; --paper-raised: #FFFFFF; --ink: #1C2126; --ink-soft: #565F68; --ink-faint: #8A8F94;
    --line: #D8D5C8; --line-soft: #E6E3D8; --accent: #1E5F6E; --accent-soft: #DCE9EA;
    --hot: #B23A2E; --hot-soft: #F6E2DE; --safe: #4B7A3F; --safe-soft: #E4EDDD;
    --muted: #8A8578; --muted-soft: #EAE7DC;
    --shadow: 0 1px 2px rgba(28,33,38,0.06), 0 4px 14px rgba(28,33,38,0.05); --radius: 10px;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --paper: #14181A; --paper-raised: #1B2022; --ink: #EDEAE0; --ink-soft: #A8A296; --ink-faint: #6E7873;
      --line: #2B322F; --line-soft: #232928; --accent: #5CC2B8; --accent-soft: #1E3336;
      --hot: #E2685A; --hot-soft: #3A2320; --safe: #8FC178; --safe-soft: #23301C;
      --muted: #7C7768; --muted-soft: #24231D;
      --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 6px 20px rgba(0,0,0,0.35);
    }}
  }}
  * {{ box-sizing: border-box; }}
  html, body {{
    margin: 0; padding: 0; background: var(--paper); color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, "PingFang TC", "Noto Sans TC", "Microsoft JhengHei", "Segoe UI", system-ui, sans-serif;
    -webkit-font-smoothing: antialiased;
  }}
  .num {{ font-family: ui-monospace, "SF Mono", "Cascadia Mono", "Roboto Mono", "Consolas", monospace; font-variant-numeric: tabular-nums; }}
  .wrap {{ max-width: 1040px; margin: 0 auto; padding: 28px 18px 80px; }}
  header.top {{ padding: 6px 0 22px; border-bottom: 1px solid var(--line); margin-bottom: 22px; }}
  .eyebrow {{ font-size: 12px; letter-spacing: 0.08em; color: var(--accent); font-weight: 700; text-transform: uppercase; margin: 0 0 8px; }}
  h1 {{ font-size: clamp(22px, 4.2vw, 30px); line-height: 1.25; margin: 0 0 10px; font-weight: 800; letter-spacing: -0.01em; text-wrap: balance; }}
  .sub {{ color: var(--ink-soft); font-size: 14.5px; line-height: 1.6; max-width: 68ch; margin: 0; }}
  .meta-row {{ display: flex; flex-wrap: wrap; gap: 6px 14px; margin-top: 14px; font-size: 12.5px; color: var(--ink-faint); }}
  .meta-row span {{ display: inline-flex; align-items: center; gap: 5px; }}
  .dot {{ width: 6px; height: 6px; border-radius: 50%; background: var(--accent); display: inline-block; }}
  .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin-bottom: 26px; }}
  .stat {{ background: var(--paper-raised); border: 1px solid var(--line); border-radius: var(--radius); padding: 14px 16px; box-shadow: var(--shadow); }}
  .stat .n {{ font-size: 24px; font-weight: 800; letter-spacing: -0.01em; }}
  .stat .l {{ font-size: 12px; color: var(--ink-soft); margin-top: 2px; }}
  section.block {{ margin-bottom: 34px; }}
  .block-head {{ display: flex; align-items: baseline; justify-content: space-between; gap: 10px; margin-bottom: 8px; flex-wrap: wrap; }}
  .block-head h2 {{ font-size: 16px; margin: 0; font-weight: 800; }}
  .block-head .count {{ font-size: 12.5px; color: var(--ink-faint); }}
  .block-note {{ font-size: 12.5px; color: var(--ink-soft); margin: 0 0 14px; line-height: 1.6; }}
  .table-scroll {{ overflow-x: auto; background: var(--paper-raised); border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--shadow); }}
  table.rank-table {{ width: 100%; border-collapse: collapse; font-size: 13px; white-space: nowrap; }}
  table.rank-table th {{
    text-align: right; font-size: 11px; color: var(--ink-faint); font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.03em; padding: 8px 10px; border-bottom: 1px solid var(--line); position: sticky; top: 0; background: var(--paper-raised);
  }}
  table.rank-table th:nth-child(1), table.rank-table th:nth-child(2), table.rank-table th:nth-child(3) {{ text-align: left; }}
  table.rank-table th.sortable {{ cursor: pointer; user-select: none; }}
  table.rank-table th.sortable:hover {{ color: var(--ink); }}
  table.rank-table th.sortable .arrow-sort {{ margin-left: 4px; font-size: 9px; opacity: 0.35; }}
  table.rank-table th.sortable.active .arrow-sort {{ opacity: 1; color: var(--accent); }}
  table.rank-table td {{ padding: 8px 10px; border-bottom: 1px solid var(--line-soft); text-align: right; }}
  table.rank-table td:nth-child(1) {{ color: var(--ink-faint); }}
  table.rank-table td:nth-child(2) {{ text-align: left; color: var(--ink-faint); }}
  table.rank-table td:nth-child(3) {{ text-align: left; font-weight: 700; }}
  table.rank-table td.ytp {{ font-weight: 800; color: var(--accent); }}
  .chip {{ font-size: 10.5px; font-weight: 700; padding: 2px 7px; border-radius: 999px; white-space: nowrap; display: inline-flex; margin-left: 6px; }}
  .chip.ky {{ background: var(--hot-soft); color: var(--hot); }}
  details.tier {{ background: var(--paper-raised); border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--shadow); }}
  details.tier summary {{ cursor: pointer; padding: 14px 16px; font-weight: 700; font-size: 14px; list-style: none; display: flex; align-items: center; justify-content: space-between; }}
  details.tier summary::-webkit-details-marker {{ display: none; }}
  details.tier summary .arrow {{ transition: transform 0.15s ease; color: var(--ink-faint); }}
  details.tier[open] summary .arrow {{ transform: rotate(90deg); }}
  footer {{ margin-top: 40px; padding-top: 18px; border-top: 1px solid var(--line); font-size: 12px; color: var(--ink-faint); line-height: 1.7; }}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <p class="eyebrow">可轉債（CB）賣回報酬率排行榜</p>
    <h1>抱到最近賣回日，年化能拿多少？</h1>
    <p class="sub">
      比照悠債網（Yobond）「CB個股與（賣回）報酬率排行榜」的算法：<b>賣回報酬率 = (最近賣回價格 − CB價格) ÷ CB價格</b>，
      再依剩餘天數換算成年化。跟先前研究的溢價套利路徑不同，這個策略<b>不需要借券、不需要放空正股</b>——
      只是買進CB、抱到最近一次賣回日執行賣回權，領回保證的賣回價，前提是公司到時候沒有違約。
    </p>
    <p class="sub" style="margin-top:10px;">
      真正該擔心的只剩兩件事：①CB本身有沒有成交量能用這個價格買到（零成交＝可能是舊價，見下方第三層）
      ②公司會不會在賣回日前違約（此表無TCRI信用評等欄位，KY股已額外標註但仍需自行查證公司治理狀況）。
    </p>
    <div class="meta-row">
      <span><span class="dot"></span>資料來源：XQ全球贏家「可轉債總表」CSV匯出</span>
      <span>產生日期 {today}</span>
      <span>單日快照，非連續追蹤</span>
    </div>
  </header>

  <div class="stats">
    <div class="stat"><div class="n num">{total}</div><div class="l">CSV總檔數</div></div>
    <div class="stat"><div class="n num">{computable}</div><div class="l">有賣回日可算(未過期)</div></div>
    <div class="stat"><div class="n num" style="color:var(--safe)">{clean_count}</div><div class="l">乾淨候選(有成交+非KY)</div></div>
    <div class="stat"><div class="n num">{ky_count}</div><div class="l">KY股候選(有成交)</div></div>
    <div class="stat"><div class="n num" style="color:var(--ink-faint)">{stale_count}</div><div class="l">零成交(舊價，僅供參考)</div></div>
    <div class="stat"><div class="n num" style="color:var(--accent)">{top_ytp}%</div><div class="l">目前最高賣回年化報酬率</div></div>
  </div>

  <section class="block">
    <div class="block-head"><h2>乾淨候選 — 今日有成交、非KY股</h2><span class="count" id="cleanCount"></span></div>
    <p class="block-note">依「賣回年化報酬率」由高到低排序，這批數字最可信，優先看這裡。</p>
    <div class="table-scroll"><table class="rank-table">
      <thead><tr>{header_row}</tr></thead>
      <tbody id="cleanRows"></tbody>
    </table></div>
  </section>

  <section class="block">
    <details class="tier">
      <summary>KY股候選（有成交，但境外註冊查核力較弱，需額外注意）<span class="arrow">▸</span></summary>
      <div class="table-scroll"><table class="rank-table">
        <thead><tr>{header_row}</tr></thead>
        <tbody id="kyRows"></tbody>
      </table></div>
    </details>
  </section>

  <section class="block">
    <details class="tier">
      <summary>零成交候選（volume=0，CB價格可能是舊價，數字僅供參考）<span class="arrow">▸</span></summary>
      <div class="table-scroll"><table class="rank-table">
        <thead><tr>{header_row}</tr></thead>
        <tbody id="staleRows"></tbody>
      </table></div>
    </details>
  </section>

  <footer>
    算法比照悠債網（Yobond）CB賣回報酬率排行榜，已用廣華二KY（102.45→106.12，129天）反算驗證年化數字與XQ原始ytp_pct欄位吻合。<br>
    賣回報酬率＝(最近賣回價格−CB價格)÷CB價格；賣回年化報酬率＝(1+賣回報酬率)^(365/距今天數)−1（即XQ「提前賣回收益率」）。<br>
    本表只反映「公司不違約」情境下的保證報酬，不是無風險套利；違約歷史與KY股風險，詳見本機可轉債套利研究記憶。<br>
    資料來源：XQ全球贏家（嘉實資訊）「可轉債總表」桌面看盤軟體匯出CSV，非公開API，需人工在XQ按匯出才能更新。本表僅供研究與觀察，非投資建議。
  </footer>
</div>

<script>
  const clean = [
{clean_js}
  ];
  const kyOnly = [
{ky_js}
  ];
  const stale = [
{stale_js}
  ];

  function renderRows(id, data) {{
    const el = document.getElementById(id);
    el.innerHTML = data.map(([rank, code, name, convPrice, stockPrice, convValue, cbPrice, simpleReturn, ytp, putDate, putPrice, days, volume, collateral, risk]) => `
      <tr>
        <td class="num">${{rank}}</td>
        <td class="num">${{code}}</td>
        <td>${{name}}${{risk === 'ky' ? '<span class="chip ky">KY</span>' : ''}}</td>
        <td class="num">${{convPrice.toFixed(2)}}</td>
        <td class="num">${{stockPrice.toFixed(2)}}</td>
        <td class="num">${{convValue.toFixed(2)}}</td>
        <td class="num">${{cbPrice.toFixed(2)}}</td>
        <td class="num">${{simpleReturn.toFixed(2)}}</td>
        <td class="num ytp">${{ytp.toFixed(2)}}</td>
        <td class="num">${{putDate}}</td>
        <td class="num">${{putPrice.toFixed(2)}}</td>
        <td class="num">${{days}}</td>
        <td class="num">${{volume}}</td>
        <td class="num">${{collateral}}</td>
      </tr>`).join('');
  }}

  renderRows('cleanRows', clean);
  renderRows('kyRows', kyOnly);
  renderRows('staleRows', stale);
  document.getElementById('cleanCount').textContent = clean.length + ' 檔';

  const NUMERIC_COLS = new Set([0, 3, 4, 5, 6, 7, 8, 10, 11, 12]);

  function attachSort(tbodyId, data) {{
    const tbody = document.getElementById(tbodyId);
    const table = tbody.closest('table');
    const ths = table.querySelectorAll('thead th.sortable');
    const sortState = {{ idx: null, dir: 1 }};
    ths.forEach(th => {{
      th.addEventListener('click', () => {{
        const idx = parseInt(th.dataset.idx, 10);
        sortState.dir = (sortState.idx === idx) ? sortState.dir * -1 : 1;
        sortState.idx = idx;
        data.sort((a, b) => {{
          const va = a[idx], vb = b[idx];
          const cmp = NUMERIC_COLS.has(idx) ? (va - vb) : String(va).localeCompare(String(vb), 'zh-Hant');
          return cmp * sortState.dir;
        }});
        renderRows(tbodyId, data);
        ths.forEach(t => {{ t.classList.remove('active'); t.querySelector('.arrow-sort').textContent = '↕'; }});
        th.classList.add('active');
        th.querySelector('.arrow-sort').textContent = sortState.dir === 1 ? '▲' : '▼';
      }});
    }});
  }}

  attachSort('cleanRows', clean);
  attachSort('kyRows', kyOnly);
  attachSort('staleRows', stale);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()

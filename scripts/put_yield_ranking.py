# -*- coding: utf-8 -*-
"""賣回報酬率排行榜——比照悠債網(Yobond)「CB個股與(賣回)報酬率排行榜」的算法，
套用在xq_cb_master.csv上（不需要借券/放空，純粹買進CB抱到最近賣回日執行賣回權）。

算法（已用xq_cb_master.csv裡的ytp_pct反算驗證吻合，如廣華二KY 102.45→106.12/129天=10.47% vs 資料裡10.46%）：
  賣回報酬率(簡單)   = (最近賣回價格 - CB價格) / CB價格
  賣回年化報酬率     = (1+賣回報酬率)^(365/距最近賣回日天數) - 1  （即CSV裡現成的ytp_pct欄位）

用法範例：
  python put_yield_ranking.py                  # 全部候選，依賣回年化報酬率排序
  python put_yield_ranking.py --top 20
  python put_yield_ranking.py --min-ytp 5       # 只看年化5%以上
  python put_yield_ranking.py --require-volume  # 只留今日有成交(volume>0)的，排除舊價
  python put_yield_ranking.py --exclude-ky      # 排除KY股(境外註冊，主管機關查核力較弱)
  python put_yield_ranking.py --clean           # 乾淨候選＝require-volume + exclude-ky 一次到位

注意（沿用[[project-cb-arbitrage-research]]已驗證的執行面教訓）：
  - volume=0代表cb_price可能是舊價，賣回報酬率數字不可信，預設仍會列出但標「無今日成交」，
    加 --require-volume 可直接濾掉。
  - 本排行榜完全不涉及轉換/放空，因此閉鎖期、停止轉換窗口、B層注意股/處置股都不影響「買進抱到賣回日」
    這個策略；真正該留意的是①CB本身流動性(能不能用這個價格買到) ②公司信用風險(TCRI/擔保/是否KY股，
    賣回權只在公司不違約時才有意義)。
"""
import argparse
import csv
from datetime import date, datetime
from pathlib import Path

BASE = Path(r"C:\Users\Evan\Desktop\Claude工作區\可轉債套利研究")
DEFAULT_CSV = BASE / "xq_cb_master.csv"


def parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y/%m/%d").date()
    except ValueError:
        return None


def load_rows(path):
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in ("cb_price", "volume", "stock_price", "conv_value", "premium_pct",
                   "conv_price", "next_put_price", "ytp_pct", "ytm_pct", "converted_pct"):
            v = r.get(k)
            r[k] = float(v) if v not in (None, "") else None
        r["_next_put_date"] = parse_date(r.get("next_put_date"))
    return rows


def build_ranking(rows, today=None):
    today = today or date.today()
    out = []
    for r in rows:
        if r["cb_price"] is None or r["next_put_price"] is None or r["_next_put_date"] is None:
            continue
        days = (r["_next_put_date"] - today).days
        if days <= 0:
            continue
        simple_return = (r["next_put_price"] - r["cb_price"]) / r["cb_price"] * 100
        r["_days_to_put"] = days
        r["_simple_return_pct"] = simple_return
        r["_is_ky"] = r["name"].rstrip().endswith("KY")
        out.append(r)
    out.sort(key=lambda r: (r["ytp_pct"] if r["ytp_pct"] is not None else -999), reverse=True)
    return out


def build_parser():
    p = argparse.ArgumentParser(description="賣回報酬率排行榜（比照悠債網CB賣回報酬率排行榜）")
    p.add_argument("--csv", default=str(DEFAULT_CSV), help="輸入CSV路徑（xq_cb_master.csv）")
    p.add_argument("--top", type=int, default=None, help="只顯示前N名")
    p.add_argument("--min-ytp", type=float, default=None, help="賣回年化報酬率下限(%%)")
    p.add_argument("--require-volume", action="store_true", help="只留今日有成交(volume>0)的候選")
    p.add_argument("--exclude-ky", action="store_true", help="排除KY股（境外註冊，主管機關查核力較弱）")
    p.add_argument("--clean", action="store_true", help="乾淨候選＝require-volume + exclude-ky 一次到位")
    return p


if __name__ == "__main__":
    args = build_parser().parse_args()
    if args.clean:
        args.require_volume = True
        args.exclude_ky = True
    rows = load_rows(args.csv)
    ranking = build_ranking(rows)

    if args.min_ytp is not None:
        ranking = [r for r in ranking if r["ytp_pct"] is not None and r["ytp_pct"] >= args.min_ytp]
    if args.require_volume:
        ranking = [r for r in ranking if r["volume"] is not None and r["volume"] > 0]
    if args.exclude_ky:
        ranking = [r for r in ranking if not r["_is_ky"]]
    if args.top is not None:
        ranking = ranking[:args.top]

    print(f"共 {len(rows)} 檔，可算賣回報酬率(有賣回日且未過期) {len(build_ranking(rows))} 檔，本次顯示 {len(ranking)} 檔\n")
    print(f"{'代碼':8s} {'名稱':12s} {'轉換價':>7s} {'現股價':>7s} {'CB理論價':>8s} {'CB價格':>7s} "
          f"{'賣回報酬%':>8s} {'賣回年化%':>8s} {'最近賣回日':10s} {'賣回價':>7s} {'距今天數':>6s} "
          f"{'今日量':>6s} {'擔保':6s} {'風險旗標'}")
    print("-" * 140)
    for r in ranking:
        vol_flag = "" if (r["volume"] or 0) > 0 else "*"
        risk = "KY股" if r["_is_ky"] else ""
        print(f"{r['code']:8s} {r['name']:12s} "
              f"{r['conv_price'] if r['conv_price'] is not None else float('nan'):7.2f} "
              f"{r['stock_price'] if r['stock_price'] is not None else float('nan'):7.2f} "
              f"{r['conv_value'] if r['conv_value'] is not None else float('nan'):8.2f} "
              f"{r['cb_price']:7.2f} "
              f"{r['_simple_return_pct']:8.2f} "
              f"{r['ytp_pct'] if r['ytp_pct'] is not None else float('nan'):8.2f} "
              f"{r['next_put_date']:10s} "
              f"{r['next_put_price']:7.2f} "
              f"{r['_days_to_put']:6d} "
              f"{(r['volume'] if r['volume'] is not None else 0):6.0f}{vol_flag} "
              f"{r['collateral']:6s} {risk}")
    print("\n* = 今日無成交（volume=0），CB價格可能是舊價，賣回報酬率數字需人工核實現價後才能信")
    print("風險旗標僅涵蓋KY股一項（境外註冊查核力較弱）；TCRI信用評等/公司治理狀況本CSV無此欄位，仍需另外查證。")

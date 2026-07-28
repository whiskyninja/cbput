# -*- coding: utf-8 -*-
"""把 Evan 每天手動存到 Drea\\XQ\\ 的「可轉債總表」原始CSV，解析成一天的封存快照，
寫進 public_put_yield/archive/data/{date}.json，並更新 archive/dates.json 索引，
index.html 本身是一次性手寫的靜態頁面（改成client端fetch archive/資料渲染），
這支之後每天重跑只會新增/更新 archive/data 底下的 JSON，不會再動 index.html。

跟舊版 build_put_yield_page.py（吃 thefew.tw+TDCC 自動管線）不同：
這支改吃 XQ 手動匯出（xq_cb_master.csv 格式），原因是實測發現同一天 thefew 的
cb_price/成交量跟 XQ 對不上（見2026-07-28查證：北基八同日CB價100.50 vs 101.05,
成交量0 vs 1），會汙染「跟前一天比」的比較基準。XQ是本專案已確立的唯一可靠源。

用法：
  python build_put_yield_archive.py "C:\\Users\\Evan\\我的雲端硬碟\\Drea\\XQ\\20260728.csv"
  python build_put_yield_archive.py <原始CSV路徑> --date 2026-07-28   # 檔名抓不到日期時手動指定

Evan說「偶爾會漏掉」，所以刻意不做「昨天沒資料就自動延用前一天」的假資料填補——
沒跑這支就是沒有那一天的封存，頁面上的「較前次」永遠比對「最近一次實際存在的封存日」，
不會出現「較昨日」這種在有缺漏時會講錯話的字眼。
"""
import argparse
import csv
import json
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent  # public_put_yield/
PARSE_XQ_CSV = REPO_ROOT.parent / "scripts" / "parse_xq_csv.py"  # 共用腳本，不重複造輪子
STABLE_DIV_CSV = REPO_ROOT.parent / "stable_dividend_cb_issuers_enriched.csv"

ARCHIVE_DIR = REPO_ROOT / "archive"
DATA_DIR = ARCHIVE_DIR / "data"
DATES_FILE = ARCHIVE_DIR / "dates.json"

sys.path.insert(0, str(REPO_ROOT.parent / "scripts"))
from put_yield_ranking import load_rows, build_ranking  # noqa: E402


def infer_date_from_filename(path: Path):
    m = re.search(r"(20\d{2})(\d{2})(\d{2})", path.stem)
    if not m:
        return None
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def load_stable_dividend_set():
    if not STABLE_DIV_CSV.exists():
        return set()
    with open(STABLE_DIV_CSV, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    return {r["stock_code"] for r in rows if r.get("stable_dividend_candidate") == "True"}


def parse_raw_xq_csv(raw_csv_path: Path) -> Path:
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    result = subprocess.run(
        [sys.executable, str(PARSE_XQ_CSV), str(raw_csv_path), str(tmp_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"parse_xq_csv.py 失敗：{result.stderr}")
    print(result.stdout.strip())
    return tmp_path


def row_to_record(r, stable_div_set):
    return {
        "code": r["code"],
        "name": r["name"],
        "conv_price": r["conv_price"],
        "stock_price": r["stock_price"],
        "conv_value": r["conv_value"],
        "cb_price": r["cb_price"],
        "simple_return_pct": round(r["_simple_return_pct"], 2),
        "ytp_pct": round(r["ytp_pct"], 2) if r["ytp_pct"] is not None else None,
        "next_put_date": r["next_put_date"],
        "next_put_price": r["next_put_price"],
        "days_to_put": r["_days_to_put"],
        "volume": r["volume"] or 0,
        "collateral": r["collateral"] or "",
        "is_ky": r["_is_ky"],
        "attack_defense": r["code"][:4] in stable_div_set,
    }


def build_snapshot(raw_csv_path: Path, snapshot_date: date):
    parsed_csv = parse_raw_xq_csv(raw_csv_path)
    try:
        rows = load_rows(parsed_csv)
        ranking = build_ranking(rows, today=snapshot_date)
    finally:
        parsed_csv.unlink(missing_ok=True)

    stable_div_set = load_stable_dividend_set()
    records = [row_to_record(r, stable_div_set) for r in ranking]

    snapshot = {
        "date": snapshot_date.isoformat(),
        "source": "XQ全球贏家 可轉債總表（手動匯出）",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_parsed": len(rows),
        "rows": records,
    }
    return snapshot


def write_snapshot(snapshot):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_DIR / f"{snapshot['date']}.json"
    out_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return out_path


def update_dates_index(new_date_str):
    dates = []
    if DATES_FILE.exists():
        dates = json.loads(DATES_FILE.read_text(encoding="utf-8"))
    if new_date_str not in dates:
        dates.append(new_date_str)
    dates.sort()
    DATES_FILE.write_text(json.dumps(dates, ensure_ascii=False), encoding="utf-8")
    return dates


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("raw_csv", help="Drea\\XQ\\ 底下的原始XQ匯出CSV路徑")
    parser.add_argument("--date", help="快照日期 YYYY-MM-DD（預設從檔名抓，如20260728.csv）")
    args = parser.parse_args()

    raw_path = Path(args.raw_csv)
    if not raw_path.exists():
        sys.exit(f"找不到檔案：{raw_path}")

    if args.date:
        snapshot_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        snapshot_date = infer_date_from_filename(raw_path)
        if snapshot_date is None:
            sys.exit("檔名抓不到日期(需含YYYYMMDD)，請用 --date YYYY-MM-DD 指定")

    snapshot = build_snapshot(raw_path, snapshot_date)
    out_path = write_snapshot(snapshot)
    dates = update_dates_index(snapshot["date"])

    clean = sum(1 for r in snapshot["rows"] if r["volume"] > 0 and not r["is_ky"])
    ky = sum(1 for r in snapshot["rows"] if r["volume"] > 0 and r["is_ky"])
    stale = sum(1 for r in snapshot["rows"] if r["volume"] == 0)
    print(f"已寫入封存：{out_path}")
    print(f"{snapshot['date']}：可算 {len(snapshot['rows'])} 檔（乾淨 {clean} / KY {ky} / 零成交 {stale}），總封存天數 {len(dates)}")
    print(f"已存在的封存日：{', '.join(dates)}")


if __name__ == "__main__":
    main()

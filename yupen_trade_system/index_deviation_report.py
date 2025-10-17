# -*- coding: utf-8 -*-
import os
import math
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import akshare as ak
import yfinance as yf
import matplotlib.pyplot as plt

# ============ 配置 =============
# 你要查的指数／现货名称 → 一些可能的代码（优先用 AkShare 接口支持的那些）
index_candidates = {
    "上证50": ["000016"],
    "沪深300": ["000300"],
    "中证500": ["000905"],
    "中证1000": ["000852"],
    "中证2000": ["932000"],
    "科创50": ["000688"],
    "创业板指": ["399006"],
    "微盘股": ["883418"],
    # 港股 / 黄金 /现货
    "恒生指数": ["HSI", "^HSI"],
    "恒生科技": ["HS2083"],
    "恒生国企": ["HSCEL", "HSCE", "^HSCE"],
    "伦敦金现": ["AUUSDO", "XAUUSD=X", "AU=F"],
}

OUT_CSV = "index_report_full.csv"
PLOT_DIR = "plots"
os.makedirs(PLOT_DIR, exist_ok=True)

# 历史数据拉取起始日期
today = datetime.now().date()
start_date = today - timedelta(days=180)
start_date_str = start_date.strftime("%Y%m%d")
end_date_str = today.strftime("%Y%m%d")

# ---------- 工具函数 ----------

def normalize_df(df):
    """规范化 DataFrame，使得有 'date' 和 'close' 两列（统一名字）"""
    date_col = None
    close_col = None
    for c in df.columns:
        if "日期" in c or "date" in c.lower():
            date_col = c
        if "收盘" in c or "close" in c.lower():
            close_col = c
    if date_col is None or close_col is None:
        # 还可以尝试 index 名字作为 date
        if df.index is not None:
            df2 = df.reset_index()
            # 重新试一次
            for c in df2.columns:
                if "日期" in c or "date" in c.lower():
                    date_col = c
                if "收盘" in c or "close" in c.lower():
                    close_col = c
            if date_col is None or close_col is None:
                raise ValueError(f"normalize_df 无法识别列: {df.columns}")
            df = df2
        else:
            raise ValueError(f"normalize_df 无法识别列: {df.columns}")
    df2 = df[[date_col, close_col]].copy()
    df2.columns = ["date", "close"]
    df2["date"] = pd.to_datetime(df2["date"]).dt.date
    df2["close"] = pd.to_numeric(df2["close"], errors="coerce")
    df2 = df2.dropna(subset=["date", "close"])
    df2 = df2.sort_values("date").reset_index(drop=True)
    return df2

def fetch_akshare_a_index(symbol):
    """用 AkShare 获取 A 股 /中证/上证 指数历史日线数据"""
    try:
        df = ak.index_zh_a_hist(symbol=symbol, period="daily",
                                 start_date=start_date_str, end_date=end_date_str,
                                 adjust="")
        if df is None or df.empty:
            return None, "no data from akshare index_zh_a_hist"
        df2 = normalize_df(df)
        return df2, ""
    except Exception as e:
        return None, f"akshare index_zh_a_hist error: {e}"

def fetch_akshare_spot_gold(symbol):
    """用 AkShare 的现货黄金接口尝试获取数据（如上海金）"""
    try:
        # symbol 如 "Au99.99" 或其他
        df = ak.spot_quotations_sge(symbol=symbol)
        if df is None or df.empty:
            return None, "no data from spot_quotations_sge"
        # 其返回通常为实时样式，不是历史日线；但我们至少可以取最新价
        df2 = normalize_df(df)
        return df2, ""
    except Exception as e:
        return None, f"akshare spot_quotations_sge error: {e}"

def fetch_yfinance(symbol):
    """回退方式：yfinance 获取历史日线数据"""
    try:
        t = yf.Ticker(symbol)
        hist = t.history(start=start_date.strftime("%Y-%m-%d"),
                         end=(today + timedelta(days=1)).strftime("%Y-%m-%d"),
                         interval="1d", auto_adjust=False)
        if hist is None or hist.shape[0] == 0:
            return None, "yfinance no data"
        hist2 = hist.reset_index()
        df2 = normalize_df(hist2)
        return df2, ""
    except Exception as e:
        return None, f"yfinance error: {e}"

def try_candidates(cands):
    """按候选顺序尝试 AkShare / AkGold / yfinance 等方式，返回 (df, which_method, used_symbol, note)"""
    for sym in cands:
        # 尝试 A 股 / 中证指数方式（适用于纯数字符号）
        df, note = fetch_akshare_a_index(sym)
        if df is not None:
            return df, "ak_a_index", sym, note
        # 尝试黄金现货接口
        df, note2 = fetch_akshare_spot_gold(sym)
        if df is not None:
            return df, "ak_gold_spot", sym, note2
        # 尝试 yfinance
        df, note3 = fetch_yfinance(sym)
        if df is not None:
            return df, "yfinance", sym, note3
    # 全部尝试失败
    return None, None, None, "all candidates failed"

# ============ 主流程 ============

rows = []
for name, cands in index_candidates.items():
    print(f"Processing {name} ...")
    df, method, used_sym, note = try_candidates(cands)
    if df is None:
        print(f"  ❌ {name} 获取失败，note = {note}")
        rows.append({
            "指数": name,
            "used_symbol": None,
            "method": None,
            "date": None,
            "close": np.nan,
            "ma20": np.nan,
            "chg_pct": np.nan,
            "dev_pct": np.nan,
            "note": note
        })
        continue

    # 计算 MA20
    df["MA20"] = df["close"].rolling(window=20).mean()

    last = df["close"].iloc[-1]
    ma20 = df["MA20"].iloc[-1] if not np.isnan(df["MA20"].iloc[-1]) else np.nan
    date = df["date"].iloc[-1]

    # 当日涨跌幅
    if len(df) >= 2:
        prev = df["close"].iloc[-2]
        if prev != 0:
            chg_pct = 100 * (last - prev) / prev
        else:
            chg_pct = np.nan
    else:
        chg_pct = np.nan

    dev_pct = 100 * (last - ma20) / ma20 if not np.isnan(ma20) else np.nan

    rows.append({
        "指数": name,
        "used_symbol": used_sym,
        "method": method,
        "date": date,
        "close": round(last, 4),
        "ma20": (round(ma20,4) if not math.isnan(ma20) else np.nan),
        "chg_pct": round(chg_pct, 4),
        "dev_pct": round(dev_pct, 4),
        "note": note
    })

    # 绘图
    try:
        plt.figure(figsize=(8,4))
        plt.plot(df["date"], df["close"], label="收盘价")
        if "MA20" in df.columns:
            plt.plot(df["date"], df["MA20"], label="20日均线", linestyle="--")
        plt.title(f"{name} ({used_sym}, via {method})")
        plt.xlabel("日期")
        plt.ylabel("价格 / 指数")
        plt.legend()
        plt.grid(True, linestyle="--", alpha=0.5)
        safe = "".join(ch if ch.isalnum() else "_" for ch in name)
        plt.tight_layout()
        plt.savefig(os.path.join(PLOT_DIR, f"{safe}_{used_sym}.png"), dpi=150)
        plt.close()
    except Exception as e:
        print("  ⚠️ 绘图失败:", e)

# 输出表格
df_out = pd.DataFrame(rows)
df_out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
print(f"All done. 输出在 {OUT_CSV}，图片保存在 {PLOT_DIR}")  
print(df_out)

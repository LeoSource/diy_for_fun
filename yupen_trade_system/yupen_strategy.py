# -*- coding: utf-8 -*-
import os
import math
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import akshare as ak
import mplfinance as mpf
from tenacity import retry, stop_after_attempt, wait_fixed
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

# ============ 配置 =============
# 你要查的指数／现货名称 → 一些可能的代码（优先用 AkShare 接口支持的那些）
index_candidates = {
    "上证50": ["000016"],
    "沪深300": ["399300"],
    "中证500": ["000905"],
    "中证1000": ["000852"],
    "中证2000": ["932000"],
    "科创50": ["000688"],
    "创业板指": ["399006"],
    "微盘股": ["883418"],
    # 港股 / 黄金 /现货 (保留但暂不处理)
    # "恒生指数": ["HSI", "^HSI"],
    # "恒生科技": ["HS2083"],
    # "恒生国企": ["HSCEL", "HSCE", "^HSCE"],
    # "伦敦金现": ["AUUSDO", "XAUUSD=X", "AU=F"],
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
        df = ak.stock_zh_a_hist_em(symbol=symbol, period="daily",
                                 start_date=start_date_str, end_date=end_date_str, adjust="qfq")
        if df is None or df.empty:
            return None, "no data from akshare index_zh_a_hist"
        # 重命名列以适应 mplfinance
        df.rename(columns={
            '日期': 'Date',
            '开盘': 'Open',
            '最高': 'High',
            '最低': 'Low',
            '收盘': 'Close',
            '成交量': 'Volume'
        }, inplace=True)
        # 设置日期为索引
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        return df[['Open', 'High', 'Low', 'Close', 'Volume']], ""
    except Exception as e:
        return None, f"akshare index_zh_a_hist error: {e}"

def try_candidates(cands, name):
    """按候选顺序尝试 AkShare 方式，返回 (df, which_method, used_symbol, note)"""
    for sym in cands:
        # 判断是否为A股指数代码（纯数字）
        if sym.isdigit() or (len(sym) == 6 and sym[:2] in ['00', '30', '60', '88', '93']):
            df, note = fetch_akshare_a_index(sym)
            if df is not None:
                return df, "ak_a_index", sym, note
        else:
            # 对于非A股指数，暂时跳过不处理
            return None, None, None, f"Skipping non-A share index: {name}"
    # 全部尝试失败
    return None, None, None, "all candidates failed"

# ============ 主流程 ============

rows = []
for name, cands in index_candidates.items():
    print(f"Processing {name} ...")
    df, method, used_sym, note = try_candidates(cands, name)
    if df is None:
        print(f"  ❌ {name} 获取失败或跳过，note = {note}")
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

    # 提取收盘价用于计算指标
    close_prices = df['Close'].copy()
    
    # 计算 MA20
    ma20_series = close_prices.rolling(window=20).mean()

    last = close_prices.iloc[-1]
    ma20 = ma20_series.iloc[-1] if not np.isnan(ma20_series.iloc[-1]) else np.nan
    date = close_prices.index[-1].date()

    # 当日涨跌幅
    if len(close_prices) >= 2:
        prev = close_prices.iloc[-2]
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

    # 使用 mplfinance 绘制更漂亮的K线图，每个指数只画一张图
    try:
        # 设置图表样式（红涨绿跌）
        mc = mpf.make_marketcolors(
            up='red',       # 上涨为红色
            down='green',   # 下跌为绿色
            edge='inherit',
            wick={'up':'red','down':'green'},
            volume='in'
        )
        
        s = mpf.make_mpf_style(marketcolors=mc, gridstyle='-', y_on_right=True,  rc={'font.family': 'SimHei'})
        
        # 生成安全的文件名
        safe = "".join(ch if ch.isalnum() else "_" for ch in name)
        
        # 添加MA20到图表
        ap = mpf.make_addplot(ma20_series, color='orange', width=1.5)
        
        # 绘制带MA20的蜡烛图并保存，解决中文显示问题
        mpf.plot(
            df,
            type='candle',
            style=s,
            title=f"{name} ({used_sym})",
            ylabel='Price (CNY)',
            volume=True,
            ylabel_lower='Volume',
            figsize=(12, 8),
            addplot=ap,
            savefig=dict(fname=os.path.join(PLOT_DIR, f"{safe}_{used_sym}_candle.png"), dpi=150),
        )
        
    except Exception as e:
        print("  ⚠️ 绘图失败:", e)

# 输出表格
df_out = pd.DataFrame(rows)
df_out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
print(f"All done. 输出在 {OUT_CSV}，图片保存在 {PLOT_DIR}")  
print(df_out)
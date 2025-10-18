"""
鱼盆模型 — 全自动版（使用 akshare 的 stock_zh_index_daily，临界点用 MA20，状态穿越日期为真正穿越 MA20 的那天）
依赖: akshare, pandas, openpyxl
pip install akshare pandas openpyxl
"""

import akshare as ak
import pandas as pd
from datetime import datetime
import os
import time

# ========== 配置区 ==========
# 你可以只写 6 位指数代码（例如 '000300'、'000016'、'399006'），也可以写 'sh000300' / 'sz399006'。
index_list = [
    ("000016", "上证50"),
    ("000300", "沪深300"),
    ("000905", "中证500"),
    ("000852", "中证1000"),
    ("399006", "创业板指"),
    ("932000", "中证2000"),
    ("000688", "科创50"),
    ("899050", "北证50"),
    ("883418", "微盘股"),
]

start_date = "20240101"  # 拉取历史起始日（可按需调整）
history_file = "history.csv"
output_dir = "."
# ============================

def try_fetch_index(symbol_attempts, start_date, end_date):
    """
    尝试多个 symbol（akshare 要求格式像 'sh000300' 或 'sz399006' 或 'sz399552' 等）。
    symbol_attempts 是按优先级排列的尝试列表，返回 DataFrame 或 None。
    """
    for s in symbol_attempts:
        try:
            df = ak.stock_zh_index_daily(symbol=s)
            # ak.stock_zh_index_daily 返回的列通常包含: date, open, high, low, close, volume ...
            if df is None or df.empty:
                continue
            # 确保按时间升序
            df = df.sort_values(by=df.columns[0])  # 第一个列通常是日期
            df = df.reset_index(drop=True)
            return df
        except Exception as e:
            # 短暂等待以避免被目标站点限流
            time.sleep(0.5)
            continue
    return None

def normalize_symbol_candidates(code):
    """
    给定用户输入 code（可能是 '000300' / 'sh000300' / '000300.SH' 等），返回尝试的 symbol 列表。
    优先尝试用户原样，然后尝试带 'sh' 和 'sz' 前缀的版本（常见于指数）。
    """
    code = str(code).strip()
    # 把像 000300.SH 或 000300.SH 去掉非字母数字
    code_clean = code.replace(".SH","").replace(".sh","").replace(".SZ","").replace(".sz","")
    candidates = []
    # 先尝试用户原样（可能已经包含 sh/sz 前缀或是 akshare 认可的写法）
    candidates.append(code)
    # 然后尝试清洗后的原码
    candidates.append(code_clean)
    # 尝试加前缀 sh/ sz（两者都试）
    if not (code_clean.startswith("sh") or code_clean.startswith("sz")):
        candidates.append("sh" + code_clean)
        candidates.append("sz" + code_clean)
    # 去重并返回
    seen = []
    out = []
    for c in candidates:
        if c not in seen:
            seen.append(c); out.append(c)
    return out

def find_last_cross_date(df_close, col_close_name="close"):
    """
    给定含有 'close' 列和已按时间升序排序的 DataFrame，计算 MA20 并返回：
      - current_close, current_ma20, current_state (True 表示 close>ma20)
      - cross_date: 最近一次布尔值发生变化的日期（即穿越日），如果没有则返回 None
    注意: df_close 的日期列一般是第一列，可用 df_close.iloc[:,0] 提取日期
    """
    # 尝试自动识别列名：有些版本是 'close'，有时是 '收盘'，这里做兼容
    df = df_close.copy()
    # 识别日期列
    date_col = df.columns[0]
    # 标准化列名：将收盘价列重命名为 'close' 以方便处理
    close_col = None
    for cand in ["close", "收盘", "close_price", "Close"]:
        if cand in df.columns:
            close_col = cand
            break
    # 如果没找到上述名字，猜测最后一列为收盘价
    if close_col is None:
        close_col = df.columns[-1]
    df = df.rename(columns={close_col: "close"})
    # 确保日期为 datetime
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(by=date_col).reset_index(drop=True)
    # 计算 MA20
    df["MA20"] = pd.to_numeric(df["close"], errors="coerce").rolling(window=20, min_periods=1).mean()
    # 计算 above 布尔序列（close > MA20）；若 MA20 为 NaN，则 above 为 False（或 np.nan，取决于需求）
    df["above"] = df["close"] > df["MA20"]
    # 当前值（最后一行）
    if df.empty:
        return None, None, None, None
    current_row = df.iloc[-1]
    current_close = float(current_row["close"])
    current_ma20 = float(current_row["MA20"]) if pd.notna(current_row["MA20"]) else None
    current_state = bool(current_row["above"]) if pd.notna(current_row["above"]) else None
    # 找最近一次 above 值发生变化的那一行（即 above != above.shift(1)）
    df["above_prev"] = df["above"].shift(1)
    df["changed"] = (df["above"] != df["above_prev"]) & (~df["above_prev"].isna())
    changed_idx = df.index[df["changed"]].tolist()
    cross_date = None
    if changed_idx:
        # 取最后一次发生变化的那一天（即穿越发生日）
        last_change_idx = changed_idx[-1]
        cross_date = df.loc[last_change_idx, date_col].strftime("%Y-%m-%d")
        # 说明：last_change_idx 对应的那一行是穿越发生日，
        # 它的 above 值是发生变化后（即新状态）的值（例如从 False->True）
    else:
        # 如果没有变化记录（例如全程都在 MA20 之上或之下，或数据太短）， cross_date 留空
        cross_date = None
    return current_close, current_ma20, current_state, cross_date

def main():
    results = []
    end_date = datetime.today().strftime("%Y%m%d")
    for code, name in index_list:
        # 生成尝试 symbol 列表
        symbol_candidates = normalize_symbol_candidates(code)
        # 优化：如果用户直接给的 6 位数字（比如 '000300'），优先尝试带 'sh' 或 'sz' 前缀:
        if len(str(code)) == 6 and not (str(code).lower().startswith("sh") or str(code).lower().startswith("sz")):
            # 把带前缀尝试放到前面（先尝试 sh, 然后 sz）
            symbol_candidates = ["sh" + code, "sz" + code] + [c for c in symbol_candidates if c not in ("sh"+code,"sz"+code)]
        # 拉数据
        df_hist = try_fetch_index(symbol_candidates, start_date, end_date)
        if df_hist is None or df_hist.empty:
            print(f"⚠️ 无法获取 {name}({code}) 的历史数据，尝试过: {symbol_candidates}")
            results.append({
                "指数代码": code,
                "指数名称": name,
                "当前点位": None,
                "临界点位": None,
                "当前状态": None,
                "偏离率(%)": None,
                "状态穿越日": None
            })
            continue
        # 处理并计算 MA20、穿越日等
        current_close, current_ma20, current_state, cross_date = find_last_cross_date(df_hist)
        # 计算偏离率（相对于 MA20）
        if current_ma20 is None or current_ma20 == 0:
            deviation = None
        else:
            deviation = (current_close - current_ma20) / current_ma20 * 100
        results.append({
            "指数代码": code,
            "指数名称": name,
            "当前点位": current_close,
            "临界点位": current_ma20,
            "当前状态": "Yes" if current_state else "No" if current_state is not None else None,
            "偏离率(%)": deviation,
            "状态穿越日": cross_date
        })

    # 构造 DataFrame
    out_df = pd.DataFrame(results)

    # 趋势强度：按 偏离率 从大到小排名（偏离率为 None 的放最后）
    # 先把 None 转为很小的数以便排名，保存原值
    out_df["偏离率_for_rank"] = out_df["偏离率(%)"].fillna(-9999999)
    out_df["趋势强度"] = out_df["偏离率_for_rank"].rank(ascending=False, method="dense").astype(int)
    # 把偏离率为 None 的行设置为最大的序号后面（使得 None 在最后）
    max_rank = out_df["趋势强度"].max() if not out_df["趋势强度"].isna().all() else 0
    out_df.loc[out_df["偏离率(%)"].isna(), "趋势强度"] = max_rank + 1

    # 排列列和排序
    final_cols = ["趋势强度", "指数代码", "指数名称", "当前状态", "当前点位", "临界点位", "偏离率(%)", "状态穿越日"]
    out_df = out_df[final_cols].sort_values(by="趋势强度").reset_index(drop=True)

    # 输出文件
    today_str = datetime.today().strftime("%Y-%m-%d")
    output_file = os.path.join(output_dir, f"鱼盆模型复盘_{today_str}.xlsx")
    out_df.to_excel(output_file, index=False)
    print(f"✅ 复盘已保存：{output_file}")
    print(out_df)

    # 更新并保存历史状态（供下次比较或展示用）
    # 这里保存上次状态和上次穿越日
    hist_df = out_df[["指数代码", "当前状态", "状态穿越日"]].rename(
        columns={"当前状态": "上次状态", "状态穿越日": "上次状态时间"})
    hist_df.to_csv(history_file, index=False)
    print("📘 已更新历史状态：", history_file)

if __name__ == "__main__":
    main()

import yfinance as yf
import time

# tickers = ["932000.SS", "899050.SS", "883418.SS"]
tickers = "932000.SS 899050.SS 883418.SS"

try:
    df = yf.download(tickers, start="2024-01-01", end="2025-10-18", progress=False)
    print(f"{tickers}: 数据行数={len(df)}")
except Exception as e:
    print(f"{tickers}: 获取失败 -> {e}")
time.sleep(5)  # 等待5秒再请求下一个

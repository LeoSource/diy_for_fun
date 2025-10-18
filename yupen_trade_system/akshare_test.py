import akshare as ak
import mplfinance as mpf  # Please install mplfinance as follows: pip install mplfinance

def demo1():
    stock_zh_a_hist_df = ak.stock_zh_a_hist(symbol="000300", period="daily", start_date="20230301", end_date='20250122', adjust="qfq")
    print(stock_zh_a_hist_df)

def demo2():
    stock_us_daily_df = ak.stock_us_daily(symbol="AAPL", adjust="qfq")
    stock_us_daily_df = stock_us_daily_df.set_index(["date"])
    stock_us_daily_df = stock_us_daily_df["2020-04-01": "2020-04-29"]
    mpf.plot(stock_us_daily_df, type="candle", mav=(3, 6, 9), volume=True, show_nontrading=False)

def demo3():
    index_stock_info_df = ak.index_stock_info()
    print(index_stock_info_df)

def demo4():
    spot = ak.stock_zh_index_spot_em()
    for code in ["932000", "899050", "883418"]:
        res = spot[spot["代码"] == code]
        if not res.empty:
            print(res[["代码", "名称", "最新价"]])
        else:
            print(f"{code} 没有找到")

if __name__ == '__main__':
    # demo1()
    # demo2()
    # demo3()
    demo4()
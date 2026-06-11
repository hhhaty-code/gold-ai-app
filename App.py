import streamlit as st
import yfinance as yf
import google.generativeai as genai
from datetime import datetime

# 設定網頁標題與樣式
st.set_page_config(page_title="黃金期貨 AI 策略助手", layout="centered")
st.title("🏆 黃金期貨 5分K 策略助手")
st.write("點擊下方按鈕，即時抓取最新盤勢並由 Gemini AI 進行多維度分析。")

# 1. 從 Streamlit Secrets 讀取 Gemini API Key
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("請在 Streamlit 後端設定您的 GEMINI_API_KEY")
    st.stop()

# 2. 定義計算技術指標的函式 (避免安裝複雜的 C 語言套件)
def calculate_indicators(df):
    # 計算布林通道 (20, 2)
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['STD20'] = df['Close'].rolling(window=20).std()
    df['Upper'] = df['MA20'] + (df['STD20'] * 2)
    df['Lower'] = df['MA20'] - (df['STD20'] * 2)
    
    # 計算 RSI (14)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-10)  # 避免除以 0
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

# 3. 按鈕觸發核心邏輯
if st.button("🔄 執行當前黃金策略分析", type="primary"):
    with st.spinner("正在抓取即時數據並呼叫 AI 分析中..."):
        try:
            # 抓取紐約黃金期貨 (GC=F) 的 5分鐘 K 線，抓取最近 5 天的資料確保指標計算完整
            gold = yf.Ticker("GC=F")
            df = gold.history(interval="5m", period="5d")
            
            if df.empty:
                st.error("無法取得即時行情，請確認目前是否為開盤時間。")
                st.stop()
                
            # 計算指標並取得最新一根 K 線數據
            df = calculate_indicators(df)
            latest = df.iloc[-1]
            prev_rows = df.tail(5) # 準備前幾根 K 線供 AI 參考型態
            
            current_price = round(latest['Close'], 2)
            upper_band = round(latest['Upper'], 2)
            middle_band = round(latest['MA20'], 2)
            lower_band = round(latest['Lower'], 2)
            rsi_value = round(latest['RSI'], 2)
            
            # 顯示當前量化數據快照
            st.subheader("📊 當前市場數據快照")
            col1, col2, col3 = st.columns(3)
            col1.metric("當前金價", f"${current_price}")
            col2.metric("RSI (14)", f"{rsi_value}")
            col3.metric("布林中軌", f"${middle_band}")
            
            st.text(f"布林上軌: ${upper_band} | 布林下軌: ${lower_band}")
            
            # 4. 打包數據並建立 Prompt 送給 Gemini
            history_str = prev_rows[['Open', 'High', 'Low', 'Close']].to_string()
            
            prompt = f"""
            你是一個精通黃金期貨（XAU/USD / GC）當沖與短波段交易的頂尖量化操盤手。
            請根據以下剛出爐的 5分鐘 K 線即時量化數據，進行嚴謹的進出場與盤勢評估。

            【當前即時指標數據】
            - 當前時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            - 當前價格：{current_price}
            - 布林通道 (20, 2)：上軌 {upper_band} / 中軌 {middle_band} / 下軌 {lower_band}
            - RSI (14)：{rsi_value}

            【最近 5 根 5分K 歷史走勢】
            {history_str}

            【你的任務】
            請結合布林通道與 RSI 的逆勢/順勢邏輯（例如：價格觸及上下軌且 RSI 超買超賣時的潛在反轉，或是強勢突破時的動能延續），並觀察近期 K 線型態是否有長上影線、下影線或吞噬型態。
            
            請以下列格式直接回覆，不要有任何前言：
            
            🚨 【黃金期貨 5分K 進場雷達評估】
            - 行動建議：[請填寫 🟢考慮做多 / 🔴考慮放空 / ⚪觀望評估]
            - AI 信心指數：[0% - 100%]
            - 建議進場點位：[給出精確價位或區間]
            - 建議停損點位：[基於技術分析的嚴格停損點]
            - 建議停利點位：[預期回檔或前波支撐壓力點]
            
            🤖 【Gemini 盤勢核心分析】
            1. [分析當前價格與布林通道的相對位置與型態含意]
            2. [分析 RSI 顯示的短線動能是否過熱或衰竭]
            3. [針對潛在的假突破或趨勢延續給出風險提示]
            """
            
            # 呼叫 Gemini 1.5 Pro 模型 (適合複雜邏輯推理)
            model = genai.GenerativeModel('gemini-1.5-pro')
            response = model.generate_content(prompt)
            
            # 顯示 AI 分析結果
            st.subheader("🤖 AI 策略推薦結果")
            st.info(response.text)
            
        except Exception as e:
            st.error(f"系統執行錯誤: {str(e)}")

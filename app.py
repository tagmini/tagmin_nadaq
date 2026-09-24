# -*- coding: utf-8 -*-
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# ---------------------------------------------------------
# 1. 페이지 레이아웃 및 스타일 설정
# ---------------------------------------------------------
st.set_page_config(
    page_title="헤지펀드 퀀트 & 리스크 대시보드",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 모바일 가독성 및 카드 스타일 CSS
st.markdown("""
<style>
    .metric-card {
        background-color: #1E1E1E;
        border-radius: 8px;
        padding: 12px;
        border: 1px solid #333;
        margin-bottom: 8px;
    }
    .macro-bar {
        font-size: 0.85rem;
        padding: 8px 12px;
        background-color: #121212;
        border-radius: 6px;
        border: 1px solid #2B2B2B;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. 데이터 수집 및 지표 계산 함수 (2분 캐싱)
# ---------------------------------------------------------
@st.cache_data(ttl=120)
def get_macro_data():
    """상단 매크로 지표 수집"""
    tickers = {
        "나스닥": "^IXIC",
        "S&P500": "^GSPC",
        "미10년물 금리": "^TNX",
        "달러인덱스": "DX-Y.NYB",
        "VIX": "^VIX"
    }
    data = {}
    for name, sym in tickers.items():
        try:
            hist = yf.Ticker(sym).history(period="5d")
            if len(hist) >= 2:
                curr = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2]
                chg = ((curr - prev) / prev) * 100
                data[name] = (curr, chg)
        except Exception:
            data[name] = (0.0, 0.0)
    return data

@st.cache_data(ttl=120)
def get_stock_data(symbol):
    """선택 종목 1년 시세 및 퀀트 지표 연산"""
    stock = yf.Ticker(symbol)
    df = stock.history(period="1y")
    info = stock.info
    
    if df.empty or len(df) < 60:
        return None, None

    # 이평선
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA60'] = df['Close'].rolling(60).mean()
    df['MA120'] = df['Close'].rolling(120).mean()
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()

    # RSI (14)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))

    # MACD (12, 26, 9)
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['Signal']

    # 스마트머니/세력 수급 추정 (OBV: On-Balance Volume)
    obv = [0]
    for i in range(1, len(df)):
        if df['Close'].iloc[i] > df['Close'].iloc[i-1]:
            obv.append(obv[-1] + df['Volume'].iloc[i])
        elif df['Close'].iloc[i] < df['Close'].iloc[i-1]:
            obv.append(obv[-1] - df['Volume'].iloc[i])
        else:
            obv.append(obv[-1])
    df['OBV'] = obv
    df['OBV_MA20'] = df['OBV'].rolling(20).mean()

    return df, info

# ---------------------------------------------------------
# [상단] 글로벌 매크로 티커 바
# ---------------------------------------------------------
macro = get_macro_data()
cols = st.columns(len(macro))
for col, (name, (val, chg)) in zip(cols, macro.items()):
    col.metric(name, f"{val:,.2f}", f"{chg:+.2f}%")

st.divider()

# ---------------------------------------------------------
# [3열 레이아웃 메인 화면]
# ---------------------------------------------------------
col_left, col_mid, col_right = st.columns([1.1, 2.2, 1.4])

# ---------------------------------------------------------
# 1. [좌측] 포트폴리오 & 관심종목 셀렉터
# ---------------------------------------------------------
with col_left:
    st.subheader("💼 포트폴리오 & 워치")
    
    # 계좌 리스크 헬스체크 카드
    with st.container():
        st.markdown("**🛡️ 계좌 리스크 요약**")
        p1, p2 = st.columns(2)
        p1.metric("현금 비중", "35%", "안정권")
        p2.metric("포트폴리오 VaR", "-1.4%", "1일 최대손실")

    st.write("---")
    
    # 종목 선택기
    watchlist = {
        "Microsoft (MSFT)": "MSFT",
        "The Trade Desk (TTD)": "TTD",
        "Enovix (ENVX)": "ENVX",
        "Apple (AAPL)": "AAPL",
        "Nvidia (NVDA)": "NVDA"
    }
    selected_name = st.selectbox("🎯 분석할 종목 선택", list(watchlist.keys()))
    custom_ticker = st.text_input("직접 티커 입력 (선택 시 우선)", "")
    
    target_ticker = custom_ticker.strip().upper() if custom_ticker else watchlist[selected_name]

    # 보유 종목 스냅샷 테이블
    st.markdown("**📋 보유 종목 현황**")
    mock_positions = pd.DataFrame({
        "종목": ["MSFT", "TTD", "현금"],
        "비중": ["40%", "25%", "35%"],
        "손익": ["+8.2%", "-2.1%", "-"]
    })
    st.dataframe(mock_positions, hide_index=True, use_container_width=True)

# ---------------------------------------------------------
# 데이터 로드
# ---------------------------------------------------------
df, info = get_stock_data(target_ticker)

if df is None:
    st.error(f"'{target_ticker}' 데이터를 불러올 수 없습니다. 올바른 티커인지 확인해 주세요.")
else:
    curr_price = df['Close'].iloc[-1]
    curr_vol = df['Volume'].iloc[-1]
    vol_ma20 = df['Vol_MA20'].iloc[-1]
    rsi = df['RSI'].iloc[-1]
    macd = df['MACD'].iloc[-1]
    macd_sig = df['Signal'].iloc[-1]
    ma5 = df['MA5'].iloc[-1]
    ma20 = df['MA20'].iloc[-1]
    ma60 = df['MA60'].iloc[-1]
    ma120 = df['MA120'].iloc[-1]
    obv_curr = df['OBV'].iloc[-1]
    obv_ma20 = df['OBV_MA20'].iloc[-1]

    # ---------------------------------------------------------
    # 2. [중앙] 메인 딥다이브 차트 & 수급 엔진
    # ---------------------------------------------------------
    with col_mid:
        st.subheader(f"📈 {target_ticker} 딥다이브 분석")
        
        # 가격 요약
        day_chg = ((curr_price - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100
        st.metric(f"현재가 ({target_ticker})", f"${curr_price:,.2f}", f"{day_chg:+.2f}%")

        # 1) 주가 및 이동평균선 차트
        st.markdown("**주가 및 이동평균선 (5, 20, 60, 120일선)**")
        st.line_chart(df[['Close', 'MA5', 'MA20', 'MA60', 'MA120']].tail(90))

        # 2) 모멘텀 지표 (RSI / MACD)
        st.markdown(f"**RSI (14): `{rsi:.1f}`** (30이하: 과매도 / 70이상: 과열)")
        st.line_chart(df[['RSI']].tail(90))

        # 3) 세력 수급 / 스마트 머니 (OBV 누적 매집선)
        st.markdown("**스마트 머니 수급 흐름 (OBV 누적 거래량 선)**")
        st.caption("주가가 횡보할 때 OBV가 급등하면 기관/세력의 매집 국면")
        st.line_chart(df[['OBV', 'OBV_MA20']].tail(90))

        # 4) 펀더멘털 스냅샷
        if info:
            st.markdown("**펀더멘털 & 밸류에이션**")
            f1, f2, f3, f4 = st.columns(4)
            pe = info.get('trailingPE', None)
            fwd_pe = info.get('forwardPE', None)
            peg = info.get('pegRatio', None)
            pb = info.get('priceToBook', None)
            
            f1.metric("Trailing PER", f"{pe:.1f}" if pe else "N/A")
            f2.metric("Forward PER", f"{fwd_pe:.1f}" if fwd_pe else "N/A")
            f3.metric("PEG Ratio", f"{peg:.2f}" if peg else "N/A")
            f4.metric("PBR", f"{pb:.2f}" if pb else "N/A")

    # ---------------------------------------------------------
    # 3. [우측] 헤지펀드 5대 필터 & 퀀트 액션 룸
    # ---------------------------------------------------------
    with col_right:
        st.subheader("🎯 5대 필터 & 액션 룸")

        # 5대 필터 평가 로직
        c1_vol = curr_vol >= (vol_ma20 * 2.0)
        c2_trend = (curr_price > ma20) and (ma20 > ma60)
        
        # 20일선 눌림목(±2% 이격) 또는 20일 신고가 돌파
        recent_high = df['Close'].tail(20).max()
        c3_pullback_or_break = (abs(curr_price - ma20) / ma20 <= 0.02) or (curr_price >= recent_high * 0.99)
        
        # RSI 50 안착 및 MACD 골든크로스/양수
        c4_signal = (50 <= rsi <= 68) or (macd > macd_sig)
        
        # OBV 20일선 상회 (세력 개입/매집 흔적)
        c5_smart_money = obv_curr > obv_ma20

        # 금지 조건 체크
        ban_choppy = abs(ma20 - ma60) / ma60 < 0.01  # 장기 횡보
        ban_low_vol = curr_vol < (vol_ma20 * 0.5)     # 거래량 극단적 침체
        ban_high = rsi >= 75                          # 과열 고점

        filters = [c1_vol, c2_trend, c3_pullback_or_break, c4_signal, c5_smart_money]
        score = sum(filters)

        st.markdown("**5대 진입 조건 검증기**")
        st.write(f"- 거래량 2배 급증: {'✅ 충족' if c1_vol else '❌ 미달'}")
        st.write(f"- 정배열/상승추세: {'✅ 충족' if c2_trend else '❌ 미달'}")
        st.write(f"- 눌림목 or 돌파: {'✅ 충족' if c3_pullback_or_break else '❌ 미달'}")
        st.write(f"- RSI/MACD 시그널: {'✅ 충족' if c4_signal else '❌ 미달'}")
        st.write(f"- 세력 매집(OBV): {'✅ 충족' if c5_smart_money else '❌ 미달'}")

        st.write("---")

        # 최종 진입 판단
        if ban_high:
            st.error("🚫 [진입 금지] 이미 급등한 고점 과열 구간 (RSI 75 이상)")
            verdict = "관망"
        elif ban_choppy or ban_low_vol:
            st.warning("⚠️ [진입 금지] 횡보장 또는 극단적 거래량 부재 구간")
            verdict = "관망"
        elif score >= 3:
            st.success(f"🟢 [진입 가능] 조건 {score}/5 충족 (확률적 우위 구간)")
            verdict = "매수 고려"
        else:
            st.info(f"🟡 [관망] 조건 {score}/5 충족 (기준 3개 미달)")
            verdict = "관망"

        # 기계적 액션 플랜 계산 (손익비 1:2 기준)
        st.markdown("**📐 기계적 트레이딩 플랜**")
        entry_price = curr_price
        stop_loss = ma20 * 0.97  # 20일선 -3% 이탈 시 칼손절
        risk_per_share = entry_price - stop_loss
        target_price = entry_price + (risk_per_share * 2.0)  # 손익비 1:2 타겟

        st.write(f"• **예상 진입가:** `${entry_price:,.2f}`")
        st.write(f"• **기계적 손절가:** `${stop_loss:,.2f}` (`-{((entry_price - stop_loss)/entry_price)*100:.1f}%`)")
        st.write(f"• **1차 목표가:** `${target_price:,.2f}` (`+{((target_price - entry_price)/entry_price)*100:.1f}%`)")
        st.write("• **권장 비중:** 계좌 대비 `5% ~ 8% 이내`")

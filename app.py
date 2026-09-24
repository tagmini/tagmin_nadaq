# -*- coding: utf-8 -*-
import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="헤지펀드 퀀트 대시보드", layout="wide", initial_sidebar_state="collapsed")

# 120초(2분) 캐시: 2분이 지나면 새로운 데이터를 자동으로 조회
@st.cache_data(ttl=120)
def load_stock_data(ticker):
    stock = yf.Ticker(ticker)
    df = stock.history(period="6mo")
    return df

st.title("🛡️ 퀀트 리스크 관리 대시보드")

col_input, col_btn = st.columns([3, 1])
with col_input:
    ticker = st.text_input("종목 티커 입력 (예: MSFT, TTD, NVDA)", "MSFT")
with col_btn:
    st.write("")
    st.write("")
    if st.button("🔄 시세 새로고침"):
        st.cache_data.clear()
        st.rerun()

if ticker:
    try:
        df = load_stock_data(ticker.strip().upper())
        if not df.empty and len(df) >= 20:
            # 이평선 및 거래량
            df['MA20'] = df['Close'].rolling(20).mean()
            df['MA60'] = df['Close'].rolling(60).mean()
            df['Vol_MA20'] = df['Volume'].rolling(20).mean()

            # RSI(14)
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / (loss + 1e-9)
            df['RSI'] = 100 - (100 / (1 + rs))

            curr_price = df['Close'].iloc[-1]
            curr_vol = df['Volume'].iloc[-1]
            vol_avg20 = df['Vol_MA20'].iloc[-1]
            curr_rsi = df['RSI'].iloc[-1]

            # 5대 필터 판정 로직
            c_vol = curr_vol >= (vol_avg20 * 2)
            c_trend = curr_price > df['MA20'].iloc[-1] and df['MA20'].iloc[-1] > df['MA60'].iloc[-1]
            c_rsi = 50 <= curr_rsi <= 65

            score = sum([c_vol, c_trend, c_rsi])

            # 모바일 뷰 카드
            c1, c2 = st.columns(2)
            c1.metric("현재가", f"${curr_price:,.2f}")
            c2.metric("RSI(14)", f"{curr_rsi:.1f}")

            st.subheader("🎯 필터 진입 판정")
            if score >= 2:
                st.success(f"🟢 [진입 검토] 충족: {score}/3 | 손익비 우위 구간")
            else:
                st.warning(f"🟡 [관망 권고] 충족: {score}/3 | 진입 기준 미달")

            st.line_chart(df[['Close', 'MA20', 'MA60']].tail(60))
        else:
            st.info("데이터가 부족하거나 티커가 올바르지 않습니다.")
    except Exception as e:
        st.error(f"데이터 조회 중 오류 발생: {e}")

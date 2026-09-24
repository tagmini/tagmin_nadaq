# -*- coding: utf-8 -*-
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from streamlit_autorefresh import st_autorefresh

# 1. 모바일 뷰포트 및 페이지 설정
st.set_page_config(page_title="헤지펀드 퀀트 대시보드", layout="wide", initial_sidebar_state="collapsed")

# 2. 2분(120초)마다 화면 자동 새로고침
st_autorefresh(interval=120 * 1000, key="datarefresh")

# 3. 데이터 로더 (캐시 120초)
@st.cache_data(ttl=120)
def load_stock_data(ticker):
    stock = yf.Ticker(ticker)
    df = stock.history(period="6mo")
    return df

st.title("🛡️ 퀀트 리스크 관리 대시보드")
ticker = st.text_input("종목 심볼 입력 (예: MSFT, TTD, 005930.KS)", "MSFT")

if ticker:
    df = load_stock_data(ticker)
    if not df.empty:
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        df['Vol_MA20'] = df['Volume'].rolling(20).mean()

        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        curr_price = df['Close'].iloc[-1]
        curr_vol = df['Volume'].iloc[-1]
        vol_avg20 = df['Vol_MA20'].iloc[-1]
        curr_rsi = df['RSI'].iloc[-1]
        
        score = 0
        cond_vol = curr_vol >= (vol_avg20 * 2)
        cond_trend = df['MA20'].iloc[-1] > df['MA60'].iloc[-1] and curr_price > df['MA20'].iloc[-1]
        cond_rsi = 50 <= curr_rsi <= 65
        
        if cond_vol: score += 1
        if cond_trend: score += 1
        if cond_rsi: score += 1

        col1, col2 = st.columns(2)
        col1.metric("현재가", f"${curr_price:,.2f}")
        col2.metric("RSI (14)", f"{curr_rsi:.1f}")

        st.subheader("🎯 5대 필터 판정")
        if score >= 2:
            st.success(f"🟢 [진입 가능] 필터 점수: {score}/3 | 손익비 우위 구간")
        else:
            st.warning(f"🟡 [관망 권고] 필터 조건 미달 ({score}/3) - 뇌동매매 주의")

        st.line_chart(df[['Close', 'MA20', 'MA60']].tail(60))

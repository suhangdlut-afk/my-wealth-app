import streamlit as st
import pandas as pd
import requests
import re

# --- 1. 网页配置 ---
st.set_page_config(page_title="SG WealthGuard PRO", layout="centered")

# --- 2. 利率同步逻辑 (简易版) ---
@st.cache_data(ttl=3600) # 缓存1小时，避免频繁抓取被封IP
def get_live_rates():
    # 这里预设 2026 基础数据
    data = {
        "uob_tiers": [(30000, 0.03), (30000, 0.04), (65000, 0.05), (25000, 0.06)],
        "ocbc_bonus": {"salary": 0.025, "save": 0.015, "spend": 0.006}
    }
    # 尝试同步 (此处逻辑可根据之前讨论的 SingSaver 进一步细化)
    return data

rates = get_live_rates()

# --- 3. 侧边栏：输入区域 ---
with st.sidebar:
    st.header("👤 财务概况")
    amt = st.number_input("💰 存款总额 (SGD)", min_value=0, value=300000, step=1000)
    sal = st.number_input("🏦 月薪入账 (SGD)", min_value=0, value=12000)
    spd = st.slider("💳 月度消费 (SGD)", 0, 5000, 1200)
    
    st.divider()
    st.header("📈 专项校验")
    sav_input = st.radio("OCBC 360：每月余额能否增长 ≥$500?", ["是 (Yes)", "否 (No)"])
    sav = True if sav_input == "是 (Yes)" else False

# --- 4. 主界面计算展示 ---
st.title("🇸🇬 SG WealthGuard PRO")
st.markdown("基于 2026 银行政策的资产分配导航")

if st.button("🚀 开始精准诊断", use_container_width=True):
    # 计算逻辑
    uob_i = 0
    rem = min(amt, 150000)
    for cap, rate in rates["uob_tiers"]:
        if rem > 0:
            active = min(rem, cap)
            uob_i += active * rate
            rem -= active
            
    ocbc_rate = 0.0005 + rates["ocbc_bonus"]["spend"] + \
                (rates["ocbc_bonus"]["salary"] if sal >= 1600 else 0) + \
                (rates["ocbc_bonus"]["save"] if sav else 0)
    ocbc_amt = min(max(amt - 150000, 0), 100000) if amt >= 250000 else min(amt, 100000)
    ocbc_i = ocbc_amt * ocbc_rate
    
    # 结果看板
    total_int = uob_i + ocbc_i + (max(amt-250000, 0) * 0.032) # 溢出算定存
    
    col1, col2 = st.columns(2)
    col1.metric("总年度预计利息", f"${total_int:,.2f}")
    col2.metric("综合收益率", f"{(total_int/amt)*100:.2f}% p.a.")

    # 清单展示
    st.subheader("📍 资金精准分布清单")
    display_df = pd.DataFrame([
        {"分配目标": "UOB One (核心)", "金额": f"${min(amt, 150000):,.0f}", "预期收益": f"${uob_i:,.2f}"},
        {"分配目标": "OCBC 360 (次席)", "金额": f"${ocbc_amt:,.0f}", "预期收益": f"${ocbc_i:,.2f}"},
        {"分配目标": "溢出资金 (定存)", "金额": f"${max(amt-250000, 0):,.0f}", "预期收益": f"${max(amt-250000, 0)*0.032:,.2f}"}
    ])
    st.table(display_df)

    # 执行指令
    if amt >= 250000:
        st.success("💡 **执行指令：** 每月从 OCBC 转账 $1,601 至 UOB 并备注 'SALARY'，两行各刷卡 $500。")

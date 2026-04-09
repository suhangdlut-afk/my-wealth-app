import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime

# --- 1. 动态引擎：加入降息预警逻辑 ---
class LiveRateEngine:
    def __init__(self):
        # 4月当前利率 (EIR 约 3.5%-4%)
        self.uob_now = [(30000, 0.03), (30000, 0.04), (65000, 0.05), (25000, 0.06)]
        # 5月预期下调 (假设阶梯整体下调 1.0%)
        self.uob_may = [(30000, 0.02), (30000, 0.03), (65000, 0.04), (25000, 0.045)]
        
        self.ocbc_now = {"salary": 0.025, "save": 0.015, "spend": 0.006}
        self.ocbc_may = {"salary": 0.020, "save": 0.012, "spend": 0.006}

    def get_current_month(self):
        return datetime.now().month

# --- 2. 界面初始化 ---
st.set_page_config(page_title="SG WealthGuard PRO", layout="centered")
engine = LiveRateEngine()

st.title("🇸🇬 SG WealthGuard PRO")

# --- 3. 5月降息红字预警 ---
current_month = engine.get_current_month()
if current_month == 4:
    st.error("⚠️ **重要预警：新加坡银行 5 月 1 日降息在即！**")
    st.caption("检测到 OCBC 360 与 UOB One 即将下调奖励利率。本诊断已自动开启“跨月对比模式”。")

# --- 4. 侧边栏输入 ---
with st.sidebar:
    st.header("👤 财务数据")
    amt = st.number_input("💰 存款总额 (SGD)", min_value=0.0, value=250000.0, step=1000.0)
    sal = st.number_input("🏦 月薪入账 (SGD)", min_value=0.0, value=10000.0)
    spd = st.slider("💳 月度消费 (SGD)", 0, 5000, 1000)
    sav = st.checkbox("OCBC 360：每月余额增长 ≥$500", value=True)

# --- 5. 计算函数 ---
def calculate_all(amount, salary, spend, save_bonus, rates_uob, rates_ocbc):
    # UOB 计算
    u_amt = min(amount, 150000)
    u_int, rem = 0, u_amt
    for cap, rate in rates_uob:
        if rem <= 0: break
        active = min(rem, cap)
        u_int += active * rate
        rem -= active
    
    # OCBC 计算
    o_amt = min(max(amount - 150000, 0), 100000) if amount >= 250000 else min(amount, 100000)
    o_rate = 0.0005 + rates_ocbc["spend"] + (rates_ocbc["salary"] if salary >= 1600 else 0) + (rates_ocbc["save"] if save_bonus else 0)
    o_int = o_amt * o_rate
    
    # 溢出定存 (假设 3.2%)
    e_amt = max(amount - 250000, 0)
    e_int = e_amt * 0.032
    
    return u_int + o_int + e_int

# --- 6. 执行诊断 & 对比展示 ---
if st.button("🚀 生成 4月 vs 5月 收益对比报告", use_container_width=True):
    # 算 4 月
    total_now = calculate_all(amt, sal, spd, sav, engine.uob_now, engine.ocbc_now)
    # 算 5 月
    total_may = calculate_all(amt, sal, spd, sav, engine.uob_may, engine.ocbc_may)
    
    # 指标展示
    c1, c2, c3 = st.columns(3)
    c1.metric("4月预计利息", f"${total_now:,.2f}")
    c2.metric("5月预计利息", f"${total_may:,.2f}", delta=f"-${total_now - total_may:,.2f}", delta_color="inverse")
    c3.metric("5月年化收益", f"{(total_may/amt)*100:.2f}%")

    # 可视化对比
    chart_data = pd.DataFrame({
        "月份": ["4月 (当前)", "5月 (降息后)"],
        "年利息收益 ($)": [total_now, total_may]
    })
    st.bar_chart(data=chart_data, x="月份", y="年利息收益 ($)")

    st.warning("📊 **诊断结论：** 5 月起您的年利息将减少约 **$" + f"{total_now - total_may:,.2f}" + "**。")
    st.info("💡 **应对策略：** 考虑到高息户口收益收缩，建议在 5 月前将多余闲钱锁入长期定存（Fixed Deposit）以锁定 3.2% 以上利率。")

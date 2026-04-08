import streamlit as st
import pandas as pd
import requests
import re

# ==========================================
# 1. 数据引擎
# ==========================================
class LiveRateEngine:
    def __init__(self):
        self.uob_tiers = [(30000, 0.03), (30000, 0.04), (65000, 0.05), (25000, 0.06)]
        self.ocbc_bonus = {"bonus_salary": 0.025, "bonus_save": 0.015, "bonus_spend": 0.006}

    def sync_rates(self):
        url = "https://www.singsaver.com.sg/blog/best-savings-accounts-singapore"
        try:
            r = requests.get(url, timeout=5)
            uob_match = re.findall(r'UOB One.*?(\d+\.\d+)%', r.text, re.S)
            if uob_match:
                factor = (float(uob_match[0])/100) / 0.06
                self.uob_tiers = [(cap, rate * factor) for cap, rate in self.uob_tiers]
            return True
        except: return False

# ==========================================
# 2. 界面初始化
# ==========================================
st.set_page_config(page_title="SG WealthGuard", layout="centered")

if 'engine' not in st.session_state:
    engine = LiveRateEngine()
    engine.sync_rates()
    st.session_state.engine = engine

st.title("🇸🇬 SG WealthGuard PRO")

with st.sidebar:
    st.header("👤 财务概况")
    amt = st.number_input("💰 存款总额 (SGD)", min_value=0.0, value=150000.0, step=1000.0)
    sal = st.number_input("🏦 月薪入账 (SGD)", min_value=0.0, value=10000.0)
    spd = st.slider("💳 月度消费 (SGD)", 0, 5000, 800)
    sav_input = st.radio("OCBC 360：每月增存 ≥$500?", ["是", "否"])
    sav = True if sav_input == "是" else False

# ==========================================
# 3. 核心计算逻辑 (全金额适配)
# ==========================================
engine = st.session_state.engine

def get_uob_int(a, s, d):
    if d < 500 or s < 1600: return a * 0.0005
    total, rem = 0, a
    for cap, rate in engine.uob_tiers:
        if rem <= 0: break
        active = min(rem, cap)
        total += active * rate
        rem -= active
    return total + (max(rem, 0) * 0.0005)

def get_ocbc_int(a, s, d, v):
    if d < 500: return a * 0.0005
    rate = 0.0005 + 0.006 + (0.025 if s >= 1600 else 0) + (0.015 if v else 0)
    return min(a, 100000) * rate + max(a-100000, 0) * 0.0005

# 触发诊断
if st.button("🚀 生成资产分布清单", use_container_width=True):
    # 分配策略逻辑
    if amt >= 250000:
        uob_amt, ocbc_amt = 150000, 100000
        extra_amt = amt - 250000
    elif amt > 150000:
        uob_amt, ocbc_amt = 150000, amt - 150000
        extra_amt = 0
    else:
        # 如果小于150k，对比哪家强
        u_val = get_uob_int(amt, sal, spd)
        o_val = get_ocbc_int(amt, sal, spd, sav)
        if u_val >= o_val:
            uob_amt, ocbc_amt, extra_amt = amt, 0, 0
        else:
            uob_amt, ocbc_amt, extra_amt = 0, amt, 0

    uob_i = get_uob_int(uob_amt, sal, spd)
    ocbc_i = get_ocbc_int(ocbc_amt, sal, spd, sav)
    extra_i = extra_amt * 0.032
    total = uob_i + ocbc_i + extra_i

    # 展示结果
    c1, c2 = st.columns(2)
    c1.metric("年度总利息", f"${total:,.2f}")
    c2.metric("综合年化", f"{(total/amt)*100:.2f}%")

    st.subheader("📍 资金精准分布清单")
    results = []
    if uob_amt > 0: results.append({"目标": "UOB One", "金额": f"${uob_amt:,.0f}", "利息": f"${uob_i:,.2f}"})
    if ocbc_amt > 0: results.append({"目标": "OCBC 360", "金额": f"${ocbc_amt:,.0f}", "利息": f"${ocbc_i:,.2f}"})
    if extra_amt > 0: results.append({"目标": "溢出定存", "金额": f"${extra_amt:,.0f}", "利息": f"${extra_i:,.2f}"})
    st.table(pd.DataFrame(results))

    if amt >= 250000:
        st.success("💡 **执行指令：** 薪水发往 OCBC，每月转账 $1,601 至 UOB 并备注 'SALARY'。")
    elif uob_amt > 0 and ocbc_amt > 0:
        st.info("💡 **分流提醒：** 您的资金已超过 UOB 上限，溢出部分存入 OCBC 收益更高。")

import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime

# ==========================================
# 1. 动态金融数据引擎 (含实时抓取)
# ==========================================
class LiveRateEngine:
    def __init__(self):
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        # 默认 2026 4月数据兜底
        self.uob_tiers = [(30000, 0.03), (30000, 0.04), (65000, 0.05), (25000, 0.06)]
        self.ocbc_bonus = {"salary": 0.025, "save": 0.015, "spend": 0.006}
        self.fd_rate = 0.032

    @st.cache_data(ttl=3600)
    def sync_all_rates(_self):
        url = "https://www.singsaver.com.sg/blog/best-savings-accounts-singapore"
        try:
            r = requests.get(url, headers=_self.headers, timeout=8)
            content = r.text
            uob_match = re.findall(r'UOB One.*?(\d+\.\d+)%', content, re.S)
            if uob_match:
                factor = (float(uob_match[0])/100) / 0.06
                _self.uob_tiers = [(cap, rate * factor) for cap, rate in _self.uob_tiers]
            ocbc_match = re.search(r'OCBC 360.*?Salary.*?(\d+\.\d+)%.*?Save.*?(\d+\.\d+)%', content, re.S)
            if ocbc_match:
                _self.ocbc_bonus["salary"] = float(ocbc_match.group(1)) / 100
                _self.ocbc_bonus["save"] = float(ocbc_match.group(2)) / 100
            return True
        except: return False

# ==========================================
# 2. 核心计算逻辑 (含低消费保护)
# ==========================================
def get_uob_yield(amount, sal, spd, tiers):
    # 门槛校验：消费 < 500 或 薪水 < 1600 则跌入基础利率 0.05%
    if spd < 500 or sal < 1600: return amount * 0.0005
    total, rem = 0, amount
    for cap, rate in tiers:
        active = min(rem, cap)
        total += active * rate
        rem -= active
    return total + (max(rem, 0) * 0.0005)

def get_ocbc_yield(amount, sal, spd, sav, bonus):
    # 门槛校验：消费 < 500 则仅有基础利率 0.05%
    if spd < 500: return amount * 0.0005
    rate = 0.0005 + bonus["spend"] + (bonus["salary"] if sal >= 1600 else 0) + (bonus["save"] if sav else 0)
    return min(amount, 100000) * rate + max(amount-100000, 0) * 0.0005

def smart_allocate(amt, sal, spd, sav, engine):
    # 预处理：判断是否触发门槛异常
    is_low_spend = (spd < 500)
    
    if is_low_spend:
        # 消费不足时，失去套利空间，按容量优先填 UOB (150k)
        uob_amt = min(amt, 150000)
        ocbc_amt = min(max(amt - 150000, 0), 100000)
        uob_first = True
    else:
        # 正常比价模式
        u_eir = get_uob_yield(150000, sal, spd, engine.uob_tiers) / 150000
        o_eir = get_ocbc_yield(100000, sal, spd, sav, engine.ocbc_bonus) / 100000
        
        if u_eir >= o_eir:
            uob_amt = min(amt, 150000)
            ocbc_amt = min(max(amt - 150000, 0), 100000)
            uob_first = True
        else:
            ocbc_amt = min(amt, 100000)
            uob_amt = min(max(amt - 100000, 0), 150000)
            uob_first = False

    fd_amt = max(amt - uob_amt - ocbc_amt, 0)
    u_i = get_uob_yield(uob_amt, sal, spd, engine.uob_tiers)
    o_i = get_ocbc_yield(ocbc_amt, sal, spd, sav, engine.ocbc_bonus)
    f_i = fd_amt * engine.fd_rate
    
    return uob_amt, ocbc_amt, fd_amt, u_i, o_i, f_i, uob_first, is_low_spend

# ==========================================
# 3. Streamlit 界面
# ==========================================
st.set_page_config(page_title="SG WealthGuard PRO", layout="centered")

if 'engine' not in st.session_state:
    st.session_state.engine = LiveRateEngine()
    st.session_state.is_live = st.session_state.engine.sync_all_rates()

engine = st.session_state.engine

st.title("🇸🇬 SG WealthGuard PRO")
st.caption(f"数据状态: {'🟢 实时同步' if st.session_state.is_live else '🟡 离线模式'} | 决策模式: 智能比价优先")

with st.sidebar:
    st.header("👤 财务数据输入")
    amt = st.number_input("💰 存款总额 (SGD)", min_value=0.0, value=250000.0, step=1000.0)
    sal = st.number_input("🏦 月薪入账 (SGD)", min_value=0.0, value=10000.0)
    spd = st.slider("💳 月度消费 (SGD)", 0, 5000, 800)
    sav_check = st.checkbox("OCBC 360：每月余额增长 ≥$500", value=True)

if st.button("🚀 生成资产最优分配清单", use_container_width=True):
    u_a, o_a, f_a, u_i, o_i, f_i, uob_first, is_low = smart_allocate(amt, sal, spd, sav_check, engine)
    total_i = u_i + o_i + f_i

    # 结果指标
    c1, c2 = st.columns(2)
    c1.metric("年度预计总收益", f"${total_i:,.2f}")
    c2.metric("综合年化收益率", f"{(total_i/amt)*100:.2f}% p.a.")

    if is_low:
        st.error("🚨 **警告：消费未达标**。您的月度消费低于 $500，无法激活任何高息奖励。")
    else:
        st.info(f"✅ **智能决策**：当前系统优先填满 {'UOB One' if uob_first else 'OCBC 360'} 以获得更高 EIR。")

    st.subheader("📍 资金分布导航")
    res_df = pd.DataFrame([
        {"分配机构": "大华银行 (UOB One)", "金额": f"${u_a:,.0f}", "预期利息": f"${u_i:,.2f}"},
        {"分配机构": "华侨银行 (OCBC 360)", "金额": f"${o_a:,.0f}", "预期利息": f"${o_i:,.2f}"},
        {"分配机构": "溢出存储 (定存/T-Bills)", "金额": f"${f_a:,.0f}", "预期利息": f"${f_i:,.2f}"}
    ])
    st.table(res_df)

    # 指令区
    with st.expander("💡 执行必看指令 (含工资对倒建议)"):
        st.write("1. **薪水发放**：公司薪水发往 **OCBC 360**。")
        st.write("2. **工资对倒**：每月从 OCBC 转账 **$1,601** 至 UOB，备注填写 **'SALARY'**。")
        st.write("3. **消费分流**：确保两张关联卡每月分别刷满 $500。")
        if is_low:
            st.warning("提示：请务必确保月度消费达到 $500，否则年收益将损失巨大。")

# 5月预警
if datetime.now().month == 4:
    st.warning("📅 **市场提示**：5月1日新加坡银行将迎来利率调整。届时程序将自动感知抓取并重置分配优先级。")


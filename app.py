import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime

# ==========================================
# 1. 动态金融数据引擎
# ==========================================
class LiveRateEngine:
    def __init__(self, fd_input_rate):
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        self.uob_tiers = [(30000, 0.03), (30000, 0.04), (65000, 0.05), (25000, 0.06)]
        self.ocbc_bonus = {"salary": 0.025, "save": 0.015, "spend": 0.006}
        self.fd_rate = fd_input_rate / 100 

    @st.cache_data(ttl=3600)
    def sync_rates(_self):
        url = "https://www.singsaver.com.sg/blog/best-savings-accounts-singapore"
        try:
            r = requests.get(url, headers=_self.headers, timeout=8)
            uob_match = re.findall(r'UOB One.*?(\d+\.\d+)%', r.text, re.S)
            if uob_match:
                factor = (float(uob_match[0])/100) / 0.06
                _self.uob_tiers = [(cap, rate * factor) for cap, rate in _self.uob_tiers]
            return True
        except: return False

# ==========================================
# 2. 核心分配算法
# ==========================================
def get_uob_stats(amt, sal, spd, tiers):
    if amt <= 0: return 0.0, 0.0005
    if spd < 500 or sal < 1600: return amt * 0.0005, 0.0005
    total_int, rem = 0.0, amt
    for cap, rate in tiers:
        active = min(rem, cap)
        total_int += active * rate
        rem -= active
    total_int += rem * 0.0005
    return total_int, (total_int / amt if amt > 0 else 0.0005)

def get_ocbc_stats(amt, sal, spd, sav, bonus):
    if amt <= 0: return 0.0, 0.0005
    rate = 0.0005
    if spd >= 500: rate += bonus["spend"]
    if sal >= 1600: rate += bonus["salary"]
    if sav: rate += bonus["save"]
    high_amt = min(amt, 100000)
    total_int = high_amt * rate + (amt - high_amt) * 0.0005
    return total_int, (total_int / amt if amt > 0 else 0.0005)

def smart_allocate(total_amt, sal, total_spd, sav, engine):
    uob_s = min(total_spd, 500)
    ocbc_s = max(total_spd - 500, 0)
    _, u_eir = get_uob_stats(150000, sal, uob_s, engine.uob_tiers)
    _, o_eir = get_ocbc_stats(100000, sal, ocbc_s, sav, engine.ocbc_bonus)
    
    options = [
        {"id": "UOB", "name": "UOB One", "eir": u_eir, "cap": 150000},
        {"id": "OCBC", "name": "OCBC 360", "eir": o_eir, "cap": 100000},
        {"id": "FD", "name": "定存 / T-Bills", "eir": engine.fd_rate, "cap": 9999999}
    ]
    sorted_opts = sorted(options, key=lambda x: x['eir'], reverse=True)
    rem, alloc = total_amt, {"UOB": 0.0, "OCBC": 0.0, "FD": 0.0}
    for opt in sorted_opts:
        take = min(rem, opt['cap'])
        alloc[opt['id']] = take
        rem -= take
        if rem <= 0: break
    
    ui, _ = get_uob_stats(alloc["UOB"], sal, uob_s, engine.uob_tiers)
    oi, _ = get_ocbc_stats(alloc["OCBC"], sal, ocbc_s, sav, engine.ocbc_bonus)
    fi = alloc["FD"] * engine.fd_rate
    return (alloc, ui + oi + fi)

# ==========================================
# 3. UI 交互与审计
# ==========================================
st.set_page_config(page_title="SG WealthGuard PRO", layout="centered")
st.title("🇸🇬 SG WealthGuard PRO")

with st.sidebar:
    st.header("👤 财务参数")
    amt = st.number_input("💰 存款总额 (SGD)", value=250000.0)
    sal = st.number_input("🏦 月薪入账 (SGD)", value=10000.0)
    sav = st.checkbox("OCBC 360 每月增存 ≥$500", value=True)
    fd_val = st.slider("📈 市场定存利率 (%)", 2.0, 4.5, 3.2, 0.1)
    
    st.divider()
    st.header("⚖️ 消费损益审计器")
    spd_1 = st.number_input("输入消费方案 A (SGD)", value=800)
    spd_2 = st.number_input("输入消费方案 B (SGD)", value=1000)

engine = LiveRateEngine(fd_val)
engine.sync_rates()

if st.button("🚀 开始深度损益分析", use_container_width=True):
    # --- 逻辑修正：自动识别低消费和高消费 ---
    spd_low = min(spd_1, spd_2)
    spd_high = max(spd_1, spd_2)
    
    alloc_low, int_low = smart_allocate(amt, sal, spd_low, sav, engine)
    alloc_high, int_high = smart_allocate(amt, sal, spd_high, sav, engine)
    
    # 损益计算
    monthly_int_gain = (int_high - int_low) / 12
    extra_cost = spd_high - spd_low
    net_profit = monthly_int_gain - extra_cost

    # 1. 审计决策区
    st.subheader("📊 消费凑单决策报告")
    if extra_cost == 0:
        st.info("两个方案消费额相同，无损益差。")
    elif net_profit > 0:
        st.success(f"✅ **建议凑单**！多花的 ${extra_cost:.0f} 换回了月均 ${monthly_int_gain:.2f} 利息，净赚 **${net_profit:.2f}/月**。")
    else:
        st.error(f"🛑 **不建议凑单**！多花的 ${extra_cost:.0f} 仅换回月均 ${monthly_int_gain:.2f} 利息，亏损 **${abs(net_profit):.2f}/月**。")

    # 2. 对比细节区
    st.write("---")
    c1, c2 = st.columns(2)
    with c1:
        st.write(f"**方案 A: ${spd_low} 消费**")
        st.metric("年预估利息", f"${int_low:,.2f}")
    with c2:
        st.write(f"**方案 B: ${spd_high} 消费**")
        st.metric("年预估利息", f"${int_high:,.2f}", delta=f"${int_high - int_low:,.2f}")

    # 3. 资产分布表
    st.subheader("📍 推荐资产分布")
    final_alloc = alloc_high if net_profit > 0 else alloc_low
    st.table(pd.DataFrame([
        {"项目": "UOB One", "本金建议": f"${final_alloc['UOB']:,.0f}"},
        {"项目": "OCBC 360", "本金建议": f"${final_alloc['OCBC']:,.0f}"},
        {"项目": "定存 / T-Bills", "本金建议": f"${final_alloc['FD']:,.0f}"}
    ]))

    with st.expander("🔗 官方参考网址"):
        st.markdown("[UOB One](https://www.uob.com.sg/personal/save/cheque-savings/uob-one-account.page)")
        st.markdown("[OCBC 360](https://www.ocbc.com/personal-banking/deposits/360-savings-account)")

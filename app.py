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
        {"id": "UOB", "name": "UOB One (150k)", "eir": u_eir, "cap": 150000},
        {"id": "OCBC", "name": "OCBC 360 (100k)", "eir": o_eir, "cap": 100000},
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
# 3. UI 与 修正后的审计逻辑
# ==========================================
st.set_page_config(page_title="SG WealthGuard PRO", layout="centered")
st.title("🇸🇬 SG WealthGuard PRO")

with st.sidebar:
    st.header("👤 基础参数")
    amt = st.number_input("💰 存款总额 (SGD)", value=250000.0)
    sal = st.number_input("🏦 月薪入账 (SGD)", value=10000.0)
    sav = st.checkbox("OCBC 360 每月增存", value=True)
    fd_val = st.slider("📈 市场利率参考 (%)", 2.0, 4.5, 3.2, 0.1)
    
    st.divider()
    st.header("⚖️ 损益对冲审计")
    spd_natural = st.number_input("🍀 自然消费 (SGD)", value=900)
    spd_forced = st.number_input("🔥 凑单金额 (SGD)", value=1000)

engine = LiveRateEngine(fd_val)
engine.sync_rates()

if st.button("🚀 进行深度审计", use_container_width=True):
    alloc_n, int_n = smart_allocate(amt, sal, spd_natural, sav, engine)
    alloc_f, int_f = smart_allocate(amt, sal, spd_forced, sav, engine)
    
    monthly_gain = (int_f - int_n) / 12
    extra_cost = spd_forced - spd_natural
    net_impact = monthly_gain - extra_cost

    st.subheader("🧐 审计结论")
    
    # 逻辑修正：考虑盈亏平衡点
    if net_impact > 0.01: # 赚超过1分钱才叫赚
        st.success(f"**【建议凑单】** 划算！每月利息增量 **${monthly_gain:.2f}** 超过了额外消费 **${extra_cost:.2f}**，每月净收益 **${net_impact:.2f}**。")
        final_alloc, final_spd = alloc_f, spd_forced
    elif abs(net_impact) <= 0.01:
        st.warning(f"**【不建议凑单】** 盈亏平衡。多拿的 **${monthly_gain:.2f}** 利息刚好被多花的钱抵消。考虑到现金流，建议维持自然消费 **${spd_natural}**。")
        final_alloc, final_spd = alloc_n, spd_natural
    else:
        st.error(f"**【不要凑单】** 亏损买卖！为了多拿 **${monthly_gain:.2f}** 利息，你多花了 **${extra_cost:.2f}**，每月纯亏 **${abs(net_impact):.2f}**。建议维持自然消费 **${spd_natural}**。")
        final_alloc, final_spd = alloc_n, spd_natural

    st.write("---")
    c1, c2 = st.columns(2)
    c1.metric(f"自然方案 (${spd_natural})", f"${int_n:,.2f} /年")
    # 修复 TypeError: 确保 delta 是纯数值
    c2.metric(f"凑单方案 (${spd_forced})", f"${int_f:,.2f} /年", delta=round(int_f - int_n, 2))

    st.subheader("📍 执行资产分布建议")
    st.table(pd.DataFrame([
        {"存放账户": "UOB One", "本金": f"${final_alloc['UOB']:,.0f}"},
        {"存放账户": "OCBC 360", "本金": f"${final_alloc['OCBC']:,.0f}"},
        {"存放账户": "外部定存 / T-Bills", "本金": f"${final_alloc['FD']:,.0f}"}
    ]))

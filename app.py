import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime

# ==========================================
# 1. 动态金融数据引擎 (同步 2026 最新调息)
# ==========================================
class LiveRateEngine:
    def __init__(self, fd_input_rate):
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        # 2.0 版 UOB/OCBC 基础逻辑
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
# 2. 核心分配算法 (ZeroDivision 防护)
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
# 3. UI 交互与审计报告
# ==========================================
st.set_page_config(page_title="SG WealthGuard PRO", layout="centered")
st.title("🇸🇬 SG WealthGuard PRO")

with st.sidebar:
    st.header("👤 个人基础财务")
    amt = st.number_input("💰 准备存入的总额 (SGD)", value=250000.0)
    sal = st.number_input("🏦 每月实发薪水 (SGD)", value=10000.0)
    sav = st.checkbox("OCBC 360 每月增存 ≥$500", value=True)
    fd_val = st.slider("📈 市场外部利率参考 (%)", 2.0, 4.5, 3.2, 0.1)
    
    st.divider()
    st.header("⚖️ 消费损益对冲审计")
    spd_natural = st.number_input("🍀 平时自然消费 (SGD)", value=800)
    spd_forced = st.number_input("🔥 强行凑单金额 (SGD)", value=1000)

engine = LiveRateEngine(fd_val)
engine.sync_rates()

if st.button("🚀 进行深度盈亏审计", use_container_width=True):
    # 逻辑核心：对比“自然”与“强行”
    alloc_n, int_n = smart_allocate(amt, sal, spd_natural, sav, engine)
    alloc_f, int_f = smart_allocate(amt, sal, spd_forced, sav, engine)
    
    monthly_gain = (int_f - int_n) / 12
    extra_cost = spd_forced - spd_natural
    net_impact = monthly_gain - extra_cost

    # --- 审计结论 ---
    st.subheader("🧐 审计结论")
    if net_impact > 0:
        st.success(f"**【建议凑单】** 凑单到 ${spd_forced} 是划算的！多拿的利息不仅覆盖了多花的 ${extra_cost}，还让你每月额外净赚 **${net_impact:.2f}**。")
        final_alloc, final_int = alloc_f, int_f
        final_spd = spd_forced
    else:
        st.error(f"**【不要凑单】** 这是一笔亏本买卖！为了多拿 ${monthly_gain:.2f} 利息，你多花了 ${extra_cost}，相当于每月倒贴 **${abs(net_impact):.2f}**。建议维持自然消费 **${spd_natural}**。")
        final_alloc, final_int = alloc_n, int_n
        final_spd = spd_natural

    # --- 对比细节 ---
    st.write("---")
    col1, col2 = st.columns(2)
    col1.metric("自然消费方案", f"${int_n:,.2f} /年", f"消费 ${spd_natural}")
    col2.metric("强行凑单方案", f"${int_f:,.2f} /年", f"消费 ${spd_forced}", delta=f"${int_f - int_n:,.2f}")

    # --- 最终执行表格 ---
    st.subheader("📍 最终推荐资产分布")
    st.caption(f"已根据审计结论，自动切换至{'凑单' if net_impact > 0 else '自然'}消费模式 (月均刷卡: ${final_spd})")
    
    st.table(pd.DataFrame([
        {"存放账户": "UOB One (150k)", "建议金额": f"${final_alloc['UOB']:,.0f}"},
        {"存放账户": "OCBC 360 (100k)", "建议金额": f"${final_alloc['OCBC']:,.0f}"},
        {"存放账户": "外部定存 / T-Bills", "建议金额": f"${final_alloc['FD']:,.0f}"}
    ]))

    with st.expander("🔗 官方数据来源验证"):
        st.markdown("[UOB One 官网政策](https://www.uob.com.sg/personal/save/cheque-savings/uob-one-account.page)")
        st.markdown("[OCBC 360 官网政策](https://www.ocbc.com/personal-banking/deposits/360-savings-account)")

if datetime.now().month == 4:
    st.warning("📅 5月1日新加坡银行降息预警已激活。")

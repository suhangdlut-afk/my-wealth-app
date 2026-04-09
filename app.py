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
# 2. 核心算法 (精细化消费门槛)
# ==========================================
def get_uob_stats(amt, sal, spd_allocated, tiers):
    # UOB 门槛：分配给 UOB 的消费必须 >= 500
    if spd_allocated < 500 or sal < 1600: return amt * 0.0005, 0.0005
    total_int, rem = 0, amt
    for cap, rate in tiers:
        active = min(rem, cap)
        total_int += active * rate
        rem -= active
    total_int += rem * 0.0005
    return total_int, total_int / amt

def get_ocbc_stats(amt, sal, spd_allocated, sav, bonus):
    rate = 0.0005
    if spd_allocated >= 500: rate += bonus["spend"]
    if sal >= 1600: rate += bonus["salary"]
    if sav: rate += bonus["save"]
    high_amt = min(amt, 100000)
    total_int = high_amt * rate + (amt - high_amt) * 0.0005
    return total_int, total_int / amt

def smart_allocate(total_amt, sal, total_spd, sav, engine):
    # 策略：优先保证 UOB 的 500 消费，剩余给 OCBC
    uob_spd = min(total_spd, 500)
    ocbc_spd = max(total_spd - 500, 0)

    _, u_eir = get_uob_stats(150000, sal, uob_spd, engine.uob_tiers)
    _, o_eir = get_ocbc_stats(100000, sal, ocbc_spd, sav, engine.ocbc_bonus)
    f_eir = engine.fd_rate

    options = [
        {"id": "UOB", "name": "UOB One", "eir": u_eir, "cap": 150000},
        {"id": "OCBC", "name": "OCBC 360", "eir": o_eir, "cap": 100000},
        {"id": "FD", "name": "定存 / T-Bills", "eir": f_eir, "cap": 9999999}
    ]
    sorted_opts = sorted(options, key=lambda x: x['eir'], reverse=True)

    rem = total_amt
    allocation = {"UOB": 0, "OCBC": 0, "FD": 0}
    for opt in sorted_opts:
        if rem <= 0: break
        take = min(rem, opt['cap'])
        allocation[opt['id']] = take
        rem -= take

    u_i, _ = get_uob_stats(allocation["UOB"], sal, uob_spd, engine.uob_tiers)
    o_i, _ = get_ocbc_stats(allocation["OCBC"], sal, ocbc_spd, sav, engine.ocbc_bonus)
    f_i = allocation["FD"] * engine.fd_rate
    return allocation, u_i, o_i, f_i, sorted_opts[0]['name'], uob_spd, ocbc_spd

# ==========================================
# 3. Streamlit 界面
# ==========================================
st.set_page_config(page_title="SG WealthGuard PRO", layout="centered")
st.title("🇸🇬 SG WealthGuard PRO")

with st.sidebar:
    st.header("🔗 官方政策查阅")
    with st.expander("点击展开网址"):
        st.markdown("[UOB One 官网](https://www.uob.com.sg/personal/save/cheque-savings/uob-one-account.page)")
        st.markdown("[OCBC 360 官网](https://www.ocbc.com/personal-banking/deposits/360-savings-account)")
    
    st.header("👤 财务参数")
    amt = st.number_input("💰 存款总额 (SGD)", value=250000.0)
    sal = st.number_input("🏦 月薪入账 (SGD)", value=10000.0)
    spd = st.slider("💳 个人总月度消费 (SGD)", 0, 3000, 1000)
    sav = st.checkbox("OCBC 360: 每月存入 ≥$500", value=True)
    fd_val = st.slider("📈 定存参考利率 (%)", 2.0, 4.5, 3.2, 0.1)

engine = LiveRateEngine(fd_val)
engine.sync_rates()

if st.button("🚀 生成分配清单", use_container_width=True):
    alloc, u_i, o_i, f_i, best, u_s, o_s = smart_allocate(amt, sal, spd, sav, engine)
    
    c1, c2 = st.columns(2)
    c1.metric("年度预计利息", f"${u_i + o_i + f_i:,.2f}")
    c2.metric("综合年化收益", f"{((u_i + o_i + f_i)/amt)*100:.2f}%")

    st.subheader("📍 资金分布建议")
    st.table(pd.DataFrame([
        {"项目": "UOB One", "金额": f"${alloc['UOB']:,.0f}", "预估利息": f"${u_i:,.2f}"},
        {"项目": "OCBC 360", "金额": f"${alloc['OCBC']:,.0f}", "预估利息": f"${o_i:,.2f}"},
        {"项目": "定存 / T-Bills", "金额": f"${alloc['FD']:,.0f}", "预估利息": f"${f_i:,.2f}"}
    ]))

    # --- 核心：消费分配说明区 ---
    st.subheader("💳 信用卡刷卡方案")
    col_u, col_o = st.columns(2)
    with col_u:
        st.info(f"**UOB 卡刷卡**: ${u_s:.0f}")
        if u_s < 500: st.error("❌ 消费不足 $500")
        else: st.success("✅ 奖励已激活")
    with col_o:
        st.info(f"**OCBC 卡刷卡**: ${o_s:.0f}")
        if o_s < 500: st.warning("⚠️ 仅获基础奖励")
        else: st.success("✅ 消费奖励已激活")

    with st.expander("💡 为什么这么分配？(逻辑摘要)"):
        st.write(f"1. 系统优先分配 **$500** 给 UOB One，因为它是高息的‘入场券’。")
        st.write(f"2. 剩余的 **${o_s:.0f}** 分配给 OCBC 360。")
        st.write(f"3. 如果总消费不足 $500，算法会自动判定 UOB 无效并转向定存比价。")

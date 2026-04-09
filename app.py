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
        # 初始基准数据 (2026年4月)
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
                # 动态缩放阶梯利率
                factor = (float(uob_match[0])/100) / 0.06
                _self.uob_tiers = [(cap, rate * factor) for cap, rate in _self.uob_tiers]
            return True
        except: return False

# ==========================================
# 2. 核心算法 (含 ZeroDivisionError 防护)
# ==========================================
def get_uob_stats(amt, sal, spd_allocated, tiers):
    if amt <= 0: return 0.0, 0.0005
    if spd_allocated < 500 or sal < 1600: return amt * 0.0005, 0.0005
    total_int, rem = 0.0, amt
    for cap, rate in tiers:
        active = min(rem, cap)
        total_int += active * rate
        rem -= active
    total_int += rem * 0.0005
    eir = total_int / amt if amt > 0 else 0.0005
    return total_int, eir

def get_ocbc_stats(amt, sal, spd_allocated, sav, bonus):
    if amt <= 0: return 0.0, 0.0005
    rate = 0.0005
    if spd_allocated >= 500: rate += bonus["spend"]
    if sal >= 1600: rate += bonus["salary"]
    if sav: rate += bonus["save"]
    high_amt = min(amt, 100000)
    total_int = high_amt * rate + (amt - high_amt) * 0.0005
    eir = total_int / amt if amt > 0 else 0.0005
    return total_int, eir

def smart_allocate(total_amt, sal, total_spd, sav, engine):
    # 消费分流方案
    uob_spd_plan = min(total_spd, 500)
    ocbc_spd_plan = max(total_spd - 500, 0)

    # 竞争力评估
    _, u_eir = get_uob_stats(150000, sal, uob_spd_plan, engine.uob_tiers)
    _, o_eir = get_ocbc_stats(100000, sal, ocbc_spd_plan, sav, engine.ocbc_bonus)
    f_eir = engine.fd_rate

    options = [
        {"id": "UOB", "name": "UOB One (账户)", "eir": u_eir, "cap": 150000},
        {"id": "OCBC", "name": "OCBC 360 (账户)", "eir": o_eir, "cap": 100000},
        {"id": "FD", "name": "定存 / T-Bills", "eir": f_eir, "cap": 9999999}
    ]
    sorted_opts = sorted(options, key=lambda x: x['eir'], reverse=True)

    rem = total_amt
    allocation = {"UOB": 0.0, "OCBC": 0.0, "FD": 0.0}
    for opt in sorted_opts:
        if rem <= 0: break
        take = min(rem, opt['cap'])
        allocation[opt['id']] = take
        rem -= take

    u_i, _ = get_uob_stats(allocation["UOB"], sal, uob_spd_plan, engine.uob_tiers)
    o_i, _ = get_ocbc_stats(allocation["OCBC"], sal, ocbc_spd_plan, sav, engine.ocbc_bonus)
    f_i = allocation["FD"] * engine.fd_rate
    return allocation, u_i, o_i, f_i, sorted_opts[0]['name'], uob_spd_plan, ocbc_spd_plan

# ==========================================
# 3. Streamlit UI
# ==========================================
st.set_page_config(page_title="SG WealthGuard PRO", layout="centered")
st.title("🇸🇬 SG WealthGuard PRO")

with st.sidebar:
    st.header("🔗 官方数据查阅")
    with st.expander("查看官方最新政策"):
        st.markdown("[UOB One 官方详情](https://www.uob.com.sg/personal/save/cheque-savings/uob-one-account.page)")
        st.markdown("[OCBC 360 官方详情](https://www.ocbc.com/personal-banking/deposits/360-savings-account)")
        st.markdown("[MAS T-Bills 实时结果](https://www.mas.gov.sg/bonds-and-bills/auctions-and-issuance-calendar)")
    st.divider()
    st.header("👤 财务参数设置")
    amt = st.number_input("💰 存款总额 (SGD)", min_value=0.0, value=250000.0, step=1000.0)
    sal = st.number_input("🏦 月薪入账 (SGD)", min_value=0.0, value=10000.0)
    spd = st.slider("💳 每月总消费 (SGD)", 0, 5000, 1000)
    sav = st.checkbox("OCBC 360: 每月增存 ≥$500", value=True)
    st.divider()
    st.header("📈 市场调节")
    fd_val = st.slider("当前定存/T-Bills 利率 (%)", 2.0, 4.5, 3.2, 0.1)

# 初始化与运行
engine = LiveRateEngine(fd_val)
engine.sync_rates()

if st.button("🚀 生成最优资产分配清单", use_container_width=True):
    alloc, u_i, o_i, f_i, best, u_s, o_s = smart_allocate(amt, sal, spd, sav, engine)
    total_i = u_i + o_i + f_i

    # 数据看板
    c1, c2 = st.columns(2)
    c1.metric("预计总利息 (年)", f"${total_i:,.2f}")
    c2.metric("综合收益率", f"{(total_i/amt)*100:.2f}%" if amt > 0 else "0.00%")

    st.success(f"🏆 **优先建议**：资金首选存入 **{best}**")

    # 展示表格
    df_res = pd.DataFrame([
        {"项目": "UOB One (150k限额)", "存放金额": f"${alloc['UOB']:,.0f}", "预估利息": f"${u_i:,.2f}"},
        {"项目": "OCBC 360 (100k限额)", "存放金额": f"${alloc['OCBC']:,.0f}", "预估利息": f"${o_i:,.2f}"},
        {"项目": "定存 / T-Bills", "存放金额": f"${alloc['FD']:,.0f}", "预估利息": f"${f_i:,.2f}"}
    ])
    st.table(df_res)

    # 消费分流说明
    st.subheader("💳 信用卡刷卡方案")
    col_u, col_o = st.columns(2)
    with col_u:
        st.info(f"**UOB 卡刷卡**: ${u_s:.0f}")
        if u_s < 500: st.error("❌ UOB 门槛未达标")
    with col_o:
        st.info(f"**OCBC 卡刷卡**: ${o_s:.0f}")
        if o_s < 500: st.warning("⚠️ 消费奖未激活")

    with st.expander("💡 逻辑摘要"):
        st.write("1. 系统自动分配前 $500 消费给 UOB One 以激活高息入门条件。")
        st.write("2. 算法已修复分配金额为 0 时的计算逻辑。")
        st.write("3. 侧边栏提供官方网址用于实时交叉验证政策。")

if datetime.now().month == 4:
    st.warning("📅 5月1日调息预警：系统将自动感知 UOB 利率下调。")

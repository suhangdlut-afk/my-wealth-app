import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime

# ==========================================
# 1. 动态金融数据引擎 (含实时爬虫)
# ==========================================
class LiveRateEngine:
    def __init__(self, fd_input_rate):
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        # 初始基准 (2026 4月 UOB Tiers)
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
# 2. 精确收益算法 (Tiered & Threshold Logic)
# ==========================================
def get_uob_stats(amt, sal, spd_allocated, tiers):
    # UOB 强门槛：消费不满 500，全盘回落至 0.05%
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
    # 策略：优先满足 UOB 的 500 消费，剩余分给 OCBC
    uob_spd_plan = min(total_spd, 500)
    ocbc_spd_plan = max(total_spd - 500, 0)

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
    allocation = {"UOB": 0, "OCBC": 0, "FD": 0}
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
# 3. Streamlit UI 界面
# ==========================================
st.set_page_config(page_title="SG WealthGuard PRO", layout="centered")
st.title("🇸🇬 SG WealthGuard PRO")

# --- 侧边栏：官方查阅中心 & 参数设置 ---
with st.sidebar:
    st.header("🔗 官方政策查阅")
    with st.expander("点击展开参考网址"):
        st.markdown("""
        **银行官网政策:**
        * [UOB One 账户条款](https://www.uob.com.sg/personal/save/cheque-savings/uob-one-account.page)
        * [OCBC 360 账户条款](https://www.ocbc.com/personal-banking/deposits/360-savings-account)
        
        **实时利率参考:**
        * [MAS T-Bills 竞标结果](https://www.mas.gov.sg/bonds-and-bills/auctions-and-issuance-calendar)
        * [SingSaver 定存利率汇总](https://www.singsaver.com.sg/blog/best-fixed-deposit-rates-singapore)
        """)
    st.divider()
    
    st.header("👤 财务参数设置")
    amt = st.number_input("💰 存款总额 (SGD)", min_value=0.0, value=250000.0, step=1000.0)
    sal = st.number_input("🏦 月薪入账 (SGD)", min_value=0.0, value=10000.0)
    spd = st.slider("💳 个人每月总消费 (SGD)", 0, 5000, 1000)
    sav = st.checkbox("OCBC 360: 每月增存 ≥$500", value=True)
    st.divider()
    
    st.header("📈 市场调节")
    fd_val = st.slider("当前定存/T-Bills 利率 (%)", 2.0, 4.5, 3.2, 0.1)

# 初始化引擎
engine = LiveRateEngine(fd_val)
engine.sync_rates()

if st.button("🚀 生成最优资产分配清单", use_container_width=True):
    alloc, u_i, o_i, f_i, best, u_s, o_s = smart_allocate(amt, sal, spd, sav, engine)
    total_i = u_i + o_i + f_i

    # 数据看板
    c1, c2 = st.columns(2)
    c1.metric("年度预计利息", f"${total_i:,.2f}")
    c2.metric("资产综合收益率", f"{(total_i/amt)*100:.2f}%")

    st.success(f"🏆 **决策建议**：当前条件下优先级最高的是 **{best}**")

    # 分布表格
    df_res = pd.DataFrame([
        {"项目": "UOB One (150k限额)", "存放本金": f"${alloc['UOB']:,.0f}", "预估年利息": f"${u_i:,.2f}"},
        {"项目": "OCBC 360 (100k限额)", "存放本金": f"${alloc['OCBC']:,.0f}", "预估年利息": f"${o_i:,.2f}"},
        {"项目": "定存 / T-Bills", "存放本金": f"${alloc['FD']:,.0f}", "预估年利息": f"${f_i:,.2f}"}
    ])
    st.table(df_res)

    # 消费分流说明
    st.subheader("💳 信用卡刷卡方案")
    col_u, col_o = st.columns(2)
    with col_u:
        st.info(f"**UOB 卡刷卡**: ${u_s:.0f}")
        if u_s < 500: st.error("❌ UOB 高息门槛未达标")
    with col_o:
        st.info(f"**OCBC 卡刷卡**: ${o_s:.0f}")
        if o_s < 500: st.warning("⚠️ 仅获基础奖励")

    with st.expander("💡 执行必看指令"):
        st.write("1. **薪水归集**：薪水发往 OCBC 360。")
        st.write("2. **指令对倒**：每月从 OCBC 转 $1,601 至 UOB，备注填写 'SALARY'。")
        if u_s < 500:
            st.warning("由于消费不满 $500，UOB 账户已失去竞争力，系统自动将资金导向了定存或 OCBC。")

if datetime.now().month == 4:
    st.warning("📅 5月1日调息提醒：系统将根据 SingSaver 自动抓取最新阶梯。")

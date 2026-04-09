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
# 2. 核心算法 (保持阶梯比价逻辑)
# ==========================================
def get_uob_stats(amt, sal, spd, tiers):
    if amt <= 0: return 0, 0
    if spd < 500 or sal < 1600: return amt * 0.0005, 0.0005
    total_int, rem = 0, amt
    for cap, rate in tiers:
        active = min(rem, cap)
        total_int += active * rate
        rem -= active
    total_int += rem * 0.0005
    return total_int, total_int / amt

def get_ocbc_stats(amt, sal, spd, sav, bonus):
    if amt <= 0: return 0, 0
    rate = 0.0005
    if spd >= 500: rate += bonus["spend"]
    if sal >= 1600: rate += bonus["salary"]
    if sav: rate += bonus["save"]
    high_amt = min(amt, 100000)
    total_int = high_amt * rate + (amt - high_amt) * 0.0005
    return total_int, total_int / amt

def smart_allocate(total_amt, sal, spd, sav, engine):
    _, u_eir = get_uob_stats(150000, sal, spd, engine.uob_tiers)
    _, o_eir = get_ocbc_stats(100000, sal, spd, sav, engine.ocbc_bonus)
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
    u_i, _ = get_uob_stats(allocation["UOB"], sal, spd, engine.uob_tiers)
    o_i, _ = get_ocbc_stats(allocation["OCBC"], sal, spd, sav, engine.ocbc_bonus)
    f_i = allocation["FD"] * engine.fd_rate
    return allocation, u_i, o_i, f_i, sorted_opts[0]['name']

# ==========================================
# 3. Streamlit 界面
# ==========================================
st.set_page_config(page_title="SG WealthGuard PRO", layout="centered")
st.title("🇸🇬 SG WealthGuard PRO")

# --- 新增：官方查阅中心 (侧边栏) ---
with st.sidebar:
    st.header("🔗 官方数据查阅")
    with st.expander("点击查看原始政策网址"):
        st.markdown("""
        **银行官网 (利息计算器):**
        * [UOB One Account 官网](https://www.uob.com.sg/personal/save/cheque-savings/uob-one-account.page)
        * [OCBC 360 Account 官网](https://www.ocbc.com/personal-banking/deposits/360-savings-account)
        
        **定存与国库券 (实时利率):**
        * [MAS T-Bills 竞标结果](https://www.mas.gov.sg/bonds-and-bills/auctions-and-issuance-calendar)
        * [SingSaver 定存对比汇总](https://www.singsaver.com.sg/blog/best-fixed-deposit-rates-singapore)
        
        **第三方监控:**
        * [Seedly 社区评测](https://seedly.sg/reviews/savings-accounts/)
        """)
    st.divider()
    
    st.header("👤 财务参数设置")
    amt = st.number_input("💰 存款总额 (SGD)", min_value=0.0, value=250000.0, step=1000.0)
    sal = st.number_input("🏦 月薪入账 (SGD)", min_value=0.0, value=10000.0)
    spd = st.slider("💳 月度消费 (SGD)", 0, 5000, 800)
    sav = st.checkbox("OCBC 360: 每月存入 ≥$500", value=True)
    st.divider()
    st.header("📈 定存基准调节")
    fd_val = st.slider("当前市场定存利率 (%)", 2.0, 4.5, 3.2, 0.1)

# 初始化与诊断
engine = LiveRateEngine(fd_val)
engine.sync_rates()

if st.button("🚀 生成最优资产分配清单", use_container_width=True):
    alloc, u_i, o_i, f_i, best = smart_allocate(amt, sal, spd, sav, engine)
    total_i = u_i + o_i + f_i

    # 指标看板
    c1, c2 = st.columns(2)
    c1.metric("年度预计利息", f"${total_i:,.2f}")
    c2.metric("综合年化收益率", f"{(total_i/amt)*100:.2f}%")

    st.success(f"🏆 **决策建议**：当前第一优先级应存入 **{best}**")

    # 表格展示
    df_res = pd.DataFrame([
        {"项目": "UOB One (150k限额)", "存放金额": f"${alloc['UOB']:,.0f}", "预估利息": f"${u_i:,.2f}"},
        {"项目": "OCBC 360 (100k限额)", "存放金额": f"${alloc['OCBC']:,.0f}", "预估利息": f"${o_i:,.2f}"},
        {"项目": "定存 / T-Bills", "存放金额": f"${alloc['FD']:,.0f}", "预估利息": f"${f_i:,.2f}"}
    ])
    st.table(df_res)

    with st.expander("💡 执行指令"):
        st.write("1. 薪水发往 OCBC，每月对倒 $1,601 至 UOB (备注 'SALARY')。")
        if spd < 500:
            st.warning("⚠️ 消费不满 $500：UOB 已失效，资金已重定向至定存。")

if datetime.now().month == 4:
    st.warning("📅 5月1日调息预警：系统将自动同步官网数据。您可以点击侧边栏链接手动核实官方公告。")

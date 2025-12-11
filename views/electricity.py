import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Dict, Tuple
from components.cards import section_header

# 引入原 app.py 的計算邏輯類
class ElectricityCalculatorV10:
    def __init__(self):
        self.errors = []
        self.unit_price = 0
        self.tdy_total_kwh = 0
        self.tdy_total_fee = 0
        self.meter_total_kwh = 0
        self.public_kwh = 0
        self.public_per_room = 0
        self.non_sharing_records = {}

    def check_tdy_bills(self, tdy_data: Dict[str, Tuple[float, float]]) -> bool:
        valid_count = 0
        total_kwh = 0
        total_fee = 0
        for floor, (fee, kwh) in tdy_data.items():
            if fee > 0 and kwh > 0:
                valid_count += 1
                total_kwh += kwh
                total_fee += fee
        
        if valid_count == 0:
            self.errors.append("🚨 沒有任何有效的台電單據")
            return False
        
        self.unit_price = total_fee / total_kwh
        self.tdy_total_kwh = total_kwh
        self.tdy_total_fee = total_fee
        return True

    def check_meter_readings(self, meter_data: Dict[str, Tuple[float, float]]) -> bool:
        valid_count = 0
        total_kwh = 0
        SHARING_ROOMS = ["2A", "2B", "3A", "3B", "3C", "3D", "4A", "4B", "4C", "4D"]
        
        for room in SHARING_ROOMS:
            if room in meter_data:
                start, end = meter_data[room]
                if end > start:
                    usage = round(end - start, 2)
                    valid_count += 1
                    total_kwh += usage
                elif end < start and not (start == 0 and end == 0):
                    self.errors.append(f"🚨 {room}: 本期讀數 < 上期讀數")
        
        if valid_count == 0:
            self.errors.append("🚨 沒有有效的分攤房間度數")
            return False
        
        self.meter_total_kwh = round(total_kwh, 2)
        return True

    def calculate_public_electricity(self) -> bool:
        SHARING_ROOMS = ["2A", "2B", "3A", "3B", "3C", "3D", "4A", "4B", "4C", "4D"]
        self.public_kwh = round(self.tdy_total_kwh - self.meter_total_kwh, 2)
        
        if self.public_kwh < 0:
            self.errors.append(f"🚨 計算錯誤：公用電度數為負數 (台電總度數 < 房間總度數)")
            return False
        
        self.public_per_room = round(self.public_kwh / len(SHARING_ROOMS))
        return True

    def diagnose(self) -> Tuple[bool, str]:
        if self.errors:
            error_msg = "\n".join([f"• {e}" for e in self.errors])
            return False, error_msg
        return True, "✅ 計算驗證通過"

ALL_ROOMS = ["1A", "1B", "2A", "2B", "3A", "3B", "3C", "3D", "4A", "4B", "4C", "4D"]

def render(db):
    section_header("⚡ 電費管理", "Electricity Management")
    
    if "current_period_id" not in st.session_state:
        st.session_state.current_period_id = None
        
    tab1, tab2, tab3 = st.tabs(["1️⃣ 新增計費期間", "2️⃣ 度數輸入與計算", "3️⃣ 歷史查詢"])
    
    # --- 新增期間 ---
    with tab1:
        with st.form("new_period_form", border=True):
            st.subheader("建立新的電費計算週期")
            c1, c2, c3 = st.columns(3)
            y = c1.number_input("年份", value=datetime.now().year)
            ms = c2.number_input("開始月份", 1, 12, 1)
            me = c3.number_input("結束月份", 1, 12, 2)
            
            if st.form_submit_button("建立期間", type="primary"):
                ok, msg, pid = db.add_electricity_period(y, ms, me)
                if ok:
                    st.session_state.current_period_id = pid
                    st.toast(msg, icon="✅")
                    st.rerun()
                else:
                    st.toast(msg, icon="❌")

    # --- 計算 ---
    with tab2:
        if not st.session_state.current_period_id:
            st.warning("請先在「新增計費期間」建立一個週期，或從歷史記錄選擇。")
        else:
            st.info(f"正在計算 Period ID: {st.session_state.current_period_id}")
            with st.form("calc_form", border=True):
                st.markdown("#### A. 台電單據 (金額/度數)")
                c1, c2, c3 = st.columns(3)
                # 簡單起見，使用 columns 布局
                f2 = c1.number_input("2F 金額", key="f2", min_value=0)
                k2 = c1.number_input("2F 度數", key="k2", min_value=0.0)
                
                f3 = c2.number_input("3F 金額", key="f3", min_value=0)
                k3 = c2.number_input("3F 度數", key="k3", min_value=0.0)
                
                f4 = c3.number_input("4F 金額", key="f4", min_value=0)
                k4 = c3.number_input("4F 度數", key="k4", min_value=0.0)
                
                st.divider()
                st.markdown("#### B. 房間抄表 (上期 -> 本期)")
                
                # 使用 Grid
                cols = st.columns(4)
                for i, room in enumerate(ALL_ROOMS):
                    with cols[i % 4]:
                        st.markdown(f"**{room}**")
                        st.number_input("始", key=f"s_{room}", min_value=0.0, label_visibility="collapsed")
                        st.number_input("終", key=f"e_{room}", min_value=0.0, label_visibility="collapsed")
                
                notes = st.text_area("計算備註")
                
                if st.form_submit_button("開始計算並儲存", type="primary"):
                    calc = ElectricityCalculatorV10()
                    
                    tdy_data = {
                        "2F": (st.session_state.f2, st.session_state.k2),
                        "3F": (st.session_state.f3, st.session_state.k3),
                        "4F": (st.session_state.f4, st.session_state.k4)
                    }
                    
                    meter_data = {
                        r: (st.session_state[f"s_{r}"], st.session_state[f"e_{r}"]) 
                        for r in ALL_ROOMS
                    }
                    
                    # 執行檢查
                    check1 = calc.check_tdy_bills(tdy_data)
                    check2 = calc.check_meter_readings(meter_data)
                    
                    if check1 and check2:
                        if calc.calculate_public_electricity():
                            # 儲存至 DB
                            ok, msg, df = db.calculate_electricity_fee(
                                st.session_state.current_period_id, calc, meter_data, notes
                            )
                            if ok:
                                st.success("計算成功！")
                                st.dataframe(df)
                            else:
                                st.error(f"儲存失敗: {msg}")
                        else:
                            st.error(f"公用電計算失敗: {calc.errors}")
                    else:
                        st.error(f"數據檢查失敗: {calc.errors}")

    # --- 歷史 ---
    with tab3:
        periods = db.get_all_periods()
        if not periods:
            st.info("無歷史資料")
        else:
            opts = {f"{p['period_year']}年 {p['period_month_start']}-{p['period_month_end']}月 (ID:{p['id']})": p['id'] for p in periods}
            sel = st.selectbox("選擇歷史期間", list(opts.keys()))
            if sel:
                pid = opts[sel]
                report = db.get_period_report(pid)
                st.dataframe(report, use_container_width=True)
                if st.button("設為當前計算期間"):
                    st.session_state.current_period_id = pid
                    st.rerun()
import streamlit as st
import time
from datetime import datetime, date
from components.cards import section_header

WATER_FEE = 100

def render(db):
    section_header("💵 租金收繳", "Rent Collection")
    
    tab1, tab2, tab3, tab4 = st.tabs(["單筆預填", "批量預填", "確認繳費", "統計"])
    
    # --- 單筆預填 ---
    with tab1:
        st.markdown("##### 📌 單筆租金預填")
        tenants = db.get_tenants()
        if tenants.empty:
            st.warning("暫無房客資料，請先至房客管理新增。")
        else:
            with st.container(border=True):
                c1, c2, c3 = st.columns(3)
                with c1:
                    room_options = {f"{r['room_number']} - {r['tenant_name']}": r['room_number'] for _, r in tenants.iterrows()}
                    selected_label = st.selectbox("選擇房間", list(room_options.keys()))
                    room = room_options[selected_label]
                    t_data = tenants[tenants['room_number'] == room].iloc[0]
                with c2: year = st.number_input("年份", value=datetime.now().year)
                with c3: month = st.number_input("月份", value=datetime.now().month, min_value=1, max_value=12)
                
                st.divider()
                
                base_rent = float(t_data['base_rent'])
                water_fee = WATER_FEE if t_data['has_water_fee'] else 0
                
                cc1, cc2, cc3 = st.columns(3)
                with cc1: new_base = st.number_input("基本租金", value=base_rent, step=100.0)
                with cc2: new_water = st.number_input("水費", value=float(water_fee), step=50.0)
                with cc3: new_discount = st.number_input("優惠折扣", value=0.0, step=100.0)
                
                final = new_base + new_water - new_discount
                st.metric("本期應收", f"${final:,.0f}")
                
                notes = st.text_input("備註說明")
                
                if st.button("建立應收單", type="primary", use_container_width=True):
                    ok, msg = db.batch_record_rent(room, t_data['tenant_name'], year, month, 1, new_base, new_water, new_discount, t_data['payment_method'], notes)
                    if ok: st.toast(msg, icon="✅"); time.sleep(1); st.rerun()
                    else: st.toast(msg, icon="❌")

    # --- 批量預填 ---
    with tab2:
        st.markdown("##### 📚 批量租金預填")
        if tenants.empty:
            st.warning("暫無房客")
        else:
            with st.container(border=True):
                # 選擇房客
                room_options = {f"{r['room_number']} - {r['tenant_name']}": r['room_number'] for _, r in tenants.iterrows()}
                selected_label_batch = st.selectbox("選擇房間", list(room_options.keys()), key="batch_room")
                room_batch = room_options[selected_label_batch]
                t_data_batch = tenants[tenants['room_number'] == room_batch].iloc[0]
                
                c1, c2 = st.columns(2)
                start_year = c1.number_input("起始年份", value=datetime.now().year, key="b_year")
                start_month = c2.number_input("起始月份", value=datetime.now().month, min_value=1, max_value=12, key="b_month")
                
                months_count = st.slider("預填月數", 1, 12, 12)
                
                if st.button("🚀 執行批量預填", type="primary", use_container_width=True):
                    # 使用預設租金與水費
                    base = float(t_data_batch['base_rent'])
                    water = WATER_FEE if t_data_batch['has_water_fee'] else 0
                    ok, msg = db.batch_record_rent(
                        room_batch, t_data_batch['tenant_name'], 
                        start_year, start_month, months_count, 
                        base, water, 0, 
                        t_data_batch['payment_method'], "批量建立"
                    )
                    if ok: st.toast(msg, icon="✅"); time.sleep(1); st.rerun()
                    else: st.toast(msg, icon="❌")

    # --- 確認繳費 ---
    with tab3:
        st.markdown("##### ✅ 確認繳費")
        pending = db.get_pending_rents()
        if pending.empty:
            st.info("目前無待確認的租金單")
        else:
            # 篩選掉已收的 (雖然 SQL 已經篩選了)
            pending_only = pending[pending['status'] != '已收']
            
            for _, row in pending_only.iterrows():
                with st.container(border=True):
                    cols = st.columns([2, 1, 1, 1])
                    cols[0].write(f"**{row['room_number']}** {row['tenant_name']}")
                    cols[1].write(f"{row['year']}年{row['month']}月")
                    cols[2].write(f"**${row['actual_amount']:,.0f}**")
                    if cols[3].button("確認收款", key=f"pay_{row['id']}"):
                        ok, msg = db.confirm_rent_payment(row['id'], date.today().strftime("%Y-%m-%d"), row['actual_amount'])
                        if ok: st.toast(msg, icon="✅"); time.sleep(0.5); st.rerun()

    # --- 統計 ---
    with tab4:
        st.markdown("##### 📊 年度統計")
        y_stat = st.number_input("統計年份", value=datetime.now().year, key="stat_y")
        summary = db.get_rent_summary(y_stat)
        
        sc1, sc2, sc3 = st.columns(3)
        sc1.metric("應收總額", f"${summary['total_due']:,.0f}")
        sc2.metric("已收總額", f"${summary['total_paid']:,.0f}")
        sc3.metric("未收餘額", f"${summary['total_unpaid']:,.0f}", delta_color="inverse")
        
        st.dataframe(db.get_rent_records(year=y_stat), use_container_width=True)
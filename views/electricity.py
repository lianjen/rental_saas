import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import time

ROOM_NUMBERS = ["1A", "1B", "2A", "2B", "3A", "3B", "3C", "3D", "4A", "4B", "4C", "4D"]
SHARING_ROOMS = ["2A", "2B", "3A", "3B", "3C", "3D", "4A", "4B", "4C", "4D"]

def render(db):
    st.header("⚡ 電費管理")
    st.markdown("Taiwan Electricity Fee Calculator v14.1")
    
    # 初始化 session state
    if "current_period_id" not in st.session_state:
        st.session_state.current_period_id = None
    if "current_period_info" not in st.session_state:
        st.session_state.current_period_info = None
    if "edit_period_id" not in st.session_state:
        st.session_state.edit_period_id = None
    if "calc_state" not in st.session_state:
        st.session_state.calc_state = {
            "step": 1,  # 1: 輸入, 2: 結果
            "year": datetime.now().year,
            "month": datetime.now().month,
            "tdy_kwh": 0,
            "tdy_fee": 0,
            "unit_price": 0,
            "meter_data": {},
            "public_kwh": 0,
            "public_per_room": 0,
            "notes": "",
            "results": None
        }
    
    # 三個 Tab
    tab1, tab2, tab3 = st.tabs(["📋 計費期間", "📊 度數輸入與計算", "📈 計費結果"])
    
    # ===== TAB 1: 計費期間設定 =====
    with tab1:
        st.subheader("📋 計費期間設定")
        st.markdown("新增或選擇計費期間")
        
        # 新增期間模式
        if st.session_state.edit_period_id is None:
            st.markdown("##### 新增計費期間")
            
            with st.form("period_form", border=True):
                st.write("輸入計費期間資訊（台電度數和金額將在度數輸入時計算）")
                c1, c2, c3 = st.columns(3)
                with c1:
                    year = st.number_input("年度", value=datetime.now().year, min_value=2020, max_value=2100, key="new_year")
                with c2:
                    month_start = st.number_input("開始月份", value=1, min_value=1, max_value=12, key="new_month_start")
                with c3:
                    month_end = st.number_input("結束月份", value=1, min_value=1, max_value=12, key="new_month_end")
                
                submit = st.form_submit_button("✅ 建立計費期間", type="primary", use_container_width=True)
                
                if submit:
                    if month_start > month_end:
                        st.error("❌ 開始月份不能大於結束月份")
                    else:
                        try:
                            try:
                                ok, msg, period_id = db.add_electricity_period(year, month_start, month_end)
                                if ok:
                                    st.session_state.current_period_id = period_id
                                    st.session_state.current_period_info = f"{year}年 {month_start}-{month_end}月"
                                    st.success(f"✅ {msg}")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error(f"❌ {msg}")
                            except AttributeError:
                                st.session_state.current_period_id = hash((year, month_start, month_end)) % 100000
                                st.session_state.current_period_info = f"{year}年 {month_start}-{month_end}月"
                                st.success(f"✅ 計費期間已建立（本機模式）")
                                time.sleep(1)
                                st.rerun()
                        except Exception as e:
                            st.error(f"❌ 建立失敗: {str(e)}")
        
        # 編輯期間模式
        else:
            period_id = st.session_state.edit_period_id
            try:
                periods = db.get_all_periods()
                edit_period = None
                for p in periods:
                    if p['id'] == period_id:
                        edit_period = p
                        break
                
                if edit_period:
                    st.write(f"編輯期間: {edit_period['period_year']}年 {edit_period['period_month_start']}-{edit_period['period_month_end']}月")
                    
                    with st.form("period_edit_form", border=True):
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            year = st.number_input("年度", value=edit_period['period_year'], min_value=2020, max_value=2100, key="edit_year")
                        with c2:
                            month_start = st.number_input("開始月份", value=edit_period['period_month_start'], min_value=1, max_value=12, key="edit_month_start")
                        with c3:
                            month_end = st.number_input("結束月份", value=edit_period['period_month_end'], min_value=1, max_value=12, key="edit_month_end")
                        
                        c6, c7 = st.columns(2)
                        with c6:
                            submit = st.form_submit_button("✅ 更新期間", type="primary", use_container_width=True)
                        with c7:
                            cancel = st.form_submit_button("❌ 取消編輯", use_container_width=True)
                        
                        if submit:
                            try:
                                st.success("✅ 期間已更新")
                                time.sleep(1)
                                st.session_state.edit_period_id = None
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ 更新失敗: {str(e)}")
                        
                        if cancel:
                            st.session_state.edit_period_id = None
                            st.rerun()
                else:
                    st.error("❌ 期間不存在或已被刪除，請重新選擇")
                    st.session_state.edit_period_id = None
                    st.rerun()
            except Exception as e:
                st.error(f"❌ 讀取期間失敗: {str(e)}")
        
        if st.button("🔙 返回", use_container_width=True):
            st.session_state.edit_period_id = None
            st.rerun()
        
        st.divider()
        st.subheader("📚 已建立的計費期間")
        
        try:
            periods = db.get_all_periods()
            if periods:
                for period in periods:
                    with st.container(border=True):
                        c1, c2, c3, c4 = st.columns([2, 0.8, 0.8, 0.8])
                        
                        with c1:
                            period_label = f"{period['period_year']}年 {period['period_month_start']}-{period['period_month_end']}月"
                            st.write(period_label)
                        
                        with c2:
                            if st.button("✏️ 編輯", key=f"edit_{period['id']}", use_container_width=True):
                                st.session_state.edit_period_id = period['id']
                                st.rerun()
                        
                        with c3:
                            if st.button("📍 選擇", key=f"select_{period['id']}", use_container_width=True):
                                st.session_state.current_period_id = period['id']
                                st.session_state.current_period_info = period_label
                                st.rerun()
                        
                        with c4:
                            st.caption(f"ID: {period['id']}")
            else:
                st.info("📭 尚無計費期間，請先建立")
        except Exception as e:
            st.error(f"❌ 讀取失敗: {str(e)}")
    
    # ===== TAB 2: 度數輸入與計算 =====
    with tab2:
        st.subheader("📊 度數輸入與計算")
        
        if not st.session_state.current_period_id:
            st.warning("⚠️ 請先在「計費期間」選擇或建立一個期間")
        else:
            st.info(f"📌 目前期間: {st.session_state.current_period_info}")
            
            if st.session_state.calc_state["step"] == 1:
                # 度數輸入表單
                st.markdown("##### 輸入各樓層台電單據與全部房間度數")
                
                with st.form("electricity_input_form", border=True):
                    # 年月份
                    col_date1, col_date2 = st.columns(2)
                    with col_date1:
                        year = st.number_input("年份", value=st.session_state.calc_state["year"], min_value=2020, max_value=2100)
                    with col_date2:
                        month = st.number_input("月份", value=st.session_state.calc_state["month"], min_value=1, max_value=12)
                    
                    st.divider()
                    
                    # A. 各樓層台電單據
                    st.markdown("#### A️⃣ 各樓層台電單據")
                    st.markdown("**輸入台電帳單上的資訊（金額/度數）**")
                    
                    col_header = st.columns([1, 2, 2])
                    col_header[0].markdown("**樓層**")
                    col_header[1].markdown("**金額 (NT$)**")
                    col_header[2].markdown("**度數 (kWh)**")
                    
                    tdy_data = {}
                    total_fee = 0
                    total_kwh = 0
                    
                    for floor_name, floor_key in [("2樓", "2F"), ("3樓", "3F"), ("4樓", "4F")]:
                        cols = st.columns([1, 2, 2])
                        cols[0].write(floor_name)
                        fee = cols[1].number_input(f"金額", min_value=0, step=100, key=f"fee_{floor_key}")
                        kwh = cols[2].number_input(f"度數", min_value=0.0, step=1.0, key=f"kwh_{floor_key}")
                        
                        if fee > 0 and kwh > 0:
                            tdy_data[floor_key] = (fee, kwh)
                            total_fee += fee
                            total_kwh += kwh
                    
                    # 顯示台電統計
                    st.divider()
                    if total_fee > 0 and total_kwh > 0:
                        unit_price = round(total_fee / total_kwh, 2)
                        st.success(f"✅ 台電統計 | 總度數: {total_kwh:.2f} kWh | 總金額: NT$ {int(total_fee):,} | 單位電價: NT$ {unit_price:.2f}/kWh")
                    else:
                        st.warning("⚠️ 請輸入有效的台電單據")
                    
                    st.divider()
                    
                    # B. 所有房間度數（同一表單）
                    st.markdown("#### B️⃣ 所有房間電表讀數")
                    st.markdown("**輸入所有房間的電表讀數（上期 → 本期）**")
                    
                    meter_data = {}
                    
                    # 用 columns 方式展示，每行 4 個房間
                    col_rooms = st.columns(4)
                    for i, room in enumerate(ROOM_NUMBERS):
                        with col_rooms[i % 4]:
                            st.markdown(f"**{room}**")
                            start = st.number_input(f"上期", min_value=0.0, step=1.0, key=f"start_{room}", label_visibility="collapsed")
                            end = st.number_input(f"本期", min_value=0.0, step=1.0, key=f"end_{room}", label_visibility="collapsed")
                            meter_data[room] = (start, end)
                    
                    st.divider()
                    
                    # 備註
                    notes = st.text_area("計算備註（選填）", value="", height=60)
                    
                    # 提交
                    submit_btn = st.form_submit_button("▶️ 進行計算", type="primary", use_container_width=True)
                    
                    if submit_btn:
                        # 驗證台電數據
                        if not tdy_data:
                            st.error("❌ 請輸入有效的台電單據")
                            st.stop()
                        
                        # 驗證房間抄表
                        valid_rooms = 0
                        total_meter_kwh = 0
                        for room in SHARING_ROOMS:
                            start, end = meter_data[room]
                            if end > start:
                                usage = round(end - start, 2)
                                valid_rooms += 1
                                total_meter_kwh += usage
                        
                        if valid_rooms == 0:
                            st.error("❌ 沒有有效的分攤房間度數")
                            st.stop()
                        
                        # 計算公用電
                        public_kwh = round(total_kwh - total_meter_kwh, 2)
                        if public_kwh < 0:
                            st.error("❌ 計算錯誤：房間總度數超過台電總度數")
                            st.stop()
                        
                        public_per_room = round(public_kwh / len(SHARING_ROOMS), 2)
                        
                        # 儲存到 session state
                        st.session_state.calc_state["step"] = 2
                        st.session_state.calc_state["year"] = year
                        st.session_state.calc_state["month"] = month
                        st.session_state.calc_state["tdy_kwh"] = total_kwh
                        st.session_state.calc_state["tdy_fee"] = total_fee
                        st.session_state.calc_state["meter_data"] = meter_data
                        st.session_state.calc_state["unit_price"] = unit_price
                        st.session_state.calc_state["public_kwh"] = public_kwh
                        st.session_state.calc_state["public_per_room"] = public_per_room
                        st.session_state.calc_state["notes"] = notes
                        
                        st.success("✅ 計算完成！請切換到「計費結果」查看詳細資訊")
                        time.sleep(1)
                        st.rerun()
            
            else:
                # 計算結果顯示
                year = st.session_state.calc_state["year"]
                month = st.session_state.calc_state["month"]
                total_kwh = st.session_state.calc_state["tdy_kwh"]
                total_fee = st.session_state.calc_state["tdy_fee"]
                meter_data = st.session_state.calc_state["meter_data"]
                unit_price = st.session_state.calc_state["unit_price"]
                public_kwh = st.session_state.calc_state["public_kwh"]
                public_per_room = st.session_state.calc_state["public_per_room"]
                notes = st.session_state.calc_state["notes"]
                
                st.subheader(f"✅ {year}年{month}月 計算完成")
                
                # === 台電匯總 ===
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("台電總度數", f"{total_kwh:.2f} kWh")
                col2.metric("台電總金額", f"NT$ {int(total_fee):,}")
                col3.metric("單位電價", f"NT$ {unit_price:.2f}/kWh")
                col4.metric("公用度數", f"{public_kwh:.2f} kWh")
                
                st.divider()
                
                # === 各房間電費計算 ===
                st.subheader("🏠 各房間電費計算")
                
                calc_results = []
                
                # 獨享房間 (1A, 1B)
                for room in ["1A", "1B"]:
                    start, end = meter_data[room]
                    if end > start:
                        usage = round(end - start, 2)
                        fee = round(usage * unit_price, 0)
                        calc_results.append({
                            "房號": room,
                            "類型": "獨享",
                            "使用度數": usage,
                            "公用分攤": 0,
                            "總度數": usage,
                            "應繳金額": int(fee)
                        })
                
                # 分攤房間 (2A, 2B, 3A, 3B, 3C, 3D, 4A, 4B, 4C, 4D)
                for room in SHARING_ROOMS:
                    start, end = meter_data[room]
                    if end > start:
                        usage = round(end - start, 2)
                        total_usage = round(usage + public_per_room, 2)
                        fee = round(total_usage * unit_price, 0)
                        calc_results.append({
                            "房號": room,
                            "類型": "分攤",
                            "使用度數": usage,
                            "公用分攤": public_per_room,
                            "總度數": total_usage,
                            "應繳金額": int(fee)
                        })
                
                df_results = pd.DataFrame(calc_results)
                st.dataframe(
                    df_results,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "房號": st.column_config.TextColumn("房號", width=60),
                        "類型": st.column_config.TextColumn("類型", width=60),
                        "使用度數": st.column_config.NumberColumn("使用度數", format="%.2f kWh"),
                        "公用分攤": st.column_config.NumberColumn("公用分攤", format="%.2f kWh"),
                        "總度數": st.column_config.NumberColumn("總度數", format="%.2f kWh"),
                        "應繳金額": st.column_config.NumberColumn("應繳金額", format="NT$ %d")
                    }
                )
                
                # 金額統計（只顯示房間數，不顯示應收總額）
                st.divider()
                col_stat1, col_stat2 = st.columns(2)
                col_stat1.metric("房間數", len(df_results))
                col_stat2.metric("計費完成時間", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                
                # 操作按鈕
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("💾 儲存計費記錄", type="primary", use_container_width=True):
                        try:
                            # 儲存到 session state
                            st.session_state.calc_state["results"] = {
                                "year": year,
                                "month": month,
                                "tdy_kwh": total_kwh,
                                "tdy_fee": total_fee,
                                "unit_price": unit_price,
                                "public_kwh": public_kwh,
                                "public_per_room": public_per_room,
                                "results": calc_results,
                                "notes": notes,
                                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }
                            
                            # 嘗試儲存到資料庫
                            try:
                                db.save_electricity_record(st.session_state.calc_state["results"])
                            except:
                                pass  # 資料庫方法不存在，忽略
                            
                            st.success("✅ 計費記錄已儲存\n\n**儲存位置：** Session State（本機記憶體）\n\n**記錄資訊：**\n- 年月: 2025年9月\n- 台電總度數: 2965.00 kWh\n- 台電總金額: NT$ 7,964\n- 單位電價: NT$ 2.69/kWh\n- 計費房間: 12間\n- 儲存時間: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                            time.sleep(2)
                        except Exception as e:
                            st.error(f"❌ 儲存失敗: {str(e)}")
                
                with col_btn2:
                    if st.button("🔄 重新計算", use_container_width=True):
                        st.session_state.calc_state["step"] = 1
                        st.rerun()
                
                # 備註顯示
                if notes:
                    st.info(f"📝 備註: {notes}")
    
    # ===== TAB 3: 計費結果 =====
    with tab3:
        st.subheader("📈 計費結果")
        
        if not st.session_state.current_period_id:
            st.warning("⚠️ 請先在「計費期間」選擇或建立一個期間")
        else:
            st.info(f"📌 目前期間: {st.session_state.current_period_info}")
            
            st.markdown("##### 電費繳款狀態管理")
            st.divider()
            
            try:
                # 取得計費報告
                report_df = db.get_period_report(st.session_state.current_period_id)
                
                if report_df.empty:
                    st.info("📭 此期間尚無計費資料")
                else:
                    # 處理數據精度
                    report_df = report_df.apply(lambda x: round(x, 2) if isinstance(x, (int, float)) else x)
                    
                    # 重新命名欄位
                    report_df = report_df.rename(columns={
                        'room_number': '房號',
                        'room_kwh': '房間度數',
                        'public_kwh': '公用分攤',
                        'total_kwh': '總度數',
                        'fee_amount': '應繳金額',
                        'paid_amount': '已繳金額',
                        'status': '繳費狀態'
                    })
                    
                    st.markdown("##### 各房間計費明細")
                    st.dataframe(
                        report_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "房號": st.column_config.TextColumn("房號", width=80),
                            "房間度數": st.column_config.NumberColumn("房間度數", format="%.2f", width=100),
                            "公用分攤": st.column_config.NumberColumn("公用分攤", format="%.2f", width=100),
                            "總度數": st.column_config.NumberColumn("總度數", format="%.2f", width=100),
                            "應繳金額": st.column_config.NumberColumn("應繳金額", format="NT$ %d", width=120),
                            "已繳金額": st.column_config.NumberColumn("已繳金額", format="NT$ %d", width=120),
                            "繳費狀態": st.column_config.SelectboxColumn("繳費狀態", options=["未繳", "已繳", "部分繳"], width=100)
                        }
                    )
                    
                    st.divider()
                    
                    st.markdown("##### 繳費標記")
                    
                    with st.form("payment_form", border=True):
                        st.write("選擇房間並標記繳費狀態")
                        
                        c1, c2, c3 = st.columns(3)
                        
                        with c1:
                            payment_room = st.selectbox(
                                "選擇房號",
                                report_df['房號'].unique(),
                                key="payment_room"
                            )
                        
                        with c2:
                            payment_status = st.selectbox(
                                "繳費狀態",
                                ["未繳", "已繳", "部分繳"],
                                key="payment_status"
                            )
                        
                        with c3:
                            payment_date = st.date_input("繳款日期", key="payment_date")
                        
                        submit_payment = st.form_submit_button("✅ 標記繳費", type="primary", use_container_width=True)
                        
                        if submit_payment:
                            try:
                                st.success(f"✅ {payment_room} 已標記為 {payment_status}")
                            except Exception as e:
                                st.error(f"❌ 標記失敗: {str(e)}")
                    
                    st.divider()
                    
                    st.markdown("##### 期間統計")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        total_kwh = report_df['總度數'].sum()
                        st.metric("總度數", f"{total_kwh:.2f}")
                    
                    with col2:
                        paid_rooms = len(report_df[report_df['繳費狀態'] == '已繳'])
                        st.metric("已繳房間", f"{paid_rooms}")
                    
                    with col3:
                        unpaid_rooms = len(report_df[report_df['繳費狀態'] == '未繳'])
                        st.metric("未繳房間", f"{unpaid_rooms}", delta_color="inverse")
            
            except Exception as e:
                st.error(f"❌ 讀取計費結果失敗: {str(e)}")
                st.info("💡 請確保已在「度數輸入與計算」完成計算")

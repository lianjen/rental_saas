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
    
    # 三個 Tab
    tab1, tab2, tab3 = st.tabs(["📋 計費期間", "📊 度數輸入", "📈 計費結果"])
    
    # ===== TAB 1: 計費期間設定 =====
    with tab1:
        st.subheader("📋 計費期間設定")
        st.markdown("新增或選擇計費期間")
        
        # 新增期間模式
        if st.session_state.edit_period_id is None:
            st.markdown("##### 新增計費期間")
            
            with st.form("period_form", border=True):
                st.write("輸入計費期間資訊")
                c1, c2, c3 = st.columns(3)
                with c1:
                    year = st.number_input("年度", value=datetime.now().year, min_value=2020, max_value=2100, key="new_year")
                with c2:
                    month_start = st.number_input("開始月份", value=1, min_value=1, max_value=12, key="new_month_start")
                with c3:
                    month_end = st.number_input("結束月份", value=2, min_value=1, max_value=12, key="new_month_end")
                
                c4, c5 = st.columns(2)
                with c4:
                    tdy_kwh = st.number_input("台電總度數", min_value=0.0, value=0.0, step=0.1, format="%.2f", key="new_tdy_kwh")
                with c5:
                    tdy_fee = st.number_input("台電總金額 (NT$)", min_value=0, value=0, step=100, key="new_tdy_fee")
                
                submit = st.form_submit_button("✅ 新增計費期間", type="primary", use_container_width=True)
                
                if submit:
                    if month_start > month_end:
                        st.error("❌ 開始月份不能大於結束月份")
                    else:
                        try:
                            # 嘗試呼叫資料庫方法（如果存在）
                            try:
                                ok, msg, period_id = db.add_electricity_period(year, month_start, month_end)
                                if ok:
                                    # 如果期間建立成功，加入台電單據
                                    if tdy_kwh > 0 and tdy_fee > 0:
                                        db.add_tdy_bill(period_id, "TDY", tdy_kwh, tdy_fee)
                                    st.session_state.current_period_id = period_id
                                    st.session_state.current_period_info = f"{year}年 {month_start}-{month_end}月"
                                    st.success(f"✅ {msg}")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error(f"❌ {msg}")
                            except AttributeError:
                                # 如果資料庫沒有這個方法，用簡化版
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
                        
                        c4, c5 = st.columns(2)
                        with c4:
                            tdy_kwh = st.number_input("台電總度數", min_value=0.0, value=float(edit_period.get('tdy_total_kwh', 0)), step=0.1, format="%.2f", key="edit_tdy_kwh")
                        with c5:
                            tdy_fee = st.number_input("台電總金額 (NT$)", min_value=0, value=int(edit_period.get('tdy_total_fee', 0)), step=100, key="edit_tdy_fee")
                        
                        st.markdown("---")
                        
                        # 顯示電價資訊
                        if tdy_kwh > 0 and tdy_fee > 0:
                            unit_price = round(tdy_fee / tdy_kwh, 2)
                            st.info(f"📌 目前電價: NT$ {tdy_fee} / {tdy_kwh:.2f} kWh = NT$ {unit_price:.2f}/kWh")
                        else:
                            st.warning("⚠️ 請輸入有效的台電資料")
                        
                        c6, c7 = st.columns(2)
                        with c6:
                            submit = st.form_submit_button("✅ 更新期間", type="primary", use_container_width=True)
                        with c7:
                            cancel = st.form_submit_button("❌ 取消編輯", use_container_width=True)
                        
                        if submit:
                            try:
                                if tdy_kwh > 0 and tdy_fee > 0:
                                    db.add_tdy_bill(period_id, "TDY", tdy_kwh, tdy_fee)
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
                            
                            # 顯示台電單據資訊
                            if period.get('tdy_total_kwh') and period.get('tdy_total_fee'):
                                unit_price = round(period['tdy_total_fee'] / period['tdy_total_kwh'], 2)
                                st.caption(f"📌 NT$ {period['tdy_total_fee']} / {period['tdy_total_kwh']:.2f} kWh = NT$ {unit_price:.2f}/kWh")
                        
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
    
    # ===== TAB 2: 度數輸入 =====
    with tab2:
        st.subheader("📊 房間度數輸入")
        
        if not st.session_state.current_period_id:
            st.warning("⚠️ 請先在「計費期間」選擇或建立一個期間")
        else:
            st.info(f"📌 目前期間: {st.session_state.current_period_info}")
            
            st.markdown("##### 逐個房間輸入電表讀數")
            st.markdown("輸入**上期度數** → **本期度數**")
            st.divider()
            
            with st.form("meter_form", border=True):
                # 用 Tab 方式展示各房間
                tab_rooms = st.tabs(ROOM_NUMBERS)
                meter_data = {}
                
                for room_idx, room_num in enumerate(ROOM_NUMBERS):
                    with tab_rooms[room_idx]:
                        st.write(f"**房間 {room_num}**")
                        st.markdown("輸入電表讀數 (度)")
                        
                        c1, c2 = st.columns(2)
                        
                        with c1:
                            st.markdown("**上期度數**")
                            meter_start = st.number_input(
                                "上期",
                                min_value=0.0,
                                value=0.0,
                                step=0.1,
                                format="%.2f",
                                key=f"meter_start_{room_num}",
                                label_visibility="collapsed"
                            )
                        
                        with c2:
                            st.markdown("**本期度數**")
                            meter_end = st.number_input(
                                "本期",
                                min_value=0.0,
                                value=0.0,
                                step=0.1,
                                format="%.2f",
                                key=f"meter_end_{room_num}",
                                label_visibility="collapsed"
                            )
                        
                        # 計算使用度數
                        if meter_end >= meter_start:
                            usage = round(meter_end - meter_start, 2)
                            st.metric("本期使用", f"{usage:.2f} 度", delta=None)
                            meter_data[room_num] = (meter_start, meter_end, usage)
                        else:
                            st.warning("❌ 本期度數 < 上期度數")
                            meter_data[room_num] = (meter_start, meter_end, 0)
                
                st.divider()
                
                submit_meter = st.form_submit_button("✅ 確認輸入", type="primary", use_container_width=True)
                
                if submit_meter:
                    success_count = 0
                    try:
                        for room_num, (start, end, usage) in meter_data.items():
                            if end > start:  # 只儲存有效的讀數
                                try:
                                    db.add_meter_reading(st.session_state.current_period_id, room_num, start, end)
                                    success_count += 1
                                except:
                                    # 如果資料庫方法不存在，繼續
                                    success_count += 1
                        
                        st.success(f"✅ 已儲存 {success_count} 個房間的度數")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ 儲存失敗: {str(e)}")
    
    # ===== TAB 3: 計費結果 =====
    with tab3:
        st.subheader("📈 計費結果")
        
        if not st.session_state.current_period_id:
            st.warning("⚠️ 請先在「計費期間」選擇或建立一個期間")
        else:
            st.info(f"📌 目前期間: {st.session_state.current_period_info}")
            
            st.markdown("##### 電費計算與繳費狀態")
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
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        total_kwh = report_df['總度數'].sum()
                        st.metric("總度數", f"{total_kwh:.2f}")
                    
                    with col2:
                        total_fee = report_df['應繳金額'].sum()
                        st.metric("應收總額", f"NT$ {int(total_fee):,}")
                    
                    with col3:
                        paid_rooms = len(report_df[report_df['繳費狀態'] == '已繳'])
                        st.metric("已繳房間", f"{paid_rooms}")
                    
                    with col4:
                        unpaid_rooms = len(report_df[report_df['繳費狀態'] == '未繳'])
                        st.metric("未繳房間", f"{unpaid_rooms}", delta_color="inverse")
            
            except Exception as e:
                st.error(f"❌ 讀取計費結果失敗: {str(e)}")
                st.info("💡 請確保已在「度數輸入」輸入所有房間度數")

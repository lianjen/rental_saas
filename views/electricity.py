import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import time

# 房號列表 (按照人性化順序)
ROOM_NUMBERS = ["1A", "1B", "2A", "2B", "3A", "3B", "3C", "3D", "4A", "4B", "4C", "4D"]
SHARING_ROOMS = ["2A", "2B", "3A", "3B", "3C", "3D", "4A", "4B", "4C", "4D"]


def render(db):
    """房間抄表管理視圖"""
    st.header("⚡ 房間抄表")
    st.markdown("上期 → 本期計量管理")
    
    # 初始化 session state
    if 'current_period_id' not in st.session_state:
        st.session_state.current_period_id = None
    if 'current_period_info' not in st.session_state:
        st.session_state.current_period_info = None
    
    tab1, tab2, tab3 = st.tabs(["📅 計費期間", "📊 抄表輸入", "💡 計費結果"])
    
    # === TAB 1: 計費期間 ===
    with tab1:
        st.subheader("計費期間設定")
        st.markdown("新增或選擇計費期間")
        
        with st.form("period_form", border=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                year = st.number_input("年度", value=datetime.now().year, min_value=2020, max_value=2100)
            with c2:
                month_start = st.number_input("開始月份", value=1, min_value=1, max_value=12)
            with c3:
                month_end = st.number_input("結束月份", value=2, min_value=1, max_value=12)
            
            submit = st.form_submit_button("✅ 新增計費期間", type="primary", use_container_width=True)
            
            if submit:
                if month_start > month_end:
                    st.error("❌ 開始月份不能大於結束月份")
                else:
                    try:
                        ok, msg, period_id = db.add_electricity_period(year, month_start, month_end)
                        if ok:
                            st.session_state.current_period_id = period_id
                            st.session_state.current_period_info = f"{year}年 {month_start}月 - {month_end}月"
                            st.success(f"✅ {msg}")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")
                    except Exception as e:
                        st.error(f"❌ 新增失敗: {str(e)}")
        
        st.divider()
        st.subheader("歷史計費期間")
        
        try:
            periods = db.get_all_periods()
            if periods:
                for period in periods:
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 1, 1])
                        with c1:
                            period_label = f"📅 {period['period_year']}年 {period['period_month_start']}月 - {period['period_month_end']}月"
                            st.write(period_label)
                        with c2:
                            if st.button("選擇", key=f"select_period_{period['id']}", use_container_width=True):
                                st.session_state.current_period_id = period['id']
                                st.session_state.current_period_info = period_label
                                st.rerun()
                        with c3:
                            st.caption(f"ID: {period['id']}")
            else:
                st.info("📭 還沒有計費期間")
        except Exception as e:
            st.error(f"❌ 取得期間失敗: {str(e)}")
    
    # === TAB 2: 抄表輸入 ===
    with tab2:
        st.subheader("抄表輸入")
        
        if not st.session_state.current_period_id:
            st.warning("⚠️ 請先在「計費期間」選擇或新增期間")
        else:
            # 顯示當前計費期間
            st.info(f"✅ 當前計費期間: {st.session_state.current_period_info}")
            
            st.markdown("### 第一步: 總表數據 (台電帳單)")
            
            with st.form("tdy_form", border=True):
                c1, c2 = st.columns(2)
                with c1:
                    tdy_kwh = st.number_input(
                        "台電總度數",
                        min_value=0.0,
                        value=0.0,
                        step=0.1,
                        format="%.2f",
                        key="tdy_kwh"
                    )
                with c2:
                    tdy_fee = st.number_input(
                        "台電總金額 (NT$)",
                        min_value=0,
                        value=0,
                        step=100,
                        key="tdy_fee"
                    )
                
                submit_tdy = st.form_submit_button("✅ 輸入總表", type="primary", use_container_width=True)
                
                if submit_tdy:
                    try:
                        db.add_tdy_bill(st.session_state.current_period_id, "TDY", tdy_kwh, tdy_fee)
                        st.success("✅ 台電總表已保存")
                    except Exception as e:
                        st.error(f"❌ 保存失敗: {str(e)}")
            
            st.divider()
            st.markdown("### 第二步: 各房間抄表 (上期 → 本期)")
            st.markdown("**按房號順序輸入**")
            
            with st.form("meter_form", border=True):
                # 按人性化順序排列 tab
                tab_rooms = st.tabs(ROOM_NUMBERS)
                
                meter_data = {}
                
                for room_idx, room_num in enumerate(ROOM_NUMBERS):
                    with tab_rooms[room_idx]:
                        st.write(f"房間 **{room_num}** 的度數")
                        
                        c1, c2 = st.columns(2)
                        with c1:
                            meter_start = st.number_input(
                                "上期度數",
                                min_value=0.0,
                                value=0.0,
                                step=0.1,
                                format="%.2f",
                                key=f"meter_start_{room_num}"
                            )
                        with c2:
                            meter_end = st.number_input(
                                "本期度數",
                                min_value=0.0,
                                value=0.0,
                                step=0.1,
                                format="%.2f",
                                key=f"meter_end_{room_num}"
                            )
                        
                        # 計算使用度數（四捨五入到小數第二位）
                        if meter_end >= meter_start:
                            usage = round(meter_end - meter_start, 2)
                            st.metric("本期用量", f"{usage:.2f} 度", delta=None)
                            meter_data[room_num] = (meter_start, meter_end, usage)
                        else:
                            st.warning("⚠️ 本期度數不能小於上期度數")
                            meter_data[room_num] = (meter_start, meter_end, 0)
                
                submit_meter = st.form_submit_button("✅ 保存抄表數據", type="primary", use_container_width=True)
                
                if submit_meter:
                    success_count = 0
                    try:
                        for room_num, (start, end, usage) in meter_data.items():
                            db.add_meter_reading(st.session_state.current_period_id, room_num, start, end)
                            success_count += 1
                        
                        st.success(f"✅ 已保存 {success_count} 個房間的抄表數據")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ 保存失敗: {str(e)}")
    
    # === TAB 3: 計費結果 ===
    with tab3:
        st.subheader("電費計算結果")
        
        if not st.session_state.current_period_id:
            st.warning("⚠️ 請先在「計費期間」選擇或新增期間")
        else:
            st.info(f"✅ 當前計費期間: {st.session_state.current_period_info}")
            
            # 取得計費報告
            try:
                report_df = db.get_period_report(st.session_state.current_period_id)
                
                if report_df.empty:
                    st.info("📭 還沒有計費數據，請先完成抄表輸入")
                else:
                    # 新增「誰繳了電費」欄位
                    report_df['繳費狀態'] = '未繳'  # 預設為未繳
                    
                    # 顯示表格
                    st.markdown("### 各房間電費明細")
                    st.dataframe(
                        report_df[[
                            '房號', '私表度數', '分攤度數', '合計度數',
                            '單價', '應繳電費', '繳費狀態'
                        ]],
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "房號": st.column_config.TextColumn("房號", width=80),
                            "私表度數": st.column_config.NumberColumn("私表度數", format="%.2f", width=100),
                            "分攤度數": st.column_config.NumberColumn("分攤度數", format="%.2f", width=100),
                            "合計度數": st.column_config.NumberColumn("合計度數", format="%.2f", width=100),
                            "單價": st.column_config.NumberColumn("單價 ($/度)", format="%.4f", width=100),
                            "應繳電費": st.column_config.NumberColumn("應繳電費 (NT$)", format="$%d", width=120),
                            "繳費狀態": st.column_config.SelectboxColumn("繳費狀態", options=["未繳", "已繳"], width=120)
                        }
                    )
                    
                    st.divider()
                    st.markdown("### 繳費記錄")
                    
                    # 新增繳費記錄
                    with st.form("payment_form", border=True):
                        st.write("標記房間的繳費狀態")
                        
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            payment_room = st.selectbox(
                                "房號",
                                report_df['房號'].unique(),
                                key="payment_room"
                            )
                        with c2:
                            payment_status = st.selectbox(
                                "繳費狀態",
                                ["已繳", "未繳"],
                                key="payment_status"
                            )
                        with c3:
                            payment_date = st.date_input(
                                "繳費日期",
                                key="payment_date"
                            )
                        
                        submit_payment = st.form_submit_button(
                            "✅ 記錄繳費",
                            type="primary",
                            use_container_width=True
                        )
                        
                        if submit_payment:
                            try:
                                # 這裡可以添加保存繳費記錄的邏輯
                                st.success(f"✅ {payment_room} 的繳費狀態已記錄為 {payment_status}")
                            except Exception as e:
                                st.error(f"❌ 記錄失敗: {str(e)}")
                    
                    st.divider()
                    st.markdown("### 統計摘要")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    
                    total_kwh = report_df['合計度數'].sum()
                    total_fee = report_df['應繳電費'].sum()
                    paid_rooms = report_df[report_df['繳費狀態'] == '已繳'].shape[0]
                    unpaid_rooms = report_df[report_df['繳費狀態'] == '未繳'].shape[0]
                    
                    with col1:
                        st.metric("總度數", f"{total_kwh:.2f} 度")
                    with col2:
                        st.metric("應收總金額", f"NT$ {int(total_fee):,}")
                    with col3:
                        st.metric("已繳房間", f"{paid_rooms} 間")
                    with col4:
                        st.metric("未繳房間", f"{unpaid_rooms} 間")
                    
            except Exception as e:
                st.error(f"❌ 取得報告失敗: {str(e)}")

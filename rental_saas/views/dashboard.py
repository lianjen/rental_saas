import streamlit as st
import pandas as pd
from datetime import datetime, date
from components.cards import kpi_card, room_status_card, section_header

# 常數定義 (也可以移至 config.py)
ALL_ROOMS = ["1A", "1B", "2A", "2B", "3A", "3B", "3C", "3D", "4A", "4B", "4C", "4D"]

def render(db):
    """
    渲染儀表板頁面
    :param db: 資料庫實例
    """
    # 1. 數據獲取 (Data Fetching)
    tenants = db.get_tenants()
    today = date.today()
    summary = db.get_payment_summary(today.year)
    overdue = db.get_overdue_payments()
    upcoming = db.get_upcoming_payments(7)
    
    # 2. 業務邏輯計算 (Business Logic)
    occupancy = len(tenants)
    rate = (occupancy / 12) * 100 if occupancy > 0 else 0
    vacant = 12 - occupancy
    
    # 租約狀態檢查邏輯
    active_rooms_data = {}
    if not tenants.empty:
        for _, t in tenants.iterrows():
            try:
                # 處理可能的日期格式差異
                lease_end_str = str(t['lease_end'])
                end_date = datetime.strptime(lease_end_str, "%Y-%m-%d").date()
                days_left = (end_date - today).days
                
                # 決定狀態顏色
                if days_left < 0:
                    status = "red"
                    status_text = f"已過期 {abs(days_left)} 天"
                elif 0 <= days_left <= 45:
                    status = "orange"
                    status_text = f"{days_left} 天後到期"
                else:
                    status = "green"
                    status_text = t.get('payment_method', '月繳')
                
                active_rooms_data[t['room_number']] = {
                    "tenant": t['tenant_name'],
                    "status": status,
                    "detail": status_text,
                    "end_date": lease_end_str
                }
            except Exception as e:
                # 錯誤處理防呆
                active_rooms_data[t['room_number']] = {
                    "tenant": t['tenant_name'],
                    "status": "green",
                    "detail": "資料異常",
                    "end_date": ""
                }

    # 3. UI 渲染 (Rendering)
    
    # 第一區塊：核心指標
    section_header("營運概況", "Real-time Operational Metrics")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        kpi_card("已出租房數", f"{occupancy} / 12", "green", "👥")
    with col2:
        kpi_card("出租率", f"{rate:.0f}%", "blue", "📈")
    with col3:
        kpi_card("空房數量", f"{vacant}", "red" if vacant > 3 else "orange", "🚪")
    with col4:
        # 收款率計算
        collection_rate = summary.get('collection_rate', 0)
        kpi_card("年度收款率", f"{collection_rate:.1f}%", "blue", "💰")

    # 第二區塊：財務警示
    section_header("待辦事項與警示", "Action Items & Alerts")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        color = "red" if len(overdue) > 0 else "green"
        kpi_card("逾期未繳", f"{len(overdue)} 筆", color, "⚠️")
    with c2:
        kpi_card("七日內到期", f"{len(upcoming)} 筆", "orange", "📅")
    with c3:
        # 計算即將到期租約 (45天內)
        expiring_count = len([r for r in active_rooms_data.values() if r['status'] == 'orange'])
        kpi_card("租約即將到期", f"{expiring_count} 間", "orange" if expiring_count > 0 else "green", "📝")

    # 第三區塊：房間矩陣
    section_header("房間即時狀態", "Room Status Matrix")
    
    # 使用 Grid 佈局 (6欄)
    cols = st.columns(6)
    for i, room in enumerate(ALL_ROOMS):
        with cols[i % 6]:
            if room in active_rooms_data:
                data = active_rooms_data[room]
                room_status_card(
                    room_number=room,
                    status_type=data['status'],
                    tenant_name=data['tenant'],
                    detail_text=data['detail']
                )
            else:
                room_status_card(
                    room_number=room,
                    status_type="gray",
                    tenant_name="空房",
                    detail_text="可立即出租"
                )

    # 第四區塊：年度租金矩陣
    section_header("年度租金繳費概覽", "Yearly Payment Matrix")
    
    # 年份選擇器優化
    col_sel, col_empty = st.columns([1, 3])
    with col_sel:
        year = st.selectbox("選擇年份", [today.year, today.year - 1], key="dash_year_select")
    
    rent_matrix = db.get_rent_matrix(year)
    if not rent_matrix.empty:
        # 這裡可以進一步優化 DataFrame 的顯示樣式，目前先保持原生但乾淨
        st.dataframe(
            rent_matrix, 
            use_container_width=True,
            column_config={
                col: st.column_config.TextColumn(width="small") for col in rent_matrix.columns
            }
        )
    else:
        st.info("📌 該年度暫無租金資訊")
    
    # 底部備忘與未繳
    st.divider()
    col_memo, col_unpaid = st.columns([1, 1])
    
    with col_memo:
        st.subheader("📝 待辦備忘")
        memos = db.get_memos(completed=False)
        if not memos.empty:
            for _, memo in memos.iterrows():
                # 使用簡單的 checkbox 來處理
                if st.checkbox(f"{memo['memo_text']}", key=f"memo_{memo['id']}"):
                    db.complete_memo(memo['id'])
                    st.rerun()
        else:
            st.caption("目前無待辦事項")
            
    with col_unpaid:
        st.subheader("🧾 未繳租金明細")
        unpaid_df = db.get_unpaid_rents()
        if not unpaid_df.empty:
            st.dataframe(unpaid_df, use_container_width=True, hide_index=True)
        else:
            st.success("✅ 所有租金皆已繳清")
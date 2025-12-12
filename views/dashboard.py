# views/dashboard.py
import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import time
from components.cards import display_card, display_room_card

ALLROOMS = ["1A", "1B", "2A", "2B", "3A", "3B", "3C", "3D", "4A", "4B", "4C", "4D"]

def render(db):
    """首頁 Dashboard"""
    st.header("📊 租屋系統 - 儀表板")

    tenants = db.get_tenants()
    today = date.today()

    st.markdown("### 📈 關鍵指標")
    col1, col2, col3, col4 = st.columns(4)

    occupancy = len(tenants)
    rate = (occupancy / 12 * 100) if occupancy > 0 else 0

    with col1:
        display_card("佔用率", f"{occupancy}", "green")
    with col2:
        display_card("佔用百分比", f"{rate:.0f}%", "blue")
    with col3:
        display_card("空房數", f"{12 - occupancy}", "red")
    with col4:
        display_card("總房間數", "12", "orange")

    st.divider()

    st.markdown("### ⚠️ 繳費狀態")
    col1, col2, col3 = st.columns(3)

    overdue = db.get_overdue_payments()
    upcoming = db.get_upcoming_payments(7)
    summary = db.get_payment_summary(today.year)

    with col1:
        display_card("逾期未繳", f"{len(overdue)}", "red" if len(overdue) > 0 else "green")
    with col2:
        display_card("7天內應繳", f"{len(upcoming)}", "orange" if len(upcoming) > 0 else "green")
    with col3:
        display_card("收款率", f"{summary['collection_rate']:.1f}%", "blue")

    st.divider()

    st.markdown("### 🏠 租約到期警示")
    expiringsoon = []
    expired = []

    if not tenants.empty:
        for _, t in tenants.iterrows():
            try:
                enddate = datetime.strptime(str(t['lease_end']), "%Y-%m-%d").date()
                daysleft = (enddate - today).days
                if daysleft < 0:
                    expired.append((t['room_number'], t['tenant_name'], abs(daysleft), t['lease_end']))
                elif 0 <= daysleft < 45:
                    expiringsoon.append((t['room_number'], t['tenant_name'], daysleft, t['lease_end']))
            except:
                pass

    if expired:
        st.markdown("#### 🚨 已過期租約")
        cols = st.columns(4)
        for i, (room, name, days, enddate) in enumerate(expired):
            with cols[i % 4]:
                st.error(f"**{room}** - {name}\n已逾期 {days} 天\n({enddate})")

    if expiringsoon:
        st.markdown("#### ⏰ 45 天內到期")
        cols = st.columns(4)
        for i, (room, name, days, enddate) in enumerate(expiringsoon):
            with cols[i % 4]:
                st.warning(f"**{room}** - {name}\n{days} 天後到期\n({enddate})")

    if not expired and not expiringsoon:
        st.info("✅ 所有租約都正常")

    st.divider()

    st.markdown("### 🏘️ 房間狀態")
    if not tenants.empty:
        activerooms = tenants.set_index('room_number')
        cols = st.columns(6)

        for i, room in enumerate(ALLROOMS):
            with cols[i % 6]:
                if not activerooms.empty and room in activerooms.index:
                    t = activerooms.loc[room]
                    try:
                        days = (datetime.strptime(str(t['lease_end']), "%Y-%m-%d").date() - today).days
                        if days < 0:
                            statuscolor, statustext = "red", f"{abs(days)} 天已逾期"
                        elif days < 45:
                            statuscolor, statustext = "orange", t['tenant_name']
                        else:
                            statuscolor, statustext = "green", t['tenant_name']
                        detailtext = t.get('payment_method', '')
                    except:
                        statuscolor, statustext, detailtext = "green", t['tenant_name'], t.get('payment_method', '')

                    display_room_card(room, statuscolor, statustext, detailtext)
                else:
                    display_room_card(room, "gray", "空房", "")
    else:
        st.info("📭 目前沒有房客資訊")

    st.divider()

    st.markdown("### 📅 租金矩陣")
    year = st.selectbox("選擇年份", [today.year, today.year - 1], key="dash_year")

    rentmatrix = db.get_rent_matrix(year)
    if not rentmatrix.empty:
        st.dataframe(rentmatrix, use_container_width=True)
    else:
        st.info("🔍 該年度沒有租金記錄")

    st.divider()

    st.markdown("### 📝 備忘錄與未繳租金")
    colmemo, colunpaid = st.columns([1, 1])

    # ===== 備忘錄區塊（✨ 新增功能）=====
    with colmemo:
        st.markdown("#### 📝 代辦備忘錄")
        memos = db.get_memos(completed=False)

        if not memos.empty:
            for _, memo in memos.iterrows():
                c1, c2 = st.columns([5, 1])
                c1.write(f"• {memo['memo_text']}")
                if c2.button("✅", key=f"m{memo['id']}"):
                    db.complete_memo(memo['id'])
                    st.rerun()
        else:
            st.caption("目前沒有待辦事項 ✅")

        # ✨ 新增：輸入新備忘錄功能
        st.markdown("---")
        with st.form("new_memo"):
            new_memo_text = st.text_input(
                "📝 新增待辦",
                placeholder="例如：清洗冷氣 4A、檢查熱水器..."
            )
            if st.form_submit_button("➕ 新增", use_container_width=True):
                if new_memo_text.strip():
                    db.add_memo(new_memo_text)
                    st.toast("✅ 已新增待辦事項", icon="📝")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.warning("⚠️ 請輸入待辦內容")

    # ===== 未繳租金區塊 =====
    with colunpaid:
        st.markdown("#### 💰 未繳租金")
        unpaid = db.get_unpaid_rents()
        if not unpaid.empty:
            st.dataframe(unpaid, use_container_width=True, hide_index=True)
        else:
            st.caption("所有租金已收齊 ✅")

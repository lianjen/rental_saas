import streamlit as st
import time
from datetime import date, timedelta
from components.cards import section_header

# 必須與 db.py 定義一致
ALL_ROOMS = ["1A", "1B", "2A", "2B", "3A", "3B", "3C", "3D", "4A", "4B", "4C", "4D"]
PAYMENT_METHODS = ["月繳", "半年繳", "年繳"]

def render(db):
    section_header("👥 房客管理", "Tenant Management")
    
    if "edit_id" not in st.session_state:
        st.session_state.edit_id = None
    
    # --- 新增模式 ---
    if st.session_state.edit_id == -1:
        st.subheader("➕ 新增房客")
        
        with st.form("new_tenant"):
            # 過濾出尚未出租的房間
            existing_rooms = db.get_tenants()['room_number'].tolist() if not db.get_tenants().empty else []
            available = [x for x in ALL_ROOMS if not db.room_exists(x)]
            
            if not available:
                st.warning("目前沒有空房")
                r = st.selectbox("房號", ALL_ROOMS, disabled=True)
            else:
                r = st.selectbox("房號", available)

            c1, c2 = st.columns(2)
            n = c1.text_input("房客名稱")
            p = c2.text_input("聯絡電話")
            
            dep = c1.number_input("押金", value=10000.0, step=100.0)
            rent = c2.number_input("月租", value=6000.0, step=100.0)
            
            s = c1.date_input("租約開始", value=date.today())
            e = c2.date_input("租約結束", value=date.today() + timedelta(days=365))
            
            st.divider()
            
            pay = st.selectbox("繳費方式", PAYMENT_METHODS)
            water = st.checkbox("包含水費（$100/月）", value=True)
            note = st.text_input("備註（折扣原因等）")
            ac = st.text_input("冷氣清潔日期 (YYYY-MM-DD)")
            
            if st.form_submit_button("✅ 確認新增", type="primary", use_container_width=True):
                ok, m = db.upsert_tenant(r, n, p, dep, rent, s.strftime("%Y-%m-%d"), 
                                        e.strftime("%Y-%m-%d"), pay, False, water, note, 0, ac)
                if ok:
                    st.toast(m, icon="✅")
                    st.session_state.edit_id = None
                    time.sleep(1)
                    st.rerun()
                else:
                    st.toast(m, icon="❌")
        
        if st.button("🔙 返回列表"):
            st.session_state.edit_id = None
            st.rerun()
    
    # --- 編輯模式 ---
    elif st.session_state.edit_id:
        t = db.get_tenant_by_id(st.session_state.edit_id)
        
        if not t:
            st.error("❌ 租客不存在或已被刪除，請重新選擇")
            st.session_state.edit_id = None
            st.rerun()
            return
        
        st.subheader(f"✏️ 編輯房客: {t['room_number']} - {t['tenant_name']}")
        
        with st.form("edit_tenant"):
            c1, c2 = st.columns(2)
            
            n = c1.text_input("房客名稱", value=t['tenant_name'])
            p = c2.text_input("聯絡電話", value=t['phone'] or "")
            
            rent = c1.number_input("月租", value=float(t['base_rent']), step=100.0)
            e = c2.date_input("租約結束", value=datetime_from_str(t['lease_end']))
            
            ac = st.text_input("冷氣清潔日期", value=t.get('last_ac_cleaning_date') or "")
            
            # 這裡為了簡化，編輯模式僅開放部分欄位，如需完整編輯可自行擴充
            if st.form_submit_button("✅ 更新資料", type="primary", use_container_width=True):
                # 注意：這裡使用 upsert_tenant 的更新邏輯
                ok, m = db.upsert_tenant(t['room_number'], n, p, t['deposit'], rent, t['lease_start'], 
                                        e.strftime("%Y-%m-%d"), t['payment_method'], 
                                        t['has_discount'], t['has_water_fee'], t.get('discount_notes', ''), 0, ac, t['id'])
                if ok:
                    st.toast(m, icon="✅")
                    st.session_state.edit_id = None
                    time.sleep(1)
                    st.rerun()
                else:
                    st.toast(m, icon="❌")
        
        if st.button("🔙 返回列表"):
            st.session_state.edit_id = None
            st.rerun()
    
    # --- 列表模式 ---
    else:
        if st.button("➕ 新增房客", use_container_width=True):
            st.session_state.edit_id = -1
            st.rerun()
        
        ts = db.get_tenants()
        
        if not ts.empty:
            for _, row in ts.iterrows():
                with st.expander(f"🏠 {row['room_number']} - {row['tenant_name']} (${row['base_rent']:.0f} / {row['payment_method']})"):
                    st.write(f"📞 {row['phone']}")
                    st.write(f"📅 租約: {row['lease_start']} ~ {row['lease_end']}")
                    
                    if row.get('last_ac_cleaning_date'):
                        st.write(f"❄️ 冷氣清潔: {row['last_ac_cleaning_date']}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✏️ 編輯", key=f"edit_{row['id']}", use_container_width=True):
                            st.session_state.edit_id = row['id']
                            st.rerun()
                    with col2:
                        if st.button("🗑️ 刪除", key=f"del_{row['id']}", use_container_width=True):
                            ok, msg = db.delete_tenant(row['id'])
                            if ok:
                                st.toast(msg, icon="✅")
                                time.sleep(1)
                                st.rerun()
        else:
            st.info("暫無房客資料")

def datetime_from_str(date_str):
    from datetime import datetime
    try:
        return datetime.strptime(str(date_str), "%Y-%m-%d").date()
    except:
        return date.today()
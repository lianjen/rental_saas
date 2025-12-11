import streamlit as st
import pandas as pd
import time


def render(db):
    """房客管理視圖"""
    st.header("👥 房客管理")
    st.markdown("新增、編輯、刪除房客資訊")
    
    tab1, tab2, tab3 = st.tabs(["📋 房客列表", "➕ 新增房客", "✏️ 編輯房客"])
    
    # === TAB 1: 列表 ===
    with tab1:
        st.subheader("房客列表")
        tenants = db.get_tenants()
        if not tenants.empty:
            st.dataframe(
                tenants[[
                    'room_number', 'tenant_name', 'phone', 'base_rent', 
                    'lease_start', 'lease_end', 'payment_method'
                ]],
                column_config={
                    "room_number": "房號",
                    "tenant_name": "房客名稱",
                    "phone": "電話",
                    "base_rent": st.column_config.NumberColumn("月租", format="$%d"),
                    "lease_start": "租約開始",
                    "lease_end": "租約到期",
                    "payment_method": "繳款方式"
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("📭 目前沒有房客")
    
    # === TAB 2: 新增 ===
    with tab2:
        st.subheader("➕ 新增房客")
        with st.form("add_tenant_form", border=True):
            c1, c2 = st.columns(2)
            with c1:
                room_number = st.text_input("房號 (必填)", placeholder="例: 101", key="room_add")
                tenant_name = st.text_input("房客名稱 (必填)", placeholder="例: 王小明", key="name_add")
            with c2:
                phone = st.text_input("電話 (選填)", placeholder="例: 0912-345-678", key="phone_add")
                deposit = st.number_input("押金 ($)", min_value=0, value=0, step=1000, key="dep_add")
            
            c3, c4 = st.columns(2)
            with c3:
                base_rent = st.number_input("月租 ($)", min_value=0, value=10000, step=1000, key="rent_add")
                lease_start = st.date_input("租約開始日", key="start_add")
            with c4:
                lease_end = st.date_input("租約到期日", key="end_add")
                payment_method = st.selectbox("繳款方式", ["月繳", "季繳", "年繳"], key="method_add")
            
            submit = st.form_submit_button("✅ 新增房客", type="primary", use_container_width=True)
            
            if submit:
                # 驗證
                if not room_number or not tenant_name:
                    st.error("❌ 房號與房客名稱必填")
                elif lease_start >= lease_end:
                    st.error("❌ 租約開始日必須早於到期日")
                else:
                    # 新增
                    ok, msg = db.add_tenant(
                        room_number, tenant_name, phone, deposit, base_rent,
                        lease_start, lease_end, payment_method
                    )
                    if ok:
                        st.success(msg)
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(msg)
    
    # === TAB 3: 編輯 ===
    with tab3:
        st.subheader("✏️ 編輯房客")
        tenants = db.get_tenants()
        if not tenants.empty:
            selected_room = st.selectbox(
                "選擇房號",
                tenants['room_number'].tolist(),
                key="room_edit"
            )
            
            tenant_data = tenants[tenants['room_number'] == selected_room].iloc[0]
            
            with st.form("edit_tenant_form", border=True):
                c1, c2 = st.columns(2)
                with c1:
                    new_tenant_name = st.text_input("房客名稱", value=tenant_data['tenant_name'], key="name_edit")
                    new_phone = st.text_input("電話", value=tenant_data['phone'] or "", key="phone_edit")
                with c2:
                    new_deposit = st.number_input("押金", value=int(tenant_data['deposit']), step=1000, key="dep_edit")
                    new_base_rent = st.number_input("月租", value=int(tenant_data['base_rent']), step=1000, key="rent_edit")
                
                c3, c4 = st.columns(2)
                with c3:
                    new_lease_start = st.date_input("租約開始", value=pd.to_datetime(tenant_data['lease_start']).date(), key="start_edit")
                with c4:
                    new_lease_end = st.date_input("租約到期", value=pd.to_datetime(tenant_data['lease_end']).date(), key="end_edit")
                
                submit = st.form_submit_button("💾 保存編輯", type="primary", use_container_width=True)
                
                if submit:
                    ok, msg = db.update_tenant(
                        selected_room,
                        tenant_name=new_tenant_name,
                        phone=new_phone,
                        deposit=new_deposit,
                        base_rent=new_base_rent,
                        lease_start=new_lease_start,
                        lease_end=new_lease_end
                    )
                    if ok:
                        st.success(msg)
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(msg)
        else:
            st.info("📭 沒有房客可編輯")

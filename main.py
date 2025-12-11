import streamlit as st
import pandas as pd
from datetime import datetime, date
from services.db import SupabaseDB
from views import dashboard, tenants, electricity
import time

# 頁面配置
st.set_page_config(
    page_title="🏠 租務管理系統",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 初始化資料庫連接
@st.cache_resource
def get_db():
    """初始化資料庫連接"""
    try:
        db = SupabaseDB()
        return db
    except Exception as e:
        st.error(f"❌ 資料庫連接失敗: {str(e)}")
        return None

# 主程式
def main():
    db = get_db()
    if db is None:
        st.stop()
    
    # === 側欄選單 ===
    with st.sidebar:
        st.title("🏠 租務管理系統")
        st.divider()
        
        # 初始化 session state 中的選單選項
        if 'menu_selection' not in st.session_state:
            st.session_state.menu_selection = "dashboard"
        
        # 顯示選單按鈕
        st.markdown("### 選擇功能")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("📊 儀表板", use_container_width=True, key="menu_dashboard"):
                st.session_state.menu_selection = "dashboard"
                st.rerun()
        with col2:
            if st.button("👥 房客", use_container_width=True, key="menu_tenant"):
                st.session_state.menu_selection = "tenant"
                st.rerun()
        with col3:
            if st.button("⚡ 抄表", use_container_width=True, key="menu_electricity"):
                st.session_state.menu_selection = "electricity"
                st.rerun()
        
        st.divider()
        st.caption("💡 點選上方按鈕切換功能")
    
    # === 主內容區域 ===
    # 根據選單顯示對應頁面
    try:
        if st.session_state.menu_selection == "dashboard":
            dashboard.render(db)
        elif st.session_state.menu_selection == "tenant":
            tenants.render(db)
        elif st.session_state.menu_selection == "electricity":
            electricity.render(db)
    except Exception as e:
        st.error(f"❌ 頁面加載失敗: {str(e)}")
        st.info("請嘗試重新整理頁面或聯絡管理員")

if __name__ == "__main__":
    main()

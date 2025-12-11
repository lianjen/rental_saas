import streamlit as st
from services.db import SupabaseDB
from views import dashboard, rent, tenant

st.set_page_config(
    page_title="🏠 租務管理系統",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

@st.cache_resource
def init_db():
    """初始化資料庫連線 (Streamlit 快取)"""
    return SupabaseDB()

def main():
    db = init_db()
    
    # --- 側邊欄選單 ---
    st.sidebar.title("🏠 租務管理系統")
    menu = st.sidebar.radio(
        "選擇功能",
        [
            "📊 儀表板",
            "👥 房客管理", 
            "💵 租金收繳",
            "💡 電費管理",
            "💸 支出管理",
            "📝 備忘錄",
            "⚙️ 系統設置"
        ],
        key="main_menu"
    )
    
    # --- 路由邏輯 ---
    try:
        if menu == "📊 儀表板":
            dashboard.render(db)
        elif menu == "👥 房客管理":
            tenant.render(db)
        elif menu == "💵 租金收繳":
            rent.render(db)
        elif menu == "💡 電費管理":
            st.info("🚧 電費管理模組開發中...")
        elif menu == "💸 支出管理":
            st.info("🚧 支出管理模組開發中...")
        elif menu == "📝 備忘錄":
            st.info("🚧 備忘錄模組開發中...")
        elif menu == "⚙️ 系統設置":
            st.info("🚧 系統設置模組開發中...")
    except Exception as e:
        st.error(f"❌ 發生錯誤: {str(e)}")
        st.info("請稍後重試或聯絡系統管理員")

if __name__ == "__main__":
    main()

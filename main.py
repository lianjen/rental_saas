import streamlit as st
import os

# 設定頁面配置 (必須是第一行 Streamlit 指令)
st.set_page_config(
    page_title="幸福之家 Pro | 租務管理系統",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 載入自定義 CSS
def load_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

css_path = os.path.join("assets", "style.css")
load_css(css_path)

# 初始化資料庫 (延遲載入以避免 import 循環)
from services.db import SupabaseDB

@st.cache_resource
def get_db():
    return SupabaseDB()

db = get_db()

# 導航與路由
from views import dashboard

def main():
    with st.sidebar:
        st.title("🏠 幸福之家 Pro")
        st.markdown("<div style='font-size: 0.8rem; color: #888; margin-bottom: 20px;'>Nordic Edition v14.0</div>", unsafe_allow_html=True)
        
        # 使用標準 Radio 但透過 CSS 美化
        menu = st.radio(
            "功能選單",
            [
                "📊 儀表板",
                "💵 租金收繳",
                "📅 繳費追蹤",
                "👥 房客管理",
                "⚡ 電費管理",
                "💰 支出管理",
                "⚙️ 系統設置"
            ],
            label_visibility="collapsed"
        )
        
    # 路由邏輯
    if menu == "📊 儀表板":
        dashboard.render(db)
    elif menu == "💵 租金收繳":
        st.info("🚧 租金收繳模組重構中... (請參照原 app.py 邏輯)")
        # 實際專案中，這裡會 import views.rent 並呼叫 render(db)
    elif menu == "📅 繳費追蹤":
        st.info("🚧 繳費追蹤模組重構中...")
    elif menu == "👥 房客管理":
        st.info("🚧 房客管理模組重構中...")
    elif menu == "⚡ 電費管理":
        st.info("🚧 電費管理模組重構中...")
    elif menu == "💰 支出管理":
        st.info("🚧 支出管理模組重構中...")
    else:
        st.info("⚙️ 系統設置")

if __name__ == "__main__":
    main()
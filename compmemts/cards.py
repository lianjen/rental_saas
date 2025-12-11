import streamlit as st

def kpi_card(title: str, value: str, color: str = "green", icon: str = ""):
    """
    渲染標準的 KPI 指標卡片
    :param color: green (Sage), red (Terracotta), blue, orange
    """
    html_content = f"""
    <div class="nordic-card border-left-{color}">
        <div class="card-title">{icon} {title}</div>
        <div class="card-value text-{color}">{value}</div>
    </div>
    """
    st.markdown(html_content, unsafe_allow_html=True)

def room_status_card(room_number, status_type, tenant_name, detail_text):
    """
    渲染房間狀態卡片
    :param status_type: active, expiring, expired, empty
    """
    # 對應 CSS class
    css_class_map = {
        "green": "status-active",
        "orange": "status-expiring",
        "red": "status-expired",
        "gray": "status-empty"
    }
    
    css_class = css_class_map.get(status_type, "status-empty")
    
    html_content = f"""
    <div class="room-card {css_class}">
        <div class="room-number">{room_number}</div>
        <div class="room-tenant">{tenant_name}</div>
        <div class="room-detail">{detail_text}</div>
    </div>
    """
    st.markdown(html_content, unsafe_allow_html=True)

def section_header(title: str, subtitle: str = ""):
    """
    渲染自定義標題
    """
    st.markdown(f"""
    <div style="margin-top: 20px; margin-bottom: 15px;">
        <h3 style="color: #5F8D78; font-weight: 700; margin-bottom: 0;">{title}</h3>
        <p style="color: #888; font-size: 0.9rem; margin-top: 0;">{subtitle}</p>
    </div>
    <hr style="margin-top: 5px; margin-bottom: 25px; border: 0; border-top: 1px solid #EEE;">
    """, unsafe_allow_html=True)
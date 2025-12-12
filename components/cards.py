# components/cards.py
import streamlit as st


def display_card(title: str, value: str, color: str = "blue"):
    """顯示 KPI 卡片"""
    colors = {
        "blue": "#f0f4f8",
        "green": "#edf2f0",
        "orange": "#fdf3e7",
        "red": "#fbeaea",
    }
    bordercolors = {
        "blue": "#98c1d9",
        "green": "#99b898",
        "orange": "#e0c3a5",
        "red": "#e5989b",
    }
    textcolor = "#4a5568"
    valuecolor = "#2d3748"

    st.markdown(
        f"""
        <div style="background: {colors.get(color, colors['blue'])}; border-radius: 10px; padding: 16px; margin-bottom: 12px; border: 1px solid {bordercolors.get(color, bordercolors['blue'])}; border-left: 5px solid {bordercolors.get(color, bordercolors['blue'])}; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
            <div style="color: {textcolor}; font-size: 0.9rem; font-weight: 600; letter-spacing: 0.5px;">{title}</div>
            <div style="color: {valuecolor}; font-size: 1.6rem; font-weight: 700; margin-top: 6px; font-family: Segoe UI, sans-serif;">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def display_room_card(room, statuscolor, statustext, detailtext):
    """顯示房間卡片"""
    bgcolor = {"green": "#eaf4e7", "red": "#fae3e3", "orange": "#fef5e6"}.get(
        statuscolor, "#f8f9fa"
    )
    textcolor = {
        "green": "#2f5d34",
        "red": "#8a2c2c",
        "orange": "#8a5a2c",
    }.get(statuscolor, "#4a5568")

    st.markdown(
        f"""
        <div style="background-color: {bgcolor}; border-radius: 12px; padding: 12px; text-align: center; height: 100px; display: flex; flex-direction: column; justify-content: center; align-items: center; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
            <div style="font-size: 1.3rem; font-weight: 700; color: {textcolor};">{room}</div>
            <div style="font-size: 0.9rem; font-weight: 600; color: {textcolor}; margin-top: 4px;">{statustext}</div>
            <div style="font-size: 0.75rem; color: {textcolor}; opacity: 0.8;">{detailtext}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(title: str, icon: str = "📋"):
    """顯示區塊標題"""
    st.markdown(f"### {icon} {title}")


def info_box(title: str, content: str, box_type: str = "info"):
    """顯示資訊框"""
    if box_type == "info":
        st.info(f"**{title}** - {content}")
    elif box_type == "warning":
        st.warning(f"**{title}** - {content}")
    elif box_type == "error":
        st.error(f"**{title}** - {content}")
    elif box_type == "success":
        st.success(f"**{title}** - {content}")


def metric_row(col_titles: list, col_values: list, col_colors: list = None):
    """顯示度量指標行"""
    if col_colors is None:
        col_colors = ["blue"] * len(col_titles)
    
    cols = st.columns(len(col_titles))
    for col, title, value, color in zip(cols, col_titles, col_values, col_colors):
        with col:
            display_card(title, value, color)

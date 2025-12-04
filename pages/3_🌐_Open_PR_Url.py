# PR URL批量访问工具
import streamlit as st

st.set_page_config(page_title="PR URL批量访问工具", layout="wide")

# 自定义CSS样式，设置蓝色按钮和页面间距
st.markdown("""
<style>
    /* 设置按钮为蓝色背景 */
    div[data-testid="stButton"] > button[kind="primary"] {
        background-color: #0066CC !important;
        color: white !important;
        border: none !important;
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover {
        background-color: #0052A3 !important;
    }
    /* 页面内容整体上移1.5cm（约57px） */
    .main .block-container {
        padding-top: 1rem !important;
    }
    h1 {
        margin-top: -1.5rem !important;
    }
    /* 成功打开信息显示样式：无背景色、字体减小1号 */
    .open-result-text {
        font-size: 0.875rem !important;
        color: #333 !important;
        margin: 0.5rem 0 !important;
        padding: 0 !important;
        background: none !important;
    }
    /* 输入框往上移动0.5cm（约19px） */
    div[data-testid="stTextArea"] {
        margin-top: -1.2rem !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("🌐 PR URL批量访问工具")
st.markdown("输入多个 PR URL（每行一个），点击按钮即可批量打开。")

# 统计有效URL数量的函数
def count_valid_urls(text):
    """统计有效URL数量（应用过滤规则）"""
    if not text:
        return 0
    count = 0
    for url in text.split('\n'):
        url = url.strip()
        # 去除空行
        if not url:
            continue
        # 去除包含jenkins的行（不区分大小写）
        if 'jenkins' in url.lower():
            continue
        # 去除引号（单引号和双引号）
        url = url.replace('"', '').replace("'", '')
        # 再次检查去除引号后是否为空
        if url:
            count += 1
    return count

# 多行输入框（高度减少1.5cm，约210px）
url_input = st.text_area(
    "",
    value="",
    placeholder="例如：\nhttps://github.com/example/pr1\nhttps://github.com/example/pr2",
    key="pr_url_input",
    height=210,  # 高度减少1.5cm（约57px）
    label_visibility="hidden"  # 隐藏标签
)

# 初始化session state
if 'open_result' not in st.session_state:
    st.session_state.open_result = None
if 'button_clicked' not in st.session_state:
    st.session_state.button_clicked = False

# 如果输入框为空，清除结果
if not url_input:
    st.session_state.open_result = None
    st.session_state.button_clicked = False

# 在输入框和按钮之间显示成功打开的信息（仅在点击按钮后显示）
if st.session_state.button_clicked and st.session_state.open_result:
    st.markdown(f'<p class="open-result-text">{st.session_state.open_result}</p>', unsafe_allow_html=True)

# 添加间距，将按钮推到底部
st.markdown("<br>", unsafe_allow_html=True)

# 底部按钮（宽度缩短一半）
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    if st.button("Open URL", key="open_button", use_container_width=True, type="primary"):
        st.session_state.button_clicked = True  # 标记按钮已点击
        if url_input:
            # 按行分割URL，并进行过滤处理
            urls = []
            for url in url_input.split('\n'):
                url = url.strip()  # 去除首尾空格
                # 去除空行
                if not url:
                    continue
                # 去除引号（单引号和双引号）
                url = url.replace('"', '').replace("'", '')
                # 再次检查去除引号后是否为空
                if url:
                    urls.append(url)
            
            if urls:
                total_count = len(urls)  # 记录总共输入的URL数量
                # 批量打开URL（在系统默认浏览器中打开）
                try:
                    import webbrowser
                    import time
                    
                    # 确保使用系统默认浏览器
                    browser = webbrowser.get()
                    opened_count = 0
                    
                    for i, url in enumerate(urls):
                        try:
                            # 在系统默认浏览器中打开URL
                            browser.open(url)
                            opened_count += 1
                            # 添加短暂延迟，避免浏览器卡顿（最后一个URL不需要延迟）
                            if i < len(urls) - 1:
                                time.sleep(0.3)  # 延迟0.3秒
                        except Exception as e:
                            st.warning(f"⚠️ 无法打开: {url} - {str(e)}")
                    
                    # 保存成功打开的信息到session state
                    st.session_state.open_result = f"成功打开{opened_count}个URL/共输入{total_count}个URL"
                    st.rerun()  # 刷新页面以显示结果
                except Exception as e:
                    st.error(f"打开URL失败: {e}")
                    st.error(f"错误详情: {str(e)}")
            else:
                st.session_state.open_result = None
                st.warning("⚠️ 请输入有效的 PR URL（已过滤空行、包含jenkins的行和无效URL）")
        else:
            st.session_state.open_result = None
            st.warning("⚠️ 请输入有效的 PR URL")


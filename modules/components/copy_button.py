"""
Shared copy button component for Streamlit pages.
Provides clipboard copy functionality via JavaScript.
"""
import streamlit as st


def copyable_text(label: str, value: str, key: str, copy_label: str = "📋"):
    """
    Render inline label with copyable text and a small copy button.

    Args:
        label: Display label prefix (e.g., "Pipeline ID:")
        value: The text value to copy to clipboard
        key: Unique identifier for this instance
        copy_label: Icon/label for copy button (default: 📋)
    """
    btn_id = f"cptbtn_{key}"
    escaped_value = value.replace('"', '\\"')
    escaped_label = label.replace('"', '\\"')

    js = f"""
<script>
(function() {{
  window._copyVal_{key} = function() {{
    var raw = "{escaped_value}";
    try {{
      navigator.clipboard.writeText(raw).then(function() {{
        var el = document.getElementById("{btn_id}");
        if(el) {{ el.textContent = "✅"; setTimeout(function(){{ el.textContent = "{copy_label}"; }}, 1500); }}
      }}).catch(function(err) {{}});
    }} catch(e) {{}}
  }}
}})();
</script>
<span style="display:inline-flex; align-items:center; gap:4px;">
    <span style="color:#555; font-size:14px;">{label}</span>
    <code style="background:#f5f5f5; padding:2px 6px; border-radius:3px; font-size:13px; color:#333;">{value}</code>
    <span id="{btn_id}" style="
        display:inline-flex; align-items:center;
        background:#e8f5e9; border:1px solid #a5d6a7; border-radius:4px;
        padding:0px 6px; font-size:11px; cursor:pointer;
        color:#2e7d32; user-select:none;
    " onclick="window._copyVal_{key}()">{copy_label}</span>
</span>
"""
    st.html(js)


def copy_button(text: str, key: str, label: str = "📋"):
    """
    Render a copy-to-clipboard button.

    Args:
        text: The text to copy to clipboard when button is clicked
        key: Unique identifier for this button instance
        label: Display label/icon for the button (default: 📋)
    """
    btn_id = f"cpbtn_{key}"
    escaped_text = text.replace('"', '\\"')

    js = f"""
<script>
(function() {{
  window._copyText_{key} = function() {{
    var raw = "{escaped_text}";
    try {{
      navigator.clipboard.writeText(raw).then(function() {{
        var el = document.getElementById("{btn_id}");
        if(el) {{ el.textContent = "✅ 已复制"; setTimeout(function(){{ el.textContent = "{label}"; }}, 1500); }}
      }}).catch(function(err) {{}});
    }} catch(e) {{}}
  }}
}})();
</script>
<span id="{btn_id}" style="
    display:inline-flex; align-items:center; gap:3px;
    background:#e8f5e9; border:1px solid #a5d6a7; border-radius:4px;
    padding:0px 8px; font-size:12px; cursor:pointer;
    color:#2e7d32; user-select:none; margin-left:4px;
" onclick="window._copyText_{key}()">{label}</span>
"""
    st.html(js)

import streamlit as st
import subprocess
import os
import glob

# =========================
# PAGE CONFIG
# =========================

st.set_page_config(
    page_title="AI QA Automation Engine",
    page_icon="🤖",
    layout="wide"
)

# =========================
# SIDEBAR
# =========================

st.sidebar.title("🤖 AI QA Automation Engine")

st.sidebar.info("""
Features Included:

✅ Website Testing  
✅ Broken Link Detection  
✅ Accessibility Testing  
✅ Screenshot Capture  
✅ AI Generated Test Cases  
✅ PDF Reports  
✅ CSV Reports  
✅ JSON Reports  
""")

# =========================
# MAIN TITLE
# =========================

st.title("🤖 AI QA Automation Engine")

st.write(
    "Enter any website URL and automatically generate QA reports, screenshots, and AI-based testing results."
)

# =========================
# URL INPUT
# =========================

website = st.text_input(
    "Enter Website URL",
    placeholder="https://example.com"
)

# =========================
# RUN BUTTON
# =========================

if st.button("🚀 Run AI QA Test"):

    # =========================
    # EMPTY URL CHECK
    # =========================

    if website.strip() == "":
        st.warning("⚠ Please enter a valid website URL")

    else:

        # =========================
        # RUN MAIN SCRIPT
        # =========================

        with st.spinner("Running AI QA Automation..."):

            process = subprocess.run(
                ["python", "main.py"],
                input=website,
                text=True,
                capture_output=True
            )

        # =========================
        # SUCCESS MESSAGE
        # =========================

        st.success("✅ Testing Completed Successfully")

        # =========================
        # SHOW OUTPUT
        # =========================

        st.subheader("📄 Test Output")

        if process.stdout:
            st.code(process.stdout)

        if process.stderr:
            st.error(process.stderr)

        # =========================
        # SHOW ONLY LATEST SCREENSHOT
        # =========================

        st.subheader("📸 Latest Website Screenshot")

        screenshot_files = sorted(
            glob.glob("screenshots/*.png"),
            key=os.path.getctime,
            reverse=True
        )

        if screenshot_files:

            latest_screenshot = screenshot_files[0]

            st.image(
                latest_screenshot,
                caption="Latest Tested Website Screenshot",
                use_container_width=True
            )

            with open(latest_screenshot, "rb") as file:

                st.download_button(
                    label="⬇ Download Screenshot",
                    data=file,
                    file_name=os.path.basename(latest_screenshot),
                    mime="image/png"
                )

        else:
            st.warning("⚠ No screenshots found")

        # =========================
        # SHOW ONLY LATEST REPORTS
        # =========================

        st.subheader("📥 Download Latest Reports")

        report_folders = [
            "reports",
            "reports/pdf",
            "reports/csv",
            "reports/excel",
            "reports/json"
        ]

        for folder in report_folders:

            if os.path.exists(folder):

                files = sorted(
                    glob.glob(f"{folder}/*"),
                    key=os.path.getctime,
                    reverse=True
                )

                if files:

                    latest_file = files[0]

                    st.markdown(f"### 📂 {folder}")

                    with open(latest_file, "rb") as file:

                        st.download_button(
                            label=f"⬇ Download {os.path.basename(latest_file)}",
                            data=file,
                            file_name=os.path.basename(latest_file)
                        )

# =========================
# FOOTER
# =========================

st.markdown("---")

st.markdown(
    "Made with ❤️ using Python, Streamlit, Selenium, Lighthouse, and Ollama AI"
)
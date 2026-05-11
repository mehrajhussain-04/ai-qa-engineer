import streamlit as st
import subprocess
import os
import glob

st.set_page_config(page_title="AI QA Automation Engine", layout="wide")

st.title("AI QA Automation Engine")
st.write("Enter any website URL to test")

website = st.text_input("Website URL")

if st.button("Run Test"):

    if website == "":
        st.warning("Please enter a website URL")

    else:
        st.info("Running AI QA Test...")

        process = subprocess.run(
            ["python", "main.py"],
            input=website,
            text=True,
            capture_output=True
        )

        st.success("Testing Completed")

        st.subheader("Test Output")
        st.code(process.stdout)

        # =========================
        # SHOW SCREENSHOTS
        # =========================

        st.subheader("Screenshots")

        screenshot_files = glob.glob("screenshots/*.png")

        if screenshot_files:
            latest_screenshot = max(screenshot_files, key=os.path.getctime)
            st.image(latest_screenshot, caption="Website Screenshot")

            with open(latest_screenshot, "rb") as file:
                st.download_button(
                    label="Download Screenshot",
                    data=file,
                    file_name=os.path.basename(latest_screenshot),
                    mime="image/png"
                )

        # =========================
        # DOWNLOAD REPORTS
        # =========================

        st.subheader("Download Reports")

        report_folders = [
            "reports",
            "reports/pdf",
            "reports/csv",
            "reports/excel",
            "reports/json"
        ]

        for folder in report_folders:

            if os.path.exists(folder):

                files = glob.glob(f"{folder}/*")

                for file_path in files:

                    if os.path.isfile(file_path):

                        with open(file_path, "rb") as file:

                            st.download_button(
                                label=f"Download {os.path.basename(file_path)}",
                                data=file,
                                file_name=os.path.basename(file_path)
                            )
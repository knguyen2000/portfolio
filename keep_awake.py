from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

URL = "https://khuongnguyen.streamlit.app/"


def main():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    driver.get(URL)

    try:
        button_xpath = "//button[contains(text(), 'Yes, get this app back up')]"
        wait = WebDriverWait(driver, 10)
        button = wait.until(EC.element_to_be_clickable((By.XPATH, button_xpath)))
        button.click()
        print("Hibernation button clicked. App is waking up.")
    except Exception:
        print("No hibernation button found. App is active.")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()

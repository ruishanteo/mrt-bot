import time
import uuid

from selenium import webdriver
from selenium.webdriver.common.by import By

CAPTCHA_IMAGE = f"captchas/{uuid.uuid4().hex}.png"
URL = "https://trainarrivalweb.smrt.com.sg/"

is_verified = False
is_captcha_image_extracted = False
captcha_id = 0
currently_selected_station = None
currently_selected_station_option = None

chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--headless")
driver = webdriver.Chrome(options=chrome_options)


def grab_stations():
    driver.get("http://journey.smrt.com.sg/journey/station_info/admiralty/map/")
    dropdown_btn = driver.find_element(By.CLASS_NAME, "k-select")
    dropdown_btn.click()

    

"""
Extract captcha image from the page
"""
def extract_images_with_selenium():
    global is_verified, is_captcha_image_extracted, captcha_id
    
    if is_captcha_image_extracted:
        print("Captcha image already extracted or verification is already done")
        return captcha_id
    
    is_verified = False
    
    driver.get(URL)
    with open(CAPTCHA_IMAGE, 'wb') as file:
        captcha_id += 1
        file.write(driver.find_element(By.ID, "imgCaptcha").screenshot_as_png)
        is_captcha_image_extracted = True
    
    return captcha_id

"""
Verification code
"""
def enter_verification_code(verification_code: str) -> None:
    global is_verified, is_captcha_image_extracted
    
    # find the input box and enter the verification code
    input_box = driver.find_element(By.ID, "txtCodeNumber")
    input_box.send_keys(verification_code)
    
    submit_btn = driver.find_element(By.ID, "ibtnSubmit")
    submit_btn.click()
    time.sleep(0.5)
    
    is_verified = check_verification_code()
    if not is_verified:
        is_captcha_image_extracted = False
    return is_verified

def check_verification_code() -> bool:
    return len(driver.find_elements(By.CLASS_NAME, "captcha-error")) == 0

"""
Select target station from dropdown
"""
def select_station(codes: list[str]) -> None:
    global currently_selected_station, currently_selected_station_option
    
    select_element = driver.find_element(By.ID, "ddlStation")
    selected_option = None
    for option in select_element.find_elements(By.TAG_NAME, 'option'):
        option_station_name = option.text.replace(" ", "").lower()
        
        if match_mrt_code(codes, option_station_name):
            selected_option = option.text
            currently_selected_station = codes
            currently_selected_station_option = selected_option
            
            option.click()
            break

    time.sleep(0.5)
    return selected_option

"""
Checks whether the station contains the MRT code
"""
def match_mrt_code(codes: list, station_name_with_codes: str) -> bool:
    for code in codes:
        if code.lower() in station_name_with_codes.lower():
            return True
    return False

"""
Get MRT lines for selected station
"""
def extract_mrt_lines(station_name_with_codes) -> list:
    # input: "Marina Bay (TE20/CE1/NS27)"
    # output: ["Thomson-East Coast Line", "Circle Line", "North-South Line"]
    codes_to_line = {
        "TE": "Thomson-East Coast Line",
        "NS": "North-South Line",
        "EW": "East-West Line",
        "CC": "Circle Line",
        "CE": "Circle Line",
        "NE": "North-East Line",
        "DT": "Downtown Line",
        "CG": "Changi Airport Line",
        "BP": "Bukit Panjang LRT",
    }
    code_index = station_name_with_codes.find("(") + 1
    station_name_with_codes = station_name_with_codes[code_index:-1]
    station_codes = station_name_with_codes.split("/")
    return [codes_to_line[code[:2]] for code in station_codes]

"""
Get arrival information for selected station
"""
def get_arrival_info_station(selected_option: str):
    arrival_data = {}
    mrt_lines = extract_mrt_lines(selected_option)
    table_elements = driver.find_elements(By.ID, "gvTime")
    
    for mrt_line in mrt_lines:
        arrival_data[mrt_line] = []
    
    print(mrt_lines, len(table_elements))
    
    for i in range(len(table_elements)):
        mrt_line = mrt_lines[i // 2]
        table = table_elements[i]
        
        table_data = [[], []]
        table_rows = table.find_elements(By.TAG_NAME, "td")

        for j in range(len(table_rows)):
            row = table_rows[j]
            table_data[j % 2].append(row.text)
        
        for data in table_data:
            arrival_data[mrt_line].append(data)
    
    return arrival_data

def refresh_arrival_time(codes: list[str]):
    global currently_selected_station, currently_selected_station_option
    if currently_selected_station != codes:
        return get_arrival_info_station(select_station(codes))
    
    refresh_btn = driver.find_element(By.ID, "ibtnRefresh")
    refresh_btn.click()
    
    time.sleep(0.5)
    
    return get_arrival_info_station(currently_selected_station_option)
    
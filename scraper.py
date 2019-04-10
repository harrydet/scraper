import logging
import os
from datetime import datetime
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver


def df_compare(row):
    if row['FTHG'] == row['FTAG']:
        val = 'D'
    elif row['FTHG'] > row['FTAG']:
        val = 'H'
    else:
        val = 'A'
    return val


def df_compare_ht(row):
    if row['HTHG'] == row['HTAG']:
        val = 'D'
    elif row['HTHG'] > row['HTAG']:
        val = 'H'
    else:
        val = 'A'
    return val


def convert_date(row):
    # Extract year
    season1, season2 = row['Season'].split('-')
    prefix = season1[slice(2)]
    if season1[slice(2, 4, 1)] == "99":
        season2 = "20" + season2
    else:
        season2 = prefix + season2

    # Parse date
    try:
        if '.' in row['Date']:
            datetime_obj = datetime.strptime(row['Date'], '%a. %d %b.')
        else:
            t1, _, _ = row['Date'].split(" ")
            if len(t1) > 2:
                datetime_obj = datetime.strptime(row['Date'], '%a %d %b')
            else:
                datetime_obj = datetime.strptime(row['Date'][3:], '%d %b')
    except ValueError:
        return 'errdate'

    # Add year
    if 8 <= datetime_obj.month <= 12:
        datetime_obj = datetime_obj.replace(year=int(season1))
    else:
        datetime_obj = datetime_obj.replace(year=int(season2))

    # Return
    return datetime_obj.strftime('%d/%m/%y')


urls = ["https://www.soccerstats.com/results.asp?league=england",
        "https://www.soccerstats.com/latest.asp?league=germany",
        "https://www.soccerstats.com/latest.asp?league=spain",
        "https://www.soccerstats.com/latest.asp?league=england2",
        "https://www.soccerstats.com/latest.asp?league=italy",
        "https://www.soccerstats.com/latest.asp?league=italy2"]

df_list = []

for url in urls:
    # Create a new Firefox session
    driver = webdriver.Chrome()
    driver.implicitly_wait(5)
    driver.get(url)

    try:
        agree_button = driver.find_element_by_class_name('details_continue--2CnZz')
        agree_button.click()
    except NameError:
        logging.debug("Button doesn't exist")

    # Get seasons
    dropdown_btn = driver.find_element_by_class_name("dropbtn")
    dropdown_list = driver.find_element_by_class_name("dropdown-content").find_elements_by_xpath(".//*")

    counter = 0

    while counter < len(dropdown_list):
        # Navigate to page
        dropdown_btn.click()
        season = dropdown_list[len(dropdown_list) - (1 + counter)]
        season_text = season.text
        season.click()
        driver.find_element_by_xpath('//*[@title="match list"]').click()

        # Switch to iframe

        driver.switch_to.frame(driver.find_element_by_id("pmatch"))

        soup_level2 = BeautifulSoup(driver.page_source, 'lxml')

        table = soup_level2.find('table', id="btable")

        # Store in data frame and remove junk
        data_frame = pd.read_html(str(table), header=0)
        data_frame = next(iter(data_frame), None)
        data_frame.drop(data_frame.columns[[1, 5, 6, 7]], axis=1, inplace=True)
        data_frame.dropna(how='all', inplace=True)

        # Rename columns
        data_frame.rename(columns={'Unnamed: 0': 'Date',
                                   'Unnamed: 2': 'Teams',
                                   'Unnamed: 3': 'Score'},
                          inplace=True)

        # Modify table

        data_frame['HomeTeam'], data_frame['AwayTeam'] = data_frame['Teams'].str.split('-', 1).str
        data_frame.drop('Teams', 1, inplace=True)

        data_frame['FTHG'], data_frame['FTAG'] = data_frame['Score'].str.split('-', 1).str
        data_frame.drop('Score', 1, inplace=True)

        data_frame['FTHG'] = pd.to_numeric(data_frame.FTHG)
        data_frame['FTAG'] = pd.to_numeric(data_frame.FTAG)

        data_frame['FTR'] = data_frame.apply(df_compare, axis=1)

        data_frame.insert(0, 'Div', 'E0')

        data_frame['HT'] = data_frame['HT'].map(lambda x: x.lstrip('(').rstrip(')'))
        data_frame['HTHG'], data_frame['HTAG'] = data_frame['HT'].str.split('-', 1).str
        data_frame['HTHG'] = pd.to_numeric(data_frame.HTHG)
        data_frame['HTAG'] = pd.to_numeric(data_frame.HTAG)
        data_frame.drop('HT', 1, inplace=True)

        data_frame['HTR'] = data_frame.apply(df_compare_ht, axis=1)

        data_frame.insert(10, 'Season', season_text.replace("/", "-"))

        data_frame['Date'] = data_frame.apply(convert_date, axis=1)

        df_list.append(data_frame)

        # Navigate to next page
        driver.switch_to.window(driver.window_handles[0])
        dropdown_list = driver.find_element_by_class_name("dropdown-content").find_elements_by_xpath(".//*")
        dropdown_btn = driver.find_element_by_class_name("dropbtn")
        counter += 1

    driver.quit()

result = pd.concat([pd.DataFrame(df_list[i]) for i in range(len(df_list))], ignore_index=True)
path = os.getcwd()
result.to_csv(path + "\\history.csv", index=False)

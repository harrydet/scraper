import logging
import os
from datetime import datetime
from sklearn import preprocessing
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
import selenium.webdriver.support.ui as ui
import selenium.webdriver.support.expected_conditions as EC


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
        "https://www.soccerstats.com/latest.asp?league=england2",
        "https://www.soccerstats.com/results.asp?league=germany"]

form_urls = ["https://www.soccerstats.com/latest.asp?league=england",
             "https://www.soccerstats.com/latest.asp?league=england2",
             "https://www.soccerstats.com/latest.asp?league=germany"]

df_list = []
df_list_fixtures = []
df_list_forms = []

for url in form_urls:
    driver = webdriver.Chrome()
    driver.implicitly_wait(5)
    driver.get(url)

    soup_level2 = BeautifulSoup(driver.page_source, 'lxml')

    tables = soup_level2.find_all('table', id="btable")
    table = tables[2]

    data_frame = pd.read_html(str(table), header=0)
    data_frame = next(iter(data_frame), None)
    data_frame.drop(data_frame.columns[[0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 13, 14]], axis=1, inplace=True)
    data_frame.dropna(how='any', inplace=True)

    data_frame.rename(columns={'Unnamed: 1': 'Team',
                               'last 8': 'Last8'},
                      inplace=True)

    data_frame['PPG'] = pd.to_numeric(data_frame.PPG)
    data_frame['Last8'] = pd.to_numeric(data_frame.Last8)

    data_frame["PPG"] = (
            (data_frame["PPG"] - data_frame["PPG"].min()) / (data_frame["PPG"].max() - data_frame["PPG"].min()))
    data_frame["Last8"] = (
            (data_frame["Last8"] - data_frame["Last8"].min()) / (data_frame["Last8"].max() - data_frame["Last8"].min()))

    df_list_forms.append(data_frame)

    driver.quit()

for url in urls:
    # Create a new Chrome session
    driver = webdriver.Chrome()
    driver.get(url)

    wait = ui.WebDriverWait(driver, 10)

    try:
        agree_button = driver.find_element_by_class_name('details_continue--2CnZz')
        agree_button.click()
    except NameError:
        logging.debug("Button doesn't exist")

    # Get seasons
    wait.until(EC.visibility_of(driver.find_element_by_class_name("dropbtn")))
    dropdown_btn = driver.find_element_by_class_name("dropbtn")
    dropdown_list = driver.find_element_by_class_name("dropdown-content").find_elements_by_xpath(".//*")

    counter = 0

    while counter < len(dropdown_list):
        # Navigate to page
        wait.until(EC.visibility_of(dropdown_btn))
        dropdown_btn.click()
        season = dropdown_list[len(dropdown_list) - (1 + counter)]

        # season = dropdown_list[counter]
        season_text = season.text
        wait.until(EC.visibility_of(season))
        season.click()
        driver.find_element_by_xpath('//*[@title="match list"]').click()

        # Switch to iframe
        wait.until(EC.visibility_of(driver.find_element_by_id("pmatch")))
        driver.switch_to.frame(driver.find_element_by_id("pmatch"))

        soup_level2 = BeautifulSoup(driver.page_source, 'lxml')

        tables = soup_level2.find_all('table', id="btable")
        table = tables[0]

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

        # Get fixtures
        if season_text == "2018/19":
            table_fixtures = tables[1]

            data_frame_fixtures = pd.read_html(str(table_fixtures), header=0)
            data_frame_fixtures = next(iter(data_frame_fixtures), None)
            data_frame_fixtures.drop(data_frame_fixtures.columns[[1, 3, 4, 5, 6, 7]], axis=1, inplace=True)
            data_frame_fixtures.dropna(how='all', inplace=True)

            data_frame_fixtures.rename(columns={'Unnamed: 0': 'Date',
                                                'Unnamed: 2': 'Teams'},
                                       inplace=True)

            data_frame_fixtures['HOME TEAM'], data_frame_fixtures['AWAY TEAM'] = data_frame_fixtures['Teams'].str.split(
                '-', 1).str

            data_frame_fixtures.insert(0, 'DIVISION', 'EPL')

            data_frame_fixtures.insert(5, 'Season', season_text.replace("/", "-"))
            data_frame_fixtures['DATE'] = data_frame_fixtures.apply(convert_date, axis=1)

            data_frame_fixtures.rename(columns={'Teams': 'FIXTURE'}, inplace=True)

            data_frame_fixtures.drop('Season', 1, inplace=True)
            data_frame_fixtures.drop('Date', 1, inplace=True)

            data_frame_fixtures = data_frame_fixtures[['DIVISION', 'DATE', 'FIXTURE', 'HOME TEAM', 'AWAY TEAM']]

            df_list_fixtures.append(data_frame_fixtures)

        # Navigate to next page
        driver.switch_to.window(driver.window_handles[0])
        dropdown_list = driver.find_element_by_class_name("dropdown-content").find_elements_by_xpath(".//*")
        wait.until(EC.visibility_of(driver.find_element_by_class_name("dropbtn")))
        dropdown_btn = driver.find_element_by_class_name("dropbtn")
        counter += 1

    driver.quit()

result = pd.concat([pd.DataFrame(df_list[i]) for i in range(len(df_list))], ignore_index=True)
result_fix = pd.concat([pd.DataFrame(df_list_fixtures[i]) for i in range(len(df_list_fixtures))], ignore_index=True)
result_forms = pd.concat([pd.DataFrame(df_list_forms[i]) for i in range(len(df_list_forms))], ignore_index=True)

result_fix['HOME TEAM'] = result_fix['HOME TEAM'].str.strip()
result_fix['AWAY TEAM'] = result_fix['AWAY TEAM'].str.strip()
result_forms['Team'] = result_forms['Team'].str.strip()

result_forms.rename(columns={'Team': 'Team_Home',
                             'PPG': 'PPG_Home',
                             'Last8': 'Last8_Home'}, inplace=True)

result_fix = pd.merge(result_fix, result_forms, left_on='HOME TEAM', right_on='Team_Home', how='left')

result_forms.rename(columns={'Team_Home': 'Team_Away',
                             'PPG_Home': 'PPG_Away',
                             'Last8_Home': 'Last8_Away'}, inplace=True)

result_fix = pd.merge(result_fix, result_forms, left_on='AWAY TEAM', right_on='Team_Away', how='left')

path = os.getcwd()
result.to_csv(path + "\\history.csv", index=False)
result_fix.to_csv(path + "\\fixtures.csv", index=False)

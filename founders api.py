#Founders API
#WARNING: This code needs the "founders-online-metadata.json" file to be within the same directory to run smoothly. This you can download at: https://founders.archives.gov/Metadata/.
#WARNING: Estimated runtime of this code is 5 hours. Be sure to keep your pc active during this time.  

import re
import time
import requests
import pandas as pd
import concurrent.futures
import threading

#gets webpage wth json content
def load_page(session, url):
    with session.get(url) as f:
        page = f.json()
    return page

#gets the part of a string after second to last slash. This will be added to a base url later. 
def get_string_after_second_to_last_slash(input_string):
    match = re.search(r'^(.*?/.*?)/([^/]+/[^/]+)$', input_string)
    if match:
        return match.group(2)
    return None

#responsible for updating the progress bar when extracting data
def update_progress_bar(index, url_total, lock):
    with lock:
        progress = (index + 1) / url_total
        progress_percent = progress * 100

        progress_bar_length = 40
        bar_length = int(progress * progress_bar_length)
        bar = '|' * bar_length + '-' * (progress_bar_length - bar_length)

        print(f"Progress: [{bar}] {progress_percent:.2f}%", end='\r')

#build in delay so no more then 10 requests are made per second. This was requested by the owners of the api
def request_delay(lock, last_request_time):
    with lock:
        now = time.time()
        elapsed = now - last_request_time[0]
        wait_time = max(0, 0.1 - elapsed)
        if wait_time > 0:
            time.sleep(wait_time)
        last_request_time[0] = time.time()

#function to load in the api data
def get_data(index, url, session, url_total, data, lock, last_request_time):
    #initiate a time delay
    request_delay(lock, last_request_time)
    
    #load data from api and save it in a list
    letter_data = load_page(session, url)    
    data.append(letter_data)
    
    #update the progress bar
    update_progress_bar(index, url_total, lock)

#constructing api urls based on base url and metadata urls
base = "https://founders.archives.gov/API/docdata/"
df_metadata = pd.read_json("founders-online-metadata.json")
url_endings = df_metadata["permalink"].apply(get_string_after_second_to_last_slash)
urls = [base + ending for ending in url_endings]
#urls = urls[:200] #for debugging purposes

#initiating variables
data = []
url_total = len(urls) 
lock = threading.Lock()
last_request_time = [0]
session = requests.Session()

#start executing data extraction
with concurrent.futures.ThreadPoolExecutor() as executor:
    futures = [
        executor.submit(get_data, index, url, session, url_total, data, lock, last_request_time)
        for index, url in enumerate(urls)
    ]
    for future in concurrent.futures.as_completed(futures):
        future.result()
    
print("\n[Loading data complete]")

#function to clean the contents of the letters
def clean_text(text):
    lines = text.split('\n')
    trimmed_lines = [line.strip() for line in lines]
    non_empty_lines = [line for line in trimmed_lines if line != '']
    cleaned_text = ' '.join(non_empty_lines)
    
    return cleaned_text

#function to recreate periods as shown on the archive website
def categorize_period(date):
    if date < pd.Timestamp('1775-04-19'):
        return 'Colonial'
    elif date >= pd.Timestamp('1775-04-19') and date <= pd.Timestamp('1783-09-03'):
        return 'Revolutionary War'
    elif date >= pd.Timestamp('1783-09-04') and date <= pd.Timestamp('1789-04-29'):
        return 'Confederation Period'
    elif date >= pd.Timestamp('1789-04-30') and date <= pd.Timestamp('1797-03-03'):
        return 'Washington Presidency'
    elif date >= pd.Timestamp('1797-03-04') and date <= pd.Timestamp('1801-03-03'):
        return 'Adams Presidency'
    elif date >= pd.Timestamp('1801-03-04') and date <= pd.Timestamp('1809-03-03'):
        return 'Jefferson Presidency'
    elif date >= pd.Timestamp('1809-03-04') and date <= pd.Timestamp('1817-03-03'):
        return 'Madison Presidency'
    elif date >= pd.Timestamp('1817-03-04'):
        return 'post-Madison Presidency'

df = pd.json_normalize(data)
df["content"] = df["content"].apply(clean_text)
df["date-from"] = pd.to_datetime(df["date-from"])
df["period"] = df["date-from"].apply(categorize_period)

df.to_csv("founders_data.csv")
print("[Successfully exported data to csv]")

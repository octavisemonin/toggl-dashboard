import streamlit as st
import io, re
import requests, json
import pandas as pd
# from cycler import cycler
from datetime import datetime
# import matplotlib.pyplot as plt

from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from json import JSONDecodeError

startup_network = st.secrets.startup_network

qualities = ['Recommended with confidence', 'Recommended', 
             'Limited recommendations', 'No recommendations', 
             'Initial impression: good', 'Initial impression: some concerns', 
             'Initial impression: poor', 'Prioritized Lead']
startup_fields = ['Primary Category','Thesis Sector','Hardware/Software','Focus','Description',
    'Headquarters','Quality Check','Funding Status','Partner Scouting','Website','Customer Type',
    'Funding Total','Powerhouse Perspective','Diversity Spotlight']

colors = ['#687090','#DF1864','#FFCD05','#A770A0','#93278F',
          '#70CADC','#3EB891','#079797','#4D4D4D',]
color_names = ['Grey','Pink','Yellow','Light purple','Purple',
               'Light blue','Light green','Turquoise','Typeform', ]

exclude_list = [
    '?', '??', '???', 'N/A', 'n/a', '\n',
    'none.com','N','n','None','none',
    ' ','Stealth','stealth',
    'linkedin.com', 'herox.com', 'activate.org', 
    'energy.gov', 'greentownlabs.com',
    'cyclotronroad.org', 'stanford.edu', 
    'berkeley.edu', 'harvard.edu', 'illinois.edu',
    'fraunhofer.de', 'solarimpulse.com',
    'engine.xyz', 'greencom-networks.com',
    'wixsite.com', 'business.site', 'carrd.co',
    'webflow.io','wordpress.com', 'weebly.com',
    'blogspot.com','herokuapp.com','us.com','forbes.com', # revisit this line!
    'substack.com','producthunt.com','instagram.com',
    'youtube.com','squarespace.com','google.com',
    'crunchbase.com','f6s.com','facebook.com',
    'apple.com',
]

# default_cycler = (cycler(color=colors))
# plt.rc('axes', prop_cycle=default_cycler)
# plt.rc('legend', frameon=False)
# plt.rc('axes.spines', right=False)
# plt.rc('axes.spines', top=False)

def query_streak(url):
    """Query Streak using Tavi's account"""
    
    headers = {
        'content-type': "application/json",
        'authorization': f"Basic {st.secrets.streak_key}"
        }

    s = requests.Session()
    retries = Retry(total=5, backoff_factor=1, 
                    status_forcelist=[ 429, 500, 502, 503, 504 ])
    s.mount('https://', HTTPAdapter(max_retries=retries))

    response = s.request("GET", url, headers=headers)

    return response

def get_pipelines():
    """Get all pipeline names and keys"""

    url = "https://www.streak.com/api/v1/pipelines"
    r = query_streak(url)
    pipes = pd.DataFrame(r.json())

    return pipes

def get_contact(contact_key):
    """Get contact for a given contact_key"""

    url = f"https://www.streak.com/api/v2/contacts/{contact_key}"
    r = query_streak(url)
    contact = pd.Series(r.json())
    cols = ['familyName','givenName','emailAddresses','title']

    return contact.reindex(cols)

def get_stages(pipeline_key=startup_network):
    """Get stages for a given pipeline_key"""

    url = f"https://www.streak.com/api/v1/pipelines/{pipeline_key}/stages"
    r = query_streak(url)
    return r.json()

def get_boxes(pipeline_key=startup_network):
    """Get boxes for a given pipeline_key"""
    
    url = f"https://www.streak.com/api/v1/pipelines/{pipeline_key}/boxes"
    r = query_streak(url)
    boxes = pd.DataFrame(r.json())
    boxes.rename(columns={'name':'Name'}, inplace=True)

    stages = get_stages(pipeline_key)
    boxes['Stage'] = boxes['stageKey'].map(lambda key: stages[key]['name'])
    
    timestamp_cols = [col for col in boxes.columns if 'Timestamp' in col]
    for col in timestamp_cols:
        boxes[col] = pd.to_datetime(boxes[col], unit='ms', errors='coerce')

    return boxes.sort_values('creationTimestamp').reset_index()

def get_fields(pipeline_key=startup_network):
    """Get fields for a given pipeline and return as DataFrame"""
    
    url = f'https://www.streak.com/api/v1/pipelines/{pipeline_key}/fields'
    r = query_streak(url)
    fields = pd.DataFrame(r.json())
    
    return fields

def get_column_info(column_name, pipeline_key=startup_network):
    """Get tags for a given custom_column and return as dict"""
    
    fields = get_fields(pipeline_key)
    field = fields.loc[fields['name']==column_name].iloc[0]
    
    if field['type'] == 'TAG':
        tags = pd.DataFrame(field['tagSettings']['tags'])
        tags = tags.set_index('key', drop=True)['tag']
        return field, tags.to_dict()
    
    elif field['type'] == 'DROPDOWN':
        tags = pd.DataFrame(field['dropdownSettings']['items'])
        tags = tags.set_index('key', drop=True)['name']
        return field, tags.to_dict()

    else:
        return field, None

def field_iterator(box_fields, column_key, decoder=None):
    """Return field value for a given box_fields and column_key"""

    try:
        contents = box_fields[column_key]
        
        if decoder:
            if type(contents) == str:
                return decoder[contents]
            else:
                tags = sorted([decoder[f] for f in contents])
                # return ', '.join(tags)
                return tags
        else:
            return contents
    except KeyError:
        return

def extract_field(boxes, fields, column_name, 
                  pipeline_key=startup_network):
    """Return field values for given boxes, fields, and column_name"""

    field, decoder = get_column_info(column_name, pipeline_key)

    new_col = boxes['fields'].apply(field_iterator, 
                                    column_key=field['key'],
                                    decoder=decoder)

    if field['type'] == 'DROPDOWN':
        return pd.Categorical(new_col, decoder.values(), ordered=True)
    else:
        return new_col

def ph_contact(row):
    """Return the level of our relationship with a startup"""

    if row['Stage'] == 'Portfolio Company':
        return 'PHV Portfolio'
    elif (# Meeting Notes are *about* companies, not *with* companies
          row['callLogCount'] > 0 or
          row['Stage'] == 'Engaged'):
        return 'Interviewed'
    elif (type(row['contacts']) == list or 
          row['gmailThreadCount'] > 0):
        return 'Email contact'
    else:
        return 'Database-only'

def get_startup_network():
    """Get and prepare all boxes for the Startup Network"""
    
    sn = get_boxes()
    
    fields = get_fields()
    for field in startup_fields:
        sn[field] = extract_field(sn, fields, field)

    sn['Quality Check'] = pd.Categorical(sn['Quality Check'], 
                            categories=qualities, ordered=True)


    _,tags = get_column_info('Focus')
    focus = [sn['Focus'].str.contains(tag, regex=False).rename(tag) for tag in tags.values()]
    focus = pd.concat(focus, axis=1)
    sn = pd.concat([sn, focus], axis=1)

    sn['PH Contact'] = sn.apply(ph_contact, axis=1)
    return sn

def unravel(series, split_string=' '):
    """Unravel a Series of strings to one list of words or sentences"""
    
    l = series.str.split(split_string).dropna().values
    flat = [item for sublist in l for item in sublist]
    
    return flat

def count_words(series):
    """Return a count of all words in a given Series of strings"""
    
    flat = unravel(series)
    stripped = [re.sub('[\W_]+', '', item).lower() for item in flat]
    counts = pd.Series(stripped).value_counts()
    
    return counts

def find_domain(website):
    """Extract the domain from website"""
    
    if website is None:
        return None
    
    pattern = '//(.+?)/'
    m = re.search(pattern, website)
    if m: subs = m.group(1).split('.')
    else: subs = website.split('.')

    if subs[-1] in ['au','br','cn','jp','ke','kr','nz','uk','za'] or '.us.com' in website:
        domain = '.'.join(subs[-3:])
    else:
        domain = '.'.join(subs[-2:])
    if 'https://' in domain:
        domain = domain.replace('https://', '')
    if 'http://' in domain:
        domain = domain.replace('http://', '')

    return domain.lower().strip().strip('/')
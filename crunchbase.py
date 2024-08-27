import requests, json, time
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from json import JSONDecodeError
from datetime import datetime
from random import random
# from tqdm import tqdm
import pandas as pd
import powerhouse as ph
import streamlit as st

cb_key = st.secrets.cb_key
userkey = {'user_key': cb_key}

def send_request(method, url, params, query=None):
    """Send a requests to Crunchbase with backoff if we overload their server"""

    s = requests.Session()
    retries = Retry(total=5, backoff_factor=2, 
                    status_forcelist=[ 429, 500, 502, 503, 504 ],
                    allowed_methods=["GET", "PUT", "POST"])
    s.mount('https://', HTTPAdapter(max_retries=retries))
    r = s.request(method, url, params=params, json=query)

    try:
        return json.loads(r.text)
    except JSONDecodeError:
        print(r.history)
        print(r.headers)
        time.sleep(10)
        return r

def match_startups(values, on_domain=True):
    """Match startups by website or permalink to Crunchbase"""

    url = "https://api.crunchbase.com/api/v4/searches/organizations"

    if on_domain:
        query_method = [
            {
                "type": "predicate",
                "field_id": "website_url",
                "operator_id": "domain_includes",
                "values": [ph.find_domain(website) for website in values]
            }
        ]
    else:
        query_method = [
            {
                "type": "predicate",
                "field_id": "identifier",
                "operator_id": "includes",
                "values": values
            }
        ]        

    query = {
        "field_ids":[
            "website_url","short_description",
            "diversity_spotlights","funding_total",
            "funding_stage","last_equity_funding_type",
            "categories","category_groups",
            "location_identifiers","founded_on",
            "last_funding_at",
            "num_employees_enum","permalink"
        ],
        "query": query_method,
        "order": [
            {
            "field_id": "created_at",
            "sort": "desc"
            }
        ],
        "limit": 1000
    }
    
    data = send_request("POST", url, userkey, query)

    if type(data) is dict and 'count' in data.keys() and data['count'] > 0:
        return data['entities']

def match_startup(website):
    """Match a single startup by website to Crunchbase"""

    entities = match_startups([website])
    
    if entities:
        return entities[0]['properties']

def parse_location(item):

    try:
        locs = item['location_identifiers']
        city = [loc for loc in locs if loc['location_type']=='city'][0]['value']
        region = [loc for loc in locs if loc['location_type']=='region'][0]['value']
        country = [loc for loc in locs if loc['location_type']=='country'][0]['value']

        if country=='United States':
            region = region  
        else:
            region = country

        return f"{city}, {region}" if region else f"{city}"

    except (IndexError, KeyError) as e:
        return None

funding_types = {'angel':'Pre-Seed',
                 'pre_seed':'Pre-Seed',
                 'seed':'Seed', 'series_a':'Series A'}

funding_cutoffs = [1E6, 5E6, 20E6]

def parse_funding(item):

    if 'last_equity_funding_type' in item.keys():
        funding_status = item['last_equity_funding_type']
        if funding_status in funding_types.keys():
            funding_status = funding_types[funding_status] 
        elif 'series' in funding_status and len(funding_status)==8:
            funding_status = 'Series B or later'
        else:
            funding_status = 'Undisclosed'
            
        last_equity_funding_type = item['last_equity_funding_type']
    else:
        funding_status = 'Undisclosed'
        last_equity_funding_type = None

    if 'funding_total' in item.keys() and item['funding_total']['value_usd'] > 0:
        funding_total = item['funding_total']['value_usd']
        if funding_status == 'Undisclosed':
            if funding_total > funding_cutoffs[-1]:
                funding_status = 'Series B or later'
            elif funding_total > funding_cutoffs[-2]:
                funding_status = 'Series A'
            elif funding_total > funding_cutoffs[-3]:
                funding_status = 'Seed'
            else:
                funding_status = 'Pre-Seed'
    else:
        funding_total = None

    return funding_status,last_equity_funding_type,funding_total

diversity_lookup = {
    'American Indian / Alaska Native Founded':'Native American or Alaskan Native',
    'American Indian / Alaska Native Led':'Native American or Alaskan Native',
    'Indigenous Founded':'Native American or Alaskan Native',
    'Indigenous Led':'Native American or Alaskan Native',
    'Black / African American Founded':'Black American or African-American or African',
    'Black / African American Led':'Black American or African-American or African',
    'Black Founded':'Black American or African-American or African',
    'Black Led':'Black American or African-American or African',
    'East Asian Founded':'Asian',
    'East Asian Led':'Asian',
    'Hispanic / Latinx Founded':'Latinx or Hispanic',
    'Hispanic / Latinx Led':'Latinx or Hispanic',
    'Hispanic / Latine Founded':'Latinx or Hispanic',
    'Hispanic / Latine Led':'Latinx or Hispanic',
    'Middle Eastern / North African Founded':'North African or Middle Eastern',
    'Middle Eastern / North African Led':'North African or Middle Eastern',
    'Native Hawaiian / Pacific Islander Founded':'Pacific Islander',
    'Native Hawaiian / Pacific Islander Led':'Pacific Islander',
    'South Asian Founded':'Asian',
    'South Asian Led':'Asian',
    'Southeast Asian Founded':'Asian',
    'Southeast Asian Led':'Asian',
    'Women Founded':'Female',
    'Women Led':'Female'
    }

def parse_diversity(item):

    if 'diversity_spotlights' in item.keys():
        diversity = [d['value'] for d in item['diversity_spotlights']]
        return set([diversity_lookup[tag] for tag in diversity])
    else:
        return None

def parse_categories(item):

    if 'categories' in item.keys():
        categories = [d['value'] for d in item['categories']]
    else:
        categories = None
    if 'category_groups' in item.keys():
        category_groups = [d['value'] for d in item['category_groups']]
    else:
        category_groups = None

    return categories,category_groups

def parse_founded_on(item):

    if 'founded_on' in item.keys():
        return item['founded_on']['value']

def parse_last_funding_at(item):

    if 'last_funding_at' in item.keys():
        return item['last_funding_at']

employees_dict = {
    "c_00001_00010" : "1-10",
    "c_00011_00050" : "11-50",
    "c_00051_00100" : "51-100",
    "c_00101_00250" : "101-250",
    "c_00251_00500" : "251-500",
    "c_00501_01000" : "501-1000",
    "c_01001_05000" : "1001-5000",
    "c_05001_10000" : "5001-10000",
    "c_10001_max" : "10001+"
}

def parse_num_employees(item):

    if 'num_employees_enum' in item.keys():
        return employees_dict[item['num_employees_enum']]

def parse_properties(item):

    name = item['identifier']['value']
    website_url = item['website_url'] if 'website_url' in item.keys() else None
    short_description = item['short_description']
    permalink = item['permalink']
    location = parse_location(item)
    funding_status,last_equity_funding_type,funding_total = parse_funding(item)
    last_funding_at = parse_last_funding_at(item)
    diversity = parse_diversity(item)
    categories,category_groups = parse_categories(item)
    founded_on = parse_founded_on(item)
    num_employees = parse_num_employees(item)

    # Focus, someday.    
    
    output = {'name': name,
              'website_url': website_url,
              'description': short_description,
              'permalink' : permalink,
              'location': location, 
              'funding_status': funding_status,
              'last_equity_funding_type': last_equity_funding_type,
              'last_funding_at': last_funding_at,
              'funding_total': funding_total,
              'diversity': diversity,
              'categories': categories,
              'category_groups': category_groups,
              'founded_on': founded_on,
              'num_employees': num_employees}
    
    return pd.Series(output)

def get_rounds(permalink):
    """Get funding rounds for a given permalink (organization)"""

    url = f'https://api.crunchbase.com/api/v4/entities/organizations/{permalink}'
    querystring = {"user_key":cb_key,
                   "card_ids":"raised_funding_rounds"}

    return send_request("GET", url, querystring)

def get_many_rounds(identifiers, by="funded_organization_identifier"):
    """Query CB for funding rounds for a list (up to 200) of identifiers"""

    query = {
        "field_ids":["announced_on", "created_at",
                     "investment_type", "money_raised",
                     "pre_money_valuation","post_money_valuation",
                     "investor_identifiers","num_investors",
                     "funded_organization_funding_total",
                     "funded_organization_identifier",
                     "identifier"
        ],
        "query": [
            {
                "type": "predicate",
                "field_id": by,
                "operator_id": "includes",
                "values": identifiers
            }
        ],
        "order": [
            {
            "field_id": "created_at",
            "sort": "desc"
            }
        ],
        "limit": 1000
    }

    url = "https://api.crunchbase.com/api/v4/searches/funding_rounds"
    return send_request("POST", url, userkey, query)

def parse_all_rounds(entities, by="funded_organization_identifier"):
    """Parse funding rounds for a list of an arbitrary number of permalinks"""

    rounds = pd.DataFrame(r['properties'] for r in entities).reset_index(drop=True)

    rounds['name'] = rounds['funded_organization_identifier'].dropna().map(lambda d: d['value'])
    rounds['permalink'] = rounds['funded_organization_identifier'].map(lambda d: d['permalink'])
    rounds['investor_names'] = rounds['investor_identifiers'].dropna().map(lambda l: [i['value'] for i in l])
    rounds['announced_on'] = pd.to_datetime(rounds['announced_on'], errors='coerce')
    rounds['usd_raised'] = rounds['money_raised'].dropna().map(lambda d: d['value_usd'])

    rounds['post_money_value_usd'] = rounds['post_money_valuation'].dropna().map(lambda d: d['value_usd'])
    rounds['pre_money_value_usd'] = rounds['pre_money_valuation'].dropna().map(lambda d: d['value_usd'])

    rounds['url'] = 'https://www.crunchbase.com/organization/' + rounds['permalink'].str[:]

    return rounds

def get_investors(data):
    rounds = data['cards']['raised_funding_rounds']

    investors = [r['investor_identifiers'] for r in rounds if 'investor_identifiers' in r.keys()]
    investors = set([i['value'] for sublist in investors for i in sublist])
    return ', '.join(investors)

def total_funding(data):
    rounds = data['cards']['raised_funding_rounds']

    values = [r['money_raised']['value_usd'] for r in rounds if 'money_raised' in r.keys()]
    return sum([int(v) for v in values])

def funding_velocity(data, cutoff = datetime(2017, 1, 1)):
    rounds = data['cards']['raised_funding_rounds']

    dates = [r['announced_on'] for r in rounds]
    return sum([datetime(*[int(i) for i in d.split('-')]) > cutoff for d in dates])
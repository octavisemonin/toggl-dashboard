import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import time
from pathlib import Path
import powerhouse as ph
import crunchbase as cb
import toggl_plot

# Set the title and favicon that appear in the Browser's tab bar.
st.set_page_config(
    page_title='Toggl dashboard',
    page_icon='https://images.squarespace-cdn.com/content/v1/5d4b459777a6c6000115bee3/1572897522106-VQQ4XSX22M5WH8JXSABH/favicon.ico?format=100w', # This is an emoji shortcode. Could be a URL too.
    layout='wide'
)

# -----------------------------------------------------------------------------
# Declare some useful functions.

@st.cache_data(ttl='1d')
def get_toggl_data():
    """Get project data from Toggl.

    This uses caching to avoid having to read the file every time.
    """

    # later: st.secrets.key
    headers = {'content-type': 'application/json', 
               'Authorization': 'Basic %s' %  st.secrets.toggl_key}

    # Get clients
    data = requests.get(
        'https://api.track.toggl.com/api/v9/workspaces/4691435/clients', 
        headers=headers
    )

    clients = pd.DataFrame(data.json())

    # Get projects
    data = requests.get(
        'https://api.track.toggl.com/api/v9/workspaces/4691435/projects', 
        headers=headers
    )

    projects = pd.DataFrame(data.json())

    projects = pd.merge(
        projects, clients[['name','id']], 
        left_on='client_id', right_on='id',
        suffixes=['','_client']
    )

    return projects

projects = get_toggl_data()

@st.cache_data(ttl='1d')
def get_startup_network():
    sn = ph.get_startup_network()

    fields = ph.get_fields().set_index('name')
    sn['permalink_streak'] = ph.extract_field(sn, fields, 'permalink')
    sn['permalink'] = sn['permalink_streak'].map(lambda s: s.split('/')[-1] if s else None)
    sn['domain'] = sn['Website'].map(ph.find_domain)

    st.toast("Streak load complete!")
    return sn

def simple_text_money(f):
    """Convert a large dollar amount to $M or $k"""
    
    if f >= 1E6:
        r = f"\${f/1E6:.1f}M"
    elif f > 0:
        r = f"\${f/1E3:.0f}k"
    else:
        r = 'an undisclosed amount'
        
    return r

def round_to_text(row):
    """Convert raise info to a descriptive string"""
    n = f"[{row['name']}]({row['Website']})"
    r = f"[{simple_text_money(row['usd_raised'])}]({row['url']})"
    
    if type(row['investor_names'])==list:
        i = ', '.join(row['investor_names'])
        return f"* {n} raised {r} from {i}"
        
    else:
        return f"* {n} raised {r}"

# -----------------------------------------------------------------------------
# Draw the actual page

# Set the title that appears at the top of the page.
'''
# :clock2: Toggl dashboard
'''

toggl_analysis = toggl_plot.plot_projects(projects)
fig, all_time_rate = toggl_analysis[0]
actives_fig, recent_rate = toggl_analysis[1]

# Display all
data_container = st.container()
config = {'displayModeBar': False}

with data_container:
    all_time, actives = st.columns(2)
    with all_time:
        '### All time history of Toggl projects'
        st.metric(
            label=f'All-time Hourly Rate',
            value=f'${all_time_rate:,.0f}/hr',
        )
        st.plotly_chart(fig, use_container_width=True, config=config)

    with actives:
        '### Active or <7 day old projects only'
        st.metric(
            label=f'Active Hourly Rate',
            value=f'${recent_rate:,.0f}/hr',
        )
        st.plotly_chart(actives_fig, use_container_width=True, config=config)

''
''
'''
# :moneybag: Rounds last week
'''

with st.spinner('Getting Startup Network...'):
    sn = get_startup_network()

permalinks = sn['permalink'].loc[~sn['domain'].isin(ph.exclude_list)]
permalinks = permalinks.dropna().drop_duplicates().tolist()

with st.spinner('Getting funding rounds (takes ~2m)'):
    rounds = cb.get_all_rounds(permalinks)

st.toast("Funding rounds complete!")

cols = ['permalink','Website','Stage']
rounds = pd.merge(rounds, sn[cols].drop_duplicates(subset=['permalink']))

now = datetime.now() - timedelta(days=0)
cutoff = datetime.now() - timedelta(days=8)
recent_rounds = rounds.loc[rounds['announced_on'].between(cutoff, now) & 
                          ~rounds['Stage'].isin(['Out of Scope'])]

total_money = recent_rounds['usd_raised'].sum() / 1E6
total_rounds = len(recent_rounds)
summary_string = f"\\${total_money:.0f}M raised in {total_rounds} rounds last week"
rounds_text = recent_rounds.sort_values('usd_raised').apply(round_to_text, axis=1)

st.write(summary_string+'\n'+'\n'.join(rounds_text))
''
st.markdown(summary_string+'\n'+'\n'.join(rounds_text))

# to be deleted:
cols = ['name','announced_on','created_at',
        'investment_type','num_investors','investor_names',
        'usd_raised','Stage']
st.dataframe(recent_rounds[cols].sort_values('announced_on'))

st.button("Rerun")
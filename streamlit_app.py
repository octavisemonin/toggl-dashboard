import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
from pathlib import Path
import powerhouse as ph
import crunchbase as cb

colors = ['#687090',
 '#DF1864',
 '#FFCD05',
 '#A770A0',
 '#93278F',
 '#70CADC',
 '#3EB891',
 '#079797',
 '#4D4D4D']

num_colors = len(colors)

# Set the title and favicon that appear in the Browser's tab bar.
st.set_page_config(
    page_title='Toggl dashboard',
    page_icon=':clock2:', # This is an emoji shortcode. Could be a URL too.
    layout='wide'
)

# -----------------------------------------------------------------------------
# Declare some useful functions.

def hovertext(row):
    f = f'Fee to date: ${row["fee_to_date"]:,.0f}'
    h = f'Hours: {row["Hours"]:.0f}'
    r = f'Effective rate: ${row["Effective $/hr"]:.0f}/hr'
    e = f'End date: {row["end_date"]}'
    
    return '<br>'.join([f,h,r,e])

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

    # Calculations and formatting
    projects['start_date'] = pd.to_datetime(projects['start_date'], errors='coerce')
    projects['end_date'] = pd.to_datetime(projects['end_date'], errors='coerce')

    projects['duration_days'] = (projects['end_date'] - projects['start_date']).dt.days
    projects['fraction_complete'] = (datetime.now() - projects['start_date']).dt.days / projects['duration_days']
    projects.loc[projects['fraction_complete'] > 1,'fraction_complete'] = 1

    projects['fee_to_date'] = projects['fixed_fee'] * projects['fraction_complete']
    projects['hourly_rate'] = projects['fee_to_date'] / projects['actual_hours']

    projects['Hours'] = projects['actual_hours']
    projects['Effective $/hr'] = projects['hourly_rate']
    projects['Value (USD)'] = projects['fixed_fee']
    projects['Value (k$)'] = projects['Value (USD)'].dropna().map(lambda n: f'${int(n/1000)}k')
    projects['Label'] = projects['name'].str[:] + ', ' + projects['Value (k$)'].str[:]
    projects['Offset'] = 5

    projects = projects.dropna(subset=['hourly_rate'])
    projects = projects.sort_values('Effective $/hr')

    projects = projects.dropna(subset=['hourly_rate'])
    projects['Left'] = projects['actual_hours'].cumsum() - projects['actual_hours']
    projects['hover_text'] = projects.apply(hovertext, axis=1)
    projects['color'] = [colors[i % num_colors] for i in range(len(projects))]

    return projects

@st.cache_data(ttl='1d')
def get_startup_network():
    sn = ph.get_startup_network()

    fields = ph.get_fields().set_index('name')
    sn['permalink_streak'] = ph.extract_field(sn, fields, 'permalink')
    sn['permalink'] = sn['permalink_streak'].map(lambda s: s.split('/')[-1] if s else None)
    sn['domain'] = sn['Website'].map(ph.find_domain)

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

projects = get_toggl_data()

# -----------------------------------------------------------------------------
# Draw the actual page

# Set the title that appears at the top of the page.
'''
# :clock2: Toggl dashboard
'''

# Toggl charts
config = {'displayModeBar': False}

fig = go.Figure()

# Create horizontal bar chart
fig.add_trace(go.Bar(
    y=projects['Left'] + projects['Hours'] / 2,
    x=projects['Effective $/hr'],
    orientation='h',
    width=projects['Hours'],
    marker=dict(color=projects['color']),
    name='Effective $/hr',
    text=projects['Label'],
    textposition='outside',
    hovertemplate=projects['hover_text'] + '<extra></extra>',  # Custom hover text without extra info
    hovertext='hover_text'
))

# Update layout
fig.update_layout(
    font_color='black',
    margin=dict(l=20, r=20, t=20, b=20),
    height=600,  # Set the height of the figure to be taller
    width=800,   # Set the width of the figure to be narrower
    yaxis_title='Hours',
    xaxis_title='Effective $/hr',
    xaxis=dict(range=[0, projects['Effective $/hr'].max()*1.5]),
    showlegend=False,
    plot_bgcolor='white',  # Set the plot background color to white
    paper_bgcolor='white'  # Set the paper background color to white
)

# Remove top and right spines (equivalent in Plotly is removing gridlines)
fig.update_xaxes(showline=True, linewidth=1, linecolor='black', gridcolor='rgba(0,0,0,0)')
fig.update_yaxes(showline=True, linewidth=1, linecolor='black', gridcolor='rgba(0,0,0,0)')

# All-time hourly rate
all_time_rate = projects['fee_to_date'].sum() / projects['actual_hours'].sum()

# Recent projects
recents = projects.loc[datetime.now() - projects['end_date'] < timedelta(days=7)].copy()
recents['Left'] = recents['actual_hours'].cumsum() - recents['actual_hours']
recents['color'] = [colors[i % num_colors] for i in range(len(recents))]

# Create horizontal bar chart
actives_fig = go.Figure()

actives_fig.add_trace(go.Bar(
    y=recents['Left'] + recents['Hours'] / 2,
    x=recents['Effective $/hr'],
    orientation='h',
    width=recents['Hours'],
    marker=dict(color=recents['color']),
    name='Effective $/hr',
    text=recents['Label'],
    textposition='outside',
    hovertemplate=recents['hover_text'] + '<extra></extra>',  # Custom hover text without extra info
    hovertext='hover_text'
))

# Update layout
actives_fig.update_layout(
    font_color='black',
    margin=dict(l=20, r=20, t=20, b=20),
    height=600,  # Set the height of the figure to be taller
    width=800,   # Set the width of the figure to be narrower
    yaxis_title='Hours',
    xaxis_title='Effective $/hr',
    xaxis=dict(range=[0, recents['Effective $/hr'].max()*1.5]),
    showlegend=False,
    plot_bgcolor='white',  # Set the plot background color to white
    paper_bgcolor='white'  # Set the paper background color to white
)

# Remove top and right spines (equivalent in Plotly is removing gridlines)
actives_fig.update_xaxes(showline=True, linewidth=1, linecolor='black', gridcolor='rgba(0,0,0,0)')
actives_fig.update_yaxes(showline=True, linewidth=1, linecolor='black', gridcolor='rgba(0,0,0,0)')

# Average hourly rate
recent_rate = recents['fee_to_date'].sum() / recents['actual_hours'].sum()

# Display all
data_container = st.container()

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

st.success("Streak load complete!")

progress_text = "Loading rounds..."
my_bar = st.progress(0, text=progress_text)

entities = []
permalinks = sn['permalink'].loc[~sn['domain'].isin(ph.exclude_list)].dropna().drop_duplicates().tolist()

for i in range(0, len(permalinks), 200):
    d = cb.get_many_rounds(permalinks[i:i+200])
    entities = entities + d['entities']
    my_bar.progress((i/len(permalinks)), text=progress_text)

time.sleep(1)
my_bar.empty()

rounds = cb.parse_all_rounds(entities)
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
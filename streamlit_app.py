import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta
import math
from pathlib import Path

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
def get_gdp_data():
    """Grab project data from Toggl.

    This uses caching to avoid having to read the file every time. If we were
    reading from an HTTP endpoint instead of a file, it's a good idea to set
    a maximum age to the cache with the TTL argument: @st.cache_data(ttl='1d')
    """

    # later: st.secrets.key
    headers = {'content-type': 'application/json', 
               'Authorization': 'Basic %s' %  'MjczMGYyMTQ0MDAxOThjZjlhN2Q1YjMwODkzNDBjNDI6YXBpX3Rva2Vu'}

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

    # Instead of a CSV on disk, you could read from an HTTP endpoint here too.
    DATA_FILENAME = Path(__file__).parent/'data/gdp_data.csv'
    raw_gdp_df = pd.read_csv(DATA_FILENAME)

    MIN_YEAR = 1960
    MAX_YEAR = 2022

    # The data above has columns like:
    # - Country Name
    # - Country Code
    # - [Stuff I don't care about]
    # - GDP for 1960
    # - GDP for 1961
    # - GDP for 1962
    # - ...
    # - GDP for 2022
    #
    # ...but I want this instead:
    # - Country Name
    # - Country Code
    # - Year
    # - GDP
    #
    # So let's pivot all those year-columns into two: Year and GDP
    gdp_df = raw_gdp_df.melt(
        ['Country Code'],
        [str(x) for x in range(MIN_YEAR, MAX_YEAR + 1)],
        'Year',
        'GDP',
    )

    # Convert years from string to integers
    gdp_df['Year'] = pd.to_numeric(gdp_df['Year'])

    return gdp_df,projects

gdp_df,projects = get_gdp_data()

# -----------------------------------------------------------------------------
# Draw the actual page

# Set the title that appears at the top of the page.
'''
# :clock2: Toggl dashboard

### All time history of Toggl projects:
'''

# Toggl chart
projects['color'] = [colors[i % num_colors] for i in range(len(projects))]

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

# Average hourly rate
all_time_rate = projects['fee_to_date'].sum() / projects['actual_hours'].sum()
print(all_time_rate)

# Update layout
fig.update_layout(
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

st.plotly_chart(fig, use_container_width=True)

# Add some spacing
''
'### Projects that are active or ended < 7 days ago '
recents = projects.loc[datetime.now() - projects['end_date'] < timedelta(days=7)].copy()
recents['Left'] = recents['actual_hours'].cumsum() - recents['actual_hours']
recents['color'] = [colors[i % num_colors] for i in range(len(recents))]

actives_fig = go.Figure()

# Create horizontal bar chart
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

# Average hourly rate
recent_rate = recents['fee_to_date'].sum() / recents['actual_hours'].sum()
print(recent_rate)

# Update layout
actives_fig.update_layout(
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

# Show the figure
st.plotly_chart(actives_fig, use_container_width=True)

# Old GDP charts
min_value = gdp_df['Year'].min()
max_value = gdp_df['Year'].max()

from_year, to_year = st.slider(
    'Which years are you interested in?',
    min_value=min_value,
    max_value=max_value,
    value=[min_value, max_value])

countries = gdp_df['Country Code'].unique()

if not len(countries):
    st.warning("Select at least one country")

selected_countries = st.multiselect(
    'Which countries would you like to view?',
    countries,
    ['DEU', 'FRA', 'GBR', 'BRA', 'MEX', 'JPN'])

''
''
''

# Filter the data
filtered_gdp_df = gdp_df[
    (gdp_df['Country Code'].isin(selected_countries))
    & (gdp_df['Year'] <= to_year)
    & (from_year <= gdp_df['Year'])
]

st.header('GDP over time', divider='gray')

''

st.line_chart(
    filtered_gdp_df,
    x='Year',
    y='GDP',
    color='Country Code',
)

''
''


first_year = gdp_df[gdp_df['Year'] == from_year]
last_year = gdp_df[gdp_df['Year'] == to_year]

st.header(f'GDP in {to_year}', divider='gray')

''

cols = st.columns(4)

for i, country in enumerate(selected_countries):
    col = cols[i % len(cols)]

    with col:
        first_gdp = first_year[first_year['Country Code'] == country]['GDP'].iat[0] / 1000000000
        last_gdp = last_year[last_year['Country Code'] == country]['GDP'].iat[0] / 1000000000

        if math.isnan(first_gdp):
            growth = 'n/a'
            delta_color = 'off'
        else:
            growth = f'{last_gdp / first_gdp:,.2f}x'
            delta_color = 'normal'

        st.metric(
            label=f'{country} GDP',
            value=f'{last_gdp:,.0f}B',
            delta=growth,
            delta_color=delta_color
        )

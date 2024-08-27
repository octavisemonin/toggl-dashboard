from datetime import datetime, timedelta
import plotly.graph_objects as go
import pandas as pd

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

def hovertext(row):
    f = f'Fee to date: ${row["fee_to_date"]:,.0f}'
    h = f'Hours: {row["Hours"]:.0f}'
    r = f'Effective rate: ${row["Effective $/hr"]:.0f}/hr'
    e = f'End date: {row["end_date"]}'
    
    return '<br>'.join([f,h,r,e])

def plot_projects(projects):

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

    # Toggl charts

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

    return (fig, all_time_rate), (actives_fig, recent_rate)
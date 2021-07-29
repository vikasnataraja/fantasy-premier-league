#!/usr/bin/env python
# coding: utf-8

import argparse
import os
import pandas as pd
import requests
import numpy as np
import matplotlib.pyplot as plt
import json
from matplotlib.gridspec import GridSpec
from time import perf_counter
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from PIL import Image
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon
import matplotlib
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica"]})

def get_position_player_data(data, json, drop_thresh=50):
    if json:
        player_df = pd.DataFrame(data['elements'])
    else:
        player_df = data
    selected_cols = ['id','first_name', 'second_name','web_name', 'element_type','team',
                     'now_cost','cost_change_start','total_points','points_per_game',
                     'selected_by_percent','value_season','minutes','photo','goals_scored',
                     'assists', 'clean_sheets', 'goals_conceded', 'own_goals',
                     'penalties_saved', 'penalties_missed', 'yellow_cards', 'red_cards',
                     'saves', 'bonus', 'bps', 'influence', 'creativity', 'threat', 'ict_index' ]
    player_df = player_df[selected_cols]
    player_df = player_df[player_df['total_points']>drop_thresh] # drop players who didn't get more than threshold
    player_df = player_df.reset_index(drop=True)
    player_df['now_cost'] = player_df['now_cost']/10. #cost is in 10s
    player_df['cost_change_start'] = player_df['cost_change_start']/10.
    player_df['avg_cost'] = (player_df['now_cost']*2 + player_df['cost_change_start'])/2
    pos_map = {1:"GK", 2:"DEF", 3:"MID", 4:"FWD"}
    
    team_ids = list(np.arange(1,21,1))
    team_names = ['Arsenal','Aston Villa','Brighton','Burnley','Chelsea','Crystal Palace',
                  'Everton','Fulham','Leicester City','Leeds United','Liverpool','Manchester City',
                  'Manchester Utd','Newcastle Utd','Sheffield Utd','Southampton','Tottenham',
                  'West Brom','West Ham','Wolves']
    team_map = dict(zip(team_ids, team_names))

    fpl_team_code_map = {'Arsenal': 3, 'Aston Villa': 7, 'Brighton': 36, 'Burnley': 90, 'Chelsea': 8,
                          'Crystal Palace': 31, 'Everton': 11, 'Fulham': 54, 'Leicester City': 13,
                          'Leeds United': 2, 'Liverpool': 14, 'Manchester City': 43, 'Manchester Utd': 1,
                          'Newcastle Utd': 4, 'Sheffield Utd': 49, 'Southampton': 20, 'Tottenham': 6,
                          'West Brom': 35, 'West Ham': 21, 'Wolves': 39}

    player_df['pos'] = player_df['element_type'].map(pos_map)
    player_df['team_name'] = player_df['team'].map(team_map)
    player_df['team_id'] = player_df['team_name'].map(fpl_team_code_map)
    player_df['team_id'] = player_df['team_id'].astype('int')
    player_df = player_df.drop(['team'], axis=1)
    
    gks = player_df[player_df['pos']=="GK"].reset_index(drop=True)
    defs = player_df[player_df['pos']=="DEF"].reset_index(drop=True)
    mids = player_df[player_df['pos']=="MID"].reset_index(drop=True)
    fwds = player_df[player_df['pos']=="FWD"].reset_index(drop=True)
    return gks, defs, mids, fwds


def top_value_players(df, top_n):
    df['points_per_million'] = np.round(df['total_points']/df['avg_cost'], 2)
    df = df.sort_values(['points_per_million']).tail(top_n).reset_index(drop=True)
    return df

def top_bonus_players(df, top_n):
    df = df.sort_values(['bonus']).tail(top_n).reset_index(drop=True)
    return df

def most_minutes_players(df, top_n):
    df = df.sort_values(['minutes']).tail(top_n).reset_index(drop=True)
    return df

def positive_price_change_players(df, top_n):
    df = df.sort_values(['cost_change_start']).tail(top_n).reset_index(drop=True)
    return df

def negative_price_change_players(df, top_n):
    df = df.sort_values(['cost_change_start']).head(top_n).reset_index(drop=True)
    return df

def add_pts_selection_history(all_players_df, num_participants):
    all_players_df['pts_history'] = ""
    all_players_df['select_percent_history'] = ""

    for i in range(len(all_players_df)):
        pid = all_players_df.loc[i, 'id']
        player_base_url = 'https://fantasy.premierleague.com/api/element-summary/{}/'.format(pid)
        player_history = requests.get(player_base_url).json()['history']
        pts_history = [player_history[idx]['total_points'] for idx in range(len(player_history))]
        select_percent_history = [round(player_history[idx]['selected']*100/num_participants, 2) for idx in range(len(player_history))]
        all_players_df.at[i, 'pts_history'] = pts_history
        all_players_df.at[i, 'select_percent_history'] = select_percent_history

    all_players_df['avg_points'] = all_players_df.apply(lambda row: round(np.mean(row.pts_history),2), axis=1)
    all_players_df['avg_ownership_pct'] = all_players_df.apply(lambda row:
                                                                   round(np.mean(row.select_percent_history),2), axis=1)
    return all_players_df

#### Top Points Per Million players ####
def plot_top_n(df, filename, title, offsets = [1.65, 1.9, 2.25]):
    fig = plt.figure(figsize=(36,20))
    plt.style.use(['ggplot'])
    gs = GridSpec(1, 1, figure=fig)
    ax = fig.add_subplot(gs[0, 0])
    ax.scatter(np.arange(0, len(df)), df['points_per_million'], c='ghostwhite')
    yticks = np.linspace(int(df['points_per_million'].min())-5, int(df['points_per_million'].max())+5, 4, dtype='int')

    for i in range(len(df)):
        img_url = 'https://resources.premierleague.com/premierleague/photos/players/110x140/p{}.png'.format(df.loc[i,'photo'].split('.')[0])
        img = Image.open(requests.get(img_url, stream=True).raw)
        img = img.resize((150,200))
        y_pos = df.loc[i, 'points_per_million']
        ax.add_artist(AnnotationBbox(OffsetImage(img), (i, y_pos), frameon=False))
        ax.text(i-0.25, y_pos+offsets[0], '$\it{}$'.format(df.loc[i,'web_name']), fontsize=20, weight="heavy")
        ax.text(i-0.1, y_pos-offsets[1], '£{:0.1f}m'.format(df.loc[i, 'avg_cost']), fontsize=20)
        ax.text(i-0.1, y_pos-offsets[2], '{}pts'.format(df.loc[i, 'total_points']), fontsize=20)

    ax.set_yticks(yticks)
    ax.set_yticklabels(yticks, fontsize=20)
    ax.set_xticks([])
    ax.set_yticks([])
    patches = []
    verts = [[-3,max(yticks)],[6,max(yticks)],[5,max(yticks)-2.5],[-3,max(yticks)-2.5]]
    polygon = Polygon(verts,closed=True)
    patches.append(polygon)
    collection = PatchCollection(patches)
    ax.add_collection(collection)
    collection.set_color('indigo')
    ax.text(-0.25, max(yticks)-1, 'Fantasy Premier League 2020/21', weight="bold", color="white", fontsize=52)
    ax.text(-0.25, max(yticks)-2, '{} - $\it{{Points \ Per \ Million*}}$'.format(title), color="white", weight="bold", fontsize=46)
    ax.text(8.4,min(yticks)+0.4,'$\it{Author: Vikas \ Nataraja}$', fontsize=16)
    ax.text(8.4,min(yticks)+0.1,'$\it{Data \ Source: Official \ FPL }$', fontsize=16)
    ax.text(-0.4,min(yticks)+0.1,'$\it{*average \ cost \ of \ player \ throughout \ season;\  min \ 50 \ pts}$', fontsize=16)
    ax.set_facecolor('ghostwhite')
    fig.savefig('{}.png'.format(filename), dpi=100, bbox_inches = 'tight', pad_inches = 0)
    plt.show();


#### Top Bonus Points ####

def plot_top_bonus(df, filename, offsets = [2.75, 3.1, 3.85]):
    fig = plt.figure(figsize=(36,20))
    plt.style.use(['ggplot'])
    gs = GridSpec(1, 1, figure=fig)
    ax = fig.add_subplot(gs[0, 0])
    ax.scatter(np.arange(0, len(df)), df['bonus'], c='ghostwhite')
    yticks = np.linspace(int(df['bonus'].min())-5, int(df['bonus'].max())+5, 5, dtype='int')

    for i in range(len(df)):
        img_url = 'https://resources.premierleague.com/premierleague/photos/players/110x140/p{}.png'.format(df.loc[i,'photo'].split('.')[0])
        img = Image.open(requests.get(img_url, stream=True).raw)
        img = img.resize((150,200))
        y_pos = df.loc[i, 'bonus']
        ax.add_artist(AnnotationBbox(OffsetImage(img), (i, y_pos), frameon=False))
        ax.text(i-0.25, y_pos+offsets[0], '$\it{}$'.format(df.loc[i,'web_name']), fontsize=20, weight="heavy")
        ax.text(i-0.3, y_pos-offsets[1], '{} bonus pts'.format(df.loc[i, 'bonus']), fontsize=20)
        ax.text(i-0.3, y_pos-offsets[2], '{} total pts'.format(df.loc[i, 'total_points']), fontsize=20)

    ax.set_yticks(yticks)
    ax.set_yticklabels(yticks, fontsize=20)
    ax.set_xticks([])
    ax.set_yticks([])
    patches = []
    verts = [[-3,max(yticks)],[6,max(yticks)],[5,max(yticks)-3.5],[-3,max(yticks)-3.5]]
    polygon = Polygon(verts,closed=True)
    patches.append(polygon)
    collection = PatchCollection(patches)
    ax.add_collection(collection)
    collection.set_color('indigo')
    ax.text(-0.25, max(yticks)-1.5, 'Fantasy Premier League 2020/21', weight="bold", color="white", fontsize=52)
    ax.text(-0.25, max(yticks)-3, '$\it{{Most \ Bonus \ Points}}$', color="white", weight="bold", fontsize=46)
    ax.text(8.4,min(yticks)+0.6,'$\it{Author: Vikas \ Nataraja}$', fontsize=16)
    ax.text(8.4,min(yticks)+0.2,'$\it{Data \ Source: Official \ FPL }$', fontsize=16)
    ax.text(-0.4,min(yticks)+0.2,'$\it{*min \ 50 \ total \ pts}$', fontsize=16)
    ax.set_facecolor('ghostwhite')
    fig.savefig('{}.png'.format(filename), dpi=100, bbox_inches = 'tight', pad_inches = 0)
    plt.show();


#### Most Minutes Played ####

def plot_most_minutes(df, filename, offsets = [15.25, 18.5, 22]):
    fig = plt.figure(figsize=(36,20))
    plt.style.use(['ggplot'])
    gs = GridSpec(1, 1, figure=fig)
    ax = fig.add_subplot(gs[0, 0])
    ax.scatter(np.arange(0, len(df)), df['minutes'], c='ghostwhite')
    yticks = [3300, 3350, 3400, 3450, 3460]

    for i in range(len(df)):
        img_url = 'https://resources.premierleague.com/premierleague/photos/players/110x140/p{}.png'.format(df.loc[i,'photo'].split('.')[0])
        img = Image.open(requests.get(img_url, stream=True).raw)
        img = img.resize((150,200))
        y_pos = df.loc[i, 'minutes']
        ax.add_artist(AnnotationBbox(OffsetImage(img), (i, y_pos), frameon=False))
        ax.text(i-0.25, y_pos+offsets[0], '$\it{}$'.format(df.loc[i,'web_name']), fontsize=20, weight="heavy")
        ax.text(i-0.3, y_pos-offsets[1], '{} min'.format(df.loc[i, 'minutes']), fontsize=20)
        ax.text(i-0.3, y_pos-offsets[2], '{} total pts'.format(df.loc[i, 'total_points']), fontsize=20)

    ax.set_yticks(yticks)
    ax.set_yticklabels(yticks, fontsize=20)
    ax.set_xticks([])
    ax.set_yticks([])
    patches = []
    verts = [[-3,max(yticks)],[6,max(yticks)],[5,max(yticks)-18],[-3,max(yticks)-18]]
    polygon = Polygon(verts,closed=True)
    patches.append(polygon)
    collection = PatchCollection(patches)
    ax.add_collection(collection)
    collection.set_color('indigo')
    ax.text(-0.25, max(yticks)-8, 'Fantasy Premier League 2020/21', weight="bold", color="white", fontsize=52)
    ax.text(-0.25, max(yticks)-16, '$\it{{Most \ Minutes \ Played \ By \ Outfield \ Players}}$', color="white", weight="bold", fontsize=46)
    ax.text(8.4,min(yticks)+4.6,'$\it{Author: Vikas \ Nataraja}$', fontsize=16)
    ax.text(8.4,min(yticks)+1.2,'$\it{Data \ Source: Official \ FPL }$', fontsize=16)
    ax.text(-0.4,min(yticks)+1.2,'$\it{*min \ 50 \ total \ pts}$', fontsize=16)
    ax.set_facecolor('ghostwhite')
    fig.savefig('{}.png'.format(filename), dpi=100, bbox_inches = 'tight', pad_inches = 0)
    plt.show();

#### Biggest Price Swings ####
def plot_price_swings(df, filename, offsets = [0.45, 0.5, 0.6]):
    fig = plt.figure(figsize=(36,20))
    plt.style.use(['ggplot'])
    gs = GridSpec(1, 1, figure=fig)
    ax = fig.add_subplot(gs[0, 0])
    ax.scatter(np.arange(0, len(df)), df['cost_change_start'], c='ghostwhite')
    yticks = [-1.8, -1.5, 1.0, 0, 1.0, 1.5, 2.0, 2.5]
    ax.plot([0,10], [0,0], linestyle='--', c='black')

    for i in range(len(df)):
        img_url = 'https://resources.premierleague.com/premierleague/photos/players/110x140/p{}.png'.format(df.loc[i,'photo'].split('.')[0])
        img = Image.open(requests.get(img_url, stream=True).raw)
        img = img.resize((150,200))
        y_pos = df.loc[i, 'cost_change_start']
        ax.add_artist(AnnotationBbox(OffsetImage(img), (i, y_pos), frameon=False))
        ax.text(i-0.25, y_pos+offsets[0], '$\it{}$'.format(df.loc[i,'web_name']), fontsize=20, weight="heavy")
        ax.text(i-0.3, y_pos-offsets[1], 'Started £{}m'.format(df.loc[i, 'now_cost']-df.loc[i, 'cost_change_start']), fontsize=20)
        if df.loc[i, 'cost_change_start'] > 0:
            plt_color = 'limegreen'
        else:
            plt_color='red'
        ax.text(i-0.3, y_pos-offsets[2], 'Ended £{}m'.format(df.loc[i, 'now_cost']), color=plt_color, fontsize=20)

    ax.set_yticks(yticks)
    ax.set_yticklabels(yticks, fontsize=20)
    ax.set_xticks([])
    ax.set_yticks([])
    patches = []
    verts = [[-3,max(yticks)],[6,max(yticks)],[5,max(yticks)-0.65],[-3,max(yticks)-0.65]]
    polygon = Polygon(verts,closed=True)
    patches.append(polygon)
    collection = PatchCollection(patches)
    ax.add_collection(collection)
    collection.set_color('indigo')
    ax.text(-0.25, max(yticks)-0.25, 'Fantasy Premier League 2020/21', weight="bold", color="white", fontsize=52)
    ax.text(-0.25, max(yticks)-0.5, '$\it{{Biggest \ Price \ Swings}}$', color="white", weight="bold", fontsize=46)
    ax.text(8.4,min(yticks)+0.2,'$\it{Author: Vikas \ Nataraja}$', fontsize=16)
    ax.text(8.4,min(yticks)+0.1,'$\it{Data \ Source: Official \ FPL }$', fontsize=16)
    ax.text(-0.4,min(yticks)+0.1,'$\it{*min \ 50 \ total \ pts}$', fontsize=16)
    ax.set_facecolor('ghostwhite')
    fig.savefig('{}.png'.format(filename), dpi=100, bbox_inches = 'tight', pad_inches = 0)
    plt.show();


#### Popularity vs Performance ####

def plot_popularity_performance(df, top_n):
    df = all_players_df.sort_values(['avg_ownership_pct']).tail(top_n).reset_index(drop=True)
    fig = plt.figure(figsize=(36,20))
    plt.style.use(['ggplot'])
    gs = GridSpec(1, 1, figure=fig)
    ax = fig.add_subplot(gs[0, 0])
    yticks = [15, 35, 80]
    xticks = list(np.linspace(df['avg_points'].min()-0.25, df['avg_points'].max()+0.25, len(df)))
    offsets = [4.8, 3, 1.8]
    ax.scatter(xticks, df['avg_ownership_pct'], c='ghostwhite')

    for i, x_pos in enumerate(df['avg_points']):
        img_url = 'https://resources.premierleague.com/premierleague/photos/players/110x140/p{}.png'.format(df.loc[i,'photo'].split('.')[0])
        img = Image.open(requests.get(img_url, stream=True).raw)
        img = img.resize((150,200))
        y_pos = df.loc[i, 'avg_ownership_pct']*1.3
        ax.add_artist(AnnotationBbox(OffsetImage(img), (x_pos, y_pos), frameon=False))
        if df.loc[i, 'web_name'] in ['Kane', 'Fernandes']:
            ax.text(x_pos+0.15, y_pos+offsets[0]-1, '$\it{}$'.format(df.loc[i,'web_name']), fontsize=20, weight="heavy", wrap=True)
            ax.text(x_pos+0.15, y_pos+offsets[1]-1, '{}% sel '.format(df.loc[i, 'avg_ownership_pct']), fontsize=20, wrap=True)
            ax.text(x_pos+0.15, y_pos+offsets[2]-1, '{}pts/game '.format(df.loc[i, 'avg_points']), fontsize=20, wrap=True)
        else:
            ax.text(x_pos-0.2, y_pos+offsets[0], '$\it{}$'.format(df.loc[i,'web_name']), fontsize=20, weight="heavy", wrap=True)
            ax.text(x_pos-0.3, y_pos+offsets[1], '{}% sel '.format(df.loc[i, 'avg_ownership_pct']), fontsize=20, wrap=True)
            ax.text(x_pos-0.3, y_pos+offsets[2], '{}pts/game '.format(df.loc[i, 'avg_points']), fontsize=20, wrap=True)

    ax.set_xticks(xticks)
    ax.set_yticks(yticks)
    ax.set_yticklabels(yticks, fontsize=20)
    ax.set_xticks([])
    ax.set_yticks([])
    patches = []
    verts = [[-3,max(yticks)],[6,max(yticks)],[5.5,max(yticks)-9.25],[-3,max(yticks)-9.25]]
    polygon = Polygon(verts,closed=True)
    patches.append(polygon)
    collection = PatchCollection(patches)
    ax.add_collection(collection)
    collection.set_color('indigo')
    ax.text(3.25, max(yticks)-4, 'Fantasy Premier League 2020/21', weight="bold", color="white", fontsize=52)
    ax.text(3.25, max(yticks)-8, '$\it{{Popularity \ vs \ Performance*}}$', color="white", weight="bold", fontsize=46)
    ax.text(6.4,min(yticks)+2,'$\it{Author: Vikas \ Nataraja}$', fontsize=16)
    ax.text(6.4,min(yticks)+1,'$\it{Data \ Source: Official \ FPL }$', fontsize=16)
    ax.text(3.25,min(yticks)+1,'$\it{*min \ 50 \ total \ pts; \ average \ ownership \ and \ pts \ over \ entire \ season}$', fontsize=16)
    ax.set_facecolor('ghostwhite')
    fig.savefig('popularity_vs_performance.png', dpi=100, bbox_inches = 'tight', pad_inches = 0)
    plt.show();


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--plot', default=None, type=str, help="Metric to plot")
    parser.add_argument('--top_n', default=10, type=int, help="Top N players to plot")
    parser.add_argument('--min_pts', default=0, type=int, help="Threshold for points. \
                        Players who scored fewer than `min_thresh` will not be considered")
    args = parser.parse_args()

    url = 'https://fantasy.premierleague.com/api/bootstrap-static/'
    r = requests.get(url)
    json_data = r.json()
    gks, defs, mids, fwds = get_position_player_data(json_data, json=True, drop_thresh=args.min_pts)
    all_players_df = pd.concat([gks, defs, mids, fwds], axis=0).reset_index(drop=True)
    names = ['Alexander-Arnold','Wan-Bissaka','Walker-Peters','Maitland-Niles','Hudson-Odoi',
         'Loftus-Cheek','Saint-Maximin','Ward-Prowse','Calvert-Lewin','Decordova-Reid',
         'Peacock-Farrell', 'Philogene-Bidace','Poveda-Ocampo','Robson-Kanu','Gibbs-White']
    replace_names = ['TAA','AWB','KWP','Niles','CHO','RLC','ASM','JWP','DCL','Reid',
                    'Farrell','Bidace','Poveda','Kanu','MGW']
    replace_dict = dict(zip(names, replace_names))
    # replace large names with shorter ones
    for count, name in enumerate(all_players_df['web_name']):
        if name in names:
            all_players_df.at[count,'web_name'] = replace_dict[name]

    if args.plot == "price_swing":
        df = pd.concat([negative_price_change_players(all_players_df, 5), positive_price_change_players(all_players_df, 5)], axis=0).reset_index(drop=True)
        plot_price_swings(df, 'price_swings')

    if args.plot == "top_position":
        top_gks = top_value_players(gks, args.top_n)
        top_defs = top_value_players(defs, args.top_n)
        top_mids = top_value_players(mids, args.top_n)
        top_fwds = top_value_players(fwds, args.top_n)

        plot_top_n(top_mids, filename="best_value_mid", title="Best Value Midfielders")
        plot_top_n(top_defs, filename="best_value_def", title="Best Value Defenders", offsets = [1.55, 1.65, 1.95])
        plot_top_n(top_gks, filename='best_value_gks', title='Best Value Goalkeepers')
        plot_top_n(top_fwds, filename='best_value_fwds', title='Best Value Forwards', offsets = [1.75, 2.05, 2.45])

    if args.plot == "top_bonus":
        df = top_bonus_players(all_players_df, args.top_n)
        plot_top_bonus(df, 'most_bonus_pts')

    if args.plot == "most_minutes":
        df = most_minutes_players(all_players_df, args.top_n)
        plot_most_minutes(df, 'most_minutes_played')

    if args.plot == "popularity":
        total_participants = json_data['total_players']
        df = add_pts_selection_history(all_players_df, total_participants)
        plot_popularity_performance(df, args.top_n)

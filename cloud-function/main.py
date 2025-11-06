# -*- coding: utf-8 -*-
"""Rugby Team Allocator - Cloud Function

HTTP-triggered Cloud Function for team allocation.
Accepts JSON payload from Google Apps Script and returns team assignments.
"""

import functions_framework
from flask import Request
import pandas as pd
from collections import defaultdict
import math
import json
import logging

# --- Team Allocation Rules ---
MIN_TEAM_SIZE = 7
MAX_TEAM_SIZE = 9
IDEAL_TEAM_SIZE = 8

# --- Coach Pairing Configuration ---
COACH_PAIRINGS = [
    # ('Coach A', 'Coach B'),
]


def preprocess_data(df):
    """Cleans and prepares player data, ensuring all required columns exist."""
    df.columns = [str(col).strip().lower().replace(' ', '_') for col in df.columns]
    required_cols = {
        'key': '', 'available': 0, 'istentpole': False,
        'pairedwith': '', 'tier': 2, 'coach': '', 'pod': 'Unknown'
    }
    for col, default_val in required_cols.items():
        if col not in df.columns:
            logging.warning(f"Column '{col}' not found. Creating it with default values.")
            df[col] = default_val

    df.fillna({
        'key': '', 'available': 0, 'istentpole': False,
        'pairedwith': '', 'tier': 2, 'coach': '', 'pod': 'Unknown'
    }, inplace=True)

    df['key'] = df['key'].astype(str).str.strip()
    df = df[df['key'] != ''].copy()
    df['available'] = pd.to_numeric(df['available'], errors='coerce').fillna(0).astype(int)
    available_players_df = df[df['available'] == 1].copy()

    available_players_df['istentpole'] = available_players_df['istentpole'].apply(
        lambda x: str(x).strip().upper() == 'TRUE'
    )
    available_players_df['pairedwith'] = available_players_df['pairedwith'].astype(str).str.strip()
    available_players_df['coach'] = available_players_df['coach'].astype(str).str.strip()
    available_players_df['tier'] = pd.to_numeric(available_players_df['tier'], errors='coerce').fillna(2).astype(int)
    available_players_df['pod'] = available_players_df['pod'].astype(str).str.strip()

    return df, available_players_df


def create_allocation_groups(df):
    """Identifies social/coach pairings and creates allocation groups with aggregated attributes."""
    parent = {key: key for key in df['key']}
    
    def find(key):
        if parent[key] == key: 
            return key
        parent[key] = find(parent[key])
        return parent[key]
    
    def union(key1, key2):
        root1, root2 = find(key1), find(key2)
        if root1 != root2: 
            parent[root2] = root1

    key_map = {name.lower(): key for name, key in zip(df['key'], df['key'])}
    for _, row in df.iterrows():
        if row['pairedwith']:
            partner_key = key_map.get(str(row['pairedwith']).lower())
            if partner_key and partner_key in parent:
                union(row['key'], partner_key)

    coach_to_kids = defaultdict(list)
    for _, row in df.iterrows():
        if row['coach']:
            coach_to_kids[row['coach']].append(row['key'])
    for coach1, coach2 in COACH_PAIRINGS:
        kids1, kids2 = coach_to_kids.get(coach1), coach_to_kids.get(coach2)
        if kids1 and kids2:
            anchor = kids1[0]
            for kid in kids1[1:] + kids2:
                union(anchor, kid)

    social_groups = defaultdict(list)
    for key in df['key']:
        social_groups[find(key)].append(key)

    player_info = df.set_index('key')
    groups = []
    for player_keys in social_groups.values():
        group_pods = player_info.loc[player_keys]['pod']
        composition = group_pods.value_counts().to_dict()

        # Determine the primary color of the group for initial placement
        primary_pod = group_pods.mode()[0] if not group_pods.empty else 'Unknown'

        groups.append({
            'keys': player_keys,
            'size': len(player_keys),
            'is_tentpole_group': any(player_info.loc[key]['istentpole'] for key in player_keys),
            'composition': composition,
            'primary_pod': primary_pod,
            'has_green': 'Green' in composition
        })
    return groups


def allocate_teams_stratified(groups, df_available):
    """Performs the new, constraint-aware preferential assignment of groups to teams."""
    assignments = {}

    # --- Phase 1 & 2: Foundation and Depth ---
    # Determine team structure
    red_players = sum(g['composition'].get('Red', 0) for g in groups)
    blue_players = sum(g['composition'].get('Blue', 0) for g in groups)
    num_red_teams = math.ceil(red_players / IDEAL_TEAM_SIZE) if red_players > 0 else 0
    num_blue_teams = math.ceil(blue_players / IDEAL_TEAM_SIZE) if blue_players > 0 else 0

    teams = {}
    for i in range(num_red_teams): 
        teams[f"Red Team {i+1}"] = {'color': 'Red'}
    for i in range(num_blue_teams): 
        teams[f"Blue Team {i+1}"] = {'color': 'Blue'}

    # Initialize team stats
    for name in teams:
        teams[name].update({'size': 0, 'red_count': 0, 'green_count': 0, 'pink_count': 0, 'groups': []})

    # Assign core Red/Blue groups
    unassigned_groups = []
    red_blue_groups = sorted([g for g in groups if g['primary_pod'] in ['Red', 'Blue']], key=lambda x: -x['size'])

    for group in red_blue_groups:
        target_color = group['primary_pod']
        potential_teams = [name for name, stats in teams.items() 
                          if stats['color'] == target_color and stats['size'] + group['size'] <= MAX_TEAM_SIZE]

        if potential_teams:
            best_team = min(potential_teams, key=lambda name: teams[name]['size'])
            teams[best_team]['size'] += group['size']
            teams[best_team]['groups'].append(group)
            for key in group['keys']: 
                assignments[key] = best_team
        else:
            unassigned_groups.append(group)

    # --- Phase 3: Strategic Filler Distribution ---
    filler_groups = unassigned_groups + [g for g in groups if g['primary_pod'] not in ['Red', 'Blue']]

    # Update team stats after initial placement
    for name, stats in teams.items():
        stats['red_count'] = sum(g['composition'].get('Red', 0) for g in stats['groups'])
        stats['green_count'] = sum(g['composition'].get('Green', 0) for g in stats['groups'])
        stats['pink_count'] = sum(g['composition'].get('Pink', 0) for g in stats['groups'])

    # Stage 3A: Targeted Green Distribution
    green_groups = sorted([g for g in filler_groups if g['has_green']], key=lambda x: -x['size'])
    relaxation_pool = []

    for group in green_groups:
        group_green_count = group['composition'].get('Green', 0)
        potential_teams = []
        for name, stats in teams.items():
            # Hard Constraint Check
            if (stats['size'] + group['size'] <= MAX_TEAM_SIZE) and \
               (stats['green_count'] + group_green_count <= 4):
                potential_teams.append(name)

        if potential_teams:
            # Preference Ranking
            best_team = sorted(potential_teams, key=lambda name: (-teams[name]['red_count'], teams[name]['size']))[0]
            # Assign and update
            teams[best_team]['size'] += group['size']
            teams[best_team]['green_count'] += group_green_count
            teams[best_team]['red_count'] += group['composition'].get('Red', 0)
            for key in group['keys']: 
                assignments[key] = best_team
        else:
            relaxation_pool.append(group)

    # Stage 3B: Constraint Relaxation
    for group in sorted(relaxation_pool, key=lambda x: -x['size']):
        group_green_count = group['composition'].get('Green', 0)
        potential_teams = [name for name, stats in teams.items() 
                          if stats['size'] + group['size'] <= MAX_TEAM_SIZE]

        if potential_teams:
            # Minimization Ranking
            best_team = sorted(potential_teams, key=lambda name: (teams[name]['green_count'], -teams[name]['red_count'], teams[name]['size']))[0]
            teams[best_team]['size'] += group['size']
            teams[best_team]['green_count'] += group_green_count
            teams[best_team]['red_count'] += group['composition'].get('Red', 0)
            for key in group['keys']: 
                assignments[key] = best_team
            logging.warning(f"Tenure constraint violated. Assigned group {group['keys']} to {best_team}, which now has {teams[best_team]['green_count']} green players.")
        else:
            logging.error(f"Could not place group {group['keys']} even after relaxing constraints.")

    # Stage 3C: Remaining Filler Distribution
    remaining_fillers = [g for g in filler_groups if not g['has_green'] and all(k not in assignments for k in g['keys'])]
    for group in sorted(remaining_fillers, key=lambda x: -x['size']):
        potential_teams = [name for name, stats in teams.items() 
                         if stats['size'] + group['size'] <= MAX_TEAM_SIZE]
        if potential_teams:
            # Preference Ranking
            best_team = sorted(potential_teams, key=lambda name: (teams[name]['pink_count'], teams[name]['size'], teams[name]['color'] != 'Red'))[0]
            teams[best_team]['size'] += group['size']
            teams[best_team]['pink_count'] += group['composition'].get('Pink', 0)
            for key in group['keys']: 
                assignments[key] = best_team
        else:
            logging.error(f"Could not place remaining filler group {group['keys']}.")

    return assignments


@functions_framework.http
def team_allocation(request: Request):
    """
    HTTP-triggered Cloud Function for rugby team allocation.
    
    Expected JSON payload:
    {
        "players": [
            {
                "key": "Player Name",
                "available": 1,
                "istentpole": false,
                "pairedwith": "",
                "tier": 2,
                "coach": "",
                "pod": "Red"
            },
            ...
        ]
    }
    
    Returns JSON response with team assignments.
    """
    if request.method != 'POST':
        return {'error': 'Method not allowed. Use POST.'}, 405
    
    try:
        # Parse JSON payload
        data = request.get_json()
        if not data:
            return {'error': 'No JSON payload provided'}, 400
        
        players = data.get('players', [])
        if not players:
            return {'error': 'No players data provided'}, 400
        
        logging.info(f'Processing {len(players)} players')
        
        # Convert to DataFrame
        df_original = pd.DataFrame(players)
        
        # Preprocess data
        df_all_players, df_available = preprocess_data(df_original.copy())
        
        if df_available.empty:
            return {
                'success': False,
                'error': 'No available players to sort',
                'data': []
            }, 200
        
        logging.info(f'Processing {len(df_available)} available players')
        
        # Phase 0: Create Groups
        allocation_groups = create_allocation_groups(df_available)
        
        # Allocate teams
        assignments = allocate_teams_stratified(allocation_groups, df_available)
        
        # Prepare response
        results = []
        for _, row in df_all_players.iterrows():
            player_key = row['key']
            assignment = assignments.get(player_key, 'Not Assigned')
            results.append({
                'key': player_key,
                'team': assignment,
                'available': int(row['available']),
                'pod': str(row['pod']),
                'tier': int(row['tier'])
            })
        
        return {
            'success': True,
            'data': {
                'allocations': results,
                'total_players': len(df_all_players),
                'available_players': len(df_available),
                'assigned_players': len([r for r in results if r['team'] != 'Not Assigned'])
            }
        }, 200
        
    except Exception as e:
        logging.error(f'Error processing team allocation: {str(e)}', exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }, 500


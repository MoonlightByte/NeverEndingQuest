#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Plot Formatting Module
Formats plot data (the module_plot.json shape, with statuses from the rules
engine's quest record: utils/quest_record.module_plot) into readable text for
the AI DM.
"""


def _sq_lines(point, status, label):
    out = ""
    quests = [sq for sq in point.get('sideQuests', []) or [] if isinstance(sq, dict) and sq.get('status') == status]
    if quests:
        out += f"  - {label}:\n"
        for sq in quests:
            out += f"    * {sq.get('title', 'Untitled')} ({sq.get('id', 'Unknown')})\n"
    return out


def _at(point):
    """The area a plot point is located in, as " @<id>" (C3: told here only)."""
    location = point.get('location') if isinstance(point, dict) else None
    return f" @{location}" if location else ""


def _requires(point, titles):
    if point.get('open'):
        return "  - Still requires: " + ", ".join(
            f"{x} ({titles.get(x, 'Unknown')})" for x in point['open']) + "\n"
    return ""


def format_plot_for_ai(plot_data):
    """
    Format plot data into readable text for AI DM

    Args:
        plot_data (dict): The plot data (module_plot.json shape; the engine's
            statuses, with open requirements and ahead completions)

    Returns:
        str: Formatted plot status text for AI consumption
    """
    # Handle case where plot_data might be a list or other non-dict type
    if not isinstance(plot_data, dict):
        print(f"WARNING: plot_data is not a dict, it's a {type(plot_data)}: {plot_data}")
        return "=== ADVENTURE PLOT STATUS ===\n\nNo plot data available.\n"

    if not plot_data or 'plotPoints' not in plot_data:
        return "=== ADVENTURE PLOT STATUS ===\n\nNo plot data available.\n"

    points = [p for p in plot_data['plotPoints'] if isinstance(p, dict)]
    titles = {p.get('id'): p.get('title', 'Untitled') for p in points}

    # Header
    output = "=== ADVENTURE PLOT STATUS ===\n\n"
    output += f"ADVENTURE: {plot_data.get('plotTitle', 'Unknown Adventure')}\n"
    output += f"MAIN GOAL: {plot_data.get('mainObjective', 'No objective defined')}\n"
    output += "(Quest statuses are the rules engine's record. Change one only with updatePlot, by its id.)\n\n"

    # Story Progress
    output += "STORY PROGRESS:\n"

    # Separate plot points by status
    completed_points = [p for p in points if p.get('status') == 'completed']
    failed_points = [p for p in points if p.get('status') == 'failed']
    active_points = [p for p in points if p.get('status') == 'in progress']
    bypassed_points = [p for p in points if p.get('status') == 'not started' and p.get('bypassed')]
    upcoming_points = [p for p in points if p.get('status') == 'not started' and not p.get('bypassed')]

    # Completed plot points
    for point in completed_points:
        output += f"[COMPLETED]: {point.get('title', 'Untitled')} ({point.get('id', 'Unknown')}){_at(point)}\n"
        output += f"  - {point.get('description', 'No description')}\n"
        if point.get('plotImpact'):
            output += f"  - Impact: {point['plotImpact']}\n"
        if point.get('aheadOf'):
            reason = point.get('aheadReason') or ''
            output += f"  - Completed ahead of: {', '.join(str(x) for x in point['aheadOf'])}"
            output += f" ({reason})\n" if reason else "\n"
        output += _sq_lines(point, 'completed', "Side quests completed")
        output += "\n"

    # Failed plot points
    for point in failed_points:
        output += f"[FAILED]: {point.get('title', 'Untitled')} ({point.get('id', 'Unknown')}){_at(point)}\n"
        output += f"  - {point.get('description', 'No description')}\n"
        if point.get('plotImpact'):
            output += f"  - Outcome: {point['plotImpact']}\n"
        output += "\n"

    # Active plot points
    # Bypassed plot points: the party finished later work by another route
    for point in bypassed_points:
        output += f"[BYPASSED]: {point.get('title', 'Untitled')} ({point.get('id', 'Unknown')}){_at(point)}\n"
        output += f"  - {point.get('description', 'No description')}\n"
        output += "  - Bypassed by: " + ", ".join(
            f"{x} ({titles.get(x, 'Unknown')})" for x in point.get('bypassedBy') or []) + "\n"
        output += "  - Not an objective: the party went another way. It becomes active only if the party takes it up.\n"
        output += "\n"

    for point in active_points:
        output += f"[ACTIVE]: {point.get('title', 'Untitled')} ({point.get('id', 'Unknown')}){_at(point)}\n"
        output += f"  - {point.get('description', 'No description')}\n"
        if point.get('plotImpact'):
            output += f"  - Current situation: {point['plotImpact']}\n"
        output += _requires(point, titles)
        output += _sq_lines(point, 'in progress', "Side quests in progress")
        output += _sq_lines(point, 'not started', "Side quests not started")
        output += _sq_lines(point, 'completed', "Side quests completed")
        output += _sq_lines(point, 'failed', "Side quests failed")
        output += "\n"

    # Upcoming objectives (C3: with their area, open requirements and side
    # quests, so the DM Note need not repeat them)
    if upcoming_points:
        output += "UPCOMING OBJECTIVES:\n"
        for point in upcoming_points:
            output += f"- {point.get('title', 'Untitled')} ({point.get('id', 'Unknown')}){_at(point)}: {point.get('description', 'No description')}\n"
            output += _requires(point, titles)
            output += _sq_lines(point, 'in progress', "Side quests in progress")
            output += _sq_lines(point, 'not started', "Side quests not started")
        output += "\n"

    return output


def format_plot_for_location(plot_data, current_location_id):
    """
    Format plot data with focus on current location context

    Args:
        plot_data (dict): The plot data from module_plot.json
        current_location_id (str): The current area/location ID

    Returns:
        str: Formatted plot status with location context
    """
    base_format = format_plot_for_ai(plot_data)

    if not current_location_id or not plot_data or 'plotPoints' not in plot_data:
        return base_format

    # Find plot points relevant to current location
    current_plot_points = []
    for point in plot_data['plotPoints']:
        if point.get('location') == current_location_id and point.get('status') not in ('completed', 'failed'):
            current_plot_points.append(point)

    if current_plot_points:
        base_format += "CURRENT LOCATION CONTEXT:\n"
        base_format += f"The party is currently at location {current_location_id} where they can:\n"

        for point in current_plot_points:
            base_format += f"- Work on: {point.get('title', 'Untitled')} - {point.get('description', 'No description')}\n"

            # Add active side quests for this location
            active_sqs = [sq for sq in point.get('sideQuests', []) if sq.get('status') in ['not started', 'in progress']]
            for sq in active_sqs:
                if current_location_id in sq.get('involvedLocations', []):
                    base_format += f"  * Side quest: {sq.get('title', 'Untitled')}\n"

        base_format += "\n"

    return base_format

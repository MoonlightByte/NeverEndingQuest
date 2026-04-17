# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

from datetime import datetime

def get_time_context(time_str):
    """
    Convert a time string (HH:MM:SS) to a contextual description.
    
    Args:
        time_str: Time in format "HH:MM:SS"
        
    Returns:
        A string describing the time of day (e.g., "early morning", "late afternoon")
    """
    try:
        time_obj = datetime.strptime(time_str, "%H:%M:%S")
        hour = time_obj.hour
        
        # Define time periods based on hour
        if 0 <= hour < 4:
            return "deep night"
        elif 4 <= hour < 6:
            return "pre-dawn"
        elif 6 <= hour < 8:
            return "early morning"
        elif 8 <= hour < 10:
            return "morning"
        elif 10 <= hour < 12:
            return "late morning"
        elif hour == 12:
            return "noon"
        elif 12 < hour < 14:
            return "early afternoon"
        elif 14 <= hour < 17:
            return "afternoon"
        elif 17 <= hour < 19:
            return "late afternoon"
        elif 19 <= hour < 21:
            return "evening"
        elif 21 <= hour < 23:
            return "night"
        else:  # 23
            return "late night"
            
    except ValueError:
        return "unknown time"

def format_time_with_context(world_conditions):
    """
    Format world conditions time data with contextual information.
    
    Args:
        world_conditions: Dictionary containing year, month, day, time
        
    Returns:
        Formatted string with date, time, and context
    """
    year = world_conditions.get('year', 1492)
    month = world_conditions.get('month', 'Unknown')
    day = world_conditions.get('day', 1)
    time_str = world_conditions.get('time', '00:00:00')
    
    context = get_time_context(time_str)
    
    # Format: "1492 Springmonth 15, 10:30 AM (late morning)"
    try:
        time_obj = datetime.strptime(time_str, "%H:%M:%S")
        formatted_time = time_obj.strftime("%I:%M %p").lstrip('0')  # 12-hour format
        return f"{year} {month} {day}, {formatted_time} ({context})"
    except ValueError:
        return f"{year} {month} {day}, {time_str} ({context})"
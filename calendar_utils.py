from icalendar import Calendar, Event
import pandas as pd
from datetime import datetime, timedelta
import pytz
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define EST timezone
EST = pytz.timezone('America/New_York')

def parse_ics(file):
    """Parse .ics file and return list of events with EST timezone"""
    try:
        calendar = Calendar.from_ical(file.read())
        events = []

        for component in calendar.walk():
            if component.name == "VEVENT":
                try:
                    # Safely get start and end times
                    start_time = component.get('dtstart')
                    end_time = component.get('dtend')

                    # Skip events without proper start/end times
                    if not start_time or not end_time:
                        logger.warning(f"Skipping event due to missing time: {component.get('summary')}")
                        continue

                    start = start_time.dt
                    end = end_time.dt

                    # Convert datetime to EST
                    if isinstance(start, datetime):
                        if start.tzinfo is None:
                            start = pytz.UTC.localize(start)
                        start = start.astimezone(EST)
                    else:
                        # If it's a date, convert to datetime at start of day
                        start = datetime.combine(start, datetime.min.time())
                        start = EST.localize(start)

                    if isinstance(end, datetime):
                        if end.tzinfo is None:
                            end = pytz.UTC.localize(end)
                        end = end.astimezone(EST)
                    else:
                        # If it's a date, convert to datetime at end of day
                        end = datetime.combine(end, datetime.max.time())
                        end = EST.localize(end)

                    events.append({
                        'summary': str(component.get('summary', 'No Title')),
                        'start': start,
                        'end': end
                    })
                    logger.info(f"Parsed event: {start} - {end} ({component.get('summary')})")
                except AttributeError as e:
                    logger.warning(f"Skipping malformed event: {str(e)}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing event: {str(e)}")
                    continue

        if not events:
            logger.warning("No valid events found in calendar file")

        return events
    except Exception as e:
        logger.error(f"Error parsing calendar file: {str(e)}")
        raise ValueError(f"Could not parse calendar file: {str(e)}")

def get_calendar_preview(slots):
    """Convert slots to pandas DataFrame for display"""
    preview_data = []

    for slot in slots:
        # Ensure times are in EST
        start_time = slot['start'].astimezone(EST)
        end_time = slot['end'].astimezone(EST)

        preview_data.append({
            'Date': start_time.strftime('%Y-%m-%d'),
            'Day': start_time.strftime('%A'),
            'Start Time': start_time.strftime('%I:%M %p'),
            'End Time': end_time.strftime('%I:%M %p'),
            'Time Zone': 'EST'
        })

    df = pd.DataFrame(preview_data)
    return df

def export_ics(new_slots, meeting_title):
    """Create new calendar with only the new scheduled meetings"""
    cal = Calendar()

    # Add only the new events
    for slot in new_slots:
        new_event = Event()
        new_event.add('summary', meeting_title)
        # Convert to UTC for ical format
        start_utc = slot['start'].astimezone(pytz.UTC)
        end_utc = slot['end'].astimezone(pytz.UTC)
        new_event.add('dtstart', start_utc)
        new_event.add('dtend', end_utc)
        cal.add_component(new_event)

    return cal
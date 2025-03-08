from datetime import datetime, timedelta
import pytz
from dateutil.relativedelta import relativedelta, TH, FR
from dateutil.rrule import rrule, MONTHLY, WEEKLY
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define EST timezone
EST = pytz.timezone('America/New_York')

def find_optimal_slots(existing_events, preferred_time, duration, recurrence, months_ahead):
    """Find optimal meeting slots based on preferences and existing schedule"""

    # Ensure all existing events are in EST timezone
    existing_events = normalize_events_timezone(existing_events)

    # Convert preferred time to EST datetime
    now = datetime.now(EST)
    end_date = now + relativedelta(months=months_ahead)

    # Generate candidate dates based on recurrence pattern
    candidate_dates = generate_candidate_dates(now, end_date, recurrence)

    # Find available slots
    optimal_slots = []

    for base_date in candidate_dates:
        logger.info(f"Searching for slots on {base_date.strftime('%Y-%m-%d')}")

        # Try to find a slot on this day
        slot = find_available_slot_on_day(
            base_date,
            preferred_time,
            duration,
            existing_events
        )

        if slot:
            optimal_slots.append(slot)
            continue

        # If no slot found, try nearby dates with same weekday
        nearby_slot = find_slot_on_nearby_dates(
            base_date,
            preferred_time,
            duration,
            existing_events,
            end_date,
            now
        )

        if nearby_slot:
            optimal_slots.append(nearby_slot)

    return optimal_slots

def normalize_events_timezone(events):
    """Ensure all events are in EST timezone"""
    normalized = []
    for event in events:
        start = event['start'].astimezone(EST)
        end = event['end'].astimezone(EST)
        normalized.append({
            'summary': event['summary'],
            'start': start,
            'end': end
        })
    return normalized

def generate_candidate_dates(start_date, end_date, recurrence):
    """Generate dates based on recurrence pattern"""
    if recurrence == "First Thursday of each month":
        dates = list(rrule(
            MONTHLY,
            dtstart=start_date,
            until=end_date,
            byweekday=[TH(1)]
        ))
    elif recurrence == "Last Friday of each month":
        dates = list(rrule(
            MONTHLY,
            dtstart=start_date,
            until=end_date,
            byweekday=[FR(-1)]
        ))
    elif recurrence == "Every two weeks":
        dates = list(rrule(
            WEEKLY,
            interval=2,
            dtstart=start_date,
            until=end_date
        ))
    else:  # Weekly
        dates = list(rrule(
            WEEKLY,
            dtstart=start_date,
            until=end_date
        ))

    return dates

def find_available_slot_on_day(date, preferred_time, duration, existing_events):
    """Find an available slot on a specific day"""
    # Convert date to datetime at 9 AM EST
    day_start = datetime.combine(
        date.date() if isinstance(date, datetime) else date,
        datetime.min.time().replace(hour=9)
    )
    day_start = EST.localize(day_start)

    # End time is 5 PM EST
    day_end = day_start.replace(hour=17)

    # Start searching from preferred time if it's within business hours
    preferred_datetime = datetime.combine(
        date.date() if isinstance(date, datetime) else date,
        preferred_time
    )
    preferred_datetime = EST.localize(preferred_datetime)

    if 9 <= preferred_time.hour < 17:
        current_time = preferred_datetime
    else:
        current_time = day_start

    # Try every 30-minute slot during business hours
    while current_time < day_end:
        slot = {
            'start': current_time,
            'end': current_time + timedelta(minutes=duration)
        }

        # Don't let meetings go past business hours
        if slot['end'] > day_end:
            break

        if not has_conflict(slot, existing_events):
            logger.info(f"Found available slot: {slot['start']} - {slot['end']} EST")
            return slot

        current_time += timedelta(minutes=30)

    logger.info(f"No available slots found on {date.strftime('%Y-%m-%d')}")
    return None

def find_slot_on_nearby_dates(base_date, preferred_time, duration, existing_events, end_date, start_date):
    """Try to find slots on nearby dates, preferring the same day of the week"""
    original_weekday = base_date.weekday()

    # Try up to 4 weeks forward and backward
    for week_offset in [1, -1, 2, -2, 3, -3, 4, -4]:
        test_date = base_date + timedelta(weeks=week_offset)

        # Don't go beyond the scheduling window
        if test_date > end_date or test_date < start_date:
            continue

        logger.info(f"Trying alternate date: {test_date.strftime('%Y-%m-%d')}")

        slot = find_available_slot_on_day(
            test_date,
            preferred_time,
            duration,
            existing_events
        )

        if slot:
            logger.info(f"Found slot {week_offset} weeks from original date")
            return slot

    return None

def has_conflict(slot, existing_events):
    """Check if a slot conflicts with existing events"""
    buffer_time = timedelta(minutes=15)  # 15-minute buffer

    # Add buffer to the slot times
    slot_start = slot['start'] - buffer_time
    slot_end = slot['end'] + buffer_time

    for event in existing_events:
        # Skip events that are clearly outside our time range
        if event['end'] < slot_start or event['start'] > slot_end:
            continue

        # Check for any overlap
        if (slot_start < event['end'] and slot_end > event['start']):
            logger.info(
                f"Conflict found: Slot {slot['start']} - {slot['end']} "
                f"conflicts with event {event['summary']}: "
                f"{event['start']} - {event['end']}"
            )
            return True

    return False
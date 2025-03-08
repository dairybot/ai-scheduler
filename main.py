import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
from calendar_utils import parse_ics, export_ics, get_calendar_preview
from scheduler import find_optimal_slots
from database import get_db, MeetingPreference, ScheduledMeeting
from sqlalchemy.orm import Session

# Initialize database session
try:
    db = next(get_db())
except Exception as e:
    st.error(f"Database connection error: {str(e)}")
    st.stop()

st.set_page_config(page_title="AI Meeting Scheduler", layout="wide")

# Custom CSS
with open("style.css") as f:
    st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

st.title("AI Meeting Scheduler")
st.markdown("""
Upload your calendar and let AI help you schedule recurring meetings optimally.
""")

# File upload
uploaded_file = st.file_uploader("Upload your .ics calendar file", type=['ics'])

if uploaded_file:
    try:
        existing_events = parse_ics(uploaded_file)
        st.success("Calendar file successfully loaded!")

        # Meeting preferences
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Meeting Preferences")
            meeting_title = st.text_input("Meeting Title", "Recurring Meeting")
            duration = st.number_input("Duration (minutes)", 
                                   min_value=15, 
                                   max_value=240, 
                                   value=60, 
                                   step=15)

            recurrence = st.selectbox("Recurrence Pattern",
                                  ["First Thursday of each month",
                                   "Last Friday of each month",
                                   "Every two weeks",
                                   "Weekly"])

            preferred_time = st.time_input("Preferred Start Time", 
                                       datetime.strptime("09:00", "%H:%M"))

            months_ahead = st.slider("Schedule for how many months?", 
                                 min_value=1, 
                                 max_value=12, 
                                 value=6)

        if st.button("Find Optimal Schedule"):
            with st.spinner("AI is finding the best meeting slots..."):
                try:
                    # Save preferences to database
                    pref = MeetingPreference(
                        title=meeting_title,
                        duration=duration,
                        recurrence_pattern=recurrence,
                        preferred_time=preferred_time.strftime("%H:%M"),
                        months_ahead=months_ahead
                    )
                    db.add(pref)
                    db.commit()

                    # Calculate optimal slots
                    optimal_slots = find_optimal_slots(
                        existing_events,
                        preferred_time,
                        duration,
                        recurrence,
                        months_ahead
                    )

                    # Save scheduled meetings to database
                    for slot in optimal_slots:
                        meeting = ScheduledMeeting(
                            preference_id=pref.id,
                            start_time=slot['start'],
                            end_time=slot['end'],
                            title=meeting_title
                        )
                        db.add(meeting)
                    db.commit()

                    # Display results with option to modify
                    st.subheader("Proposed Schedule")
                    preview_df = get_calendar_preview(optimal_slots)
                    st.dataframe(preview_df)

                    # Export button for new meetings only
                    if len(optimal_slots) > 0:
                        new_calendar = export_ics(optimal_slots, meeting_title)

                        st.download_button(
                            label="Download New Meetings Calendar",
                            data=new_calendar.to_ical(),
                            file_name="new_meetings.ics",
                            mime="text/calendar"
                        )
                    else:
                        st.error("No suitable slots found. Try adjusting your preferences.")
                except Exception as e:
                    st.error(f"Error scheduling meetings: {str(e)}")
                    db.rollback()

    except Exception as e:
        st.error(f"Error processing calendar file: {str(e)}")

# Display past schedules with modification options
try:
    with st.expander("View and Modify Past Schedules"):
        past_prefs = db.query(MeetingPreference).filter_by(is_active=True).all()
        for pref in past_prefs:
            st.write(f"### {pref.title}")
            st.write(f"Recurrence: {pref.recurrence_pattern}")
            st.write(f"Preferred Time: {pref.preferred_time}")

            meetings = db.query(ScheduledMeeting).filter_by(preference_id=pref.id).all()
            if meetings:
                meeting_data = [{
                    'Date': m.start_time.strftime('%Y-%m-%d'),
                    'Start Time': m.start_time.strftime('%H:%M'),
                    'End Time': m.end_time.strftime('%H:%M')
                } for m in meetings]
                st.dataframe(pd.DataFrame(meeting_data))

                # Option to export just these meetings
                if st.button(f"Export {pref.title} Meetings", key=f"export_{pref.id}"):
                    slots = [{
                        'start': m.start_time,
                        'end': m.end_time
                    } for m in meetings]
                    calendar = export_ics(slots, pref.title)
                    st.download_button(
                        label=f"Download {pref.title} Calendar",
                        data=calendar.to_ical(),
                        file_name=f"{pref.title.lower().replace(' ', '_')}.ics",
                        mime="text/calendar",
                        key=f"download_{pref.id}"
                    )

except Exception as e:
    st.error(f"Error loading past schedules: {str(e)}")
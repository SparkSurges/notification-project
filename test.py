import requests 

def get_event_time(form_id):
    # Extract components from the form_id
    type_code = int(form_id[0])
    year = form_id[1:5]
    month = form_id[5:7]
    day = form_id[7:9]
    time_created_24hr = form_id[9:13]
    close_time_24hr = form_id[13:17]

    return {
        "type": type_code,
        "year": year,
        "month": f"{month:02}",
        "day": f"{day:02}",
        "time_created": time_created_24hr,
        "close_time": close_time_24hr
    }

# Function: should take every form from the response and verify if the form needs to be notified, if indeed, schedule notification
def check_for_updates():
    # Make a request to your endpoint
    response = requests.get('https://sports-performance-c6dd6-default-rtdb.firebaseio.com/notifquest.json')
    serialized_forms = response.json()  # Assuming the response is in JSON format

    # Check for new items and update the local database
    for form_id in serialized_forms:
        print(form_id)
        print(serialized_forms[form_id])
        event_time = get_event_time(form_id)
        print(event_time)
        

check_for_updates()
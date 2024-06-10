import os
import time
import sqlite3
import requests
import firebase_admin
import datetime
import pytz
from firebase_admin import credentials, messaging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

# Define how much minutes before the close time to notify the user
MINUTES_BEFORE = 30

# Define the request delay time
REQUEST_DELAY = 20

# Form list type
FORM_STRING = ['PSE', 'PSR', 'QDM']

# Define Brasilia timezone
brasilia_tz = pytz.timezone('America/Sao_Paulo')

# Initialize Firebase Admin SDK
print("Initializing Firebase Admin SDK...")
cred = credentials.Certificate("./secrets.json")
firebase_admin.initialize_app(cred)
print("Firebase Admin SDK initialized.")

# Database connection
print("Connecting to the database...")
conn = sqlite3.connect('./notification.db', check_same_thread=False)

# Create a table if it doesn't exist
with conn:
    conn.execute('''
        CREATE TABLE IF NOT EXISTS notifications
        (id TEXT PRIMARY KEY, notified INTEGER)
    ''')
print("Database connection established.")

def get_event_time(form_id):
    if len(form_id) == 16:
        # Case without type code: YYYYMMDDHHMMHHMM
        year = int(form_id[0:4])
        month = int(form_id[4:6])
        day = int(form_id[6:8])
        close_time_24hr = form_id[12:16]
    else:
        # Case with type code: TYYYYMMDDHHMMHHMM
        year = int(form_id[1:5])
        month = int(form_id[5:7])
        day = int(form_id[7:9])
        close_time_24hr = form_id[13:17]
    
    # Extract hours and minutes from the close_time
    close_hour = int(close_time_24hr[:2])
    close_minute = int(close_time_24hr[2:])
    
    # Create a datetime object for the close time
    close_time = brasilia_tz.localize(datetime.datetime(year, month, day, close_hour, close_minute))
    
    return close_time

def check_for_updates():
    print('Checking for a new update...')
    # Make a request to your endpoint
    response = requests.get('https://sports-performance-c6dd6-default-rtdb.firebaseio.com/notifquest.json')
    serialized_forms = response.json()  # Assuming the response is in JSON format
    print(f"Request made to the server successfully.")

    # Check for new items and update the local database
    for form_id in serialized_forms:
        print(f"Initiating the verification of {form_id}.")
        event_time = get_event_time(form_id)
        
        with conn:
            c = conn.cursor()
            c.execute('SELECT * FROM notifications WHERE id = ?', (form_id,))

            if not c.fetchone():
                print(f"{form_id} wasn't found in the database...")
                print(f"Initiating verification...")
                current_time = datetime.datetime.now(brasilia_tz)
                if event_time < current_time:
                    c.execute('INSERT INTO notifications (id, notified) VALUES (?, ?)', (form_id, 1))
                    print(f"{form_id} is already notified")
                    continue

                c.execute('INSERT INTO notifications (id, notified) VALUES (?, ?)', (form_id, 0))

                # Schedule a notification
                schedule_notification(event_time, form_id)
            else:
                print(f"{form_id} is already notified")

def schedule_notification(event_time, form_id):
    notification_time = event_time - datetime.timedelta(minutes=MINUTES_BEFORE)  # 30 minutes before the event
    scheduler.add_job(send_notifications, 'date', run_date=notification_time, args=[form_id], misfire_grace_time=1800)
    print(f"Notification scheduled for {form_id} on {notification_time}")

def send_notifications(form_id):
    try:
        with conn:
            c = conn.cursor()
            # Check if the notification exists and has not been sent yet
            c.execute('SELECT * FROM notifications WHERE id = ? AND notified = 0', (form_id,))
            rows = c.fetchall()

            if not rows:
                print(f"No pending notifications found for form_id: {form_id}")
                return

            # Request to the endpoint to get user_ids for the form_id
            response = requests.get(f'https://sports-performance-c6dd6-default-rtdb.firebaseio.com/notifquest/{form_id}.json')
            if response.status_code != 200:
                print(f"Failed to retrieve user_ids for form_id: {form_id}")
                return
            
            user_ids = response.json()  # Assuming the response is a JSON list of user_ids
            for user_id in user_ids:
                user_key = user_ids[user_id]
                send_firebase_notification(
                    user_key, 
                    f"O formulário {FORM_STRING[int(form_id[0])]} precisa ser preenchido", 
                    f"Por favor, preencha seu formulário, faltam apenas {MINUTES_BEFORE} minutos."
                )

            # Update the notification status in the database
            c.execute('UPDATE notifications SET notified = 1 WHERE id = ?', (form_id,))

    except Exception as e:
        print(f"An error occurred: {e}")

def send_firebase_notification(token, title, body):
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            token=token,
        )
        response = messaging.send(message)
        print('Successfully sent message:', response)
    except Exception as e:
        print(f"Failed to send message to {token}: {e}")

if __name__ == '__main__':
    print("Starting the service...")

    global scheduler

    scheduler = BackgroundScheduler(timezone=brasilia_tz)
    scheduler.add_job(check_for_updates, 'interval', minutes=REQUEST_DELAY)
    scheduler.start()

    print(f"Service started. Checking for updates every {REQUEST_DELAY} minutes.")

    try:
        while True:
            time.sleep(2)
    except (KeyboardInterrupt, SystemExit):
        print("Stopping the service...")
        scheduler.shutdown()
        conn.close()
        print("Service stopped.")

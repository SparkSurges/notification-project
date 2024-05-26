import os
import time
import sqlite3
import requests
import firebase_admin
import datetime
from firebase_admin import credentials, messaging
from apscheduler.schedulers.background import BackgroundScheduler

# Initialize Firebase Admin SDK
cred = credentials.Certificate("./secrets.json")
firebase_admin.initialize_app(cred)

# Database connection
conn = sqlite3.connect('notification.db')
c = conn.cursor()

# Create a table if it doesn't exist
c.execute('''
          CREATE TABLE IF NOT EXISTS notifications
          (id INTEGER PRIMARY KEY, notified INTEGER)
          ''')
conn.commit()

def get_event_time(form_id):
    # Extract components from the form_id
    # Example: TYYYMMDDHHMMHHMM
    type_code = int(form_id[0])
    year = int(form_id[1:5])
    month = int(form_id[5:7])
    day = int(form_id[7:9])
    close_time_24hr = form_id[13:17]
    
    # Extract hours and minutes from the close_time
    close_hour = int(close_time_24hr[:2])
    close_minute = int(close_time_24hr[2:])
    
    # Create a datetime object for the close time
    close_time = datetime(year, month, day, close_hour, close_minute)
    
    return close_time

def check_for_updates():
    # Make a request to your endpoint
    response = requests.get('https://sports-performance-c6dd6-default-rtdb.firebaseio.com/notifquest.json')
    serialized_forms = response.json()  # Assuming the response is in JSON format

    # Check for new items and update the local database
    for form_id in serialized_forms:
        print(form_id)
        event_time = get_event_time(form_id)  
        c.execute('SELECT * FROM notifications WHERE id = ?', (form_id,))

        if not c.fetchone():
            if event_time < datetime.datetime.now():
                c.execute('INSERT INTO notifications (id, notified) VALUES (?, ?)', (form_id, 1))
                conn.commit()
                continue

            c.execute('INSERT INTO notifications (id, notified) VALUES (?, ?)', (form_id, 0))
            conn.commit()

            # Schedule a notification
            schedule_notification(event_time, form_id)

def schedule_notification(event_time, form_id):
    notification_time = event_time - datetime.timedelta(minutes=30)  # 30 minutes before the event
    scheduler.add_job(send_notifications, 'date', run_date=notification_time, args=[form_id])
    print(f"Notification scheduled for {notification_time}")


def send_notifications(form_id):
    try:
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
            send_firebase_notification(user_key, "Faltam 30 minutos!", f"Por favor, preencha seu formulário, faltam apenas 30 minutos.")

            # Update the notification status in the database
            c.execute('UPDATE notifications SET notified = 1 WHERE id = ?', (form_id,))
            conn.commit()

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
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_for_updates, 'interval', minutes=30)
    scheduler.start()

    try:
        while True:
            time.sleep(2)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        conn.close()

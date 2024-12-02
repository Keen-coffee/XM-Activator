from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from sqlalchemy.orm import scoped_session, make_transient
from sqlalchemy.exc import SQLAlchemyError
import requests
import sys
import json
import uuid
import threading
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

logging.info("Starting the Flask app and background thread.")

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///radios.db'
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
db = SQLAlchemy(app)
SESSION = requests.Session()

debug = False

user_agent = "SXM Dealer/2.7.0 CFNetwork/978.0.7 Darwin/18.7.0"
x_kony_app_secret = "e3048b73f2f7a6c069f7d8abf5864115"
x_kony_app_key = "85ee60a3c8f011baaeba01ff3a5ae2c9"
app_version = "2.7.0"
uuid4 = str(uuid.uuid4())
auth_token = None
device_id = None
seq_value = None

debug_code = None
debug_body = None

# Background Task for Auto-Activation
def check_and_activate_radios():
    with app.app_context():
        db.create_all()
        while True:
            try:
                # Get the current date and time
                current_time = datetime.now()

                # Log the current time of the check
                logging.info(f"[{current_time}] Running check for radios older than 90 days.")

                # Calculate the threshold time (90 days ago)
                threshold_time = current_time - timedelta(days=90)
                last_attempt_threshold = current_time - timedelta(hours=24)

                # Query radios with activated date older than 90 days
                radios_to_activate = Radio.query.filter(
                    ((Radio.activated < threshold_time) | (Radio.activated == None)) &
                    ((Radio.last_attempt == None) | (Radio.last_attempt < last_attempt_threshold))
                ).all()

                for radio in radios_to_activate:
                    try:
                        # Trigger the /activate endpoint
                        response = requests.post(f"http://127.0.0.1:5000/activate/{radio.id}")
                        
                        # Log the response for debugging
                        if response.status_code == 200:
                            logging.info(f"Successfully activated radio {radio.id}.")
                        else:
                            logging.error(f"Failed to activate radio {radio.id}: {response.text}")

                    except Exception as e:
                        logging.error(f"Error activating radio {radio.id}: {str(e)}")
                
                logging.info(f"[{datetime.now()}] Completed one iteration of the check-and-activate loop.")
                # Sleep for a set interval (e.g., 1 hour) before checking again
                time.sleep(3600)  # Adjust the interval as needed
            except Exception as e:
                    logging.error(f"Error in background thread: {str(e)}")

def appconfig():
    global debug_code
    global debug_body
    try:
        response = SESSION.post(
            url="https://mcare.siriusxm.ca/authService/100000002/appconfig",
            headers={
                "X-Kony-Integrity": "GWSUSEVMJK;FEC9AA232EC59BE8A39F0FAE1B71300216E906B85F40CA2B1C5C7A59F85B17A4",
                "X-HTTP-Method-Override": "GET",
                "Accept": "*/*",
                "X-Kony-App-Secret": x_kony_app_secret,
                "Accept-Language": "en-us",
                "Accept-Encoding": "br, gzip, deflate",
                "X-Kony-App-Key": x_kony_app_key,
                "User-Agent": user_agent,
            },
        )
        debug_code=response.status_code
        debug_body=response.content
        return response.json()        
    except requests.exceptions.RequestException:
        logging.error ('HTTP Request Failed')

def login():
    global debug_code
    global debug_body
    try:
        response = SESSION.post(
            url="https://mcare.siriusxm.ca/authService/100000002/login",
            headers={
                "X-Kony-Platform-Type": "ios",
                "Accept": "application/json",
                "X-Kony-App-Secret": x_kony_app_secret,
                "Accept-Language": "en-us",
                "X-Kony-SDK-Type": "js",
                "Accept-Encoding": "br, gzip, deflate",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": user_agent,
                "X-Kony-SDK-Version": "8.4.134",
                "X-Kony-App-Key": x_kony_app_key,
            },
        )
        debug_code=response.status_code
        debug_body=response.content
        return response.json().get('claims_token').get('value')
    except requests.exceptions.RequestException:
        logging.error ('HTTP Request Failed')

def version_control():
    global debug_code
    global debug_body
    try:
        response = SESSION.post(
            url="https://mcare.siriusxm.ca/services/DealerAppService7/VersionControl",
            headers={
                "Accept": "*/*",
                "X-Kony-API-Version": "1.0",
                "X-Kony-DeviceId": uuid4,
                "Accept-Language": "en-us",
                "Accept-Encoding": "br, gzip, deflate",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": user_agent,
                "X-Kony-Authorization": auth_token,
            },
            data={
                "deviceCategory": "iPhone",
                "appver": app_version,
                "deviceLocale": "en_US",
                "deviceModel": "iPhone%206%20Plus",
                "deviceVersion": "12.5.7",
                "deviceType": "",
            },
        )
        debug_code=response.status_code
        debug_body=response.content
        return response.json()
    except requests.exceptions.RequestException:
        logging.error ('HTTP Request Failed')

def get_properties():
    global debug_code
    global debug_body
    try:
        response = SESSION.post(
            url="https://mcare.siriusxm.ca/services/DealerAppService7/getProperties",
            headers={
                "Accept": "*/*",
                "X-Kony-API-Version": "1.0",
                "X-Kony-DeviceId": uuid4,
                "Accept-Language": "en-us",
                "Accept-Encoding": "br, gzip, deflate",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": user_agent,
                "X-Kony-Authorization": auth_token,
            },
            data={
            },
        )
        debug_code=response.status_code
        debug_body=response.content
        return response.json()
    except requests.exceptions.RequestException:
        logging.error ('HTTP Request Failed')

def update_device_sat_refresh_with_priority():
    global debug_code
    global debug_body
    try:
        response = SESSION.post(
            url="https://mcare.siriusxm.ca/services/USUpdateDeviceSATRefresh/updateDeviceSATRefreshWithPriority",
            headers={
                "Accept": "*/*",
                "X-Kony-API-Version": "1.0",
                "X-Kony-DeviceId": uuid4,
                "Accept-Language": "en-us",
                "Accept-Encoding": "br, gzip, deflate",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": user_agent,
                "X-Kony-Authorization": auth_token,
            },
            data={
                "deviceId": device_id,
                "appVersion": app_version,
                "lng": "-86.210274696",
                "deviceID": uuid4,
                "provisionPriority": "2",
                "provisionType": "activate",
                "lat": "32.374343677",
            },
        )
        debug_code=response.status_code
        debug_body=response.content
        return response.json()
    except requests.exceptions.RequestException:
        logging.error ('HTTP Request Failed')

def get_crm_account_plan_information():
    global debug_code
    global debug_body
    try:
        response = SESSION.post(
            url="https://mcare.siriusxm.ca/services/DemoConsumptionRules/GetCRMAccountPlanInformation",
            headers={
                "Accept": "*/*",
                "X-Kony-API-Version": "1.0",
                "X-Kony-DeviceId": uuid4,
                "Accept-Language": "en-us",
                "Accept-Encoding": "br, gzip, deflate",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": user_agent,
                "X-Kony-Authorization": auth_token,
            },
            data={
                "seqVal": seq_value,
                "deviceId": device_id,
            },
        )
        debug_code=response.status_code
        debug_body=response.content
        return response.json()
    except requests.exceptions.RequestException:
        logging.error ('HTTP Request Failed')

def db_update_for_google():
    global debug_code
    global debug_body
    try:
        response = SESSION.post(
            url="https://mcare.siriusxm.ca/services/DBSuccessUpdate/DBUpdateForGoogle",
            headers={
                "Accept": "*/*",
                "X-Kony-API-Version": "1.0",
                "X-Kony-DeviceId": uuid4,
                "Accept-Language": "en-us",
                "Accept-Encoding": "br, gzip, deflate",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": user_agent,
                "X-Kony-Authorization": auth_token,
            },
            data={
                "OM_ELIGIBILITY_STATUS": "Eligible",
                "appVersion": app_version,
                "flag": "failure",
                "Radio_ID": device_id,
                "deviceID": uuid4,
                "G_PLACES_REQUEST": "",
                "OS_Version": "iPhone 12.5.7",
                "G_PLACES_RESPONSE": "",
                "Confirmation_Status": "SUCCESS",
                "seqVal": seq_value,
            },
        )
        debug_code=response.status_code
        debug_body=response.content
        return response.json()
    except requests.exceptions.RequestException:
        logging.error ('HTTP Request Failed')

def block_list_device():
    global debug_code
    global debug_body
    try:
        response = SESSION.post(
            url="https://mcare.siriusxm.ca/services/USBlockListDevice/BlockListDevice",
            headers={
                "Accept": "*/*",
                "X-Kony-API-Version": "1.0",
                "X-Kony-DeviceId": uuid4,
                "Accept-Language": "en-us",
                "Accept-Encoding": "br, gzip, deflate",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": user_agent,
                "X-Kony-Authorization": auth_token,
            },
            data={
                "deviceId": uuid4,
            },
        )
        debug_code=response.status_code
        debug_body=response.content
        return response.json()
    except requests.exceptions.RequestException:
        logging.error ('HTTP Request Failed')

def create_account():
    global debug_code
    global debug_body
    try:
        response = SESSION.post(
            url="https://mcare.siriusxm.ca/services/DealerAppService3/CreateAccount",
            headers={
                "Connection": "close",
                "Accept": "*/*",
                "X-Kony-API-Version": "1.0",
                "X-Kony-DeviceId": uuid4,
                "Accept-Language": "en-us",
                "Accept-Encoding": "br, gzip, deflate",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": user_agent,
                "X-Kony-Authorization": auth_token,
            },
            data={
                "seqVal": seq_value,
                "deviceId": device_id,
                "oracleCXFailed": "1",
                "appVersion": app_version,
            },
        )
        debug_code=response.status_code
        debug_body=response.content
        return response.json()
    except requests.exceptions.RequestException:
        logging.error ('HTTP Request Failed')

def update_device_sat_refresh_with_priority_cc():
    global debug_code
    global debug_body
    try:
        response = SESSION.post(
            url="https://mcare.siriusxm.ca/services/USUpdateDeviceRefreshForCC/updateDeviceSATRefreshWithPriority",
            headers={
                "Accept": "*/*",
                "X-Kony-API-Version": "1.0",
                "X-Kony-DeviceId": uuid4,
                "Accept-Language": "en-us",
                "Accept-Encoding": "br, gzip, deflate",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": user_agent,
                "X-Kony-Authorization": auth_token,
            },
            data={
                "deviceId": device_id,
                "provisionPriority": "2",
                "appVersion": app_version,
                "device_Type": "iPhone iPhone 6 Plus",
                "deviceID": uuid4,
                "os_Version": "iPhone 12.5.7",
                "provisionType": "activate",
            },
        )
        debug_code=response.status_code
        debug_body=response.content
        return response.json()
    except requests.exceptions.RequestException:
        logging.error ('HTTP Request Failed')

class Radio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    radio_id = db.Column(db.String(50), unique=True, nullable=False)
    activated = db.Column(db.DateTime, nullable=True)
    last_attempt = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=True)
    message = db.Column(db.String(200), nullable=True)
    log = db.Column(db.Text, nullable=True)
    alias = db.Column(db.String(50), nullable=True)

# Use the app context for database operations
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    global debug
    debug = True
    radios = Radio.query.all()
    return render_template('index.html', radios=radios, debug=debug)

@app.route('/add', methods=['GET', 'POST'])
def add_radio():
    if request.method == 'POST':
        radio_id = request.form['new_radio_id']
        alias = request.form['new_alias']
        
        # Create a new instance of Radio within the current session
        new_radio = Radio(radio_id=radio_id, alias=alias)
        
        with app.app_context():
            db.session.add(new_radio)
            db.session.commit()

        return redirect(url_for('index'))
    
    return render_template('index.html', radios=Radio.query.all())

@app.route('/delete/<int:id>', methods=['GET', 'POST'])
def delete_radio(id):
    if request.method == 'POST':
        with app.app_context():
            radio_to_delete = Radio.query.get_or_404(id)
            db.session.delete(radio_to_delete)
            db.session.commit()

        return redirect(url_for('index'))

    radio_to_delete = Radio.query.get_or_404(id)
    return render_template('delete.html', radio=radio_to_delete)

@app.route('/activate/<int:id>', methods=['POST'])
def activate_radio(id):
    global debug 
    global auth_token
    global device_id
    global seq_value

    radio_to_activate = Radio.query.get_or_404(id)
    device_id = radio_to_activate.radio_id

    appconfig()
    auth_token = login()
    get_properties()
    response = update_device_sat_refresh_with_priority()
    seq_value = int(response.get('seqValue'))
    output = {
        "device_id": device_id,
        "auth_token": len(auth_token),
        "update_1": response,
        "seq": seq_value,
        "get_crm": get_crm_account_plan_information(),
        "db_1": db_update_for_google(),
        "block": block_list_device(),
        "create": create_account(),
        "update_2": update_device_sat_refresh_with_priority_cc(),
        "db_2": db_update_for_google()
    }
    logging.error(output)
    result_data = output["create"]["resultData"]
    if len(result_data) >= 3:
        actMessage = result_data[2].get('message')
        actCode = result_data[0].get('resultCode')
    else:
        actMessage = result_data[0].get('resultCode')
        actCode = result_data[0].get('resultCode')


    with app.app_context():
        try:
            currentTime_last_attempt = datetime.now()
            if actCode == "SUCCESS":
                currentTime_activated = datetime.now()
            else:
                currentTime_activated = radio_to_activate.activated
        
            # Mark the 'status' attribute as dirty
            db.session.execute(
                db.update(Radio)
                .where(Radio.id == id)
                .values(status=actCode)
                .values(message=actMessage)
                .values(activated=currentTime_activated)
                .values(last_attempt=currentTime_last_attempt)
                .values(log=(json.dumps(output, indent=2)))
            )

            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()

    return redirect(url_for('index'))

@app.route('/refresh/<int:id>', methods=['POST'])
def refresh_radio(id):
    global debug 
    global auth_token
    global device_id
    global seq_value

    radio_to_activate = Radio.query.get_or_404(id)
    device_id = radio_to_activate.radio_id

    appconfig()
    auth_token = login()
    get_properties()
    
    output = {
        "device_id": device_id,
        "update_1": update_device_sat_refresh_with_priority(),
        "update_2": update_device_sat_refresh_with_priority_cc(),
    }
    return jsonify(output)

@app.route('/debug')
def debug():
    # Your debugging logic here
    # For example:
    if debug:
        logging.info('Code: {status_code}'.format(status_code=debug_code))
        logging.info('Body: {content}'.format(content=debug_body))
    
    # Return a response indicating success or failure
    return jsonify({'message': 'Debugging information logged successfully'})

# Start the background task
logging.info("Starting background thread for auto-activation...")
background_thread = threading.Thread(target=check_and_activate_radios, daemon=True)
background_thread.start()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0')


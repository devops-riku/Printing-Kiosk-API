from machine import Pin
from config import SSID, PASSWORD, SERVER_URL
import time
import network
import urequests
import machine

ir_sensor = Pin(2, Pin.IN)
relay = Pin(15, Pin.OUT)

previous_state = ir_sensor.value()
object_detected = False
relay_status = False
relay_state = relay.value(0)


def connect_to_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)

    while not wlan.isconnected():
        print('Connecting to WiFi...')
        time.sleep(1)

    print('Connected to WiFi:', wlan.ifconfig())


def read_ir_sensor():
    """Read the proximity sensor and update LEDs with proper object detection logic."""
    global previous_state, object_detected
    current_state = ir_sensor.value()

    if current_state == 0 and not object_detected:
        object_detected = True
        return True

    elif current_state == 1 and object_detected:
        object_detected = False

    return False


def check_for_file():
    """Check the server for new files."""
    try:
        response = urequests.get(SERVER_URL + '/check_for_file')  # Endpoint to check for new files
        if response.status_code == 200:
            file_info = response.json()
            print('File available:', file_info)
            return file_info
        else:
            print('No new files or failed to connect')
    except Exception as e:
        print('Error checking for file:', e)
    return None


def update_shredded_pages(file_id, shredded_pages):
    """Notify the server that the file has been processed."""
    try:
        response = urequests.post(
            SERVER_URL + f'/update_shredded_pages/{file_id}',
            json={'shredded_pages': shredded_pages}
        )
        if response.status_code == 200:
            print(f'Updated shredded pages: {shredded_pages}')
        else:
            print('Failed to update server')
    except Exception as e:
        print('Error updating server:', e)


def clear_current_process():
    response = urequests.get(SERVER_URL + '/clear-current-file')
    relay.value(1)


def get_current_file_id():
    response = urequests.get(SERVER_URL + '/current_file_id')
    id = response.json()
    return id
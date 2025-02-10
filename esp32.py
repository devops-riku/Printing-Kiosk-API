import network
import urequests
import time
import machine

# Wi-Fi credentials
SSID = 'Hehe'
PASSWORD = 'Devric02'

# FastAPI server URL
SERVER_URL = 'http://192.168.254.133:8000'  # Replace with your FastAPI server URL

# Printer IPP URL
PRINTER_URL = 'http://192.168.18.19:631/ipp/print'  # Replace with your printer's IPP URL

# Set up the IR sensor pin (GPIO15)
sensor_pin = machine.Pin(15, machine.Pin.IN)

# Set up the LED pins
green_led = machine.Pin(14, machine.Pin.OUT)  # Green LED for no object detected
red_led = machine.Pin(13, machine.Pin.OUT)  # Red LED for object detected

# Initialize previous sensor state
previous_state = sensor_pin.value()
object_detected = False  # Track if an object was detected


def connect_to_wifi():
    """Connect to the Wi-Fi network."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)

    while not wlan.isconnected():
        print('Connecting to WiFi...')
        time.sleep(1)

    print('Connected to WiFi:', wlan.ifconfig())


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


def print_file(file_url):
    """Send the file to the printer using IPP."""
    print('File is printing...')
    try:
        response = urequests.get(file_url)
        if response.status_code == 200:
            file_data = response.content
            headers = {'Content-Type': 'application/pdf'}  # Adjust based on file type
            print_response = urequests.post(PRINTER_URL, data=file_data, headers=headers)
            if print_response.status_code == 200:
                print('File sent to printer successfully')
            else:
                print('Failed to print file')
        else:
            print('Failed to download file')
    except Exception as e:
        print('Error printing file:', e)


def check_force_print(file_id):
    """Check if a force print was triggered."""
    try:
        response = urequests.get(SERVER_URL + f'/check_force_print/{file_id}')
        if response.status_code == 200:
            force_print_info = response.json()
            if force_print_info.get("force_print") and force_print_info.get("pages_to_print") > 0:
                return force_print_info
        return None
    except Exception as e:
        print('Error checking force print:', e)
        return None


def read_proximity_sensor():
    """Read the proximity sensor and update LEDs with proper object detection logic."""
    global previous_state, object_detected
    current_state = sensor_pin.value()  # Read the current state of the sensor

    if current_state == 0 and not object_detected:  # Object detected
        print("Object Detected!")
        red_led.value(1)  # Turn on the red LED
        green_led.value(0)  # Turn off the green LED
        object_detected = True
        return True  # Return True only when an object is first detected

    elif current_state == 1 and object_detected:  # Object removed
        print("No Object")
        red_led.value(0)  # Turn off the red LED
        green_led.value(1)  # Turn on the green LED
        object_detected = False

    return False  # Return False when no new object is detected


def main():
    connect_to_wifi()
    while True:
        file_info = check_for_file()
        if file_info and 'file_id' in file_info and 'required_shredded_pages' in file_info:
            file_id = file_info['file_id']
            required_shredded_pages = file_info['required_shredded_pages']
            shredded_pages = file_info.get('shredded_pages', 0)

            while shredded_pages < required_shredded_pages:
                if read_proximity_sensor():  # Increment only when an object is first detected
                    shredded_pages += 1
                    print(f'Shredded pages: {shredded_pages}/{required_shredded_pages}')
                    update_shredded_pages(file_id, shredded_pages)

                # **Check if user triggered force print**
                force_print_info = check_force_print(file_id)
                if force_print_info:
                    print("Force print triggered by user")
                    pages_to_print = force_print_info["pages_to_print"]
                    print(f"Printing {pages_to_print} pages")
                    print_file(file_info['file_url'])
                    break  # Stop shredding and print immediately

                time.sleep(0.1)

            # Once required pages are shredded, trigger print
            if shredded_pages == required_shredded_pages:
                print("All pages shredded. Sending file to print...")
                print_file(file_info['file_url'])

        time.sleep(1)  # Check every second


if __name__ == '__main__':
    main()


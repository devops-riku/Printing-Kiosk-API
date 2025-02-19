from functions import connect_to_wifi, read_ir_sensor, check_for_file, update_shredded_pages, relay, \
    clear_current_process
import time


def main():
    connect_to_wifi()
    relay.value(1)
    while True:
        file_info = check_for_file()
        if file_info and 'file_id' in file_info and 'required_shredded_pages' in file_info:
            file_id = file_info['file_id']
            required_shredded_pages = file_info['required_shredded_pages']
            shredded_pages = file_info.get('shredded_pages', 0)

            print("Relay turned ON. Starting shredding...")
            time.sleep(6)
            relay.value(0)

            while shredded_pages < required_shredded_pages:
                if read_ir_sensor():
                    shredded_pages += 1
                    print(f'Shredded pages: {shredded_pages}/{required_shredded_pages}')
                    update_shredded_pages(file_id, shredded_pages)
                time.sleep(0.1)

            if shredded_pages == required_shredded_pages:
                print("All pages shredded. Relay turned OFF.")
                clear_current_process()
                time.sleep(6)
                relay.value(1)

            time.sleep(1)


if __name__ == '__main__':
    main()


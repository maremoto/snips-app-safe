#!/usr/bin/env python3
# -*-: coding utf-8 -*-

from src.snipsTools   import SnipsI18n, SnipsConfigParser
from src.peripherals  import Button, Pixels, Alarm
from src.contacts     import Contacts
from src.snipsMPU     import SnipsMPU
from src.service      import AssistancesManager
from src.phone        import Phone

VERSION = '0.1.0'

CONFIG_INI = 'config.ini'
I18N_DIR = 'assets'

TIMEOUT_START_ALARM=35 #no action done or dialogue is working, raise alarm and call default
TIMEOUT_STOP_ALARM=300 #seconds to re-check client status

# ============
# Get config and create elements
# ============

def init_action():

    config = SnipsConfigParser.read_configuration_file(CONFIG_INI).get('global')
    
        # Read comm configuration
    MQTT_ADDR_HOST = str(config.get('mqtt_host'))
    MQTT_ADDR_PORT = str(config.get('mqtt_port'))
    MQTT_ADDR = "{}:{}".format(MQTT_ADDR_HOST, MQTT_ADDR_PORT)
    SITE_ID = str(config.get('site_id'))
    
        # Read peripherals configuration
    BUTTON_GPIO = int(config.get('button_gpio_bcm'))
    PIXELS_N = int(config.get('pixels_n'))
    ALARM_GPIO = int(config.get('alarm_gpio_bcm'))
    
    config = SnipsConfigParser.read_configuration_file(CONFIG_INI).get('secret')
    
        # Read customization configuration
    LOCALE = str(config.get('locale'))
    CLIENT_NAME = str(config.get('client_name'))
    DEFAULT_CONTACT_NAME = str(config.get('default_contact'))


    config = SnipsConfigParser.read_configuration_file(CONFIG_INI).get('phone')

        # Read softphone configuration
    PHONE_CONFIG = str(config.get('softphone_config_file'))
    TIMEOUT_END = str(config.get('timeout_call_end'))
    CAPTURE_SNDC = str(config.get('capture_soundcard_name'))
    PLAYBACK_SNDC = str(config.get('playback_soundcard_name'))
    SOS_WAV = str(config.get('sos_message_wav'))
    SOS_TXT = str(config.get('sos_message_text'))
    
        # Create objects
    pixels = Pixels(PIXELS_N)
    alarm = Alarm(ALARM_GPIO, TIMEOUT_STOP_ALARM)
    i18n = SnipsI18n(I18N_DIR, LOCALE)
    phone = Phone(i18n, SITE_ID, PHONE_CONFIG, TIMEOUT_END, CAPTURE_SNDC, PLAYBACK_SNDC, SOS_WAV, SOS_TXT)
    contacts = Contacts(DEFAULT_CONTACT_NAME)
    assistances_manager = AssistancesManager(phone, i18n, contacts, CLIENT_NAME)
    client = SnipsMPU(i18n, MQTT_ADDR, SITE_ID, TIMEOUT_START_ALARM, 
                      assistances_manager, alarm, pixels)
    button = Button(BUTTON_GPIO, client.pushed_button)
    
    return alarm, client, button

# ============
# Main 
# ============

if __name__ == "__main__":
    alarm, client, button = init_action()
    
    try:
        client.start_block()

    except KeyboardInterrupt:
        client.stop()
        alarm.clear(with_gpio=False)
        button.clear()

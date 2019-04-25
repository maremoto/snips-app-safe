#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess

from src.snipsTools import SnipsConfigParser
from src.contacts   import Contacts

"""
This is the payload for injection:
    
{
    "operations": [
        [
            "addFromVanilla",
            {
                "callee_name" : [
                    "Antonio",
                    "Maria"
                ]
            }
        ]
    ]
}

This is the command for injection:
    
    $ mosquitto_pub -t hermes/injection/perform -f injections.json
"""

CONFIG_INI = 'config.ini'
INJECTIONS_INPUT_FILE="./injections.json"

def inject():
        # Some configuration
    config = SnipsConfigParser.read_configuration_file(CONFIG_INI).get('secret')
    DEFAULT_CONTACT_NAME = str(config.get('default_contact'))    
    
        # Load contacts an create payload file
    contacts = Contacts(DEFAULT_CONTACT_NAME)
    payload = contacts.injection_payload() 
    with open(INJECTIONS_INPUT_FILE,'w') as f:
        f.write(payload)
        print("injection file created ",INJECTIONS_INPUT_FILE)
        
        # Execute injection
    cmd = 'mosquitto_pub -t hermes/injection/perform -f '+INJECTIONS_INPUT_FILE
    try:
        subprocess.call(cmd, shell=True)   
    except Exception as e:
        print(e)
        print("injection failure.")
    else:
        print("injection done.")
        
    # Main
if __name__ == "__main__":
    inject()

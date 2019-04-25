#!/usr/bin/env python3
# -*- coding: utf-8 -*-

MAX_CONTACTS_LEN=15
ENCODING_FORMAT = "utf-8"

import json
import re

class Contacts(object):
    '''
    Load and manage customer contacts
    '''
    
    __dic = {}

    __path = None
    __filename = None

    def __init__(self, default_contact, path=".", filename="contacts.json"):
        self.__default_contact = default_contact
        self.__path = path
        self.__filename = filename
        self.__load_dictionary()

    def __load_dictionary(self):
        filepath = '{}/{}'.format(self.__path, self.__filename)
        try:
            with open(filepath, 'r', encoding=ENCODING_FORMAT) as f:
                print("loading contacts from ",filepath)
                self.__dic = json.loads(f.read())
        except IOError as e:
            print (e)
        if len(self.__dic) > MAX_CONTACTS_LEN:
            raise ValueError("ERROR too many contacts configured ("+str(len(self.__dic))+" over "+str(MAX_CONTACTS_LEN)+")")
        if self.__default_contact not in self.__dic:
            raise ValueError("ERROR, the default contact "+self.__default_contact+" is not in the configuration file "+self.__filename)

    def get(self, raw_key, parameters = {}):
        keys = raw_key.split('.')
        temp = self.__dic

        for key in keys:
            temp = temp.get(key, 'null')

        if not parameters or temp == 'null':
            return temp
        else:
            for key in parameters:
                pattern = '(\{){2}(\s)*(' + key +'){1}(\s)*(\}){2}'
                temp = re.sub(pattern, str(parameters[key]), temp)
            return temp

    def get_default(self):
        return self.__default_contact, self.get(self.__default_contact)

    def list_entities(self):
        return [key for key in self.__dic]

    def injection_payload(self,operation="addFromVanilla"):
        entities = ", ".join(['"%s"' % (key) for key in self.__dic])
        return '{\n\t "operations": [\n\t\t [\n\t\t\t "%s", {\n\t\t\t\t "callee_name": [ %s ] \n\t\t\t} \n\t\t] \n\t] \n}' % \
                    (operation, entities)

    def print(self):
        print(self.__dic)

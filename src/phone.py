#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#import re
import os
import subprocess
from subprocess import PIPE, STDOUT
import time
import threading

from .snipsMPU import INTENT_CALL_SOMEONE

RESULT_END=0
RESULT_FAILURE=1
RESULT_FATAL=2

SOS_TXT_TIMES=3
TIMEOUT_END_SOS_CALL=30

class Phone(object):
    '''
    Call for Assistance
    '''

    def __init__(self, i18n, site_id, config_file, timeout_call_end, 
                 capture_soundcard_name, playback_soundcard_name, sos_message_wav, sos_message_text):
        self.__i18n = i18n
        self.__base_site_id = site_id
        self.__softphone_config_file = config_file
        self.__timeout_end = int(timeout_call_end)
        self.__capture_sndc = capture_soundcard_name
        self.__playback_sndc = playback_soundcard_name
        self.__sos_wav = sos_message_wav
        self.__sos_txt = sos_message_text

        self._no_call_status()
        
    def _no_call_status(self):
        self.__calling_contact = None
        self.__calling_number = None
        self.__calling_site_id = None
        self.__inform_cb = None
        self.__failure_cb = None
        self.__fatal_cb = None
        self.__end_cb = None
        self.__play_sos_message = False
        self.__manually_terminated = False
        self.__call_proc = None
        self.__check_timer = None

    def _ended_call(self, res):
        time.sleep(3) # avoid race conditions
        if res == RESULT_END:
            print("  call ended")
            sentence = self.__i18n.get('call.callEnd')
            if self.__end_cb is not None: self.__end_cb(sentence=sentence)
        elif res == RESULT_FAILURE:
            print("  call failure")
            sentence = self.__i18n.get('call.callFailure', {"contact_name": self.__calling_contact})
            if self.__failure_cb is not None: self.__failure_cb(sentence=sentence)
        else:            
            print("  call system error")
            sentence = self.__i18n.get('error.systemFatal')
            if self.__fatal_cb is not None: self.__fatal_cb(sentence=sentence)
    
        self._no_call_status()
    
    def _check_call(self):
        if self.__call_proc is None: return
           
            # check and read output
        rc = self.__call_proc.poll()
        txt = self.__call_proc.stdout.readline()
        print(txt, end=" ")

        #TODO borrar esto, NO SE PUEDE PORQUE EL AUDIO SE CORTA Y LA LLAMADA SE ACABA
        '''
        connected = False
        if re.search('StreamsRunning', txt): connected = True
        condition1 = (self.__sos_wav == "" or self.__sos_wav is None)
        condition2 = (self.__sos_txt != "" and self.__sos_txt is not None)
        if self.__play_sos_message and condition1 and condition2 and connected :
            sentence = " . ".join(x for x in [ self.__sos_txt ]* SOS_TXT_TIMES)
            print("  play sos message","("+str(SOS_TXT_TIMES)+"times):",self.__sos_txt)
            if self.__inform_cb is not None: 
                self.__inform_cb(sentence=sentence)
            self.__play_sos_message = False
            print("  and finish the call in",str(TIMEOUT_END_SOS_CALL),"seconds")
            t = threading.Timer(TIMEOUT_END_SOS_CALL, self.stop_call) # automatic end of call
            t.start()
            '''
        
        if self.__call_proc.returncode is not None:
                # ended call
            print(self.__call_proc.stdout.read(), end=" ")
            res = rc
            if res > RESULT_FATAL or res < RESULT_END: 
                res = RESULT_FATAL
            if self.__manually_terminated:
                res = 0
            print("CALL RESULT",rc,"->",res)
            self._ended_call(res)
        else:
                # ongoing call, keep checking
            self.__check_timer = threading.Timer(0.5, self._check_call)
            self.__check_timer.start()
        
    def _spell_number(self, number):
        #TODO si es largo no lo saco?
        #TODO tener en cuenta si el string no es number sino una dirección SIP o similar
        return " ".join([x for x in number])

    def get_ready_to_call(self, name, number, site_id, 
                          inform_cb, failure_cb, fatal_cb, end_cb, play_sos_message=False):
        '''
        Prepare the call
        '''
        if self.__calling_number is not None: 
            #TODO llamar a callback de fallo o algo o entregar una sentence de error
            return "" ""

        print("Preparing a call to", name, number, "at", site_id)
        
        self.__calling_contact = name
        self.__calling_number = number
        self.__calling_site_id = site_id
        self.__inform_cb = inform_cb
        self.__failure_cb = failure_cb
        self.__fatal_cb = fatal_cb
        self.__end_cb = end_cb
        self.__play_sos_message = play_sos_message

        sentence = self.__i18n.get('call.callingNow', {"contact_name": name, "contact_number": self._spell_number(number)})
        cdata = ""

            # Calling from a pendant satellite, remote call instead of local call
        if self.__calling_site_id != self.__base_site_id:
            cdata = INTENT_CALL_SOMEONE       + "," + \
                    self.__calling_contact    + "," + \
                    self.__calling_number     + "," + \
                    str(self.__play_sos_message) # aware the pendand through the custom_data
        
        return sentence, cdata

    def start_call(self):
        '''
        Call the selected contact, invoked when the audio session is over with the "calling..." message
        '''
        if self.__calling_number is None: 
            print("WEIRD trying to start a non prepared call")
            return
        
            # Calling from a pendant satellite, remote call instead of local call, not locally checked
        if self.__calling_site_id != self.__base_site_id:
            print("Satellite "+self.__calling_site_id+" calling to", self.__calling_contact, self.__calling_number)
            #TODO ¿hacer un timeout local por si acaso?
            print("CALL REMOTE")
            return
        
            # Local calling from the base
        print("Calling to", self.__calling_contact, self.__calling_number)
        
        #usage: ./linphone_call.sh [-v(erbose)] [-m <wav>] [-t <end_timeout_s>] [-p <playback_soundcard_name>] [-c <capture_soundcard_name>] <conf_file> <contact_number>
        working_dir = os.getcwd()
        # TODO quitar el -v
        args = [working_dir+"/linphone_call.sh", "-v" ,"-t", str(self.__timeout_end)]
        if self.__play_sos_message:
            if self.__sos_wav != "":
                args = args + ["-m", self.__sos_wav]
            else:
                print("WEIRD no configured sos_message_wav file")
        if self.__playback_sndc != "":
            args = args + ["-p", self.__playback_sndc]
        if self.__capture_sndc != "":
            args = args + ["-c", self.__capture_sndc]
        args = args + [self.__softphone_config_file, self.__calling_number]
        print("CALL EXEC",' '.join(x for x in args))
            
        try:
            self.__call_proc = subprocess.Popen(args, stdout=PIPE, stderr=STDOUT, universal_newlines=True, 
                                                shell=False)
            self._check_call()

        except Exception as e:
            print("CALL EXCEPTION",e)
            self._ended_call(RESULT_FATAL)
        
        
    #TODO tener en cuenta llamada remota para lo siguiente
        
    def stop_call(self):
        '''
        Interrupt call forcefully
        '''
        if self.__call_proc is None: return
        
        self.__manually_terminated = True
        self.__call_proc.terminate()

    def remote_ended_call(self, res):
            # remote ended call
        rc = res
        if res > RESULT_FATAL or res < RESULT_END: 
            res = RESULT_FATAL
        print("CALL RESULT REMOTE",rc,"->",res)
        self._ended_call(res)

    def is_calling(self):
        return self.__call_proc is not None
        
    def is_ready_to_call(self):
        return self.__calling_number is not None and not self.is_calling()

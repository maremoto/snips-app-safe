#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import functools

from hermes_python.hermes import Hermes
#from hermes_python.ontology import *

import datetime, time
from threading import Timer

THRESHOLD_INTENT_CONFSCORE_DROP = 0.3
THRESHOLD_INTENT_CONFSCORE_TAKE = 0.6

CREATOR = "maremoto:"
INTENT_HELP_ME =      CREATOR + "helpMe"
INTENT_CALL_SOMEONE = CREATOR + "callSomeone"
INTENT_RAISE_ALARM =  CREATOR + "raiseAlarm"
INTENT_YES =          CREATOR + "yes"
INTENT_NO =           CREATOR + "No"
INTENT_END =          CREATOR + "everythingIsOk"

# fake intents to communicate to satellites
INTENT_CALL_END =     CREATOR + "callEnd"
INTENT_CLEAR_ALARM =  CREATOR + "clearAlarm"

INTENT_FILTER_INCLUDE_ALL = [
    INTENT_HELP_ME,
    INTENT_CALL_SOMEONE,
    INTENT_RAISE_ALARM,
    INTENT_YES,
    INTENT_NO,
    INTENT_END
]

"""
INTENT_FILTER_GET_NAME = [
    INTENT_CALL_SOMEONE,
    INTENT_RAISE_ALARM,
    INTENT_END
]

INTENT_FILTER_YESNO = [
    INTENT_YES,
    INTENT_NO,
    INTENT_CALL_SOMEONE,
    INTENT_RAISE_ALARM,
    INTENT_END
]
"""

    # Waiting before launch an alarm to the final assistance message
SECONDS_LOCUTION_TO_SOUND = 6

def ahora():
    then = datetime.datetime.now()
    return (time.mktime(then.timetuple())*1e3 + then.microsecond/1e3)/1000

class SnipsMPU(object):
    '''
    Client for MQTT protocol at BASE
    '''
    
    def __init__(self, i18n, mqtt_addr, site_id, timeout_failure_seconds,
                 assistances_manager, alarm, pixels):
        self.__i18n = i18n
        self.__mqtt_addr = mqtt_addr
        self.__base_site_id = site_id
        self.__timeout_failure_seconds = timeout_failure_seconds
        
        self.__assistances_manager = assistances_manager
        self.__alarm = alarm
        self.__pixels = pixels

        self.__hermes = None
        self.__check_timer = None

    # ============
    # Checking decorators and helpers
    # ============

    def _append_text(self, sentence, text):
        if len(sentence.strip()) > 1:
            return sentence + " . " + text # para que haga espacio
        else:
            return text

    def _check_site_id(handler):
        @functools.wraps(handler)
        def wrapper(self, hermes, intent_message):
            if intent_message.site_id != self.__base_site_id:
                print("SATTELLITE SESSION:",intent_message.site_id,"!=",self.__base_site_id)
                return handler(self, hermes, intent_message)
            else:
                return handler(self, hermes, intent_message)
        return wrapper

    def _check_confidence_score(handler):
        @functools.wraps(handler)
        def wrapper(self, hermes, intent_message):
            session_id = intent_message.session_id
            if handler is None:
                return None
            '''
            if intent_message.intent.confidence_score < THRESHOLD_INTENT_CONFSCORE_DROP:
                hermes.publish_end_session(session_id, "")
                return None
                '''
            if intent_message.intent.confidence_score <= THRESHOLD_INTENT_CONFSCORE_TAKE:
                hermes.publish_continue_session(session_id, self.__i18n.get('error.doNotUnderstand'), INTENT_FILTER_INCLUDE_ALL)
                return None
            return handler(self, hermes, intent_message)
        return wrapper
    
    # ============
    # Session helpers
    # ============

    def _trace_session(self, msg):
        session_id = msg.session_id
        site_id = msg.site_id
        custom_data = msg.custom_data

        print("  sessionID:", session_id)
        print("  session site ID:",site_id)
        print("  customData:",custom_data)
        
        return session_id, site_id, custom_data

    def _session_started(self, hermes, session_started_message):

        print("# Session Started")
        session_id, site_id, custom_data = self._trace_session(session_started_message)

            # Satellite session button pushed, help requested
        if site_id != self.__base_site_id:
            if custom_data is not None and (custom_data.split(",")[0] in [ INTENT_HELP_ME , INTENT_CALL_END, INTENT_CLEAR_ALARM ]):
                return
                # The actions will be executed when the session is finished, to avoid sessions to mix
            
        assistance = self.__assistances_manager.get_assistance(site_id, hermes)
        assistance.update_session(hermes, session_id, self.__base_site_id)
    
    def _session_ended(self, hermes, session_ended_message):
        
        print("# Session Ended")
        session_id, site_id, custom_data = self._trace_session(session_ended_message)

        if site_id == self.__base_site_id or custom_data is None or custom_data == "":

            assistance = self.__assistances_manager.get_assistance(site_id, hermes)
            assistance.update_session(hermes, None, self.__base_site_id)

            # Internal messaging satellite->base
        else:
            
            time.sleep(0.5) # avoid race conditions
            action = custom_data.split(",")[0]
            
                # Satellite request for help
            if action == INTENT_HELP_ME:
                client_name=custom_data.split(",")[1]
                if self.__alarm.is_on():
                    self.__alarm.off()
                    assistance = self.__assistances_manager.get_assistance(site_id, hermes, client_name)
                    assistance.alarm_off(hermes)
                else:
                    self.handler_user_request_help(hermes, None, site_id, client_name=client_name)

                # Satellite informs of call result
            elif action == INTENT_CALL_END:
                assistance = self.__assistances_manager.get_assistance(site_id, hermes)
                assistance.remote_call_result(hermes, int(custom_data.split(",")[1]))

                # Satellite informs of alarm clear
            elif action == INTENT_CLEAR_ALARM:
                if self.__alarm.is_on():
                    self.__alarm.off()
                    assistance = self.__assistances_manager.get_assistance(site_id, hermes)
                    assistance.alarm_off(hermes)

                # No message to base, act normal
            else:
                assistance = self.__assistances_manager.get_assistance(site_id, hermes)
                assistance.update_session(hermes, None, self.__base_site_id)

    # ============
    # Intent handlers
    # ============

    #@_check_confidence_score
    def handler_user_request_help(self, hermes, intent_message, site_id=None, client_name=None):
        print("User is asking for help")

        if site_id is None:
            site_id = intent_message.site_id

        assistance = self.__assistances_manager.get_assistance(site_id, hermes, client_name)
        assistance.start(hermes)

    @_check_confidence_score
    def handler_user_gives_name(self, hermes, intent_message):
        print("User is calling to someone")
        site_id = intent_message.site_id

        name = None
        if intent_message.slots.callee_name:
            name = intent_message.slots.callee_name.first().value
    
        assistance = self.__assistances_manager.get_assistance(site_id, hermes)
        assistance.call_to_contact(hermes, name)

    @_check_confidence_score
    def handler_user_says_yes(self, hermes, intent_message):
        print("User says yes")
        site_id = intent_message.site_id

        assistance = self.__assistances_manager.get_assistance(site_id, hermes)
        assistance.yesno_answer(hermes, is_yes=True)

    @_check_confidence_score
    def handler_user_says_no(self, hermes, intent_message):
        print("User says no")
        site_id = intent_message.site_id

        assistance = self.__assistances_manager.get_assistance(site_id, hermes)
        assistance.yesno_answer(hermes, is_yes=False)

    @_check_confidence_score
    def handler_user_quits(self, hermes, intent_message):
        print("User wants to quit")
        site_id = intent_message.site_id
       
        assistance = self.__assistances_manager.get_assistance(site_id, hermes)
        assistance.quit_assistance(hermes)

    @_check_confidence_score
    def handler_raise_alarm(self, hermes, intent_message):
        print("User wants to raise the alarm")
        site_id = intent_message.site_id
        
        assistance = self.__assistances_manager.get_assistance(site_id, hermes)
        self.fatal(assistance, hermes)

    # ============
    # Check failed assistances every second
    # ============
    def _check_failed_assistances(self):
        
        #print("  ...check failed assistances\n", self.__assistances_manager)
        
        failed_assistances = self.__assistances_manager.get_failed_assistances(self.__timeout_failure_seconds)
        for assistance in failed_assistances:
            if assistance.immediate_alarm():
                sentence = self.__i18n.get('error.automaticAlarmOn')
                self.fatal(assistance, assistance.get_hermes(), sentence=sentence, call_to_default=False)
            else:
                sentence = self.__i18n.get('error.silenceAlarmOn', {"timeout": self.__timeout_failure_seconds})
                self.fatal(assistance, assistance.get_hermes(), sentence=sentence, call_to_default=True)
            break # no more than one alarm
            
        self.__check_timer = Timer(1, self._check_failed_assistances)
        self.__check_timer.start()

    # ============
    # Exported procedures
    # ============

    def pushed_button(self):
        '''
        Hardware hotword or cancel alarm
        '''
        print("User pushes the button")
        
        site_id = self.__base_site_id # action in the base
        hermes = self.__hermes
        assistance = self.__assistances_manager.get_assistance(site_id, hermes)

        self.__pixels.wakeup()
        time.sleep(0.1)
        self.__pixels.off()

        if self.__alarm.is_on():
            self.__alarm.off()
            assistance.alarm_off(hermes)

        elif assistance.is_active():
            
            if assistance.is_calling():
                print("Hang up the call")
                assistance.hang_up()
            else:
                print("The last assistance is on progress, nothing to be done")

        #TODO poner BOUNCE_TIME para el botón
 
        else:
            self.handler_user_request_help(hermes, None, site_id)

    def fatal(self, assistance, hermes, sentence="", call_to_default=False):
        '''
        Fatal error action
        '''

        if not self.__alarm.is_on():

            def alarm_off_callback():
                assistance.alarm_off(hermes)

                # delay alarm on with a callback to allow emergency call
            if call_to_default:
                def call_to_default_callback():
                    self.__alarm.on(delay=SECONDS_LOCUTION_TO_SOUND, off_callback=alarm_off_callback)
                assistance.alarm_on(hermes, sentence=sentence, call_to_default_callback=call_to_default_callback)

                # alarm on now
            else:
                assistance.alarm_on(hermes, sentence=sentence)
                self.__alarm.on(delay=SECONDS_LOCUTION_TO_SOUND, off_callback=alarm_off_callback)

        else:
            print("[Alarm] already on")

    def start_block(self):
        '''
        Protocol start
        '''

            # Start check timer
        self._check_failed_assistances()

            # Subscribe to voice intents
        with Hermes(self.__mqtt_addr
                     ,rust_logs_enabled=True #TODO quitar
                    ) as h:
            self.__hermes = h
            h.subscribe_intent(INTENT_HELP_ME, self.handler_user_request_help) \
                .subscribe_intent(INTENT_CALL_SOMEONE, self.handler_user_gives_name) \
                .subscribe_intent(INTENT_YES, self.handler_user_says_yes) \
                .subscribe_intent(INTENT_NO, self.handler_user_says_no) \
                .subscribe_intent(INTENT_RAISE_ALARM, self.handler_raise_alarm) \
                .subscribe_intent(INTENT_END, self.handler_user_quits) \
                .subscribe_session_ended(self._session_ended) \
                .subscribe_session_started(self._session_started) \
                .loop_forever()
                
            '''
                .loop_start()
            while True:
                time.sleep(1)

                #TODO aclarar si funciona y si se puede poner aquí vigilar asistencias fallidas
                '''

    def stop(self):
        '''
        Stop working
        '''

            # Cancel check timer
        if self.__check_timer is not None:
            self.__check_timer.cancel()
            self.__check_timer = None

            # Alarm stop
        self.__alarm.off(dismiss_callback=True)

            # Stop client
        self.__hermes.loop_stop()
        self.__hermes = None

             

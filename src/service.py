#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import functools
import datetime, time

from .snipsMPU import INTENT_FILTER_INCLUDE_ALL, INTENT_END

SUGGESTIONS_PER_SENTENCE = 3

def set_not_none_dict_value(to_update, update):
    to_update = to_update or {}
    for key, value in update.iteritems():
        if value is not None:
            to_update[key] = value
    return to_update

def ahora():
    then = datetime.datetime.now()
    return (time.mktime(then.timetuple())*1e3 + then.microsecond/1e3)/1000

def tracetime(txt):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), txt))
    
# ===============================
# Manager class
# ===============================

class AssistancesManager(object):
    '''
    Manages a dict of assistances, one per site_id (base and pendants)
    '''
    
    def __init__(self, phone, i18n, 
                 contacts, client_name="", suggestions_per_sentence=SUGGESTIONS_PER_SENTENCE):
        self.__phone = phone
        self.__i18n = i18n
        self.__contacts = contacts
        self.__client_name = client_name
        assert suggestions_per_sentence > 0
        self.__suggestions_per_sentence = suggestions_per_sentence

        self.__assistances = {}

    # ============
    # Internal helpers
    # ============

    def __printme__(self):
        res = "["
        for key in self.__assistances:
            res = res + "\n" + self.__assistances[key].__printme__()
        res = res+" ]"
        return res
        
    def __repr__(self): return self.__printme__()
    def __str__(self):  return self.__printme__()

    # ============
    # Exported procedures
    # ============

    def get_assistance(self, site_id, hermes, client_name=None):
        
        if not site_id in self.__assistances:
            if client_name is None or client_name == "":
                client_name = self.__client_name # base client name
            self.__assistances[site_id] = Assistance(site_id, hermes, self.__phone, self.__i18n, 
                                                      self.__contacts, client_name, self.__suggestions_per_sentence)

        return self.__assistances[site_id]

    def get_failed_assistances(self, timeout_failure_seconds):

        failed = []
        
        for site_id in self.__assistances:
            assistance = self.__assistances[site_id]
            if assistance.is_failed(timeout_failure_seconds):
                failed.append(assistance)
                
        return failed

# ===============================
# Assistance class
# ===============================

class Assistance(object):
    '''
    Assistance to a site_id, end to end with lifecycle
    '''
    
    def __init__(self, site_id, hermes, phone, i18n, 
                 contacts, client_name="", suggestions_per_sentence=SUGGESTIONS_PER_SENTENCE):
        assert site_id is not None
        assert hermes is not None

        self.__site_id = site_id
        self.__hermes = hermes
        self.__session_id = None # last active session_id

        self.__phone = phone
        self.__i18n = i18n
        
        self.__conversation = Conversation(i18n, contacts, client_name, suggestions_per_sentence)
        self.__last_activity_time = None

    # ============
    # Internal helpers
    # ============

    def __printme__(self):
        return "<assistance site_id:%s sess_id:%s ei:%.2f %s>" % (self.__site_id, 
                                                                              self.__session_id, 
                                                                              self._elapsed_inactivity(),
                                                                              self.__conversation.__printme__())
        
    def __repr__(self): return self.__printme__()
    def __str__(self):  return self.__printme__()

    def _elapsed_inactivity(self):
        if self.__last_activity_time is None:
            return 0.0
        elif self.__last_activity_time < 0:
            return float('inf') # direct failure
        else:
            return ahora() - self.__last_activity_time

    def _append_text(self, sentence, text):
        if len(sentence.strip()) > 1:
            return sentence + " . " + text # para que haga espacio hablando
        else:
            return text

    # ============
    # Hermes sessions, one assistance session may involve more than one hermes session
    # ============

    def update_session(self, hermes, session_id, base_site_id):
        self.__session_id = session_id
        if session_id is None:
            # session ended, do a call if it is scheduled
            if self.__phone.is_ready_to_call():
                '''
                if self.__site_id != base_site_id:
                    self.__hermes = None  # calling from satellite taintes hermes?
                    '''
                self.__phone.start_call()
        '''
        elif self.__hermes is None:
            self.__hermes = hermes # get new hermes object
            '''

    def _start_conversation(self, hermes, sentence, intent_filter=INTENT_FILTER_INCLUDE_ALL, custom_data=""):
        print("## Start conversation ei:%.2f cdata:%s" % (self._elapsed_inactivity(),custom_data))

        if self.__hermes is None:
            print("WEIRD START: No hermes")
            return

            # Programatically initiated session
        if self.__session_id is None:
            self.__hermes.publish_start_session_action(
                                       site_id=self.__site_id, 
                                       session_init_text=sentence, 
                                       session_init_intent_filter=intent_filter,
                                       session_init_can_be_enqueued=False,
                                       session_init_send_intent_not_recognized=False,
                                       custom_data=custom_data )
            
            # Snips initiated session
        else:
            self._continue_conversation(hermes, sentence, intent_filter, custom_data)

    def _continue_conversation(self, hermes, sentence, intent_filter=INTENT_FILTER_INCLUDE_ALL, custom_data=""):
        print("## Continue conversation ei:%.2f cdata:%s" % (self._elapsed_inactivity(),custom_data))

        if self.__session_id is not None:
            if hermes is None:
                print("WEIRD CONTINUE: hermes is None")
                hermes = self.__hermes
                if self.__hermes is None:
                    print("WEIRD CONTINUE: No hermes")
                    return
            hermes.publish_continue_session(self.__session_id, sentence, intent_filter, custom_data=custom_data)
        else:
            print("WEIRD CONTINUE: No session to continue talking")

    def _end_conversation(self, hermes, sentence=""):
        print("## End conversation ei:%.2f" % (self._elapsed_inactivity()))

        if self.__session_id is not None:
            if hermes is None:
                print("WEIRD END: hermes is None")
                hermes = self.__hermes
                if self.__hermes is None:
                    print("WEIRD END: No hermes")
                    return
            hermes.publish_end_session(self.__session_id, sentence)
        else:
            print("WEIRD END: No session to say goodbye")

    def _do_notification(self, hermes, sentence, end=False, custom_data=""):
        print("## Notify ei:%.2f" % (self._elapsed_inactivity()))

        if self.__hermes is None:
            print("WEIRD NOTIFY: No hermes")
            return

            # Programatically initiated notification
        if self.__session_id is None:
            self.__hermes.publish_start_session_notification(
                                               site_id=self.__site_id, 
                                               session_initiation_text=sentence,
                                               custom_data=custom_data )
            # Pre-existent Snips initiated session
        else:
            if hermes is None:
                hermes = self.__hermes
            if not end:
                self._continue_conversation(hermes, sentence, INTENT_FILTER_INCLUDE_ALL, custom_data=custom_data)
            else:
                if custom_data != "" :
                    self._end_conversation(hermes, "")
                    self.__hermes.publish_start_session_notification(
                                               site_id=self.__site_id, 
                                               session_initiation_text=sentence,
                                               custom_data=custom_data )
                else:
                    self._end_conversation(hermes, sentence)

    # ============
    # Assistance sessions
    # ============

    def start(self, hermes):
        
        self.__last_activity_time = ahora()
        
        print("### Start assistance", self.__printme__())

        sentence = self.__conversation.start()
        self._start_conversation(hermes, sentence)
        
    def call_to_contact(self, hermes, name):
        
        do_call, sentence, name, number = self.__conversation.call_to_contact(name)
        if do_call:
            self.__last_activity_time = None # unkown call duration
            sphone, cdata = self.__phone.get_ready_to_call(name, number, self.__site_id,
                                                    self.inform,
                                                    self.call_failure, 
                                                    self.fatal, 
                                                    self.call_finished)
            self._do_notification(hermes, sphone, end=True, custom_data=cdata)
        else:
            self.__last_activity_time = ahora()
            self._continue_conversation(hermes, sentence)

    def yesno_answer(self, hermes, is_yes):
        
        if is_yes:
            sentence, end = self.__conversation.affirmative_answer()
        else:
            sentence, end = self.__conversation.negative_answer()

        if end:
            self._do_notification(hermes, sentence, end=True, custom_data=INTENT_END)
            self.end()
        else:
            self._continue_conversation(hermes, sentence)
            self.__last_activity_time = ahora()

    def quit_assistance(self, hermes):
        
        sentence, end = self.__conversation.i_am_ok()

        if end:
            self._do_notification(hermes, sentence, end=True, custom_data=INTENT_END)
            self.end()
        else:
            self._continue_conversation(hermes, sentence)
            self.__last_activity_time = ahora()

    def call_failure(self, sentence=""):
        
        self.__last_activity_time = ahora()
        
        sentence = self._append_text(sentence, self.__conversation.start())
        self._start_conversation(self.__hermes, sentence)
        
    def call_finished(self, sentence=""):
        
        self.__last_activity_time = ahora()

        sentence = self._append_text(sentence, self.__conversation.are_you_ok())
        self._start_conversation(self.__hermes, sentence)

    def remote_call_result(self, hermes, res):

        self.__last_activity_time = ahora()

        '''
        if self.__hermes is None: 
            self.__hermes = hermes
            '''
        self.__phone.remote_ended_call(res)        

    def inform(self, hermes=None, sentence=""):
        '''
        Initiated by the assistant
        '''
            # __last_activity_time not updated, information means no activity from the user
        if sentence != "":
            self._do_notification(hermes, sentence)

    def fatal(self, sentence=""):
        
        self.__last_activity_time = -1 # inmediate raise alarm

        print("## Failed assistance", self.__printme__())
        if sentence != "":
            self._do_notification(self.__hermes, sentence)
        
    def alarm_on(self, hermes, sentence="", call_to_default_callback=None):
        
        self.__last_activity_time = None # no more failures
        
        def final_callback(sentence=""):
            sentence = self._append_text(sentence, self.__i18n.get('alarm.on'))
            self._do_notification(hermes, sentence, end=True, custom_data=INTENT_END)
            self.end()

        if call_to_default_callback is not None:

                # Call default number and when it ends, raise alarm with callback
            
            def final_call_callback(sentence=""):
                final_callback(sentence)
                call_to_default_callback()
            
            name, number = self.__conversation.call_to_default_contact()
            sphone, cdata = self.__phone.get_ready_to_call(name, number, self.__site_id,
                                                    self.inform,
                                                    final_call_callback,  #call_failure
                                                    final_call_callback,  #fatal_error
                                                    final_call_callback,   #call_finished
                                                    play_sos_message=True) 
            self._do_notification(hermes, self._append_text(sentence, sphone), custom_data=cdata)
        else:
            final_callback(sentence)

    def alarm_off(self, hermes):
        
        self.__last_activity_time = ahora()

        sentence = self.__i18n.get('alarm.off')
        sentence = self._append_text(sentence, self.__conversation.are_you_ok())
        self._start_conversation(hermes, sentence)

    def hang_up(self):
        self.__phone.stop_call()

    def end(self):
        
        self.__last_activity_time = None

        print("### End assistance", self.__printme__())

    def is_failed(self, timeout_seconds):
        return self._elapsed_inactivity() > timeout_seconds

    def immediate_alarm(self):
        if self.__last_activity_time is None: return False
        return self.__last_activity_time < 0
    
    def is_active(self):
        if self.__session_id is not None:
            return True
        if self.__phone.is_calling():
            return True
        return False

    def is_calling(self):
        return self.__phone.is_calling()

    def get_hermes(self):
        return self.__hermes

# ===============================
# Conversation class
# ===============================

class Conversation(object):
    '''
    Conversation piece for Assistance, end to end with lifecycle
    '''
    
    def __init__(self, i18n, contacts, client_name="", suggestions_per_sentence=SUGGESTIONS_PER_SENTENCE):

        self.__i18n = i18n
        self.__contacts = contacts
        self.__client_name = client_name
        assert suggestions_per_sentence > 0
        self.__suggestions_per_sentence = suggestions_per_sentence
        
        self._reset_state()

    # ============
    # Internal helpers
    # ============

    def __printme__(self):
        return "<conversation name:%s q_ok:%s>" % (self.__client_name,
                                                   self.__session_state["questioning_ok"])
        
    def __repr__(self): return self.__printme__()
    def __str__(self):  return self.__printme__()

    def _reset_state(self):
        self.__session_state = {
            "next_suggestion_id": 0,
            "questioning_ok": False
        }

    def _init_message(self):
        return self.__i18n.get('conversation.whoToCall')

    def _next_suggestion(self):
        contacts_list = self.__contacts.list_entities()
        L = len(contacts_list)

            # First suggestion
        I = self.__session_state['next_suggestion_id']
        suggested_name = contacts_list[I]
        sentence = self.__i18n.get('conversation.suggestContact', {"contact_name": suggested_name})
            # Add more
        for i in range(2,self.__suggestions_per_sentence):
            I = (I+1) % L
            suggested_name = contacts_list[I]
            sentence = sentence + " " + self.__i18n.get('conversation.listUnion', {"contact_name": suggested_name})
            
        I = (I+1) % L
        self.__session_state['next_suggestion_id'] = I
        return sentence

    def _question_message(self):
        return self.__i18n.get('conversation.areYouOk', {"client_name": self.__client_name})

    def _sorry_message(self):
        return self.__i18n.get('conversation.sorry')

    def _goodbye_message(self):
        return self.__i18n.get('conversation.goodBye', {"client_name": self.__client_name})

    def _append_text(self, sentence, text):
        if len(sentence.strip()) > 1:
            return sentence + " . . . " + text # para que haga espacio
        else:
            return text

    # ============
    # Checking decorators
    # ============
    def _check_i_am_questioning(handler):
        @functools.wraps(handler)
        def wrapper(self):
            if not self.__session_state['questioning_ok'] :
                print("WARNING: intent-Yes-No triggered outside of questioning")
                return self._init_message(), False
            else:
                return handler(self)
        return wrapper
    
    # ============
    # Exported procedures
    # ============

    def start(self):
        self._reset_state()
        return self._init_message()

    def call_to_default_contact(self):
        '''
        Invoked to do a default call
        '''
        
        name, number = self.__contacts.get_default()
        self.__session_state['pending_suggestion'] = None
        
        return name, number

    def call_to_contact(self, name):
        '''
        Invoked when a contact has beeen selected
        Returns :
            if a call has to be done
            next sentence to say error (if not)
            called name
            called number
        '''
        
        number = 'null'
        if name is not None: 
            number = self.__contacts.get(name)
        else:
            name = ""

            # Unable to call, ask again with more info
        if number == 'null':
            sentence = self.__i18n.get('error.noContact')
            if name != "":
                sentence = self.__i18n.get('error.unknownContact', {"contact_name": name})
            sentence = self._append_text(sentence, self._next_suggestion())
            sentence = self._append_text(sentence, self._init_message())
            return False, sentence, None, None
        
            # Do the call
        else:
            self.__session_state['pending_suggestion'] = None
            return True, "", name, number
    
    def are_you_ok(self):
        '''
        In some situations we want to confirm that the user is Ok
        '''
        self.__session_state['questioning_ok'] = True
        return self._question_message()

    def ask_again(self):
        '''
        If no recent valid answer, ask again
        '''
        if self.__session_state['questioning_ok']:
            return self._question_message()
        else:
            return self._init_message()
    
    @_check_i_am_questioning
    def affirmative_answer(self):
        '''
        The user says "yes"
        Returns the next message and if this is the end of the conversation
        '''
        self._reset_state()
        return self._goodbye_message(), True

    @_check_i_am_questioning
    def negative_answer(self):
        '''
        The user says "no"
        Returns the next message and if this is the end of the conversation
        '''
        self.__session_state['questioning_ok'] = False
        return self._sorry_message()+ " " + self._init_message(), False

    def i_am_ok(self):
        '''
        The user says "i am ok, stop bothering me"
        Returns the next message and if this is the end of the conversation
        '''
        if not self.__session_state['questioning_ok'] :
            return self.are_you_ok(), False
        else:
            self._reset_state()
            return self._goodbye_message(), True


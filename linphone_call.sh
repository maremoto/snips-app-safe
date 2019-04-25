#!/bin/bash

# 
# Call script
# return 0=ok 1=not_connected 2=system_error 3=bad_usage_or_config
#

LOGFILE=$(dirname $(realpath $0))/linphone_call.log
> $LOGFILE; chmod 666 $LOGFILE > /dev/null 2>&1
#if [[ $(whoami) == "_snips-skills" ]]; then LOGFILE=/dev/stdout; fi

# Check binaries

type linphonec > /dev/null 2>&1
if [[ $? -ne 0 ]]; then echo "NOT FOUND linphone console binary \"linphonec\""; exit 2; fi
type linphonecsh > /dev/null 2>&1
if [[ $? -ne 0 ]]; then echo "NOT FOUND linphone command shell binary \"linphonecsh\""; exit 2; fi

# Hardcoded config

#SOUND_SERVER=Pulseaudio
SOUND_SERVER=ALSA

PRE_TIMEOUT=1 # do not rush into communications
TIMEOUT_REGISTER=3 # wait for SIP registrar to get done
TIMEOUT_CONNECT=20 # wait for the call to connect
TIMEOUT_SOS=10 # wait after the S.O.S. message is played

# Default config

PLAYBACK_SOUNDCARD="seeed-2mic-voicecard"
CAPTURE_SOUNDCARD="seeed-2mic-voicecard"

TIMEOUT_END=900 # wait for the call to end
REGISTRABLE_PROXY=0
HELP_MSG_WAV=""
VERBOSITY="-d 0"

# Check parameters

USAGE="usage: $0 [-v(erbose)]"
USAGE=$USAGE" [-m <help_message_wav>] [-t <end_timeout_s> def: $TIMEOUT_END]"
USAGE=$USAGE" [-p <playback_soundcard_name> def: $PLAYBACK_SOUNDCARD] [-c <capture_soundcard_name> def: $CAPTURE_SOUNDCARD]"
USAGE=$USAGE" <conf_file> <contact_number>"

while getopts "vt:m:p:c:" opt #se pone ":" detrás de cada flag que tenga parámetros
do
  case $opt in
                v) VERBOSITY="-d 6 -S" ;; # -d = verbosity 0-6 (0=nothing) # -S = show status msgs
                t) if [[ $OPTARG =~ ^[0-9]+$ ]]; then TIMEOUT_END=$OPTARG; fi ;; # wait for the call to end
                m) HELP_MSG_WAV=$OPTARG ;; # wav file to play voice message asking for help
                p) PLAYBACK_SOUNDCARD=$OPTARG ;; 
                c) CAPTURE_SOUNDCARD=$OPTARG ;; 
                \?) echo $USAGE; exit 3 ;; # syntax error
        esac
done
shift $(($OPTIND - 1))

if [[ $# -ne 2 ]]; then echo $USAGE; exit 3; fi
CONFIG_FILE=$1
if [[ ! -f $CONFIG_FILE ]]; then echo "NOT FOUND configuration file "$CONFIG_FILE; exit 3; fi
NUMBER=$2

MSG_SECONDS=0
if [[ ! -z $HELP_MSG_WAV ]]
then
  if [[ ! -f $HELP_MSG_WAV ]]; then echo "NOT FOUND help wav message file "$HELP_MSG_WAV; exit 3; fi
  multiplier=3600
  MSG_SECONDS=1 # at least one
  for term in $(soxi $HELP_MSG_WAV | grep  Duration | cut -d: -f2- | cut -d= -f1 | tr -d " " | tr ":" " " | tr "." " ")
  do
	((MSG_SECONDS=$MSG_SECONDS+($term*$multiplier)))
	((multiplier=$multiplier/60))
  done
fi

function configure()
{
  # Get configuration data
  echo " ... reading configuration"
  CMD=$(awk -F= 'BEGIN {section=""; host=""; username=""; passwd=""; registrable_proxy=0;}
  /\[[a-z]/ { section=$0; next; }
  {
	var=$1; value=$2
	if (section ~ /\[auth_info/) {
		if (var == "username") username=value;
		if (var == "passwd") passwd=value;
		if (var == "realm") host=value;
	}
	if (section ~ /\[proxy/) {
		if (var == "reg_sendregister") registrable_proxy=value;
	}
  }
  END {
	if ((host == "") || (username == "") || (passwd == "")) { 
		print("ERROR: invalid or inexistent [auth_info_X] configuration in '$CONFIG_FILE'");
		exit(1); 
	}
	print("HOST="host";USERNAME="username";PASSWORD="passwd";REGISTRABLE_PROXY="registrable_proxy);
	exit(0);
  }' $CONFIG_FILE)
  res=$?
  if [[ $res -ne 0 ]]; then echo $CMD; stop; exit 3; fi
  eval $CMD

  # Config clean
  echo '
[sound]
echocancellation=1

[video]
enabled=0
size=vga' > ~/.linphonerc

  # Database clean and recreation
  mkdir -p ~/.local/share/linphone/
return #TODO revisar si lo quiero hacer
  rm -f ~/.local/share/linphone/linphone.db
  linphonec <<:FIN > /dev/null
quit
:FIN
}

function sound() {
  # set the proper sound devices
  echo " ... setup sound"
  playback_id=$(linphonecsh generic "soundcard list" | grep $PLAYBACK_SOUNDCARD | grep $SOUND_SERVER | head -1 | cut -d: -f1)
  if [[ -z $playback_id ]]; then echo "ERROR unable to find playback sound device"; stop; exit 2; fi
  capture_id=$(linphonecsh generic "soundcard list" | grep $CAPTURE_SOUNDCARD | grep $SOUND_SERVER | head -1 | cut -d: -f1)
  if [[ -z $capture_id ]]; then echo "ERROR unable to find capture sound device"; stop; exit 2; fi
  linphonecsh generic "soundcard capture $capture_id"
  check_error $? "set_capture_snd"
  linphonecsh generic "soundcard playback $playback_id"
  check_error $? "set_playback_snd"
  linphonecsh generic "soundcard ring $playback_id"
  check_error $? "set_ring_snd"
}

function start() {
  # recover from faulty sessions
  sudo pkill linphonec

  # stop snips audio server to take control of the audio
  #sudo systemctl stop snips-audio-server; sleep 1
  if [[ $(whoami) != "_snips-skills" ]]; then sudo systemctl stop snips-audio-server; sleep 1; fi
  
  # set configuration
  configure

  # start linphonec daemon
  echo " ... starting daemon"
  traceout="-l "$LOGFILE
  linphonecsh init -b $CONFIG_FILE -c ~/.linphonerc $VERBOSITY $traceout 
  check_error $? "init"
  sleep 1

  # setup sound
  sound

  # see proxies and check register in proxy
  PROXYREG=0
  if [[ $REGISTRABLE_PROXY -eq 1 ]]
  then
    echo " ... proxy registration"
    sleep $PRE_TIMEOUT # wait to regitration resubmit for address changes
    i=0
    while [ True ]
    do
	registered=$(linphonecsh generic "proxy list" | grep registered: | cut -d: -f2 | tr -d " ")
	if [[ -z $registered ]]; then echo '     no proxy'; break; fi # NO PROXY
    	echo '     registered_proxy: '$registered
	if [[ $registered == "yes" ]]; then PROXYREG=1; else PROXYREG=0; fi
	sleep 1
	((i+=1))
    	if [[ $i -ge $TIMEOUT_REGISTER ]] 
	then
	  if [[ $PROXYREG -ne 1 ]]; then echo "ERROR unable to register"; stop; exit 2; fi
	  break
        fi
    done
  fi

  # register to destination if not in proxy
  REG=0
  if [[ $PROXYREG -ne 1 ]]
  then
    echo " ... registration"
    sleep $PRE_TIMEOUT # wait to regitration resubmit for address changes
    REG_HOST=$HOST
    linphonecsh register --host $REG_HOST --username $USERNAME --password $PASSWORD
    check_error $? "register"
    i=0
    while [ True ]
    do
  	registered=$(linphonecsh generic "status register")
    	echo '     '$registered
	if [[ $registered =~ identity ]]; then REG=1; else REG=0; fi
	sleep 1
	((i+=1))
    	if [[ $i -ge $TIMEOUT_REGISTER ]]
	then
	  if [[ $REG -ne 1 ]]; then echo "ERROR unable to register"; stop; exit 2; fi
	  break
	fi
    done
  fi
}

function call() {
  # call
  echo " ... calling to "$1
  linphonecsh generic "call sip:$1@$HOST --audio-only"
  check_error $? "call"

  # wait to end
  msg_played=0
  i=0
  while [ True ]
  do
    info=$(linphonecsh generic calls | grep ^[0-9])
    state=$(echo $info | cut -d'|' -f3 | tr -d " ")
    if [[ $state == StreamsRunning ]]; then CONNECTED=1; fi
    if [[ -z $info ]]; then break; fi # llamada terminada por si misma
    echo '     '$info
	# play help message if required
    if [[ $msg_played -ne 1 ]] && [[ $CONNECTED -eq 1 ]] && [[ ! -z $HELP_MSG_WAV ]]
    then
	msg_played=1
	sleep 3
	echo " ... playing 3 times " $HELP_MSG_WAV " (each time lasts "$MSG_SECONDS" s)"
	linphonecsh generic pause
	linphonecsh generic "play $HELP_MSG_WAV"
	sleep $MSG_SECONDS
	sleep $MSG_SECONDS
	sleep $MSG_SECONDS
	linphonecsh generic resume
	sleep $TIMEOUT_SOS
	echo " ... terminating sos call after "$TIMEOUT_SOS" seconds of last message"
	linphonecsh generic terminate
    fi
    sleep 1
    ((i+=1))
    if [[ $i -ge $TIMEOUT_CONNECT ]] && [[ $CONNECTED -ne 1 ]]; then terminate; break; fi
    if [[ $i -ge $TIMEOUT_END ]]; then terminate; break; fi
  done
}

function terminate()
{
  # terminate 
  echo " ... terminating call by end timeout of "$TIMEOUT_END" seconds"
  linphonecsh generic terminate
}

function stop() {
  # unregister
  echo " ... unregister"
  linphonecsh unregister

  # end
  echo " ... stop daemon"
  linphonecsh exit

  # recover from faulty sessions
  sudo pkill linphonec

  # recover snips server
  #sudo systemctl start snips-audio-server; sleep 1
  if [[ $(whoami) != "_snips-skills" ]]; then sudo systemctl start snips-audio-server; sleep 1; fi
}

function check_error() {
  # if there is an error: exit with error code
  if [[ $1 -ne 0 ]]; then echo "ERROR "$1" "$2; stop; exit 2; fi
}

function signal_catch() {
  # signal termination
  echo " ... signal termination"
  stop
  if [[ $CONNECTED -ne 1 ]]; then exit 1; fi
  exit 0
}

#
# MAIN
#

trap signal_catch SIGTERM SIGINT
CONNECTED=0
start
call $NUMBER
stop
if [[ $CONNECTED -ne 1 ]]; then exit 1; fi
exit 0


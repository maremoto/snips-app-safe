#!/bin/bash

# 
# Failure recovery script to force back to normal after a call
#

function reset() {
  type linphonecsh > /dev/null 2>&1
  if [[ $? -eq 0 ]]
  then
      # end call
      echo " ... forcefully end call"
      linphonecsh generic terminate

      # unregister
      echo " ... unregister"
      linphonecsh unregister

      # end
      echo " ... stop daemon"
      linphonecsh exit
  else
      echo "WARNING NOT FOUND linphone command shell binary \"linphonecsh\""
  fi

  # recover from faulty sessions
  sudo pkill linphonec 

  # recover snips server
  sudo systemctl start snips-audio-server
}

function clean() {
  echo " ... cleaning "$1

  cd $1
  sudo rm -f .linphonerc
  sudo rm -f .linphone-zidcache
  mkdir -p .local/share/linphone/
  chmod 777 .local/share/linphone/
  sudo rm -f .local/share/linphone/linphone.db
  linphonec <<:FIN
quit
:FIN
  cd - > /dev/null
}


#
# MAIN
#
reset
clean /var/lib/snips/skills/snips-app-safe
clean ~

exit 0

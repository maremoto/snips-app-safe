# snips-app-safe
SAFE APP code

[![MIT License](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/maremoto/snips-app-safe/blob/master/LICENSE)

This action code performs the SAFE (Snips Assistant For Emergencies) procedures as a human interface for Snips Voice Platform.

## Features

With the hotword "hey Snips" the assistant starts to listen and initiates its procedure:
- Help for emergency dialogue with list of contact people+numbers to call in case of emergency.
- Alarm bell raise or clear management.
- Internet VoIP-to-mobile adapter to call or calls to be performed.

### Intents

- helpMe - start assistance
- callSomeone - do a call to a given contact
- everythingIsOk - stop assistance
- alarm - raise the alarm to alert the neighbors

### Button

Pressing the button will be equivalent to the hotword + intent "helpMe".

## Hardware and third party software

The app is developed for raspberry pi with reSpeaker2Mic hat (for button, leds, microphone and speaker capabilities), and fully tested in [Snips - Seeed voice interaction base kit](https://www.seeedstudio.com/Snips-Voice-Interaction-Base-Kit.html).

The snips voice platform will be installed in the [Raspberry pi B+](https://docs.snips.ai/getting-started/quick-start-raspberry-pi).
The app requires linphone software console [linphonec](https://www.linphone.org/technical-corner/linphone) to be deployed and available in command line.

## Installation

#### By using `sam`:

> Beware that `sam` only supports Raspberry Pi platform. For other platforms, please refer to manual installation guide.

```bash
sam install actions -g https://github.com/maremoto/snips-app-safe.git
```

To be able to access GPIO and SPI hardware, `_snips-skills` user need to be appended with `spi`, `gpio`, `audio` groups. Run the following command on your snips device:

```bash
sudo usermod -a -G spi,gpio,audio _snips-skills
```

#### Manually:

> If there is no `snips-skill-server` installed yet, please run the following command:
>
> `sudo apt-get install snips-skill-server`

Firstly, add your current user to the `snips-skills-admin` group:

```bash
sudo usermod -a -G snips-skills-admin $USER
```

Secondly, add `_snips-skills` user to the `spi`, `gpio`, `audio` groups:

```bash
sudo usermod -a -G spi,gpio,audio _snips-skills
```

Finally, clone the repository and manually run `setup.sh`:

```bash
git clone  https://github.com/maremoto/snips-app-safe.git
cp -r snips-app-safe /var/lib/snips/skills/
cd /var/lib/snips/skills/snips-app-safe
./setup.sh
```

## Snips configuration for satellite pendant support

In  order to make available the service to satellite pendants of SAFE, the Snips configuration will be updated this way:

```bash
sudo vi /etc/snips.toml

	#at [snips-audio-server]
    bind = "safebase@mqtt"

	#at [snips-hotword]
    audio = ["safebase@mqtt", "safependant0@mqtt"]

sudo systemctl restart snips-*
```

If there is more than one pendant, add further elements at the `[snips-hotword]` section in the `audio` list.

## App configuration

All the configuration options of the app are written in `config.ini` file at `/var/lib/snips/skills/snips-app-safe`. 
There are three sections used to represent three different kinds of parameters. Please refer to your actual usage to modify.
> ***Whenever the configuration is modified, the skill will need a restart:***
```bash
sudo systemctl restart snips-skill-server
```

### `[secret]`

This section contains the user options that which will be asked to input from user during the installation. (Using sam)

| Config | Description | Default |
| --- | --- | --- |
| `local` | Language of the voice interface Hardware, only english is supported by now. | `en_US` |
| `client_name` | Customised name that the voice interface uses to adress the customer. ***Optional*** | ***Empty*** |
| `default_contact` | Default contact to call in case of emergency. | `Emergency` |

> ***The `default_contact` has to exist among the configured contacts (see below)***

### `[global]`

This section contains some options that usually will not change if deployed with tested hardware.

| Config | Description | Value | Default |
| --- | --- | --- | --- |
| `mqtt_host` | MQTT host name | `<ip address>`/`<hostname>` | `localhost` |
| `mqtt_port` | MQTT port number | `<mqtt port>` | `1883` |
| `site_id` | Snips device ID | Refering to the actual `snips.toml` | `safebase` |
| `button_gpio_bcm` | Button gpio pin | Depends on the hardware configuration | `17` |
| `pixels_n` | LEDs id | Depends on the hardware configuration | `3` |
| `alarm_gpio_bcm` | Relay gpio pin | Depends on the hardware configuration | `12` |

#### `[phone]`

Sofpthone invoke configuration, .

| Config | Description | Default |
| --- | --- | --- |
| `softphone_config_file` | Softphone configuration file name (relative to app path) with linphone formatting | linphonerc.ini |
| `timeout_call_end` | Seconds to wait for a call to end, avoid inconsistent situations | `900` |
| `capture_soundcard_name` | ALSA name of the capture sound card | `seeed-2mic-voicecard` |
| `playback_soundcard_name` | ALSA name of the playback sound card | `seeed-2mic-voicecard` |
| `sos_message_wav` | Wav file name (relative to app path) to play when a default call is made. ***Optional*** | ***Empty*** |

> ***The `linphonerc.ini` file in the project is only a sample, and has to be modified***

### `[static]`

This section only contains one option, `config_ver`, which is used to track the `config.ini` file version. **You are not supposed to change this value at any time.**

A general update will work basing the old `config.ini` without any problem if there is no change required for adding new config options. But this also means that the config entities might be changed at some point. During the installation/updating, `setup.sh` will always check if the old `config.ini` file meets the latest requirement. If it doesn't, it will be overwrote by a new default config. The old config information will be dropped.

In this case, please do make sure that you have to re-modify the options' value after the installation/updating if needed.

## Contacts for calls

The contact names and phone numbers are in the `contacts.json` file.
Initially it is populated only with standard Emergency (112) and Police (091) numbers, and should be customized.
The `.json` format involves only `name: phone` fields.
Regular numbers should have the country code with plus prepending the number: `***+34***655555555`
You can use the same number for more than one field, for example:
```json
{
    "Emergency": "112",
    "Emergencies": "112",
    "My daughter": "+34655555555",
    "Anne": "+34655555555"
}
```

> ***After modifying the contacts file, they have to be injected in Snips platform:***
```bash
cd /var/lib/snips/skills/snips-app-safe
. venv/bin/activate
inject_contacts.py
deactivate
```

## Record your own sos message

The sos mesage is a wav file that will be automatically played when the system takes the default call actions (when the client is not able to skpeak or indicate who to call).
You should record it with a clear message, e.g. "Please help, there is an emergency at 5 Elm st.".

## To Do

- Separate softphone management for base and satellites.

## Copyright

This library is provided by [Alaba](https://www.alaba.io) as Open Source software. See [LICENSE](https://github.com/maremoto/snips-app-safe/blob/master/LICENSE) for more information.

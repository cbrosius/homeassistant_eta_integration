[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

# ETA Integration for Home Assistant
Integration of ETA (Heating) sensors and switches to Home Assistant

This integration uses the [ETA REST API](https://www.meineta.at/javax.faces.resource/downloads/ETA-RESTful-v1.2.pdf.xhtml?ln=default&v=0) to get sensor values and set switch states from the ETA pellets heating unit.

This is a fork of [nigl's repo](https://github.com/nigl/homeassistant_eta_integration) with the following changes:
- Friendly sensor names
- Shows the current values for all sensors during configuration
    - This makes it way easier to select the relevant sensors
- Implemented Switches
- Implemented Text Sensors (state of some endpoints, e.g. `Bereit` (`Ready`) or `Heizen` (`Heating`) for the boiler)
- Implemented error sensors:
    - A binary sensor, which activates if the ETA terminal reports at least one error
    - A sensor, which shows the number of active errors
    - A sensor, which shows the latest active error message
- Implemented error events ([details](#error-events))

## Installation:
This integration can be configured directly in Home Assistant via HACS:

1. Go to `HACS` -> `Integrations` -> Click on the three dots in the top right corner --> Click on `Userdefined repositories`
1. Insert `https://github.com/Tidone/homeassistant_eta_integration` into the field `Repository`
1. Choose `Integration` in the dropdown field `Category`.
1. Click on the `Add` button.
1. Then search for the new added `ETA` integration, click on it and the click on the button `Download` on the bottom right corner
1. Restart Home Assistant when it says to.
1. In Home Assistant, go to `Configuration` -> `Integrations` -> Click `+ Add Integration`
Search for `Eta Sensors` and follow the instructions.
    - **Note**: After entering the host and port the integration will query information about every possible endpoint. This step can take a very long time, so please have some patience.
    - **Note**: This only affects the configuration step when adding the integration. After the integration has been configured, only the selected entities will be queried.
    - **Note**: The integration will also query the current sensor values of all endpoints when clicking on `Configure`. This will also take a bit of time, but not as much as when adding the integration for the first time.

## General Notes

- You have to activate the webservices API on your pellet heater first: see the "official" [documentation](https://www.meineta.at/javax.faces.resource/downloads/ETA-RESTful-v1.2.pdf.xhtml?ln=default&v=0):
    - Log in to `meinETA`
    - Go to `Settings` in the middle of the page (not the bottom one!)
    - Click on `Activate Webservices`
    - Follow the instructions

- For best results, your pellet heater has to support at least API version **1.2**. If you are on an older version the integration will fall back to a compatibility mode, which means that some sensors may not be correctly detected/identified. The ones that are correctly detected and identified should still work without problems.\
If you want to update the firmware of your pellet heater you can find the firmware files on `meinETA` (`Settings at the bottom` -> `Installation & Software`).

- Your ETA pellets unit needs a static IP address! Either configure the IP adress directly on the ETA terminal, or set the DHCP server on your router to give the ETA unit a static lease.

## Error Events
This integration publishes an event whenever a new error is reported by the ETA terminal, or when an active error is cleared.
These events can then be handled in automations.

### Event Info
If a new error is reported, an `eta_webservices_error_detected` event is published.\
If an error is cleared, an `eta_webservices_error_cleared` event is published.

Every event has the following data:
| Name       | Info                                               | Sample Data                                                                                 |
|------------|----------------------------------------------------|---------------------------------------------------------------------------------------------|
| `msg`      | Short error message                                | Water pressure too low 0,00 bar                                                             |
| `priority` | Error priority                                     | Error                                                                                       |
| `time`     | Time of the error, as reported by the ETA terminal | 2011-06-29T12:48:12                                                                         |
| `text`     | Detailed error message                             | Top up heating water! If this warning occurs more than once a year, please contact plumber. |
| `fub`      | Functional Block of the error                      | Kessel                                                                                      |
| `host`     | Address of the ETA terminal connection             | 0.0.0.0                                                                                     |
| `port`     | Port of the ETA terminal connection                | 8080                                                                                        |

### Checking Event Info
If you want to check the data of an active event, you can follow these steps.

**Note**: This is only possible if the ETA terminal actually reports an ective error!

1. Open Home Assistant in two tabs
1. On the first tab go to `Settings` -> `Devices & Services` -> `Devices` on top -> `ETA`
1. On the second tab go to `Developer tools` -> `Events` on top -> Enter `eta_webservices_error_detected` in the field `Event to subscribe to` -> Click on `Start Listening`
1. On the first tab click on the `Resend Error Events` button
1. On the second tab you can now see the detailed event info

### Sending a Test Event
If you want to send a test event to check if your automations work you can follow these steps:
1. Go to `Developer tools` -> `Events` on top
1. Enter `eta_webservices_error_detected` in the field `Event type`
1. Enter your test payload in the `Event data` field
    - ```
      msg: Test
      priority: Error
      time: "2023-11-06T12:48:12"
      text: This is a test error.
      fub: Kessel
      host: 0.0.0.0
      port: 8080
      ```
1. Click on `Fire Event`
1. Your automation should have been triggered

## Future Development
The ETA REST interface allows users to set many configuration values, like setpoints for temperatures, warning limits, etc.
I did not implement most of these in this integration, because I don't need that functionality.

If you need to set temperature setpoints or other values, or if you have some other ideas about expanding this implementation, you should open an issue and I may look into it.

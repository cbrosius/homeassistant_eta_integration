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
- Implemented an error sensor, which activates if the ETA terminal reports at least one error
    - This integration does not show which specific errors are reported because the user has to go to the ETA Terminal and manually reset the errors anyway.

## Notes

- You have to activate the webservices API on your pellet heater first: see the "official" [documentation](https://www.meineta.at/javax.faces.resource/downloads/ETA-RESTful-v1.2.pdf.xhtml?ln=default&v=0):
    - Log in to `meinETA`
    - Go to `Settings` in the middle of the page (not the bottom one!)
    - Click on `Activate Webservices`
    - Follow the instructions

- For best results, your pellet heater has to support at least API version **1.2**. If you are on an older version the integration will fall back to a compatibility mode, which means that some sensors may not be correctly detected/identified. The ones that are correctly detected and identified should still work without problems.\
If you want to update the firmware of your pellet heater you can find the firmware files on `meinETA` (`Settings at the bottom` -> `Installation & Software`).

- Your ETA pellets unit needs a static IP address! Either configure the IP adress directly on the ETA terminal, or set the DHCP server on your router to give the ETA unit a static lease.

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

## Future Development
The ETA REST interface allows users to set many configuration values, like setpoints for temperatures, warning limits, etc.
I did not implement most of these in this integration, because I did not need that functionality.

If you need to set temperature setpoints or other values, or if you have some other ideas about expanding this implementation, you should open an issue and I may look into it.

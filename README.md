[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

# ETA integration for Home Assistant
Integration of ETA (Heating) sensors and switches to Home Assistant

This integration uses the [ETA REST API](https://www.meineta.at/javax.faces.resource/downloads/ETA-RESTful-v1.2.pdf.xhtml?ln=default&v=0) to get sensor values and set switch states from the ETA pellets heating unit.

This is a fork of [nigl's repo](https://github.com/nigl/homeassistant_eta_integration) with the following changes:
- Friendly sensor names
- Implemented Switches
- Implemented Text Sensors (state of some endpoints, e.g. `Bereit` (`Ready`) or `Heizen` (`Heating`) for the boiler)
- Implemented an error sensor, which

**Note**: You have to activate the webservices API on your pellet heater first: see the [documentation](https://www.meineta.at/javax.faces.resource/downloads/ETA-RESTful-v1.2.pdf.xhtml?ln=default&v=0):
- Log in to `meinETA`
- Go to `Settings` in the middle of the page (not the bottom one!)
- Click on `Activate Webservices`
- Follow the instructions

**Note 2**: Your pellet heater has to support at least API version 1.2! If you are on an older version (check by calling `http:\\<host>:8080/user/api`) you have to update your firmware to the latest version. Firmware files can be found on `meinETA` (`Settings at the bottom` -> `Installation & Software`).

**Note 3**: Your ETA pellets unit needs a static IP address! Either configure the IP adress directly on the ETA terminal, or set the DHCP server on your router to give the ETA unit a static lease.

## Installation:
This integration can be configured directly in Home Assistant:

1. Go to HACS -> Integrations -> Click on the three dots in the top right corner --> Click on "userdefined repositories"
1. Insert "https://github.com/Tidone/homeassistant_eta_integration" into the field "repository"
1. Choose "integration" in the dropdown field "category".
1. Click on the "Add" button.
1. Then search for the new added "ETA" integration, click on it and the click on the button "Download" on the right bottom corner
1. Restart Home Assistant when it says to.
1. In Home Assistant, go to Configuration -> Integrations -> Click "+ Add Integration"
Search for "Eta sensors" and follow the instructions to setup.
    - Note: After entering the host and port the integration will query information on every possible endpoint. This step can take a very long time, so please have some patience.
    - Note: This only affects the configuration step when adding the integration. After the integration has been configured, only the selected entities will be queried.

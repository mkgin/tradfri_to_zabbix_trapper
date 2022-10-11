# Templates.md

Brief description of Templates and their functions

## Template_Tradfri_Gateway.xml 

* Trapper items for Gateway

## Template_Tradfri_Gateway_Device_Discovery.xml 

* Trapper item for Gateway's discovered devices
* Devices are discovery from the same gateway item, key: tradfri.device.list
* If the device type has a specific discovery rules defined it is used to apply appropriate templates
  * Tradfri Device Discovery Remote or Motion Sensor
  * Tradfri Device Discovery Outlet
  * Tradfri Device Discovery Bulb
* Devices that don't match a defined device type use the following rule 
  * Tradfri Device Discovery

## Template_Tradfri_Devices.xml 
* Items that apply to all devices

## Template_Tradfri_Devices_Bulbs.xml
* Items only applying to Bulbs

## Template_Tradfri_Devices_Outlets.xml
* Items only applying to Outlets

## Template_Tradfri_Devices_Remote_and_Sensor.xml
* Items only applying to Remotes, Dimmers and Motion Sensors (haven't tested with buttons yet)

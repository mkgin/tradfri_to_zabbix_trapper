# NOTES.md

## Zabbix Discovery

* considering the easiest way to do this with zabbix.

### zabbix trapper

* https://www.zabbix.com/documentation/4.2/en/manual/config/items/itemtypes/trapper
  * "Zabbix trapper process does not expand macros used in the item key in attempt to check corresponding item key existence for targeted host."
* maybe the best approach is send gateway devices. (endpoint#, first created, type, Name) to an item... as json? and discover from there via a dependant item
  
### implementation

* each device could be items with a unique key parameter
  * key: tradfri.device.bulb.reachable.[65578_1639261274]
* each device could be made a host in hostgroup "Tradfri"
  * host: 65578_1639261274
  * key: tradfri.device.bulb.reachable
  * I think this case makes more sense
    * some items work well for inventory.
	* hosts could be later grouped by their rooms

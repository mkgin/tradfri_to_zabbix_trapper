# NOTES.md

## Zabbix Discovery

### zabbix trapper

* https://www.zabbix.com/documentation/4.2/en/manual/config/items/itemtypes/trapper
  * "Zabbix trapper process does not expand macros used in the item key in attempt to check corresponding item key existence for targeted host."
* maybe the best approach is send gateway devices. (endpoint#, first created, type, Name) to an item... as json? and discover from there via a dependant item

* sending devices to tradfri.device.list Item and using discovering from that item

### implementation

* each discovered device becomes a host in hostgroup "Tradfri"
  * host: 65578_1639261274.DEVICE_TYPE.tradfri (comination of device_id and first_seen)
  * key: tradfri.device.KEY...

## PSK

Same PSK in ```tradfri_standalone_psk.conf``` works after rebooting GW

## Crashes

Probably need to add "try:" to calls that make requests to the API, and should aim to reduce the number of calls made.

Polling devices and gateway every 60s ... maybe the Gateway gets tired.

Error after 2-3 hours...
```
 <Command get ['15001', 65582]>]
Traceback (most recent call last):
  File "/home/username/git/pytradfri_zabbix/pytradfri_to_zabbix.py", line 276, in <module>
    main()
  File "/home/username/git/pytradfri_zabbix/pytradfri_to_zabbix.py", line 168, in main
    devices = api(devices_commands)
  File "/home/username/.local/lib/python3.9/site-packages/pytradfri/api/libcoap_api.py", line 131, in request
    result = self._execute(api_command, timeout=timeout)
  File "/home/username/.local/lib/python3.9/site-packages/pytradfri/api/libcoap_api.py", line 106, in _execute
    api_command.process_result(_process_output(return_value, parse_json))
  File "/home/username/.local/lib/python3.9/site-packages/pytradfri/command.py", line 62, in process_result
    self._result = self._process_result(result)
  File "/home/username/.local/lib/python3.9/site-packages/pytradfri/gateway.py", line 144, in process_result
    return Device(result)
  File "/home/username/.local/lib/python3.9/site-packages/pytradfri/resource.py", line 39, in __init__
    self.raw = self._model_class(**raw)
TypeError: pytradfri.device.DeviceResponse() argument after ** must be a mapping, not NoneType
>>>
```
The gateway still pings.
And on restarting the program: 
```
/home/username/git/pytradfri_zabbix /home/username/git/pytradfri_zabbix/config.yml /home/username/git/pytradfri_zabbix/own_config.yml
** devices_command
<Command get ['15001']>
Traceback (most recent call last):
  File "/home/username/git/pytradfri_zabbix/pytradfri_to_zabbix.py", line 276, in <module>
    main()
  File "/home/username/git/pytradfri_zabbix/pytradfri_to_zabbix.py", line 164, in main
    devices_commands = api(devices_command)
  File "/home/username/.local/lib/python3.9/site-packages/pytradfri/api/libcoap_api.py", line 126, in request
    return self._execute(api_commands, timeout=timeout)
  File "/home/username/.local/lib/python3.9/site-packages/pytradfri/api/libcoap_api.py", line 101, in _execute
    raise RequestTimeout() from None
pytradfri.error.RequestTimeout
>>>
```

Timeout after a couple hours:
```
Traceback (most recent call last):
  File "/home/username/git/pytradfri_zabbix/pytradfri_to_zabbix.py", line 276, in <module>
    main()
  File "/home/username/git/pytradfri_zabbix/pytradfri_to_zabbix.py", line 168, in main
    devices = api(devices_commands)
  File "/home/username/.local/lib/python3.9/site-packages/pytradfri/api/libcoap_api.py", line 131, in request
    result = self._execute(api_command, timeout=timeout)
  File "/home/username/.local/lib/python3.9/site-packages/pytradfri/api/libcoap_api.py", line 101, in _execute
    raise RequestTimeout() from None
pytradfri.error.RequestTimeout
```

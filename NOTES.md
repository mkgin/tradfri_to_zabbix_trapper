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
### Potential Causes and cures.

Have seen many things mentioned...

* Spamming / Polling too often and not being 'close' on the network
  * https://github.com/home-assistant-libs/pytradfri#known-issues
  * I have tried polling at different rates and spacing out times between API calls, and often manage 9 hours or more without the gateway needing to be reatarted
* Number of devices 
  * reddit? github?
* DHCP
  * https://github.com/home-assistant-libs/pytradfri/issues/310
  * I haven't noticed any correlation after going through logs
* Access to webhook.logentries.com
  * https://www.reddit.com/r/tradfri/comments/gl80in/why_does_the_tradfri_hub_need_to_talk_to/
  * check app settings
* Power supply
  * https://www.reddit.com/r/tradfri/comments/qq4yyn/gateway_stuck_in_an_infinite_reboot_cycle/
  * This makes sense, I am still using the original Ikea one.
  * Switched to a different power source (computer USB port), maybe a shorter USB cable.
  
  
### Dumps

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

- again... maybe 2-3 hours and gateway crashes. in this case one of the motion sensors had a blinking red light.
- maybe the sensor having a low battery and acting funny kept the gw busy with zigbee stuff?
- battery was at 34%
- needed to connect my phone app to it again, but the psk for this program was ok.

```
  File "/home/username/.local/lib/python3.9/site-packages/pytradfri/gateway.py", line 297, in __init__
    self.raw = GatewayInfoResponse(**raw)
TypeError: pytradfri.gateway.GatewayInfoResponse() argument after ** must be a mapping, not NoneType
```

- Possibly to do with DHCP?
  - https://github.com/home-assistant-libs/pytradfri/issues/310
  - Possible, but i didn't really see any correlation in DHCP logs 
  - more likely to do with spamming/querying the GW at high rates.


```
1665623375.972598 DEBUG:root:Zabbix Sender succeeded
1665623375.972640 {"processed": 11, "failed": 1, "total": 12, "time": "0.000501", "chunk": 1}
1665623375.972675 DEBUG:root:*** END Polling devices for loop
1665623375.972696 DEBUG:root:** gateway info
1665623375.972717 DEBUG:root:** gateway endpoint
1665623376.573468 DEBUG:pytradfri.api.libcoap_api:Executing tradfri.private get ['15011', '15012']
1665623376.632636 DEBUG:pytradfri.api.libcoap_api:Received: 
1665623376.632947 Traceback (most recent call last):
1665623376.633000   File "/home/user1/git/pytradfri_zabbix/pytradfri_to_zabbix.py", line 327, in <module>
1665623376.633243     main()
1665623376.633284   File "/home/user1/git/pytradfri_zabbix/pytradfri_to_zabbix.py", line 285, in main
1665623376.633320     gateway_data = api(gateway.get_gateway_info()).raw
1665623376.633339   File "/home/user1/.local/lib/python3.9/site-packages/pytradfri/api/libcoap_api.py", line 126, in request
1665623376.633370     return self._execute(api_commands, timeout=timeout)
1665623376.633394   File "/home/user1/.local/lib/python3.9/site-packages/pytradfri/api/libcoap_api.py", line 106, in _execute
1665623376.633479     api_command.process_result(_process_output(return_value, parse_json))
1665623376.633522   File "/home/user1/.local/lib/python3.9/site-packages/pytradfri/command.py", line 62, in process_result
1665623376.633545     self._result = self._process_result(result)
1665623376.633564   File "/home/user1/.local/lib/python3.9/site-packages/pytradfri/gateway.py", line 193, in process_result
1665623376.633663     return GatewayInfo(result)
1665623376.633706   File "/home/user1/.local/lib/python3.9/site-packages/pytradfri/gateway.py", line 297, in __init__
1665623376.633729     self.raw = GatewayInfoResponse(**raw)
1665623376.633749 TypeError: pytradfri.gateway.GatewayInfoResponse() argument after ** must be a mapping, not NoneType
```

### While powering off GW

```
Oct 05 13:16:00 DEBUG:pyzabbix.sender:Response header: b'ZBXD\x01Z\x00\x00\x00\x00\x00\x00\x00'
Oct 05 13:16:00 DEBUG:pyzabbix.sender:Data received: {'response': 'success', 'info': 'processed: 1; failed: 0; total: 1; seconds spent: 0.000057'}
Oct 05 13:16:00 DEBUG:pyzabbix.sender:('z4p.private', 10051) response: {'response': 'success', 'info': 'processed: 1; failed: 0; total: 1; seconds spent: 0.000057'}
Oct 05 13:16:00 DEBUG:root:Zabbix Sender succeeded
Oct 05 13:16:00 {"processed": 1, "failed": 0, "total": 1, "time": "0.000057", "chunk": 1}
Oct 05 13:16:00 Traceback (most recent call last):
Oct 05 13:16:00   File "/home/username/git/pytradfri_zabbix/pytradfri_to_zabbix.py", line 273, in <module>
Oct 05 13:16:00     main()
Oct 05 13:16:00   File "/home/username/git/pytradfri_zabbix/pytradfri_to_zabbix.py", line 204, in main
Oct 05 13:16:00     f'{key_begin}.group_name', device_group_dict[repr(dev.id)]['name'] , epoch_timestamp)]
Oct 05 13:16:00 KeyError: '65583'
```

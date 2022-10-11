# pytradfri to zabbix.

- messing about for now and it's still a bit of a hack.
- prints out and can send values from remotes, motion detectors, light bulbs
- sends unique identifier ( device_id + created_at ) for discovery.
- key format is 'tradfri.device.(dict{application_type}).[device_id_created_at,parameter/key....]'

## config

- see `config.yml` and `own_config.yml`
- `own_config.yml` overwrites the defaults in config if present.
- can use the same psk file from pytradfri examples. (`tradfri_standalone_psk.conf`)

## Zabbix

### Zabbix Templates

See the [Zabbix Templates directory](Zabbix_Templates/)

## modules used

* pytradfri https://github.com/home-assistant-libs/pytradfri
  * note that you need compile libcoap dtls first
* pyzabbix https://github.com/adubkov/py-zabbix
* yaml https://github.com/yaml/pyyaml

* api_polling (as submodule ) 
  * Use ```git clone --recurse-submodules``` to clone this repo and the api_polling submodule

## Trådfri Gateway

* The Gateway crashes occasionally
  * https://github.com/home-assistant-libs/pytradfri#known-issues

* Trying to poll less frequently and not poll too many commands at once.
  * adjusting intervals between api requests
  * eventually may need to set up a watchdog to power cycle the gateway.

## Recent changes
- gateway items
- get groups, put group name into devices data/inventory
- slow down polling the gateway
- poll lights, outlets and devices undergoing ota update regularly
- poll other items less often, first run + every quarter hour.

## Todo:

- use my api polling module for sending stategies, polling intervals
- update zabbix templates
- test making a new PSK from Gateway secret

# pytradfri to zabbix.

- messing about for now and it's still a bit of a hack.
- prints out and can send values from remotes, motion detectors, light bulbs
- sends unique identifier ( device_id + created_at ) for discovery.
- key format is 'tradfri.device.(dict{application_type}).[device_id_created_at,parameter/key....]'

## config

- see `config.yml` and `own_config.yml`
- `own_config.yml` overwrites the defaults in config if present.
- can use the same psk file from pytradfri examples. (`tradfri_standalone_psk.conf`)

## modules used

* pytradfri https://github.com/home-assistant-libs/pytradfri
  * note that you need compile libcoap dtls first
* pyzabbix https://github.com/adubkov/py-zabbix
* yaml https://github.com/yaml/pyyaml

## Todo:

- use my api polling module for sending stategies, polling intervals
- gateway items
- zabbix template
- low level discovery
- test new PSK from Gateway secret
- check gateway items

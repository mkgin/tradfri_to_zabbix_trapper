"""
Tradfri to Zabbix

Collects data from a IKEA(r) Tradfri(r) Gateway and
sends it to a Zabbix(r)? server.

Used example_sync.py form the pytradfri-library as a starting point.
"""
import socket #for errors from ZabbixSender
import logging #ZabbixSender
from pyzabbix import ZabbixMetric, ZabbixSender, ZabbixResponse

import os
from datetime import datetime

# Hack to allow relative import above top level package
# from example_sync.py... probably not needed?
# ( two lined after 'import sys' )
import sys
folder = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath("%s/.." % folder))

import json
import time
import uuid
import yaml

from pytradfri import Gateway
from pytradfri.api.libcoap_api import APIFactory
from pytradfri.error import PytradfriError
from pytradfri.util import load_json, save_json

import pprint

CONFIG_FILE = "tradfri_standalone_psk.conf"

# Count data recieved from zabbix server
zabbix_server_processed = 0 #
zabbix_server_failed = 0    # Zabbix server did not accept (wrong key, wrong type of data)
zabbix_server_total = 0     #
zabbix_send_failed_time = 0

def send_zabbix_packet(zabbix_packet , zabbix_sender_setting):
    """Sends zabbix packet to server(s)"""
    sending_status = False
    zasender = ZabbixSender(zabbix_sender_setting)
    global epoch_time, zabbix_server_processed, zabbix_server_failed, zabbix_server_total
    try:
        zaserver_response = zasender.send(zabbix_packet)
        zabbix_packet = [] #it's sent now ok to erase
        zabbix_send_failed_time = 0 #in case it failed earlier
        zabbix_server_processed += zaserver_response.processed
        zabbix_server_failed += zaserver_response.failed
        zabbix_server_total += zaserver_response.total
        logging.debug(f'Zabbix Sender succeeded\n{zaserver_response}')
        sending_status = True
    except (socket.timeout, socket.error, ConnectionRefusedError ) as error_msg:
        logging.warning('Zabbix Sender Failed to send some or all: {0}'.format(error_msg))
        # if sending fails, Zabbix server may be restarting or rebooting.
        # maybe it gets sent after the next polling attempt.
        # if zabbix_packet is more than x items or if failure time
        # greater than x save to disk
        if zabbix_send_failed_time == 0 : #first fail (after successful send or save)
            zabbix_send_failed_time = epoch_time
            # could set defaults for failed item sending timeout and count.
        if  ( epoch_time - zabbix_send_failed_time > zabbix_send_failed_time_max #900
            or len(zabbix_packet) > zabbix_send_failed_items_max #500
            ):
            logging.error(f'Zabbix Sender failed {epoch_time-zabbix_send_failed_time} seconds ago')
            logging.error(f'{len(zabbix_packet)} items pending.\nWill try to dump them to disk')
            save_zabbix_packet_to_disk(zabbix_packet)
            zabbix_send_failed_time = epoch_time
            zabbix_packet = [] #it's saved now ok to erase
            # clear keys from lastchanged so fresh values are collected to be sent next time
            lastchanged={}
    except:
        logging.error(f'Unexpected error: {sys.exc_info()[0]}')
        raise
    return sending_status,zaserver_response 


def load_config():
    """Loads the YAML config first from config.yml, then own_config.yml"""
    # basic config
    # api config
    config = {}
    current_path = os.getcwd()
    # should really just loop through config files.
    # and maybe allow one to be specified as an argument
    configfile_default = f'{current_path}/config.yml'
    configfile_own = f'{current_path}/own_config.yml'
    print( current_path,configfile_default, configfile_own)
    if os.path.isfile(configfile_default):
        config = yaml.safe_load(open(configfile_default))
    else:
        logging.warning(f'Missing:  {configfile_default}' )
    if os.path.isfile(configfile_own):
        config.update(yaml.safe_load(open(configfile_own)))
    else:
        logging.warning('Missing: {configfile_own}' )
    return config

def zabbix_send_result_string( result ):
    return 'zabbix_send_result[' \
                    f'processed: {result.processed} , ' \
                    f'failed: {result.failed} , ' \
                    f'total: {result.total}]'

def zabbix_tradfri_discovery_send( devid, devtype, dev_name, created_at,  zahost, monhost):
    """Send discovery data to zabbix
    """
    # TODO check devid valid...
    key = f'tradfri.device.discovery.{devtype}'
    value = f'{devid}_{created_at} {dev_name}'
    timestamp = int(time.time())
    zapacket = [ZabbixMetric( monhost, f'{key}', value, timestamp)]
    pprint.pp(zapacket)
    return send_zabbix_packet(zapacket , zahost)

def main():
    """main."""
    config = load_config()
    monitored_hostname=config['monitored_hostname']
    # variables for zabbix
    zabbix_config=config['zabbix_sender_settings']
    # load last used psk
    tradfri_gw_psk = load_json(CONFIG_FILE)

    # load dict for application_type
    app_type_dict = yaml.safe_load(open('application_type.yml'))

    # loop starts here
    while True: #breaks at end for single run
        # load the the tradfri config, check we are have credentials to connect
        try:
            identity = tradfri_gw_psk[monitored_hostname].get("identity")
            psk = tradfri_gw_psk[monitored_hostname].get("key")
            api_factory = APIFactory(host=monitored_hostname, psk_id=identity, psk=psk)
        except KeyError:
            identity = uuid.uuid4().hex
            api_factory = APIFactory(host=monitored_hostname, psk_id=identity)

            try:
                psk = api_factory.generate_psk(config['tradfri_security_code'])
                print("Generated PSK: ", psk)

                tradfri_gw_psk[args.host] = {"identity": identity, "key": psk}
                save_json(CONFIG_FILE, tradfri_gw_psk)
            except AttributeError:
                raise PytradfriError(
                    "Maybe you need to add the 'Security Code' on the "
                    "back of your Tradfri gateway to own_config.yml"
                )

        api = api_factory.request
        gateway = Gateway()
        epoch_timestamp = int(time.time())

        # get device endpoints
        devices_command = gateway.get_devices()
        print('** devices_command')
        pprint.pp( devices_command)
        # 
        devices_commands = api(devices_command)
        print('** devices_commands')
        pprint.pp(devices_commands)
        # device data
        devices = api(devices_commands)
        #
        print('** devices')
        pprint.pp(devices)
        
        lights = [dev for dev in devices if dev.has_light_control]
        
        print("*** START dev.raw")
        key_prefix = 'tradfri'
        device_item_list = ['name','ota_update_state',
                       'application_type', 'last_seen', 'reachable']
        # 'id' and 'created_at' are used to create a unique id
        #
        # not interested yet 'air_purifier_control', blind_control,
        #light_control=None, signal_repeater_control, socket_control
        device_light_item_list = ['state', 'dimmer','color_hex',]
        #light_control=[LightResponse(id=0, color_mireds=251, color_hex='f5faf6', color_xy_x=25022,
        #color_xy_y=24884, color_hue=None, color_saturation=None, dimmer=254, state=0)]
        # Some light may change brightness during the day, maybe nice to make
        # template graphs that use dimmer * state
        device_info_item_list = [ 'firmware_version', 'power_source', 'battery_level','model_number' ]
        # empty or less interesting
        # 'serial','manufacturer',
        
        device_discovery = True #or False
        #device_discovery = False  #TODO: fix... debugging /testing
        list_all_items = True     # TODO: fix... debugging /testing
        #list_all_items = False
        device_discovery_list = ''
        for dev in devices:
            key_begin = f'{key_prefix}.device' #+ '.' + app_type_dict[dev.application_type]['type']
            #key_end = f'[{dev.id}_{int (datetime.timestamp(dev.created_at))}]'
            key_end = ''
            tradfri_hostname = f'{dev.id}_{int (datetime.timestamp(dev.created_at))}.' + \
                               app_type_dict[dev.application_type]['type'] + '.' + \
                               'tradfri'
            if device_discovery:
                device_discovery_item = f'{dev.id}_{int (datetime.timestamp(dev.created_at))},' + \
                                         app_type_dict[dev.application_type]['type'] + \
                                         f',{dev.name}\n'
                za_device_send = [ZabbixMetric( config['monitored_hostname'],
                                    'tradfri.device.list',
                                    device_discovery_item , epoch_timestamp)] #int (datetime.timestamp(dev.created_at)))] #epoch_timestamp)]
                if config['print_zabbix_send']:
                    pprint.pp(za_device_send)
                if config['do_zabbix_send']:
                    zabbix_send_result = send_zabbix_packet(za_device_send, zabbix_config)
                    if config['print_zabbix_send']:
                        print (zabbix_send_result_string(zabbix_send_result[1]))
            if True: #send_device_values:
                ivlist=[] # send separately per device
                devtype = app_type_dict[dev.application_type]['type'] #TODO: not used probably
                print('****')
                print( type(dev.raw) , type(dev) )
                for k in dev.raw: #device_item_list:
                    if list_all_items:
                        print( k )
                    if k[0] in device_item_list and k[1] is not None:
                        ivlist += [ZabbixMetric( tradfri_hostname,
                                    f'{key_begin}.{k[0]}{key_end}', k[1], epoch_timestamp)]
                #print( dev.device_info.raw , type(dev.device_info.raw) )
                for k in dev.device_info.raw:
                    if list_all_items:
                        print (k)
                    if k[0] in device_info_item_list and k[1] is not None:
                        ivlist += [ZabbixMetric( tradfri_hostname,
                                f'{key_begin}.device_info.{k[0]}{key_end}',
                                k[1],epoch_timestamp)]
                if dev.light_control is not None:
                    for k in dev.light_control.raw[0]:
                        if list_all_items:
                            print(k[0], k[1],type(k),)
                        if k[0] in device_light_item_list and k[1] is not None:
                            ivlist += [ZabbixMetric( tradfri_hostname,
                                    f'{key_begin}.light_control.{k[0]}{key_end}',
                                    k[1],epoch_timestamp)]            
                if config['print_zabbix_send']:
                    print('*** zabbix ivlist:')
                    pprint.pp(ivlist)
                if config['do_zabbix_send']:
                    zabbix_send_result = send_zabbix_packet(ivlist, zabbix_config)
                    if config['print_zabbix_send']:
                        print('*** zabbix server returned:')
                        print(f'zabbix_send_result: {zabbix_send_result[0]} , ' \
                        f'processed: {zabbix_send_result[1].processed} , ' \
                        f'failed: {zabbix_send_result[1].failed} , ' \
                        f'total: {zabbix_send_result[1].total}')
        print("*** END dev.raw")

        # TODO: check if lamps are in a group.
        # put group names to inventory

        print('** gateway info')
        gateway_item_list = ['ota_update_state','firmware_version','first_setup',
                             'ota_type:','update_progress']
        pprint.pp(api(gateway.get_gateway_info()).raw)
        print('** gateway endpoint')
        #print_gateway_endpoints(api, gateway)
        #print_gateway(api, gateway)
        gw_endpoints = api(gateway.get_endpoints())
        #for gw_endpoint in gw_endpoints:
        #    pprint.pp(gw_endpoint)
        
        if config['do_it_once']:
            break
        else:
            time.sleep(60)
    #end while
main()

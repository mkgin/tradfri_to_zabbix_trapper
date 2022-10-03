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

#own libs
sys.path.append('api_polling')
from api_poll_config import *
from api_poll_zabbix import *
from api_poll_tools import *

import json
import time
import uuid
import yaml

from pytradfri import Gateway
from pytradfri.api.libcoap_api import APIFactory
from pytradfri.error import PytradfriError,RequestTimeout
from pytradfri.util import load_json, save_json

import pprint

CONFIG_FILE = "tradfri_standalone_psk.conf"

# Count data recieved from zabbix server
zabbix_server_processed = 0 #
zabbix_server_failed = 0    # Zabbix server did not accept (wrong key, wrong type of data)
zabbix_server_total = 0     #
zabbix_send_failed_time = 0


def main():
    """main."""
    logging.basicConfig(level=logging.INFO)
    config = load_config()
    monitored_hostname=config['monitored_hostname']
    # variables for zabbix
    zabbix_config=config['zabbix_sender_settings']
    # load last used psk
    tradfri_gw_psk = load_json(CONFIG_FILE)

    # load dict for application_type
    app_type_dict = yaml.safe_load(open('application_type.yml'))

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
    first_loop = True
    epoch_timestamp_last = int(time.time())
    sleep_between_api_calls = 1

    # loop starts here
    while True: #breaks at end for single run    
        # do this less often
        epoch_timestamp = int(time.time())
        api = api_factory.request
        gateway = Gateway()
        if first_loop or test_times_straddle_minute(epoch_timestamp_last, epoch_timestamp ,[0,15,30,45]):
            logging.info(f'Checking Devices {epoch_timestamp} first_loop: {first_loop}')
            first_loop = False
            
            # get device endpoints
            devices_command = gateway.get_devices() #try
            # try sleeping 

            logging.debug('** devices_command' , devices_command)

            #devices_commands = api(devices_command) #try:
            devices_commands = try_n_times( api, devices_command,expected_exceptions=RequestTimeout )
            # try sleeping
            logging.debug('** devices_commands', devices_commands)
            
        # device data
        #devices = api(devices_commands) #try:
        # TODO: test would this fail if devices changed.
        devices = try_n_times( api,devices_commands,expected_exceptions=RequestTimeout ) 
        
        #
        logging.debug('** devices', devices)
        
        logging.debug("*** START dev.raw")
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
                    logging.info( f'za_device_send {za_device_send}')
                if config['do_zabbix_send']:
                    zabbix_send_result = send_zabbix_packet(za_device_send, zabbix_config)
                    if config['print_zabbix_send']:
                        logging.info(zabbix_send_result_string(zabbix_send_result[1]))
            if True: #send_device_values:
                ivlist=[] # send separately per device
                devtype = app_type_dict[dev.application_type]['type'] #TODO: not used probably
                logging.debug('****', type(dev.raw) , type(dev) )
                for k in dev.raw: #device_item_list:
                    if list_all_items:
                        logging.debug( k )
                    if k[0] in device_item_list and k[1] is not None:
                        ivlist += [ZabbixMetric( tradfri_hostname,
                                    f'{key_begin}.{k[0]}{key_end}', k[1], epoch_timestamp)]
                for k in dev.device_info.raw:
                    if list_all_items:
                        logging.debug (k)
                    if k[0] in device_info_item_list and k[1] is not None:
                        ivlist += [ZabbixMetric( tradfri_hostname,
                                f'{key_begin}.device_info.{k[0]}{key_end}',
                                k[1],epoch_timestamp)]
                if dev.light_control is not None:
                    for k in dev.light_control.raw[0]:
                        if list_all_items:
                            logging.debug(k[0], k[1],type(k),)
                        if k[0] in device_light_item_list and k[1] is not None:
                            ivlist += [ZabbixMetric( tradfri_hostname,
                                    f'{key_begin}.light_control.{k[0]}{key_end}',
                                    k[1],epoch_timestamp)]            
                if config['print_zabbix_send']:
                    logging.info('*** zabbix ivlist:')
                    pprint.pp(ivlist)
                if config['do_zabbix_send']:
                    zabbix_send_result = send_zabbix_packet(ivlist, zabbix_config)
                    if config['print_zabbix_send']:
                        logging.info('*** zabbix server returned:')
                        logging.info(zabbix_send_result_string(zabbix_send_result[1]))
        logging.debug("*** END dev.raw")

        # TODO: check if devices are in a group.
        # put group names to inventory
        # use group in visible name

        logging.debug('** gateway info')
        gateway_item_list = ['ota_update_state','firmware_version','first_setup',
                             'ota_type','update_progress']
        logging.debug('** gateway endpoint')
        gateway_data = api(gateway.get_gateway_info()).raw
        #pprint.pp(gateway_data)
        ivlist=[]
        for k in gateway_data:
            if k[0] in gateway_item_list:
                ivlist += [ZabbixMetric( config['monitored_hostname'],
                        f'{key_prefix}.gateway.{k[0]}', k[1], epoch_timestamp)]
        if config['print_zabbix_send']:
            logging.info('*** zabbix ivlist [gateway]:')
            pprint.pp(ivlist)     
        if config['do_zabbix_send']:
            zabbix_send_result = send_zabbix_packet(ivlist, zabbix_config)
            if config['print_zabbix_send']:
                logging.info('*** zabbix server returned:')
                logging.info(zabbix_send_result_string(zabbix_send_result[1]))
        epoch_timestamp_last = epoch_timestamp
        if config['do_it_once']:
            break
        else:
            logging.info('sleeping')
            time.sleep(60)
    #end while
main()

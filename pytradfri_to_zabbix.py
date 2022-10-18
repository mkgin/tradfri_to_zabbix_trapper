"""
Tradfri to Zabbix

Collects data from a IKEA(r) Tradfri(r) Gateway and
sends it to a Zabbix(r)? server.

Used example_sync.py form the pytradfri-library as a starting point.
"""
import pprint
import time
import uuid
#import socket #for errors from ZabbixSender
import logging
#import os
from datetime import datetime
import sys
import yaml
from pyzabbix import ZabbixMetric
#from pyzabbix import ZabbixMetric, ZabbixSender, ZabbixResponse
from pytradfri import Gateway
from pytradfri.api.libcoap_api import APIFactory
from pytradfri.error import PytradfriError,RequestTimeout
from pytradfri.util import load_json, save_json

#own libs
sys.path.append('api_polling')
from api_poll_config import *
from api_poll_zabbix import *
from api_poll_tools import *

def main():
    """main."""
    key_prefix = 'tradfri'
    device_item_list = ['name','ota_update_state',
                   'application_type', 'last_seen', 'reachable']

    # 'id' and 'created_at' are used to create a unique id
    # not interested yet 'air_purifier_control', blind_control, signal_repeater_control
    device_light_item_list = ['state', 'dimmer','color_hex', 'color_mireds',
                              'color_xy_x', 'color_xy_y','color_hue', 'color_saturation' ]
    device_info_item_list = [ 'firmware_version', 'power_source', 'battery_level','model_number' ]
    device_socket_item_list = ['id','state']
    device_discovery = True #or False

    gateway_expected_exceptions = (RequestTimeout, TypeError ) #a Tuple... leave last comma ( x, )
    #maybe have a list for exceptions for restarting the gateway.

    #logging.basicConfig(level=logging.INFO)
    logging.basicConfig(level=logging.DEBUG)
    config = load_config()
    monitored_hostname=config['monitored_hostname']
    # variables for zabbix
    zabbix_config=config['zabbix_sender_settings']
    # api polling throttling
    sleep_between_api_calls = config['delay_api_calls_large']
    sleep_short_between_api_calls = config['delay_api_calls_small']
    # api polling intervals
    polling_interval = config['frequent_poll_interval']
    occasional_poll_minutes = config['occasional_poll_minutes']
    # load last used psk
    tradfri_gw_psk = load_json(config['tradfri_standalone_psk_conf'])
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
            save_json(config['tradfri_standalone_psk_conf'], tradfri_gw_psk)
        except AttributeError:
            raise PytradfriError(
                "Maybe you need to add the 'Security Code' on the "
                "back of your Tradfri gateway to own_config.yml"
            )
    no_gateway_data_counter = 0 #counter for data not recieved from gateway
    first_loop = True
    epoch_timestamp_last = int(time.time())
    epoch_timestamp_start = epoch_timestamp_last
    # main loop starts here
    while True: #breaks at end for single run
        epoch_timestamp = int(time.time())
        api = api_factory.request
        gateway = Gateway()
        # occasional_loop says when to collect data (commands) for devices we want to
        # monitor frequently
        occasional_loop = False
        # first_time and occasionally run
        if first_loop or test_times_straddle_minute(epoch_timestamp_last, epoch_timestamp
                                                    ,occasional_poll_minutes):
            logging.info(f'Checking Devices {epoch_timestamp} first_loop: {first_loop}')
            first_loop = False
            occasional_loop = True
            # get device commands
            devices_command_all = gateway.get_devices()
            #time.sleep(sleep_between_api_calls)# try sleeping between api calls to GW
            logging.debug(f'** devices_command_all: {devices_command_all}')
            #if config['gateway_detailed_debug']:
            #    print( f'devices_command_all: type{devices_command_all}')
            #    pprint.pp(devices_command_all)
            #devices_commands = api(devices_command) #try:
            devices_commands_all = \
                try_n_times( api, devices_command_all,expected_exceptions = gateway_expected_exceptions)
            time.sleep(sleep_between_api_calls) # try sleeping between api calls to GW
            logging.debug(f'** devices_commands_all {devices_commands_all}')
            if config['gateway_detailed_debug']:
                print( f'devices_commands_all: type{devices_commands_all}')
                pprint.pp(devices_commands_all)
            # Create dictionary for device group names and ids
            #""" get group name  or id from a device with this dictionary
            #    eg: device_group_dict['65582']['name']
            #        device_group_dict['65582']['groupid'])
            #"""
            group_item_list = ['id','name','group_members']
            device_group_dict = {}
            logging.debug('gateway.get_groups()')
            groups = api( gateway.get_groups()) #get command list for groups #TODO: try!!
            time.sleep(sleep_short_between_api_calls) # try sleeping between api calls to GW
            logging.debug(f'groups: {groups}')
            for group in groups:
                logging.debug(f'for groups in group: {group}, api(group)')
                groupname = groupid = groupdevs = ''
                api_group_result = try_n_times( api, group,
                                         expected_exceptions=( gateway_expected_exceptions ),
                                         try_slowly_seconds=sleep_short_between_api_calls)
                logging.debug(f'api_group_result: type {type(api_group_result)}\n{api_group_result}')
                logging.debug(f'api_group_result.raw: type {type(api_group_result.raw)}\n{api_group_result.raw}')
                for k in api_group_result.raw:
                    if k[0] in group_item_list:
                        logging.debug(f'k[0] in group_item_list  {k[0]},{k[1]}')
                    if k[0] == 'name':
                        groupname=k[1]
                    if k[0] == 'id':
                        groupid=k[1]
                    if k[0] == 'group_members':
                        groupdevs=k[1]['15002']['9003']
                if groupname not in ('SuperGroup', ''):
                    for dev_id in groupdevs :
                        devdict = {}
                        devdict['name'] = groupname #api(group).name
                        devdict['groupid'] = groupid #api(group).id
                        device_group_dict[repr(dev_id)] = devdict
        ## End of if first_loop
        logging.debug("*** START Polling devices for loop: occasional_loop: {occasional_loop}")
        # set devices to monitor here, in 'devices_commands'
        # if we are in an "occasional_loop" we monitor all.
        # and update the list of regularly monitored devices, otherwise, loop through
        # the list of regularly_monitored devices.
        #
        # regularly monitored devices are:
        # - lights 
        # - outlets
        # - any device with a ota_update status of 1
        if occasional_loop:
            devices_commands = devices_commands_all
            devices_commands_frequent = []
        else:
            devices_commands = devices_commands_frequent
        # device data for loop
        for devcount in range( 0, len(devices_commands) ):
            print(f'devcount: {devcount}')
            dev = try_n_times( api,devices_commands[devcount],
                               expected_exceptions=( gateway_expected_exceptions ),
                               try_slowly_seconds=sleep_short_between_api_calls)
            key_begin = f'{key_prefix}.device'
            key_end = ''
            tradfri_hostname = f'{dev.id}_{int (datetime.timestamp(dev.created_at))}.' + \
                               app_type_dict[dev.application_type]['type'] + '.' + \
                               'tradfri'
            if device_discovery:
                device_discovery_item = f'{dev.id}_{int (datetime.timestamp(dev.created_at))},' + \
                                         app_type_dict[dev.application_type]['type'] + \
                                         f',{dev.name},' + device_group_dict[repr(dev.id)]['name']+\
                                         ',' + repr(device_group_dict[repr(dev.id)]['groupid'])+'\n'
                za_device_send = [ZabbixMetric( config['monitored_hostname'],
                                    'tradfri.device.list',
                                    device_discovery_item , epoch_timestamp)]
                zabbix_send_result = send_zabbix_packet(za_device_send, zabbix_config, do_send=config['do_zabbix_send'] )
                log_zabbix_send_result(zabbix_send_result)
            if True: # send_device_values:
                ivlist = []  # send separately per device
                # group name
                ivlist += [ZabbixMetric( tradfri_hostname,
                            f'{key_begin}.group_name',
                            device_group_dict[repr(dev.id)]['name'] , epoch_timestamp)]
                # group id
                ivlist += [ZabbixMetric( tradfri_hostname,
                           f'{key_begin}.group_id',
                           device_group_dict[repr(dev.id)]['groupid'] , epoch_timestamp)]
                for k in dev.raw: #device_item_list:
                    if config['list_all_items']:
                        logging.debug( k )
                    if k[0] in device_item_list and k[1] is not None:
                        ivlist += [ZabbixMetric( tradfri_hostname,
                                    f'{key_begin}.{k[0]}{key_end}', k[1], epoch_timestamp)]
                    if k[0] == 'ota_update_state' and occasional_loop:
                        if k[1] != 0 and dev.light_control is None and dev.socket_control is None:
                            devices_commands_frequent += [devices_commands[devcount]]
                for k in dev.device_info.raw:
                    if config['list_all_items']:
                        logging.debug (k)
                    if k[0] in device_info_item_list and k[1] is not None:
                        ivlist += [ZabbixMetric( tradfri_hostname,
                                f'{key_begin}.device_info.{k[0]}{key_end}',
                                k[1],epoch_timestamp)]
                #light_control
                if dev.light_control is not None:
                    if occasional_loop: #add to frequent
                        devices_commands_frequent += [devices_commands[devcount]]
                    for k in dev.light_control.raw[0]:
                        if config['list_all_items']:
                            logging.debug(f'list_all_items.light_control {k[0]}, {k[1]},{type(k)}')
                        if k[0] in device_light_item_list and k[1] is not None:
                            ivlist += [ZabbixMetric( tradfri_hostname,
                                    f'{key_begin}.light_control.{k[0]}{key_end}',
                                    k[1],epoch_timestamp)]
                #socket_control
                if dev.socket_control is not None:
                    if occasional_loop:
                        devices_commands_frequent += [devices_commands[devcount]]
                    for k in dev.socket_control.raw[0]:
                        if config['list_all_items']:
                            logging.debug(f'list_all_items.socket_control {k[0]}, {k[1]},{type(k)}')
                        if k[0] in device_socket_item_list and k[1] is not None:
                            ivlist += [ZabbixMetric( tradfri_hostname,
                                    f'{key_begin}.socket_control.{k[0]}{key_end}',
                                    k[1],epoch_timestamp)]
                #send to zabbix
                zabbix_send_result = send_zabbix_packet(ivlist, zabbix_config, do_send=config['do_zabbix_send'] )
                log_zabbix_send_result(zabbix_send_result)
        logging.debug("*** END Polling devices for loop")
        # devices_commands_frequent should not have duplicates
        if config['gateway_detailed_debug'] and occasional_loop:
            print('devices_commands_frequent')
            pprint.pp(devices_commands_frequent)
        logging.debug('** gateway info')
        gateway_item_list = ['ota_update_state','firmware_version','first_setup',
                             'ota_type','update_progress', 'commissioning_mode']
        logging.debug('** gateway endpoint')
        time.sleep(sleep_between_api_calls)# try sleeping between api calls to GW
        no_gateway_data_state = False
        #
        gateway_info_command = gateway.get_gateway_info()
        gateway_data_result = try_n_times( api, gateway_info_command ,
                                         expected_exceptions=( gateway_expected_exceptions ),
                                         try_slowly_seconds=sleep_short_between_api_calls)
        #gateway_data = api(gateway_data_result).raw
        logging.debug(f'** get gateway data: try_n_times.success: {try_n_times.success}')
        gateway_data = gateway_data_result.raw
        ## if not no_gateway_data_state: # not critical if this isn't sent each iteration
        if try_n_times.success: # not critical if this isn't sent each iteration
            ivlist=[]
            for k in gateway_data:
                if config['list_all_items']:
                    logging.info(f'list_all_items: gateway: {k}')
                if k[0] in gateway_item_list:
                    ivlist += [ZabbixMetric( config['monitored_hostname'],
                            f'{key_prefix}.gateway.{k[0]}', k[1], epoch_timestamp)]
            zabbix_send_result = send_zabbix_packet(ivlist, zabbix_config, do_send=config['do_zabbix_send'] )
            log_zabbix_send_result(zabbix_send_result)
        #
        # TODO: send uptime and debug/failure info to zabbix, exception counts.
        # TODO: restarting the gateway via a relay.
        # 
        epoch_timestamp_last = epoch_timestamp
        logging.info(f'try_slowly.expected_exception_count: {try_slowly.expected_exception_count}, '
                  f'try_slowly.unexpected_exception_count: {try_slowly.unexpected_exception_count}')
        if config['do_it_once']:
            break
        uptime = int(time.time()) - epoch_timestamp_start
        logging.info(f'uptime: {uptime} seconds.')
        # calculate sleep
        iteration_time= int(time.time()) - epoch_timestamp
        sleep_time = polling_interval - iteration_time
        logging.info(f'This iteration took {iteration_time} seconds.')
        if sleep_time > 0:
            logging.info(f'Sleeping for {sleep_time} seconds.')
            time.sleep(sleep_time)
    #end while
main()

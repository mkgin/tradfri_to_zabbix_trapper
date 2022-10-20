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
# for restarting gateway
import urllib.request
import ssl
# for config
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

restart_gateway_count = 0
restart_gateway_timestamp_list = []

def restart_gateway():
    """
    This will depend on your setup. I use a esp-01 and relay board.
    Power to the gateway is through the NC (normally closed) contact and common so power cycling
    is accomplished by turning relay on for a second then off.

    Don't restart if last restart was within config['gateway_restart_min_interval']
    quit if gateway_restart_fail_count_exceeds exceeded in gateway_restart_fail_interval
    """
    global restart_gateway_count, restart_gateway_timestamp_list
    # don't check the host certificate if using SSL/TLS
    ssl._create_default_https_context = ssl._create_unverified_context
    config = load_config()
    if not config['gateway_restart_enabled']:
        logging.error('** gateway_restart_enabled: False')
        logging.error('** gateway is not responding to requests. Quitting...')
        raise
    relay_on = config['relay_host'] + '/' + config['relay_on_path']
    relay_off = config['relay_host'] + '/' + config['relay_off_path']
    sleep_time_factor = 1
    za_key_start = config['key_prefix'] + '.gateway.'
    # do not restart if  last restart < config['gateway_restart_min_interval']
    if count_timestamps_in_interval(restart_gateway_timestamp_list,
                                    interval=config['gateway_restart_min_interval']) > 0:
        logging.info('already restarted within last ' +
                     repr(config['gateway_restart_min_interval']) +' s')
        logging.info('sleeping for ' + repr(config['gateway_restart_time']/5) +
                     ' s before trying again')
        relay_urls = [relay_off] # just make sure relay is off
        sleep_time_factor = 0.2 # sleep less if not resetting
        # tell zabbix we are not restarting
        za_device_send = [ZabbixMetric( config['monitored_hostname'], za_key_start + 'restart',
                                    'min_interval_no_restart' )]
        zabbix_send_result = send_zabbix_packet(za_device_send, config['zabbix_sender_settings'],
                                                do_send=config['do_zabbix_send'])
    else:
        restart_gateway_count += 1
        restart_gateway_timestamp_list += [int(time.time())]
        # quit if gateway_restart_fail_count_exceeds exceeded in gateway_restart_fail_interval
        logging.debug('restart_gateway: config gateway_restart_fail_interval: ' +
                      repr(config['gateway_restart_fail_interval']))
        logging.debug('restart_gateway: config gateway_restart_fail_count_exceeds: ' +
                      repr(config['gateway_restart_fail_count_exceeds']))
        logging.debug('restart_gateway: count_timestamps ' +
                      repr(count_timestamps_in_interval(restart_gateway_timestamp_list,
                      interval=config['gateway_restart_fail_interval'])))
        if count_timestamps_in_interval(restart_gateway_timestamp_list,
                                        interval=config['gateway_restart_fail_interval'])\
                                        > config['gateway_restart_fail_count_exceeds']:
            logging.error('** gateway_restart over ' +
                         repr(config['gateway_restart_fail_count_exceeds']) + ' times in last ' +
                         repr(config['gateway_restart_fail_interval']) + ' s')
            # tell zabbix we are quitting
            za_device_send = [ZabbixMetric( config['monitored_hostname'], za_key_start + 'restart',
                                       'fail_count_in_interval_exceeded' )]
            zabbix_send_result = send_zabbix_packet(za_device_send,config['zabbix_sender_settings'],
                                                   do_send=config['do_zabbix_send'])
            raise
        else:
            relay_urls = [relay_on, relay_off]
            # tell zabbix we are restarting
            za_device_send = [ZabbixMetric( config['monitored_hostname'], za_key_start + 'restart',
                                        'restarting' )]
            zabbix_send_result = send_zabbix_packet(za_device_send,config['zabbix_sender_settings'],
                                                    do_send=config['do_zabbix_send'] )
            logging.warning('restarting the gateway')
    # TODO: error handling in case response != 200, timeout, etc.
    for url in relay_urls:
        logging.info(f'fetching url...')
        with urllib.request.urlopen(url) as response:
            bodyhtml = response.read()
            response_code = response.getcode()
        # tell zabbix we are talking to the relay host
        # just keep these in the Gateway host template.
        za_device_send = [ZabbixMetric(config['monitored_hostname'], za_key_start + 'relay',
                                   f'{response_code},{bodyhtml}' )]
        zabbix_send_result = send_zabbix_packet(za_device_send, config['zabbix_sender_settings'],
                                                do_send=config['do_zabbix_send'])
        logging.warning(f'response_code: {response_code}\n{bodyhtml}' )
        time.sleep(config['relay_on_time'])
    logging.info('sleeping for ' + repr(config['gateway_restart_time'] * sleep_time_factor) +
                 ' s so gateway has time to come up after restart')
    time.sleep(config['gateway_restart_time'] * sleep_time_factor)
    logging.info('done sleeping, resuming polling the gateway.')

def main():
    """main."""
    global restart_gateway_count, restart_gateway_timestamp_list
    device_item_list = ['name','ota_update_state',
                   'application_type', 'last_seen', 'reachable']

    # 'id' and 'created_at' are used to create a unique id
    # not interested yet 'air_purifier_control', blind_control, signal_repeater_control
    device_light_item_list = ['state', 'dimmer','color_hex', 'color_mireds',
                              'color_xy_x', 'color_xy_y','color_hue', 'color_saturation']
    device_info_item_list = [ 'firmware_version', 'power_source', 'battery_level','model_number' ]
    device_socket_item_list = ['id','state']
    device_discovery = True # or False
    # a Tuple... leave last comma ( x, ) if just one item
    gateway_expected_exceptions = (RequestTimeout, TypeError )
    #logging.basicConfig(level=logging.INFO)
    logging.basicConfig(level=logging.DEBUG)
    config = load_config()
    key_prefix = config['key_prefix']
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
    #no_gateway_data_counter = 0 # counter for data not recieved from gateway
    first_loop = True
    epoch_timestamp_last = int(time.time())
    epoch_timestamp_start = epoch_timestamp_last
    api = api_factory.request
    gateway = Gateway()
    gateway_restart = False
    # main loop starts here
    while True: # breaks at end for single run
        # this is the best place to restart the gateway if needed
        if gateway_restart:
            restart_gateway()
            first_loop = True
            gateway_restart = False
            # TODO: Might want to test connecting and wait a bit if failing
        epoch_timestamp = int(time.time())
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
            logging.debug(f'** devices_command_all: {devices_command_all}')
            try:
                devices_commands_all = \
                    try_n_times(api, devices_command_all,expected_exceptions =
                                gateway_expected_exceptions)
            except TooManyRetries:
                logging.warning('** get devices_commands failed')
                gateway_restart = True
                continue
            # time.sleep(sleep_between_api_calls) # try sleeping between api calls to GW
            logging.debug(f'** devices_commands_all {devices_commands_all}')
            # TODO: Test API call suceeded
            # if try_n_times.success:
            # else reset gateway and "continue" (new while loop, as first_loop when its up

            if config['gateway_detailed_debug']:
                print(f'devices_commands_all: type{devices_commands_all}')
                pprint.pp(devices_commands_all)
            # Create dictionary for device group names and ids
            #""" get group name  or id from a device with this dictionary
            #    eg: device_group_dict['65582']['name']
            #        device_group_dict['65582']['groupid'])
            #"""
            group_item_list = ['id','name','group_members']
            device_group_dict = {}
            logging.debug('gateway.get_groups()')
            try:
                groups = api(gateway.get_groups())   # get  groups api call
                logging.debug(f'groups: {groups}')
            except:
                logging.debug(f'get_groups failed {groups}')
                raise ## TODO:FIXME!! checking if we fail here often
            for group in groups:
                logging.debug(f'for groups in group: {group}, api(group)')
                groupname = groupid = groupdevs = ''
                try:
                    api_group_result = try_n_times(api, group,
                                            expected_exceptions=( gateway_expected_exceptions ),
                                            try_slowly_seconds=sleep_short_between_api_calls)
                except TooManyRetries:
                    logging.warning('** get group failed')
                    gateway_restart = True
                    break
                # TODO: Test API call suceeded
                # if try_n_times.success:
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
        if gateway_restart:
            continue
        ## End of if 'first_loop'/occasional_loop
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
            if gateway_restart:
                break
            print(f'devcount: {devcount}')
            try:
                dev = try_n_times( api,devices_commands[devcount],
                                   expected_exceptions=( gateway_expected_exceptions ),
                                   try_slowly_seconds=sleep_short_between_api_calls)
            except TooManyRetries:
                logging.warning(f'** get device_command failed for {devices_commands[devcount]}')
                gateway_restart = True
                break
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
                zabbix_send_result = send_zabbix_packet(za_device_send, zabbix_config,
                                                        do_send=config['do_zabbix_send'] )
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
                zabbix_send_result = send_zabbix_packet(ivlist, zabbix_config,
                                                        do_send=config['do_zabbix_send'] )
                log_zabbix_send_result(zabbix_send_result)
        logging.debug("*** END Polling devices for loop")
        if gateway_restart:
            continue
        # devices_commands_frequent should not have duplicates
        if config['gateway_detailed_debug'] and occasional_loop:
            print('devices_commands_frequent')
            pprint.pp(devices_commands_frequent)
        logging.debug('** gateway info')
        gateway_item_list = ['ota_update_state','firmware_version','first_setup',
                             'ota_type','update_progress', 'commissioning_mode']
        logging.debug('** gateway endpoint')
        time.sleep(sleep_between_api_calls)# try sleeping between api calls to GW
        #no_gateway_data_state = False
        #
        gateway_info_command = gateway.get_gateway_info()
        try:
            gateway_data_result = try_n_times( api, gateway_info_command ,
                                   expected_exceptions=( gateway_expected_exceptions ),
                                   try_slowly_seconds=sleep_short_between_api_calls)
        except TooManyRetries:
            logging.warning(f'** get gateway info command failed')
        #gateway_data = api(gateway_data_result).raw
        logging.debug(f'** get gateway data: try_n_times.success: {try_n_times.success}')
        gateway_data = gateway_data_result.raw
        # not critical if this isn't sent each iteration, it will fail next time if the
        # gateway needs to be restarted
        if try_n_times.success: # not critical if this isn't sent each iteration
            ivlist=[]
            for k in gateway_data:
                if config['list_all_items']:
                    logging.info(f'list_all_items: gateway: {k}')
                if k[0] in gateway_item_list:
                    ivlist += [ZabbixMetric( config['monitored_hostname'],
                            f'{key_prefix}.gateway.{k[0]}', k[1], epoch_timestamp)]
            zabbix_send_result = send_zabbix_packet(ivlist, zabbix_config,
                                                    do_send=config['do_zabbix_send'] )
            log_zabbix_send_result(zabbix_send_result)
        # TODO: send uptime and debug/failure info to zabbix, exception counts.
        epoch_timestamp_last = epoch_timestamp
        logging.info(f'try_slowly.expected_exception_count: {try_slowly.expected_exception_count}')
        logging.info(f'try_slowly.unexpected_exception_count: {try_slowly.unexpected_exception_count}')
        logging.info(f'restart_gateway_count: {restart_gateway_count}')
        logging.info('gateway_restarted ' +
                     repr(count_timestamps_in_interval(restart_gateway_timestamp_list,
                                                       interval=3600))
                     + ' times in last hour')
        uptime = int(time.time()) - epoch_timestamp_start
        if uptime < 86400:
            log_string = 'since start'
        else:
            log_string = 'in the last 24 hours'
        logging.info('gateway_restarted ' +
                     repr(count_timestamps_in_interval(restart_gateway_timestamp_list,
                                                       interval=86400))
                     + f' times {log_string}')
        logging.debug(f'restart_gateway_timestamp_list: {restart_gateway_timestamp_list}')
        if config['do_it_once']:
            break
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

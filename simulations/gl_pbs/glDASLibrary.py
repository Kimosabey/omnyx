#!/usr/bin/env python
################## Context Logging ###################
from inspect import currentframe, getframeinfo
################## Time Operations ###################
from datetime import date, time, datetime, timedelta
################## Input File Processing csv and json ###################
import csv, json, random
################## DB Operations ###################
NO_DB_CONNECTOR = False

try:
	import mysql.connector
	import mysql.connector.pooling
except ImportError:
	NO_DB_CONNECTOR = True

################## Notify to Recipients ###################
import asyncio
import httpx
# import nest_asyncio
# nest_asyncio.apply()
# import tracemalloc
# tracemalloc.start()
################## timeit - performance analysis ###################
import timeit
import time as _time
################## socket - socket connectivity ###################
import socket,os
################## uuid - for unique ids #################
import uuid, abc
################################################################

# input file content format
# 127.0.0.1:2337,2:124,objectName,presentValue,2:125,objectName,presentValue,2:128,objectName,presentValue,2:122,objectName,presentValue,2:126,objectName,presentValue,2:127,objectName,presentValue,2:123,objectName,presentValue
# 127.0.0.1:2327,2:214,objectName,presentValue,2:215,objectName,presentValue,2:216,objectName,presentValue,2:218,objectName,presentValue,2:219,objectName,presentValue,2:213,objectName,presentValue,2:217,objectName,presentValue
# curl http://localhost:7080/discoverobjects_nosegmentation/192.168.0.106:2001/8:2001
# INSERT INTO gl_subsystem (id, name, ss_tag, description, ss_type, ss_address_type, ss_address_value) VALUES (uuid(), 'ESSL-2001', 2001, 'CPM Each 5', 'GL_SS_ADDRESS_BACNET_DDC', 'GL_SS_ADDRESS_IP', '127.0.0.1:2001')
# curl --header "Content-Type: application/json" -d "{\"id\":\"d756a9e9-2013-11ef-ba7d-1cbfc035e11f\"}" -k https://localhost:8443/v1/devices/registerBacnetDevice

# point list, set according to your devices - sample
gl_point_list = [
    ('10.0.1.14', [
        ('analogValue:1', 'presentValue'),
        ('analogValue:2', 'presentValue'),
        ]),
    ('10.0.1.15', [
        ('analogValue:1', 'presentValue'),
        ('analogValue:2', 'presentValue'),
        ]),
    ]
gl_configuration = {}
_GL_GLOBALS = {}
def getstrTimeNow():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

def myerror(*objects, sep=' ', end='\n', file=None, flush=False):
    print(getstrTimeNow(),*objects, sep=sep, end=end, file=file, flush=flush)
    # pass

def myprint(*objects, sep=' ', end='\n', file=None, flush=False):
    # print(getstrTimeNow(),*objects, sep=sep, end=end, file=file, flush=flush)
    pass

def printDebug(arg):pass
    #print('{}-{}'.format(getstrTimeNow(),arg))

def printTrace(msg):
    print('TR:{} {}'.format(getstrTimeNow(), msg))

def getRandomAnalogInput(low_limit=0.0, high_limit=100.0, digits=2):
    return round(random.uniform(low_limit,high_limit),digits)

def getRandomBinaryOutput():
    return random.choice([0,1])

def getMyRandomMultiStateValue(number_of_states):
    return random.randint(0, number_of_states - 1)

def getRandomAnalogOutput():
    return round(random.uniform(0,10),2)

def mythread_dump(*objects, sep=' ', end='\n', file=None, flush=False, fileName=None):
    pass
    # try:
    #     if fileName != None:
    #         myfile = open(fileName, "a")
    #         print(getstrTimeNow(),*objects, sep=sep, end=end, file=myfile, flush=flush)
    #         myfile.close()
    #     else:
    #         print(getstrTimeNow(),*objects, sep=sep, end=end, file=None, flush=flush)
    # except:
    #     print(getstrTimeNow(),*objects, sep=sep, end=end, file=None, flush=flush)

# def getLocalIPAddress(port=1940, noNetwork=False, noPort=False):
#     # https://www.delftstack.com/howto/python/get-ip-address-python/
#     deviceIp = '127.0.0.1'
#     if noNetwork == False:
#         s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#         s.connect(("8.8.8.8", 80))
#         deviceIp = s.getsockname()[0]
#     if noPort == True:
#         return deviceIp
#     else:
#         return '{}:{}'.format(deviceIp, port)
#     # return '192.168.1.220:1903'

def getLocalIPAddress_wifi(port=1940, noNetwork=False, noPort=True, useEthernet=False, defaultIp=None, autoDetectIp=True):
    # Highest priority - useEthernet
    # useEthernet and 
    # https://www.delftstack.com/howto/python/get-ip-address-python/
    # deviceIp = '127.0.0.1'
    # if noNetwork == False:
    #     s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    #     s.connect(("8.8.8.8", 80))
    #     deviceIp = s.getsockname()[0]

    if defaultIp == None: defaultIp = os.getenv("HOST", "")
    deviceIp = '192.168.1.220' #'127.0.0.1'#
    if useEthernet == True:
        deviceIp = defaultIp
    # elif noNetwork == True:
    #     deviceIp = '127.0.0.1'
    else:
        if autoDetectIp == True:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                deviceIp = s.getsockname()[0]
            except:
                print('Unable to connect to network. Handle Network Connectivity Error ======')
        else:
            deviceIp = defaultIp

    if noPort == False:
        return '{}:{}'.format(deviceIp, port)
    else:
        return deviceIp
    
def ipaddress_from_string(s):
    return s

def get_all_unix_ips():
    import netifaces
    ips = set()
    interfaces = netifaces.interfaces()
    for interface in interfaces:
        addresses = netifaces.ifaddresses(interface)
        for address_family in (netifaces.AF_INET, netifaces.AF_INET6):
            family_addresses = addresses.get(address_family)
            if not family_addresses:
                continue
            for address in family_addresses:
                ips.add(ipaddress_from_string(address['addr']))
    return sorted(ips)

import os, socket
def checkEthernetIPAddress(myaddress,interface='eth0'):
    platform = os.name
    if platform == 'posix':
        try:
           
           ips=get_all_unix_ips()
           if myaddress in ips:
               return myaddress
           else:
               return '127.0.0.1'
        except Exception as e:
            print("Error getting IP address:", e)
            return '127.0.0.1'
        
    elif platform == 'nt':
        try:
           
            ip_addresses = socket.gethostbyname_ex(socket.gethostname())[2]
            ipv4_addresses = [addr for addr in ip_addresses if ':' not in addr]
            if myaddress in ipv4_addresses:
                return myaddress
            else:
                return '127.0.0.1'

        except Exception as e:
            print("Error getting IP address:", e)
            return '127.0.0.1'
    

def getLocalIPAddress_eth(noNetwork=False, useEthernet=True, defaultIPAddress=None):
    global logger,GL_GLOBALS
    myip = None
    if defaultIPAddress == None: defaultIPAddress= GL_GLOBALS['DEFAULT_IP_ADDRESS']#192.168.1.200
    printTrace('Default IP Address {}'.format(defaultIPAddress))
    if useEthernet == True:
        myip=checkEthernetIPAddress(defaultIPAddress)
        return myip
    elif noNetwork:
        # return '{}'.format('127.0.0.1')
        return '127.0.0.1'
    else:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # s.connect(("8.8.8.8", 80))
            s.connect(("10.254.254.254", 1))
            print('Socket Details: {}'.format(s.getsockname()))
            myip = s.getsockname()[0]

        except Exception as err:
            # _log.exception("an error has occurred: %s", err)
            if logger is not None: logger.error('GL_{}: Network Error: Not getting IP Address'.format(10001))
        finally:
            printTrace('My IP Address: {}'.format(myip))
            # if _debug:
            #     _log.debug("finally address is %s", myip)
        # https://www.delftstack.com/howto/python/get-ip-address-python/

        return myip
    
def getLocalIPAddress(port=1940, noNetwork=False, noPort=True, useEthernet=False, defaultIp=None, autoDetectIp=True):
    # import os, socket
    # Highest priority - useEthernet
    # useEthernet and 
    # https://www.delftstack.com/howto/python/get-ip-address-python/
    deviceIp = '127.0.0.1'
    # if noNetwork == False:
    #     s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    #     s.connect(("8.8.8.8", 80))
    #     deviceIp = s.getsockname()[0]

    if defaultIp == None: defaultIp = os.getenv("HOST", "")
    if useEthernet == True:
        deviceIp=checkEthernetIPAddress(defaultIp)
    elif noNetwork:
        # return '{}'.format('127.0.0.1')
        deviceIp =  '127.0.0.1'
    else:
        if autoDetectIp == True:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                deviceIp = s.getsockname()[0]
            except:
                print('Unable to connect to network. Handle Network Connectivity Error ======')
        else:
            deviceIp = defaultIp

    if noPort == False:
        return '{}:{}'.format(deviceIp, port)
    else:
        return deviceIp


def getHexString(num, places=4):
    result = ''
    if places == 4:
        result = '{0:04x}'.format(num)
    elif places == 3:
        result = '{0:03x}'.format(num)
    elif places == 2:
        result = '{0:02x}'.format(num)
    else:
        result = '{0:x}'.format(num)
    return result

def getRequestUUID(myquery={}):
    id_present = False
    if 'id' in myquery:
        if isinstance(myquery['id'], abc.Sequence):
            test_request_id = str(myquery['id'][0])
        else:
            test_request_id = str(myquery['id'])
        try:
            id_present = uuid.UUID(test_request_id, version=4)
        except ValueError:
            id_present = False
    if id_present == False:
        test_request_id = str(uuid.uuid4())
    return test_request_id

def setConfigurationDetails(glInputConfig = None):
    getBool = lambda value: True if value == 'True' else False
    myprint('setConfigurationDetails Input: {}'.format(glInputConfig))
    glConfig = {
        'rpmRequestsFile': 'cpm_reader.txt',#'loadTest/Samples_1065.txt',#'CompleteCodeUsed/infor_reader.txt',#'cpm_reader.txt',#'Read10Chillers.txt',#'Samples_1065.txt', 'Read75Chillers.txt',#'sample.txt',#'sample50_Pumps.txt', #'glRequestsFile.txt', #
        'deploymentConfigFile': 'glIBMSDeployment.json',
        'useReadPropertyMultiple': True,
        'interBatchInterval': 0.2, #2.0, # Minutes between successive batch data loads
        'checkCoV': True,
        'notifyReadData': 'ONLY_COV',#'DONOT_NOTIFY', #'ALL_RM', #  One of ALL_RM,
        'postURL': 'https://localhost:8443/v1/newapis/mypost/',
        'threadDumpFilePrefix': 'tdout_',
        'USE_OBJECT_NAME_HANDLER': False,
        'recurringDataLoad': True,
        'numberOfReadCycles': -1,
        'insertRMDataintoDB': True,
        'dbConnectionPool': None,
        'ibms_database_name': 'tepldb',#'das_pbs_2',#
        'database_table_name': '',#'vav_0000b5c010_ahu_om_p',
        'usePerEquipmentTable': True,#True to use per equipment table
        'numberOfReadingThreads': 250,
        'useLocalDDCSimulators': True,
        'discoverDeviceIPAddress': True,
        'myBACnetPort': 1928,
        'CoVComputationWithinThread': True,
        'storeEquipmentParameterData': True,
        'useInThreadCoVCheck': True,# DONT CHANGE THIS
        'useMultipleTables': True,
        'createEquipmentTable': True,
        # Use a Global Interval Counter – to handle multiple polling intervals
        'timeIntervalCounter': -1,# No Need to CHANGE THIS
        'counterLimit': 12,#900,
        'allowMultipleSamplingRates': True,
        'rpmBatchSize': 15,

        'databasehost': 'localhost',
        'databaseuser': 'ibms_db',
        'databaseTableNameLength': 12,
        'databasehost': 'localhost',
        'databaseuser': 'ibms_db',
        'databaseTableNameLength': 12,
        'enablePBS2web': True,
        'PBS2Webport': 7060,
        'useEthernet': False,
        'defaultIPAddress': '127.0.0.1',
        'autoDetectIP': True,
        'databasePassword': '1234',
        'counterLimit': 13,
        'GLCodeBookCSV': './CBParameters.csv',
        'deploymentDetailsFile': './GLSDeploymentDetails.json',
        'webPostTimeoutSecs': 2.5,
        'dataAcquisitionHeartbeatMinutes': 15,
        'dataAcquisitionTimeoutSecs': 15,
        'CoVThresholdPercent': 12,
        'dataAcquisitionMaximumRetryAttempts': 3,
        'controllermap': {"DDC1":"127.0.0.1:7090"},
        'mstpNetworksMap': {}
	  }
    if glInputConfig is None:
        pass
        '''
        glConfig = {
            'rpmRequestsFile': 'Read75Chillers.txt',# 'sample50_Pumps.txt', #'glRequestsFile.txt',
            'interBatchInterval': 5, # Minutes between successive batch data loads
            'checkCoV': True,
            'notifyReadData': 'ALL_RM', # One of ALL_RM, ONLY_COV, DONOT_NOTIFY
            'postURL': 'http://localhost:8443/mypost',
            'threadDumpFilePrefix': 'tdout_',
            'USE_OBJECT_NAME_HANDLER': False,
            'recurringDataLoad': True
        }
        '''
    else:
        if 'rpmrequestsfile' in glInputConfig: glConfig['rpmRequestsFile'] = glInputConfig['rpmrequestsfile']
        if 'deploymentconfigfile' in glInputConfig: glConfig['deploymentConfigFile'] = glInputConfig['deploymentconfigfile']
        if 'usereadpropertymultiple' in glInputConfig: glConfig['useReadPropertyMultiple'] = getBool(glInputConfig['usereadpropertymultiple'])
        # if 'useReadPropertyMultiple': True,
        if 'interbatchinterval' in glInputConfig: glConfig['interBatchInterval'] = float(glInputConfig['interbatchinterval'])
        if 'checkcov' in glInputConfig: glConfig['checkCoV'] = bool(glInputConfig['checkcov'])
        if 'notifyreaddata' in glInputConfig: glConfig['notifyReadData'] = glInputConfig['notifyreaddata']
        if 'posturl' in glInputConfig: glConfig['postURL'] = glInputConfig['posturl']
        if 'threaddumpfileprefix' in glInputConfig: glConfig['threadDumpFilePrefix'] = glInputConfig['threaddumpfileprefix']
        if 'use_object_name_handler' in glInputConfig: glConfig['USE_OBJECT_NAME_HANDLER'] = getBool(glInputConfig['use_object_name_handler'])
        if 'recurringdataload' in glInputConfig: glConfig['recurringDataLoad'] = getBool(glInputConfig['recurringdataload'])
        if 'numberofreadcycles' in glInputConfig: glConfig['numberOfReadCycles'] = int(glInputConfig['numberofreadcycles'])
        if 'insertrmdataintodb' in glInputConfig: glConfig['insertRMDataintoDB'] = getBool(glInputConfig['insertrmdataintodb'])
        if 'ibms_database_name' in glInputConfig: glConfig['ibms_database_name'] = glInputConfig['ibms_database_name']
        if 'database_table_name' in glInputConfig: glConfig['database_table_name'] = glInputConfig['database_table_name']
 
        if 'useperequipmenttable' in glInputConfig: glConfig['usePerEquipmentTable'] = getBool(glInputConfig['useperequipmenttable'])
        if 'uselocalddcsimulators' in glInputConfig: glConfig['useLocalDDCSimulators'] = getBool(glInputConfig['uselocalddcsimulators'])
        if 'discoverdeviceipaddress' in glInputConfig: glConfig['discoverDeviceIPAddress'] = getBool(glInputConfig['discoverdeviceipaddress'])
        if 'mybacnetport' in glInputConfig: glConfig['myBACnetPort'] = int(glInputConfig['mybacnetport'])
        if 'storeequipmentparameterdata' in glInputConfig: glConfig['storeEquipmentParameterData'] = getBool(glInputConfig['storeequipmentparameterdata'])
        if 'usemultipletables' in glInputConfig: glConfig['useMultipleTables'] = getBool(glInputConfig['usemultipletables'])
        if 'createequipmenttable' in glInputConfig: glConfig['createEquipmentTable'] = getBool(glInputConfig['createequipmenttable'])
        if 'allowmultiplesamplingrates' in glInputConfig: glConfig['allowMultipleSamplingRates'] = getBool(glInputConfig['allowmultiplesamplingrates'])

# Configurations Added
        if 'databasehost' in glInputConfig: glConfig['databasehost'] = glInputConfig['databasehost']
        if 'databaseuser' in glInputConfig: glConfig['databaseuser'] = glInputConfig['databaseuser']
        if 'databasetablenamelength' in glInputConfig: glConfig['databaseTableNameLength'] = int(glInputConfig['databasetablenamelength'])
        # if 'numberofreadcycles' in glInputConfig: glConfig['numberOfReadCycles'] = int(glInputConfig['numberofreadcycles'])
        if 'enablepbs2web' in glInputConfig: glConfig['enablePBS2web'] = getBool(glInputConfig['enablepbs2web'])
        if 'pbs2webport' in glInputConfig: glConfig['PBS2Webport'] = int(glInputConfig['pbs2webport'])
        if 'useethernet' in glInputConfig: glConfig['useEthernet'] = getBool(glInputConfig['useethernet'])
        if 'defaultipaddress' in glInputConfig: glConfig['defaultIPAddress'] = glInputConfig['defaultipaddress']
        if 'autodetectip' in glInputConfig: glConfig['autoDetectIP'] = getBool(glInputConfig['autodetectip'])
        if 'databasepassword' in glInputConfig: glConfig['databasePassword'] = glInputConfig['databasepassword']
        if 'counterlimit' in glInputConfig: glConfig['counterLimit'] = int(glInputConfig['counterlimit'])
        if 'glcodebookcsv' in glInputConfig: glConfig['GLCodeBookCSV'] = glInputConfig['glcodebookcsv']
        if 'deploymentdetailsfile' in glInputConfig: glConfig['deploymentDetailsFile'] = glInputConfig['deploymentdetailsfile']
        if 'webposttimeoutsecs' in glInputConfig: glConfig['webPostTimeoutSecs'] = float(glInputConfig['webposttimeoutsecs'])
        if 'dataacquisitionheartbeatminutes' in glInputConfig: glConfig['dataAcquisitionHeartbeatMinutes'] = float(glInputConfig['dataacquisitionheartbeatminutes'])
        if 'dataacquisitiontimeoutsecs' in glInputConfig: glConfig['dataAcquisitionTimeoutSecs'] = float(glInputConfig['dataacquisitiontimeoutsecs'])
        if 'covthresholdpercent' in glInputConfig: glConfig['CoVThresholdPercent'] = float(glInputConfig['covthresholdpercent'])
        if 'dataacquisitionmaximumretryattempts' in glInputConfig: glConfig['dataAcquisitionMaximumRetryAttempts'] = int(glInputConfig['dataacquisitionmaximumretryattempts'])
        if 'controllermap' in glInputConfig: glConfig['controllermap'] = json.loads(glInputConfig['controllermap'])
        if 'mstpnetworksmap' in glInputConfig: glConfig['mstpNetworksMap'] = json.loads(glInputConfig['mstpnetworksmap'])
        if 'rpmbatchsize' in glInputConfig: glConfig['rpmBatchSize'] = int(glInputConfig['rpmbatchsize'])
    return glConfig
def initializeNH(mynamesfile='data/eqp_name_handling.csv'):
    global _GL_GLOBALS
    nrows = -1

    myobj = {}
    with open(mynamesfile) as csvFile:
        reader = csv.DictReader(csvFile)
        for row in reader:
            myprint(row)
            ddc = row['ddc_id']
            oid_key = '{}:{}'.format(row['obj_type'], row['obj_id'])
            if ddc not in myobj:
                myobj[ddc] = {}
                myprint(myobj)
            myobj[ddc][oid_key] = [row['eqp'], row['gl_param_name'], row['display_name'], row['gl_code']]
            nrows += 1
    myprint(myobj)
    printTrace('initializeNH Loaded - {} Objects'.format(nrows))
    _GL_GLOBALS['csv_data_ini'] = myobj
###########################################################################################################

def preparePointListFromNH(fileName='data/eqp_name_handling.csv', rpm=False, makeNameList=False,
                            useLocalDDCSimulators=True, myip=None, tblNameLength=12, ddcmapper={},
                            batchSize=15):
    """
    Single-source replacement for preparePointList() + initializeNH().

    Reads eqp_name_handling.csv once to:
      1. Populate _GL_GLOBALS['csv_data_ini'] (name-handler lookup).
      2. Build and return the BACnet point list in the same format as
         preparePointList(), honouring the optional 'Skip' column.

    CSV columns: ddc_id, obj_type, obj_id, eqp, gl_param_name, display_name,
                 gl_code, skip
    Set skip = Y (or YES / 1 / TRUE) on any row to exclude that point from
    BACnet reads while still keeping it in the name-handler lookup.

    Returns: (pt_list, on_list) when makeNameList=True, else pt_list.
    """
    global _GL_GLOBALS

    pt_list = []
    on_list = [] if makeNameList else None
    csv_data = {}           # → _GL_GLOBALS['csv_data_ini']
    device_points = {}      # ddc_id → [obj_type:obj_id, ...]   (read order preserved)

    try:
        if useLocalDDCSimulators:
            myip = getLocalIPAddress(noNetwork=False, noPort=True)

        with open(fileName, newline='', encoding='utf-8-sig') as csvFile:
            reader = csv.DictReader(csvFile)
            for row in reader:
                ddc_id   = row.get('ddc_id',        '').strip()
                obj_type = row.get('obj_type',       '').strip()
                obj_id   = row.get('obj_id',         '').strip()
                eqp      = row.get('eqp',            '').strip()
                gl_param = row.get('gl_param_name',  '').strip()
                display  = row.get('display_name',   '').strip()
                gl_code  = row.get('gl_code',        '').strip()
                skip     = row.get('skip',           '').strip().upper()

                if not ddc_id or not obj_type or not obj_id:
                    continue

                # --- name-handler lookup (same structure as initializeNH) ---
                oid_key = '{}:{}'.format(obj_type, obj_id)
                if ddc_id not in csv_data:
                    csv_data[ddc_id] = {}
                csv_data[ddc_id][oid_key] = [eqp, gl_param, display, gl_code]

                # --- skip flagged points from the read list -----------------
                if skip in ('Y', 'YES', '1', 'TRUE'):
                    continue

                if ddc_id not in device_points:
                    device_points[ddc_id] = []
                device_points[ddc_id].append(oid_key)

        _GL_GLOBALS['csv_data_ini'] = csv_data
        total_pts = sum(len(v) for v in device_points.values())
        printTrace('preparePointListFromNH: {} devices, {} points to read'.format(
            len(device_points), total_pts))

        # --- build pt_list (chunked by batchSize points per entry) ----------
        for addr, points in device_points.items():
            (addr_clean, _samplingInterval) = getSamplingInterval_DAS(addr)
            addrNew = str(ddcmapper[addr_clean]) if addr_clean in ddcmapper else addr_clean
            if useLocalDDCSimulators and myip:
                addrNew = addrNew.replace('127.0.0.1', myip)

            # split into chunks so each RPM request stays within APDU limits
            chunks = [points[i:i + batchSize] for i in range(0, len(points), batchSize)]
            for chunk in chunks:
                # flat list: [objType:objId, presentValue, objType:objId, presentValue, ...]
                flat = []
                for oid in chunk:
                    flat.extend([oid, 'presentValue'])

                # Use the actual BACnet network address (addrNew) as entry[0]
                # so that iter_batch_entries and ReadPointListThread use the
                # correct IP:port for BACnet communication instead of the DDC ID.
                # Preserve any sampling-interval suffix from the original addr.
                addr_net = '{}@{}'.format(addrNew, _samplingInterval) if _samplingInterval else addrNew

                if rpm:
                    myONs = prepareObjectNamesAsPreviousValuesByLookup(
                        addr_clean, flat, tblNameLength=tblNameLength)
                    pt_list.append([addr_net, flat, {addrNew: myONs}])
                    if makeNameList:
                        name_flat = ['objectName' if x == 'presentValue' else x for x in flat]
                        on_list.append([addr_net, name_flat])
                else:
                    myONs = prepareObjectNamesAsPreviousValuesByLookup(
                        addr_clean, flat, tblNameLength=tblNameLength)
                    pt_list.append([addr_net, [(flat[i], flat[i + 1]) for i in range(0, len(flat), 2)], {addrNew: myONs}])
                    if makeNameList:
                        name_flat = ['objectName' if x == 'presentValue' else x for x in flat]
                        on_list.append([addr_net, [(name_flat[i], name_flat[i + 1])
                                              for i in range(0, len(name_flat), 2)]])

    except Exception as e:
        frameinfo = getframeinfo(currentframe())
        printTrace('Exception in file-{} function-{} line-{}'.format(
            frameinfo.filename, frameinfo.function, frameinfo.lineno))
        printTrace('Exception details: {}: {}'.format(type(e).__name__, e))

    return (pt_list, on_list) if makeNameList else pt_list

###########################################################################################################


def getSamplingInterval_DAS(myaddr, separator='@'):
    interval = 0
    ad_parts = myaddr.split(separator)
    if len(ad_parts) > 2:
        addr = myaddr
        printTrace('Unexpected ADDRESS input - {}; Assuming full parameter as BACnet Device Address'.format(myaddr))
    elif len(ad_parts) > 1:
        if ad_parts[1].isnumeric():
            interval = int(ad_parts[1])
        else:
            printTrace('Unexpected Sampling Interval input - {}; Assuming Default Sampling Interval'.format(ad_parts[1]))
        addr = ad_parts[0]
    else:
        addr = ad_parts[0]
    return (addr, interval)


###########################################################################################################
def preparePointList(fileName, separator=',', rpm=False, makeNameList=False, useLocalDDCSimulators=True, myip=None, useObjectNameHandler=False, tblNameLength=12, ddcmapper={}):
    pt_list = []
    f = None
    # myip = ''
    if makeNameList == True: on_list = []
    try:
      if useLocalDDCSimulators==True: myip = getLocalIPAddress(noNetwork=False, noPort=True)
    #   printTrace('fileName-{}, separator={}, rpm={}, makeNameList={}, useLocalDDCSimulators={}, myip={}, useObjectNameHandler={}'.format(fileName, separator, rpm, makeNameList, useLocalDDCSimulators, myip, useObjectNameHandler))
    #   if myip==None: myip = getLocalIPAddress(noNetwork=False, noPort=True)
      with open(fileName, "r") as f:
          if f != None:
              myprint('file--{}'.format(f))
          else:
              myprint('file--{} not found'.format(fileName))
          reader = csv.reader(f, delimiter=separator)
          for line in reader:
              if len(line) == 0: continue
              # Processing for multi rate Data Acquisition
              (addr, samplingInterval) = getSamplingInterval_DAS(line[0])
              addrNew = str(ddcmapper[addr]) if addr in ddcmapper else addr 
              if useLocalDDCSimulators == True: addrNew = addrNew.replace('127.0.0.1', myip)
              line[0] = line[0].replace(addr, addrNew)
              if makeNameList == True: nameLine = ['objectName' if x=='presentValue' else x for x in line]
              myprint('preparePointList ------ My Line = {} - addr - {} addrNew - {} Modified - {}'.format(line, addr, addrNew, line[0]))
              if rpm == True:
                  if (useObjectNameHandler == True):
                    #   self.previous_values[self.device_address][x][0]
                      # objectNames = {'192.168.1.61:2401': {'analogValue:177': ['', '', 0.0], 'analogValue:178': ['', '', 0.0], 'analogValue:179': ['', '', 0.0], 'analogValue:180': ['', '', 0.0]}}
                      # (addr, samplingInterval) = getSamplingInterval_DAS(line[0])
                      #printTrace("nameHandlerTrueMultiRateTrue-------->.{}-{}-{}".format(line[0],addr,samplingInterval)) 
                      myONs = prepareObjectNamesAsPreviousValuesByLookup(addr, line[1:],tblNameLength=tblNameLength)#
                    #   printTrace('My objectNames = {}'.format({line[0]:myONs}))
                      # pt_list.append([line[0], prepareRPMRequest(line[1:]), {line[0]:myONs}])
                      pt_list.append([line[0], prepareRPMRequest(line[1:]), {addrNew:myONs}])
                  else:
                      pt_list.append([line[0], prepareRPMRequest(line[1:])])
                  if makeNameList == True: on_list.append([nameLine[0], prepareRPMRequest(nameLine[1:])])
              else:
                #   pt_list.append((line[0], [tuple(line[1:])]))
                #   if makeNameList == True: on_list.append((nameLine[0], [tuple(nameLine[1:])]))
                # updated to work with DDC/PLC not supporting ReadMultiple                 
                # (addr, samplingInterval) = getSamplingInterval_DAS(line[0]) 
                pt_list.append([line[0], [(line[1:][i], line[1:][i+1]) for i in range(0, len(line[1:]), 2)]])
                printTrace("nameHandlerTrueMultiRateTrue-------->.{}-{}-{}-{}".format(line[0],addr,samplingInterval,nameLine)) 
                # pt_list.append([line[0], [(line[1:][i], line[1:][i+1]) for i in range(0, len(line[1:]), 2)]]) 
                if makeNameList == True: on_list.append([nameLine[0], [(nameLine[1:][i], nameLine[1:][i+1]) for i in range(0, len(nameLine[1:]), 2)]])
                # myprint('point---->',pt_list)
    except:
        frameinfo = getframeinfo(currentframe())
        printTrace("Exception in file-{} function-{} line-{}".format(frameinfo.filename, frameinfo.function, frameinfo.lineno))
    myprint('Sample pt_list:{}'.format(pt_list))
    # printTrace('Sample pt_list:{} - Count-{}'.format(pt_list[0], len(pt_list)))
    return (pt_list, on_list) if makeNameList == True else pt_list


def prepareRPMRequest(myinput, mysep=','):
    myprint('Input Now: {}'.format(myinput))
    bacnetArgs = []
    if isinstance(myinput, str):
        bacnetArgs = myinput.split(mysep)
    elif len(myinput) != None:
        bacnetArgs = myinput
    else:
        myprint('unexpected input: {}'.format(myinput))
    return bacnetArgs

def getObjectName2(ddc, oid, objType='analogValue'):
    # print("========IM here object name 2", ddc, oid, objnameddc, objType)
    global _GL_GLOBALS
    # print("im here 2nd log=====>",_GL_GLOBALS['csv_data_ini'], [str(ddc), "{}:{}".format(objType, oid)])
    # objname = getDeepObject(_GL_GLOBALS['csv_data_ini'], [str(ddc), "{}:{}".format(objType, oid)])
    objname = getDeepObject(_GL_GLOBALS['csv_data_ini'], [str(ddc), str(oid)])
    myprint("modified object name - {} {}".format(objname, (objname != None)))
    # objname = _GL_GLOBALS['csv_data_ini'][str(ddc)]["{}:{}".format(objType, oid)]
    if objname != None:
        glName = objname[3]
    else:
        glName = objname
    #     print('Unable to get Object Name')
    # print("im gere glname",glName)
    return glName
    # csv_data = _GL_GLOBALS.get('csv_data_ini', {})
    # # Construct the key
    # key = "{}:{}".format(objType, oid)
    # # Return the object name or a default value if not found
    # return csv_data.get(ddc, {}).get(key, 'Unknown Object Name')"

def getDisplayName(ddc, oid):
    """Return display_name (index 2) from the name-handler lookup, or '' if not found."""
    entry = getDeepObject(_GL_GLOBALS.get('csv_data_ini', {}), [str(ddc), str(oid)])
    return entry[2] if entry is not None and len(entry) > 2 else ''

def prepareObjectNamesAsPreviousValuesByLookup(ddcId, objIdList, tblNameLength=12):
    mylist = {}
    myprint('My Inputs {} {}'.format(ddcId, objIdList))
    for myobj in objIdList:
        myprint('My Inputs {} {} {}'.format(ddcId, myobj, (str(myobj) != 'presentValue')))
        if str(myobj) != 'presentValue':
            objName = getObjectName2(ddcId, myobj)
            myprint('My ObjectName {} {} {}'.format(ddcId, myobj, objName))
            eqpDetails = processEquipmentCode(objName, tblNameLength=tblNameLength)
            displayName = getDisplayName(ddcId, myobj)
            mylist[str(myobj)] = [objName, '2025-04-01 00:00:00.0', None, eqpDetails['p_name'], displayName, eqpDetails['e_id'], eqpDetails['eqp_tableName'], '', False]
            myprint('My Output {} {} {} {}'.format(ddcId, myobj, objName, eqpDetails))
    myprint('My Outputs {} {} {} {}'.format(ddcId, objIdList, mylist, eqpDetails))
    return mylist


# def prepareObjectNamesAsPreviousValuesByLookup(ddcId, objIdList): # Changed to parameterize tblNameLength
def prepareObjectNamesAsPreviousValuesByLookup0(ddcId, objIdList, tblNameLength=12):
    mylist = {}
    # printTrace('My Inputs {} {}'.format(ddcId, objIdList))
    for myobj in objIdList:
        # printTrace('My Inputs {} {}'.format(ddcId, myobj))
        if myobj != 'presentValue':
            objName = getObjectName(ddcId, str(myobj))
            eqpDetails = processEquipmentCode(objName, tblNameLength=tblNameLength)
            mylist[str(myobj)]=[objName,'',0.0, eqpDetails['p_name'], eqpDetails['e_id']]
            myprint('My Output {} {} {} {}'.format(ddcId, myobj, objName, eqpDetails))
    # printTrace('My Outputs {} {} {}'.format(ddcId, objIdList, mylist))
    return mylist

def getDeepObject(rootObj=None, myindexes=[]):
    getChild = lambda parent, child: parent[child] if child in parent  else None
    myObject = rootObj
    for myChild in myindexes:
        if myObject != None:
            myObject = getChild(myObject, myChild)
        else: break
    return myObject

def getObjectName(ddc, oid, givenName='', ahuId=1, startPort=2400, defaultDDC=1):
    # print('getObjName: DDC - {} Obj - {} AHU - {}'.format(ddc, oid, ahuId))
    # print("x-{}".format(ddc))
    namePattern = "GL {0:02x} 00 {1:02x} B5 C {2:02x}{3:01x}"
    glName = ''
    x = str(ddc).split(":")
    # print(x, len(x))
    if len(x) == 1:
        ddcId = defaultDDC
        device_id = (int(x[0], 16) & 0xffff)-startPort
    elif len(x) == 2:
        ddcId = x[0]
        if ddcId.isnumeric() and int(ddcId)<256:
            device_id = x[1]
        else:
            ddcId = defaultDDC
            device_id = int(x[1])-startPort

    # print('getObjName: DDC-ID - {} Obj - {} Device-ID - {}'.format(ddcId, oid, device_id))
    if (oid == 177) or (oid=='2:177') or (str(oid)=='analogValue:177'):
        param_id = 6
    elif (oid == 178) or (oid=='2:178') or (str(oid)=='analogValue:178'):
        param_id = 1
    elif (oid == 179) or (oid=='2:179') or (str(oid)=='analogValue:179'):
        param_id = 5
    elif (oid == 180) or (oid=='2:180') or (str(oid)=='analogValue:180'):
        param_id = 0
    else:
        param_id = 15

    glName = namePattern.format(int(ddcId), int(device_id), ahuId, param_id)
    # print(glName)

    return glName

def prepareEquipmentssIds(connectionPool):
    deviceIds = {}
    cursor = cnx = None
    try:
      cnx = connectionPool.get_connection()
      cursor = cnx.cursor()

      # printTrace('Table Now-{}'.format(mynewtable))
      # Uses List Comprehension
      # "INSERT INTO {} ({}) VALUES ({})".format('mytable', ','.join(myparams), v)
      stmt = "SELECT CONCAT('0x', ss_address_value) AS glSSId, ss_type, ddcid, id, name FROM gl_subsystem eqp, (SELECT id AS ddcid FROM gl_subsystem WHERE ss_type='GL_SS_ADDRESS_BACNET_DDC' AND ss_status='GL_SS_STATUS_ACTIVE') ddc WHERE eqp.ss_parent=ddcid ORDER BY ss_type, CONVERT(name,decimal)"
      myprint(stmt)

      cursor.execute(stmt)
      myresults = cursor.fetchall()
      for x in myresults: deviceIds[int(x[0], 16)]=x[3]
      [myprint('My Eqp: {}:{}'.format(x,str(deviceIds[x]))) for x in deviceIds]

    except Exception as e:
        frameinfo = getframeinfo(currentframe())
        printTrace("Exception{}-'{}' in file-{} function-{} line-{}".format(type(e), e, frameinfo.filename, frameinfo.function, frameinfo.lineno))

    finally:
      if cursor != None: cursor.close()
      if cnx != None: cnx.close()
    return deviceIds

def prepareDeploymentConfiguration(glConfigFile, myConnectionPool=None):
    global gl_configuration
    getMyid = lambda p: int(p, 16)
    with open(glConfigFile) as f:
        myconfig = json.load(f)
    # gl_configuration['deviceParams'] = {}
    if 'deviceParams' in myconfig:
        myparams = myconfig['deviceParams']
        gl_configuration['deviceParams'] = {getMyid(myid): myparamid for myid, myparamid in myparams.items()}
    if "deviceType" in myconfig:
        myparams = myconfig["deviceType"]
        gl_configuration["deviceTypes"] = {getMyid(myid): myparamid for myid, myparamid in myparams.items()}
    if myConnectionPool != None:
        myDeviceIds = prepareEquipmentssIds(myConnectionPool)
        if myDeviceIds != None:
            gl_configuration['deviceIds'] = myDeviceIds
        else:
            printTrace('Unable to get Device IDs...')

def prepareConfigurationFromCodeBook(glConfigFile='data/CBParameters.csv', deplDtlsJSONFile='data/GLSDeploymentDetails.json', myConnectionPool=None):
    global gl_configuration
    getMyid = lambda p: int(p, 16)

    eqpDetails = {}
    with open(deplDtlsJSONFile) as f:
        eqpDetails = json.load(f)
    myconfig = getDeepObject(eqpDetails, ['Equipment_Specs','EQUIPMENT_TYPE_DETAILED'])
    if myconfig != None:
        gl_configuration["deviceTypes"] = {getMyid(myid): myparamid for myid, myparamid in myconfig.items()}
        myprint('prepareConfigurationFromCodeBook-gl_configuration["deviceTypes"]-{}'.format(gl_configuration['deviceTypes']))
    else:
        printTrace('prepareConfigurationFromCodeBook-ERROR: Unable to load Device Types from-{}'.format(deplDtlsJSONFile))

    myconfig = loadCodeBook(glConfigFile)[2]
    # gl_configuration['deviceParams'] = {}
    myparams = myconfig['EQUIPMENT_PARAMETERS']
    if myparams != None:
        myprint('prepareConfigurationFromCodeBook-TODO-gl_configuration["deviceParams"]{}'.format(myparams))
        gl_configuration['deviceParams'] = {myid: myparamid for myid, myparamid in myparams.items()}
    else:
        printTrace('prepareConfigurationFromCodeBook-ERROR: Unable to load Parameters from-{}'.format(glConfigFile))

    if myConnectionPool != None:
        myDeviceIds = prepareEquipmentssIds(myConnectionPool)
        if myDeviceIds != None:
            gl_configuration['deviceIds'] = myDeviceIds
        else:
            printTrace('prepareConfigurationFromCodeBook-ERROR: Unable to get Device IDs...')
    else:
        printTrace('prepareConfigurationFromCodeBook - Unable to get connection pool')

def loadParamsJSON(paramsJSONFile = 'myParameters.json'):
    global eqpParamObjects
    with open(paramsJSONFile) as f:
        eqpParamObjects = json.load(f)

# EqpTypeCode,EqpTypeName,ParameterCode,ParameterName,ParameterDescription,ParameterUnit,RangeHigh,RangeLow,ResetValue,ParameterWritable,BACnetObjectType
# 0xA0,AHU,0,RAT,RAT,degreeCentigrade,30,20,26,,true,analogValue
def loadCodeBook(fileName='./CBParameters.csv', separator=',', useObjectNameHandler=False, useEqpTypeCodeAsKey=False):
    myParameter = {}
    eqpParamObjects = {}
    eqpTypeNameToCode = {}
    parameterList = {"EQUIPMENT_PARAMETERS":{}}
    f = None
    try:
      with open(fileName, "r") as f:
          if f != None:
              myprint('file--{}'.format(f))
          else:
              printTrace('file--{} not found'.format(fileName))
          reader = csv.DictReader(f, delimiter=separator)
          for line in reader:
              if len(line) == 0: continue
              myParameter = {}
              myParameter['name'] = line['ParameterName']
              myParameter['units'] = line['ParameterUnit']
              myParameter['type'] = line['BACnetObjectType']
              myParameter['writable'] = line['ParameterWritable']
              myParameter['paramCode'] = getHexString(int(line['ParameterCode']), places=4)#line['ParameterCode']#
            #   myParameter['paramCode'] = getHexString(int(line['ParameterCode']), places=3)#CHANGED TO 4 to include N9#
              if (myParameter['type'] == 'multiStateValue'):
                myParameter['numberOfStates'] = 3
              elif (any(myParameter['type'] in s for s in ['analogInput','analogOutput','analogValue'])):#(myParameter['type'] == 'analogValue')
                myParameter['rangeLow'] = line['RangeLow']
                myParameter['rangeHigh'] = line['RangeHigh']
              elif (any(myParameter['type'] in s for s in ['binaryInput','binaryOutput','binaryValue'])):#(myParameter['type'] == 'binaryValue')
                myParameter['resetValue'] = line['ResetValue']

              myEqpType = getHexString(int(line['EqpTypeCode'],16), places=2)
              if useEqpTypeCodeAsKey == True:
                if myEqpType not in eqpParamObjects:
                    myprint('Loading Equipment Type: {}'.format(myEqpType))
                    eqpTypeNameToCode[line['EqpTypeName']] = myEqpType
                    eqpParamObjects[myEqpType] = {'Equipment_Type': myEqpType, 'Equipment_Parameters': {}}
                eqpParamObjects[myEqpType]['Equipment_Parameters'][myParameter['name']] = myParameter
              else:
                if line['EqpTypeName'] not in eqpParamObjects:
                    myprint('Loading Equipment Type: {}'.format(myEqpType))
                    eqpTypeNameToCode[line['EqpTypeName']] = myEqpType
                    eqpParamObjects[line['EqpTypeName']] = {'EqpTypeCode': myEqpType, 'Equipment_Type': line['EqpTypeName'], 'Equipment_Parameters': {}}
                eqpParamObjects[line['EqpTypeName']]['Equipment_Parameters'][myParameter['name']] = myParameter

              # printTrace('{}-{}'.format(line['EqpTypeCode'], myParameter['paramCode']))
              parameterList['EQUIPMENT_PARAMETERS'][int(line['EqpTypeCode']+myParameter['paramCode'], 16)] = myParameter['name']
              # printTrace(line)
    except:
        frameinfo = getframeinfo(currentframe())
        printTrace("Exception in file-{} function-{} line-{}".format(frameinfo.filename, frameinfo.function, frameinfo.lineno))
    # printTrace('Sample parameterList: Length - {} Item:1 - {} ==> {}'.format(len(eqpParamObjects.items()), list(eqpParamObjects.keys()), eqpParamObjects['PUMP']))#'0xA0'
    # for k, v in parameterList['EQUIPMENT_PARAMETERS'].items(): printTrace('{}-{}'.format(hex(int(k)), v))
    # printTrace('Equipment Types - {} Parameters - {}'.format(eqpParamObjects, parameterList))#eqpParamObjects['0xB1']
    # printTrace('Sample parameterList:{} - Count-{}'.format(parameterList[0], len(parameterList)))
    return [eqpParamObjects, eqpTypeNameToCode, parameterList]

def getMyParamName(objName):
    global gl_configuration
    param_name = None
    if objName.startswith('GL '):
        eqpCode = int(objName[2:].replace(' ',''),16)
        if (0xC000 & eqpCode) == 0xC000:#if (eqpCode & 0xf000):
            param_name = getDeepObject(gl_configuration['deviceParams'],[eqpCode & 0xffe00f])
        else:
            param_name = getDeepObject(gl_configuration['deviceParams'],[eqpCode & 0xffffff])
    if param_name == None:
        printTrace('getMyParamName - ERROR: unable to get param_name forcccccccc {}'.format(objName))
    return param_name

'''
Lookup for the Object Name from objId as per GL Code Book, if not available in the Device
Process Object Name to extract Equipment ss_id (if available), table name, parameter name
Handle alternatives/ exceptions
def processObjectIdName(myObjId='2:170', myObjName='GL 00 00 13 B5 C 003', objNameCompliant=False):
'''
def processObjectIdName(myObjId=None, myObjName=None, objNameCompliant=False):
    objDtl = None
    if objNameCompliant==False:
        if myObjId == None:
            myprint("Exception{}-'{}' Unable to Process - no object Id")
        else:
            myObjName = getObjectName()# lookupObjectName(deviceAddress, myObjId)
    objDtl = {}# processEquipmentCode(myObjName)
    return objDtl

def processEquipmentCode(eqpCodeStr, useFullCodeBook=True, tblNameLength=12):
    # eqpCodeStr = String(eqpCodeStr)
    eqpCodeObject = { 'inputValid': True, 'errorCode': [] }
    eqpParamCode=0
    tblCode = devCode = devIdCode = 0
    tblName = devType = paramName = myCodeStr = ssid = ''
    paramCode = 0
    bValid = True
    i=0
 
    if eqpCodeStr.startswith('GL'):
        eqpParamCode = int(eqpCodeStr[2:].replace(' ',''),16)
 
        devCode = (0xFF0000 & eqpParamCode) >> 16
        devType = getDeepObject(gl_configuration['deviceTypes'],[devCode])
        if (devType != None):
            eqpCodeObject['e_ss_type'] = devType[0]
        else:
            eqpCodeObject['inputValid'] = False
            eqpCodeObject['errorCode'].append('Invalid Equipment Type: ' + getHexString(devCode, 2))
            # mylog('Invalid Equipment Type: ' + devCode.toString(16))
 
    #   // parameter Code and table Code
        paramCode = 0xFFFFFF & eqpParamCode
        if (tblNameLength == 12):
            tblCode = 0xFFFFFFFF0000 & eqpParamCode #(0xFFFFFF0000 & eqpParamCode) >> 16;
        elif (tblNameLength == 10):
            tblCode = 0xFFFFFF0000 & eqpParamCode #(0xFFFFFF0000 & eqpParamCode) >> 16;
        else:
            eqpCodeObject['inputValid'] = False
            eqpCodeObject['errorCode'].append('Invalid Table Name Length: ' + tblNameLength)
        devIdCode = tblCode
    #   // Handle Parameters of Child Objects
        # paramCode = (0xFFC00F & paramCode) if ((0xC000 & paramCode) == 0xC000) else paramCode
        if (0xC000 & paramCode) == 0xC000:
            paramCode &= 0xFFE00F # 0xFFC00F # Handle Child Alarms
            # tblCode = 0xFFFF00FF0000 & eqpParamCode if useFullCodeBook == True else 0xFFFFF0 & eqpParamCode#(0xFFFF00FFF0 & eqpParamCode) >> 4
            # 0xFFFF00FF0000 replaced by 0FFFF00FFCFF0 to be in line with db table names and child alarms also
            tblCode = 0xFFFF00FFCFF0 & eqpParamCode if useFullCodeBook == True else 0xFFFFF0 & eqpParamCode#(0xFFFF00FFF0 & eqpParamCode) >> 4
            devIdCode = 0xFFFFFFFFFFF0 & eqpParamCode if useFullCodeBook == True else 0xFFFFFFF0 & eqpParamCode
            myprint('DevIdCode: {0:10x}'.format(devIdCode))
 
        eqpCodeObject['e_address_value'] = '{0:10x}'.format(devIdCode).replace(' ','0')
        eqpCodeObject['e_name'] = (devIdCode & 0xff000000) >> 24
 
        if 'deviceIds' not in gl_configuration:
            ssid = eqpCodeStr[:-6]
        else:
            ssid = getDeepObject(gl_configuration['deviceIds'],[devIdCode])
        if ssid != None:            
            myprint('DevIdCode-ssid: {}'.format(ssid))
            eqpCodeObject['e_id'] = ssid
            eqpCodeObject['p_parent_eqp'] = ssid
        else:
            printTrace('Unable to get ssid: {} devIdCode = {}'.format(eqpCodeObject, gl_configuration['deviceIds']))
        # } else if (createEquipment === true) {
        #   ssid = uuid();tblName
        #   deviceIds[devIdCode] = ssid;
        #   eqpCodeObject['e_id'] = ssid;
        #   eqpCodeObject['p_parent_eqp'] = ssid;
        #   eqpCodeObject['createEquipment'] = true;
        #   // Create Equipment
        # else:
        #   eqpCodeObject['inputValid'] = False
        #   eqpCodeObject['errorCode'].push('Undefined Equipment ID: ' + devIdCode.toString(16));
    #       mylog('Undefined Equipment ID: ' + devIdCode.toString(16))
    #   }
 
        if (eqpParamCode & 0xc000) == 0xc000:
            # paramName = getDeepObject(gl_configuration['deviceParams'],[eqpParamCode & 0xffc00f])
            paramName = getDeepObject(gl_configuration['deviceParams'],[eqpParamCode & 0xffe00f])# Handle Child Alarm also
        else:
            paramName = getDeepObject(gl_configuration['deviceParams'],[eqpParamCode & 0xffffff])
        if (paramName != None):
            eqpCodeObject['p_name'] = paramName
            eqpCodeObject['p_description'] = myCodeStr
        else:
            eqpCodeObject['inputValid'] = False
            eqpCodeObject['errorCode'].append('Invalid Parameter: ' + getHexString(paramCode, 4))
            # mylog('Invalid Parameter: ' + paramCode.toString(16))
 
        # tblName = `${devType[1]}${tblCode.toString(16).toLowerCase().padStart(10, 0)}${devType[2]}`.toLowerCase();
        if (tblNameLength == 12):
            tblName = '{0:12x}'.format(tblCode).replace(' ','0')
        else:
            tblName = '{0:10x}'.format(tblCode).replace(' ','0')
        
        if devType is not None:
            eqpCodeObject['eqp_tableName'] = '{}{}{}'.format(devType[1], tblName, devType[2])
        else:
            eqpCodeObject['eqp_tableName'] = ''
 
    #   // mylog(`eqpParamCode, tblCode, tblName, paramCode, paramName, devCode, devType, bValid, ssid, devIdCode, myCodeStr, eqpCodeObject`);
    #   // console.log(eqpParamCode, tblCode, tblName, paramCode, paramName, devCode, devType, bValid, ssid, devIdCode, myCodeStr, eqpCodeObject);
    #   // mylog('eqpParamCode, tblCode, paramCode, devCode, devIdCode, myCodeStr');
    #   // printHex([eqpParamCode, tblCode, paramCode, devCode, devIdCode, myCodeStr]);
    # } else {
    #   eqpCodeObject['inputValid'] = false;
    #   eqpCodeObject['errorCode'].push('Invalid Equipment Code');
    #   mylog('Invalid Equipment Code: ' + eqpCode);
    # }
    if eqpCodeObject['inputValid'] == False:
        printTrace('processEquipmentCode - ERROR: {}'.format(eqpCodeObject))
        pass
    return eqpCodeObject
 
def processEquipmentCode10(eqpCodeStr, useFullCodeBook=False):
	# eqpCodeStr = String(eqpCodeStr)
	eqpCodeObject = { 'inputValid': True, 'errorCode': [] }
	eqpParamCode=0
	tblCode = devCode = devIdCode = 0
	tblName = devType = paramName = myCodeStr = ssid = ''
	paramCode = 0
	bValid = True
	i=0

	if eqpCodeStr.startswith('GL'):
		eqpParamCode = int(eqpCodeStr[2:].replace(' ',''),16)

		devCode = (0xFF0000 & eqpParamCode) >> 16
		devType = getDeepObject(gl_configuration['deviceTypes'],[devCode])
		if (devType != None):
			eqpCodeObject['e_ss_type'] = devType[0]
		else:
			eqpCodeObject['inputValid'] = False
			eqpCodeObject['errorCode'].append('Invalid Equipment Type: ' + getHexString(devCode, 2))
			# mylog('Invalid Equipment Type: ' + devCode.toString(16))

	# 	// parameter Code and table Code
		paramCode = 0xFFFFFF & eqpParamCode
		tblCode = 0xFFFFFF0000 & eqpParamCode #(0xFFFFFF0000 & eqpParamCode) >> 16;
		devIdCode = tblCode
	# 	// Handle Parameters of Child Objects
		paramCode = (0xFFC00F & paramCode) if ((0xC000 & paramCode) == 0xC000) else paramCode
		if (0xC000 & paramCode) == 0xC000:
			paramCode &= 0xFFC00F
			tblCode = 0xFFFFFF0000 & eqpParamCode if useFullCodeBook == True else 0xFFFFF0 & eqpParamCode#(0xFFFF00FFF0 & eqpParamCode) >> 4
			devIdCode = 0xFFFFFFFFF0 & eqpParamCode if useFullCodeBook == True else 0xFFFFFFF0 & eqpParamCode
			myprint('DevIdCode: {0:10x}'.format(devIdCode))

		eqpCodeObject['e_address_value'] = '{0:10x}'.format(devIdCode).replace(' ','0')
		eqpCodeObject['e_name'] = (devIdCode & 0xff000000) >> 24

		if 'deviceIds' not in gl_configuration:
			ssid = eqpCodeStr[:-6]
		else:
			ssid = getDeepObject(gl_configuration['deviceIds'],[devIdCode])
		if ssid != None:			
			myprint('DevIdCode-ssid: {}'.format(ssid))
			eqpCodeObject['e_id'] = ssid
			eqpCodeObject['p_parent_eqp'] = ssid
		else:
			printTrace('Unable to get ssid: {} devIdCode = {}'.format(eqpCodeObject, gl_configuration['deviceIds']))
		# } else if (createEquipment === true) {
		# 	ssid = uuid();
		# 	deviceIds[devIdCode] = ssid;
		# 	eqpCodeObject['e_id'] = ssid;
		# 	eqpCodeObject['p_parent_eqp'] = ssid;
		# 	eqpCodeObject['createEquipment'] = true;
		# 	// Create Equipment
		# else:
		# 	eqpCodeObject['inputValid'] = False
		# 	eqpCodeObject['errorCode'].push('Undefined Equipment ID: ' + devIdCode.toString(16));
	# 		mylog('Undefined Equipment ID: ' + devIdCode.toString(16))
	# 	}

		if (eqpParamCode & 0xf000):
			paramName = getDeepObject(gl_configuration['deviceParams'],[eqpParamCode & 0xffc00f])
		else:
			paramName = getDeepObject(gl_configuration['deviceParams'],[eqpParamCode & 0xffffff])
		if (paramName != None):
			eqpCodeObject['p_name'] = paramName
			eqpCodeObject['p_description'] = myCodeStr
		else:
			eqpCodeObject['inputValid'] = False
			eqpCodeObject['errorCode'].append('Invalid Parameter: ' + getHexString(paramCode, 4))
			# mylog('Invalid Parameter: ' + paramCode.toString(16))

		# tblName = `${devType[1]}${tblCode.toString(16).toLowerCase().padStart(10, 0)}${devType[2]}`.toLowerCase();
		tblName = '{0:10x}'.format(tblCode).replace(' ','0')
		eqpCodeObject['eqp_tableName'] = '{}{}{}'.format(devType[1], tblName, devType[2])

	# 	// mylog(`eqpParamCode, tblCode, tblName, paramCode, paramName, devCode, devType, bValid, ssid, devIdCode, myCodeStr, eqpCodeObject`);
	# 	// console.log(eqpParamCode, tblCode, tblName, paramCode, paramName, devCode, devType, bValid, ssid, devIdCode, myCodeStr, eqpCodeObject);
	# 	// mylog('eqpParamCode, tblCode, paramCode, devCode, devIdCode, myCodeStr');
	# 	// printHex([eqpParamCode, tblCode, paramCode, devCode, devIdCode, myCodeStr]);
	# } else {
	# 	eqpCodeObject['inputValid'] = false;
	# 	eqpCodeObject['errorCode'].push('Invalid Equipment Code');
	# 	mylog('Invalid Equipment Code: ' + eqpCode);
	# }
	return eqpCodeObject

# def createDBConnectionPool(mydatabase='acrex_02', dbuser='root', dbpassword = 'qwertyuiop', dbPoolName='glpool', dbAutoCommit=True, dbPoolSize=32,host='127.0.0.1'):
# def createDBConnectionPool(mydatabase='das_wip', dbuser='root', dbpassword = 'SenZ0pt@123', dbPoolName='glpool', dbAutoCommit=True, dbPoolSize=32):
def createDBConnectionPool(mydatabase='acrex_02', dbuser='graylinx', dbpassword = 'GrayLinx@24', dbPoolName='glpool', dbAutoCommit=True, dbPoolSize=32,host='127.0.0.1'):
    global NO_DB_CONNECTOR
    printTrace('createDBConnectionPool - mydatabase: {}, dbuser: {}, dbpassword: {}, dbPoolName: {}, dbAutoCommit: {}, dbPoolSize: {}, host: {}'.format(mydatabase, dbuser, 'dbpassword', dbPoolName, dbAutoCommit, dbPoolSize,host))

    dbconfig = {
    "host": host, # "host": '192.168.1.193',
    "database": mydatabase,
    "user":     dbuser,
    "password": dbpassword,
    "autocommit": dbAutoCommit
    }
    if NO_DB_CONNECTOR == True:
      return None
    else:
      return mysql.connector.pooling.MySQLConnectionPool(pool_name = dbPoolName, pool_size = dbPoolSize, **dbconfig)

def getEquipmentDataTableNameType1(deviceAddress, name_prefix='equipment_'):
    try:
      mytablename = name_prefix+deviceAddress.split(':')[1]
    except Exception as e:
      mytablename = ''
    return mytablename

def prepareUpdateStatementsOptimized(mytable='gl_subsystem_latest_event', 
                                     myparams=['ss_id', 'measured_time', 'param_id', 'param_value'], 
                                     myvalues=[('d5dc4c34-496d-4eb8-96fe-9b88f9f9b9ae', '2023-03-10 18:37:27', 'EA_Dmpr_Pos_SP', 22.989999771118164)], 
                                     mycursor=None, optimized=True):
    
    stmts = ''
    mytemplate = "UPDATE {} SET measured_time = '{}', param_value = (CASE WHEN (param_id = 'VAV_Dmpr_Pos' AND ss_id = '{}') THEN 37.0 WHEN (param_id = 'VAV_ZAT' AND ss_id = '{}') THEN 24.5 END) WHERE ss_id IN ({}) AND param_id IN ({});"

        
    for val in updated_data:
        try:
            if mycursor is not None:
                update_stmt = mytemplate.format(mytable, val[1], val[0], val[0], "'{}','{}'".format(val[2], val[2]))
                mycursor.execute(update_stmt)
                stmts += update_stmt + '\n'
            print(f"Data going to table: {val}")
        except Exception as e:
            print(f"Error occurred: {e}")
        finally:
            print("Attempted to update data in the table.")
    
    if stmts == '':
        stmts = None

    print(f'prepareUpdateStatements - UPDATE Statements: {stmts}')
    return stmts


def prepareUpdateStatementsNoProc(mytable='gl_subsystem_latest_event', myparams=['ss_id', 'measured_time', 'param_id', 'param_value'], myvalues=[('d5dc4c34-496d-4eb8-96fe-9b88f9f9b9ae', '2023-03-10 18:37:27', 'EA_Dmpr_Pos_SP', 22.989999771118164)], mycursor=None):

# UPDATE gl_subsystem_latest_event SET param_value = (case when (param_id = 'VAV_Dmpr_Pos' and ss_id='78146d11-c2a9-42db-be71-9c15515cb64d') then 37.0 when (param_id = 'VAV_ZAT' and ss_id='78146d11-c2a9-42db-be71-9c15515cb64d') then 24.5 end) where ss_id in ('78146d11-c2a9-42db-be71-9c15515cb64d') AND param_id in ('VAV_Dmpr_Pos','VAV_ZAT');

    stmts = ''
    mytemplate = "UPDATE {} SET measured_time='{}', param_value='{}' WHERE ss_id='{}' AND param_id='{}';"
    for val in myvalues:
      if mycursor != None: mycursor.execute(mytemplate.format(mytable, val[1], val[3], val[0], val[2]))
      stmts = stmts + mytemplate.format(mytable, val[1], val[3], val[0], val[2])
    if stmts=='': stmts=None
    myprint('prepareUpdateStatements - UPDATE Statements: {}'.format(stmts))
    return stmts

def prepareUpdateStatements(mytable='gl_subsystem_latest_event', myparams=['ss_id', 'measured_time', 'param_id', 'param_value'], myvalues=[('d5dc4c34-496d-4eb8-96fe-9b88f9f9b9ae', '2023-03-10 18:37:27', 'EA_Dmpr_Pos_SP', 22.989999771118164)], mycursor=None):

# UPDATE gl_subsystem_latest_event SET param_value = (case when (param_id = 'VAV_Dmpr_Pos' and ss_id='78146d11-c2a9-42db-be71-9c15515cb64d') then 37.0 when (param_id = 'VAV_ZAT' and ss_id='78146d11-c2a9-42db-be71-9c15515cb64d') then 24.5 end) where ss_id in ('78146d11-c2a9-42db-be71-9c15515cb64d') AND param_id in ('VAV_Dmpr_Pos','VAV_ZAT');

    updated_data = []
    for myparam in myvalues:
        myparam = list(myparam)
        if myparam[2] == 'CHW_In_Temp':
            myparam[3] = str(round(myparam[3] / 10, 2))
        if myparam[2] == 'CHW_Out_Temp':
            myparam[3] = round(myparam[3] / 10, 2)
        if myparam[2] == 'Cooling_Range':
            myparam[3] = round(myparam[3] / 10, 2)
        if myparam[2] == 'Set_EWT':
            myparam[3] = round(myparam[3] / 10, 2)
        else:
            pass
        updated_data.append(tuple(myparam))

    if mycursor is None:
        # Return placeholder string for logging purposes only (no execution)
        stmts = ""
        for val in updated_data:
            stmts += "CHECK-UPSERT {}: ss_id={} param_id={}\n".format(mytable, val[0], val[2])
        return stmts if stmts else None

    # Check-then-update-or-insert: SELECT first to determine if the point exists,
    # then UPDATE if found, INSERT only if not found.
    # This avoids duplicates caused by MySQL rowcount=0 when value is unchanged.
    exists_stmt = (
        "SELECT COUNT(*) FROM {} WHERE ss_id=%s AND param_id=%s"
    ).format(mytable)
    update_stmt = (
        "UPDATE {} SET measured_time=%s, param_value=%s "
        "WHERE ss_id=%s AND param_id=%s"
    ).format(mytable)
    insert_stmt = (
        "INSERT INTO {} (ss_id, measured_time, param_id, param_value) "
        "VALUES (%s, %s, %s, %s)"
    ).format(mytable)

    for val in updated_data:
        # val: (ss_id, measured_time, param_id, param_value [, eqp_tableName])
        ss_id, measured_time, param_id, param_value = val[0], val[1], val[2], val[3]
        try:
            mycursor.execute(exists_stmt, (ss_id, param_id))
            point_exists = mycursor.fetchone()[0] > 0
            if point_exists:
                mycursor.execute(update_stmt, (measured_time, param_value, ss_id, param_id))
            else:
                mycursor.execute(insert_stmt, (ss_id, measured_time, param_id, param_value))
        except mysql.connector.errors.InternalError as e:
            if e.errno == 1213:  # Deadlock — re-raise so outer retry loop handles it
                raise
            frameinfo = getframeinfo(currentframe())
            printTrace("prepareUpdateStatements Exception{}-'{}' file-{} line-{} ss_id={} param_id={}".format(
                type(e), e, frameinfo.filename, frameinfo.lineno, ss_id, param_id))
        except Exception as e:
            frameinfo = getframeinfo(currentframe())
            printTrace("prepareUpdateStatements Exception{}-'{}' file-{} line-{} ss_id={} param_id={}".format(
                type(e), e, frameinfo.filename, frameinfo.lineno, ss_id, param_id))
    return None

def insertIntoIBMSTables(mycursor, myps, myvs=[]):
    stmt = "INSERT IGNORE INTO {} ({}) VALUES ('{}')"
    mytable = ''
    
    for myvals in myvs:
        myvals = [str(myvals[j]) for j in range(len(myvals))]
        if (myvals[4].strip() != ''):
            mytable = myvals[4].strip()
            mystmt = stmt.format(myvals[4], ','.join(myps), "','".join(myvals[0:4]))
            mycursor.execute(mystmt)
        else:
            printTrace('insertIntoIBMSTables-ERROR - NOT GETTING TABLE NAME - Args-{}'.format(myvals))

def insertIntoIBMSTablesOptimizedNocallproc(mycursor, myps, myvs=[], optimize = True):
    stmt = "INSERT IGNORE INTO {} " + "({}) VALUES ({})".format(','.join(myps), ','.join(['%s' for x in myps]))
    mytable = ''
    myinsertvalues = []
    
    for myvals in myvs:
        myvals = [str(myvals[j]) for j in range(len(myvals))]
        if (myvals[4].strip() != ''):
            if (mytable == ''):
                mytable = myvals[4].strip()
                # prepare for new table
            elif mytable != myvals[4].strip():
                # prepare for next table
                mycursor.executemany(stmt.format(mytable), myinsertvalues)
                myinsertvalues = []
                mytable = myvals[4].strip()
            myinsertvalues.append(myvals[0:4])
        else:
            printTrace('insertIntoIBMSTablesOptimized-ERROR - NOT GETTING TABLE NAME - Params-{} - Values-{}'.format(myps,myvals))
    if len(myinsertvalues) > 0:
        mycursor.executemany(stmt.format(mytable), myinsertvalues)

def insertIntoIBMSTablesOptimized(mycursor, myps, myvs=[], optimize = True):
	mystatement = "INSERT IGNORE INTO {} " + "({}) VALUES ".format(','.join(myps)) + "{};"
	makemyvalues = lambda myvalarray=[]: ','.join("('" + "','".join(myvalarray[j]) + "')" for j in range(len(myvalarray)))
	makequery = lambda mytbl, myInsertValues=[]: mystatement.format(mytbl, makemyvalues(myInsertValues))
 
	mytable = ''
	myinsertvalues = []
	myquery = ''
	updated_data=[]
    

	for myparam in myvs:
		myparam=list(myparam)
		if myparam[2] == 'CHW_In_Temp':
			myparam[3] = str(round(myparam[3] / 10, 2))
		if myparam[2] == 'CHW_Out_Temp':
			myparam[3] = round(myparam[3] / 10, 2)
		if myparam[2] == 'Cooling_Range':
			myparam[3] = round(myparam[3] / 10, 2)
		if myparam[2] == 'Set_EWT':
			myparam[3] = round(myparam[3] / 10, 2)
		else:
			pass
		updated_data.append(tuple(myparam))    

	for myvals in updated_data:
		myvals = [str(myvals[j]) for j in range(len(myvals))]
		if (myvals[4].strip() != ''):
			if (mytable == ''):
				# prepare for new table
				mytable = myvals[4].strip()
			elif mytable != myvals[4].strip():
				# prepare for next table
				myquery += makequery(mytable, myinsertvalues) # mycursor.executemany(stmt.format(mytable), myinsertvalues)
				myinsertvalues = []
				mytable = myvals[4].strip()
			myinsertvalues.append(myvals[0:4])
		else:
			printTrace('insertIntoIBMSTablesOptimized-ERROR - NOT GETTING TABLE NAME - Args-{}'.format(myvals))
	if len(myinsertvalues) > 0:
		myquery += makequery(mytable, myinsertvalues) # mycursor.executemany(stmt.format(mytable), myinsertvalues)
	if myquery != '' and mycursor != None:
		myprint('insertIntoIBMSTablesOptimized----{}'.format(myquery))
		mycursor.callproc('executeMyQueries', [myquery])
	return myquery

def insertDataIntoDatabase(connectionPool, mytable='gl_subsystem_latest_event', myparams=['ss_id', 'measured_time', 'param_id', 'param_value'], myvalues=[('d5dc4c34-496d-4eb8-96fe-9b88f9f9b9ae', '2023-03-10 18:37:27', 'EA_Dmpr_Pos_SP', 22.989999771118164)], useMultipleTables=False, device_Address=None, createEquipmentTable=False, updateLatestEventTable=True, usePerEquipmentTable=False):
# def insertDataIntoDatabase(connectionPool, mytable='equipment_parameter', myparams=['ss_id', 'measured_time', 'param_id', 'param_value'], myvalues=[('d5dc4c34-496d-4eb8-96fe-9b88f9f9b9ae', '2023-03-10 18:37:27', 'EA_Dmpr_Pos_SP', 22.989999771118164)]):
    MAX_DEADLOCK_RETRIES = 5
    for attempt in range(MAX_DEADLOCK_RETRIES):
      cursor = cnx = None
      mynewtable = ''
      try:
        cnx = connectionPool.get_connection()
        cursor = cnx.cursor()
        if (useMultipleTables == True) and (device_Address != None): mynewtable = getEquipmentDataTableNameType1(device_Address)
        if mynewtable == '':
          mynewtable = mytable
        elif createEquipmentTable:
          # CREATE [TEMPORARY] TABLE [IF NOT EXISTS] tbl_name { LIKE old_tbl_name | (LIKE old_tbl_name) }
          cursor.execute('CREATE TABLE IF NOT EXISTS {} LIKE {}'.format(mynewtable, mytable))

        # printTrace('Table Now-{}'.format(mynewtable))
        # Uses List Comprehension
        # "INSERT INTO {} ({}) VALUES ({})".format('mytable', ','.join(myparams), v)
        if usePerEquipmentTable==True:
            myprint("==========================================")
            insertIntoIBMSTablesOptimized(cursor, myparams, myvalues)
            # callproc() leaves pending result sets on the cursor; drain them
            # so prepareUpdateStatements can reuse the same cursor cleanly.
            try:
                for _ in cursor.stored_results():
                    pass
            except Exception:
                pass
        else:
          # When writing to a historical/equipment table, INSERT IGNORE is correct
          # (each timestamped row is a new record).
          # When mynewtable IS gl_subsystem_latest_event, skip INSERT IGNORE and
          # let prepareUpdateStatements do the upsert — otherwise we get a new row
          # on every cycle instead of updating the existing one.
          if mynewtable != 'gl_subsystem_latest_event':
            stmt = "INSERT IGNORE INTO {} ({}) VALUES ({})".format(mynewtable, ','.join(myparams), ','.join(['%s' for x in myparams]))
            myprint(stmt)
            myprint(myvalues)
            myprint("==========================================")
            cursor.executemany(stmt, myvalues)
        if updateLatestEventTable==True:
          prepareUpdateStatements(myvalues=myvalues, mycursor=cursor)
        break  # Success, exit retry loop

      except mysql.connector.errors.InternalError as e:
          if e.errno == 1213 and attempt < MAX_DEADLOCK_RETRIES - 1:
              printTrace("Deadlock detected (attempt {}/{}), retrying after backoff...".format(attempt + 1, MAX_DEADLOCK_RETRIES))
              if cursor is not None: cursor.close()
              if cnx is not None: cnx.close()
              cursor = cnx = None
              _time.sleep(0.1 * (2 ** attempt) + random.uniform(0, 0.1))  # Exponential backoff with jitter
              continue
          else:
              frameinfo = getframeinfo(currentframe())
              printTrace("Exception{}-'{}' in file-{} function-{} line-{} myvalues-{}".format(type(e), e, frameinfo.filename, frameinfo.function, frameinfo.lineno, myvalues))

      except Exception as e:
          frameinfo = getframeinfo(currentframe())
          printTrace("Exception{}-'{}' in file-{} function-{} line-{} myvalues-{}".format(type(e), e, frameinfo.filename, frameinfo.function, frameinfo.lineno, myvalues))

      finally:
        if cursor != None: cursor.close()
        if cnx != None: cnx.close()

_post_error_logged = False
async def gl_async_post(postURL, postBody, glVerify=False, timeout=2.50):
    global _post_error_logged
    try:
      async with httpx.AsyncClient(verify=glVerify) as client:
        response = await client.post(postURL, json=postBody, timeout=timeout, headers=[('Connection', 'close')])
        myprint(response)
        _post_error_logged = False  # Reset on success so next failure is logged
        # client.aclose()
    except httpx.ConnectError:
        if not _post_error_logged:
            printTrace("POST endpoint unreachable: {} (suppressing further connect errors until resolved)".format(postURL))
            _post_error_logged = True
    except Exception as e:
        frameinfo = getframeinfo(currentframe())
        printTrace("Exception{}-'{}' in file-{} function-{} line-{}".format(type(e), e, frameinfo.filename, frameinfo.function, frameinfo.lineno))

def processValueTransformation(mybody, myddc = '192.168.76.220'):
	if myddc in mybody:
		for (mykey, myparam) in mybody[myddc].items():
			if myparam[0] == 'CHW_In_Temp':
				mybody[myddc][mykey][1] = round(float(myparam[1]) / 10, 2) # myparam[3] = str(round(myparam[3] / 10, 3))
			elif myparam[0] == 'CHW_Out_Temp':
				mybody[myddc][mykey][1] = round(float(myparam[1]) / 10, 2)
			elif myparam[0] == 'Cooling_Range':
				mybody[myddc][mykey][1] = round(float(myparam[1]) / 10, 2)
			elif myparam[0] == 'Set_EWT':
				mybody[myddc][mykey][1] = round(float(myparam[1]) / 10, 2)	   
			elif myparam[0]=='Pump_Drive_Volt_AC':
				mybody[myddc][mykey][1] = round(float(myparam[1])/10,2)
			else:
				pass
	return mybody

def postEquipmentData(myurl='https://localhost:8443/mypost', myBody={}, timeout=0.1):
    if myBody is not None and bool(myBody):
        myBody = processValueTransformation(myBody, myddc = '192.168.76.220')# Pass the correct DDC 
        myprint('url:{}; body:{}'.format(myurl, myBody))
        asyncio.run(gl_async_post(myurl, myBody, timeout=timeout))

# def f(x):
#     return x**2
# def g(x):
#     return x**4
# def h(x):
#     return x**8

# Object of deviceAddress[bacnetObjId[objectName, lastRecordedTime, presentValue]]
glEqpParamData = {}
#
#   Process CoV
#
def processEqpParamCoV(deviceAddress, bacnetObjId, propertyId, propertyValue, measuredTime=None, paramType='analog'):
    global glEqpParamData
    deltaGreater = lambda a, b, delta=0.1: abs(float(a)-float(b)) > float(a)*float(delta)
    timeExceeded = lambda t1, t2, ti, fmt='%Y-%m-%d %H:%M:%S.%f': (datetime.strptime(t2,fmt) - datetime.strptime(t1,fmt)).seconds>=ti*60
    foundCoV = False
    # Parameterize dataAcquisitionHeartbeatMinutes and CoVThresholdPercent
    thresholdInterval = GL_GLOBALS['dataAcquisitionHeartbeatMinutes'] # 15 # minutes
    thresholdPresentValue = GL_GLOBALS['CoVThresholdPercent'] * 0.01 # 0.1 # 10% variation    thresholdInterval = 15 # minutes
    # thresholdPresentValue = 0.1 # 10% variation
    if measuredTime is None: measuredTime=getstrTimeNow()
    objectName = propertyValue if propertyId == 'objectName'  else ''
    # presentValue = propertyValue if propertyId == 'presentValue'  else ''
    presentValue = propertyValue if propertyId == 'presentValue'  else 0
    if deviceAddress not in glEqpParamData: # Adding deviceAddress
        glEqpParamData[deviceAddress] = {bacnetObjId: [objectName, measuredTime, presentValue]}
    elif bacnetObjId not in glEqpParamData[deviceAddress]: # Adding bacnetObject
        glEqpParamData[deviceAddress][bacnetObjId] = [objectName, measuredTime, presentValue]
    elif objectName != '': # Received ObjectName
        if  glEqpParamData[deviceAddress][bacnetObjId][0] == '':
            glEqpParamData[deviceAddress][bacnetObjId][0] = objectName
            glEqpParamData[deviceAddress][bacnetObjId][3] = getMyObjectName(objectName)
        elif glEqpParamData[deviceAddress][bacnetObjId][0] != objectName:
            printTrace('Conflict in ObjectName: {} {} currentName-{} newName-{}'.format(deviceAddress, bacnetObjId, glEqpParamData[deviceAddress][bacnetObjId][0], objectName))
    elif presentValue != '': # Received presentValue
        if paramType=='analog':
            if deltaGreater(glEqpParamData[deviceAddress][bacnetObjId][2], presentValue, thresholdPresentValue) or timeExceeded(glEqpParamData[deviceAddress][bacnetObjId][1], measuredTime, thresholdInterval):
                foundCoV = True
                glEqpParamData[deviceAddress][bacnetObjId][1] = measuredTime
                glEqpParamData[deviceAddress][bacnetObjId][2] = presentValue
        elif paramType == 'binary' or paramType == 'multiState':
            if (glEqpParamData[deviceAddress][bacnetObjId][2] != presentValue) or timeExceeded(glEqpParamData[deviceAddress][bacnetObjId][1], measuredTime, thresholdInterval):
                foundCoV = True
                glEqpParamData[deviceAddress][bacnetObjId][1] = measuredTime
                glEqpParamData[deviceAddress][bacnetObjId][2] = presentValue
            pass
        else:
            printTrace('Unexpected Check CoV Request: {} {} propertyId-{} propertyValue-{} paramType-{}'.format(deviceAddress, bacnetObjId, propertyId, propertyValue, paramType))
    else:
        printTrace('Unexpected Check CoV Request: {} {} propertyId-{} propertyValue-{}'.format(deviceAddress, bacnetObjId, propertyId, propertyValue))
    # myprint('processEqpParamCoV-{}'.format(glEqpParamData))
    return foundCoV

def getMyObjectName(devAddress,objId):
    global glEqpParamData
    myprint('getMyObjectName-{}'.format(glEqpParamData))
    if (devAddress in glEqpParamData) and (objId in glEqpParamData[devAddress]):
        return glEqpParamData[devAddress][objId][0]
    else:
        return ''

def test_processEqpParamCoV():
    global glEqpParamData
    myprint(processEqpParamCoV('127.0.0.1:2100','2:1','objectName', 'GL 00 01 01 a0 0 001'))
    myprint(glEqpParamData)
    myprint(processEqpParamCoV('127.0.0.1:2100','2:1','presentValue', 10.2))
    myprint(glEqpParamData)
    myprint(processEqpParamCoV('127.0.0.1:2100','2:1','presentValue', 10.1))
    myprint(glEqpParamData)

def prepareEquipmentParameterDataFile(myfilename):
    global glEqpParamData
    with open(myfilename, "w", encoding='utf-8') as myfile:
        json.dump(glEqpParamData, myfile, ensure_ascii=False, indent=2)

def prepareDataLoaderFile(parameters = [2191,2193,13001,70], ipaddress = '127.0.0.1', maxlength = 20, objType=2):
	# mytemplate = '127.0.0.1:2351,2:196,presentValue,2:192,presentValue,2:197,presentValue,2:194,presentValue,2:193,presentValue,2:198,presentValue,2:195,presentValue'
	getParam = lambda objId,property,objType=2: ','.join([':'.join([str(objType),str(objId)]),property])
	getAllParams = lambda myparams: ','.join([getParam(x, 'presentValue') for x in myparams])
	myitem = parameters # myitem = [2101,2190,13000,70]
	myline = ''
	for i in range(myitem[0], myitem[1]):
		mybegin = myitem[2]
		myend = myitem[2]+myitem[3]-1
		while mybegin<myend:
			mylen = min(myend-mybegin+1, maxlength)
			mytext = getAllParams([j for j in range(mybegin, mybegin+mylen)])
			myline = '{}:{},{}'.format(ipaddress, i, mytext)
			print(myline)
			mybegin += mylen

def test_other_functions():
    # print(timeit.timeit('[func(42) for func in (f,g,h)]', globals=globals()))
    # test preparePointList
    myprint(preparePointList('sample.txt'))
    # test preparePointList with timeit
    print(timeit.timeit("[func('sample.txt') for func in [preparePointList]]", number=1000, globals=globals()))
    # test postEquipmentData
    postEquipmentData(myurl="https://localhost:8443/v1/newapis/mypost/", myBody={"test":"trial"})

def test_prepare_loader():
	prepareDataLoaderFile([2100,2190,13001,70])# AHUs
	prepareDataLoaderFile([2190,2215,10001,14])# Chillers
	prepareDataLoaderFile([2215,2240,20001,4])# Pumps
	prepareDataLoaderFile([2240,2265,30001,4])# Secondary Pumps
	prepareDataLoaderFile([2265,2355,101,140])# VAVs

def test_db_insert():
    myconnectionpool = createDBConnectionPool()
    insertDataIntoDatabase(myconnectionpool)

def test_load_eqp_ids(mydatabase='acrex_02'):
    global gl_configuration
    myconnectionpool = createDBConnectionPool(mydatabase=mydatabase)
    if myconnectionpool == None: printTrace('Unable to get Connection Pool')
    prepareDeploymentConfiguration('glIBMSDeployment.json', myconnectionpool)
    [printTrace('Key {} Length {}'.format(x, len(gl_configuration[x]))) for x in gl_configuration]
    test = {'inputValid': True, 'errorCode': [], 'e_ss_type': 'NONGL_SS_VAV', 'e_address_value': '0000b5c000', 'e_name': 0, 'e_id': '9682ff60-35ea-4041-aea8-df92dc291d31', 'p_parent_eqp': '9682ff60-35ea-4041-aea8-df92dc291d31', 'p_name': 'VAV_ZAT', 'p_description': '', 'eqp_tableName': 'vav_0000b5c000_ahu_om_p'}
    # myObjs = ['GL 01 00 01 b0 0 00d', 'GL 01 00 02 a0 0 03e', 'GL 01 00 00 B8 C 002', 'GL 00 00 00 b5 c 000', 'GL 01 00 02 B0 0 003']
    myObjs = ['GL 01 00 01 b0 0 00d', 'GL 01 00 02 a0 0 03e']
    [print('objName: {} - param: {}'.format(x, processEquipmentCode(x))) for x in myObjs]
    myCodeDetails = processEquipmentCode('GL 01 00 01 b0 0 00d')
    insertDataIntoDatabase(myconnectionpool, mytable=myCodeDetails['eqp_tableName'], myvalues=[(myCodeDetails['e_id'],getstrTimeNow(), myCodeDetails['p_name'], 23.4)])

def test_get_objectName():
    printTrace(getObjectName('5:42', 180))
    printTrace(getObjectName('5:24', 180))
    printTrace(getObjectName('127.0.0.1:2401', 177))
    printTrace(getObjectName('5:42', 177))
    printTrace(getObjectName('5:24', 177))

def test_with_codebook(testdb='acrex_02'):
    conPool = createDBConnectionPool(testdb)
    prepareConfigurationFromCodeBook(myConnectionPool=conPool)
    myObjs = ['GL 01 00 05 a0 0 001', 'GL 01 00 05 b2 0 005', 'GL 01 00 02 b0 0 015', 'GL 01 00 04 b4 0 000', 'GL 01 03 05 b8 C 034', 'GL 01 00 05 b7 0 007', 'GL 01 00 01 b1 0 000', 'GL 01 02 03 b5 C 020']
    for x in myObjs: processEquipmentCode(x, tblNameLength=10)
    for x in myObjs: processEquipmentCode(x, tblNameLength=12)
    [print('objName: {} - param: {}'.format(x, processEquipmentCode(x, tblNameLength=10))) for x in myObjs]
    [print('objName: {} - param: {}'.format(x, processEquipmentCode(x, tblNameLength=12))) for x in myObjs]

def executeMySQLQuery(mydb='ibms_for_cpm', myquery=None, conPool=None):
    query = "select table_name from information_schema.tables where table_schema = 'ibms_for_cpm' and table_name like '%_om_p' and table_name not in ('reference_om_p');"
    myresults = []
    # ALTER TABLE {} DROP INDEX unique_index, ADD UNIQUE KEY `unique_index` (`ss_id`,`param_id`,`measured_time`);

    if myquery != None: query = myquery
    try:
        if conPool == None: conPool = createDBConnectionPool(mydb)
        cnx = conPool.get_connection()
        cursor = cnx.cursor(buffered=True)
        cursor.execute(query)
        myresults = [x[0] for x in cursor.fetchall()]
        [printTrace(x[0]) for x in myresults]
    except Exception as e:
        frameinfo = getframeinfo(currentframe())
        printTrace("Exception{}-'{}' in file-{} function-{} line-{} table-{}".format(type(e), e, frameinfo.filename, frameinfo.function, frameinfo.lineno, mytbl))
    finally:
        if cursor != None: cursor.close()
        if cnx != None: cnx.close()
        return myresults

def checkDBUpdateSummary(mydb='ibms_for_cpm', myquery=None, conPool=None, qTables=None):
    mytables = ['ahu_0001a00000_om_p', 'ahu_0002a00000_om_p', 'ahu_0003a00000_om_p', 'ahu_0004a00000_om_p', 'ahu_0005a00000_om_p', 'ahu_0006a00000_om_p', 'ahu_0007a00000_om_p', 'vav_0000b5c010_ahu_om_p', 'vav_0000b5c020_ahu_om_p', 'vav_0000b5c030_ahu_om_p', 'vav_0000b5c040_ahu_om_p', 'vav_0000b5c050_ahu_om_p', 'vav_0000b5c060_ahu_om_p', 'vav_0000b5c070_ahu_om_p', 'ch_0001b00000_om_p', 'ch_0002b00000_om_p', 'ch_0003b00000_om_p', 'ch_0004b00000_om_p', 'ch_0005b00000_om_p', 'ct_0001b70000_om_p', 'ct_0002b70000_om_p', 'ct_0003b70000_om_p', 'ct_0004b70000_om_p', 'ct_0005b70000_om_p', 'ctf_0000b8c010_ct_om_p', 'ctf_0000b8c020_ct_om_p', 'ctf_0000b8c030_ct_om_p', 'ctf_0000b8c040_ct_om_p', 'ctf_0000b8c050_ct_om_p', 'pu_0001b10000_om_p', 'pu_0002b10000_om_p', 'pu_0003b10000_om_p', 'pu_0004b10000_om_p', 'pu_0005b10000_om_p', 'secpu_0001b20000_om_p', 'secpu_0002b20000_om_p', 'secpu_0003b20000_om_p', 'secpu_0004b20000_om_p', 'secpu_0005b20000_om_p', 'cndpu_0001b40000_om_p', 'cndpu_0002b40000_om_p', 'cndpu_0003b40000_om_p', 'cndpu_0004b40000_om_p', 'cndpu_0005b40000_om_p', 'gl_subsystem_latest_event']
    if qTables != None: mytables = qTables
    query = 'select date(modified_at) mydate, hour(modified_at) myhour, min(modified_at), max(modified_at), count(*) mycount from {} group by mydate, myhour order by mydate desc, myhour desc limit 1;'
    # ALTER TABLE {} DROP INDEX unique_index, ADD UNIQUE KEY `unique_index` (`ss_id`,`param_id`,`measured_time`);

    if myquery != None: query = myquery
    try:
        if conPool == None: conPool = createDBConnectionPool(mydb)
        cnx = conPool.get_connection()
        cursor = cnx.cursor(buffered=True)
        myout = []
        for mytbl in mytables:
            cursor.execute(query.format(mytbl))
            myout.append(cursor.fetchone())
        # [printTrace(x) for x in cursor.fetchall()]
        print(query, len(mytables), mytables[-1])
        for j in range(len(mytables)):
            print('{}, {}, {}, {}, {}, {}'.format(mytables[j], myout[j][0], myout[j][1], myout[j][2], myout[j][3], myout[j][4]))
    except Exception as e:
        frameinfo = getframeinfo(currentframe())
        printTrace("Exception{}-'{}' in file-{} function-{} line-{} table-{}".format(type(e), e, frameinfo.filename, frameinfo.function, frameinfo.lineno, mytbl))
    finally:
        if cursor != None: cursor.close()
        if cnx != None: cnx.close()

def test_eqp_code():
    myConnectionPool=createDBConnectionPool(mydatabase='srn_atl_f1a', dbuser='graylinx', dbpassword ='GrayLinx@24', host='localhost')
    prepareConfigurationFromCodeBook(glConfigFile='./data/CBParameters.csv', deplDtlsJSONFile='./data/GLSDeploymentDetails.json', myConnectionPool=myConnectionPool)
    processEquipmentCode('GL 01 00 09 aa A 001', tblNameLength=12)

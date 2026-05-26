#!/usr/bin/python
'''
glObjectNameHandler.py as a Module
Steps - To Handle Retrofit Scenarios with Graylinx Object Names

Data Preparation
    Dictionary/ JSON - DONE
    Dictionary of {DDCIP:{OBJID:{OBJNAME}}} - DONE
    Prefix Changed Samples - DONE
    CSV File from Commissioning
    DB Table Post Commissioning
    Reuse description column of gl_subsystem table ???
    Generalized Path of ObjectName - PARTIAL ???
PBS Updates/ Enhancements
    DEFAULT use of name from DDC - DONE
    ObjectHandler as a Configurable Parameter in PBS - DONE
    Invoke processObjectNames from PBS - DONE
    STEPS
        IMPORT - from glObjectNameHandler import processObjectNames
        GLOBALS
            GL_DEFAULTS['USE_OBJECT_NAME_HANDLER'] = True
            parser.add_argument("--useObjectNameHandler", type=str, help="Use Object Name Handler", default=GL_DEFAULTS['USE_OBJECT_NAME_HANDLER'])
            GL_GLOBALS['USE_OBJECT_NAME_HANDLER'] = args.useObjectNameHandler
        INVOKE
            Modify (with optional argument useObjNameHandler) _get_RPM_ACK_Dict(self, listOfReadAccessResults, useObjNameHandler = GL_GLOBALS['USE_OBJECT_NAME_HANDLER'])
            Use in _get_RPM_ACK_Dict - if (useObjNameHandler): myDict = processObjectNames(myDict, {"prefixChanged":"JL"}, [])
GL Server Updates/ Enhancements
ObjID -> Param in UI, Graphs, Analytics
Testing/ Demo
    Test Cases - GV --> GL and work end-to-end - (SIMULATOR->PBS)->GL_SERVER->UI
    Custom data from Other Samples/ Scenarios
    Demonstration, if required ...
    Sample Input from Current Scenarios
Prepare Data from Commissioning ???
'''
############################## Import Libraries ########################
from glIBMSLibrary import *
import csv
########################################################################

############################### Module Globals #########################
_GL_GLOBALS = {}
_mycompliantsample1 = {"request": {"request_uuid": "8631d397-620e-4c2e-a531-543ad8e2a0e5", "request_parts": ["", "readmultiple", "192.168.1.20:1944", "2:13033", "objectName", "presentValue", "2:13047", "objectName", "presentValue", "2:13007", "objectName", "presentValue", "2:13043", "objectName", "presentValue", "2:13049", "objectName", "presentValue", "2:13050", "objectName", "presentValue", "2:13009", "objectName", "presentValue", "2:13025", "objectName", "presentValue", "2:13056", "objectName", "presentValue", "2:13052", "objectName", "presentValue"], "query_params": {"type": ["_p"]}, "Request_At": "2023-10-06 12:45:00", "Arguments": ["", "readmultiple", "192.168.1.20:1944", "2:13033", "objectName", "presentValue", "2:13047", "objectName", "presentValue", "2:13007", "objectName", "presentValue", "2:13043", "objectName", "presentValue", "2:13049", "objectName", "presentValue", "2:13050", "objectName", "presentValue", "2:13009", "objectName", "presentValue", "2:13025", "objectName", "presentValue", "2:13056", "objectName", "presentValue", "2:13052", "objectName", "presentValue"], "current_status": "Work in progress..."}, "response": {"propertyResults": [{"objectType": "analogValue", "objectId": 13033, "properties": [{"propertyId": "objectName", "datatype": "Any", "propertyValue": "GL 00 00 01 A0 0 020"}, {"propertyId": "presentValue", "datatype": "Any", "propertyValue": 111.0999984741211}]}, {"objectType": "analogValue", "objectId": 13047, "properties": [{"propertyId": "objectName", "datatype": "Any", "propertyValue": "GL 00 00 01 A0 0 02e"}, {"propertyId": "presentValue", "datatype": "Any", "propertyValue": 3.700000047683716}]}, {"objectType": "analogValue", "objectId": 13007, "properties": [{"propertyId": "objectName", "datatype": "Any", "propertyValue": "GL 00 00 01 A0 0 006"}, {"propertyId": "presentValue", "datatype": "Any", "propertyValue": 35.72999954223633}]}, {"objectType": "analogValue", "objectId": 13043, "properties": [{"propertyId": "objectName", "datatype": "Any", "propertyValue": "GL 00 00 01 A0 0 02a"}, {"propertyId": "presentValue", "datatype": "Any", "propertyValue": 391.239990234375}]}, {"objectType": "analogValue", "objectId": 13049, "properties": [{"propertyId": "objectName", "datatype": "Any", "propertyValue": "GL 00 00 01 A0 0 030"}, {"propertyId": "presentValue", "datatype": "Any", "propertyValue": 217.94000244140625}]}, {"objectType": "analogValue", "objectId": 13050, "properties": [{"propertyId": "objectName", "datatype": "Any", "propertyValue": "GL 00 00 01 A0 0 031"}, {"propertyId": "presentValue", "datatype": "Any", "propertyValue": 210.4600067138672}]}, {"objectType": "analogValue", "objectId": 13009, "properties": [{"propertyId": "objectName", "datatype": "Any", "propertyValue": "GL 00 00 01 A0 0 008"}, {"propertyId": "presentValue", "datatype": "Any", "propertyValue": 24.829999923706055}]}, {"objectType": "analogValue", "objectId": 13025, "properties": [{"propertyId": "objectName", "datatype": "Any", "propertyValue": "GL 00 00 01 A0 0 018"}, {"propertyId": "presentValue", "datatype": "Any", "propertyValue": 48.18000030517578}]}, {"objectType": "analogValue", "objectId": 13056, "properties": [{"propertyId": "objectName", "datatype": "Any", "propertyValue": "GL 00 00 01 A0 0 037"}, {"propertyId": "presentValue", "datatype": "Any", "propertyValue": -93.79000091552734}]}, {"objectType": "analogValue", "objectId": 13052, "properties": [{"propertyId": "objectName", "datatype": "Any", "propertyValue": "GL 00 00 01 A0 0 033"}, {"propertyId": "presentValue", "datatype": "Any", "propertyValue": 22.700000762939453}]}]}}

_myPrefixChangedsample1 = {"request": {"request_uuid": "8631d397-620e-4c2e-a531-543ad8e2a0e5", "request_parts": ["", "readmultiple", "192.168.1.20:1944", "2:13033", "objectName", "presentValue", "2:13047", "objectName", "presentValue", "2:13007", "objectName", "presentValue", "2:13043", "objectName", "presentValue", "2:13049", "objectName", "presentValue", "2:13050", "objectName", "presentValue", "2:13009", "objectName", "presentValue", "2:13025", "objectName", "presentValue", "2:13056", "objectName", "presentValue", "2:13052", "objectName", "presentValue"], "query_params": {"type": ["_p"]}, "Request_At": "2023-10-06 12:45:00", "Arguments": ["", "readmultiple", "192.168.1.20:1944", "2:13033", "objectName", "presentValue", "2:13047", "objectName", "presentValue", "2:13007", "objectName", "presentValue", "2:13043", "objectName", "presentValue", "2:13049", "objectName", "presentValue", "2:13050", "objectName", "presentValue", "2:13009", "objectName", "presentValue", "2:13025", "objectName", "presentValue", "2:13056", "objectName", "presentValue", "2:13052", "objectName", "presentValue"], "current_status": "Work in progress..."}, "response": {"propertyResults": [{"objectType": "analogValue", "objectId": 13033, "properties": [{"propertyId": "objectName", "datatype": "Any", "propertyValue": "JL 00 00 01 A0 0 020"}, {"propertyId": "presentValue", "datatype": "Any", "propertyValue": 111.0999984741211}]}, {"objectType": "analogValue", "objectId": 13047, "properties": [{"propertyId": "objectName", "datatype": "Any", "propertyValue": "JL 00 00 01 A0 0 02e"}, {"propertyId": "presentValue", "datatype": "Any", "propertyValue": 3.700000047683716}]}, {"objectType": "analogValue", "objectId": 13007, "properties": [{"propertyId": "objectName", "datatype": "Any", "propertyValue": "JL 00 00 01 A0 0 006"}, {"propertyId": "presentValue", "datatype": "Any", "propertyValue": 35.72999954223633}]}, {"objectType": "analogValue", "objectId": 13043, "properties": [{"propertyId": "objectName", "datatype": "Any", "propertyValue": "JL 00 00 01 A0 0 02a"}, {"propertyId": "presentValue", "datatype": "Any", "propertyValue": 391.239990234375}]}, {"objectType": "analogValue", "objectId": 13049, "properties": [{"propertyId": "objectName", "datatype": "Any", "propertyValue": "JL 00 00 01 A0 0 030"}, {"propertyId": "presentValue", "datatype": "Any", "propertyValue": 217.94000244140625}]}, {"objectType": "analogValue", "objectId": 13050, "properties": [{"propertyId": "objectName", "datatype": "Any", "propertyValue": "JL 00 00 01 A0 0 031"}, {"propertyId": "presentValue", "datatype": "Any", "propertyValue": 210.4600067138672}]}, {"objectType": "analogValue", "objectId": 13009, "properties": [{"propertyId": "objectName", "datatype": "Any", "propertyValue": "JL 00 00 01 A0 0 008"}, {"propertyId": "presentValue", "datatype": "Any", "propertyValue": 24.829999923706055}]}, {"objectType": "analogValue", "objectId": 13025, "properties": [{"propertyId": "objectName", "datatype": "Any", "propertyValue": "JL 00 00 01 A0 0 018"}, {"propertyId": "presentValue", "datatype": "Any", "propertyValue": 48.18000030517578}]}, {"objectType": "analogValue", "objectId": 13056, "properties": [{"propertyId": "objectName", "datatype": "Any", "propertyValue": "JL 00 00 01 A0 0 037"}, {"propertyId": "presentValue", "datatype": "Any", "propertyValue": -93.79000091552734}]}, {"objectType": "analogValue", "objectId": 13052, "properties": [{"propertyId": "objectName", "datatype": "Any", "propertyValue": "JL 00 00 01 A0 0 033"}, {"propertyId": "presentValue", "datatype": "Any", "propertyValue": 22.700000762939453}]}]}}

_testSample = {"request": {"request_uuid": "8631d397-620e-4c2e-a531-543ad8e2a0e5"}, "response":{"propertyResults":[{"objectType": "analogValue", "objectId": 13033, "properties":[{"propertyId": "objectName", "datatype": "Any", "propertyValue": "JL 00 00 01 A0 0 020"}]}]}}

def _sampleDemo(inputObject=('ddc1','2:13033'), compliantRMResponse={}, nonCompliantRMResponse={}):
    myresult = ''
    a = {'b':'input'}
    # print("Given Object: {}".format(a))
    # print("Modified Object {}".format(_testUpdate(a,'b','inputModified')))
    print('####################### Sample Demo Starts #######################')
    # Get Name as per Graylinx Code Book
    print("############### Get Name as per Graylinx Code Book ###############")
    print("ObjIn: {} ==> GCB Name '{}'".format(inputObject, getObjectName(inputObject[0], inputObject[1])))
    # Transform Sample ReadMultipleResponse - Sample1 - Compliant
    # print("################# Compliant Sample per Code Book #################")
    # print("Test Sample: {} ==> Processed Result {}".format(_mycompliantsample1, processObjectNames(_mycompliantsample1)))
    # # Transform Sample ReadMultipleResponse - Sample2 - NonCompliant
    print("################ Prefix Changed Sample: Processed ################")
    # print("Test Sample ==> {}".format(_myPrefixChangedsample1))
    # processObjectNames(_myPrefixChangedsample1)
    # print("Processed Result {}".format(_myPrefixChangedsample1))
    print("Test Sample ==> {}".format(_testSample))    
    print("Processed Result {}".format(processObjectNames(_testSample)))
    print("Test Sample 2 ==> {}".format(_myPrefixChangedsample1["response"]))    
    print("Processed Result 2 {}".format(processObjectNames(_myPrefixChangedsample1["response"],{"prefixChanged":"JL"}, objNameLocation = ['propertyResults'])))
    print("############ Look up Table as a Dictionary: Processed ############")
    # print(_GL_GLOBALS['mappingTable']['DDC-1']['13060'])
    # print("Test Input {}".format("'DDC-1', '13070'"))
    # print("Output ==> ", getObjectName("DDC-1", '13070'))
    print("############ Look up Table as a Dictionary: VAV Mapping Processed ############")
    print(_GL_GLOBALS['vavMappingTable']['1']['102'])
    print("Test Input {}".format("'1', '102'"))
    print("Output ==> ", getObjectName("1", '102'))
    print('####################### End of Sample Demo #######################')
    # print("################ Prefix Changed Sample: Updater 1 ################")
    # _myupdater(_testSample, ["response", "propertyResults", 0, "properties", 0, "propertyValue"], "GL 00 00 01 A0 0 020")
    # print('Updated Input - {}'.format(_testSample))
    # print('####################### End of Sample Demo #######################')
    return myresult
########################################################################

############################## Libraries Exposed #######################
def initialize():
    global _GL_GLOBALS
    _GL_GLOBALS['nameTable'] = {
        'DDCIP':{'OBJID':{'OBJNAME':('RAT','GL 00 00 01 A0 0 02e')}},
        'ddc1':{'2:13033':{'OBJNAME':('RAT','GL 00 00 01 A0 0 020')}}
    }
    _GL_GLOBALS['mappingTable'] = {'DDC-1': {'13001': ['AHU-2', 'RAT', 'RAT', 'GL 00 01 01 A0 0 000'], '13002': ['AHU-2', 'RAT_SP', 'RAT_SP', 'GL 00 01 01 A0 0 001'], '13003': ['AHU-2', 'RARH', 'RARH', 'GL 00 01 01 A0 0 002'], '13004': ['AHU-2', 'RARH_SP', 'RARH_SP', 'GL 00 01 01 A0 0 003'], '13005': ['AHU-2', 'SAT', 'SAT', 'GL 00 01 01 A0 0 004'], '13006': ['AHU-2', 'SAT_SP', 'SAT_SP', 'GL 00 01 01 A0 0 005'], '13007': ['AHU-2', 'SARH', 'SARH', 'GL 00 01 01 A0 0 006'], '13008': ['AHU-2', 'SARH_SP', 'SARH_SP', 'GL 00 01 01 A0 0 007'], '13009': ['AHU-2', 'OAT', 'OAT', 'GL 00 01 01 A0 0 008'], '13010': ['AHU-2', 'OARH', 'OARH', 'GL 00 01 01 A0 0 009'], '13011': ['AHU-2', 'MAT', 'MAT', 'GL 00 01 01 A0 0 00a'], '13012': ['AHU-2', 'MARH', 'MARH', 'GL 00 01 01 A0 0 00b'], '13013': ['AHU-2', 'CHW_Vlv_Pos', 'CHW_Vlv_Pos', 'GL 00 01 01 A0 0 00c'], '13014': ['AHU-2', 'CHW_Vlv_Pos_SP', 'CHW_Vlv_Pos_SP', 'GL 00 01 01 A0 0 00d'], '13015': ['AHU-2', 'OA_Dmpr_Pos', 'OA_Dmpr_Pos', 'GL 00 01 01 A0 0 00e'], '13016': ['AHU-2', 'OA_Dmpr_Pos_SP', 'OA_Dmpr_Pos_SP', 'GL 00 01 01 A0 0 00f'], '13017': ['AHU-2', 'RA_Dmpr_Pos', 'RA_Dmpr_Pos', 'GL 00 01 01 A0 0 010'], '13018': ['AHU-2', 'RA_Dmpr_Pos_SP', 'RA_Dmpr_Pos_SP', 'GL 00 01 01 A0 0 011'], '13019': ['AHU-2', 'EA_Dmpr_Pos', 'EA_Dmpr_Pos', 'GL 00 01 01 A0 0 012'], '13020': ['AHU-2', 'EA_Dmpr_Pos_SP', 'EA_Dmpr_Pos_SP', 'GL 00 01 01 A0 0 013'], '13021': ['AHU-2', 'SA_Dmpr_Pos', 'SA_Dmpr_Pos', 'GL 00 01 01 A0 0 014'], '13022': ['AHU-2', 'SA_Dmpr_Pos_SP', 'SA_Dmpr_Pos_SP', 'GL 00 01 01 A0 0 015'], '13023': ['AHU-2', 'SA_CFM', 'SA_CFM', 'GL 00 01 01 A0 0 016'], '13024': ['AHU-2', 'DSP', 'DSP', 'GL 00 01 01 A0 0 017'], '13025': ['AHU-2', 'DSP_SP', 'DSP_SP', 'GL 00 01 01 A0 0 018'], '13026': ['AHU-2', 'SP_Pre_Filter', 'SP_Pre_Filter', 'GL 00 01 01 A0 0 019'], '13027': ['AHU-2', 'SP_Post_Filter', 'SP_Post_Filter', 'GL 00 01 01 A0 0 01a'], '13028': ['AHU-2', 'DPS_Filter', 'DPS_Filter', 'GL 00 01 01 A0 0 01b'], '13029': ['AHU-2', 'SAF_VFD_On_Off', 'SAF_VFD_On_Off', 'GL 00 01 01 A0 0 01c'], '13030': ['AHU-2', 'SAF_VFD_On_Off_Fbk', 'SAF_VFD_On_Off_Fbk', 'GL 00 01 01 A0 0 01d'], '13031': ['AHU-2', 'SAF_VFD_AM', 'SAF_VFD_AM', 'GL 00 01 01 A0 0 01e'], '13032': ['AHU-2', 'SAF_VFD_AM_Fbk', 'SAF_VFD_AM_Fbk', 'GL 00 01 01 A0 0 01f'], '13033': ['AHU-2', 'SAF_VFD_Trip_SS', 'SAF_VFD_Trip_SS', 'GL 00 01 01 A0 0 020'], '13034': ['AHU-2', 'SAF_VFD_Speed', 'SAF_VFD_Speed', 'GL 00 01 01 A0 0 021'], '13035': ['AHU-2', 'SAF_VFD_Speed_Fbk', 'SAF_VFD_Speed_Fbk', 'GL 00 01 01 A0 0 022'], '13036': ['AHU-2', 'VFD_Byp_SS', 'VFD_Byp_SS', 'GL 00 01 01 A0 0 023'], '13037': ['AHU-2', 'Fire_Sensor', 'Fire_Sensor', 'GL 00 01 01 A0 0 024'], '13038': ['AHU-2', 'RAQ_Co2', 'RAQ_Co2', 'GL 00 01 01 A0 0 025'], '13039': ['AHU-2', 'RAQ_Co2_SP', 'RAQ_Co2_SP', 'GL 00 01 01 A0 0 026'], '13040': ['AHU-2', 'DPS_SAF_SS', 'DPS_SAF_SS', 'GL 00 01 01 A0 0 027'], '13041': ['AHU-2', 'SAF_Pwr_A', 'SAF_Pwr_A', 'GL 00 01 01 A0 0 028'], '13042': ['AHU-2', 'SAF_Pwr_B', 'SAF_Pwr_B', 'GL 00 01 01 A0 0 029'], '13043': ['AHU-2', 'SAF_Pwr_C', 'SAF_Pwr_C', 'GL 00 01 01 A0 0 02a'], '13044': ['AHU-2', 'SAF_Volt_A', 'SAF_Volt_A', 'GL 00 01 01 A0 0 02b'], '13045': ['AHU-2', 'SAF_Volt_B', 'SAF_Volt_B', 'GL 00 01 01 A0 0 02c'], '13046': ['AHU-2', 'SAF_Volt_C', 'SAF_Volt_C', 'GL 00 01 01 A0 0 02d'], '13047': ['AHU-2', 'SAF_Amps_A', 'SAF_Amps_A', 'GL 00 01 01 A0 0 02e'], '13048': ['AHU-2', 'SAF_Amps_B', 'SAF_Amps_B', 'GL 00 01 01 A0 0 02f'], '13049': ['AHU-2', 'SAF_Amps_C', 'SAF_Amps_C', 'GL 00 01 01 A0 0 030'], '13050': ['AHU-2', 'SAF_PF_A', 'SAF_PF_A', 'GL 00 01 01 A0 0 031'], '13051': ['AHU-2', 'SAF_PF_B', 'SAF_PF_B', 'GL 00 01 01 A0 0 032'], '13052': ['AHU-2', 'SAF_PF_C', 'SAF_PF_C', 'GL 00 01 01 A0 0 033'], '13055': ['AHU-2', 'DPS_RAF_SS', 'DPS_RAF_SS', 'GL 00 01 01 A0 0 036'], '13056': ['AHU-2', 'RAF_Pwr_A', 'RAF_Pwr_A', 'GL 00 01 01 A0 0 037'], '13057': ['AHU-2', 'RAF_Pwr_B', 'RAF_Pwr_B', 'GL 00 01 01 A0 0 038'], '13058': ['AHU-2', 'RAF_Pwr_C', 'RAF_Pwr_C', 'GL 00 01 01 A0 0 039'], '13059': ['AHU-2', 'RAF_Volt_A', 'RAF_Volt_A', 'GL 00 01 01 A0 0 03a'], '13060': ['AHU-2', 'RAF_Volt_B', 'RAF_Volt_B', 'GL 00 01 01 A0 0 03b'], '13061': ['AHU-2', 'RAF_Volt_C', 'RAF_Volt_C', 'GL 00 01 01 A0 0 03c'], '13062': ['AHU-2', 'RAF_Amps_A', 'RAF_Amps_A', 'GL 00 01 01 A0 0 03d'], '13063': ['AHU-2', 'RAF_Amps_B', 'RAF_Amps_B', 'GL 00 01 01 A0 0 03e'], '13064': ['AHU-2', 'RAF_Amps_C', 'RAF_Amps_C', 'GL 00 01 01 A0 0 03f'], '13066': ['AHU-2', 'RAF_PF_A', 'RAF_PF_A', 'GL 00 01 01 A0 0 041'], '13067': ['AHU-2', 'RAF_PF_B', 'RAF_PF_B', 'GL 00 01 01 A0 0 042'], '13068': ['AHU-2', 'RAF_PF_C', 'RAF_PF_C', 'GL 00 01 01 A0 0 043'], '13070': ['AHU-2', 'AHU_On_Off', 'AHU_On_Off', 'GL 00 01 01 A0 0 045']}}
    _GL_GLOBALS["vavMappingTable"] = {"1": {"114": ["1", "analogValue", "VAV_Dmpr_Pos-14", "VAV_Dmpr_Pos-14", "GL 01 00 02 B5 0 006"], "108": ["1", "analogValue", "VAV_ZAT-2", "VAV_ZAT-2", "GL 01 00 02 B5 0 000"], "109": ["1", "analogValue", "VAV_ZAT_SP-4", "VAV_ZAT_SP-4", "GL 01 00 02 B5 0 001"], "111": ["1", "analogValue", "VAV_CFM_Design-8", "VAV_CFM_Design-8", "GL 01 00 02 B5 0 003"], "110": ["1", "analogValue", "VAV_ZARH-6", "VAV_ZARH-6", "GL 01 00 02 B5 0 002"], "113": ["1", "analogValue", "VAV_CFM_Actual-12", "VAV_CFM_Actual-12", "GL 01 00 02 B5 0 005"], "112": ["1", "analogValue", "VAV_CFM_SP-10", "VAV_CFM_SP-10", "GL 01 00 02 B5 0 004"], "102": ["1", "analogValue", "VAV_ZAT_SP-3", "VAV_ZAT_SP-3", "GL 01 00 01 B5 0 001"], "103": ["1", "analogValue", "VAV_ZARH-5", "VAV_ZARH-5", "GL 01 00 01 B5 0 002"], "101": ["1", "analogValue", "VAV_ZAT-1", "VAV_ZAT-1", "GL 01 00 01 B5 0 000"], "106": ["1", "analogValue", "VAV_CFM_Actual-11", "VAV_CFM_Actual-11", "GL 01 00 01 B5 0 005"], "107": ["1", "analogValue", "VAV_Dmpr_Pos-13", "VAV_Dmpr_Pos-13", "GL 01 00 01 B5 0 006"], "104": ["1", "analogValue", "VAV_CFM_Design-7", "VAV_CFM_Design-7", "GL 01 00 01 B5 0 003"], "105": ["1", "analogValue", "VAV_CFM_SP-9", "VAV_CFM_SP-9", "GL 01 00 01 B5 0 004"]}}

def getObjectName(ddc,oid,givenName=''):
    '''
    # To load the csv file and prepare Look-up Dictionary
    # DDC-ID,ObjId,AHU-ID,GL Param Name,Display Name,GL Code
    # DDC-1,13001,AHU-2,RAT,RAT,GL 00 01 01 A0 0 000
    import csv
    myobj = {}
    with open('HVACObjectMapping.csv') as csvFile:
        reader = csv.DictReader(csvFile,['DDC-ID','ObjID'],'Object')
        for row in reader:
            # print(row)
            if row['DDC-ID'] not in myobj:
                myobj[row['DDC-ID']] = {}
                print(myobj)
            myobj[row['DDC-ID']][row['ObjID']] = row['Object']
    print(myobj)
    '''
    # myname = 'DDC:{} => OID:{}'.format(ddc, oid)
    myname = givenName
    if isinstance(ddc, str) and (ddc in _GL_GLOBALS['nameTable']):
        if _GL_GLOBALS['nameTable'][ddc][oid]['OBJNAME'][1] is not None:
            myname = _GL_GLOBALS['nameTable'][ddc][oid]['OBJNAME'][1]
    elif isinstance(ddc, dict) and ddc["prefixChanged"] is not None:
        myname = givenName.replace(ddc["prefixChanged"], "GL")
    # elif isinstance(_GL_GLOBALS['mappingTable'][ddc], dict) and _GL_GLOBALS['mappingTable'][ddc][oid][3] is not None:
    #     myname = _GL_GLOBALS['mappingTable'][ddc][oid][3]
    elif _GL_GLOBALS['vavMappingTable'][ddc][oid][3] is not None:
        myname = _GL_GLOBALS['vavMappingTable'][ddc][oid][3]
    else:
        if _GL_GLOBALS['nameTable'][ddc][oid]['OBJNAME'][1] is not None: myname = _GL_GLOBALS['nameTable'][ddc][oid]['OBJNAME'][1]
    return myname

def _myTestupdater(d, mylocation = ['response','propertyResults'], myValue='newInput'):
    for k,v in d.items():
        print("_myTestupdater: d-{}, mylocation-{}, myValue-{}".format(d, mylocation, myValue))
        if isinstance(v, dict):
            if (k == mylocation.pop(0)):
                if isinstance(k,str):
                    d[k] = myValue
                else:
                    _myTestupdater(d[k], mylocation, myValue)

def _myupdater(d, mylocation = ['response','propertyResults'], myValue='newInput'):
    mykey = mylocation.pop(0)
    print("_myupdater: d-{}, mylocation-{}, myValue-{}, mykey-{}".format(d, mylocation, myValue, mykey))
    if len(mylocation) > 0:
        _myupdater(d[mykey], mylocation, myValue)
    else:
        d[mykey]=myValue

def _testUpdate(a,b,c):
    a[b]=c
    return a

def processObjectNames(ddcResponse, ddcId={"prefixChanged":"JL"}, objNameLocation = ['response','propertyResults']):
    myresponse = {}
    processedResponse = ddcResponse.copy()
    myelements = processedResponse
    for myindex in objNameLocation:
        myelements = myelements[myindex]
    myresponse["objects"] = []
    mylocation = objNameLocation.copy()
    for i in range(len(myelements)):
        mylocation.append(i)
        element = myelements[i]
        oid = element["objectId"]
        mylocation.append("properties")
        for j in range(len(element["properties"])):
            if (element["properties"][j]["propertyId"] == "objectName"):
                mylocation.append(j)
                mylocation.append("propertyValue")
                ddcObjName = element["properties"][j]["propertyValue"]
                glObjName = getObjectName(ddcId, oid, ddcObjName)
                element["properties"][j]["propertyValue"] = glObjName
        myresponse['objects'].append((oid, ddcObjName, glObjName, mylocation))
        mylocation = objNameLocation.copy()
    print("Details of my Objects: {}".format(myresponse['objects']))
    return processedResponse
########################################################################

# MAIN Function
def main():
    print('Welcome to Graylinx Python Object Name Handler Solution! {}'.format(getstrTimeNow()))
    print('This Module enables to handle Retrofit Scenarios with Graylinx Object Names')
    global _GL_GLOBALS
    initialize()
    _sampleDemo()

################################################


################################################

###############################################################
# STARTER
if __name__ == "__main__":
    main()
###############################################################

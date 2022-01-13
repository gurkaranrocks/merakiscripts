readMe = """
 This is a script to mass-provision Meraki combined networks as individually managed networks 
 described in a CSV, without using templates. For every device to be provisioned, the script creates a 
 new network by cloning an existing one, claims the device into it, modifies VLAN subnets, 
 updates the firewall rules, create DHCP reservation and setup site to site VPN.

Usage:
  python cloneprovision.py -k <api key> -o <org name> -b <base net name> -f <input file name>
  
Parameters:
    -k <api key>            : Your Meraki Dashboard API key
    -o <org name>           : Name of the Meraki dashboard organization you want to modify
    -b <base net name>      : Name of the network to be used as a base for cloning
    -f <input file name>    : Name of CSV file containing device serial - net name - VLAN subnet mappings
  
Example:
  python provision.py -k 1234 -o "FCL - Retail" -b "_Golden_Image" -f input.csv
  
Input file example:

# AAAA-BBBB-CCCC,Network Name,TimeZone,Tag1 Tag2 Tag3,10:192.168.1.0/24
AAAA-BBBB-JJJJ,Retail5,America/Regina,Retail5 Alberta Calgary,100:10.1.105.0/24


  
Notes:    
 * The script supports cloning of combined networks
 * To configure VLANs, the clone source network must have MX VLANs enabled and the VLAN IDs to be modified
   must exist in it
 * In Windows, use double quotes ("") to enter command line parameters containing spaces
 * This script was built for Python 3.7.1
 * Depending on your operating system, the command to start python can be either "python" or "python3"

Required Python modules:
  Requests     : http://docs.python-requests.org
  
After installing Python, you can install these additional modules using pip with the following commands:
  pip install requests

Depending on your operating system, the command can be "pip3" instead of "pip"
Re-coded by a Network professional please excuse for any lame code.
"""

import sys, getopt, requests, time, datetime, ipaddress, json, re, urllib3

#SECTION: GLOBAL VARIABLES: MODIFY TO CHANGE SCRIPT BEHAVIOUR

API_EXEC_DELAY              = 0.21 #Used in merakiRequestThrottler() to avoid hitting dashboard API max request rate

#connect and read timeouts for the Requests module in seconds
REQUESTS_CONNECT_TIMEOUT    = 90
REQUESTS_READ_TIMEOUT       = 90

#SECTION: GLOBAL VARIABLES AND CLASSES: DO NOT MODIFY

LAST_MERAKI_REQUEST         = datetime.datetime.now()   #used by merakiRequestThrottler()


#SECTION: Classes


class ConfigLine:
    def __init__(self):
        self.netName = ''
        self.serial  = ''
        self.timezone = ''
        self.tags = ''
        self.vlans   = []
    
class Vlan:
    def __init__(self):
        self.id      = ''
        self.subnet  = ''
        self.mxIp    = ''


#SECTION: General use functions
 
def killScript():
    print('Execution interrupted')
    sys.exit(2)

    
def printHelpAndExit():
    print(readMe)
    sys.exit(2)
    
    
def loadFile(p_fileName):
    returnValue = []

    try:
        f = open(p_fileName, 'r')
    
        for line in f:
            if len(line) > 0:
                returnValue.append(line.strip())
            
        f.close()
    except:
        print('ERROR 01: Error loading file "%s"' % p_fileName)
        return None     
        
    return returnValue
    
    
def configDump(p_config):
    for network in p_config:
        print ("\nNetwork:", network.netName)
        print ("Serial:", network.serial)
        print ("\n TimeZone:", network.timezone)
        for vlan in network.vlans:
            print(vlan.id, str(vlan.subnet))            
    
  
def parseConfig(p_config):
    # returns parsed config list, or None on error

    retVal = []
    lineCounter = 0

    for line in p_config:
        lineCounter += 1
        stripLine = line.strip()
        if stripLine != '':
            if stripLine[0] != '#':
                splitLine = stripLine.split(',')
                
                if len(splitLine) < 2:
                    print('ERROR 02: Invalid config in line %s' % lineCounter)
                    return None
                    
                newLine = ConfigLine()
                
                newLine.serial    = splitLine[0].strip()
                newLine.netName   = splitLine[1].strip()
                newLine.timezone  = splitLine[2].strip()
                newLine.tags  = splitLine[3].strip()
                
                for i in range(4, len(splitLine)):
                    vlanElements = splitLine[i].split(':')
                    if len(vlanElements) != 2:
                        print('ERROR 03: Invalid VLAN definition in line %s' % lineCounter)
                        return None
                        
                    newVlan     = Vlan()
                    newVlan.id  = vlanElements[0].strip()
                    
                    try:
                        newVlan.subnet   = ipaddress.IPv4Network(vlanElements[1].strip(), False)
                        newVlan.mxIp     = list(newVlan.subnet.hosts())[0]
                        newVlan.start_reserved     = list(newVlan.subnet.hosts())[199]
                        newVlan.end_reserved     = list(newVlan.subnet.hosts())[249]
                    except:
                        print('ERROR 04: Invalid subnet definition in line %s' % lineCounter)
                        return None
                        
                    newLine.vlans.append(newVlan)
                    
                retVal.append(newLine)
                
    return retVal
    

def merakiRequestThrottler():
    #prevents hitting max request rate shaper of the Meraki Dashboard API
    global LAST_MERAKI_REQUEST
    
    if (datetime.datetime.now()-LAST_MERAKI_REQUEST).total_seconds() < (API_EXEC_DELAY):
        time.sleep(API_EXEC_DELAY)
    
    LAST_MERAKI_REQUEST = datetime.datetime.now()
    return
    
    
#SECTION: Meraki Dashboard API communication functions


def getOrgId(p_apiKey, p_orgName):
    #returns the organizations' list for a specified admin, with filters applied
        
    merakiRequestThrottler()
    try:
        r = requests.get('https://api.meraki.com/api/v0/organizations', headers={'X-Cisco-Meraki-API-Key': p_apiKey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    except:
        return None
    
    if r.status_code != requests.codes.ok:
        return None
        
    rjson = r.json()
    
    for org in rjson:
        if org['name'] == p_orgName:
            return org['id']
    
    return None
    
    
def getShardHost(p_apiKey, p_orgId):
    #patch
    return("api-mp.meraki.com")
    
    
def getNetId(p_apiKey, p_orgId, p_shard, p_netName):

    merakiRequestThrottler()

    requestUrl = "https://%s/api/v0/organizations/%s/networks" % (p_shard, p_orgId)
    
    try:
        r = requests.get(requestUrl, headers={'X-Cisco-Meraki-API-Key': p_apiKey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT), verify=False)
    except:
        return None
    
    if r.status_code != requests.codes.ok:

        return None
        
    rjson = r.json()
    for net in rjson:
        if net['name'] == p_netName:
            return net['id']
    
    return None

def getHubId(p_apiKey, p_shard, p_baseNetId):

    merakiRequestThrottler()
    
    requestUrl = "https://%s/api/v0/networks/%s/siteToSiteVpn" % (p_shard, p_baseNetId)
    
    try:
        r = requests.get(requestUrl, headers={'X-Cisco-Meraki-API-Key': p_apiKey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT), verify=False)

        
    except:
        return None
    
    if r.status_code != requests.codes.ok:
        return None
        
    rjson = r.json()
    for net in rjson['hubs']:
        return net['hubId']
    return None
        
def updateVpn(p_apiKey, p_shard, p_netId, p_hubId, p_vlanSubnet):

    merakiRequestThrottler()
    payload = json.dumps({"mode": "spoke","hubs": [{"hubId": p_hubId,"useDefaultRoute": "false"}],"subnets": [{"localSubnet": p_vlanSubnet,"useVpn": "true"}]})
    requestUrl = "https://%s/api/v0/networks/%s/siteToSiteVpn" % (p_shard, p_netId)
    
    try:
        r = requests.put(requestUrl, data=payload, headers={'X-Cisco-Meraki-API-Key': p_apiKey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT), verify=False)
    except:
        return None
    
    if r.status_code != requests.codes.ok:
        return None
        
    return 'success'
        

def createNet(p_apikey, p_orgid, p_shardurl, p_name, p_timezone, p_tags, p_basenetid):
   #creates a network into an organization, by cloning an existing one
   
    merakiRequestThrottler()
    
    payload = json.dumps({'name':p_name, 'type':'appliance cellularGateway environmental switch wireless', 'timeZone':p_timezone, 'tags':p_tags, 'copyFromNetworkId': p_basenetid})   
    try:
        r = requests.post('https://%s/api/v0/organizations/%s/networks' % (p_shardurl, p_orgid), data=payload, headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json', "Accept": "application/json"}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT), verify=False)

    except:

        return None
    
    if 200 <= r.status_code < 300:
        rjson = r.json()
        return rjson['id']

    print(r.status_code)
    return None
    
    
def claimDevice(p_apiKey, p_shard, p_netId, p_deviceSerial):
    #claims a device into a network
    
    merakiRequestThrottler()
    
    try:
        r = requests.post('https://%s/api/v0/networks/%s/devices/claim' % (p_shard, p_netId), data=json.dumps({'serial': p_deviceSerial}), headers={'X-Cisco-Meraki-API-Key': p_apiKey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT), verify=False)
    except:
        return None
        
    if 200 <= r.status_code < 300:
        return 'success'
    
    return None
    
    
def updateVlan(p_apiKey, p_shard, p_netId, p_vlanId, p_vlanSubnet, p_mxIp, p_start_reserved, p_end_reserved):
    #updates an existing MX VLAN in the specified org
    
    merakiRequestThrottler()
    
    payload = json.dumps({'applianceIp': p_mxIp, 'subnet': p_vlanSubnet, 'reservedIpRanges': [{"start": p_start_reserved,"end": p_end_reserved,"comment": "A reserved IP range"}]})  
    try:
        r = requests.put('https://%s/api/v0/networks/%s/vlans/%s' % (p_shard, p_netId, p_vlanId), data=payload, headers={'X-Cisco-Meraki-API-Key': p_apiKey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT), verify=False)
    except:
        return None        
    
    if 200 <= r.status_code < 300:
        return 'success'
    
    return None

def updateFirewall(p_apiKey, p_shard, p_netId, p_vlanSubnet):
    merakiRequestThrottler()
    p_originalSubnet = "10.64.1.0/24"
    payload = None
    try:
        r = requests.get('https://api-mp.meraki.com/api/v0/networks/%s/l3FirewallRules' % (p_netId), data=payload, headers={'X-Cisco-Meraki-API-Key': p_apiKey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT), verify=False)
    except:
        return None
    if r.status_code == 200:
        rjson = r.json()
        #print(json.dumps(rjson, sort_keys=True, indent=4))
        for row in rjson: 
            if re.search("10.64.1.0/24", row['srcCidr']) is not None:
                row['srcCidr'] = row['srcCidr'].replace("10.64.1.0/24",p_vlanSubnet)
            if re.search("10.64.1.0/24", row['destCidr']) is not None:
                row['destCidr'] = row['destCidr'].replace("10.64.1.0/24",p_vlanSubnet)
        payload = {"rules": rjson}
        try:
            r = requests.put('https://api-mp.meraki.com/api/v0/networks/%s/l3FirewallRules' % (p_netId), data=json.dumps(payload), headers={'X-Cisco-Meraki-API-Key': p_apiKey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT), verify=False)
        except:
            return None 
        if 200 <= r.status_code < 300:
             return 'success'

#SECTION: main
    
def main(argv):
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    errorCounter    = 0
    warningCounter  = 0

    argApiKey   = ''
    argOrgName  = ''
    argBaseNet  = ''
    argFile     = ''
    
    #get command line arguments
    try:
        opts, args = getopt.getopt(argv, 'hk:o:b:f:')
    except getopt.GetoptError:
        printHelpAndExit()
        
        
    for opt, arg in opts:
        if   opt == '-h':
            printHelpAndExit()
        elif opt == '-k':
            argApiKey   = arg
        elif opt == '-o':
            argOrgName  = arg
        elif opt == '-b':
            argBaseNet  = arg
        elif opt == '-f':
            argFile     = arg
            
    #make sure all mandatory arguments have been given
    if argApiKey == '' or argOrgName == '' or argBaseNet == '' or argFile == '':
        printHelpAndExit()
        
    print('Loading configuration file (%s)...' % argFile)
    fileRaw = loadFile(argFile)
    if fileRaw is None:
        killScript()
    
    print('Parsing configuration...')
    config = parseConfig(fileRaw)
 
    if config is None:
        killScript()
            
    print('Resolving organization parameters...')
    orgId = getOrgId(argApiKey, argOrgName)
    if orgId is None:
        print('ERROR 05: Unable to fetch organization Id')
        killScript()
    print('Organization ID is %s' % orgId)
    
    shard = getShardHost(argApiKey, orgId)    
    if shard is None:
        print("WARNING: Unable to resolve dashboard shard")
        warningCounter += 1
        shard = "api.meraki.com"
        
    baseNetId = getNetId(argApiKey, orgId, shard, argBaseNet)
    baseHubId = getHubId(argApiKey, shard, baseNetId)

    if baseNetId is None:
        print('ERROR 06: Unable to fetch Id for base network name "%s"' % argBaseNet)
        killScript()       
    print('Base network ID is %s' % baseNetId)

    print('Provisioning devices...')
    for item in config:
       print('Creating network "%s"...' % item.netName)        
       newNetId = createNet(argApiKey, orgId, shard, item.netName, item.timezone, item.tags, baseNetId)

       if newNetId is None:
           print('ERROR 07: Unable to create network')
           errorCounter += 1
       else:
           print('New network ID is %s' % newNetId)
           
           print('Claiming device "%s"...' % item.serial)
           
           success = claimDevice(argApiKey, shard, newNetId, item.serial)
           if success is None:
               print('ERROR 08: Unable to claim device')
               errorCounter += 1
                       
           if len(item.vlans) > 0:
               print('Setting VLAN subnets...')
                               
               for vlan in item.vlans:
                   print("Setting VLAN subnet", vlan.id, str(vlan.subnet))
                   success = updateVlan(argApiKey, shard, newNetId, vlan.id, str(vlan.subnet), str(vlan.mxIp), str(vlan.start_reserved), str(vlan.end_reserved))
                   if success is None:
                       print('ERROR 09: Unable to update VLAN %s' % vlan.id)
                       errorCounter += 1
                       
               for vlan in item.vlans:
                   print("Updating Firewall Rules for VLAN", vlan.id, str(vlan.subnet))
                   firewall = updateFirewall(argApiKey, shard, newNetId, str(vlan.subnet))
                   if firewall is None:
                       print('ERROR 10: Unable to update Firewall Rules for %s' % vlan.id)
                       errorCounter += 1
                       
               for vlan in item.vlans:
                   print('Creating site to site vpn for Network "%s"...' % item.netName)
                   updateVPN = updateVpn(argApiKey, shard, newNetId, baseHubId, str(vlan.subnet))
                   if updateVPN is None:
                       print('ERROR 11: Unable to update VPN Settings for "%s"...' % item.netName)
                       errorCounter += 1

    print('Execution complete: %s errors, %s warnings' % (errorCounter, warningCounter))
    
if __name__ == '__main__':
    main(sys.argv[1:])
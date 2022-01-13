import csv, os, meraki, time
import json
from datetime import datetime


# Either input your API key below by uncommenting line 10 and changing line 16 to api_key=API_KEY,
# or set an environment variable (preferred) to define your API key. The former is insecure and not recommended.
# For example, in Linux/macOS:  export MERAKI_DASHBOARD_API_KEY=093b24e85df15a3e66f1fc359f4c48493eaa1b73
# API_KEY = '093b24e85df15a3e66f1fc359f4c48493eaa1b73'


def main():
    # Instantiate a Meraki dashboard API session
    dashboard = meraki.DashboardAPI(
        api_key='PUT API KEY HERE',
        base_url='https://api-mp.meraki.com/api/v1/',
        output_log=False,
        log_file_prefix=os.path.basename(__file__)[:-3],
        log_path='',
        print_console=False
    )

    # Get list of organizations to which API key has access
    #organizations = dashboard.organizations.getOrganizations()
    org_id = 932734
    
    # Get list of networks in organization
    try:
        networks = dashboard.organizations.getOrganizationNetworks(org_id)
    except meraki.APIError as e:
        print(f'Meraki API error: {e}')
        print(f'status code = {e.status}')
        print(f'reason = {e.reason}')
        print(f'error = {e.message}')
        
    except Exception as e:
        print(f'some other error: {e}')
        

    # Create local folder
    todays_date = f'{datetime.now():%Y-%m-%d}'
    folder_name = f'Org {org_id}{todays_date}'
    if folder_name not in os.listdir():
        os.mkdir(folder_name)

    # Iterate through networks
    total = len(networks)
    counter = 1
    results = []
    data = {}
    print(f'  - iterating through {total} networks in organization {org_id}')
    for net in networks:
        print(f'Generating AP report in network {net["name"]} ({counter} of {total})')
        try:
            # Get ap channel utilization of last 10 minutes
            response = dashboard.networks.getNetworkNetworkHealthChannelUtilization(net['id'], timespan=60*10*1*1, total_pages='all')
            for result in response:
                try:
                    ap_info = dashboard.devices.getDevice(result['serial'])
                    wifi0 = result['wifi0']
                    wifi1 = result['wifi1']
                    if len(wifi0) and len(wifi1):
                        data = {
                            'AP Mac': ap_info['mac'],
                            'Serial': result['serial'],
                            'Model': result['model'],
                            'Tags': result['tags'],
                            '2.4Ghz Utilization': result['wifi0'][0]['utilization'],
                            '5.0Ghz Utilization': result['wifi1'][0]['utilization']
                        }
                    elif len(wifi0) and not len(wifi1):
                        data = {
                            'AP Mac': ap_info['mac'],
                            'Serial': result['serial'],
                            'Model': result['model'],
                            'Tags': result['tags'],
                            '2.4Ghz Utilization': result['wifi0'][0]['utilization'],
                            '5.0Ghz Utilization': 'Data not available'
                        }
                    elif len(wifi1) and not len(wifi0):
                        data = {
                            'AP Mac': ap_info['mac'],
                            'Serial': result['serial'],
                            'Model': result['model'],
                            'Tags': result['tags'],
                            '2.4Ghz Utilization': 'Data not available',
                            '5.0Ghz Utilization': result['wifi1'][0]['utilization']
                        }
                    else:
                        data = {
                            'AP Mac': ap_info['mac'],
                            'Serial': result['serial'],
                            'Model': result['model'],
                            'Tags': result['tags'],
                            '2.4Ghz Utilization': 'Data not available',
                            '5.0Ghz Utilization': 'Data not available'
                        }
                    results.append(data)
           
                   
                except meraki.APIError as e:
                    print(f'Meraki API error: {e}')
                    print(f'status code = {e.status}')
                    print(f'reason = {e.reason}')
                    print(f'error = {e.message}') 
                except Exception as e:
                    print(f'some other error: {e}')
                    continue
                
            if response:
                #Write to file
                file_name = f'{net["name"]}.csv'
                output_file = open(f'{folder_name}/{file_name}', mode='w', newline='\n')
                field_names = results[0].keys()
                csv_writer = csv.DictWriter(output_file, field_names, delimiter=',', quotechar='"',
                                            quoting=csv.QUOTE_ALL)
                csv_writer.writeheader()
                csv_writer.writerows(results)
                output_file.close()
                
                
            print(f'  - found {len(results)} APs')
            results = []
    
                    
                
        except meraki.APIError as e:
            print(f'Meraki API error: {e}')
            print(f'status code = {e.status}')
            print(f'reason = {e.reason}')
            print(f'error = {e.message}')
        except Exception as e:
            print(f'some other error: {e}')
            continue
        counter += 1

    #Stitch together one consolidated CSV per org
    output_file = open(f'{folder_name}.csv', mode='w', newline='\n')
    field_names = ['AP Mac', 'Serial', 'Model', 'Tags', '2.4Ghz Utilization', '5.0Ghz Utilization']
    field_names.insert(0, "Network Name")

    csv_writer = csv.DictWriter(output_file, field_names, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
    csv_writer.writeheader()
    for net in networks:
        file_name = f'{net["name"]}.csv'
        if file_name in os.listdir(folder_name):
            with open(f'{folder_name}/{file_name}') as input_file:
                csv_reader = csv.DictReader(input_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
                # next(csv_reader)
                for row in csv_reader:
                    row['Network Name'] = net['name']
                    csv_writer.writerow(row)


if __name__ == '__main__':
    start_time = datetime.now()
    main()
    end_time = datetime.now()
    print(f'\nScript complete, total runtime {end_time - start_time}')

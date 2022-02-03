import re
import meraki
import os
import requests
regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
API_KEY = 'ENTER YOUR API KEY HERE'

def check(email):
    # pass the regular expression
    # and the string into the fullmatch() method
    if (re.fullmatch(regex, email)):
        return True
    else:
        return False

def createadmin():
    username = str(input("Name of the Administrator to be created: "))
    while True:     
        try:
            if all(x.isalpha() or x.isspace() for x in username):
                break
            else:
                username = str(input("Please enter a valid name: "))
               
        except ValueError:
            print("Please enter a valid name! Try again.")
    emailid = str(input("Enter the email address: "))
    while True:
        if check(emailid):
            break
        else:
            emailid = str(input("Enter a valid email address: "))
            check(emailid)
            continue
    dashboard = meraki.DashboardAPI(
        api_key=API_KEY,
        base_url='https://api.meraki.com/api/v1/',
        output_log=False,
        log_file_prefix=os.path.basename(__file__)[:-3],
        log_path='',
        print_console=False
    )
    organizations = dashboard.organizations.getOrganizations()
    
    # Iterate through list of orgs
    for org in organizations:
        org_id = org['id']
        org_name = org['name']
        # Get list of networks in organization
        try:
            dashboard.organizations.createOrganizationAdmin(org_id, emailid, username, 'full')
            print('Admin %s has been created successfully in %s' %(username, org_name))
        except meraki.APIError as e:
            if(e.status == 400):
                print(f'Email has already in Use')
        except Exception as e:
            print(f'some other error: {e}')

def deleteadmin():
    emailid = str(input("Enter the email address of the admin to be deleted: "))
    while True:
        if check(emailid):
            break
        else:
            emailid = str(input("Enter a valid email address: "))
            check(emailid)
            continue
    dashboard = meraki.DashboardAPI(
        api_key=API_KEY,
        base_url='https://api.meraki.com/api/v1/',
        output_log=False,
        log_file_prefix=os.path.basename(__file__)[:-3],
        log_path='',
        print_console=False
    )
    organizations = dashboard.organizations.getOrganizations()
    # Iterate through list of orgs
    for org in organizations:
        org_id = org['id']
        # Get list of networks in organization
        try:
            admins = dashboard.organizations.getOrganizationAdmins(org_id)
            for admin in admins:
                if((admin['email'].lower()) == emailid.lower()):
                    admin_id = admin['id']
                    dashboard.organizations.deleteOrganizationAdmin(org_id, admin_id)
                    print('Admin %s has been deleted successfully from %s' %(admin['name'], org['name']))  
        except meraki.APIError as e:
            print(f'Meraki API error: {e}')
            print(f'status code = {e.status}')
            print(f'reason = {e.reason}')
            print(f'error = {e.message}')
        except Exception as e:
            print(f'some other error: {e}')
                
if __name__ == '__main__':
    while True:
        print(
            '''
1. Create Admin User across all organizations
2. Remove Admin User across all organizations
            '''
        )
        try:
            answer = int(input("What do you want to do? "))
        except ValueError:
            print("Not an integer! Try again.")
            continue
        if answer == 1:
            createadmin()
            break
        elif answer == 2:
            deleteadmin()
            break
        else:
            print("Please enter a valid option")

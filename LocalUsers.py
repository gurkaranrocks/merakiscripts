import re
import meraki
import os
import requests
regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
API_KEY = 'ENTER API KEY HERE'
emailid = ""
username = ""

def check(email):
    # pass the regular expression
    # and the string into the fullmatch() method
    if (re.fullmatch(regex, email)):
        return True
    else:
        return False

def getuserdetails():
    while True:
        try:
            global username
            username = str(input("Name of the Administrator to be created: "))
        except ValueError:
            print("Please enter a valid name! Try again.")
            continue
        while True:
            global emailid
            emailid = str(input("Enter the email address: "))
            if check(emailid):
                break
            else:
                print("Enter a Valid email")
                continue
        break


def deleteuser():
        print("Sorry not implemented yet")
        exit(0)
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
            getuserdetails()
            break
        elif answer == 2:
            deleteuser()
            break
        else:
            print("Please enter a valid option")
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
            dashboard.organizations.createOrganizationAdmin(org_id, emailid, username, 'full')
            print('Admin %s has been created successfully' % username)
        except meraki.APIError as e:
            print(f'Meraki API error: {e}')
            print(f'status code = {e.status}')
            print(f'reason = {e.reason}')
            print(f'error = {e.message}')
            continue
        except Exception as e:
            print(f'some other error: {e}')
            continue

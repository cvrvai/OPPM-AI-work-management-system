import requests
import json

# Login to get fresh token
login_res = requests.post(
    'http://localhost:8000/api/auth/login',
    json={'email': 'choonvai@gmail.com', 'password': '12345678'}
)
print(f'Login status: {login_res.status_code}')
if login_res.status_code == 200:
    data = login_res.json()
    token = data.get('access_token')
    print(f'Token: {token[:50]}...' if token else 'No token')
    
    # Test workspaces API
    ws_res = requests.get(
        'http://localhost:8000/api/v1/workspaces',
        headers={'Authorization': f'Bearer {token}'}
    )
    print(f'Workspaces status: {ws_res.status_code}')
    print(f'Workspaces response: {ws_res.text[:200]}')
    
    # Test scaffold API
    scaffold_res = requests.get(
        'http://localhost:8000/api/v1/workspaces/4cb12b24-daca-4c05-8ebd-75eb58e16bd1/projects/479ba1f2-4702-48d5-abe1-5b1ec182cf66/oppm/scaffold',
        headers={'Authorization': f'Bearer {token}'}
    )
    print(f'Scaffold status: {scaffold_res.status_code}')
    if scaffold_res.status_code == 200:
        scaffold_data = scaffold_res.json()
        print(f'Scaffold source: {scaffold_data.get("source")}')
        sheet_data = scaffold_data.get('sheet_data', [])
        print(f'Sheet data length: {len(sheet_data)}')
        if sheet_data:
            first_sheet = sheet_data[0]
            print(f'First sheet name: {first_sheet.get("name")}')
            print(f'First sheet row count: {len(first_sheet.get("data", []))}')
    else:
        print(f'Scaffold error: {scaffold_res.text[:200]}')
else:
    print(f'Login error: {login_res.text[:200]}')

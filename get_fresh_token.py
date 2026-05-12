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
    refresh = data.get('refresh_token')
    print(f'Access token: {token}')
    print(f'Refresh token: {refresh[:50]}...' if refresh else 'No refresh token')
    
    # Save to file for browser injection
    with open('fresh_token.json', 'w') as f:
        json.dump(data, f)
    print('Token saved to fresh_token.json')
    
    # Test workspaces API
    ws_res = requests.get(
        'http://localhost:8000/api/v1/workspaces',
        headers={'Authorization': f'Bearer {token}'}
    )
    print(f'Workspaces status: {ws_res.status_code}')
    print(f'Workspaces: {ws_res.text[:200]}')
else:
    print(f'Login error: {login_res.text}')

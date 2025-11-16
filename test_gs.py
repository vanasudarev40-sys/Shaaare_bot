import os
import json
import gspread
from google.oauth2.service_account import Credentials

GSHEET_ID = os.environ.get('GSHEET_ID')

def get_client():
    creds_json = os.environ.get('GS_CREDS_JSON')
    creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    try:
        if creds_json:
            info = json.loads(creds_json)
            creds = Credentials.from_service_account_info(info, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        elif creds_path and os.path.exists(creds_path):
            creds = Credentials.from_service_account_file(creds_path, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        else:
            print('No credentials found. Set GS_CREDS_JSON or GOOGLE_APPLICATION_CREDENTIALS')
            return None
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        print('Failed to create gspread client:', e)
        return None

def test_append():
    if not GSHEET_ID:
        print('GSHEET_ID not set. Set environment variable GSHEET_ID to your spreadsheet id.')
        return 2
    client = get_client()
    if not client:
        return 3
    try:
        sh = client.open_by_key(GSHEET_ID)
    except Exception as e:
        print('Failed to open spreadsheet:', e)
        return 4
    try:
        try:
            ws = sh.worksheet('Test')
        except Exception:
            ws = sh.add_worksheet(title='Test', rows=100, cols=10)
        row = ['test', 'python', 'gspread', str(os.getpid())]
        ws.append_row(row, value_input_option='USER_ENTERED')
        print('Appended test row to sheet: Test')
        return 0
    except Exception as e:
        print('Failed to append row:', e)
        return 5

if __name__ == '__main__':
    exit_code = test_append()
    exit(exit_code)

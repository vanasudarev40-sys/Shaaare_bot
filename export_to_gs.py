import os
import json
import sys
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

GSHEET_ID = os.environ.get('GSHEET_ID')
DATA_FILE = os.path.join(os.path.dirname(__file__), 'data.json')

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

def ensure_sheet(sh, title, headers):
    try:
        try:
            ws = sh.worksheet(title)
        except Exception:
            ws = sh.add_worksheet(title=title, rows=1000, cols=max(10, len(headers)))
        # add header if first row empty
        try:
            first = ws.row_values(1)
            if not first:
                ws.insert_row(headers, index=1)
        except Exception:
            pass
        return ws
    except Exception as e:
        print(f'Failed to ensure worksheet {title}:', e)
        return None

def export_all(dry_run=False):
    if not GSHEET_ID:
        print('GSHEET_ID not set. Set GSHEET_ID env var to your spreadsheet id.')
        return 2
    client = get_client()
    if not client:
        return 3
    try:
        sh = client.open_by_key(GSHEET_ID)
    except Exception as e:
        print('Failed to open spreadsheet:', e)
        return 4

    # load data.json
    if not os.path.exists(DATA_FILE):
        print('data.json not found at', DATA_FILE)
        return 5
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    bookings_ws = ensure_sheet(sh, 'Bookings', ['exported_at', 'user_id', 'username', 'spec', 'date', 'time'])
    messages_ws = ensure_sheet(sh, 'Messages', ['exported_at', 'msg_id', 'from_id', 'from_username', 'tag', 'spec', 'text'])

    b_count = 0
    m_count = 0

    # Export bookings
    recs_all = data.get('records', {})
    for uid, recs in recs_all.items():
        for r in recs:
            row = [datetime.now().isoformat(), uid, r.get('username'), r.get('spec'), r.get('date'), r.get('time')]
            if dry_run:
                b_count += 1
                continue
            try:
                bookings_ws.append_row(row, value_input_option='USER_ENTERED')
                b_count += 1
            except Exception as e:
                print('Failed to append booking row:', e)

    # Export messages
    msgs = data.get('messages', [])
    for m in msgs:
        row = [datetime.now().isoformat(), m.get('id'), m.get('from_id'), m.get('from_username'), m.get('tag'), m.get('spec', ''), m.get('text')]
        if dry_run:
            m_count += 1
            continue
        try:
            messages_ws.append_row(row, value_input_option='USER_ENTERED')
            m_count += 1
        except Exception as e:
            print('Failed to append message row:', e)

    print(f'Export completed. Bookings appended: {b_count}, Messages appended: {m_count}')
    return 0

if __name__ == '__main__':
    dry = False
    if len(sys.argv) > 1 and sys.argv[1] in ('--dry', '-n'):
        dry = True
    code = export_all(dry_run=dry)
    sys.exit(code)

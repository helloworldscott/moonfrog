import os
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
from datetime import datetime, timedelta
import logging

# Load environment variables
load_dotenv()

# Fetch environment variables
secret_key = os.getenv('IRONSOURCE_SECRET_KEY')
refresh_token = os.getenv('IRONSOURCE_REFRESH_TOKEN')
sheet_id = os.getenv('GOOGLE_SHEET_ID')
credentials_file = 'WaterfallBot/google-credentials.json'
app_key_ios = os.getenv('IRONSOURCE_APP_KEY_IOS')
app_key_android = os.getenv('IRONSOURCE_APP_KEY_ANDROID')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Calculate dates
yesterday = datetime.now() - timedelta(days=1)
yesterday_str = yesterday.strftime("%Y-%m-%d")

# Function to get Bearer Token with GET request
def get_bearer_token():
    try:
        url = "https://platform.ironsrc.com/partners/publisher/auth"
        headers = {
            "secretKey": secret_key,
            "refreshToken": refresh_token
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an error if the request fails
        return response.text.strip('"')  # Extract and return the Bearer token
    except requests.RequestException as e:
        logging.error(f"Failed to get Bearer Token: {e}")
        raise

# Fetch data from IronSource API with the correct field names
def fetch_ironsource_data(app_key, start_date, end_date):
    try:
        bearer_token = get_bearer_token()
        url = f"https://platform.ironsrc.com/partners/publisher/mediation/applications/v6/stats"
        headers = {"Authorization": f"Bearer {bearer_token}"}
        
        params = {
            "startDate": start_date,
            "endDate": end_date,
            "breakdowns": "date,adSource,instance,app,adUnits",
            "metrics": "revenue,eCPM,impressions,adSourceAvailabilityRate",
            "appKey": app_key
        }
        
        logging.info(f"Fetching data for {app_key} from {start_date} to {end_date} with params: {params}")
        
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        return response.json()  # Return the JSON response
    except requests.RequestException as e:
        logging.error(f"Failed to fetch data for appKey {app_key} from {start_date} to {end_date}: {e}")
        return []

# Function to find the next available row in Google Sheets
def find_next_available_row(sheet):
    str_list = list(filter(None, sheet.col_values(2)))  # Assuming Column 2 (B) is always populated with Date values
    return len(str_list) + 1  # Return the next empty row

# Fill Google Sheets with IronSource data for both iOS and Android using batch updates
def fill_google_sheets(sheet, ironsource_data_ios, ironsource_data_android):
    # Clear the range B1:J to remove any previous data
    sheet.update('B1:J', [['' for _ in range(9)] for _ in range(sheet.row_count)])  # Clear the content of range B1:J

    # Insert the header row in B1:J1
    header = ["Date", "Ad Source", "Instance", "App Name", "Ad Unit", "Revenue", "eCPM", "Impressions", "Availability Rate"]
    sheet.update('B1:J1', [header])
    
    # Prepare data for batch update
    batch_data = []
    
    # Prepare iOS data
    for item in ironsource_data_ios:
        for data in item.get('data', []):  # Ensure 'data' field exists
            batch_data.append([
                item.get('date', ''),                        # Date in Column B
                item.get('providerName', ''),                # Ad Source in Column C
                item.get('instanceName', ''),                # Instance in Column D
                item.get('appName', ''),                     # App Name in Column E
                item.get('adUnits', ''),                     # Ad Unit in Column F
                data.get('revenue', 0),                      # Revenue in Column G
                data.get('eCPM', 0),                         # eCPM in Column H
                data.get('impressions', 0),                  # Impressions in Column I
                data.get('adSourceAvailabilityRate', 0)      # Availability Rate in Column J
            ])
    
    # Prepare Android data
    for item in ironsource_data_android:
        for data in item.get('data', []):  # Ensure 'data' field exists
            batch_data.append([
                item.get('date', ''),                        # Date in Column B
                item.get('providerName', ''),                # Ad Source in Column C
                item.get('instanceName', ''),                # Instance in Column D
                item.get('appName', ''),                     # App Name in Column E
                item.get('adUnits', ''),                     # Ad Unit in Column F
                data.get('revenue', 0),                      # Revenue in Column G
                data.get('eCPM', 0),                         # eCPM in Column H
                data.get('impressions', 0),                  # Impressions in Column I
                data.get('adSourceAvailabilityRate', 0)      # Availability Rate in Column J
            ])
    
    # Batch update the sheet starting from B2:J
    if batch_data:
        sheet.update(f'B2:J{1 + len(batch_data)}', batch_data)


# Setup Google Sheets API
def setup_google_sheets(sheet_id, credentials_file):
    scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
    client = gspread.authorize(creds)
    return client.open_by_key(sheet_id).worksheet('Placement Fill Rate')  # Open specific tab

# Main function to automate the process for both iOS and Android
def main():
    # Fetch IronSource data for yesterday
    start_date = yesterday_str
    end_date = start_date
    
    # Fetch iOS data
    ironsource_data_ios = fetch_ironsource_data(app_key_ios, start_date, end_date)
    logging.info(f"iOS Data: {ironsource_data_ios}")  # Log fetched iOS data
    
    # Fetch Android data
    ironsource_data_android = fetch_ironsource_data(app_key_android, start_date, end_date)
    logging.info(f"Android Data: {ironsource_data_android}")  # Log fetched Android data
    
    if ironsource_data_ios and ironsource_data_android:
        # Google Sheets setup
        gather_sheet = setup_google_sheets(sheet_id, credentials_file)
        
        # Fill Google Sheets with IronSource data for both iOS and Android
        fill_google_sheets(gather_sheet, ironsource_data_ios, ironsource_data_android)
    else:
        logging.warning("No data to insert into Google Sheets")


if __name__ == "__main__":
    main()

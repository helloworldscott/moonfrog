import os
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
from datetime import datetime, timedelta
import logging

# Load environment variables from .env file
load_dotenv()

# Fetch environment variables
secret_key = os.getenv('IRONSOURCE_SECRET_KEY')
refresh_token = os.getenv('IRONSOURCE_REFRESH_TOKEN')
sheet_id = os.getenv('GOOGLE_SHEET_DAILY_ID')
credentials_file = 'WaterfallBot/google-credentials.json'
app_key_ios = os.getenv('IRONSOURCE_APP_KEY_IOS')
app_key_android = os.getenv('IRONSOURCE_APP_KEY_ANDROID')
sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"

# Path to the summary file in the Summary folder
summary_file_path = 'Summary/summary.txt'

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Function to get Bearer Token with GET request
def get_bearer_token():
    try:
        url = "https://platform.ironsrc.com/partners/publisher/auth"
        headers = {
            "secretKey": secret_key,
            "refreshToken": refresh_token
        }
        
        # Request token from IronSource
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an error if the request fails
        bearer_token = response.text.strip('"')  # Extract and return the Bearer token
        logging.info("Successfully retrieved Bearer token.")
        return bearer_token
    except requests.RequestException as e:
        logging.error(f"Failed to get Bearer Token: {e}")
        raise

# Function to connect to Google Sheets
def connect_to_google_sheets(sheet_id, credentials_file):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(sheet_id)
        logging.info("Successfully connected to Google Sheets.")
        return sheet
    except Exception as e:
        logging.error(f"Failed to connect to Google Sheets: {e}")
        raise

# Function to fetch date from M1 in "Raw Data" tab
def get_date_from_sheet(sheet):
    try:
        worksheet = sheet.worksheet("Raw Data")
        date_str = worksheet.acell('M1').value
        
        # Check if the cell is empty
        if not date_str:
            raise ValueError("Cell M1 is empty.")
        
        # Try parsing the date in MM/DD/YYYY format
        try:
            date_m1 = datetime.strptime(date_str, "%m/%d/%Y").date()
            logging.info(f"Retrieved date from cell M1: {date_m1}")
            return date_m1
        except ValueError:
            raise ValueError(f"Failed to parse date from M1: {date_str} (expected format MM/DD/YYYY)")
    except gspread.exceptions.WorksheetNotFound:
        logging.error(f"Worksheet 'Raw Data' not found.")
        raise
    except Exception as e:
        logging.error(f"Failed to retrieve date from sheet: {e}")
        raise

# Function to pull data from IronSource API
def fetch_ironsource_data(app_key, start_date, end_date):
    try:
        bearer_token = get_bearer_token()
        url = f"https://platform.ironsrc.com/partners/publisher/mediation/applications/v6/stats"
        
        params = {
            'startDate': start_date,
            'endDate': end_date,
            'appKey': app_key,
            'metrics': 'revenue,eCPM,appFillRate,appRequests,impressions,activeUsers,engagedUsers,revenuePerActiveUser,revenuePerEngagedUser',
            'breakdowns': 'date,app'
        }
        
        headers = {"Authorization": f"Bearer {bearer_token}"}
        
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()  # Raise an error if the request fails
        data = response.json()
        
        logging.info(f"Data returned for app key {app_key}: {data}")
        return data
    except requests.RequestException as e:
        logging.error(f"Failed to fetch IronSource data: {e}")
        raise

# Function to insert data into Google Sheets
def insert_data_to_sheet(worksheet, data, platform_name):
    try:
        next_row = len(worksheet.get_all_values()) + 1  # Get the next available row

        # Iterate over the list of data entries
        for entry in data:
            date_str = entry.get('date', '').strip("'")  # Ensure no single quotes

            # Convert date to the desired YYYY-MM-DD format
            try:
                date_formatted = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
            except ValueError:
                logging.error(f"Date format is incorrect for {date_str}. Skipping.")
                continue  # Skip this entry if the date format is incorrect

            metrics = entry.get('data', {})
            if isinstance(metrics, list):  # If 'data' is a list, iterate over its items
                for metric in metrics:
                    formatted_row = [
                        date_formatted,  # Properly formatted date
                        f"{entry.get('appName', '')} ({platform_name})".replace(f"({platform_name}) ({platform_name})", f"({platform_name})"),  # Ensure no double platform tag
                        metric.get('revenue', 0),
                        metric.get('eCPM', 0),
                        metric.get('appFillRate', 0),
                        metric.get('appRequests', 0),
                        metric.get('impressions', 0),
                        metric.get('activeUsers', 0),  # DAU
                        metric.get('engagedUsers', 0),  # DEU
                        metric.get('revenuePerActiveUser', 0),  # ARPDAU
                        metric.get('revenuePerEngagedUser', 0)  # ARPDEU
                    ]
                    
                    # Insert row into Google Sheets with USER_ENTERED option to treat date as a date
                    worksheet.append_row(formatted_row, value_input_option="USER_ENTERED")
                    next_row += 1  # Move to the next row
            else:
                logging.warning(f"Unexpected format for 'data' in entry: {entry}")

        logging.info(f"Data successfully inserted for {platform_name}")
    except Exception as e:
        logging.error(f"Failed to insert data to sheet: {e}")
        raise

# Main execution flow with summary and error logging
if __name__ == '__main__':
    try:
        # Connect to Google Sheets
        sheet = connect_to_google_sheets(sheet_id, credentials_file)
        
        # Get the date from M1
        m1_date = get_date_from_sheet(sheet)

        # Calculate the date range: Start from the day after M1's date until yesterday
        start_date = m1_date + timedelta(days=1)
        yesterday = datetime.now().date() - timedelta(days=1)

        # If start_date is after yesterday, log that the data is already up to date
        if start_date > yesterday:
            logging.info(f"Data is already up to date until {yesterday}. No new data to fetch.")
        else:
            # Format dates to YYYY-MM-DD for the API request
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = yesterday.strftime('%Y-%m-%d')

            # Fetch iOS and Android data from IronSource
            ios_data = fetch_ironsource_data(app_key_ios, start_date_str, end_date_str)
            android_data = fetch_ironsource_data(app_key_android, start_date_str, end_date_str)

            # Insert data into the Google Sheet
            worksheet = sheet.worksheet("Raw Data")
            insert_data_to_sheet(worksheet, ios_data, "iOS")
            insert_data_to_sheet(worksheet, android_data, "Android")

            # Generate the summary for this script with a single hyperlink
            summary = f"<{sheet_url}|Performance>"

            # Append the summary to the Summary/summary.txt file without duplicate "Performance"
            with open(summary_file_path, 'a') as file:
                file.write(summary + '\n')

    except Exception as e:
        error_message = f"Error in dailyrev.py: {str(e)}"
        logging.error(error_message)
        
        # Log the error in the Summary/summary.txt file
        with open(summary_file_path, 'a') as file:
            file.write(f"{error_message}\n")

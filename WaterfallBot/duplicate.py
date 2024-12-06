import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from googleapiclient.discovery import build
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

# Fetch environment variables
sheet_id = os.getenv('GOOGLE_SHEET_BLANK_WATERFALL_ID')  # The ID of the sheet you want to copy
credentials_file = 'WaterfallBot/google-credentials.json'
slack_token = os.getenv('SLACK_API_TOKEN')  # Slack Bot Token
slack_channel = os.getenv('SLACK_CHANNEL_ID')  # Slack Channel ID
share_emails = os.getenv('SHARE_EMAILS').split(',')  # Comma-separated emails to share the sheet with

# Setup Google Sheets API
def setup_google_sheets(credentials_file):
    scope = ["https://www.googleapis.com/auth/drive", "https://spreadsheets.google.com/feeds"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
    return build('drive', 'v3', credentials=creds)

# Copy entire Google Sheet as a new document
def copy_google_sheet():
    # Get the current date for naming the copied sheet
    today_str = datetime.now().strftime("%-m/%-d")  # Format like '9/12'
    new_sheet_name = f'{today_str} - Waterfalls'

    # Setup Google Sheets API
    drive_service = setup_google_sheets(credentials_file)

    # Make a copy of the file
    copy_body = {'name': new_sheet_name}
    copied_file = drive_service.files().copy(fileId=sheet_id, body=copy_body).execute()

    # Share the file with the specified emails
    for email in share_emails:
        permission_body = {
            'type': 'user',
            'role': 'writer',
            'emailAddress': email
        }
        drive_service.permissions().create(
            fileId=copied_file['id'],
            body=permission_body,
            fields='id',
            sendNotificationEmail=False  # Don't send notification emails
        ).execute()

    print(f"Copied and renamed sheet to '{new_sheet_name}' with new file ID: {copied_file['id']}")

    # Return the link to the copied file and the name for Slack
    return f"https://docs.google.com/spreadsheets/d/{copied_file['id']}/edit", new_sheet_name

# Function to send a message to Slack with the sheet link and sheet name
def send_message_to_slack(sheet_link, sheet_name, error_message=None):
    # If there is an error, include it in the message
    if error_message:
        message = f"{sheet_name}: <{sheet_link}|{sheet_name}> \nError: {error_message}"
    else:
        message = f"<{sheet_link}|{sheet_name}>"  # Hyperlink with the sheet_name as the display text

    # Send the message to Slack
    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Authorization": f"Bearer {slack_token}",
        "Content-Type": "application/json"
    }
    data = {
        "channel": slack_channel,
        "text": message
    }
    
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        print("Message sent successfully to Slack")
    else:
        print(f"Failed to send message: {response.status_code}, {response.text}")

# Main function to copy the sheet and send the link to Slack
def main():
    try:
        # Copy Google Sheet and get the link
        sheet_link, sheet_name = copy_google_sheet()

        # Send the simple "date - Waterfalls" message to Slack
        send_message_to_slack(sheet_link, sheet_name)

    except Exception as e:
        error_message = f"Error in duplicate.py: {str(e)}"
        print(error_message)

        # Send the error message to Slack
        send_message_to_slack(sheet_link, sheet_name, error_message)

if __name__ == "__main__":
    main()

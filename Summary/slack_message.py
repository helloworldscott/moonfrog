import os
import requests

# Load environment variables
slack_token = os.getenv('SLACK_API_TOKEN')
slack_channel = os.getenv('SLACK_CHANNEL_ID')

# Path to summary.txt in the Summary folder
summary_file_path = 'Summary/summary.txt'

# Function to send the message to Slack
def send_slack_message(message):
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

# Read the content from summary.txt or create the file if missing
def read_summary():
    if not os.path.exists(summary_file_path):
        with open(summary_file_path, 'w') as file:
            file.write("No summary available yet.\n")
    with open(summary_file_path, 'r') as file:
        return file.read()

# Main function to send the message
if __name__ == "__main__":
    summary_message = read_summary()
    send_slack_message(summary_message)

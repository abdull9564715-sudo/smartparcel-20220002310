import json
import boto3

# Create SNS client
sns = boto3.client('sns', region_name='ap-southeast-2')

# Correct SNS Topic ARN my ID 
TOPIC_ARN = "arn:aws:sns:ap-southeast-2:230195035124:smartparcel-alerts-20220002310"

def lambda_handler(event, context):
    for record in event['Records']:
        try:
            # Read message from SQS
            body = json.loads(record['body'])
        except Exception:
            body = {}

        # Extract data safely
        parcel_id = body.get('parcel_id', 'N/A')
        status = body.get('new_status', 'N/A')
        email = body.get('customer_email', 'N/A')
        timestamp = body.get('timestamp', 'N/A')

        # Create message
        message = f"""
🚚 SmartParcel Update

Parcel ID: {parcel_id}
Status: {status}
Time: {timestamp}
"""

        try:
            # Send notification via SNS
            sns.publish(
                TopicArn=TOPIC_ARN,
                Message=message,
                Subject="SmartParcel Update"
            )
        except Exception as e:
            print(f"Error sending notification: {str(e)}")

    return {
        'statusCode': 200,
        'body': 'Notifications sent successfully'
    }

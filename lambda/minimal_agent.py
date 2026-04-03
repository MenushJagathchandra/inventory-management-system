#!/usr/bin/env python3
"""
Minimal Lambda function for inventory management
"""

import json
import boto3
import os
from datetime import datetime

def lambda_handler(event, context):
    """Lambda handler for inventory processing"""
    
    try:
        print(f"Received event: {json.dumps(event)}")
        
        # Get bucket and key from S3 event
        if 'Records' in event:
            for record in event['Records']:
                bucket = record['s3']['bucket']['name']
                key = record['s3']['object']['key']
                
                print(f"Processing file: {key} from bucket: {bucket}")
                
                # Initialize AWS clients
                s3_client = boto3.client('s3')
                dynamodb = boto3.resource('dynamodb')
                
                # Read CSV file from S3
                response = s3_client.get_object(Bucket=bucket, Key=key)
                csv_content = response['Body'].read().decode('utf-8')
                
                # Simple CSV processing
                lines = csv_content.strip().split('\n')
                headers = lines[0].split(',')
                data_rows = lines[1:]
                
                # Simple analysis
                total_items = len(data_rows)
                processed_count = 0
                
                for row in data_rows:
                    if row.strip():
                        processed_count += 1
                
                # Save to DynamoDB
                table = dynamodb.Table(os.environ['DYNAMO_TABLE'])
                report_id = f"report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
                
                table.put_item(Item={
                    'report_id': report_id,
                    'timestamp': datetime.utcnow().isoformat(),
                    'source_file': key,
                    'total_items': total_items,
                    'processed_items': processed_count,
                    'status': 'completed'
                })
                
                print(f"Successfully processed {processed_count} items from {key}")
                
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': f'Successfully processed {key}',
                        'report_id': report_id,
                        'total_items': total_items,
                        'processed_items': processed_count
                    })
                }
        
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'No S3 records found'})
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

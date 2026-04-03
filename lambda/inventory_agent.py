import json
import os
import uuid
import boto3
import pandas as pd
import logging
from datetime import datetime, timezone
from io import StringIO, BytesIO
from typing import Dict, Any, Optional

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Set matplotlib backend for Lambda
import matplotlib
matplotlib.use('Agg')

# Import our modules
from data_cleaner import clean, validate_with_pydantic
from analyzer import analyze
from chart_generator import generate_comprehensive_charts

# AWS clients
s3 = boto3.client('s3')
dynamo = boto3.resource('dynamodb').Table(os.environ['DYNAMO_TABLE'])
sns = boto3.client('sns')
cloudwatch = boto3.client('cloudwatch')
sqs = boto3.client('sqs')

# Environment variables
OUTPUT_BUCKET = os.environ['OUTPUT_BUCKET']
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']
DLQ_URL = os.environ.get('DLQ_URL')  # Dead Letter Queue

def lambda_handler(event, context):
    """
    Enhanced Lambda handler with industry features:
    - Idempotency control
    - Comprehensive error handling
    - CloudWatch metrics
    - Dead Letter Queue support
    - Detailed logging
    """
    
    request_id = str(uuid.uuid4())
    start_time = datetime.now(timezone.utc)
    
    logger.info(f"Request {request_id}: Processing started")
    
    try:
        # Extract S3 event data
        record = event['Records'][0]
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        etag = record['s3']['object']['eTag']
        
        logger.info(f"Request {request_id}: Processing file {key} from bucket {bucket}")
        
        # 1. IDEMPOTENCY CHECK - Prevent duplicate processing
        if is_duplicate_processing(key, etag):
            logger.info(f"Request {request_id}: Duplicate file detected, skipping")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'File already processed',
                    'request_id': request_id
                })
            }
        
        # 2. INPUT VALIDATION
        if not key.endswith('.csv'):
            raise ValueError(f"Invalid file type: {key}. Only CSV files are supported")
        
        # 3. LOAD CSV DATA
        df, file_info = load_csv_from_s3(bucket, key)
        logger.info(f"Request {request_id}: Loaded {len(df)} rows from CSV")
        
        # 4. DATA CLEANING AND VALIDATION
        df_cleaned, cleaning_issues = clean(df)
        
        # Additional Pydantic validation
        is_valid, validation_errors = validate_with_pydantic(df_cleaned)
        if not is_valid:
            error_msg = f"Data validation failed: {validation_errors}"
            logger.error(f"Request {request_id}: {error_msg}")
            raise ValueError(error_msg)
        
        logger.info(f"Request {request_id}: Data cleaning completed. Issues: {cleaning_issues}")
        
        # 5. BUSINESS ANALYSIS
        analysis_results = analyze(df_cleaned)
        logger.info(f"Request {request_id}: Analysis completed")
        
        # 6. CHART GENERATION
        chart_metadata = generate_and_upload_charts(df_cleaned, analysis_results, key)
        logger.info(f"Request {request_id}: Charts generated and uploaded")
        
        # 7. STORE REPORT IN DYNAMODB
        report_id = store_report(
            request_id=request_id,
            source_file=key,
            file_info=file_info,
            analysis_results=analysis_results,
            chart_metadata=chart_metadata,
            cleaning_issues=cleaning_issues
        )
        
        # 8. SEND ALERTS IF NEEDED
        if analysis_results['summary_metrics']['low_stock_count'] > 0:
            send_alert(analysis_results, report_id, request_id)
            logger.info(f"Request {request_id}: Low stock alerts sent")
        
        # 9. PUBLISH CLOUDWATCH METRICS
        publish_cloudwatch_metrics(analysis_results, request_id)
        
        # 10. LOG PROCESSING SUMMARY
        processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.info(f"Request {request_id}: Processing completed in {processing_time:.2f} seconds")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Inventory analysis completed successfully',
                'report_id': report_id,
                'request_id': request_id,
                'processing_time_seconds': processing_time,
                'total_items_processed': len(df_cleaned),
                'low_stock_alerts': analysis_results['summary_metrics']['low_stock_count'],
                'charts_generated': len(chart_metadata)
            })
        }
        
    except Exception as e:
        error_msg = f"Processing failed: {str(e)}"
        logger.error(f"Request {request_id}: {error_msg}")
        
        # Send to Dead Letter Queue if configured
        if DLQ_URL:
            send_to_dlq(event, str(e), request_id)
        
        # Publish error metric
        try:
            cloudwatch.put_metric_data(
                Namespace='InventoryAgent',
                MetricData=[{
                    'MetricName': 'ProcessingErrors',
                    'Value': 1,
                    'Unit': 'Count',
                    'Timestamp': datetime.now(timezone.utc)
                }]
            )
        except Exception as metric_error:
            logger.error(f"Failed to publish error metric: {str(metric_error)}")
        
        raise

def is_duplicate_processing(file_key: str, etag: str) -> bool:
    """
    Check if file has already been processed using DynamoDB
    Implements idempotency to prevent duplicate processing
    """
    try:
        response = dynamo.query(
            IndexName='source_file_index',  # You'll need to create this GSI
            KeyConditionExpression=boto3.dynamodb.conditions.Key('source_file').eq(file_key),
            ProjectionExpression='file_etag, processed_at',
            Limit=1
        )
        
        if response['Items']:
            existing_record = response['Items'][0]
            if existing_record.get('file_etag') == etag:
                logger.info(f"File {file_key} with etag {etag} already processed at {existing_record.get('processed_at')}")
                return True
        
        return False
        
    except Exception as e:
        logger.warning(f"Failed to check for duplicate processing: {str(e)}")
        # If we can't check, proceed with processing (better than missing data)
        return False

def load_csv_from_s3(bucket: str, key: str) -> tuple[pd.DataFrame, Dict]:
    """Load CSV from S3 with comprehensive error handling"""
    
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        content = obj['Body'].read().decode('utf-8')
        
        # Get file metadata
        file_info = {
            'size_bytes': obj.get('ContentLength', 0),
            'last_modified': obj.get('LastModified', '').isoformat() if obj.get('LastModified') else '',
            'content_type': obj.get('ContentType', ''),
            'etag': obj.get('ETag', '').strip('"')
        }
        
        # Parse CSV
        df = pd.read_csv(StringIO(content))
        
        # Validate basic structure
        if df.empty:
            raise ValueError("CSV file is empty")
        
        return df, file_info
        
    except UnicodeDecodeError:
        raise ValueError("File encoding error. Please ensure CSV is UTF-8 encoded")
    except pd.errors.EmptyDataError:
        raise ValueError("CSV file has no data")
    except pd.errors.ParserError as e:
        raise ValueError(f"CSV parsing error: {str(e)}")
    except Exception as e:
        raise ValueError(f"Failed to load CSV from S3: {str(e)}")

def generate_and_upload_charts(df: pd.DataFrame, analysis_results: Dict, source_key: str) -> Dict[str, Dict]:
    """Generate charts and upload to S3 with metadata"""
    
    try:
        # Generate all charts
        charts = generate_comprehensive_charts(df, analysis_results)
        
        chart_metadata = {}
        base_filename = source_key.replace('.csv', '')
        
        for chart_name, chart_buffer in charts.items():
            # Generate unique chart key
            chart_key = f"charts/{base_filename}-{chart_name}-{uuid.uuid4().hex[:8]}.png"
            
            # Upload to S3
            s3.put_object(
                Bucket=OUTPUT_BUCKET,
                Key=chart_key,
                Body=chart_buffer.getvalue(),
                ContentType='image/png',
                Metadata={
                    'chart_type': chart_name,
                    'source_file': source_key,
                    'generated_at': datetime.now(timezone.utc).isoformat()
                }
            )
            
            # Generate presigned URL (valid for 7 days)
            presigned_url = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': OUTPUT_BUCKET, 'Key': chart_key},
                ExpiresIn=7*24*3600  # 7 days
            )
            
            chart_metadata[chart_name] = {
                's3_key': chart_key,
                'presigned_url': presigned_url,
                'chart_type': chart_name,
                'generated_at': datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(f"Uploaded chart: {chart_key}")
        
        return chart_metadata
        
    except Exception as e:
        logger.error(f"Chart generation failed: {str(e)}")
        raise

def store_report(request_id: str, source_file: str, file_info: Dict, 
                analysis_results: Dict, chart_metadata: Dict, cleaning_issues: List[str]) -> str:
    """Store comprehensive report in DynamoDB"""
    
    report_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    
    try:
        item = {
            'report_id': report_id,
            'request_id': request_id,
            'processed_at': timestamp,
            'source_file': source_file,
            'file_info': json.dumps(file_info),
            
            # Analysis results
            'summary_metrics': json.dumps(analysis_results['summary_metrics']),
            'low_stock_items': json.dumps(analysis_results['low_stock_items']),
            'top_sellers': json.dumps(analysis_results['top_sellers']),
            'stockout_analysis': json.dumps(analysis_results['stockout_analysis']),
            'abc_analysis': json.dumps(analysis_results['abc_analysis']),
            'reorder_recommendations': json.dumps(analysis_results['reorder_recommendations']),
            'business_insights': json.dumps(analysis_results['business_insights']),
            'inventory_health': json.dumps(analysis_results['inventory_health']),
            
            # Chart metadata
            'chart_metadata': json.dumps(chart_metadata),
            
            # Processing metadata
            'cleaning_issues': json.dumps(cleaning_issues),
            'status': 'COMPLETED',
            'file_etag': json.loads(file_info).get('etag', '') if isinstance(file_info, str) else file_info.get('etag', '')
        }
        
        dynamo.put_item(Item=item)
        logger.info(f"Stored report {report_id} in DynamoDB")
        
        return report_id
        
    except Exception as e:
        logger.error(f"Failed to store report: {str(e)}")
        raise

def send_alert(analysis_results: Dict, report_id: str, request_id: str):
    """Send enhanced low stock alert via SNS"""
    
    try:
        low_stock_items = analysis_results['low_stock_items']
        critical_items = analysis_results['stockout_analysis']['critical']
        summary = analysis_results['summary_metrics']
        
        # Build alert message
        message_lines = [
            f"⚠️ INVENTORY ALERT - Report {report_id}",
            f"Request ID: {request_id}",
            f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            f"📊 SUMMARY:",
            f"• Total Items: {summary['total_items']}",
            f"• Low Stock Items: {summary['low_stock_count']}",
            f"• Critical Stockout Risk: {summary['critical_stockout_count']}",
            f"• Inventory Health Score: {summary['inventory_health_score']}/100",
            ""
        ]
        
        # Add critical items first
        if critical_items:
            message_lines.extend([
                "🚨 CRITICAL STOCKOUT RISK (Next 7 days):",
                *[f"  • {item['item_name']} — {item['days_until_stockout']} days remaining" 
                  for item in critical_items[:5]],
                ""
            ])
        
        # Add low stock items
        if low_stock_items:
            message_lines.extend([
                "⚠️ LOW STOCK ITEMS:",
                *[f"  • {item['item_name']} — Stock: {item['stock_level']}, Reorder at: {item['reorder_level']}" 
                  for item in low_stock_items[:10]],
                ""
            ])
        
        # Add business insights
        insights = analysis_results.get('business_insights', [])
        if insights:
            message_lines.extend([
                "💡 BUSINESS INSIGHTS:",
                *[f"  • {insight}" for insight in insights[:3]],
                ""
            ])
        
        # Add call to action
        message_lines.extend([
            "🔗 VIEW FULL REPORT:",
            f"Check your inventory dashboard for detailed charts and recommendations.",
            "",
            "This is an automated message from the AWS Inventory Management Agent."
        ])
        
        message = "\n".join(message_lines)
        
        # Send SNS notification
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"[Inventory Agent] Low Stock Alert - {summary['low_stock_count']} items need attention",
            Message=message,
            MessageAttributes={
                'report_id': {'DataType': 'String', 'StringValue': report_id},
                'urgency_level': {'DataType': 'String', 'StringValue': 'HIGH' if summary['critical_stockout_count'] > 0 else 'MEDIUM'}
            }
        )
        
        logger.info(f"Alert sent for report {report_id}")
        
    except Exception as e:
        logger.error(f"Failed to send alert: {str(e)}")
        # Don't raise - alert failure shouldn't fail the whole process

def publish_cloudwatch_metrics(analysis_results: Dict, request_id: str):
    """Publish business metrics to CloudWatch"""
    
    try:
        summary = analysis_results['summary_metrics']
        
        metrics = [
            {
                'MetricName': 'TotalItemsProcessed',
                'Value': summary['total_items'],
                'Unit': 'Count'
            },
            {
                'MetricName': 'LowStockItems',
                'Value': summary['low_stock_count'],
                'Unit': 'Count'
            },
            {
                'MetricName': 'CriticalStockoutItems',
                'Value': summary['critical_stockout_count'],
                'Unit': 'Count'
            },
            {
                'MetricName': 'InventoryHealthScore',
                'Value': summary['inventory_health_score'],
                'Unit': 'None'
            }
        ]
        
        # Add ABC analysis metrics
        abc_analysis = analysis_results.get('abc_analysis', {})
        if abc_analysis:
            abc_info = abc_analysis.get('analysis', {})
            metrics.extend([
                {
                    'MetricName': 'CategoryAItemCount',
                    'Value': abc_info.get('a_count', 0),
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'CategoryBItemCount',
                    'Value': abc_info.get('b_count', 0),
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'CategoryCItemCount',
                    'Value': abc_info.get('c_count', 0),
                    'Unit': 'Count'
                }
            ])
        
        cloudwatch.put_metric_data(
            Namespace='InventoryAgent',
            MetricData=metrics
        )
        
        logger.info(f"Published {len(metrics)} CloudWatch metrics")
        
    except Exception as e:
        logger.error(f"Failed to publish CloudWatch metrics: {str(e)}")

def send_to_dlq(event: Dict, error_message: str, request_id: str):
    """Send failed event to Dead Letter Queue"""
    
    try:
        dlq_message = {
            'request_id': request_id,
            'error_message': error_message,
            'failed_at': datetime.now(timezone.utc).isoformat(),
            'original_event': event
        }
        
        sqs.send_message(
            QueueUrl=DLQ_URL,
            MessageBody=json.dumps(dlq_message),
            MessageAttributes={
                'error_type': {'DataType': 'String', 'StringValue': 'ProcessingError'}
            }
        )
        
        logger.info(f"Sent failed request {request_id} to DLQ")
        
    except Exception as e:
        logger.error(f"Failed to send to DLQ: {str(e)}")

# Health check endpoint for monitoring
def health_check(event, context):
    """Simple health check for Lambda function"""
    
    try:
        # Test DynamoDB connection
        dynamo.describe_table(TableName=os.environ['DYNAMO_TABLE'])
        
        # Test S3 access
        s3.head_bucket(Bucket=OUTPUT_BUCKET)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'status': 'healthy',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'services': {
                    'dynamodb': 'connected',
                    's3': 'connected',
                    'sns': 'available'
                }
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 503,
            'body': json.dumps({
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        }

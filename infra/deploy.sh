#!/bin/bash

# AWS Inventory Management Agent - Lambda Deployment Script
# This script packages and deploys the Lambda function
# USAGE: ./deploy.sh your-unique-name

set -e  # Exit on any error

# Check if name argument is provided
if [ $# -eq 0 ]; then
    echo "❌ Error: Please provide the same unique name used in setup.sh"
    echo "Usage: ./deploy.sh your-name"
    exit 1
fi

YOUR_NAME=$1
REGION="us-east-1"

echo "🚀 Deploying Lambda function for: $YOUR_NAME"
echo "📍 Region: $REGION"
echo ""

# Get AWS Account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "🔑 AWS Account ID: $ACCOUNT_ID"

# Check if setup was completed
BUCKET_NAME="inventory-agent-uploads-$YOUR_NAME"
if ! aws s3 ls s3://$BUCKET_NAME &>/dev/null; then
    echo "❌ Error: Infrastructure not found. Please run ./setup.sh $YOUR_NAME first"
    exit 1
fi

# Get resource ARNs
TOPIC_ARN=$(aws sns list-topics --query "Topics[?contains(TopicArn, \`inventory-low-stock-alerts\`)].TopicArn" --output text | head -1)
DLQ_URL=$(aws sqs get-queue-url --queue-name inventory-agent-dlq --query 'QueueUrl' --output text)
ROLE_ARN="arn:aws:iam::$ACCOUNT_ID:role/lambda-inventory-role-$YOUR_NAME"

echo "📋 Resource Configuration:"
echo "• S3 Uploads Bucket: $BUCKET_NAME"
echo "• S3 Outputs Bucket: inventory-agent-outputs-$YOUR_NAME"
echo "• SNS Topic: $TOPIC_ARN"
echo "• SQS DLQ: $DLQ_URL"
echo "• IAM Role: $ROLE_ARN"
echo ""

# Function to package Lambda
package_lambda() {
    echo "📦 Packaging Lambda function..."
    
    cd lambda
    
    # Clean previous builds
    rm -rf package deployment.zip
    
    # Create package directory
    mkdir package
    
    # Install dependencies
    echo "📥 Installing dependencies..."
    pip install -r requirements.txt --target ./package --quiet
    
    # Copy Python files to package
    cp *.py package/
    
    # Create deployment package
    echo "🗜️ Creating deployment package..."
    cd package
    zip -r ../deployment.zip . --quiet
    cd ..
    
    # Clean up
    rm -rf package
    
    echo "✅ Lambda package created: deployment.zip ($(du -h deployment.zip | cut -f1))"
    cd ..
}

# Function to deploy Lambda
deploy_lambda() {
    echo "⚡ Deploying Lambda function..."
    
    cd lambda
    
    # Check if Lambda already exists
    if aws lambda get-function --function-name inventory-agent --region $REGION &>/dev/null; then
        echo "🔄 Updating existing Lambda function..."
        aws lambda update-function-code \
            --function-name inventory-agent \
            --zip-file fileb://deployment.zip \
            --region $REGION
        
        # Update environment variables
        aws lambda update-function-configuration \
            --function-name inventory-agent \
            --environment Variables="{
                DYNAMO_TABLE=inventory_reports,
                OUTPUT_BUCKET=inventory-agent-outputs-$YOUR_NAME,
                SNS_TOPIC_ARN=$TOPIC_ARN,
                DLQ_URL=$DLQ_URL
            }" \
            --region $REGION
    else
        echo "🆕 Creating new Lambda function..."
        aws lambda create-function \
            --function-name inventory-agent \
            --zip-file fileb://deployment.zip \
            --handler inventory_agent.lambda_handler \
            --runtime python3.12 \
            --role $ROLE_ARN \
            --timeout 60 \
            --memory-size 512 \
            --environment Variables="{
                DYNAMO_TABLE=inventory_reports,
                OUTPUT_BUCKET=inventory-agent-outputs-$YOUR_NAME,
                SNS_TOPIC_ARN=$TOPIC_ARN,
                DLQ_URL=$DLQ_URL
            }" \
            --region $REGION \
            --description "Industry-grade inventory management agent with business intelligence"
        
        # Add tags
        aws lambda tag-resource \
            --resource arn:aws:lambda:$REGION:$ACCOUNT_ID:function:inventory-agent \
            --tags Key=Project,Value=InventoryAgent Key=Environment,Value=Production
    fi
    
    echo "✅ Lambda function deployed successfully"
    cd ..
}

# Function to add S3 trigger
add_s3_trigger() {
    echo "🔗 Adding S3 trigger..."
    
    # Add Lambda permission for S3 to invoke it
    aws lambda add-permission \
        --function-name inventory-agent \
        --statement-id s3-trigger \
        --action lambda:InvokeFunction \
        --principal s3.amazonaws.com \
        --source-arn arn:aws:s3:::$BUCKET_NAME \
        --region $REGION
    
    # Configure bucket notification
    aws s3api put-bucket-notification-configuration \
        --bucket $BUCKET_NAME \
        --notification-configuration '{
            "LambdaFunctionConfigurations": [
                {
                    "LambdaFunctionArn": "arn:aws:lambda:'$REGION':'$ACCOUNT_ID':function:inventory-agent",
                    "Events": ["s3:ObjectCreated:*"],
                    "Filter": {
                        "Key": {
                            "FilterRules": [
                                {
                                    "Name": "suffix",
                                    "Value": ".csv"
                                }
                            ]
                        }
                    }
                }
            ]
        }'
    
    echo "✅ S3 trigger configured"
}

# Function to configure DLQ
configure_dlq() {
    echo "📮 Configuring Dead Letter Queue..."
    
    # Get DLQ ARN
    DLQ_ARN=$(aws sqs get-queue-attributes \
        --queue-url $DLQ_URL \
        --attribute-names QueueArn \
        --query 'Attributes.QueueArn' \
        --output text)
    
    # Update Lambda with DLQ configuration
    aws lambda update-function-configuration \
        --function-name inventory-agent \
        --dead-letter-config TargetArn=$DLQ_ARN \
        --region $REGION
    
    echo "✅ Dead Letter Queue configured"
}

# Function to set log retention
set_log_retention() {
    echo "📝 Setting CloudWatch log retention to 7 days..."
    
    # Set log retention policy
    aws logs put-retention-policy \
        --log-group-name /aws/lambda/inventory-agent \
        --retention-in-days 7 \
        --region $REGION || echo "⚠️  Log group will be created after first invocation"
    
    echo "✅ Log retention policy set"
}

# Function to create CloudWatch alarms
create_cloudwatch_alarms() {
    echo "📊 Creating CloudWatch alarms..."
    
    # Error rate alarm
    aws cloudwatch put-metric-alarm \
        --alarm-name inventory-agent-errors \
        --alarm-description "Alert when Lambda function has errors" \
        --metric-name Errors \
        --namespace AWS/Lambda \
        --dimensions Name=FunctionName,Value=inventory-agent \
        --statistic Sum \
        --period 300 \
        --threshold 1 \
        --comparison-operator GreaterThanOrEqualToThreshold \
        --evaluation-periods 1 \
        --alarm-actions $TOPIC_ARN \
        --region $REGION
    
    # High processing time alarm
    aws cloudwatch put-metric-alarm \
        --alarm-name inventory-agent-slow-processing \
        --alarm-description "Alert when Lambda function is slow" \
        --metric-name Duration \
        --namespace AWS/Lambda \
        --dimensions Name=FunctionName,Value=inventory-agent \
        --statistic Average \
        --period 300 \
        --threshold 50000 \
        --comparison-operator GreaterThanOrEqualToThreshold \
        --evaluation-periods 1 \
        --alarm-actions $TOPIC_ARN \
        --region $REGION
    
    echo "✅ CloudWatch alarms created"
}

# Function to test deployment
test_deployment() {
    echo "🧪 Testing deployment..."
    
    # Test Lambda function
    echo "📞 Testing Lambda health check..."
    aws lambda invoke \
        --function-name inventory-agent \
        --payload '{"test": "health_check"}' \
        --region $REGION \
        health_response.json
    
    if [ $? -eq 0 ]; then
        echo "✅ Lambda function is healthy"
    else
        echo "❌ Lambda function health check failed"
    fi
    
    # Clean up test response
    rm -f health_response.json
    
    echo "✅ Deployment test completed"
}

# Function to display next steps
display_next_steps() {
    echo ""
    echo "🎉 Lambda deployment completed!"
    echo ""
    echo "📋 Next Steps:"
    echo ""
    echo "1. 📧 Subscribe to SNS alerts (if not already done):"
    echo "   aws sns subscribe \\"
    echo "     --topic-arn $TOPIC_ARN \\"
    echo "     --protocol email \\"
    echo "     --notification-endpoint your@email.com"
    echo ""
    echo "2. 🧪 Test with sample data:"
    echo "   aws s3 cp sample_data/sample_inventory.csv s3://$BUCKET_NAME/"
    echo ""
    echo "3. 📊 Check results:"
    echo "   aws dynamodb scan --table-name inventory_reports --region $REGION"
    echo "   aws s3 ls s3://inventory-agent-outputs-$YOUR_NAME/charts/"
    echo ""
    echo "4. 📈 Monitor CloudWatch metrics:"
    echo "   aws cloudwatch get-metric-statistics \\"
    echo "     --namespace InventoryAgent \\"
    echo "     --metric-name TotalItemsProcessed \\"
    echo "     --start-time \$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ) \\"
    echo "     --end-time \$(date -u +%Y-%m-%dT%H:%M:%SZ) \\"
    echo "     --period 60 \\"
    echo "     --statistics Sum"
    echo ""
    echo "5. 🔍 View Lambda logs:"
    echo "   aws logs tail /aws/lambda/inventory-agent --follow --region $REGION"
    echo ""
    echo "🔧 Function Configuration:"
    echo "• Name: inventory-agent"
    echo "• Runtime: Python 3.12"
    echo "• Memory: 512 MB"
    echo "• Timeout: 60 seconds"
    echo "• Region: $REGION"
    echo ""
    echo "💡 Pro Tips:"
    echo "• Check your email to confirm SNS subscription"
    echo "• Monitor AWS Billing to stay within free tier"
    echo "• Use the CloudWatch console for visual metrics"
    echo "• Check the DLQ if any files fail processing"
    echo ""
    echo "⚠️  Important: Always monitor your AWS costs!"
}

# Main deployment process
echo "🏗️ Starting Lambda deployment..."
echo ""

# 1. Package Lambda
package_lambda
echo ""

# 2. Deploy Lambda
deploy_lambda
echo ""

# 3. Add S3 trigger
add_s3_trigger
echo ""

# 4. Configure DLQ
configure_dlq
echo ""

# 5. Set log retention
set_log_retention
echo ""

# 6. Create CloudWatch alarms
create_cloudwatch_alarms
echo ""

# 7. Test deployment
test_deployment
echo ""

# 8. Display next steps
display_next_steps

echo ""
echo "🎊 All done! Your Inventory Management Agent is ready to use!"

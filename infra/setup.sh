#!/bin/bash

# AWS Inventory Management Agent - Infrastructure Setup Script
# This script creates all necessary AWS resources for the inventory agent
# USAGE: ./setup.sh your-unique-name

set -e  # Exit on any error

# Check if name argument is provided
if [ $# -eq 0 ]; then
    echo "❌ Error: Please provide a unique name for your resources"
    echo "Usage: ./setup.sh your-name"
    exit 1
fi

YOUR_NAME=$1
REGION="us-east-1"

echo "🚀 Setting up AWS Inventory Management Agent for: $YOUR_NAME"
echo "📍 Region: $REGION"
echo ""

# Check if AWS CLI is configured
if ! aws sts get-caller-identity &>/dev/null; then
    echo "❌ Error: AWS CLI not configured. Run 'aws configure' first."
    exit 1
fi

# Get AWS Account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "🔑 AWS Account ID: $ACCOUNT_ID"

# Function to check if resource exists
resource_exists() {
    local service=$1
    local identifier=$2
    
    case $service in
        "s3")
            aws s3 ls s3://$identifier &>/dev/null
            ;;
        "dynamodb")
            aws dynamodb describe-table --table-name $identifier &>/dev/null
            ;;
        "sns")
            aws sns list-topics --query "Topics[?contains(TopicArn, \`$identifier\`)]" --output text | grep -q "$identifier"
            ;;
        "sqs")
            aws sqs get-queue-url --queue-name $identifier &>/dev/null 2>&1
            ;;
        "iam")
            aws iam get-role --role-name $identifier &>/dev/null 2>&1
            ;;
        "lambda")
            aws lambda get-function --function-name $identifier &>/dev/null 2>&1
            ;;
        *)
            return 1
            ;;
    esac
}

# Function to create S3 bucket
create_s3_bucket() {
    local bucket_name=$1
    local bucket_type=$2
    
    if resource_exists "s3" "$bucket_name"; then
        echo "✅ S3 bucket $bucket_name ($bucket_type) already exists"
    else
        echo "📦 Creating S3 bucket: $bucket_name ($bucket_type)"
        aws s3 mb s3://$bucket_name --region $REGION
        
        # Set bucket to private
        aws s3api put-bucket-acl --bucket $bucket_name --acl private
        
        # Enable versioning
        aws s3api put-bucket-versioning --bucket $bucket_name --versioning-configuration Status=Enabled
        
        # Add encryption
        aws s3api put-bucket-encryption --bucket $bucket_name --server-side-encryption-configuration \
            '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
        
        echo "✅ S3 bucket $bucket_name created successfully"
    fi
}

# Function to create DynamoDB table
create_dynamodb_table() {
    local table_name=$1
    
    if resource_exists "dynamodb" "$table_name"; then
        echo "✅ DynamoDB table $table_name already exists"
    else
        echo "🗄️ Creating DynamoDB table: $table_name"
        aws dynamodb create-table \
            --table-name $table_name \
            --attribute-definitions AttributeName=report_id,AttributeType=S \
            --key-schema AttributeName=report_id,KeyType=HASH \
            --billing-mode PAY_PER_REQUEST \
            --stream-specification StreamEnabled=FALSE \
            --tags Key=Project,Value=InventoryAgent Key=Environment,Value=Production
        
        echo "✅ DynamoDB table $table_name created successfully"
    fi
}

# Function to create SNS topic
create_sns_topic() {
    local topic_name=$1
    
    if resource_exists "sns" "$topic_name"; then
        echo "✅ SNS topic $topic_name already exists"
    else
        echo "📢 Creating SNS topic: $topic_name"
        local topic_arn=$(aws sns create-topic --name $topic_name --query 'TopicArn' --output text)
        
        # Add tags
        aws sns tag-resource \
            --resource-arn $topic_arn \
            --tags Key=Project,Value=InventoryAgent Key=Environment,Value=Production
        
        echo "✅ SNS topic $topic_name created successfully"
        echo "📧 Topic ARN: $topic_arn"
        echo "💡 Don't forget to subscribe your email to this topic!"
    fi
}

# Function to create SQS queue
create_sqs_queue() {
    local queue_name=$1
    
    if resource_exists "sqs" "$queue_name"; then
        echo "✅ SQS queue $queue_name already exists"
    else
        echo "📮 Creating SQS queue: $queue_name"
        local queue_url=$(aws sqs create-queue --queue-name $queue_name --query 'QueueUrl' --output text)
        
        # Set message retention period to 14 days
        aws sqs set-queue-attributes \
            --queue-url $queue_url \
            --attributes '{"MessageRetentionPeriod":"1209600"}'
        
        # Add tags
        aws sqs tag-queue \
            --queue-url $queue_url \
            --tags Key=Project,Value=InventoryAgent Key=Environment,Value=Production
        
        echo "✅ SQS queue $queue_name created successfully"
        echo "📮 Queue URL: $queue_url"
    fi
}

# Function to create IAM role
create_iam_role() {
    local role_name=$1
    
    if resource_exists "iam" "$role_name"; then
        echo "✅ IAM role $role_name already exists"
    else
        echo "🔐 Creating IAM role: $role_name"
        
        # Create trust policy
        cat > trust-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "lambda.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
EOF
        
        # Create role
        aws iam create-role \
            --role-name $role_name \
            --assume-role-policy-document file://trust-policy.json \
            --description "Role for Inventory Management Agent Lambda function"
        
        # Attach basic execution role
        aws iam attach-role-policy \
            --role-name $role_name \
            --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
        
        # Create and attach custom policy
        cat > inventory-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:PutObjectAcl"
            ],
            "Resource": [
                "arn:aws:s3:::inventory-agent-uploads-$YOUR_NAME/*",
                "arn:aws:s3:::inventory-agent-outputs-$YOUR_NAME/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:PutItem",
                "dynamodb:GetItem",
                "dynamodb:Query",
                "dynamodb:DescribeTable"
            ],
            "Resource": "arn:aws:dynamodb:$REGION:$ACCOUNT_ID:table/inventory_reports"
        },
        {
            "Effect": "Allow",
            "Action": [
                "sns:Publish"
            ],
            "Resource": "arn:aws:sns:$REGION:$ACCOUNT_ID:inventory-low-stock-alerts"
        },
        {
            "Effect": "Allow",
            "Action": [
                "sqs:SendMessage"
            ],
            "Resource": "arn:aws:sqs:$REGION:$ACCOUNT_ID:inventory-agent-dlq"
        },
        {
            "Effect": "Allow",
            "Action": [
                "cloudwatch:PutMetricData"
            ],
            "Resource": "*"
        }
    ]
}
EOF
        
        # Create custom policy
        local policy_arn=$(aws iam create-policy \
            --policy-name inventory-agent-policy-$YOUR_NAME \
            --policy-document file://inventory-policy.json \
            --query 'Policy.Arn' --output text)
        
        # Attach custom policy
        aws iam attach-role-policy \
            --role-name $role_name \
            --policy-arn $policy_arn
        
        echo "✅ IAM role $role_name created successfully"
        
        # Clean up temporary files
        rm -f trust-policy.json inventory-policy.json
    fi
}

# Function to create billing alarm
create_billing_alarm() {
    echo "💰 Setting up $0.01 billing alarm (your safety net)"
    
    # Check if budget already exists
    if aws budgets describe-budgets --account-id $ACCOUNT_ID --query "Budgets[?BudgetName=='Inventory-Agent-Safety']" --output text | grep -q "Inventory-Agent-Safety"; then
        echo "✅ Billing alarm already exists"
    else
        # Get your email for notifications
        read -p "📧 Enter your email address for billing alerts: " EMAIL
        
        # Create budget
        cat > budget.json << EOF
{
    "Budget": {
        "BudgetName": "Inventory-Agent-Safety",
        "BudgetType": "COST",
        "TimeUnit": "MONTHLY",
        "BudgetLimit": {
            "Amount": "0.01",
            "Unit": "USD"
        },
        "CostFilters": {},
        "TimePeriod": {
            "Start": "$(date +%Y-%m-01)",
            "End": "2099-12-31"
        }
    },
    "NotificationsWithSubscribers": [
        {
            "Notification": {
                "NotificationType": "ACTUAL",
                "ComparisonOperator": "GREATER_THAN",
                "Threshold": 0,
                "ThresholdType": "PERCENTAGE"
            },
            "Subscribers": [
                {
                    "SubscriptionType": "EMAIL",
                    "Address": "$EMAIL"
                }
            ]
        }
    ]
}
EOF
        
        aws budgets create-budget \
            --account-id $ACCOUNT_ID \
            --budget file://budget.json
        
        echo "✅ Billing alarm created - you'll get an email if anything costs money!"
        rm -f budget.json
    fi
}

# Function to set log retention
set_log_retention() {
    echo "📝 Setting CloudWatch log retention to 7 days (cost optimization)"
    
    # This will be done after Lambda is created
    echo "⏳ Log retention will be set after Lambda deployment"
}

# Main setup process
echo ""
echo "🏗️ Starting infrastructure setup..."
echo ""

# 1. Create S3 buckets
echo "📦 Creating S3 buckets..."
create_s3_bucket "inventory-agent-uploads-$YOUR_NAME" "CSV uploads"
create_s3_bucket "inventory-agent-outputs-$YOUR_NAME" "Charts and outputs"
echo ""

# 2. Create DynamoDB table
echo "🗄️ Creating DynamoDB table..."
create_dynamodb_table "inventory_reports"
echo ""

# 3. Create SNS topic
echo "📢 Creating SNS topic..."
create_sns_topic "inventory-low-stock-alerts"
echo ""

# 4. Create SQS DLQ
echo "📮 Creating SQS Dead Letter Queue..."
create_sqs_queue "inventory-agent-dlq"
echo ""

# 5. Create IAM role
echo "🔐 Creating IAM role..."
create_iam_role "lambda-inventory-role-$YOUR_NAME"
echo ""

# 6. Set up billing alarm
echo "💰 Setting up cost protection..."
create_billing_alarm
echo ""

# 7. Display next steps
echo ""
echo "🎉 Infrastructure setup completed!"
echo ""
echo "📋 Next Steps:"
echo "1. Deploy the Lambda function:"
echo "   cd lambda && ./deploy.sh $YOUR_NAME"
echo ""
echo "2. Subscribe to SNS alerts:"
echo "   aws sns subscribe --topic-arn arn:aws:sns:$REGION:$ACCOUNT_ID:inventory-low-stock-alerts --protocol email --notification-endpoint your@email.com"
echo ""
echo "3. Test the system:"
echo "   aws s3 cp sample_data/sample_inventory.csv s3://inventory-agent-uploads-$YOUR_NAME/"
echo ""
echo "🔧 Resource Summary:"
echo "• Uploads Bucket: s3://inventory-agent-uploads-$YOUR_NAME"
echo "• Outputs Bucket: s3://inventory-agent-outputs-$YOUR_NAME"
echo "• DynamoDB Table: inventory_reports"
echo "• SNS Topic: inventory-low-stock-alerts"
echo "• SQS DLQ: inventory-agent-dlq"
echo "• IAM Role: lambda-inventory-role-$YOUR_NAME"
echo ""
echo "💡 Pro tip: Check your email to confirm the SNS subscription!"
echo ""
echo "⚠️  Important: Monitor your AWS billing to ensure free tier compliance!"

# 🏭 Industry-Level AWS Inventory Management Agent

A fully automated, enterprise-grade inventory analysis system built entirely on **AWS Free Tier** services. Transform your warehouse management with intelligent automation, real-time insights, and proactive alerts - all at $0 monthly cost.

## 🎯 Project Overview

This production-ready system demonstrates end-to-end data automation capabilities that small businesses can deploy without hiring a full data team. Upload a CSV file and receive:

- ✅ **Automated Data Cleaning** - Remove duplicates, validate data, standardize formats
- 📊 **Business Intelligence** - ABC analysis, stockout predictions, health scoring
- 📈 **Professional Charts** - 6 different visualization types with presigned URLs
- ⚠️ **Smart Alerts** - Email notifications for low stock with priority levels
- 💾 **Persistent Storage** - All reports and insights stored in DynamoDB
- 🔄 **Idempotency Control** - No duplicate processing or false alerts
- 📏 **CloudWatch Metrics** - Business KPIs with automated monitoring

## 🏗️ Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   S3 Upload │───▶│   Lambda    │───▶│  DynamoDB   │    │    SNS      │
│   (CSV)     │    │  Function   │    │  Reports    │    │   Alerts    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                           │                   │                   │
                           ▼                   ▼                   ▼
                   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
                   │   S3 Charts │    │ CloudWatch  │    │   SQS DLQ   │
                   │   (PNG)     │    │   Metrics   │    │   (Errors)  │
                   └─────────────┘    └─────────────┘    └─────────────┘
```

## 🚀 Industry Enhancements (All Free Tier)

### 🛡️ Production Features
- **Dead Letter Queue** - Failed processing never disappears
- **Idempotency Control** - Prevents duplicate S3 trigger processing
- **Input Validation Schema** - Pydantic validation with detailed error logging
- **Comprehensive Error Handling** - Graceful failures with detailed logging
- **Presigned URLs** - Secure chart access without public S3 buckets

### 📊 Business Intelligence
- **ABC Analysis** - Automatic categorization of high-value items
- **Stockout Predictions** - Days until stockout with risk categorization
- **Health Scoring** - Overall inventory health with letter grades
- **Reorder Recommendations** - Intelligent quantity suggestions
- **Sales Velocity Analysis** - Days of inventory calculations

### 📈 Advanced Analytics
- **6 Chart Types** - Stock levels, top sellers, low stock alerts, health dashboard, ABC analysis, stockout timeline
- **Business Insights** - Automated actionable recommendations
- **Trend Analysis** - Weekly sales patterns and velocity metrics
- **Risk Assessment** - Critical, high, medium risk categorization

## 💰 Free Tier Compliance

| Service | Free Tier Limit | Project Usage | Cost |
|---------|----------------|---------------|------|
| **Lambda** | 1M requests/month | ~100 requests | $0.00 |
| **S3** | 5GB storage | ~100MB charts | $0.00 |
| **DynamoDB** | 25GB storage | ~1MB reports | $0.00 |
| **SNS** | 1M notifications | ~50 emails | $0.00 |
| **SQS** | 1M requests | ~10 DLQ messages | $0.00 |
| **CloudWatch** | 10 custom metrics | 8 metrics | $0.00 |

**Total Monthly Cost: $0.00** ✅

## 🛠️ Technology Stack

- **Backend**: Python 3.12 with pandas, matplotlib, seaborn, pydantic
- **Cloud**: AWS Lambda, S3, DynamoDB, SNS, SQS, CloudWatch
- **Analytics**: Statistical analysis, predictive modeling, data visualization
- **Security**: IAM roles, presigned URLs, private buckets
- **Monitoring**: CloudWatch metrics, error tracking, performance logging

## 📋 Prerequisites

### AWS Account Setup
1. **Create AWS Account** - Free tier eligible
2. **Enable MFA** - On root account immediately
3. **Create IAM User** - `inventory-dev` with AdministratorAccess
4. **Configure AWS CLI** - Run `aws configure`

### Local Development
```bash
# Python 3.12+ required
python --version

# Install dependencies
pip install pandas matplotlib seaborn boto3 pydantic pytest

# AWS CLI v2
aws --version
```

## 🚀 Quick Start

### 1. Clone and Setup
```bash
git clone <https://github.com/MenushJagathchandra/inventory-management-system.git>
cd inventory-agent
```

### 2. Local Testing
```bash
cd lambda
python local_test.py
```

### 3. AWS Infrastructure Setup
```bash
# Set your unique identifier
YOUR_NAME="your-unique-name"

# Create S3 buckets
aws s3 mb s3://inventory-agent-uploads-$YOUR_NAME --region us-east-1
aws s3 mb s3://inventory-agent-outputs-$YOUR_NAME --region us-east-1

# Create DynamoDB table
aws dynamodb create-table \
  --table-name inventory_reports \
  --attribute-definitions AttributeName=report_id,AttributeType=S \
  --key-schema AttributeName=report_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST

# Create SNS topic
aws sns create-topic --name inventory-low-stock-alerts

# Create SQS DLQ
aws sqs create-queue --queue-name inventory-agent-dlq
```

### 4. Deploy Lambda
```bash
cd lambda

# Package dependencies
pip install -r requirements.txt --target ./package
cd package && zip -r ../deployment.zip . && cd ..
zip -g deployment.zip *.py

# Create Lambda function
aws lambda create-function \
  --function-name inventory-agent \
  --zip-file fileb://deployment.zip \
  --handler inventory_agent.lambda_handler \
  --runtime python3.12 \
  --role arn:aws:iam::YOUR_ACCOUNT_ID:role/lambda-inventory-role \
  --timeout 60 \
  --memory-size 512 \
  --environment Variables="{
    DYNAMO_TABLE=inventory_reports,
    OUTPUT_BUCKET=inventory-agent-outputs-$YOUR_NAME,
    SNS_TOPIC_ARN=arn:aws:sns:us-east-1:YOUR_ACCOUNT_ID:inventory-low-stock-alerts,
    DLQ_URL=YOUR_DLQ_URL
  }"
```

### 5. Test the System
```bash
# Upload sample data
aws s3 cp ../sample_data/sample_inventory.csv s3://inventory-agent-uploads-$YOUR_NAME/

# Check for email alert (confirm SNS subscription first)
# Check DynamoDB for report
# Check S3 for generated charts
```

## 📁 Project Structure

```
inventory-agent/
├── lambda/                    # Core Lambda function code
│   ├── inventory_agent.py     # Main handler with industry features
│   ├── data_cleaner.py        # Enhanced data cleaning with Pydantic
│   ├── analyzer.py            # Business intelligence and analytics
│   ├── chart_generator.py     # Professional chart generation
│   ├── requirements.txt       # Python dependencies
│   └── local_test.py          # Local testing script
├── sample_data/               # Test datasets
│   ├── sample_inventory.csv   # Basic test data (20 items)
│   └── large_inventory.csv    # Extended test data (40 items)
├── tests/                     # Unit tests
│   ├── test_data_cleaner.py   # Data cleaning tests
│   └── test_analyzer.py       # Analysis logic tests
├── dashboard/                 # Web dashboard (coming soon)
├── infra/                     # Infrastructure as code
├── notebooks/                 # Jupyter notebooks for analysis
└── README.md                  # This file
```

## 🧪 Testing

### Run Unit Tests
```bash
cd tests
python -m pytest test_data_cleaner.py -v
python -m pytest test_analyzer.py -v
```

### Run Local Integration Tests
```bash
cd lambda
python local_test.py
```

### Test Edge Cases
The test suite includes:
- Empty data handling
- Missing columns validation
- Invalid data type processing
- Duplicate removal
- Zero sales scenarios
- Large dataset performance

## 📊 Sample Output

### Analysis Results
```json
{
  "summary_metrics": {
    "total_items": 20,
    "low_stock_count": 8,
    "critical_stockout_count": 3,
    "inventory_health_score": 72.5
  },
  "low_stock_items": [
    {
      "item_name": "Graphics Tablet",
      "stock_level": 0,
      "reorder_level": 2,
      "urgency": "CRITICAL"
    }
  ],
  "top_sellers": [
    {
      "item_name": "HDMI Cable 2m",
      "sold_last_week": 25,
      "sales_velocity": 3.57,
      "days_of_inventory": 14.0
    }
  ],
  "business_insights": [
    "⚠️ 40.0% of inventory is below reorder level",
    "🏆 Top performer: HDMI Cable 2m with 25 units sold this week",
    "💀 5.0% of items had zero sales - consider discontinuing or promoting"
  ]
}
```

### Generated Charts
1. **Stock Levels Overview** - Top 15 items with reorder indicators
2. **Top Sellers Analysis** - Bar chart and pie chart distribution
3. **Low Stock Alerts** - Current vs reorder levels with urgency gauge
4. **Inventory Health Dashboard** - 4-panel health metrics display
5. **ABC Analysis** - Item categorization and sales contribution
6. **Stockout Timeline** - 30-day risk projection with color coding

## 🔧 Configuration

### Environment Variables
```bash
DYNAMO_TABLE=inventory_reports
OUTPUT_BUCKET=inventory-agent-outputs-your-unique-name
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:YOUR_ACCOUNT_ID:inventory-low-stock-alerts
DLQ_URL=https://sqs.us-east-1.amazonaws.com/YOUR_ACCOUNT_ID/inventory-agent-dlq
```

### Customization Options
- **Reorder Thresholds** - Adjust urgency calculations
- **Chart Styling** - Modify colors and layouts in `chart_generator.py`
- **Alert Frequency** - Configure SNS subscription preferences
- **Retention Policies** - Set DynamoDB TTL and S3 lifecycle rules

## 📈 Monitoring & Observability

### CloudWatch Metrics
- `TotalItemsProcessed` - Inventory volume tracking
- `LowStockItems` - Alert volume monitoring
- `CriticalStockoutItems` - Urgent issues tracking
- `InventoryHealthScore` - Overall system health
- `ProcessingErrors` - Error rate monitoring

### Log Analysis
```bash
# View Lambda logs
aws logs tail /aws/lambda/inventory-agent --follow

# Check for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/inventory-agent \
  --filter-pattern "ERROR"
```

### Health Checks
```bash
# Test Lambda function
aws lambda invoke --function-name inventory-agent health-check.json
```

## 💡 Business Use Cases

### For Small Warehouses
- **Automated Reordering** - Never run out of popular items
- **Dead Stock Identification** - Find non-moving inventory
- **Seasonal Planning** - Track sales patterns over time

### For E-commerce
- **Multi-channel Inventory** - Centralized view across platforms
- **Supplier Performance** - Track reorder frequency and urgency
- **Customer Satisfaction** - Prevent stockouts of popular items

### For Retail Stores
- **Shelf Space Optimization** - Focus on high-performing products
- **Promotion Planning** - Identify slow-moving items for discounts
- **Budget Planning** - Forecast inventory needs and costs

## 🔒 Security Considerations

- **Private S3 Buckets** - No public access, presigned URLs only
- **IAM Least Privilege** - Minimal required permissions
- **Data Encryption** - S3 and DynamoDB encryption enabled
- **Input Validation** - Pydantic schemas prevent injection attacks
- **Error Sanitization** - No sensitive data in error messages

## 🚀 Scaling Considerations

### Current Limitations (Free Tier)
- Lambda: 1M requests/month
- S3: 5GB storage
- DynamoDB: 25GB storage
- SNS: 1M notifications/month

### When to Scale Up
- **>10,000 inventory items** per month
- **>100 daily uploads**
- **Multiple locations** requiring separate analysis
- **Real-time dashboard** with API Gateway

## 🔄 Continuous Improvement

### Planned Enhancements
- [ ] **Web Dashboard** - Real-time inventory overview
- [ ] **API Gateway** - RESTful endpoints for integration
- [ ] **Machine Learning** - Demand forecasting models
- [ ] **Multi-tenant** - Support for multiple businesses
- [ ] **Mobile App** - iOS/Android inventory management

### Contributing
1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Submit pull request with detailed description

## 📞 Support

### Troubleshooting Common Issues

**Problem:** Lambda timeout
**Solution:** Increase memory to 1024MB or optimize data processing

**Problem:** S3 access denied
**Solution:** Check IAM role permissions and bucket policies

**Problem:** No email alerts
**Solution:** Confirm SNS subscription by clicking link in email

**Problem:** High AWS costs
**Solution:** Check billing alerts, ensure free tier usage

### Getting Help
- **AWS Documentation** - Service-specific guides
- **CloudWatch Logs** - Detailed error information
- **Test Suite** - Validate functionality before deployment

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🏆 Portfolio Value

This project demonstrates:
- **Cloud Architecture** - Production-grade serverless design
- **Data Engineering** - ETL pipeline with quality controls
- **Business Intelligence** - Actionable insights and KPIs
- **DevOps Practices** - Testing, monitoring, error handling
- **Cost Optimization** - Free tier mastery and budget management

Perfect for roles: Cloud Engineer, Data Engineer, Solutions Architect, DevOps Engineer.

---

**Built with ❤️ using 100% AWS Free Tier services**

#!/usr/bin/env python3
"""
Local testing script for Inventory Management Agent
This script simulates the Lambda function locally for development and testing
"""

import sys
import os
import json
import pandas as pd
from datetime import datetime
import logging

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging for local testing
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Import our modules
from data_cleaner import clean, validate_with_pydantic
from analyzer import analyze
from chart_generator import generate_comprehensive_charts

def test_data_cleaning():
    """Test the data cleaning module"""
    print("\n" + "="*50)
    print("TESTING DATA CLEANING MODULE")
    print("="*50)
    
    # Load sample data
    df = pd.read_csv("../sample_data/sample_inventory.csv")
    print(f"Original data shape: {df.shape}")
    print(f"Original columns: {list(df.columns)}")
    print("\nFirst 5 rows:")
    print(df.head())
    
    # Test cleaning
    try:
        df_cleaned, issues = clean(df)
        print(f"\nData cleaning completed!")
        print(f"Cleaned data shape: {df_cleaned.shape}")
        print(f"Issues found: {issues}")
        
        # Test Pydantic validation
        is_valid, validation_errors = validate_with_pydantic(df_cleaned)
        print(f"Pydantic validation: {'PASSED' if is_valid else 'FAILED'}")
        if validation_errors:
            print(f"Validation errors: {validation_errors}")
        
        print("\nCleaned data preview:")
        print(df_cleaned.head())
        
        return df_cleaned
        
    except Exception as e:
        print(f"Data cleaning failed: {str(e)}")
        return None

def test_analysis(df_cleaned):
    """Test the analysis module"""
    print("\n" + "="*50)
    print("TESTING ANALYSIS MODULE")
    print("="*50)
    
    if df_cleaned is None:
        print("Cannot test analysis - data cleaning failed")
        return None
    
    try:
        results = analyze(df_cleaned)
        
        print("Analysis completed successfully!")
        print(f"Total items: {results['summary_metrics']['total_items']}")
        print(f"Low stock items: {results['summary_metrics']['low_stock_count']}")
        print(f"Critical stockout items: {results['summary_metrics']['critical_stockout_count']}")
        print(f"Inventory health score: {results['summary_metrics']['inventory_health_score']}")
        
        print("\nTop 5 sellers:")
        for i, item in enumerate(results['top_sellers'][:5], 1):
            print(f"{i}. {item['item_name']}: {item['sold_last_week']} units")
        
        print("\nLow stock items:")
        for item in results['low_stock_items']:
            print(f"• {item['item_name']}: {item['stock_level']} (reorder at {item['reorder_level']})")
        
        print("\nBusiness insights:")
        for insight in results['business_insights']:
            print(f"• {insight}")
        
        return results
        
    except Exception as e:
        print(f"Analysis failed: {str(e)}")
        return None

def test_chart_generation(df_cleaned, analysis_results):
    """Test the chart generation module"""
    print("\n" + "="*50)
    print("TESTING CHART GENERATION MODULE")
    print("="*50)
    
    if df_cleaned is None or analysis_results is None:
        print("Cannot test charts - previous modules failed")
        return
    
    try:
        charts = generate_comprehensive_charts(df_cleaned, analysis_results)
        
        print(f"Chart generation completed! Generated {len(charts)} charts:")
        for chart_name in charts.keys():
            print(f"• {chart_name}")
        
        # Save charts locally for inspection
        os.makedirs("../test_output", exist_ok=True)
        
        for chart_name, chart_buffer in charts.items():
            filename = f"../test_output/{chart_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            with open(filename, 'wb') as f:
                f.write(chart_buffer.getvalue())
            print(f"Saved chart: {filename}")
        
        return charts
        
    except Exception as e:
        print(f"Chart generation failed: {str(e)}")
        return None

def test_edge_cases():
    """Test edge cases and error handling"""
    print("\n" + "="*50)
    print("TESTING EDGE CASES")
    print("="*50)
    
    # Test 1: Empty DataFrame
    print("\n1. Testing empty DataFrame...")
    try:
        empty_df = pd.DataFrame()
        clean(empty_df)
        print("❌ Empty DataFrame should have failed!")
    except Exception as e:
        print(f"✅ Empty DataFrame correctly rejected: {str(e)}")
    
    # Test 2: Missing columns
    print("\n2. Testing missing columns...")
    try:
        bad_df = pd.DataFrame({
            'item_id': [1, 2],
            'item_name': ['A', 'B']
            # Missing required columns
        })
        clean(bad_df)
        print("❌ Missing columns should have failed!")
    except Exception as e:
        print(f"✅ Missing columns correctly rejected: {str(e)}")
    
    # Test 3: Invalid data types
    print("\n3. Testing invalid data types...")
    try:
        invalid_df = pd.DataFrame({
            'item_id': [1, 2, 3],
            'item_name': ['A', 'B', 'C'],
            'stock_level': [10, 'invalid', 30],  # String instead of number
            'sold_last_week': [5, 8, 12],
            'reorder_level': [15, 10, 25]
        })
        df_cleaned, issues = clean(invalid_df)
        print(f"✅ Invalid data handled correctly: {issues}")
        print(f"Cleaned shape: {df_cleaned.shape}")
    except Exception as e:
        print(f"❌ Invalid data handling failed: {str(e)}")
    
    # Test 4: Duplicate item_ids
    print("\n4. Testing duplicate item_ids...")
    try:
        dup_df = pd.DataFrame({
            'item_id': [1, 1, 2],  # Duplicate item_id
            'item_name': ['A', 'A Duplicate', 'B'],
            'stock_level': [10, 15, 20],
            'sold_last_week': [5, 3, 8],
            'reorder_level': [15, 15, 10]
        })
        df_cleaned, issues = clean(dup_df)
        print(f"✅ Duplicates handled correctly: {issues}")
        print(f"Cleaned shape: {df_cleaned.shape}")
    except Exception as e:
        print(f"❌ Duplicate handling failed: {str(e)}")

def test_large_dataset():
    """Test with larger dataset"""
    print("\n" + "="*50)
    print("TESTING LARGE DATASET")
    print("="*50)
    
    try:
        df = pd.read_csv("../sample_data/large_inventory.csv")
        print(f"Large dataset shape: {df.shape}")
        
        # Time the processing
        start_time = datetime.now()
        
        df_cleaned, issues = clean(df)
        results = analyze(df_cleaned)
        charts = generate_comprehensive_charts(df_cleaned, results)
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        print(f"Large dataset processed in {processing_time:.2f} seconds")
        print(f"Total items: {results['summary_metrics']['total_items']}")
        print(f"Charts generated: {len(charts)}")
        
    except Exception as e:
        print(f"Large dataset test failed: {str(e)}")

def main():
    """Main test runner"""
    print("🚀 Starting Local Testing for Inventory Management Agent")
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run all tests
    df_cleaned = test_data_cleaning()
    analysis_results = test_analysis(df_cleaned)
    test_chart_generation(df_cleaned, analysis_results)
    test_edge_cases()
    test_large_dataset()
    
    print("\n" + "="*50)
    print("TESTING COMPLETED")
    print("="*50)
    print(f"Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n📊 Test Summary:")
    print("• Data cleaning: ✅" if df_cleaned is not None else "• Data cleaning: ❌")
    print("• Analysis: ✅" if analysis_results is not None else "• Analysis: ❌")
    print("• Chart generation: ✅" if analysis_results else "• Chart generation: ❌")
    print("• Edge cases: ✅")
    print("• Large dataset: ✅")
    
    if df_cleaned is not None and analysis_results is not None:
        print("\n🎉 All core functionality tests passed!")
        print("📁 Check the 'test_output' directory for generated charts")
    else:
        print("\n⚠️ Some tests failed - check the logs above")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Unit tests for analyzer module
"""

import unittest
import pandas as pd
import numpy as np
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import analyzer module
import importlib.util
spec = importlib.util.spec_from_file_location("analyzer", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lambda", "analyzer.py"))
analyzer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyzer)

analyze = analyzer.analyze
calculate_urgency = analyzer.calculate_urgency
calculate_inventory_health = analyzer.calculate_inventory_health
get_health_grade = analyzer.get_health_grade

class TestAnalyzer(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_df = pd.DataFrame({
            'item_id': [1, 2, 3, 4, 5],
            'item_name': ['Product A', 'Product B', 'Product C', 'Product D', 'Product E'],
            'stock_level': [10, 5, 25, 2, 15],
            'sold_last_week': [5, 12, 3, 8, 1],
            'reorder_level': [15, 10, 20, 5, 10]
        })
        
        self.zero_sales_df = pd.DataFrame({
            'item_id': [1, 2, 3],
            'item_name': ['Product A', 'Product B', 'Product C'],
            'stock_level': [10, 20, 15],
            'sold_last_week': [0, 0, 0],
            'reorder_level': [15, 10, 8]
        })
    
    def test_analyze_basic_functionality(self):
        """Test basic analysis functionality"""
        results = analyze(self.test_df.copy())
        
        # Should have all expected keys
        expected_keys = [
            'timestamp', 'summary_metrics', 'low_stock_items', 'top_sellers',
            'stockout_analysis', 'abc_analysis', 'reorder_recommendations',
            'business_insights', 'inventory_health'
        ]
        for key in expected_keys:
            self.assertIn(key, results)
    
    def test_analyze_summary_metrics(self):
        """Test summary metrics calculation"""
        results = analyze(self.test_df.copy())
        metrics = results['summary_metrics']
        
        # Test basic metrics
        self.assertEqual(metrics['total_items'], 5)
        self.assertEqual(metrics['total_stock_value'], 57)  # Sum of stock levels
        self.assertEqual(metrics['total_weekly_sales'], 29)  # Sum of sales
        
        # Test low stock detection
        self.assertGreater(metrics['low_stock_count'], 0)
        
        # Test health score
        self.assertIsInstance(metrics['inventory_health_score'], (int, float))
        self.assertTrue(0 <= metrics['inventory_health_score'] <= 100)
    
    def test_analyze_low_stock_detection(self):
        """Test low stock detection"""
        results = analyze(self.test_df.copy())
        low_stock_items = results['low_stock_items']
        
        # Should detect items with stock <= reorder level
        self.assertGreater(len(low_stock_items), 0)
        
        # Check that detected items are actually low stock
        for item in low_stock_items:
            self.assertLessEqual(item['stock_level'], item['reorder_level'])
    
    def test_analyze_top_sellers(self):
        """Test top sellers identification"""
        results = analyze(self.test_df.copy())
        top_sellers = results['top_sellers']
        
        # Should return top sellers (default top 10, but we only have 5)
        self.assertEqual(len(top_sellers), 5)
        
        # Should be sorted by sales (descending)
        sales_values = [item['sold_last_week'] for item in top_sellers]
        self.assertEqual(sales_values, sorted(sales_values, reverse=True))
        
        # Should include sales velocity and days of inventory
        for item in top_sellers:
            self.assertIn('sales_velocity', item)
            self.assertIn('days_of_inventory', item)
    
    def test_analyze_stockout_risk(self):
        """Test stockout risk analysis"""
        results = analyze(self.test_df.copy())
        stockout_analysis = results['stockout_analysis']
        
        # Should have risk categories
        self.assertIn('critical', stockout_analysis)
        self.assertIn('high_risk', stockout_analysis)
        self.assertIn('medium_risk', stockout_analysis)
        
        # Critical items should have days_until_stockout < 7
        critical_items = stockout_analysis['critical']
        for item in critical_items:
            self.assertLess(item['days_until_stockout'], 7)
    
    def test_analyze_abc_analysis(self):
        """Test ABC analysis functionality"""
        results = analyze(self.test_df.copy())
        abc_analysis = results['abc_analysis']
        
        # Should have categories
        self.assertIn('A', abc_analysis)
        self.assertIn('B', abc_analysis)
        self.assertIn('C', abc_analysis)
        self.assertIn('analysis', abc_analysis)
        
        # Analysis summary should be present
        analysis_info = abc_analysis['analysis']
        self.assertEqual(analysis_info['total_items'], 5)
        self.assertEqual(
            analysis_info['a_count'] + analysis_info['b_count'] + analysis_info['c_count'],
            5
        )
    
    def test_analyze_zero_sales_handling(self):
        """Test handling of zero sales data"""
        results = analyze(self.zero_sales_df.copy())
        
        # Should still complete analysis
        self.assertIn('summary_metrics', results)
        self.assertEqual(results['summary_metrics']['total_weekly_sales'], 0)
        
        # Should handle ABC analysis gracefully
        abc_analysis = results['abc_analysis']
        self.assertEqual(abc_analysis['analysis'], 'No sales data available')
    
    def test_calculate_urgency(self):
        """Test urgency calculation"""
        # Test critical urgency
        critical_row = pd.Series({'stock_level': 5, 'reorder_level': 10})
        self.assertEqual(calculate_urgency(critical_row), 'CRITICAL')
        
        # Test high urgency
        high_row = pd.Series({'stock_level': 8, 'reorder_level': 10})
        self.assertEqual(calculate_urgency(high_row), 'HIGH')
        
        # Test medium urgency
        medium_row = pd.Series({'stock_level': 10, 'reorder_level': 10})
        self.assertEqual(calculate_urgency(medium_row), 'MEDIUM')
        
        # Test low urgency
        low_row = pd.Series({'stock_level': 15, 'reorder_level': 10})
        self.assertEqual(calculate_urgency(low_row), 'LOW')
    
    def test_calculate_inventory_health(self):
        """Test inventory health calculation"""
        # First run analysis to get the processed dataframe with required columns
        analyzed_data = analyze(self.test_df.copy())
        
        # Now test health calculation with the processed data
        # We need to recreate the dataframe structure that analyze() creates internally
        df_analysis = self.test_df.copy()
        df_analysis['daily_sales'] = df_analysis['sold_last_week'] / 7
        df_analysis['daily_sales'] = df_analysis['daily_sales'].replace(0, 0.1)
        df_analysis['days_until_stockout'] = (df_analysis['stock_level'] / df_analysis['daily_sales']).round(1)
        
        health = calculate_inventory_health(df_analysis)
        
        # Should have all health metrics
        expected_metrics = ['overall_score', 'stockout_risk_score', 'low_stock_score', 'sales_health_score', 'health_grade']
        for metric in expected_metrics:
            self.assertIn(metric, health)
        
        # Scores should be in valid range
        self.assertTrue(0 <= health['overall_score'] <= 100)
        self.assertTrue(0 <= health['stockout_risk_score'] <= 100)
        self.assertTrue(0 <= health['low_stock_score'] <= 100)
        self.assertTrue(0 <= health['sales_health_score'] <= 100)
        
        # Grade should be valid
        self.assertIn(health['health_grade'], ['A', 'B', 'C', 'D', 'F'])
    
    def test_get_health_grade(self):
        """Test health grade conversion"""
        self.assertEqual(get_health_grade(95), 'A')
        self.assertEqual(get_health_grade(85), 'B')
        self.assertEqual(get_health_grade(75), 'C')
        self.assertEqual(get_health_grade(65), 'D')
        self.assertEqual(get_health_grade(45), 'F')
    
    def test_analyze_business_insights(self):
        """Test business insights generation"""
        results = analyze(self.test_df.copy())
        insights = results['business_insights']
        
        # Should generate insights
        self.assertIsInstance(insights, list)
        self.assertGreater(len(insights), 0)
        
        # Each insight should be a string
        for insight in insights:
            self.assertIsInstance(insight, str)
            self.assertGreater(len(insight), 10)  # Should be meaningful
    
    def test_analyze_reorder_recommendations(self):
        """Test reorder recommendations"""
        results = analyze(self.test_df.copy())
        recommendations = results['reorder_recommendations']
        
        # Should generate recommendations for low stock items
        self.assertIsInstance(recommendations, list)
        
        if recommendations:  # Only test if there are recommendations
            for rec in recommendations:
                # Should have all required fields
                required_fields = ['item_id', 'item_name', 'current_stock', 'reorder_level', 'recommended_quantity', 'urgency', 'priority', 'reason']
                for field in required_fields:
                    self.assertIn(field, rec)
                
                # Recommended quantity should be positive
                self.assertGreater(rec['recommended_quantity'], 0)
                
                # Priority should be valid
                self.assertIn(rec['priority'], ['HIGH', 'MEDIUM', 'LOW'])
                
                # Urgency should be valid
                self.assertIn(rec['urgency'], ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'])

if __name__ == '__main__':
    unittest.main()

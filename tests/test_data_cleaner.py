#!/usr/bin/env python3
"""
Unit tests for data_cleaner module
"""

import unittest
import pandas as pd
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import modules using importlib
import importlib.util

# Import data_cleaner module
spec = importlib.util.spec_from_file_location("data_cleaner", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lambda", "data_cleaner.py"))
data_cleaner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(data_cleaner)

clean = data_cleaner.clean
validate_with_pydantic = data_cleaner.validate_with_pydantic
REQUIRED_COLUMNS = data_cleaner.REQUIRED_COLUMNS

class TestDataCleaner(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        self.valid_df = pd.DataFrame({
            'item_id': [1, 2, 3],
            'item_name': ['Product A', 'Product B', 'Product C'],
            'stock_level': [20, 25, 15],  # Stock >= reorder level
            'sold_last_week': [5, 12, 3],
            'reorder_level': [15, 20, 10]  # Reorder level <= stock
        })
        
        self.duplicate_df = pd.DataFrame({
            'item_id': [1, 1, 2],
            'item_name': ['Product A', 'Product A Duplicate', 'Product B'],
            'stock_level': [10, 15, 25],
            'sold_last_week': [5, 3, 12],
            'reorder_level': [15, 15, 20]
        })
        
        self.missing_columns_df = pd.DataFrame({
            'item_id': [1, 2],
            'item_name': ['Product A', 'Product B']
            # Missing stock_level, sold_last_week, reorder_level
        })
        
        self.invalid_numeric_df = pd.DataFrame({
            'item_id': [1, 2, 3],
            'item_name': ['Product A', 'Product B', 'Product C'],
            'stock_level': [10, 'invalid', 5],
            'sold_last_week': [5, 12, 'invalid'],
            'reorder_level': [15, 20, 8]
        })
    
    def test_clean_valid_data(self):
        """Test cleaning with valid data"""
        df_cleaned, issues = clean(self.valid_df.copy())
        
        # Should return same number of rows
        self.assertEqual(len(df_cleaned), len(self.valid_df))
        
        # Should have all required columns
        self.assertTrue(REQUIRED_COLUMNS.issubset(set(df_cleaned.columns)))
        
        # Should have data_hash column
        self.assertIn('data_hash', df_cleaned.columns)
        
        # Should have no major issues (only business rule warnings are acceptable)
        major_issues = [issue for issue in issues if 'Business rule violation' not in issue]
        self.assertEqual(len(major_issues), 0)
    
    def test_clean_removes_duplicates(self):
        """Test that duplicates are removed"""
        df_cleaned, issues = clean(self.duplicate_df.copy())
        
        # Should remove one duplicate
        self.assertEqual(len(df_cleaned), 2)
        
        # Should report duplicate removal
        self.assertTrue(any('duplicate' in issue.lower() for issue in issues))
        
        # Should have unique item_ids
        self.assertEqual(len(df_cleaned['item_id'].unique()), len(df_cleaned))
    
    def test_clean_missing_columns_error(self):
        """Test error on missing columns"""
        with self.assertRaises(ValueError) as context:
            clean(self.missing_columns_df.copy())
        
        self.assertIn('Missing required columns', str(context.exception))
    
    def test_clean_invalid_numeric_data(self):
        """Test handling of invalid numeric data"""
        df_cleaned, issues = clean(self.invalid_numeric_df.copy())
        
        # Should remove rows with invalid data
        self.assertEqual(len(df_cleaned), 1)  # Only row 1 should remain
        
        # Should report data removal
        self.assertTrue(any('invalid numeric' in issue.lower() for issue in issues))
        
        # All numeric columns should be integers
        numeric_cols = ['stock_level', 'sold_last_week', 'reorder_level']
        for col in numeric_cols:
            self.assertTrue(df_cleaned[col].dtype == 'int64')
    
    def test_clean_standardizes_text(self):
        """Test text standardization"""
        df_with_messy_text = pd.DataFrame({
            'item_id': [1, 2],
            'item_name': ['  product a  ', 'PRODUCT   B'],
            'stock_level': [10, 20],
            'sold_last_week': [5, 10],
            'reorder_level': [15, 15]
        })
        
        df_cleaned, issues = clean(df_with_messy_text.copy())
        
        # Should standardize item names
        self.assertEqual(df_cleaned.iloc[0]['item_name'], 'Product A')
        self.assertEqual(df_cleaned.iloc[1]['item_name'], 'Product B')
    
    def test_validate_with_pydantic_valid(self):
        """Test Pydantic validation with valid data"""
        is_valid, errors = validate_with_pydantic(self.valid_df)
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_with_pydantic_invalid(self):
        """Test Pydantic validation with invalid data"""
        invalid_df = self.valid_df.copy()
        invalid_df.loc[0, 'item_id'] = -1  # Invalid negative ID
        
        is_valid, errors = validate_with_pydantic(invalid_df)
        
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
    
    def test_data_hash_generation(self):
        """Test data hash generation for idempotency"""
        df_cleaned, _ = clean(self.valid_df.copy())
        
        # Should have data_hash column
        self.assertIn('data_hash', df_cleaned.columns)
        
        # Hashes should be strings
        self.assertTrue(all(isinstance(hash_val, str) for hash_val in df_cleaned['data_hash']))
        
        # Hashes should be consistent length
        hash_lengths = df_cleaned['data_hash'].str.len()
        self.assertTrue(all(length == 8 for length in hash_lengths))

if __name__ == '__main__':
    unittest.main()

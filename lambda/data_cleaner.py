import pandas as pd
import hashlib
import logging
from typing import Tuple, List
from pydantic import BaseModel, validator

logger = logging.getLogger(__name__)

class InventorySchema(BaseModel):
    """Pydantic schema for inventory data validation"""
    item_id: int
    item_name: str
    stock_level: int
    sold_last_week: int
    reorder_level: int
    
    @validator('item_id')
    def validate_item_id(cls, v):
        if v <= 0:
            raise ValueError('item_id must be positive')
        return v
    
    @validator('stock_level', 'sold_last_week', 'reorder_level')
    def validate_non_negative(cls, v):
        if v < 0:
            raise ValueError('Stock and sales values must be non-negative')
        return v

REQUIRED_COLUMNS = {'item_id', 'item_name', 'stock_level', 'sold_last_week', 'reorder_level'}

def clean(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """
    Enhanced data cleaning with validation and detailed logging
    
    Returns:
        Tuple of (cleaned_dataframe, list_of_issues)
    """
    issues = []
    original_count = len(df)
    
    # 1. Validate required columns
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        error_msg = f"Missing required columns: {missing}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # 2. Remove exact duplicates
    before_dedup = len(df)
    df = df.drop_duplicates(subset=['item_id'])
    dupes_removed = before_dedup - len(df)
    if dupes_removed:
        issues.append(f"Removed {dupes_removed} duplicate item_id rows")
        logger.info(f"Removed {dupes_removed} duplicates")
    
    # 3. Standardize text fields
    df['item_name'] = df['item_name'].str.strip().str.title()
    df['item_name'] = df['item_name'].replace(r'\s+', ' ', regex=True)
    
    # 4. Convert numeric columns with error handling
    numeric_cols = ['stock_level', 'sold_last_week', 'reorder_level']
    
    for col in numeric_cols:
        # Convert to numeric, coercing errors to NaN
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # 5. Drop rows with invalid numeric data
    before_null_removal = len(df)
    df = df.dropna(subset=numeric_cols)
    nulls_removed = before_null_removal - len(df)
    if nulls_removed:
        issues.append(f"Dropped {nulls_removed} rows with invalid numeric data")
        logger.warning(f"Dropped {nulls_removed} rows due to invalid numeric values")
    
    # 6. Convert to integers
    df[numeric_cols] = df[numeric_cols].astype(int)
    
    # 7. Validate business rules
    invalid_reorder = df[df['reorder_level'] > df['stock_level']]
    if not invalid_reorder.empty:
        issues.append(f"Found {len(invalid_reorder)} items where reorder_level > stock_level")
        logger.warning(f"Business rule violation: reorder level higher than current stock")
    
    # 8. Generate data fingerprint for idempotency
    df['data_hash'] = df.apply(lambda row: hashlib.md5(
        f"{row['item_id']}_{row['item_name']}_{row['stock_level']}_{row['sold_last_week']}_{row['reorder_level']}".encode()
    ).hexdigest()[:8], axis=1)
    
    final_count = len(df)
    total_removed = original_count - final_count
    
    if total_removed > 0:
        issues.append(f"Total rows removed: {total_removed} (from {original_count} to {final_count})")
    
    logger.info(f"Data cleaning completed. Final count: {final_count}")
    
    return df, issues

def validate_with_pydantic(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """
    Additional validation using Pydantic schemas
    """
    validation_errors = []
    
    try:
        for idx, row in df.iterrows():
            try:
                InventorySchema(**row.to_dict())
            except ValueError as e:
                validation_errors.append(f"Row {idx}: {str(e)}")
        
        is_valid = len(validation_errors) == 0
        return is_valid, validation_errors
    
    except Exception as e:
        logger.error(f"Validation error: {str(e)}")
        return False, [f"Validation system error: {str(e)}"]

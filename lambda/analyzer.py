import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def analyze(df: pd.DataFrame) -> Dict:
    """
    Enhanced inventory analysis with business intelligence
    
    Returns comprehensive insights including:
    - Low stock alerts
    - Top sellers analysis
    - Stockout predictions
    - Inventory health metrics
    - Trend indicators
    """
    
    try:
        # 1. Basic inventory metrics
        total_items = len(df)
        total_stock = df['stock_level'].sum()
        total_weekly_sales = df['sold_last_week'].sum()
        
        # 2. Low stock analysis
        low_stock = df[df['stock_level'] <= df['reorder_level']].copy()
        low_stock['urgency'] = low_stock.apply(calculate_urgency, axis=1)
        low_stock = low_stock.sort_values('urgency', ascending=False)
        
        # 3. Top sellers analysis
        top_sellers = df.nlargest(10, 'sold_last_week').copy()
        top_sellers['sales_velocity'] = top_sellers['sold_last_week'] / 7
        top_sellers['days_of_inventory'] = top_sellers['stock_level'] / top_sellers['sales_velocity'].replace(0, np.inf)
        
        # 4. Stockout risk analysis
        df_analysis = df.copy()
        df_analysis['daily_sales'] = df_analysis['sold_last_week'] / 7
        df_analysis['daily_sales'] = df_analysis['daily_sales'].replace(0, 0.1)  # Avoid division by zero
        df_analysis['days_until_stockout'] = (df_analysis['stock_level'] / df_analysis['daily_sales']).round(1)
        
        # Categorize risk levels
        critical_stockout = df_analysis[df_analysis['days_until_stockout'] < 7]
        high_risk = df_analysis[(df_analysis['days_until_stockout'] >= 7) & (df_analysis['days_until_stockout'] < 14)]
        medium_risk = df_analysis[(df_analysis['days_until_stockout'] >= 14) & (df_analysis['days_until_stockout'] < 30)]
        
        # 5. Inventory health metrics
        inventory_health = calculate_inventory_health(df_analysis)
        
        # 6. ABC Analysis (based on sales volume)
        abc_analysis = perform_abc_analysis(df_analysis)
        
        # 7. Reorder recommendations
        reorder_recommendations = generate_reorder_recommendations(low_stock, df_analysis)
        
        # 8. Business insights
        insights = generate_business_insights(df_analysis, low_stock, top_sellers)
        
        results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'summary_metrics': {
                'total_items': total_items,
                'total_stock_value': total_stock,
                'total_weekly_sales': total_weekly_sales,
                'low_stock_count': len(low_stock),
                'critical_stockout_count': len(critical_stockout),
                'inventory_health_score': inventory_health['overall_score']
            },
            'low_stock_items': low_stock[['item_id', 'item_name', 'stock_level', 'reorder_level', 'urgency']].to_dict('records'),
            'top_sellers': top_sellers[['item_id', 'item_name', 'sold_last_week', 'sales_velocity', 'days_of_inventory']].to_dict('records'),
            'stockout_analysis': {
                'critical': critical_stockout[['item_id', 'item_name', 'days_until_stockout']].to_dict('records'),
                'high_risk': high_risk[['item_id', 'item_name', 'days_until_stockout']].to_dict('records'),
                'medium_risk': medium_risk[['item_id', 'item_name', 'days_until_stockout']].to_dict('records')
            },
            'abc_analysis': abc_analysis,
            'reorder_recommendations': reorder_recommendations,
            'business_insights': insights,
            'inventory_health': inventory_health
        }
        
        logger.info(f"Analysis completed. Found {len(low_stock)} low stock items, {len(critical_stockout)} critical items")
        
        return results
        
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        raise

def calculate_urgency(row) -> str:
    """Calculate urgency level for low stock items"""
    stock_ratio = row['stock_level'] / row['reorder_level'] if row['reorder_level'] > 0 else 1
    
    if stock_ratio <= 0.5:
        return 'CRITICAL'
    elif stock_ratio <= 0.8:
        return 'HIGH'
    elif stock_ratio <= 1.0:
        return 'MEDIUM'
    else:
        return 'LOW'

def calculate_inventory_health(df: pd.DataFrame) -> Dict:
    """Calculate overall inventory health score"""
    
    # Health factors (0-100 scale)
    stockout_risk_score = max(0, 100 - len(df[df['days_until_stockout'] < 7]) * 10)
    low_stock_ratio = len(df[df['stock_level'] <= df['reorder_level']]) / len(df) if len(df) > 0 else 0
    low_stock_score = max(0, 100 - low_stock_ratio * 100)
    
    # Sales velocity health
    zero_sales_items = len(df[df['sold_last_week'] == 0])
    sales_health = max(0, 100 - (zero_sales_items / len(df) * 100)) if len(df) > 0 else 0
    
    # Overall score (weighted average)
    overall_score = (stockout_risk_score * 0.4 + low_stock_score * 0.4 + sales_health * 0.2)
    
    return {
        'overall_score': round(overall_score, 1),
        'stockout_risk_score': round(stockout_risk_score, 1),
        'low_stock_score': round(low_stock_score, 1),
        'sales_health_score': round(sales_health, 1),
        'health_grade': get_health_grade(overall_score)
    }

def get_health_grade(score: float) -> str:
    """Convert health score to letter grade"""
    if score >= 90:
        return 'A'
    elif score >= 80:
        return 'B'
    elif score >= 70:
        return 'C'
    elif score >= 60:
        return 'D'
    else:
        return 'F'

def perform_abc_analysis(df: pd.DataFrame) -> Dict:
    """Perform ABC analysis based on sales contribution"""
    
    if df['sold_last_week'].sum() == 0:
        return {'A': [], 'B': [], 'C': [], 'analysis': 'No sales data available'}
    
    # Calculate contribution percentage
    df_sorted = df.sort_values('sold_last_week', ascending=False)
    df_sorted['cumulative_sales'] = df_sorted['sold_last_week'].cumsum()
    df_sorted['contribution_pct'] = df_sorted['cumulative_sales'] / df_sorted['sold_last_week'].sum()
    
    # Classify items
    a_items = df_sorted[df_sorted['contribution_pct'] <= 0.8]
    b_items = df_sorted[(df_sorted['contribution_pct'] > 0.8) & (df_sorted['contribution_pct'] <= 0.95)]
    c_items = df_sorted[df_sorted['contribution_pct'] > 0.95]
    
    return {
        'A': a_items[['item_id', 'item_name', 'sold_last_week']].to_dict('records'),
        'B': b_items[['item_id', 'item_name', 'sold_last_week']].to_dict('records'),
        'C': c_items[['item_id', 'item_name', 'sold_last_week']].to_dict('records'),
        'analysis': {
            'total_items': len(df),
            'a_count': len(a_items),
            'b_count': len(b_items),
            'c_count': len(c_items),
            'a_contribution': round(a_items['sold_last_week'].sum() / df['sold_last_week'].sum() * 100, 1) if len(a_items) > 0 else 0
        }
    }

def generate_reorder_recommendations(low_stock: pd.DataFrame, df: pd.DataFrame) -> List[Dict]:
    """Generate intelligent reorder recommendations"""
    
    recommendations = []
    
    for _, item in low_stock.iterrows():
        # Calculate recommended order quantity
        avg_weekly_sales = item['sold_last_week']
        safety_stock = max(avg_weekly_sales * 2, item['reorder_level'])
        recommended_qty = int(safety_stock * 1.5 - item['stock_level'])
        
        # Priority based on sales velocity and urgency
        priority = 'HIGH' if item['urgency'] in ['CRITICAL', 'HIGH'] else 'MEDIUM'
        
        rec = {
            'item_id': item['item_id'],
            'item_name': item['item_name'],
            'current_stock': item['stock_level'],
            'reorder_level': item['reorder_level'],
            'recommended_quantity': max(recommended_qty, item['reorder_level']),
            'urgency': item['urgency'],
            'priority': priority,
            'reason': f"Stock at {item['stock_level']} units, reorder at {item['reorder_level']} units"
        }
        
        recommendations.append(rec)
    
    return recommendations[:10]  # Return top 10 recommendations

def generate_business_insights(df: pd.DataFrame, low_stock: pd.DataFrame, top_sellers: pd.DataFrame) -> List[str]:
    """Generate actionable business insights"""
    
    insights = []
    
    # Low stock insights
    low_stock_pct = len(low_stock) / len(df) * 100 if len(df) > 0 else 0
    if low_stock_pct > 20:
        insights.append(f"⚠️ {low_stock_pct:.1f}% of inventory is below reorder level - consider reviewing ordering patterns")
    
    # Top seller insights
    if len(top_sellers) > 0:
        top_seller = top_sellers.iloc[0]
        insights.append(f"🏆 Top performer: {top_seller['item_name']} with {top_seller['sold_last_week']} units sold this week")
    
    # Dead stock insights
    dead_stock = df[df['sold_last_week'] == 0]
    dead_stock_pct = len(dead_stock) / len(df) * 100 if len(df) > 0 else 0
    if dead_stock_pct > 30:
        insights.append(f"💀 {dead_stock_pct:.1f}% of items had zero sales - consider discontinuing or promoting")
    
    # Inventory turnover insight
    if df['sold_last_week'].sum() > 0:
        turnover_rate = df['sold_last_week'].sum() / df['stock_level'].sum() if df['stock_level'].sum() > 0 else 0
        insights.append(f"📊 Weekly inventory turnover rate: {turnover_rate:.2f}")
    
    return insights

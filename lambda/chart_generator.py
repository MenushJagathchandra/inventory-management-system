import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import pandas as pd
import numpy as np
import logging
from io import BytesIO
from typing import Dict, List
import uuid

logger = logging.getLogger(__name__)

# Set style for professional charts
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")

def generate_comprehensive_charts(df: pd.DataFrame, analysis_results: Dict) -> Dict[str, BytesIO]:
    """
    Generate multiple professional charts for inventory dashboard
    
    Returns:
        Dictionary with chart names as keys and BytesIO objects as values
    """
    
    charts = {}
    
    try:
        # 1. Stock Levels Overview
        charts['stock_levels'] = create_stock_levels_chart(df)
        
        # 2. Top Sellers Chart
        charts['top_sellers'] = create_top_sellers_chart(df)
        
        # 3. Low Stock Alert Chart
        charts['low_stock_alerts'] = create_low_stock_chart(df)
        
        # 4. Inventory Health Dashboard
        charts['inventory_health'] = create_inventory_health_dashboard(analysis_results)
        
        # 5. ABC Analysis Chart
        charts['abc_analysis'] = create_abc_analysis_chart(analysis_results)
        
        # 6. Stockout Risk Timeline
        charts['stockout_timeline'] = create_stockout_timeline_chart(df)
        
        logger.info("Successfully generated all charts")
        return charts
        
    except Exception as e:
        logger.error(f"Chart generation failed: {str(e)}")
        raise

def create_stock_levels_chart(df: pd.DataFrame) -> BytesIO:
    """Create stock levels bar chart with reorder indicators"""
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Get top 15 items by stock level
    top_items = df.nlargest(15, 'stock_level').copy()
    
    # Color based on stock status
    colors = []
    for _, row in top_items.iterrows():
        if row['stock_level'] <= row['reorder_level']:
            colors.append('#E74C3C')  # Red for low stock
        elif row['stock_level'] <= row['reorder_level'] * 1.5:
            colors.append('#F39C12')  # Orange for caution
        else:
            colors.append('#27AE60')  # Green for healthy
    
    # Create horizontal bar chart
    bars = ax.barh(top_items['item_name'], top_items['stock_level'], color=colors, alpha=0.8)
    
    # Add reorder level indicators
    for i, (_, row) in enumerate(top_items.iterrows()):
        ax.axvline(x=row['reorder_level'], ymin=i/len(top_items), 
                  ymax=(i+1)/len(top_items), color='red', linestyle='--', alpha=0.5, linewidth=2)
    
    # Formatting
    ax.set_title('Inventory Stock Levels (Top 15 Items)', fontsize=16, fontweight='bold', pad=20)
    ax.set_xlabel('Stock Level (Units)', fontsize=12)
    ax.set_ylabel('Product Name', fontsize=12)
    
    # Add legend
    legend_elements = [
        plt.Rectangle((0,0),1,1, facecolor='#27AE60', alpha=0.8, label='Healthy Stock'),
        plt.Rectangle((0,0),1,1, facecolor='#F39C12', alpha=0.8, label='Caution'),
        plt.Rectangle((0,0),1,1, facecolor='#E74C3C', alpha=0.8, label='Below Reorder'),
        plt.Line2D([0], [0], color='red', linestyle='--', alpha=0.5, linewidth=2, label='Reorder Level')
    ]
    ax.legend(handles=legend_elements, loc='lower right')
    
    # Add value labels on bars
    for i, bar in enumerate(bars):
        width = bar.get_width()
        ax.text(width + width*0.01, bar.get_y() + bar.get_height()/2, 
                f'{int(width)}', ha='left', va='center', fontweight='bold')
    
    plt.tight_layout()
    
    # Save to BytesIO
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    plt.close()
    
    return buf

def create_top_sellers_chart(df: pd.DataFrame) -> BytesIO:
    """Create top sellers chart with sales velocity"""
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    
    # Top 10 sellers by units sold
    top_sellers = df.nlargest(10, 'sold_last_week')
    
    # Bar chart for units sold
    bars1 = ax1.bar(range(len(top_sellers)), top_sellers['sold_last_week'], 
                    color='#3498DB', alpha=0.8)
    ax1.set_title('Top 10 Sellers (Units Sold)', fontsize=14, fontweight='bold')
    ax1.set_xlabel('Product Rank', fontsize=12)
    ax1.set_ylabel('Units Sold (Last 7 Days)', fontsize=12)
    ax1.set_xticks(range(len(top_sellers)))
    ax1.set_xticklabels(top_sellers['item_name'], rotation=45, ha='right')
    
    # Add value labels
    for i, bar in enumerate(bars1):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, height + height*0.01,
                f'{int(height)}', ha='center', va='bottom', fontweight='bold')
    
    # Pie chart for sales distribution
    sales_data = top_sellers['sold_last_week']
    colors = plt.cm.Set3(np.linspace(0, 1, len(sales_data)))
    
    wedges, texts, autotexts = ax2.pie(sales_data, labels=top_sellers['item_name'], 
                                       autopct='%1.1f%%', colors=colors, startangle=90)
    ax2.set_title('Sales Distribution', fontsize=14, fontweight='bold')
    
    # Make percentage text bold
    for autotext in autotexts:
        autotext.set_fontweight('bold')
    
    plt.tight_layout()
    
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    plt.close()
    
    return buf

def create_low_stock_chart(df: pd.DataFrame) -> BytesIO:
    """Create low stock alert dashboard"""
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    
    # Low stock items
    low_stock = df[df['stock_level'] <= df['reorder_level']].copy()
    
    if len(low_stock) > 0:
        # Sort by urgency
        low_stock['stock_ratio'] = low_stock['stock_level'] / low_stock['reorder_level']
        low_stock = low_stock.sort_values('stock_ratio')
        
        # Bar chart showing stock vs reorder level
        x_pos = np.arange(len(low_stock))
        width = 0.35
        
        bars1 = ax1.bar(x_pos - width/2, low_stock['stock_level'], width, 
                       label='Current Stock', color='#E74C3C', alpha=0.8)
        bars2 = ax1.bar(x_pos + width/2, low_stock['reorder_level'], width, 
                       label='Reorder Level', color='#95A5A6', alpha=0.8)
        
        ax1.set_title('Low Stock Items - Current vs Reorder Level', fontsize=14, fontweight='bold')
        ax1.set_xlabel('Products', fontsize=12)
        ax1.set_ylabel('Units', fontsize=12)
        ax1.set_xticks(x_pos)
        ax1.set_xticklabels(low_stock['item_name'], rotation=45, ha='right')
        ax1.legend()
        
        # Add value labels
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2, height + height*0.01,
                        f'{int(height)}', ha='center', va='bottom', fontsize=9)
        
        # Urgency gauge
        urgency_counts = low_stock['stock_ratio'].apply(lambda x: 
            'Critical' if x <= 0.5 else 'High' if x <= 0.8 else 'Medium').value_counts()
        
        colors_gauge = ['#E74C3C', '#F39C12', '#3498DB']
        wedges, texts, autotexts = ax2.pie(urgency_counts.values, labels=urgency_counts.index,
                                          autopct='%1.0f', colors=colors_gauge[:len(urgency_counts)])
        ax2.set_title('Low Stock Urgency Distribution', fontsize=14, fontweight='bold')
        
        for autotext in autotexts:
            autotext.set_fontweight('bold')
            autotext.set_color('white')
    
    else:
        ax1.text(0.5, 0.5, 'No Low Stock Items! 🎉', ha='center', va='center', 
                transform=ax1.transAxes, fontsize=16, fontweight='bold', color='green')
        ax1.set_title('Low Stock Status', fontsize=14, fontweight='bold')
        ax2.text(0.5, 0.5, 'All Items Healthy', ha='center', va='center', 
                transform=ax2.transAxes, fontsize=14, color='green')
        ax2.set_title('Urgency Distribution', fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    plt.close()
    
    return buf

def create_inventory_health_dashboard(analysis_results: Dict) -> BytesIO:
    """Create inventory health score dashboard"""
    
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
    
    health = analysis_results.get('inventory_health', {})
    metrics = analysis_results.get('summary_metrics', {})
    
    # 1. Overall Health Score Gauge
    score = health.get('overall_score', 0)
    grade = health.get('health_grade', 'F')
    
    # Create gauge chart
    theta = np.linspace(0, np.pi, 100)
    r = 1
    
    # Background arc
    ax1.fill_between(theta, 0, r, color='lightgray', alpha=0.3)
    
    # Score arc
    score_theta = np.linspace(0, np.pi * (score/100), 100)
    color = '#27AE60' if score >= 70 else '#F39C12' if score >= 50 else '#E74C3C'
    ax1.fill_between(score_theta, 0, r, color=color, alpha=0.8)
    
    ax1.set_xlim(-1.2, 1.2)
    ax1.set_ylim(-0.2, 1.2)
    ax1.set_aspect('equal')
    ax1.axis('off')
    
    # Add score text
    ax1.text(0, 0.5, f'{score}\nGrade: {grade}', ha='center', va='center', 
            fontsize=20, fontweight='bold', color=color)
    ax1.set_title('Inventory Health Score', fontsize=14, fontweight='bold')
    
    # 2. Risk Distribution
    stockout_analysis = analysis_results.get('stockout_analysis', {})
    critical_count = len(stockout_analysis.get('critical', []))
    high_risk_count = len(stockout_analysis.get('high_risk', []))
    medium_risk_count = len(stockout_analysis.get('medium_risk', []))
    
    risk_data = [critical_count, high_risk_count, medium_risk_count]
    risk_labels = ['Critical', 'High Risk', 'Medium Risk']
    risk_colors = ['#E74C3C', '#F39C12', '#3498DB']
    
    if sum(risk_data) > 0:
        wedges, texts, autotexts = ax2.pie(risk_data, labels=risk_labels, colors=risk_colors,
                                          autopct='%1.0f', startangle=90)
        ax2.set_title('Stockout Risk Distribution', fontsize=14, fontweight='bold')
        for autotext in autotexts:
            autotext.set_fontweight('bold')
    else:
        ax2.text(0.5, 0.5, 'No Stockout Risk', ha='center', va='center', 
                transform=ax2.transAxes, fontsize=14, color='green', fontweight='bold')
        ax2.set_title('Stockout Risk Distribution', fontsize=14, fontweight='bold')
    
    # 3. Key Metrics Bar Chart
    metric_names = ['Total Items', 'Low Stock', 'Critical Risk']
    metric_values = [metrics.get('total_items', 0), metrics.get('low_stock_count', 0), 
                    metrics.get('critical_stockout_count', 0)]
    metric_colors = ['#3498DB', '#F39C12', '#E74C3C']
    
    bars = ax3.bar(metric_names, metric_values, color=metric_colors, alpha=0.8)
    ax3.set_title('Key Inventory Metrics', fontsize=14, fontweight='bold')
    ax3.set_ylabel('Count', fontsize=12)
    
    # Add value labels
    for bar in bars:
        height = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2, height + height*0.01,
                f'{int(height)}', ha='center', va='bottom', fontweight='bold')
    
    # 4. Health Components Radar Chart
    components = ['Stockout Risk', 'Low Stock', 'Sales Health']
    scores = [
        health.get('stockout_risk_score', 0),
        health.get('low_stock_score', 0),
        health.get('sales_health_score', 0)
    ]
    
    # Create simple bar chart as alternative to radar
    bars4 = ax4.bar(components, scores, color=['#27AE60', '#F39C12', '#3498DB'], alpha=0.8)
    ax4.set_title('Health Component Scores', fontsize=14, fontweight='bold')
    ax4.set_ylabel('Score (0-100)', fontsize=12)
    ax4.set_ylim(0, 100)
    
    # Add value labels
    for bar in bars4:
        height = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2, height + 1,
                f'{int(height)}', ha='center', va='bottom', fontweight='bold')
    
    plt.tight_layout()
    
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    plt.close()
    
    return buf

def create_abc_analysis_chart(analysis_results: Dict) -> BytesIO:
    """Create ABC analysis visualization"""
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    
    abc_data = analysis_results.get('abc_analysis', {})
    
    # Get counts
    a_count = len(abc_data.get('A', []))
    b_count = len(abc_data.get('B', []))
    c_count = len(abc_data.get('C', []))
    
    # 1. ABC Distribution Pie Chart
    sizes = [a_count, b_count, c_count]
    labels = ['A Items', 'B Items', 'C Items']
    colors = ['#27AE60', '#F39C12', '#95A5A6']
    
    if sum(sizes) > 0:
        wedges, texts, autotexts = ax1.pie(sizes, labels=labels, colors=colors,
                                          autopct='%1.1f%%', startangle=90)
        ax1.set_title('ABC Item Distribution', fontsize=14, fontweight='bold')
        
        for autotext in autotexts:
            autotext.set_fontweight('bold')
    
    # 2. Sales Contribution Bar Chart
    analysis_info = abc_data.get('analysis', {})
    a_contribution = analysis_info.get('a_contribution', 0)
    
    # Create stacked bar for contribution
    categories = ['Sales Contribution']
    a_contrib = [a_contribution]
    b_contrib = [100 - a_contribution]  # Simplified
    
    ax2.bar(categories, a_contrib, label='A Items', color='#27AE60', alpha=0.8)
    ax2.bar(categories, b_contrib, bottom=a_contrib, label='B & C Items', color='#95A5A6', alpha=0.8)
    
    ax2.set_title('Sales Contribution by Category', fontsize=14, fontweight='bold')
    ax2.set_ylabel('Contribution (%)', fontsize=12)
    ax2.legend()
    ax2.set_ylim(0, 100)
    
    # Add percentage text
    ax2.text(0, a_contrib[0]/2, f'{a_contribution:.1f}%', ha='center', va='center',
            fontweight='bold', color='white')
    ax2.text(0, a_contrib[0] + b_contrib[0]/2, f'{100-a_contribution:.1f}%', ha='center', va='center',
            fontweight='bold', color='white')
    
    plt.tight_layout()
    
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    plt.close()
    
    return buf

def create_stockout_timeline_chart(df: pd.DataFrame) -> BytesIO:
    """Create stockout risk timeline"""
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Calculate days until stockout
    df_timeline = df.copy()
    df_timeline['daily_sales'] = df_timeline['sold_last_week'] / 7
    df_timeline['daily_sales'] = df_timeline['daily_sales'].replace(0, 0.1)  # Avoid division by zero
    df_timeline['days_until_stockout'] = (df_timeline['stock_level'] / df_timeline['daily_sales']).round(1)
    
    # Filter items that will stockout within 30 days
    at_risk = df_timeline[df_timeline['days_until_stockout'] <= 30].copy()
    at_risk = at_risk.sort_values('days_until_stockout')
    
    if len(at_risk) > 0:
        # Create horizontal timeline
        y_pos = np.arange(len(at_risk))
        
        # Create color map based on urgency
        colors = []
        for days in at_risk['days_until_stockout']:
            if days <= 7:
                colors.append('#E74C3C')  # Critical - Red
            elif days <= 14:
                colors.append('#F39C12')  # High - Orange
            else:
                colors.append('#3498DB')  # Medium - Blue
        
        bars = ax.barh(y_pos, at_risk['days_until_stockout'], color=colors, alpha=0.8)
        
        # Formatting
        ax.set_title('Stockout Risk Timeline (Next 30 Days)', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Days Until Stockout', fontsize=12)
        ax.set_ylabel('Products', fontsize=12)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(at_risk['item_name'])
        
        # Add vertical lines for risk thresholds
        ax.axvline(x=7, color='red', linestyle='--', alpha=0.5, linewidth=2, label='Critical (7 days)')
        ax.axvline(x=14, color='orange', linestyle='--', alpha=0.5, linewidth=2, label='High Risk (14 days)')
        
        # Add value labels
        for i, bar in enumerate(bars):
            width = bar.get_width()
            ax.text(width + width*0.01, bar.get_y() + bar.get_height()/2,
                    f'{width:.1f} days', ha='left', va='center', fontweight='bold')
        
        ax.legend(loc='lower right')
        
        # Add risk zones
        ax.axvspan(0, 7, alpha=0.1, color='red', label='Critical Zone')
        ax.axvspan(7, 14, alpha=0.1, color='orange', label='High Risk Zone')
        
    else:
        ax.text(0.5, 0.5, 'No Stockout Risk in Next 30 Days! 🎉', 
                ha='center', va='center', transform=ax.transAxes, 
                fontsize=16, fontweight='bold', color='green')
        ax.set_title('Stockout Risk Timeline', fontsize=16, fontweight='bold')
    
    plt.tight_layout()
    
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    plt.close()
    
    return buf

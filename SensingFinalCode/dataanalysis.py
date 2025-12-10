import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import numpy as np

# plot styling
sns.set_style("whitegrid")
plt.rcParams['figure.facecolor'] = 'white'
plt.rcParams['axes.facecolor'] = 'white'
plt.rcParams['font.size'] = 10
plt.rcParams['axes.labelsize'] = 11
plt.rcParams['axes.titlesize'] = 12
plt.rcParams['xtick.labelsize'] = 9
plt.rcParams['ytick.labelsize'] = 9

# Loads the data 
with open('smartplantsensor-default-rtdb-export.json', 'r') as f:
    data = json.load(f)


logs = data['plants']['plant1']['logs']
df = pd.DataFrame.from_dict(logs, orient='index')

df = df.sort_values('timestamp')

# Separate the two types of timestamps
THRESHOLD = 10_000_000_000  
df['is_unix_timestamp'] = df['timestamp'] > THRESHOLD

if df['is_unix_timestamp'].any():
    # We have real timestamps, use those
    df['datetime'] = pd.NaT
    df.loc[df['is_unix_timestamp'], 'datetime'] = pd.to_datetime(df.loc[df['is_unix_timestamp'], 'timestamp'], unit='ms')
    
    # For device uptime entries, estimate their datetime based on the pattern
    # Use the first Unix timestamp as reference
    first_unix_idx = df[df['is_unix_timestamp']].index[0]
    first_unix_time = df.loc[first_unix_idx, 'datetime']
    first_unix_timestamp_val = df.loc[first_unix_idx, 'timestamp']
    
    # Fill in missing datetimes by using index order
    df['datetime'] = df['datetime'].ffill().bfill()
    
    # Create clean time labels
    df['time_label'] = df['datetime'].dt.strftime('%Y-%m-%d %H:%M')
else:
    # Only device uptime, use hours from start
    df['seconds_from_start'] = df['timestamp'] - df['timestamp'].min()
    df['hours_from_start'] = df['seconds_from_start'] / 3600
    df['datetime'] = pd.to_datetime('2025-01-01') + pd.to_timedelta(df['seconds_from_start'], unit='s')
    df['time_label'] = df['hours_from_start'].apply(lambda x: f'{x:.1f}h')

# Calculate rolling averages for smoother trends
df['soil_smooth'] = df['soil_raw'].rolling(window=5, min_periods=1).mean()
df['light_smooth'] = df['light_raw'].rolling(window=5, min_periods=1).mean()
df['temp_smooth'] = df['temp_c'].rolling(window=5, min_periods=1).mean()
df['hum_smooth'] = df['hum'].rolling(window=5, min_periods=1).mean()

# Basic statistics
print("=== MONITORING PERIOD ===")
print(f"Start: {df['datetime'].min()}")
print(f"End: {df['datetime'].max()}")
duration_hours = (df['datetime'].max() - df['datetime'].min()).total_seconds() / 3600
print(f"Total duration: {duration_hours:.1f} hours ({duration_hours/24:.1f} days)")
print(f"Number of readings: {len(df)}")

print("\n=== SENSOR STATISTICS ===")
print(df[['soil_raw', 'light_raw', 'temp_c', 'hum']].describe())

# Mood distribution
print("\n=== MOOD DISTRIBUTION ===")
print(df['mood'].value_counts())

# Correlation matrix
print("\n=== CORRELATIONS ===")
corr = df[['soil_raw', 'light_raw', 'temp_c', 'hum']].corr()
print(corr)

# IMPROVED VISUALIZATIONS

# Figure 1: Time series (4 subplots) with better styling
fig, axes = plt.subplots(4, 1, figsize=(14, 12))
fig.suptitle('Plant Sensor Readings Over Time', fontsize=16, fontweight='bold', y=0.995)

# Soil Moisture
axes[0].plot(df['datetime'], df['soil_raw'], alpha=0.3, color='gray', linewidth=0.5, label='Raw Data')
axes[0].plot(df['datetime'], df['soil_smooth'], color='#8B4513', linewidth=2, label='Smoothed')
axes[0].set_ylabel('Soil Moisture (raw)', fontweight='bold')
axes[0].set_title('Soil Moisture Level', fontsize=11, pad=10)
axes[0].legend(loc='upper right')
axes[0].grid(True, alpha=0.3)

# Light Intensity
axes[1].plot(df['datetime'], df['light_raw'], alpha=0.3, color='gray', linewidth=0.5, label='Raw Data')
axes[1].plot(df['datetime'], df['light_smooth'], color='#FFD700', linewidth=2, label='Smoothed')
axes[1].set_ylabel('Light Intensity (raw)', fontweight='bold')
axes[1].set_title('Light Exposure', fontsize=11, pad=10)
axes[1].legend(loc='upper right')
axes[1].grid(True, alpha=0.3)

# Temperature
axes[2].plot(df['datetime'], df['temp_c'], alpha=0.3, color='gray', linewidth=0.5, label='Raw Data')
axes[2].plot(df['datetime'], df['temp_smooth'], color='#FF6347', linewidth=2, label='Smoothed')
axes[2].set_ylabel('Temperature (°C)', fontweight='bold')
axes[2].set_title('Temperature', fontsize=11, pad=10)
axes[2].legend(loc='upper right')
axes[2].grid(True, alpha=0.3)

# Humidity
axes[3].plot(df['datetime'], df['hum'], alpha=0.3, color='gray', linewidth=0.5, label='Raw Data')
axes[3].plot(df['datetime'], df['hum_smooth'], color='#4169E1', linewidth=2, label='Smoothed')
axes[3].set_ylabel('Humidity (%)', fontweight='bold')
axes[3].set_xlabel('Date & Time', fontweight='bold')
axes[3].set_title('Humidity', fontsize=11, pad=10)
axes[3].legend(loc='upper right')
axes[3].grid(True, alpha=0.3)

# Format x-axis for all subplots
for ax in axes:
    ax.tick_params(axis='x', rotation=45)
    # Auto-format dates
    import matplotlib.dates as mdates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    
plt.tight_layout()
plt.savefig('time_series.png', dpi=300, bbox_inches='tight')
print("\n✓ Saved: time_series.png")

# Figure 2: Correlation heatmap 
plt.figure(figsize=(10, 8))
sns.heatmap(corr, annot=True, cmap='RdYlGn', center=0, 
            square=True, linewidths=1, cbar_kws={"shrink": 0.8},
            fmt='.2f', annot_kws={'size': 11})
plt.title('Sensor Correlation Matrix', fontsize=14, fontweight='bold', pad=20)
plt.tight_layout()
plt.savefig('correlation_heatmap.png', dpi=300, bbox_inches='tight')
print("✓ Saved: correlation_heatmap.png")

# Figure 3: Mood distribution 
plt.figure(figsize=(10, 8))
mood_counts = df['mood'].value_counts()
colors = ['#90EE90', '#FFD700', '#FF6347', '#87CEEB']  # Green, Gold, Red, Blue
plt.pie(mood_counts, labels=mood_counts.index, autopct='%1.1f%%', 
        startangle=90, colors=colors[:len(mood_counts)],
        textprops={'fontsize': 12, 'weight': 'bold'},
        explode=[0.05] * len(mood_counts))
plt.title('Plant Mood Distribution', fontsize=14, fontweight='bold', pad=20)
plt.savefig('mood_distribution.png', dpi=300, bbox_inches='tight')
print("✓ Saved: mood_distribution.png")

# Figure 4: Combined overview dashboard
fig = plt.figure(figsize=(16, 10))
gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

# Main time series
ax1 = fig.add_subplot(gs[0:2, :])
ax1_twin1 = ax1.twinx()
ax1_twin2 = ax1.twinx()
ax1_twin3 = ax1.twinx()

ax1_twin2.spines['right'].set_position(('outward', 60))
ax1_twin3.spines['right'].set_position(('outward', 120))

p1 = ax1.plot(df['datetime'], df['soil_smooth'], color='#8B4513', linewidth=2, label='Soil Moisture')
p2 = ax1_twin1.plot(df['datetime'], df['light_smooth'], color='#FFD700', linewidth=2, label='Light')
p3 = ax1_twin2.plot(df['datetime'], df['temp_smooth'], color='#FF6347', linewidth=2, label='Temperature')
p4 = ax1_twin3.plot(df['datetime'], df['hum_smooth'], color='#4169E1', linewidth=2, label='Humidity')

ax1.set_xlabel('Date & Time', fontweight='bold')
# datetime on x-axis
import matplotlib.dates as mdates
ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
ax1.set_ylabel('Soil Moisture', color='#8B4513', fontweight='bold')
ax1_twin1.set_ylabel('Light Intensity', color='#FFD700', fontweight='bold')
ax1_twin2.set_ylabel('Temperature (°C)', color='#FF6347', fontweight='bold')
ax1_twin3.set_ylabel('Humidity (%)', color='#4169E1', fontweight='bold')

ax1.tick_params(axis='y', labelcolor='#8B4513')
ax1_twin1.tick_params(axis='y', labelcolor='#FFD700')
ax1_twin2.tick_params(axis='y', labelcolor='#FF6347')
ax1_twin3.tick_params(axis='y', labelcolor='#4169E1')

ax1.set_title('All Sensors Overview', fontsize=13, fontweight='bold', pad=10)
ax1.grid(True, alpha=0.3)

#  legend
lines = p1 + p2 + p3 + p4
labels = [l.get_label() for l in lines]
ax1.legend(lines, labels, loc='upper left')

# Bottom left: Mood pie chart
ax2 = fig.add_subplot(gs[2, 0])
mood_counts.plot(kind='pie', ax=ax2, autopct='%1.1f%%', 
                 colors=colors[:len(mood_counts)],
                 textprops={'fontsize': 9})
ax2.set_ylabel('')
ax2.set_title('Mood Distribution', fontweight='bold')

# Bottom middle: Statistics summary
ax3 = fig.add_subplot(gs[2, 1])
ax3.axis('off')
stats_text = f"""
SENSOR STATISTICS

Soil Moisture:
  Avg: {df['soil_raw'].mean():.1f}
  Min: {df['soil_raw'].min():.1f}
  Max: {df['soil_raw'].max():.1f}

Light Intensity:
  Avg: {df['light_raw'].mean():.1f}
  Min: {df['light_raw'].min():.1f}
  Max: {df['light_raw'].max():.1f}

Temperature (°C):
  Avg: {df['temp_c'].mean():.1f}
  Min: {df['temp_c'].min():.1f}
  Max: {df['temp_c'].max():.1f}

Humidity (%):
  Avg: {df['hum'].mean():.1f}
  Min: {df['hum'].min():.1f}
  Max: {df['hum'].max():.1f}
"""
ax3.text(0.1, 0.5, stats_text, fontsize=9, verticalalignment='center',
         fontfamily='monospace', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
ax3.set_title('Statistics Summary', fontweight='bold')

# Bottom right: Correlation mini heatmap
ax4 = fig.add_subplot(gs[2, 2])
sns.heatmap(corr, annot=True, cmap='RdYlGn', center=0, ax=ax4,
            square=True, cbar=False, fmt='.2f', annot_kws={'size': 8})
ax4.set_title('Correlations', fontweight='bold')

fig.suptitle('Plant Sensor Dashboard', fontsize=16, fontweight='bold')
plt.savefig('dashboard_overview.png', dpi=300, bbox_inches='tight')
print("saved dashboard_overview.png")
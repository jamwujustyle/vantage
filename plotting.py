import matplotlib
matplotlib.use('Agg') # Non-interactive backend
import matplotlib.pyplot as plt
import io
from typing import List
from youtube_client import Video
from matplotlib.ticker import FuncFormatter

def format_axis(x, pos):
    if x >= 1_000_000:
        return f'{x*1e-6:.1f}M'
    elif x >= 1_000:
        return f'{x*1e-3:.0f}K'
    return f'{int(x)}'

def generate_comparison_chart(channels_data: List[dict]) -> bytes:
    """
    Generates a bar chart comparing top video views.
    channels_data: list of dicts {'title': str, 'videos': List[Video]}
    """
    with plt.style.context('dark_background'):
        fig, ax = plt.subplots(figsize=(10, 6))

        names = []
        top_views = []

        for data in channels_data:
            if not data['videos']:
                continue
            # Take the top video
            top_video = data['videos'][0]
            names.append(data['title'][:15]) # Truncate long names
            top_views.append(top_video.view_count)

        if not names:
            plt.close(fig)
            return None

        # Gold color for bars
        bars = ax.bar(names, top_views, color='#FFD700', edgecolor='white', alpha=0.8)

        ax.set_title('Top Video Views Comparison', color='white', fontsize=14, pad=20)
        ax.set_xlabel('Channel', color='white', fontsize=12)
        ax.set_ylabel('Views', color='white', fontsize=12)

        # Rotate x labels
        plt.xticks(rotation=45, ha='right', color='white')
        plt.yticks(color='white')

        # Remove top and right spines
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # Grid
        ax.grid(axis='y', linestyle='--', alpha=0.3, color='gray')

        # Format Y axis to normal numbers
        ax.yaxis.set_major_formatter(FuncFormatter(format_axis))

        # Add value labels
        for bar in bars:
            height = bar.get_height()
            label = format_axis(height, None)
            ax.text(bar.get_x() + bar.get_width()/2., height,
                    label,
                    ha='center', va='bottom', color='white', fontweight='bold')

        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close(fig)

        return buf.getvalue()

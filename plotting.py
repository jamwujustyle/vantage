import matplotlib.pyplot as plt
import io
from typing import List
from youtube_client import Video

def generate_comparison_chart(channels_data: List[dict]) -> bytes:
    """
    Generates a bar chart comparing top video views.
    channels_data: list of dicts {'title': str, 'videos': List[Video]}
    """
    plt.figure(figsize=(10, 6))

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
        return None

    bars = plt.bar(names, top_views, color='skyblue')

    plt.title('Top Video Views Comparison')
    plt.xlabel('Channel')
    plt.ylabel('Views')
    plt.xticks(rotation=45)

    # Format Y axis to normal numbers
    plt.ticklabel_format(style='plain', axis='y')

    # Add value labels
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height):,}',
                ha='center', va='bottom')

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()

    return buf.getvalue()

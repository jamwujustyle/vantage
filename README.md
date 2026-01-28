# YT-Vantage Bot 🚀

**YT-Vantage** is a high-efficiency Telegram bot designed to provide deep insights into YouTube channels. It allows users to compare top VODs and Shorts, visualize performance with charts, and track engagement metrics like Engagement Rate (ER).

## ✨ Features

*   **Compare Top Videos**: Instantly compare the top 3 most-watched VODs or Shorts from multiple channels.
*   **Visual Graphs**: Generates beautiful dark-mode bar charts for easy comparison.
*   **Rich Analytics**: Displays detailed metrics including Views (👁️), Likes (👍), Comments (💬), and Engagement Rate (📈).
*   **Favorites System**: Save your favorite creators for quick access.
*   **Optimized Performance**:
    *   **Smart Caching**: Caches results for 6 hours and channel IDs for 30 days to save API quota.
    *   **Efficient API Usage**: Uses playlist ID swapping for VODs to minimize quota consumption.
    *   **Non-Blocking**: Fully asynchronous architecture ensuring high responsiveness.

## 🛠 Prerequisites

*   **Python 3.10+** (if running manually)
*   **Docker & Docker Compose** (recommended for deployment)
*   **Telegram Bot Token**: Get one from [@BotFather](https://t.me/BotFather).
*   **YouTube Data API Key**: Enable "YouTube Data API v3" in [Google Cloud Console](https://console.cloud.google.com/).

## 🚀 Setup & Launch

### Option 1: Docker (Recommended)

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-repo/yt-vantage.git
    cd yt-vantage
    ```

2.  **Configure Environment:**
    Create a `.env` file in the root directory:
    ```ini
    BOT_TOKEN=your_telegram_bot_token
    YOUTUBE_API_KEY=your_youtube_api_key
    DB_PATH=/data/bot_data.db
    ```

3.  **Launch:**
    ```bash
    docker-compose up -d
    ```
    The bot will start and persist data in a Docker volume.

### Option 2: Manual Installation

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Configure Environment:**
    Create a `.env` file:
    ```ini
    BOT_TOKEN=your_telegram_bot_token
    YOUTUBE_API_KEY=your_youtube_api_key
    DB_PATH=bot_data.db
    ```

3.  **Run:**
    ```bash
    python bot.py
    ```

## 🎮 Usage

| Command | Description | Example |
| :--- | :--- | :--- |
| `/start` | Welcome message and instructions. | `/start` |
| `/compare` | Compare top videos/shorts. Supports quoted names. | `/compare PewDiePie "MrBeast Gaming"` |
| `/favorites` | List your saved channels. | `/favorites` |
| `/add` | Add a channel to your favorites. | `/add PewDiePie` |
| `/remove` | Remove a channel from favorites. | `/remove PewDiePie` |

**Interactive Features:**
*   Use the **"Switch to Shorts/VODs"** button to toggle the view.
*   Use **"⭐ Add to Favorites"** on reports to quickly save channels.

## 🏗 Technology Stack

*   **Framework**: [aiogram v3](https://docs.aiogram.dev/)
*   **API**: YouTube Data API v3 (via `google-api-python-client`)
*   **Database**: SQLite (via `aiosqlite`)
*   **Validation**: Pydantic
*   **Visualization**: Matplotlib

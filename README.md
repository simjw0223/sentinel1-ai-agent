# Sentinel-1 AI Agent

Interactive satellite data download chatbot powered by LangChain and Streamlit. Chat in natural language to search and download Sentinel-1 SAR imagery automatically.
<p align="center">
  <img src="https://github.com/user-attachments/assets/a38c1dda-f12c-4d97-bc84-6d330766b2fb" width="750" />
</p>

---

## Features

- Chat-based interface using Streamlit
- LangChain Agent with GPT-4o-mini for intelligent tool selection
- Automated satellite data search and download
- Extracts location (lat/lon) and date from natural language queries
- Searches Sentinel-1 GRD scenes via STAC API
- Downloads VV/VH polarization bands automatically
- Dual interface modes: Chat Agent and Direct Download
- Real satellite data from AWS Element84 STAC

---

## Tech Stack

- Python
- Streamlit - chat UI
- OpenAI API - GPT-4o-mini
- LangChain - agent framework and tool integration
- pystac-client - STAC API for satellite data search
- python-dotenv - environment variable management

---

## How It Works

1. User sends a natural language request in the chat UI
2. LangChain agent receives the message with access to satellite download tools
3. GPT-4o-mini extracts location (latitude, longitude) and date from the query
4. Agent calls the tool with extracted parameters
5. Tool searches STAC API for Sentinel-1 GRD scenes within ±10 days
6. Selects the scene closest to the requested date
7. Downloads VV and VH polarization GeoTIFF files to local directory
8. Agent synthesizes download results into natural language response

---

## Installation

Clone the repository:
```bash
git clone https://github.com/yourusername/sentinel1-ai-agent.git
cd sentinel1-ai-agent
```

Install dependencies:
```bash
pip install -r requirements.txt
```

Set up environment variables:
```bash
cp .env.example .env
```

Edit `.env` and add your OpenAI API key:
```
OPENAI_API_KEY=your_api_key_here
```

---

## Usage

Run the Streamlit app:
```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

### Chat Agent Mode

Type natural language requests like:
- "Download Sentinel-1 data near Seoul from May 2024"
- "부산 근처 2023년 6월 1일 Sentinel-1 내려줘"
- "Get Sentinel-1 imagery for Jeju Island on 2024-03-15"

### Direct Download Mode

Manually input:
- Latitude and longitude coordinates
- Target date
- Search range (±days)

---

## Project Structure

```
sentinel1-ai-agent/
├── app.py              # Main application
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variables template
├── .gitignore         # Git ignore rules
└── README.md          # Project documentation
```

---

## Configuration

Default settings in the app:
- Search range: ±10 days from target date
- Spatial range: ±0.2° (~20km) from target coordinates
- Model: GPT-4o-mini
- Data source: AWS Element84 STAC (Sentinel-1 GRD)

Environment variables (`.env`):
```bash
OPENAI_API_KEY=your_openai_api_key
SAVE_DIR=./downloads  # Optional, defaults to ./downloads
```

---

## Data Information

Sentinel-1 GRD (Ground Range Detected):
- Sensor: C-band SAR (5.405 GHz)
- Spatial resolution: 10m × 10m
- Polarization: VV, VH (or HH, HV)
- Revisit time: 6 days (Sentinel-1A/B combined)
- Data format: GeoTIFF
- Data provider: ESA Copernicus (free and open)

---

## Example Queries

English:
- "Download Sentinel-1 near Busan on June 1, 2023"
- "Get SAR imagery for coordinates 37.5665, 126.9780 from May 2024"

Korean:
- "서울 근처 2024년 5월 28일 Sentinel-1 내려줘"
- "제주도 2023년 여름 센티널 영상 필요해"

---

## Acknowledgments

- LangChain - LLM application framework
- Streamlit - Web app framework
- Element84 - STAC API provider
- ESA Copernicus - Sentinel-1 data provider

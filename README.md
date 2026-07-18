# Adaptive Weekly Meal Planner

A globally configurable weekly meal-planning system for households, schools, workers, and community programmes. It creates practical meal plans from local foods, household size, market observations, and user-confirmed availability.

## See it in a browser

The fastest way to understand the result is the responsive browser dashboard. It needs Python 3.10 or newer and no third-party packages.

```bash
git clone https://github.com/True-African/Adaptive-Weekly-Meal-Planner.git
cd Adaptive-Weekly-Meal-Planner
python web_app.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) on the computer. Enter a location, household members, and any foods confirmed by a local person. The dashboard presents:

- the seven-day meal plan first;
- household-scaled budget estimates;
- price coverage and provisional-price labels;
- local food confirmation and substitutions;
- optional mapped food-access places from OpenStreetMap.

The demonstration-price checkbox is only for testing the interface. Replace it with current local market observations before using the budget for decisions.

### View it on a mobile phone

The Python server runs on the **computer**. The phone only opens the dashboard in its browser.

1. Connect the computer and phone to the same trusted Wi-Fi network.
2. On the computer, from the repository folder, run:

```bash
python web_app.py --host 0.0.0.0 --port 8000
```

3. On the computer, find its local IPv4 address with `ipconfig` on Windows or `ip addr` on Linux/macOS.
4. On the phone, open the computer's address in Chrome, Safari, or another browser:

```text
http://COMPUTER_IP:8000
```

For example, if the computer shows `192.168.1.25`, enter `http://192.168.1.25:8000` on the phone. Keep the computer's terminal and server running while using the dashboard. The layout adapts to the phone screen. For public use, deploy behind HTTPS and an authenticated production server instead of exposing the development server.

## Use the command-line engine

```bash
python scripts/adaptive_meal_planner.py \
  --location "Your city or district" \
  --household adult_man:1 adult_woman:2 child_2_5:1
```

The planner always returns a seven-day plan. If location discovery is incomplete, interactive users are prompted to ask a trusted local person about missing food groups. Non-interactive runs use clearly labelled fallback foods.

## Detailed documentation

See [docs/DETAILED_GUIDE.md](docs/DETAILED_GUIDE.md) for:

- command-line options and local confirmation;
- market CSV format and budget logic;
- household quantity factors;
- location adaptation and fallback rules;
- OpenStreetMap usage and attribution;
- automation, offline deployment, and Hugging Face adaptation;
- safety boundaries and testing commands.

## Package contents

- `web_app.py`: dependency-free browser API and local server.
- `web/index.html`: responsive dashboard for desktop and mobile browsers.
- `scripts/adaptive_meal_planner.py`: reference planning and budgeting engine.
- `scripts/location_discovery.py`: geocoding and food-access discovery adapter.
- `skills/adaptive-weekly-meal-planner/SKILL.md`: reusable planning skill.
- `examples/`: local profile and market-data templates.
- `tests/`: regression tests.

## Safety

This is a general planning and budgeting aid. It does not diagnose disease or replace clinical nutrition care. Seek qualified professional advice for medical, pregnancy, allergy, severe malnutrition, or child growth concerns.

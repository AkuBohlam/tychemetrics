name: TycheMetrics Quantitative Scanner

on:
  schedule:
    - cron: '*/15 * * * *'
  workflow_dispatch:

jobs:
  run-scanner:
    runs-on: ubuntu-latest
    permissions:
      contents: write # Izin krusial agar bot bisa menulis & menyimpan memori

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install yfinance pandas requests

      - name: Run Algorithm
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python scanner.py

      - name: Save Bot Memory (Auto-Commit)
        run: |
          git config --global user.name 'github-actions[bot]'
          git config --global user.email 'github-actions[bot]@users.noreply.github.com'
          git add signals.json
          git commit -m "🤖 Auto-update bot memory state" || echo "Tidak ada perubahan memori"
          git push

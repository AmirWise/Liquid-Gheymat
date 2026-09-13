# 💧 Liquid Gheymat - Currency Tracker
A modern currency tracker with Liquid Glass design, vivid colors, and dynamic blur effects.

> [!IMPORTANT]
> ## 📦 This project has moved
> **Liquid Gheymat has been renamed and rewritten as [Gheymat Morabba](https://github.com/AmirWise/GheymatMorabba).**
>
> The project now continues in its **new home** — the code, the roadmap, and all future releases live there.
>
> 👉 **Please use the new repository going forward:**
> **➡️ [github.com/AmirWise/GheymatMorabba](https://github.com/AmirWise/GheymatMorabba)**
>
> - New releases, fixes, and feature work ship in the new repo
> - Open issues and pull requests in the new repo
> - Clone from the new repo:
>
> ```bash
> git clone https://github.com/AmirWise/GheymatMorabba.git
> ```
>
> This repository is kept **read-only for reference** and will no longer receive updates.

| Language | زبان |
|----------|------|
| [English](README.md) | [فارسی](README.fa.md) |


**Version:** 4.0.0 (legacy)  
**Author:** AmirWise  
**Repository (new home):** [github.com/AmirWise/GheymatMorabba](https://github.com/AmirWise/GheymatMorabba)


A clean, modern desktop currency/crypto/metal tracker with a liquid-glass UI, fast updates, and useful tools for daily monitoring.

> **Note:** Everything below describes the legacy v4.0.0 codebase. For the current version (v5.0.0) and up, see [Gheymat Morabba](https://github.com/AmirWise/GheymatMorabba).

## ✨ What's New in v4.0.0

- Much faster UI updates — cards are reused instead of rebuilding everything
- Full portfolio management (add/remove currencies, drag-to-sort)
- Searchable currency selector
- Market overview section (top gainers & losers)
- Instant startup using local cache (first paint in <1s)
- Improved auto-refresh system (Tkinter-based scheduler)
- Export selected items to CSV or copy to clipboard
- Settings panel (refresh interval, price alerts, notifications, cache management)
- More robust API handling (retries, circuit breaker, in-memory fallback)
- Desktop widgets & compact mode support
- Price history sparklines and quick converter

> This README matches the legacy codebase (v4.0.0).

## ⚠️ Notice

The API used in the source code and the release version are different.
To use the full features of the application, please download the release version.
If you have your own API, use the source code.

> **Looking for the latest version?** The project has moved to [Gheymat Morabba](https://github.com/AmirWise/GheymatMorabba).

## 🚀 Quick Start

### Prerequisites
- Windows 10 (build 1903+) or Windows 11 (recommended)
- Python 3.8+

### Installation
```bash
git clone https://github.com/AmirWise/GheymatMorabba.git
cd Gheymat-Morabba
pip install -r requirements.txt
python main.py
```

### Notes
- On first launch the app loads instantly from local SQLite cache, then fetches fresh data in the background.
- Desktop widgets work on Windows (other platforms run the main window only).

## 🧭 Project Structure
```
Liquid-Gheymat/
├── main.py              # Entry point & core application
├── requirements.txt     # Dependencies
├── README.md            # English documentation
├── README.fa.md         # Persian documentation
├── LICENSE              # MIT License
└── assets/
    ├── fonts/
    │   └── Vazirmatn-Regular.ttf
    └── icons/
        └── icon.ico
```

## 🛠️ Contributing

Contributions are welcome!

> Please open contributions in the new repository — [Gheymat Morabba](https://github.com/AmirWise/GheymatMorabba).

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "Add your feature"`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request

Please keep the code style consistent and add comments where helpful.

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for details.

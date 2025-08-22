# 💧 Liquid Gheymat - Currency Tracker

A **modern currency tracker** with **Liquid Glass design**, vivid colors, and dynamic blur effects.

![Style](https://img.shields.io/badge/Style-Liquid%20Glass-blue) ![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-green) ![Python](https://img.shields.io/badge/Python-3.8%2B-yellow)
‌
## ✨ Features

- **Liquid Glass UI** – Smooth transparency, vivid 3D highlights and shadows  
- **Real-time currency tracking** – USD, EUR, BTC, ETH and more  
- **Dynamic blur effects** – Works best with Windows transparency enabled  
- **Auto Dark/Light mode** – Matches your system theme automatically  
- **Persian font support** – Beautiful Vazirmatn rendering out of the box  

## 🖼 Screenshots

*(Add your preview images here – for example:)*  
![Preview1](images/firstpic.png)  
![Preview2](images/secondpic.png)  

## 🚀 Installation

### Prerequisites
- Windows 10 (1903+) or Windows 11  
- Python 3.8+  
- Enable *Transparency effects* in Windows Settings for best results  

### Quick Setup
```bash
git clone https://github.com/AmirWise/Liquid-Gheymat.git
cd Liquid-Gheymat
pip install -r requirements.txt
python main.py
```

### Manual Installation
```bash
pip install customtkinter>=5.2.0
pip install pywinstyles>=1.7
pip install pyglet>=2.0.0
```

## 📁 Project Structure
```
Liquid-Gheymat/
├── main.py
├── requirements.txt
├── README.md
└── assets/
    ├── fonts/
    │   └── Vazirmatn-Regular.ttf
    ├── icons/
    │   └── icon.ico
    └── allprices.json
```

## ⚙️ Configuration

1. **Enable Windows Transparency**  
   Settings → Personalization → Colors → *Turn on Transparency effects*

2. **Font setup**  
   Ensure `Vazirmatn-Regular.ttf` exists in `assets/fonts/`  

## 🔧 Troubleshooting

- **Blur not visible?** Enable Windows transparency and run as administrator.  
- **Fonts not loading?** Install Vazirmatn system-wide or keep font in `assets/fonts/`.  
- **Currency data missing?** Ensure `allprices.json` exists and is UTF-8 encoded.  

## 📞 Support

Open an **Issue** on GitHub with:  
- Windows version  
- Python version  
- Full error message (if any)  
- Steps to reproduce  

---

Made with ❤️ and ☕ – Enjoy tracking your currency in style! 🚀

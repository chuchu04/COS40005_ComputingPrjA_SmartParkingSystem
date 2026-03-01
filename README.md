## 🎬 Demo Video

[▶ Watch the demo](https://liveswinburneeduau-my.sharepoint.com/:v:/r/personal/104663478_student_swin_edu_au/Documents/Uni/COS40005%20-%20Computing%20Project%20A/Video%20Demo/2026-03-01%2022-50-33.mkv?csf=1&web=1&nav=eyJyZWZlcnJhbEluZm8iOnsicmVmZXJyYWxBcHAiOiJPbmVEcml2ZUZvckJ1c2luZXNzIiwicmVmZXJyYWxBcHBQbGF0Zm9ybSI6IldlYiIsInJlZmVycmFsTW9kZSI6InZpZXciLCJyZWZlcnJhbFZpZXciOiJNeUZpbGVzTGlua0NvcHkifX0&e=VBXKsE)

---

# 🚗 Smart Parking Web & Database System

A **full-stack proof-of-concept web application** designed to automate supermarket parking operations. This project simulates an end-to-end vehicle lifecycle — from AI-based license plate entry to automated digital wallet fee deduction upon exit.

This project focuses **only on the Web Application and Database layer**.  
IoT hardware and AI inference are **handled by separate team members** (ESP32-S3 gate system and Raspberry Pi 5).

**Project:** COS40005 — Computing Technology Project A (Group 1)

---

## 📌 Features

- 🗺️ **Real-Time Parking Map** — Live-updating CSS Grid dashboard showing lot occupancy via HTTP polling
- 🔐 **JWT Authentication** — Secure user registration and login with token-based auth
- 💳 **Digital Wallet Integration** — Each user has a digital wallet for cashless parking fee deduction
- 💰 **Dynamic Fee Calculation** — 10,000 credits for the first 24 hours, +1,000 credits/hour thereafter (partial hours rounded up)
- 🧾 **Retail Receipt Discount** — Redeem supermarket receipt codes to reduce parking fees:
  - Purchase ≥ 500,000 → 10,000 credit discount (free parking)
  - Purchase ≥ 200,000 → 5,000 credit discount
  - One receipt per session, each receipt can only be claimed once
- 🧪 **Hardware Simulation Portal** — Built-in UI buttons to simulate IoT sensor triggers (Entry/Exit) since physical hardware is not connected in this demo

---

## 🧠 System Behavior Overview

### 🚘 Parking Flow

User registers & logs in  
⬇️  
Clicks **"Create Parking Session"** (simulates ALPR camera detection)  
⬇️  
System assigns an available slot → slot turns **red** on the Live Map  
⬇️  

**Optional: Apply Receipt Discount**
- Navigate to **Receipt** page
- Enter a valid receipt code
- Discount is applied to the active session

⬇️  
Clicks **"Exit"**  
⬇️  
System calculates duration → applies discount → deducts fee from wallet → frees slot

---

## 🔧 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | ASP.NET Core 8.0 Web API (C#) |
| ORM | Entity Framework Core + Pomelo MySQL Provider |
| Database | MySQL 8.0 (via XAMPP) |
| Authentication | ASP.NET Core Identity + JWT Bearer Tokens |
| Frontend | React 19, Vite, Axios, React Router |
| Caching | ASP.NET Core `IMemoryCache` (5-second TTL for map data) |

---

## 🧩 Project Structure

```text
Web_MobileApp_Database/
├── WebApplication1/            # ASP.NET Core Backend
│   ├── Controllers/            # API endpoints (Auth, Parking)
│   ├── Models/                 # Entity models (User, Wallet, ParkingSession, etc.)
│   ├── DTOs/                   # Request/response data transfer objects
│   ├── Data/                   # EF Core DbContext and configuration
│   └── Database/               # EF Core migration files
├── smart-parking-client/       # React Frontend
│   └── src/
│       ├── pages/              # Page components (LiveMap, Profile, Receipt, etc.)
│       ├── components/         # Reusable components (HardwareSimulator)
│       └── services/           # API client and auth service
└── docs/                       # Architecture and flow documentation
```

---

## ⚙️ Getting Started

### Prerequisites

- [.NET 8 SDK](https://dotnet.microsoft.com/download)
- [Node.js](https://nodejs.org/) (v18+)
- [XAMPP](https://www.apachefriends.org/) (for MySQL 8.0)

### 1. Database Setup

1. Start **Apache** and **MySQL** from the XAMPP Control Panel.
2. Open phpMyAdmin (`http://localhost/phpmyadmin`) and create a database called `SmartParkingDb`.

### 2. Backend Setup

```bash
cd WebApplication1
dotnet ef database update
dotnet run --launch-profile http
```

> API server starts at `http://localhost:5219`

### 3. Frontend Setup

```bash
cd smart-parking-client
npm install
npm run dev
```

> Open your browser to the URL shown in the terminal (typically `http://localhost:5173`)

---

## 🧪 How to Test the Demo

Since the physical IoT edge devices (ESP32-S3, ALPR cameras) are not connected for this web-only demo, use the **Hardware Simulator** panel on the Live Map page:

1. **Register & Log In** — Create a new account from the registration page.

2. **Simulate Car Entry** — On the Live Map page, click **"Create Parking Session"**.  
   This mimics the ALPR camera detecting your car. You will see an available slot turn red on the map.

3. **Apply a Receipt Discount (Optional)** — Insert a test receipt into the `RetailReceipts` table:
   ```sql
   INSERT INTO RetailReceipts (ReceiptUid, PurchaseAmount, IsClaimed)
   VALUES ('RCP-TEST-001', 500000, 0);
   ```
   Then navigate to the **Receipt** page and enter the code `RCP-TEST-001`.

4. **Simulate Car Exit** — Click **"Exit"** on the Live Map page.  
   The system will calculate your parking duration, apply any discounts, deduct the final fee from your wallet, and free the slot on the map.

5. **Check your Profile** — The Profile page shows your wallet balance, and if you have an active session, the current fee with any applied discount.

---

## 📝 Notes

```text
This project covers only the Web Application and Database components
Designed for clean integration with the IoT gate system (ESP32-S3) and AI module (Raspberry Pi 5)
Hardware interactions are simulated via UI buttons for demo purposes
All timing and polling uses non-blocking patterns for responsive real-time updates
```

# 🗺️ NYC DoT Parking Signs Interactive Map

> **Status:** Actively in Development 🚀 
> 
> *A civic-tech initiative transforming complex administrative data into an accessible, intuitive public utility.*

## 📌 The Problem
The NYC Department of Transportation (DoT) maintains a massive dataset of parking regulations. However, this data is point-based—meaning it only shows the exact latitude and longitude of physical street signs. While useful for internal asset management, it fails to answer the primary question every driver has: **"Exactly where along this sidewalk can I park, and when?"**

## 💡 The Solution
This project bridges the gap between raw government data and public accessibility. By building an automated geospatial ETL pipeline, we ingest isolated sign coordinates and map them directly to continuous NYC curb-line geometries. The result is an interactive, color-coded map that instantly communicates parking legality to the user.

## ✨ Core Features
* **Geospatial ETL Pipeline:** Automated Python scripts that extract raw OpenData, clean invalid coordinates, and transform isolated points into continuous spatial boundaries.
* **Curb-Line Mapping:** Connects sign data to the city's street layout, drawing precise lines along curbs to show exactly where specific regulations start and end.
* **Interactive UI:** Click-to-view pop-ups that translate complex municipal codes into human-readable parking rules.

## 🚀 Roadmap & Active Development
We are continuously iterating on this project to build a highly robust tool. Upcoming features include:
- [ ] **Dynamic Temporal Filtering:** Implementing a search module where users can input a specific time (e.g., "Tuesday at 8:00 PM") and watch the map dynamically update to show all legally available spots at that exact hour.
- [ ] **Advanced Spatial Joins:** Refining the snap-to-curb logic using Shapely and GeoPandas for edge-case intersections.
- [ ] **Web Deployment:** Transitioning the local map interface into a live, interactive web application.

## 🛠️ Tech Stack
* **Languages:** Python
* **Data Engineering & GIS:** `pandas`, `geopandas`, `shapely`
* **Version Control:** Git, GitHub
* **Data Source:** [NYC OpenData - Parking Regulations](https://opendata.cityofnewyork.us/)

## 👥 The Team
* **Ruhma Arshad** - Data & Geospatial Lead
* **Sanjar Melikov** - Frontend & Mapping Lead

---
*Developed as an independent project utilizing NYC OpenData.*

# Tech Stack: Air Sports Live Tracking (ASLT)

This document outlines the core technologies and frameworks utilized in the Air Sports Live Tracking platform.

## 1. Backend

*   **Language:** Python 3.12
*   **Framework:** Django (Web framework)
*   **API:** Django REST Framework
*   **Asynchronous Tasks:** Celery (for background task processing)

## 2. Frontend

*   **Framework:** React
*   **Build Tool:** Vite
*   **Language:** JavaScript/TypeScript
*   **Styling:** Tailwind CSS

## 3. Database

*   **Primary Database:** MySQL

## 4. Caching & Messaging

*   **In-memory Data Store:** Redis (for caching, session management, and inter-process communication)

## 5. Deployment & Orchestration

*   **Containerization:** Docker
*   **Container Orchestration:** Kubernetes
*   **Package Manager for Kubernetes:** Helm

## 6. Integrations

*   **GPS Tracking Server:** Traccar (for receiving and processing position reports)
*   **Hosting/User Management (Authentication):** Firebase

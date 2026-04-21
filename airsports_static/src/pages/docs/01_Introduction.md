---
layout: ../../layouts/DocsLayout.astro
title: "Introduction to Air Sports Live Tracking (ASLT)"
---


# Introduction to Air Sports Live Tracking (ASLT)

Welcome to the comprehensive user manual for **Air Sports Live Tracking (ASLT)**. This platform is an open-source, non-profit system specifically engineered to modernize the management and scoring of competitive flying events. 

By leveraging the ubiquitous nature of smartphones and the power of cloud-based real-time computation, ASLT provides a professional-grade tracking and results service without the prohibitive costs of traditional specialized hardware.

## Core Philosophy: Modernizing the Skies

ASLT was born from a desire to make air sports more transparent, interactive, and accessible. Traditional scoring often relies on manual logs and post-flight processing, which can take hours or even days. ASLT changes this by:
*   **Real-time Scoring:** Penalties are calculated as they happen, allowing for live leaderboards in the clubhouse.
*   **Cost Efficiency:** Using existing hardware (iOS/Android devices) as primary trackers.
*   **Accessibility:** An intuitive interface for both pilots and organizers.
*   **Reliability:** Advanced offline buffering and "Adaptive Start" logic to handle the realities of aviation (variable wind, signal gaps, and pre-flight delays).

## Who Should Use This Guide?

This documentation library is organized by user roles to help you find the information you need quickly:

### 1. The Contestant (Pilots & Crew)
If you are participating in an event, this guide will show you how to:
*   Configure your mobile device for maximum tracking reliability.
*   Register for events and manage your team details.
*   Understand the "Adaptive Start" and how to use your Flight Order.
*   *Refer to: `02_Contestant_Guide.md` and `06_Tracking_Devices.md`*

### 2. The Contest Manager (Organizers & Officials)
If you are running an event, this guide is your operational manual. It covers:
*   Setting up Contests and Navigation Tasks from scratch.
*   Using the **Flight Scheduler Optimizer** to handle complex logistics (shared aircraft/trackers).
*   Building routes with the integrated editor and applying specific scorecards.
*   Managing the **Results Service** for both flying and ground-based tests (landings, theory).
*   *Refer to: `03_Contest_Manager_Guide.md`, `04_Route_Creation_and_Tasks.md`, `05_Results_Service_Guide.md`, and `07_Competition_Types_and_Scorecards.md`*

## How to Become an Organizer
To host a contest, you need **Organizer** status. This is **automatically approved** for all registered users. Simply log in to the platform and click the **"Become an Organizer"** button in the navigation bar. Once activated, the **"Management"** menu will appear, providing access to your contests and tools.

## Technical Context
ASLT is a high-performance ecosystem utilizing:
*   **Google Firebase:** For secure, passwordless authentication.
*   **Cloud Infrastructure:** Scalable servers that process thousands of GPS points per second.
*   **Linear Programming:** Advanced mathematical solvers to optimize flight schedules.
*   **Open Glider Network (OGN) & SafeSky Integration:** Aggregating data from multiple sources for a complete tactical picture.

## Support & Community
ASLT is a community-driven project. For specialized map processing (GeoTIFF) or to request organizer status, please contact **support@airsports.no**. 

Proceed to the next chapters to begin your journey with Air Sports Live Tracking.

---
schemaVersion: 1
id: case-iot-buoy-fault-diagnosis
documentType: case-study
section: experience
parentEntryId: hydrosphere-systems-integration-2024-2026
date: 2025-11
title: IoT Buoy Fault Diagnosis Through Data Analysis
organization: Hydrosphere UK Ltd
retrievalPriority: normal
---

# IoT Buoy Fault Diagnosis Through Data Analysis

## Overview

- This case demonstrates the Owner's ability to use data analysis to diagnose complex
  technical systems, distinguish multiple simultaneous faults, create and test
  hypotheses, work with incomplete evidence, collaborate across software and hardware
  boundaries, and convert findings into operational and engineering improvements.

## Context

- The buoy transmitted operational measurements every few minutes, including wave
  height, wave direction, underwater current, surface current, wind speed, temperature,
  and other environmental indicators.
- The buoy was a first-of-its-kind engineering configuration within the company, so
  there was no directly comparable internal installation.
- Direct inspection was difficult and expensive because an engineer would need to travel
  to Scotland and then reach the offshore buoy by vessel.

## Problem

- Hydrosphere UK encountered intermittent incorrect readings from an experimental marine
  IoT buoy installed offshore.
- The measurements supported vessel-mooring decisions in a narrow marine passage, so
  inconsistent readings created an operational risk.
- Visual observations from shore sometimes contradicted the direction of waves and wind
  reported by the buoy.
- Replacing components without identifying the likely source of failure would therefore
  have created substantial unnecessary servicing costs.

## Analysis

- The Owner used Python and Pandas to analyse the buoy's historical telemetry.
- The dataset contained more than one hundred measurements and technical indicators
  collected at regular intervals.
- The Owner searched for correlations, recurring patterns, environmental conditions, and
  relationships between apparently unrelated measurements.
- The analysis showed that two separate faults were occurring rather than one single
  equipment failure.

## First Fault — Software Defect

- The first fault was a regular data reset or invalid reading occurring approximately
  every six hours.
- The precise periodicity indicated that this issue was software-related rather than a
  random hardware failure.
- The six-hour issue was traced to the software responsible for collecting or processing
  measurements on the same interval.
- The software was corrected, and the monitoring dashboards stopped generating false
  equipment-failure notifications every six hours.

## Second Fault — Data Analysis

- A second intermittent fault remained and did not follow the same six-hour pattern.
- A major storm later produced additional high-intensity observations that made the
  relationship between affected signals more visible.
- During high waves and severe weather conditions, activity recorded by one device was
  associated with distortions in data produced by another device.
- The Owner created several hypotheses to explain the relationship.
- The Owner reviewed the internal arrangement of the buoy's electronic boards and
  identified that the devices associated with the affected measurements were located on
  separate controller boards installed very close to each other.
- The relevant controllers used RS-232 communication.
- The data nevertheless indicated that one device influenced another only under
  particular operating conditions.

## Constraints

- A full office simulation was not practical because the Doppler sensor required
  immersion approximately three metres underwater and realistic storm conditions could
  not be reproduced.
- The available documentation did not describe specific separation or shielding
  requirements for the boards.

## Validation

- The Owner therefore used elimination, historical data, technical documentation,
  hardware drawings, and smaller controlled experiments to evaluate the remaining
  hypotheses.
- During an office experiment, a shielding layer was placed between the two controllers.
- The affected signals changed after shielding was introduced, providing supporting
  evidence for the interference hypothesis.

## Results

- The investigation narrowed the probable cause and gave the engineering team a defined
  plan for the next offshore intervention instead of replacing components without
  evidence.
- The findings avoided an unnecessary exploratory offshore maintenance visit and reduced
  the risk of replacing unrelated hardware.
- Assembly instructions were updated for engineers responsible for soldering, arranging,
  and installing electronic boards inside the buoy.
- The revised instructions accounted for board placement, separation, and potential
  interference between components.
- The investigation resolved the six-hour software defect and narrowed the remaining
  intermittent fault to a probable hardware-layout or interference issue supported by
  telemetry analysis and shielding tests.

## Limitations

- Initial analysis did not provide enough evidence to isolate the second fault.
- One hypothesis was interference between the Doppler-based sensor system and the device
  responsible for measuring sea conditions.
- The Owner proposed that electromagnetic or signal interference between the closely
  positioned controllers could be contributing to the incorrect readings.

## Retrieval

### Retrieval Hints

- Useful as a technical data-analysis case involving IoT, marine telemetry, Python,
  Pandas, time-series analysis, correlations, anomaly detection, hypothesis testing,
  software defects, hardware investigation, RS-232, controller interference, shielding,
  offshore maintenance, and engineering documentation.
- Useful for questions about how the Owner works with noisy sensor data, finds periodic
  failures, separates multiple root causes, investigates faults that cannot be
  reproduced directly, and uses data to reduce maintenance costs.
- Useful as an example of data analysis supporting engineering decisions rather than
  only reporting or dashboard creation.
- Useful for questions about cross-functional work between data analysis, software,
  electronics, IoT systems, and operational engineering.

### Primary Tags

- case-study
- iot
- data-analysis
- python
- pandas
- fault-diagnosis
- time-series
- root-cause-analysis

### Secondary Tags

- marine-telemetry
- sensor-data
- anomaly-detection
- correlation-analysis
- hypothesis-testing
- software-defect
- hardware-investigation
- rs-232
- electromagnetic-interference
- shielding
- offshore-maintenance
- engineering-documentation
- operational-risk
- cost-avoidance

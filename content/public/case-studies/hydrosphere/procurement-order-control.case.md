---
schemaVersion: 1
id: case-procurement-order-control
documentType: case-study
section: experience
parentEntryId: hydrosphere-systems-integration-2024-2026
date: 2026-04
title: ERP-Integrated Procurement and Order Control
organization: Hydrosphere UK Ltd
retrievalPriority: normal
---

# ERP-Integrated Procurement and Order Control

## Overview

- This case demonstrates the Owner's ability to investigate incidents without stopping
  at an individual error, identify systemic causes, model processes, design controls,
  work within technology constraints, integrate ERP data, and reduce operational
  dependency on a specific employee.

## Context

- Following the unexpected departure of a specialist responsible for procurement and
  product tracking, the Owner investigated whether recurring errors were caused only by
  the individual or by the underlying operating process.
- Management initially planned to recruit a direct replacement, but the Owner asked for
  several days to analyse the work before the position was filled.
- Warehouse staff, salespeople, engineers, and other employees entered operational
  information into multiple pages of the same Excel workbook.
- The workbook was used as the weekly source of truth for operational meetings and
  company-wide process coordination.

## Problem

- The investigation showed that any replacement would remain exposed to a high
  probability of errors because the process depended on fragmented Excel files, manual
  data entry, informal rules, and uncontrolled editing.
- Several Excel workbooks were logically connected but had no technical integration
  between them.
- Complete operating instructions were missing for many recurring scenarios.
- Some process stages had no clearly defined owner, controller, or validation point.
- The main operational workbook could be edited by the wider sales team and had no
  reliable change logging or audit trail.
- Calculations, operational coefficients, reports, and dashboards depended on the
  workbook, so one incorrect entry could affect multiple downstream indicators.
- Product categories and other controlled values were typed manually rather than
  selected from governed lists.
- Excel cells were also unsuitable for some detailed operational descriptions, creating
  usability and data-quality limitations.

## Analysis

- The Owner concluded that the main issue was not one employee's performance but a
  process design that allowed errors without sufficient prevention, validation,
  ownership, or traceability.
- The Owner documented the existing workflow using BPMN and identified participants,
  process owners, controllers, handoffs, decision points, and missing controls.

## Constraints

- The business required the solution to remain accessible through Excel, so a standalone
  Python application was not suitable for the agreed constraints.

## Decision

- The Owner proposed redesigning the process, validating incoming information,
  introducing controlled lists, connecting related datasets, removing duplicate work,
  and adding exception checks.
- The Owner reviewed the available Odoo ERP capabilities and proposed an Excel/VBA
  integration layer connected to the ERP.
- Management approved the proposed implementation.

## Implementation

- The Owner built an ERP-integrated Excel/VBA operations module with data loading,
  validation, workflow controls, and logging.
- The solution loaded operational and purchasing data from Odoo ERP.
- It matched sales orders with purchasing and fulfilment information.
- It tracked products held in stock and products still in transit.
- It supported partial deliveries, orders fulfilled in several stages, and orders
  associated with multiple invoices.
- The Owner reviewed the ERP configuration for automatic replenishment and purchase
  order creation when inventory reached defined thresholds.
- The module guided warehouse and operational users through the next required process
  stage.
- It generated notifications when an order moved from one stage to another and displayed
  the new requirements and actions for that stage.
- The Owner embedded operational reports and dashboards into the workflow.
- Instead of repeatedly entering the same information, users primarily reviewed
  automatically loaded data, selected controlled options, confirmed completed actions,
  and moved orders to the next stage.
- Repetitive data collection, matching, checking, and status preparation were handled by
  the integration layer.

## Validation

- Human involvement was retained for operational decisions, exceptions, verbal updates,
  and confirmation that physical actions had been completed.

## Results

- The final solution reduced reliance on individual knowledge and made the process
  easier to transfer to another employee.
- The work previously required approximately 37.5 hours per week from a dedicated
  specialist.
- After implementation, the operational process was maintained by a less specialised
  part-time employee working approximately 15 hours per week.
- This represents an approximate 60% reduction in the weekly labour required to maintain
  the process.
- The result was an ERP-integrated, semi-automated procurement and order-control
  workflow based on Odoo, Excel, and VBA.

## Recognition

- In recognition of the successful delivery and operational impact of this project, the
  Owner received a substantial performance bonus and a second written letter of
  appreciation from the company.

## Retrieval

### Retrieval Hints

- Useful as an end-to-end automation case involving procurement, order tracking, Odoo
  ERP, Excel, VBA, BPMN, workflow redesign, operational controls, stock tracking, goods
  in transit, partial deliveries, multiple invoices, dashboards, notifications, logging,
  validation, and process ownership.
- Useful for questions about how the Owner performs root-cause analysis, investigates
  recurring human errors, reduces key-person dependency, works within an Excel-only
  constraint, and redesigns processes before automating them.
- Useful as an example of business analysis, process modelling, data analysis, ERP
  integration, operational automation, internal controls, human-in-the-loop workflow
  design, and externally recognised business impact.

### Primary Tags

- case-study
- procurement
- order-management
- odoo
- erp
- automation
- business-analysis
- bpmn

### Secondary Tags

- excel
- vba
- api-integration
- root-cause-analysis
- workflow-redesign
- process-ownership
- process-controls
- stock-management
- goods-in-transit
- partial-deliveries
- invoicing
- notifications
- logging
- dashboards
- data-validation
- human-in-the-loop
- key-person-risk
- operational-continuity
- professional-recognition

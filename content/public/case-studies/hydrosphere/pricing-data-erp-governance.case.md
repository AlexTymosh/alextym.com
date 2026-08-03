---
schemaVersion: 1
id: case-pricing-data-erp-governance
documentType: case-study
section: experience
parentEntryId: hydrosphere-systems-integration-2024-2026
date: 2024-12
title: Pricing Data and ERP Governance
organization: Hydrosphere UK Ltd
retrievalPriority: normal
---

# Pricing Data and ERP Governance

## Overview

- This case demonstrates the Owner's ability to move from an apparently simple price
  update to root-cause analysis, data governance, ERP data restructuring, process
  redesign, automation, validation, stakeholder negotiation, and measurable operational
  control.

## Context

- Shortly after joining Hydrosphere UK, the Owner was asked to update purchasing and
  sales prices in Odoo ERP, a task that had been repeatedly postponed because the
  existing process was complex and unreliable.
- Before the project, some prices were updated through a legacy Microsoft Access-based
  workflow, while the remaining prices were entered manually into individual product
  records.

## Problem

- The Owner began with root-cause analysis and found that the problem extended far
  beyond outdated prices.
- Supplier price lists arrived in inconsistent Excel and PDF formats.
- Supplier product codes changed without a controlled mapping process.
- Product prices depended on combinations of product attributes.
- Attribute names differed across catalogues, supplier price lists, and the ERP, with
  extensive duplication and inconsistent terminology.
- Product creation, classification, naming, archiving, and price maintenance were not
  governed by a single controlled process.
- Obsolete products were not consistently archived.
- Important procurement fields were missing or incomplete, including supplier product
  code, supplier product name, price validity dates, purchase currency, purchase
  quantity, and delivery time.
- Product attributes were sometimes applied to unrelated product categories, producing
  invalid product variants.
- A single product template could generate approximately 700 sales-price combinations
  because of the multiplicative effect of attributes.
- Multiple users could edit prices without a controlled review process.
- Price history was not maintained consistently.
- Cost, margin, and selling-price calculations were partly managed outside the ERP and
  then entered manually.
- Dashboards connected to the affected data produced unreliable results.
- Odoo 16 did not provide the required purchasing-price management for product
  attributes, while direct ERP modification was restricted.

## Analysis

- The Owner created an epic to manage the work as a structured improvement project.
- The Owner selected two principal suppliers covering approximately 95.5% of product
  positions, reducing the initial scope while preserving most of the business value.
- The Owner investigated supplier code changes, product naming differences, missing
  attributes, inconsistent internal names, and gaps between supplier and ERP data.
- The analysis showed that many products existed under internal names that were
  substantially different from their original supplier names.

## Constraints

- Sales stakeholders resisted some product renaming because they were accustomed to the
  existing terminology.
- Stakeholders rejected restrictions on permissions for creating and editing prices. The
  Owner documented the risk and warned that uncontrolled edits would continue to create
  errors.
- The use of Python was also rejected because Excel was considered more familiar and
  accessible to the business.

## Decision

- The Owner prepared and presented an action plan to stakeholders. The plan was accepted
  with limited changes.
- The Owner therefore implemented the solution using Excel, VBA-style macros, ERP
  exports, controlled imports, and validation workflows.

## Implementation

- The Owner reviewed each relevant product template, corrected existing attributes, and
  created missing attributes.
- The Owner enriched procurement data in the ERP supplier model.
- The Owner created a standard supplier price-list structure in Excel with consistent
  navigation, grouping, and data layout.
- The Owner built a macro that imported supplier prices and highlighted changed
  positions.
- The Owner built a separate transformation workflow that reduced several thousand
  exported product variants to approximately 300–400 unique product and attribute
  combinations requiring review.
- The Owner built another macro that compared the supplier price list with the current
  ERP state and generated four update tables.
- The four update tables supported purchasing prices, sales prices, product costs, and
  attribute-based prices.
- Because stakeholders retained unrestricted price-editing permissions, the Owner added
  automatic notifications when prices were changed outside the controlled process.
- After stabilising pricing, the Owner introduced naming standards for products and
  attributes.
- The Owner created an internal product-code standard.
- The Owner corrected errors in the product-category tree.
- The Owner reduced inconsistencies between duplicated product descriptions.
- The Owner added tags describing product type, promotional status, urgency, and price
  relevance.

## Validation

- The import workflow included validation checks for row counts, control totals, product
  attributes, missing fields, and median price movement compared with the previous
  period.
- The Owner added checks for missing values, currency consistency by supplier,
  wholesale-purchase rules, price history, and abnormal price movements.

## Results

- The Owner completed the initial pricing-control solution within approximately 60 days
  and before Christmas.
- The project brought more than 21,000 pricing points under a controlled workflow.
- Odoo ERP became the operational source of truth for product and pricing data.
- Product search became more consistent through standardised names, catalogue structure,
  internal codes, and tags.
- The improved data structure created a reliable foundation for later dashboard
  corrections and reporting improvements.

## Limitations

- The project did not eliminate every external dependency. Suppliers continued changing
  product names, product codes, and price-list formats, so incoming files still required
  validation.
- Stakeholders also retained the ability to edit prices outside the controlled workflow.
  The Owner mitigated this risk through monitoring and automatic notifications rather
  than claiming it had been removed.

## Recognition

- In recognition of the successful delivery of this project, the Owner received a
  performance bonus and a written letter of appreciation.
- The project also contributed directly to the Owner being offered a permanent position
  with the company.

## Retrieval

### Retrieval Hints

- Useful as an end-to-end case involving pricing automation, ERP governance, Odoo,
  supplier data, product attributes, product variants, master data, Excel automation,
  VBA macros, data validation, price history, margin control, dashboards, stakeholder
  resistance, permissions, monitoring, and controlled imports.
- Useful for questions about how the Owner handles unclear tasks, discovers deeper root
  causes, manages fragmented data, works within technical restrictions, chooses a
  practical tool when Python is rejected, and mitigates risks when stakeholders reject
  recommended controls.
- Useful as an example of business analysis, data analysis, BI foundations, ERP/CRM
  workflow improvement, data quality, internal controls, and pragmatic software
  automation.

### Primary Tags

- case-study
- pricing
- odoo
- erp
- automation
- data-governance
- business-analysis
- data-analysis

### Secondary Tags

- excel
- vba
- supplier-data
- product-data
- product-attributes
- master-data
- data-quality
- pricing-workflow
- cost-management
- margin-control
- controlled-imports
- validation
- monitoring
- stakeholder-management
- permissions
- root-cause-analysis
- dashboards
- source-of-truth

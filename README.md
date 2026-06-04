# Comfort Index Pipeline
*A modular data engineering pipeline currently under active development.*

## Overview
This repository contains the in‑progress implementation of a **Comfort Index data pipeline**, designed to ingest, clean, transform, and aggregate environmental, meteorological, geospatial, and census data into a unified Comfort Index metric.

The pipeline models production‑style data engineering patterns with a focus on:
- A clean, maintainable **src‑based Python project structure**
- **Workflow‑driven orchestration** across ingestion, validation, transformation, and output stages
- **Configurable pipeline components** with clear boundaries
- **Test‑first development** using pytest
- **Production‑inspired engineering practices** suitable for real‑world data pipelines

## Current Status
🚧 **Under Construction**  
This repository is publicly visible but not yet feature‑complete.  
Core pipeline components, workflow logic, and data transformations are still being built.  
Expect structural changes, refactors, and incremental additions as development progresses.

## Planned Capabilities
- Ingestion of multiple data sources  
- Coverage filtering and data quality validation  
- Transformation into standardized intermediate datasets  
- Calculation of the Comfort Index using:
  - Physiological discomfort factors  
  - Human vulnerability modifiers  
  - Derived metrics from available data sources  
- Modular workflow execution with clear orchestration boundaries  
- Extensible architecture for future data sources and model variations  

## Short‑Term Roadmap
- Finalize Phase 0 project scaffolding  
- Implement ingestion and coverage filtering modules  
- Build transformation layer and intermediate data models  
- Add Comfort Index computation logic  
- Introduce workflow orchestration engine  
- Expand test suite coverage  

## Competencies
- Data Engineering
- Data Modeling
- Data Enablement/Governance
- Application Engineering

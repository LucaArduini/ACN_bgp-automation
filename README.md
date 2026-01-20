Project for the "**Advanced Network Architectures And Wireless Systems**" class (2025-26) at Pisa University.<br>
Group work carried out by the students: [Luca Arduini](https://github.com/LucaArduini), [Valerio Triolo](https://github.com/valeriot30).

# 📡 ACN – BGP Network Automation Project

<p align="center">
  <img src="OtherFiles/networkTopologyDiagram.png" alt="Network Topology Diagram" width="700" />
</p>


This repository contains the implementation of a network automation project developed for the **Advanced Computer Networks (ACN)** course.

The project focuses on the design, emulation, and automation of a **multi–Autonomous System (AS) BGP network**, composed of customer ASes, a provider AS (AS65020), and multiple upstream providers.

## 🚀 Project Features
- **Reusable router configuration templates** built with **Jinja2**, supporting full parameterization (AS numbers, router IDs, interfaces, BGP neighbors).
- **Network emulation using Containerlab and FRRouting (FRR)** to deploy and validate the multi-AS topology.
- **Network automation system** running on a Manager node inside AS65020, capable of:
  - Processing periodic traffic prediction matrices.
  - Computing optimal traffic distribution across upstream links.
  - Dynamically adjusting BGP attributes (e.g., `LOCAL_PREF`, `MED`) to influence routing decisions.
  - Automatically applying configuration changes to routers.

## 🧪 Goals
- Reduce manual configuration errors through automation.
- Enable reproducible network experiments.
- Demonstrate traffic engineering techniques using BGP in a realistic emulated environment.

## 📁 Repository Contents
- Jinja2 templates and configuration scripts  
- Containerlab topology and deployment files  
- Automation system source code  
- Documentation and report describing design choices and testing methodology  

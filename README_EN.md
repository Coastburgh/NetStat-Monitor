# NetStat Monitor

[Versão em português](README.md)

Semester Project — Faculdade de Princípios Militares

Courses: Estatística Aplicada à Informática (Applied Statistics for Computing) and Introdução a Redes de Computadores (Introduction to Computer Networks)

Team: Eduardo Costa Borges, João P. Pereira, Fernando Ferreira Vaz, Tamynne Vitória, Paulo Henrique and Cid Mendes
Professor: Leonardo A. Portes

## Overview

NetStat Monitor is a tool for monitoring and analyzing network metrics in real time, with a focus on latency, jitter, packet loss and internet access behavior. The project collects data using ping at configurable intervals, stores measurements in CSV files and applies statistical analysis to characterize network behavior and detect anomalies. Results are presented in an interactive Streamlit dashboard.

The project documentation is available in English here and in Portuguese in [README.md](README.md).

The main idea is to allow a single collection session to compare different network layers (LAN, MAN and WAN) without requiring manual IP configuration in most cases. For this purpose, the system includes automatic detection of the default gateway and of the first external host from the Internet provider. This layer-based organization connects the project directly to the "Network types (LAN, MAN, WAN)" topic from the Introduction to Computer Networks syllabus.

## Scope changes and project evolution

During development, some initial plans were revised:

- the comparison with the theoretical M/M/1 queue model was removed from the confirmed scope, with no decision on a future implementation;
- the Streamlit dashboard became a central part of the solution instead of an optional add-on — including full start/stop control of the collection from the browser, not just visualization;
- `main.py`, the original terminal entry point, was discontinued: its multi-host collection logic was absorbed into `app.py`, eliminating the duplication that existed between the two entry points for a period of the project;
- collection was structured to work with multiple simultaneous destinations across network layers (LAN/MAN/WAN), naming files by layer label instead of by IP;
- automatic network detection became a key feature, reducing the need for manual configuration;
- distribution histograms (requirement 17) and the hypothesis test / t-test (requirement 15) were evaluated and **permanently removed from the confirmed scope** of the project — neither is in progress nor planned for reinstatement;
- primary storage remained CSV-based; the alternative SQLite support (requirement 7) was implemented and tested as a module (`ArmazenamentoSQLite`), but is not used in the active `app.py` pipeline, which relies on CSV exclusively;
- the schedule was removed from the scope document, to be defined later.

## Implemented features

- periodic latency collection via ping (req. 1, 2, 3);
- jitter (req. 5) and packet loss rate (req. 4) calculation;
- simultaneous monitoring of multiple hosts, using threads (req. 10);
- timeout and unreachable-host handling without interrupting collection (req. 8);
- CSV storage (req. 6); alternative SQLite support implemented but not used in the active pipeline (req. 7);
- automatic detection of the default gateway on the local network (LAN);
- approximation of the first external host through traceroute/tracepath (MAN);
- Streamlit web interface to start/stop collection and visualize charts in real time (req. 19);
- descriptive statistics: mean, median, standard deviation and percentiles (req. 11);
- outlier detection using IQR (req. 13) — Z-score (req. 12) evaluated and removed;
- correlation between time of day and latency (req. 14);
- synthetic data generation for development and testing.

## Data format

Each CSV row represents one measurement, with the following schema:

    timestamp,host,latencia_ms,jitter_ms,perda_pacotes_pct

The connection type is not a CSV column: it is recorded in the file name, using the format:

    dados/medicoes_{layer_label}_{session_label}.csv

Example: `medicoes_lan_gateway_wifi.csv`. The layer labels used are `lan_gateway`, `man_provedor` and `wan_google`; the stored session labels are `wifi` and `cabo`, displayed as "Wi-Fi" and "Cabo". The `tipo_conexao` column is reconstructed when the data is loaded, from the file name suffix.

Hosts used in the reference collections:

| Host | Layer | Description |
|---|---|---|
| `172.20.10.1` | LAN | Local gateway (mobile hotspot, in the test environment) |
| First public hop via traceroute | MAN | Approximation of the provider's infrastructure |
| `8.8.8.8` | WAN | Google DNS |
| `1.1.1.1` | WAN (alternative) | Cloudflare DNS |

## Relation to course content

| Syllabus topic | Where it appears in the project |
|---|---|
| Measures of position and dispersion | Descriptive statistics (req. 11) |
| Probability distributions | Not covered — depended on the queueing theory comparison, currently out of confirmed scope |
| Correlation | Correlation between time of day and latency (req. 14) |
| Hypothesis testing (Z, t) | Both removed from confirmed scope — z-score due to masking (req. 12); t-test (req. 15) not implemented |
| Network types (LAN, MAN, WAN) | Hosts organized and automatically detected by layer |
| Diagnostic commands (ping, traceroute, ipconfig) | Basis of the collector and of automatic host detection |
| Protocols (ICMP) | Implicit in ping-based collection |
| Packet analysis with Wireshark | Complementary manual activity, not integrated into the codebase |

## Methodological decisions

- **IQR for outliers, no Z-score.** The Z-score was evaluated and removed because it assumes a normal distribution and suffers from masking: the outliers themselves inflate the standard deviation and escape detection. Network latency distributions are skewed with a long right tail, which makes IQR the more robust and appropriate choice.
- **Simple solutions first.** Complexity is deferred when not immediately needed (for example, there is no error-type column in the CSV yet).
- **t-test removed from scope.** Statistical comparison between groups (e.g., Wi-Fi vs. Ethernet) using a t-test was evaluated, but is no longer part of the project's confirmed scope.
- **Aggregation only for visualization.** Per-minute averages smooth the time-series charts, but are never used for outlier detection — aggregating before detecting outliers would mask real spikes.
- **Packet loss per window, not cumulative.** The loss rate shown in charts is recalculated per time window, avoiding the cumulative counter (which resets on every collector run) hiding pointwise instability spikes.

## Implementation decisions

- collection is decoupled from storage: `PingCollector` uses callbacks;
- ping runs through `subprocess`, with `platform.system()` for cross-platform compatibility, avoiding the privilege issues of the `ping3` library on Windows;
- multi-host collection uses threads, with a `threading.Event` to allow each one to be stopped in a controlled way from the interface (needed for the Streamlit "Stop" button, since there is no Ctrl+C inside a browser);
- network detection uses `ipconfig`/PowerShell on Windows and `ip route` on Linux for the gateway; `tracert` (Windows), `tracepath` (Linux) or `traceroute` (macOS) for the first external hop;
- the `dados/` folder is listed in `.gitignore`, covering both real and synthetic CSVs;
- `scripts/gerar_dados_simulados.py` generates synthetic data so development does not depend on accumulating real measurements.

## Project structure

- app.py — main Streamlit dashboard, the application's single entry point;
- coletor/ — collection and network detection modules;
- armazenamento/ — persistence layer for collected data;
- analise/ — statistical analysis and pattern detection;
- visualizacao/ — charts and visualizations;
- dados/ — CSV files generated by collections (ignored by Git);
- scripts/ — support utilities and synthetic data generation.

All code folders contain an `__init__.py` file.

## Requirements

- Python 3.10 or newer;
- pip;
- a virtual environment is recommended.

Main dependencies: streamlit, pandas, numpy, scipy and plotly. The `requirements.txt` file contains the full list.

## Installation

1. Clone the repository:

       git clone <repository-url>

2. Enter the project folder:

       cd NetStat-Monitor

3. Create and activate a virtual environment:

   Windows (PowerShell):

       python -m venv venv
       .\venv\Scripts\Activate.ps1

   If script execution is blocked, run once:

       Set-ExecutionPolicy RemoteSigned -Scope CurrentUser

   Alternatively, use `cmd.exe` with `venv\Scripts\activate.bat`.

   Linux/macOS:

       python -m venv venv
       source venv/bin/activate

4. Install dependencies:

       pip install -r requirements.txt

## Running the project

### Streamlit dashboard

    streamlit run app.py

In the interface, it is possible to:

- enter hosts for the LAN, MAN and WAN layers;
- automatically detect the gateway and the first external host;
- start and stop data collection;
- visualize latency, jitter and packet loss charts, plus the instantaneous latency of the latest reading.

### Automatic network detection

To test only the layer detection logic:

    python -m coletor.deteccao_rede

### Direct collection test

For quick validation of the collection module:

    python -m coletor.ping_collector

## Typical usage flow

1. the user opens the web app;
2. hosts are entered manually or detected automatically;
3. collection starts across multiple threads;
4. measurements are saved to CSV files;
5. charts and statistical indicators are updated in real time.

## Current project status

### Implemented

- [x] periodic ping-based collection (req. 1, 2, 3);
- [x] jitter and packet loss calculation (req. 4, 5);
- [x] monitoring of multiple targets by network layer (req. 10);
- [x] failure and timeout handling (req. 8);
- [x] CSV storage (req. 6); SQLite support implemented, not used in the active pipeline (req. 7);
- [x] automatic detection of gateway and provider host;
- [x] Streamlit dashboard with full start/stop control (req. 19);
- [x] descriptive statistics (req. 11);
- [x] IQR-based outlier detection (req. 13);
- [x] correlation between time of day and latency (req. 14).

### Pending

- [ ] visual highlighting of outliers directly on the time-series charts (req. 18);
- [ ] automated consolidated report generation (req. 20);
- [ ] extended multi-day collection for real validation;
- [ ] deeper comparison between Wi-Fi and Ethernet;
- [ ] refinement of visualizations and report export;
- [ ] traffic capture and inspection with Wireshark (manual activity, planned for the final report stage).

### Confirmed out of scope

- [ ] distribution histograms (req. 17) — evaluated and removed;
- [ ] hypothesis testing / t-test (req. 15) — evaluated and removed;
- [ ] comparison with the theoretical M/M/1 queue model;
- [ ] TCP vs. UDP performance comparison.

## Important notes

- the project is a practical network diagnosis tool and does not replace specialized network analysis tools;
- the MAN layer is an approximation based on traceroute, not a precise provider identification;
- on Linux, `tracepath` sometimes gets no response from the first external router, returning the second hop instead — a behavior observed even when `traceroute`/`tracert`, in the same environment, do detect the first hop. This is a limitation of the technique/network, not a system error;
- gateway and first external host detection is a support feature; users can adjust the values manually when detection fails;
- high outlier rates on the mobile hotspot gateway result from mobile network characteristics, not from collection errors.

## License

This project is intended for academic and software development purposes within a university context.

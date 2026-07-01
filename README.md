# EvilDetective

> *Crack the case. Every secret, exposed.*

![Python](https://img.shields.io/badge/Python-3776AB.svg?style=flat-square&logo=Python&logoColor=white)

## Overview

Evil Detective is a Python desktop tool for Android forensic analysis. It connects to devices via ADB, extracts and decrypts application artifacts from SQLite databases, and presents findings through a structured GUI built on a shared base window class.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Contributing](#contributing)
- [License](#license)

---

## Features

|      | Component         | Details                                                                                                                                                                                                                                          |
| :--- | :---------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ⚙️  | **Architecture**  | <ul><li>Python-based CLI/script tool for digital forensics & artifact analysis</li><li>Flat script architecture — entry point likely via `py` files</li><li>Dependency-driven pipeline: fetch → parse → decrypt → report</li></ul>               |
| 🔩  | **Code Quality**  | <ul><li>Uses `wrapt-timeout-decorator` for robust timeout handling on long-running operations</li><li>Leverages `dataclasses` for structured, typed data modeling</li><li>No linting or formatting tools detected (e.g., no `flake8`, `black`)</li></ul> |
| 📄  | **Documentation** | <ul><li>Includes a `LICENSE` file — project is openly licensed</li><li>No dedicated docs folder, wiki, or docsite detected</li><li>`requirements.txt` serves as implicit dependency documentation</li></ul>                                       |
| 🔌  | **Integrations**  | <ul><li>`requests` — HTTP client for remote data fetching or API calls</li><li>`javaobj-py3` — deserializes Java serialized objects (`.ser` files), suggesting Android/Java artifact parsing</li><li>`XlsxWriter` — exports results to `.xlsx` reports</li><li>`Jinja2` — templated output generation (HTML or text reports)</li></ul> |
| 🧩  | **Modularity**    | <ul><li>Dependencies suggest distinct functional layers: **networking**, **parsing**, **crypto**, **reporting**</li><li>No package structure (`setup.py` / `pyproject.toml`) detected — likely a single-module or flat-file layout</li></ul>       |
| ⚡️  | **Performance**   | <ul><li>`wrapt-timeout-decorator` prevents hanging on unresponsive operations</li><li>`python-dateutil` + `dateutils` used for efficient date parsing across formats</li><li>No async framework detected — likely **synchronous** execution</li></ul> |

---

## Project Structure

```
└── EvilDetective/
    ├── adb_connection.py
    ├── classes.py
    ├── config.py
    ├── core.py
    ├── cracking.py
    ├── decoders.py
    ├── detective.py
    ├── engines.py
    ├── evildetective.py
    ├── LICENSE
    ├── lockscreens.py
    ├── messages.py
    ├── preferences.py
    ├── README.md
    ├── requirements.txt
    ├── screen_capture.py
    ├── statics.py
    ├── tooltips.py
    ├── utils.py
    └── windows.py
```

---

## Getting Started

### Prerequisites

- Python 3.10+ / Node.js 18+ *(depending on the stack above)*

### Installation

```sh
git clone "https://github.com/IlluzyonistCode/EvilDetective
cd EvilDetective"
pip install -r requirements.txt
```

### Usage

```sh
python main.py
```

---

## Contributing

- [Report Issues](https://github.com/IlluzyonistCode/EvilDetective/issues)
- [Submit Pull Requests](https://github.com/IlluzyonistCode/EvilDetective/pulls)
- [Discussions](https://github.com/IlluzyonistCode/EvilDetective/discussions)

---

## License

Distributed under the [AGPL-3.0](LICENSE) license.

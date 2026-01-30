<div align="center">
<h1>FortiTopology</h1>
</div>

<div align="center">
  <p>
    An open-source tool to automatically visualize Fortinet network topologies.
  </p>
  
  ![License](https://img.shields.io/badge/License-MIT-blue.svg)
  ![Python](https://img.shields.io/badge/Python-3.8%2B-yellow.svg)
  ![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey.svg)
</div>

---

## About

**FortiTopology** is a Python-based utility with a graphical user interface (GUI) designed to automate the documentation of Fortinet networks. 

It connects to a **FortiGate** or a **FortiManager**, retrieves connected devices (Switches, Access Points), and analyzes LLDP/CDP neighbors to generate a topology map. The output is a `.drawio` XML file that can be opened and edited directly in [Diagrams.net](https://app.diagrams.net/) (formerly Draw.io).

## Features

* **Dual Connection Modes:**
    * **Direct Mode:** Connect directly to a single FortiGate.
    * **FortiManager Mode:** Connect to FMG and select a specific FortiGate to map.
* **Device Discovery:** Automatically detects:
    * FortiGates
    * FortiSwitches (Managed)
    * FortiAPs (Managed)
* **Link Analysis:**
    * Visualizes connections between Fortigate and Switches.
    * Visualizes connections between Switches.
    * Visualizes connections to Access Points.
* **Export:** Generates ready-to-use `.drawio` files.
* **User Friendly:** Simple GUI built with Tkinter.

## Installation

### Prerequisites
* Python 3.x installed
* Network access to your FortiGate or FortiManager (HTTPS)
* API User with Read Only access on FortiGate or FortiManager

### Setup
1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/YOUR_USERNAME/FortiTopology.git](https://github.com/YOUR_USERNAME/FortiTopology.git)
    cd FortiTopology
    ```

2.  **Install dependencies:**
    ```bash
    pip install requests urllib3
    ```
    *(Note: `tkinter` is usually included with Python. If not, install `python3-tk` on Linux)*

## Usage

1.  **Start the application:**
    ```bash
    python fortitopology.py
    ```

2.  **Choose your mode:**

    * **Tab 1: FortiGate (Direct)**
        * Enter IP/Hostname of the Gate.
        * Enter the REST API Token (ensure the admin has read access to System, Network, and WiFi).
    
    * **Tab 2: FortiManager**
        * Enter FMG IP and API Token.
        * Click **Load Devices** to fetch the list of managed devices.
        * Select the target FortiGate from the dropdown list.

3.  **Generate Map:**
    * Select the output path for the `.drawio` file.
    * Click **Create topology**.
    * Open the resulting file in [Diagrams.net](https://app.diagrams.net/).

## Building Standalone (EXE/Binary)

To run this tool without installing Python (e.g., on a colleague's machine), you can build a standalone executable using `PyInstaller`.

**Windows (.exe):**
```bash
pyinstaller --onefile --noconsole --name "FortiTopology" forti_mapper.py
```

**Linux (Binary):**
```bash
pyinstaller --onefile --noconsole --name "FortiTopology" forti_mapper.py
chmod +x dist/FortiTopology
```

## Contributing
Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are greatly appreciated.
1. Fork the Project
2. Create your Feature Branch (```git checkout -b feature/AmazingFeature```)
3. Commit your Changes ( ```git commit -m 'Add some AmazingFeature'```)
4. Push to the Branch (```git push origin feature/AmazingFeature```)
5. Open a Pull Request

## License
Distributed under the MIT License. See ```LICENSE``` for more information.
  Note: You are free to use, modify, and distribute this software as long as the original copyright notice is included.

## Acknowledgments
This tool relies on the following open-source libraries:
  * [Requests](https://pypi.org/project/requests/) (Apache 2.0)
  * [URLLIB3](https://pypi.org/project/urllib3/) (MIT)

# Disclaimer:
This tool is not affiliated with or endorsed by Fortinet. Use it at your own risk. Always test in a non-production environment first.

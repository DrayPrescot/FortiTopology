# -----------------------------------------------------------------------------
# FortiTopology
# Copyright (c) 2026 Michael Schmerbeck
# Licensed under the MIT License.
# See LICENSE file in the project root for full license information.
# -----------------------------------------------------------------------------

import requests
import urllib3
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading

# Surpress warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- GLOBALE VARIABLES ---
CONNECTION_MODE = "DIRECT"  # 'DIRECT' or 'FMG'
CURRENT_IP = ""             # IP Adress (Gate or FMG)
CURRENT_PORT = "11443"      # Port (Gate or FMG)
CURRENT_TOKEN = ""          # API Token
CURRENT_SESSION = ""        # Session
SELECTED_DEVICE_DATA = {}   # List with Fortigate data
SELECTED_DEVICE_SERIAL = "" # Necessary for FMG mode
SELECTED_DEVICE_NAME = ""   # Necessary for FMG mode
BASE_URL = ""               # created dynamically
GUI_DEVICE_MAP = {}         # List to find device data from Combo Box

# Callback for GUI Logs
gui_log_callback = None

def log(message):
    print(message)
    if gui_log_callback:
        gui_log_callback(message)

# Clean up
def clean_id(text):
    if not text: return "unknown"
    return str(text).strip().replace(" ", "_").replace(":", "").replace(".", "").replace("-", "_")

# JSON communication to FMG
def fmg_json_rpc(method, url, payload=None):
    """
    Sendet einen JSON-RPC Request an den FortiManager.
    """

    headers = {
        'Authorization': f'Bearer {CURRENT_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    body = {
        "method": method,
        "params": [
            {
                "url": url,
                "data": payload if payload else {}
            }
        ],
        "id": 1
    }

    full_url = f"https://{CURRENT_IP}:{CURRENT_PORT}/jsonrpc"

    try:
        response = requests.post(full_url, json=body, headers=headers, verify=False, timeout=15)
        
        log(f"Connecting")

        if response.status_code == 200:

            log(f"Connection successfull")

            json_resp = response.json()
            
            # Error Handling for JSON Body
            if 'result' in json_resp and len(json_resp['result']) > 0:
                result_obj = json_resp['result'][0]

                status = result_obj.get('status', {})
                
                # Code 0 --> Success
                if status.get('code') == 0:
                    return result_obj.get('data')
                else:
                    log(f"FMG RPC Error: {status.get('message')} (Code {status.get('code')})")
                    return None
            else:
                log(f"FMG Empty Response: {json_resp}")
                return None
        else:
            log(f"FMG HTTP Error: {response.status_code}")
            return None

    except Exception as e:
        log(f"FMG Exception: {e}")
        return None

def get_data(endpoint):
    # Direct mode
    if CONNECTION_MODE == "DIRECT":
        headers = {'Authorization': f'Bearer {CURRENT_TOKEN}'}
        try:
            full_url = f"https://{CURRENT_IP}:{CURRENT_PORT}/api/v2{endpoint}"
            response = requests.get(full_url, headers=headers, verify=False, timeout=8)
            if response.status_code == 200:
                data = response.json()
                return data
            return []
        except Exception as e:
            log(f"Error {endpoint}: {e}")
            return []

    # FMG mode
    elif CONNECTION_MODE == "FMG":
        if not SELECTED_DEVICE_DATA:
            return {}

        dev_name = SELECTED_DEVICE_DATA.get('name')
        dev_adom = SELECTED_DEVICE_DATA.get('adom', 'root')

        targets_to_try = [
            # 1. Path as String
            f"adom/{dev_adom}/device/{dev_name}",

            # 2. Path as List
            [f"adom/{dev_adom}/device/{dev_name}"],
            
            # 3. Global Path as List
            [f"device/{dev_name}"],
            
            # 4. Only name as List
            [dev_name],            
            
            # 5. Only name
            dev_name
        ]
        
        for i, target_variant in enumerate(targets_to_try):
            target_path = target_variant

            log(f"{target_path}")

            # Create Payload
            payload = {
                "target": [target_path], 
                "action": "get",
                "resource": f"/api/v2{endpoint}"
            }
            
            result = fmg_json_rpc("exec", "/sys/proxy/json", payload)
            
            # Handle result
            data = result
            if data is not None: 
                return data
            
        return {}
    
def get_gate_details():
    """Holt Infos. Im FMG Modus vertrauen wir der Auswahl."""
    log("Fetching Hostname and Serial")
    
    serial = None
    hostname = "MyFortiGate"
    
    # Serial Number is known from selection
    if CONNECTION_MODE == "FMG" and SELECTED_DEVICE_DATA:
        serial = SELECTED_DEVICE_DATA.get('serial')
        hostname = SELECTED_DEVICE_DATA.get('name')
        log(f"Gateway: {hostname} ({serial})")

    # Serial Number via API for Direct Mode
    elif CONNECTION_MODE == "DIRECT":
        try:
            res = get_data("/monitor/license/status")
            serial = res.get('serial')
        except: pass
        try:
            res = get_data("/monitor/system/status")
            results = res.get('results')
            hostname = results.get('hostname')
        except: pass
    
    if not serial: serial = "FG-UNKNOWN"
    
    log(f"Target: {hostname} ({serial})")
    return serial, hostname

def fetch_fmg_devices():
    log("Load device list")
    global GUI_DEVICE_MAP
    GUI_DEVICE_MAP = {}
    
    payload = {
        "option": "1" 
    }
    
    devices_data = fmg_json_rpc("get", "/dvmdb/device", payload)
    
    gui_list = []
    
    if devices_data and isinstance(devices_data, list):
        for d in devices_data:
            name = d.get('hostname', 'Unknown')
            sn = d.get('sn', '')
            adom = d.get('mgt_vdom', 'root')
            oid = d.get('oid')
            conn_status = d.get('conn_status') # 1 = Up
            
            if sn and sn.startswith("FG"): 

                display_str = f"{name} ({sn}) [{adom}]"
                gui_list.append(display_str)
                
                # Save in Map for later use
                GUI_DEVICE_MAP[display_str] = {
                    'name': name,
                    'serial': sn,
                    'adom': adom,
                    'oid': oid
                }
                
        log(f"{len(gui_list)} devices loaded.")
        return sorted(gui_list)
    else:
        log("No devices found.")
        return []

# --- XML GENERATOR ---
def create_drawio_xml(devices, links):
    mxfile = ET.Element('mxfile', host="Electron", agent="PythonScript", type="device")
    diagram = ET.SubElement(mxfile, 'diagram', id="diagram_1", name="FortiTopology")
    mxGraphModel = ET.SubElement(diagram, 'mxGraphModel', dx="1422", dy="794", grid="1", gridSize="10", guides="1", tooltips="1", connect="1", arrows="1", fold="1", page="1", pageScale="1", pageWidth="827", pageHeight="1169", math="0", shadow="0")
    root = ET.SubElement(mxGraphModel, 'root')
    ET.SubElement(root, 'mxCell', id="0")
    ET.SubElement(root, 'mxCell', id="1", parent="0")

    y_gate, y_switch, y_ap = 50, 250, 450
    x_sw, x_ap, spacing = 0, 0, 180
    existing_ids = set()

    for dev in devices:
        safe_id = clean_id(dev['id'])
        existing_ids.add(safe_id)
        style = "rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;fontColor=#000000;"
        if dev['type'] == 'fortigate':
            style = "shape=mxgraph.cisco.firewalls.firewall;html=1;fillColor=#f8cecc;strokeColor=#b85450;fontColor=#FF0000;"
            x, y = 400, y_gate
        elif dev['type'] == 'switch':
            style = "shape=mxgraph.cisco.switches.layer_3_switch;html=1;fillColor=#d5e8d4;strokeColor=#82b366;fontColor=#0000FF;"
            x, y = 100 + (x_sw * spacing), y_switch
            x_sw += 1
        elif dev['type'] == 'ap':
            style = "shape=mxgraph.cisco.wireless.access_point;html=1;fillColor=#fff2cc;strokeColor=#d6b656;fontColor=#000000;"
            x, y = 100 + (x_ap * spacing), y_ap
            x_ap += 1
        
        cell = ET.SubElement(root, 'mxCell', id=safe_id, value=f"{dev['name']}\n{dev['serial']}", style=style, parent="1", vertex="1")
        geo = ET.SubElement(cell, 'mxGeometry', x=str(x), y=str(y), width="80", height="60", attribute="geometry")
        geo.set('as', 'geometry')

    unique_links = set() 
    for link in links:
        src = clean_id(link['src'])
        dst = clean_id(link['dst'])

        src_label = link.get('src_port')
        dst_label = link.get('dst_port')

        if src in existing_ids and dst in existing_ids:
            link_signature = tuple(sorted((src, dst)))
            if link_signature not in unique_links:
                unique_links.add(link_signature)
                edge_id = f"edge_{src}_{dst}"
                edge = ET.SubElement(root, 'mxCell', id=edge_id, value="", style="endArrow=none;html=1;rounded=0;", parent="1", source=src, target=dst, edge="1")
                geo_edge = ET.SubElement(edge, 'mxGeometry', relative="1")
                geo_edge.set('as', 'geometry')
                
                if src_label:
                    lbl_s = ET.SubElement(root, 'mxCell', id=f"lbl_src_{edge_id}", value=src_label, style="edgeLabel;html=1;align=center;verticalAlign=middle;resizable=0;points=[];fontSize=10;fontColor=#666666;", parent=edge_id, vertex="1", connectable="0")
                    geo_s = ET.SubElement(lbl_s, 'mxGeometry', x="-0.8", y="0", relative="1")
                    geo_s.set('as', 'geometry')

                if dst_label:
                    lbl_d = ET.SubElement(root, 'mxCell', id=f"lbl_dst_{edge_id}", value=dst_label, style="edgeLabel;html=1;align=center;verticalAlign=middle;resizable=0;points=[];fontSize=10;fontColor=#666666;", parent=edge_id, vertex="1", connectable="0")
                    geo_d = ET.SubElement(lbl_d, 'mxGeometry', x="0.8", y="0", relative="1")
                    geo_d.set('as', 'geometry')

    return ET.tostring(mxfile, encoding='utf-8', method='xml')

# --- THREAD WORKER ---
def run_process_thread(on_finish_callback, custom_path=""):
    try:
        devices = []
        links = []
        name_to_serial = {}

        # 1. Identify Gate
        fg_serial, fg_hostname = get_gate_details()
        
        devices.append({'id': fg_serial, 'name': fg_hostname, 'serial': fg_serial, 'type': 'fortigate'})
        name_to_serial[fg_hostname] = fg_serial 
        name_to_serial[fg_serial] = fg_serial   
        name_to_serial['FortiGate'] = fg_serial 

        # 2. Switches
        log("Load switches")
        results = get_data("/cmdb/switch-controller/managed-switch")

        if (CONNECTION_MODE == "FMG"):
            data = results[0].get('response', results)
            
            # Check if it is a list
            if isinstance(data, dict):
                switches_data = data.get('results', [])
            elif isinstance(data, list):
                switches_data = data
            else:
                switches_data = []
                log("Warning: No switches loaded.")
        else:
            switches_data = results.get('results', [])

        for i, sw in enumerate(switches_data):
            s_serial = sw.get('switch-id', f"Unknown_SW_{i}")
            s_name = sw.get('name', s_serial)
            devices.append({'id': s_serial, 'name': s_name, 'serial': s_serial, 'type': 'switch'})
            log(f"Switch: {s_serial} ({s_name})")
            name_to_serial[s_name] = s_serial
            name_to_serial[s_serial] = s_serial 

        # 3. APs
        log("Load access points")
        results = get_data("/monitor/wifi/managed_ap/select")

        if (CONNECTION_MODE == "FMG"):
            data = results[0].get('response', results)
            
            # Check if it is a list
            if isinstance(data, dict):
                aps_data = data.get('results', [])
            elif isinstance(results, list):
                aps_data = data
            else:
                aps_data = []
                log("Warning: No access points loaded.")
        else:
            aps_data = results.get('results', [])

        for i, ap in enumerate(aps_data):
            ap_serial = ap.get('serial', f"Unknown_AP_{i}")
            ap_name = ap.get('name', ap_serial)
            devices.append({'id': ap_serial, 'name': ap_name, 'serial': ap_serial, 'type': 'ap'})
            log(f"{ap_serial} {ap_name}")
            name_to_serial[ap_name] = ap_serial

        log(f"Created mappings. {len(devices)} devices found.")

        # 4. Links (Switches)
        found_links = 0
        for sw in switches_data:
            my_serial = sw.get('switch-id')
            if not my_serial: continue
            
            ports = sw.get('ports', [])
            for port in ports:
                local_port = port.get('port-name')
                peer_name = port.get('isl-peer-device-name')
                if peer_name:
                    peer_serial = name_to_serial.get(peer_name)
                    parent_port = port.get('isl-peer-port-name')
                    if peer_serial:
                        links.append({
                            'src': peer_serial,
                            'dst': my_serial,
                            'src_port': parent_port,
                            'dst_port': local_port})
                        found_links += 1
                else:
                    peer_name = port.get('fgt-peer-device-name')
                    if peer_name:
                        peer_serial = peer_name
                        parent_port = port.get('fgt-peer-port-name')
                        if peer_serial:
                            links.append({
                            'src': peer_serial,
                            'dst': my_serial,
                            'src_port': parent_port,
                            'dst_port': local_port})
        
        log(f"Connections found: {found_links}")

        # 5. Links (APs)
        for ap in aps_data:
            my_serial = ap.get('serial')
            lldp_info = ap.get('lldp')
            parent_name = ""
            if len(lldp_info) > 0:
                parent_name = lldp_info[0].get('system_name')
                parent_port = lldp_info[0].get('port_id')
                local_port = lldp_info[0].get('local_port')

            if parent_name:
                parent_serial = name_to_serial.get(parent_name)
                if parent_serial:
                    links.append({
                            'src': parent_serial,
                            'dst': my_serial,
                            'src_port': parent_port,
                            'dst_port': local_port})
            else:
                parent_serial = ap.get('connected_switch_serial')
                if parent_serial and parent_serial in name_to_serial.values():
                    links.append({
                            'src': parent_serial,
                            'dst': my_serial,
                            'src_port': "?",
                            'dst_port': "eth0"})

        if custom_path:
            filename = custom_path
        else:
            filename = f"topology_{fg_hostname}.drawio"

        xml_content = create_drawio_xml(devices, links)
        with open(filename, "wb") as f:
            f.write(xml_content)
        
        log(f"File saved: {filename}")
        on_finish_callback(True)

    except Exception as e:
        log(f"Critical Error: {e}")
        on_finish_callback(False)

# --- GUI ---
class FortiMapperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FortiTopology")
        self.root.geometry("600x650")

        # TAB SYSTEM
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="x", padx=10, pady=5)
        
        # Create Tabs
        self.tab_direct = ttk.Frame(self.notebook)
        self.tab_fmg = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_direct, text="FortiGate")
        self.notebook.add(self.tab_fmg, text="FortiManager")
        
        # Event Listener for Tab change
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_change)

        # --- TAB 1: DIREKT ---
        frame_d = ttk.Frame(self.tab_direct, padding=15)
        frame_d.pack(fill="both")
        
        ttk.Label(frame_d, text="IP/DNS:").grid(row=0, column=0, sticky="w")
        self.entry_ip_d = ttk.Entry(frame_d, width=35)
        self.entry_ip_d.insert(0, "192.168.1.99")
        self.entry_ip_d.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(frame_d, text="Port:").grid(row=1, column=0, sticky="w")
        self.entry_port_d = ttk.Entry(frame_d, width=35)
        self.entry_port_d.insert(0, "11443")
        self.entry_port_d.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(frame_d, text="API Token:").grid(row=2, column=0, sticky="w")
        self.entry_token_d = ttk.Entry(frame_d, width=35, show="*")
        self.entry_token_d.grid(row=2, column=1, padx=5, pady=5)

        # --- TAB 2: FMG ---
        frame_f = ttk.Frame(self.tab_fmg, padding=15)
        frame_f.pack(fill="both")

        ttk.Label(frame_f, text="IP/DNS:").grid(row=0, column=0, sticky="w")
        self.entry_ip_f = ttk.Entry(frame_f, width=35)
        self.entry_ip_f.insert(0, "10.0.0.1")
        self.entry_ip_f.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(frame_f, text="Port:").grid(row=1, column=0, sticky="w")
        self.entry_port_f = ttk.Entry(frame_f, width=35)
        self.entry_port_f.insert(0, "11443")
        self.entry_port_f.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(frame_f, text="API Token:").grid(row=2, column=0, sticky="w")
        self.entry_token_f = ttk.Entry(frame_f, width=35, show="*")
        self.entry_token_f.grid(row=2, column=1, padx=5, pady=5)

        self.btn_load = ttk.Button(frame_f, text="Load Devices", command=self.load_devices)
        self.btn_load.grid(row=2, column=1, sticky="e", pady=10)

        ttk.Label(frame_f, text="Selected firewall:").grid(row=3, column=0, sticky="w")
        self.combo_devices = ttk.Combobox(frame_f, width=32, state="readonly")
        self.combo_devices.grid(row=3, column=1, padx=5, pady=5)

        # --- MAIN BUTTON ---
        self.btn_start = ttk.Button(root, text="Create topology", command=self.start_process)
        self.btn_start.pack(pady=10)

        # --- Save ---
        frame_save = ttk.Frame(root, padding=10)
        frame_save.pack(fill="x")
        
        ttk.Label(frame_save, text="Save").pack(side="left")
        
        self.entry_path = ttk.Entry(frame_save)
        self.entry_path.pack(side="left", fill="x", expand=True, padx=5)
        
        self.btn_browse = ttk.Button(frame_save, text="...", width=5, command=self.choose_save_path)
        self.btn_browse.pack(side="left")

        # Log
        self.log_area = scrolledtext.ScrolledText(root, width=70, height=20, state='disabled', font=("Consolas", 9))
        self.log_area.pack(padx=10, pady=5)

    def append_log(self, text):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, text + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def on_tab_change(self, event):
        # Change mode according to Tab
        tab_id = self.notebook.index(self.notebook.select())
        global CONNECTION_MODE
        if tab_id == 0:
            CONNECTION_MODE = "DIRECT"
        else:
            CONNECTION_MODE = "FMG"

    def load_devices(self):
        # Get data from Inputs
        global CURRENT_IP, CURRENT_PORT, CURRENT_TOKEN, gui_log_callback
        CURRENT_IP = self.entry_ip_f.get().strip()
        CURRENT_PORT = self.entry_port_f.get().strip()
        CURRENT_TOKEN = self.entry_token_f.get().strip()
        gui_log_callback = self.append_log

        if not CURRENT_IP or not CURRENT_TOKEN:
            messagebox.showwarning("Error: Please enter IP and API Token.")
            return

        # Start Thread
        self.btn_load.config(state="disabled", text="Lade...")
        threading.Thread(target=self._thread_load).start()

    def _thread_load(self):
        try:
            dev_list = fetch_fmg_devices()
            self.combo_devices['values'] = dev_list
            if dev_list:
                self.combo_devices.current(0)
        finally:
            self.btn_load.config(state="normal", text="Load devices")

    def choose_save_path(self):
        filename = filedialog.asksaveasfilename(
            defaultextension=".drawio",
            filetypes=[("Draw.io Dateien", "*.drawio"), ("Alle Dateien", "*.*")],
            title="Choose Save path"
        )
        if filename:
            self.entry_path.delete(0, tk.END)
            self.entry_path.insert(0, filename)

    def start_process(self):
        global CURRENT_IP, CURRENT_PORT, CURRENT_TOKEN, SELECTED_DEVICE_DATA, gui_log_callback
        gui_log_callback = self.append_log
        
        # Read inputs depending on mode
        if CONNECTION_MODE == "DIRECT":
            CURRENT_IP = self.entry_ip_d.get().strip()
            CURRENT_PORT = self.entry_port_d.get().strip()
            CURRENT_TOKEN = self.entry_token_d.get().strip()
            SELECTED_DEVICE_DATA = {'serial': 'DIRECT', 'name': 'DIRECT'}
        else:
            CURRENT_IP = self.entry_ip_f.get().strip()
            CURRENT_PORT = self.entry_port_f.get().strip()
            CURRENT_TOKEN = self.entry_token_f.get().strip()
            
            selection = self.combo_devices.get()
            if not selection:
                messagebox.showwarning("Error: Please select a firewall")
                return
            
            # Get data from map
            if selection in GUI_DEVICE_MAP:
                SELECTED_DEVICE_DATA = GUI_DEVICE_MAP[selection]
                self.append_log(f"Ziel: {SELECTED_DEVICE_DATA['name']} (ADOM: {SELECTED_DEVICE_DATA['adom']})")
            else:
                self.append_log("Error: Mapping not found")
                return

        if not CURRENT_IP or not CURRENT_TOKEN:
            messagebox.showwarning("Error: Please enter a IP and API Token")
            return
        
        user_path = self.entry_path.get().strip()

        # Lock GUI and start
        self.btn_start.config(state="disabled", text="Verarbeite...")
        self.log_area.config(state='normal')
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state='disabled')
        
        threading.Thread(target=run_process_thread, args=(self.on_process_finish, user_path)).start()

    def on_process_finish(self, success):
        self.btn_start.config(state="normal", text="Topologie erstellen")
        if success:
            messagebox.showinfo("Success")

if __name__ == "__main__":
    root = tk.Tk()
    app = FortiMapperApp(root)
    root.mainloop()

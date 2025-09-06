import pywifi
from pywifi import const
import time
import json
import subprocess
import os


class WiFiSwitcher:
    def __init__(self, json_path='networks.json'):
        self.pywifi = pywifi.PyWiFi()
        self.iface = self.pywifi.interfaces()[0]
        self.json_path = json_path
        self.known_networks = self.load_known_networks()

    def load_known_networks(self):
        """Loads known network credentials from the JSON file."""
        if not os.path.exists(self.json_path):
            return {}
        try:
            with open(self.json_path, 'r') as f:
                networks = json.load(f)
                print(f"✅ Successfully loaded {len(networks)} networks from {self.json_path}")
                return networks
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"⚠️ Error loading {self.json_path}: {e}. Starting with an empty list.")
            return {}

    def _save_networks_to_json(self):
        """
        Saves the current known_networks dict to the JSON file atomically.
        Writes to a temporary file first, then renames it to prevent corruption.
        """
        temp_path = self.json_path + ".tmp"
        try:
            with open(temp_path, 'w') as f:
                json.dump(self.known_networks, f, indent=4)
            # If write is successful, replace the original file
            os.replace(temp_path, self.json_path)
            return True
        except Exception as e:
            print(f"❌ Error saving to {self.json_path}: {e}")
            return False

    def add_network(self, ssid, password, network_type='home', priority=99, username=None):
        """Adds or updates a network in our list and saves to JSON."""
        self.known_networks[ssid] = {
            "password": password,
            "type": network_type,
            "priority": priority,
            "username": username
        }
        return self._save_networks_to_json()

    def remove_network(self, ssid_to_remove):
        """Removes a network from our list and saves the change to JSON."""
        if ssid_to_remove in self.known_networks:
            del self.known_networks[ssid_to_remove]
            return self._save_networks_to_json()
        return False

    def scan_available_networks(self):
        """Scans for all available networks and returns them in a dictionary."""
        self.iface.scan()
        time.sleep(5)
        scan_results = self.iface.scan_results()
        networks_dict = {}
        for profile in scan_results:
            ssid = profile.ssid
            signal_dbm = profile.signal
            if ssid:  # Only add if SSID is not empty
                networks_dict[ssid] = {'signal': signal_dbm}
        return networks_dict

    def get_current_connection(self):
        """Returns the currently connected SSID and signal strength."""
        try:
            result = subprocess.check_output(['netsh', 'wlan', 'show', 'interfaces'], encoding='utf-8', errors='ignore')
            current_ssid = None
            signal_percent = None
            for line in result.split('\n'):
                if "SSID" in line and "BSSID" not in line:
                    current_ssid = line.split(":")[1].strip()
                if "Signal" in line:
                    signal_percent = int(line.split(":")[1].strip().replace('%', ''))
            return current_ssid, signal_percent
        except Exception:
            return None, None

    def connect_to_network(self, ssid, password):
        """Connects to a standard WPA2-Personal network."""
        self.iface.disconnect()
        time.sleep(2)
        profile = pywifi.Profile()
        profile.ssid = ssid
        profile.auth = const.AUTH_ALG_OPEN
        profile.akm.append(const.AKM_TYPE_WPA2PSK)
        profile.cipher = const.CIPHER_TYPE_CCMP
        profile.key = password
        tmp_profile = self.iface.add_network_profile(profile)
        self.iface.connect(tmp_profile)
        time.sleep(10)
        return self.iface.status() == const.IFACE_CONNECTED

    def connect_to_enterprise_network(self, ssid, username, password):
        """Connects to an enterprise network using a pre-existing Windows profile."""
        self.iface.disconnect()
        time.sleep(2)
        command = f'netsh wlan connect name="{ssid}"'
        try:
            subprocess.run(command, shell=True, check=True, capture_output=True, text=True, errors='ignore')
            for _ in range(10):  # Check for up to 30 seconds
                time.sleep(3)
                current_ssid, _ = self.get_current_connection()
                if current_ssid == ssid:
                    return True
            return False
        except subprocess.CalledProcessError as e:
            print(f"❌ Error executing netsh command for '{ssid}': {e.stderr}")
            return False
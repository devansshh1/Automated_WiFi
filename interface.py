import customtkinter
import threading
import time
from plyer import notification
from wifi_logic import WiFiSwitcher

class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        # --- 1. Initialize variables ---
        self.wifi_manager = WiFiSwitcher()
        self.auto_switch_thread = None
        self.stop_thread_event = threading.Event()
        self.auto_switch_var = customtkinter.BooleanVar(value=False)

        # --- 2. Configure the main window ---
        self.title("Smart Wi-Fi Switcher")
        self.geometry("850x650")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=3)
        self.grid_rowconfigure(3, weight=2)

        # --- 3. Create UI elements ---
        self.create_status_frame()
        self.create_networks_frame()
        self.create_controls_frame()
        self.log_textbox = customtkinter.CTkTextbox(self, height=100, state="disabled")
        self.log_textbox.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="ew")

        # --- 4. Start background tasks ---
        self.after(500, self.start_threaded_scan)
        self.after(1000, self.schedule_periodic_status_check)

    # --- UI Creation Methods ---
    def create_status_frame(self):
        status_frame = customtkinter.CTkFrame(self)
        status_frame.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")
        status_frame.grid_columnconfigure(1, weight=1)
        customtkinter.CTkLabel(status_frame, text="Status:", font=customtkinter.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=5)
        self.status_value_label = customtkinter.CTkLabel(status_frame, text="Checking...", text_color="orange")
        self.status_value_label.grid(row=0, column=1, padx=10, pady=5, sticky="w")
        customtkinter.CTkLabel(status_frame, text="SSID:", font=customtkinter.CTkFont(weight="bold")).grid(row=1, column=0, padx=10, pady=5)
        self.ssid_value_label = customtkinter.CTkLabel(status_frame, text="N/A")
        self.ssid_value_label.grid(row=1, column=1, padx=10, pady=5, sticky="w")
        customtkinter.CTkLabel(status_frame, text="Signal:", font=customtkinter.CTkFont(weight="bold")).grid(row=2, column=0, padx=10, pady=5)
        self.signal_value_label = customtkinter.CTkLabel(status_frame, text="N/A")
        self.signal_value_label.grid(row=2, column=1, padx=10, pady=5, sticky="w")

    def create_networks_frame(self):
        networks_main_frame = customtkinter.CTkFrame(self)
        networks_main_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        networks_main_frame.grid_rowconfigure(0, weight=1)
        networks_main_frame.grid_columnconfigure(0, weight=1)
        self.scrollable_networks_frame = customtkinter.CTkScrollableFrame(networks_main_frame, label_text="Available Networks")
        self.scrollable_networks_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        self.scrollable_networks_frame.grid_columnconfigure(0, weight=1)

    def create_controls_frame(self):
        self.controls_frame = customtkinter.CTkFrame(self)
        self.controls_frame.grid(row=2, column=0, padx=10, pady=(5, 10), sticky="ew")
        self.controls_frame.grid_columnconfigure(3, weight=1)
        scan_button = customtkinter.CTkButton(self.controls_frame, text="Scan for Networks", command=lambda: self.start_threaded_scan())
        scan_button.grid(row=0, column=0, padx=10, pady=10)
        self.filter_known_checkbox = customtkinter.CTkCheckBox(self.controls_frame, text="Show only known networks", command=lambda: self.start_threaded_scan())
        self.filter_known_checkbox.grid(row=0, column=1, padx=10, pady=10)
        settings_button = customtkinter.CTkButton(self.controls_frame, text="Manage Networks", command=self.open_management_window)
        settings_button.grid(row=0, column=2, padx=10, pady=10)
        self.auto_switch_toggle = customtkinter.CTkSwitch(self.controls_frame, text="Enable Automatic Switching", variable=self.auto_switch_var, command=self.toggle_auto_switch_thread)
        self.auto_switch_toggle.grid(row=0, column=4, padx=20, pady=10, sticky="e")

    # --- Pop-up Window Methods ---
    def open_management_window(self):
        if hasattr(self, 'management_window') and self.management_window.winfo_exists():
            self.management_window.focus()
            return
        self.management_window = customtkinter.CTkToplevel(self)
        self.management_window.title("Manage Saved Networks")
        self.management_window.geometry("500x400")
        self.management_window.transient(self)
        self.management_window.grab_set()
        scrollable_frame = customtkinter.CTkScrollableFrame(self.management_window, label_text="Saved Networks")
        scrollable_frame.pack(padx=20, pady=20, fill="both", expand=True)
        scrollable_frame.grid_columnconfigure(0, weight=1)
        def refresh_network_list():
            for widget in scrollable_frame.winfo_children():
                widget.destroy()
            for i, ssid in enumerate(sorted(self.wifi_manager.known_networks.keys())):
                network_frame = customtkinter.CTkFrame(scrollable_frame)
                network_frame.grid(row=i, column=0, padx=5, pady=5, sticky="ew")
                network_frame.grid_columnconfigure(0, weight=1)
                label = customtkinter.CTkLabel(network_frame, text=ssid, anchor="w")
                label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
                remove_button = customtkinter.CTkButton(network_frame, text="Remove", width=80, command=lambda s=ssid: remove_network_and_refresh(s))
                remove_button.grid(row=0, column=2, padx=5, pady=5)
                edit_button = customtkinter.CTkButton(network_frame, text="Edit", width=80, command=lambda s=ssid: self.open_settings_window(ssid_to_edit=s))
                edit_button.grid(row=0, column=1, padx=5, pady=5)
        def remove_network_and_refresh(ssid):
            if self.wifi_manager.remove_network(ssid):
                self.log_message(f"Network '{ssid}' removed.")
                refresh_network_list()
                self.start_threaded_scan()
            else:
                self.log_message(f"Failed to remove network '{ssid}'.")
        add_button = customtkinter.CTkButton(self.management_window, text="Add New Network", command=lambda: self.open_settings_window())
        add_button.pack(padx=20, pady=(0, 20), side="bottom")
        refresh_network_list()

    def open_settings_window(self, ssid_to_edit=None):
        if hasattr(self, 'settings_window') and self.settings_window.winfo_exists():
            self.settings_window.focus()
            return
        self.settings_window = customtkinter.CTkToplevel(self)
        self.settings_window.transient(self)
        self.settings_window.grab_set()
        self.settings_window.geometry("400x550")
        if ssid_to_edit:
            self.settings_window.title("Edit Network")
            network_details = self.wifi_manager.known_networks.get(ssid_to_edit, {})
        else:
            self.settings_window.title("Add New Network")
            network_details = {}
        main_frame = customtkinter.CTkFrame(self.settings_window, fg_color="transparent")
        main_frame.pack(padx=20, pady=20, fill="both", expand=True)
        customtkinter.CTkLabel(main_frame, text="Network Name (SSID):").pack(anchor="w")
        ssid_entry = customtkinter.CTkEntry(main_frame)
        ssid_entry.insert(0, ssid_to_edit or "")
        if ssid_to_edit:
            ssid_entry.configure(state="disabled")
        ssid_entry.pack(pady=(0, 10), fill="x")
        customtkinter.CTkLabel(main_frame, text="Password:").pack(anchor="w")
        password_entry = customtkinter.CTkEntry(main_frame, show="*")
        password_entry.insert(0, network_details.get("password", ""))
        password_entry.pack(pady=(0, 10), fill="x")
        customtkinter.CTkLabel(main_frame, text="Network Type:").pack(anchor="w")
        type_menu = customtkinter.CTkOptionMenu(main_frame, values=["home", "enterprise"])
        type_menu.set(network_details.get("type", "home"))
        type_menu.pack(pady=(0, 10), fill="x")
        customtkinter.CTkLabel(main_frame, text="Username (for enterprise only):").pack(anchor="w")
        username_entry = customtkinter.CTkEntry(main_frame)
        username_entry.insert(0, network_details.get("username") or "")
        username_entry.pack(pady=(0, 10), fill="x")
        customtkinter.CTkLabel(main_frame, text="Priority (lower number is higher):").pack(anchor="w")
        priority_entry = customtkinter.CTkEntry(main_frame)
        priority_entry.insert(0, str(network_details.get("priority") or ""))
        priority_entry.pack(pady=(0, 20), fill="x")
        def save_network():
            ssid = ssid_entry.get()
            password = password_entry.get()
            network_type = type_menu.get()
            username = username_entry.get() or None
            priority_str = priority_entry.get() or "99"
            if ssid and password:
                self.wifi_manager.add_network(ssid, password, network_type, int(priority_str), username)
                self.log_message(f"Network '{ssid}' saved!")
                title = "Network Updated" if ssid_to_edit else "New Network Added"
                notification.notify(title=title, message=f"Successfully saved credentials for {ssid}.", timeout=10)
                self.start_threaded_scan()
                self.settings_window.destroy()
                if hasattr(self, 'management_window') and self.management_window.winfo_exists():
                    self.management_window.destroy()
                    self.open_management_window()
            else:
                self.log_message("Error: SSID and Password cannot be empty.")
        save_button = customtkinter.CTkButton(main_frame, text="Save Network", command=save_network)
        save_button.pack(side="bottom")

    # --- Logic and Utility Methods ---
    def log_message(self, message):
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_textbox.configure(state="disabled")
        self.log_textbox.see("end")

    def toggle_auto_switch_thread(self):
        if self.auto_switch_var.get():
            self.stop_thread_event.clear()
            self.auto_switch_thread = threading.Thread(target=self._auto_switch_loop, daemon=True)
            self.auto_switch_thread.start()
            self.log_message("▶️ Automatic switching enabled.")
        else:
            self.stop_thread_event.set()
            self.log_message("⏹️ Automatic switching disabled.")

    def _auto_switch_loop(self):
        SWITCH_THRESHOLD = 10
        SCAN_INTERVAL = 45
        while not self.stop_thread_event.is_set():
            try:
                self.log_message("⚙️ Auto-scan running...")
                current_ssid, _ = self.wifi_manager.get_current_connection()
                available_networks_dict = self.wifi_manager.scan_available_networks()
                if not available_networks_dict:
                    time.sleep(SCAN_INTERVAL)
                    continue
                current_signal_dbm = None
                if current_ssid and current_ssid in available_networks_dict:
                    current_signal_dbm = available_networks_dict[current_ssid].get('signal')
                valid_networks = [item for item in available_networks_dict.items() if 'signal' in item[1]]
                if not valid_networks:
                    time.sleep(SCAN_INTERVAL)
                    continue
                best_net_item = sorted(valid_networks, key=lambda item: item[1]['signal'], reverse=True)[0]
                best_ssid = best_net_item[0]
                if best_ssid not in self.wifi_manager.known_networks:
                    time.sleep(SCAN_INTERVAL)
                    continue
                best_signal_dbm = best_net_item[1]['signal']
                if current_ssid and current_signal_dbm is not None:
                    if current_ssid == best_ssid:
                        self.log_message(f"✅ Already on the best network: {current_ssid}")
                    elif best_signal_dbm > (current_signal_dbm + SWITCH_THRESHOLD):
                        notification.notify(title="Smart Wi-Fi Switcher", message=f"Switching to {best_ssid} for a better signal.", timeout=10)
                        self.start_threaded_connect(best_ssid)
                elif self.wifi_manager.known_networks:
                    best_known_ssid = best_net_item[0]
                    notification.notify(title="Smart Wi-Fi Switcher", message=f"Connecting to best available network: {best_known_ssid}", timeout=10)
                    self.start_threaded_connect(best_known_ssid)
            except Exception as e:
                self.log_message(f"Error in auto-switch loop: {e}")
            time.sleep(SCAN_INTERVAL)

    def start_threaded_scan(self):
        self.log_message("Starting network scan...")
        thread = threading.Thread(target=self.update_networks_list, daemon=True)
        thread.start()

    def update_networks_list(self):
        available_networks = self.wifi_manager.scan_available_networks()
        self.after(0, self.populate_networks_frame, available_networks)

    def populate_networks_frame(self, available_networks):
        for widget in self.scrollable_networks_frame.winfo_children():
            widget.destroy()
        networks_to_display = available_networks
        if self.filter_known_checkbox.get():
            networks_to_display = {ssid: details for ssid, details in available_networks.items() if ssid in self.wifi_manager.known_networks}
        for i, (ssid, details) in enumerate(networks_to_display.items()):
            network_frame = customtkinter.CTkFrame(self.scrollable_networks_frame)
            network_frame.grid(row=i, column=0, padx=5, pady=5, sticky="ew")
            network_frame.grid_columnconfigure(0, weight=1)
            signal_strength = details.get('signal', 'N/A')
            label = customtkinter.CTkLabel(network_frame, text=f"{ssid} ({signal_strength} dBm)")
            label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
            if ssid in self.wifi_manager.known_networks:
                connect_button = customtkinter.CTkButton(network_frame, text="Connect", command=lambda s=ssid: self.start_threaded_connect(s))
                connect_button.grid(row=0, column=1, padx=10, pady=5)
        self.log_message(f"Scan complete. Found {len(networks_to_display)} networks.")

    def start_threaded_connect(self, ssid):
        self.log_message(f"Attempting to connect to {ssid}...")
        thread = threading.Thread(target=self.perform_connection, args=(ssid,), daemon=True)
        thread.start()

    def perform_connection(self, ssid):
        network_details = self.wifi_manager.known_networks.get(ssid)
        if not network_details:
            self.log_message(f"Error: Could not find details for known network '{ssid}'.")
            return
        network_type = network_details.get('type', 'home')
        success = False
        if network_type == 'enterprise':
            username = network_details.get('username')
            password = network_details.get('password')
            success = self.wifi_manager.connect_to_enterprise_network(ssid, username, password)
        else:
            password = network_details.get('password')
            success = self.wifi_manager.connect_to_network(ssid, password)
        if success:
            self.log_message(f"Successfully connected to {ssid}!")
        else:
            self.log_message(f"Failed to connect to {ssid}.")
        self.after(0, self.start_threaded_scan)

    def schedule_periodic_status_check(self):
        thread = threading.Thread(target=self.fetch_and_update_status, daemon=True)
        thread.start()
        self.after(5000, self.schedule_periodic_status_check)

    def fetch_and_update_status(self):
        current_ssid, current_signal = self.wifi_manager.get_current_connection()
        self.after(0, self.update_status_labels, current_ssid, current_signal)

    def update_status_labels(self, ssid, signal):
        if signal is not None:
            self.status_value_label.configure(text="Connected", text_color="green")
            self.ssid_value_label.configure(text=ssid)
            self.signal_value_label.configure(text=f"{signal}%")
        else:
            self.status_value_label.configure(text="Disconnected", text_color="orange")
            self.ssid_value_label.configure(text="N/A")
            self.signal_value_label.configure(text="N/A")

# ===================================================================
# THIS BLOCK IS ESSENTIAL - DO NOT DELETE IT
# ===================================================================
if __name__ == "__main__":
    app = App()
    app.mainloop()
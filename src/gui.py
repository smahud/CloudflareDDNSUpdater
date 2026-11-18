"""Cloudflare DDNS Updater - Compact GUI Application."""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import sys
import winreg
from pathlib import Path
from typing import Optional, List
import logging

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import Config, RecordConfig, IPDetectionConfig, get_base_dir, setup_logging
from ip_detector import IPDetector
from cloudflare import CloudflareClient
from scheduler import DDNSUpdater, Scheduler


class LogHandler(logging.Handler):
    """Logging handler that sends records to a queue for GUI display."""
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        try:
            self.log_queue.put(self.format(record))
        except Exception:
            pass


class DDNSGuiApp:
    """Compact GUI application for Cloudflare DDNS Updater."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.base_dir = get_base_dir()
        self.root.title("Cloudflare DDNS Updater")
        self.root.geometry("460x440")
        self.root.minsize(460, 440)
        self.root.resizable(True, False)

        # App state
        self.config: Optional[Config] = None
        self.cf_client: Optional[CloudflareClient] = None
        self.ip_detector: Optional[IPDetector] = None
        self.updater: Optional[DDNSUpdater] = None
        self.scheduler: Optional[Scheduler] = None
        self.scheduler_thread: Optional[threading.Thread] = None
        self.is_running = False
        self.auto_start_enabled = False
        self.auto_hide_enabled = False
        self._shutting_down = False
        self._tray_started = False

        # Queues
        self.log_queue = queue.Queue()
        self.record_rows = []  # Track record input rows

        # Load saved settings first
        self.load_settings()

        # Load or create config
        self.load_or_create_config()

        # Setup UI
        self.setup_ui()
        self.setup_logging()
        self.setup_tray()

        # Start log processor
        self.process_log_queue()

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Initialize components and start auto-scheduler
        self.root.after(100, self.initialize_app)

        # Auto-hide on start if enabled
        if self.auto_hide_enabled:
            self.root.after(200, self.hide_window)

    def load_or_create_config(self):
        """Load config from file or create default."""
        try:
            self.config = Config.load("config.yaml", self.base_dir)
        except Exception:
            self.config = self.create_default_config()

    def create_default_config(self) -> Config:
        """Create default configuration."""
        return Config(
            interval_minutes=15,
            api_token="",
            zone_identifier="",
            records=[
                RecordConfig(name="host", type="A", proxied=False, comment="DDNS managed"),
                RecordConfig(name="host", type="AAAA", proxied=False, comment="DDNS managed"),
            ],
            ip_detection=IPDetectionConfig(),
            log_level="INFO",
            log_file="ddns.log"
        )

    def save_config_to_file(self):
        """Save current config to YAML file."""
        import yaml
        data = {
            'interval_minutes': self.config.interval_minutes,
            'api_token': self.config.api_token,
            'zone_identifier': self.config.zone_identifier,
            'records': [
                {
                    'name': r.name,
                    'type': r.type,
                    'proxied': r.proxied,
                    'comment': r.comment,
                    'ttl': r.ttl
                } for r in self.config.records
            ],
            'ip_detection': {
                'ipv4_enabled': self.config.ip_detection.ipv4_enabled,
                'ipv6_enabled': self.config.ip_detection.ipv6_enabled,
                'providers': self.config.ip_detection.providers,
                'timeout_seconds': self.config.ip_detection.timeout_seconds
            },
            'log_level': self.config.log_level,
            'log_file': self.config.log_file
        }
        config_path = self.base_dir / "config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def load_settings(self):
        """Load saved settings from registry."""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\CloudflareDDNS", 0, winreg.KEY_READ)
            self.auto_start_enabled, _ = winreg.QueryValueEx(key, "AutoStart")
            self.auto_hide_enabled, _ = winreg.QueryValueEx(key, "AutoHide")
            winreg.CloseKey(key)
        except FileNotFoundError:
            pass
        except Exception:
            pass

    def save_settings(self):
        """Save settings to registry."""
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\CloudflareDDNS")
            winreg.SetValueEx(key, "AutoStart", 0, winreg.REG_DWORD, int(self.auto_start_enabled))
            winreg.SetValueEx(key, "AutoHide", 0, winreg.REG_DWORD, int(self.auto_hide_enabled))
            winreg.CloseKey(key)
        except Exception:
            pass

    def set_auto_start(self, enable: bool):
        """Enable/disable auto-start with Windows."""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            if enable:
                exe_path = sys.executable
                if exe_path.endswith("python.exe"):
                    script_path = Path(__file__).parent.parent / "src" / "main.py"
                    winreg.SetValueEx(key, "CloudflareDDNS", 0, winreg.REG_SZ,
                                     f'"{sys.executable}" "{script_path}" --gui')
                else:
                    winreg.SetValueEx(key, "CloudflareDDNS", 0, winreg.REG_SZ,
                                     f'"{exe_path}" --gui')
            else:
                try:
                    winreg.DeleteValue(key, "CloudflareDDNS")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
            self.auto_start_enabled = enable
            self.auto_start_var.set(enable)
            self.save_settings()
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"Failed to set auto-start: {e}")

    def setup_ui(self):
        """Setup the compact UI."""
        # Main container with padding
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        # === TOP: Config Inputs ===
        cfg_frame = ttk.LabelFrame(main, text="Configuration", padding=8)
        cfg_frame.pack(fill=tk.X, pady=(0, 8))

        # Row 0: API Token
        ttk.Label(cfg_frame, text="API Token:").grid(row=0, column=0, sticky=tk.W, pady=3)
        self.token_var = tk.StringVar(value=self.config.api_token)
        token_entry = ttk.Entry(cfg_frame, textvariable=self.token_var, show="*", width=50)
        token_entry.grid(row=0, column=1, sticky=tk.EW, pady=3, padx=(8, 0))
        token_entry.bind("<FocusOut>", lambda e: self.on_config_change())

        # Row 1: Domain/Zone
        ttk.Label(cfg_frame, text="Domain:").grid(row=1, column=0, sticky=tk.W, pady=3)
        self.domain_var = tk.StringVar(value=self.config.zone_identifier)
        ttk.Entry(cfg_frame, textvariable=self.domain_var, width=50).grid(row=1, column=1, sticky=tk.EW, pady=3, padx=(8, 0))
        self.domain_var.trace_add("write", lambda *_: self.on_config_change())

        # Row 2: Interval
        ttk.Label(cfg_frame, text="Interval (min):").grid(row=2, column=0, sticky=tk.W, pady=3)
        self.interval_var = tk.StringVar(value=str(self.config.interval_minutes))
        interval_spin = ttk.Spinbox(cfg_frame, from_=1, to=1440, width=8,
                                    textvariable=self.interval_var, command=self.on_config_change)
        interval_spin.grid(row=2, column=1, sticky=tk.W, pady=3, padx=(8, 0))

        cfg_frame.columnconfigure(1, weight=1)

        # === RECORDS: Compact list ===
        rec_frame = ttk.LabelFrame(main, text="DNS Records", padding=8)
        rec_frame.pack(fill=tk.X, pady=(0, 8))

        # Headers
        hdr = ttk.Frame(rec_frame)
        hdr.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(hdr, text="Name", width=12).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(hdr, text="Type", width=7).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(hdr, text="Proxy", width=7).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(hdr, text="Comment", width=22).pack(side=tk.LEFT)

        # Records container
        self.records_container = ttk.Frame(rec_frame)
        self.records_container.pack(fill=tk.X)

        # Build record rows
        self.build_record_rows()

        # Add record button
        ttk.Button(rec_frame, text="+ Add Record", command=self.add_record_row).pack(anchor=tk.W, pady=(6, 0))

        # === BOTTOM: Status & Controls ===
        bottom = ttk.Frame(main)
        bottom.pack(fill=tk.X, pady=(6, 0))

        # Left: IP Status
        ip_frame = ttk.Frame(bottom)
        ip_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.ipv4_var = tk.StringVar(value="IPv4: detecting...")
        self.ipv6_var = tk.StringVar(value="IPv6: detecting...")
        ttk.Label(ip_frame, textvariable=self.ipv4_var, font=("Segoe UI", 9)).pack(anchor=tk.W)
        ttk.Label(ip_frame, textvariable=self.ipv6_var, font=("Segoe UI", 9)).pack(anchor=tk.W)

        # Right: Buttons & Toggles
        ctrl_frame = ttk.Frame(bottom)
        ctrl_frame.pack(side=tk.RIGHT)

        # Update Now button (main action)
        self.update_btn = ttk.Button(ctrl_frame, text="Update Now", command=self.manual_update, width=14)
        self.update_btn.pack(side=tk.LEFT, padx=(0, 8))

        # Toggles
        self.auto_start_var = tk.BooleanVar(value=self.auto_start_enabled)
        ttk.Checkbutton(ctrl_frame, text="Auto-start", variable=self.auto_start_var,
                        command=self.toggle_auto_start).pack(side=tk.LEFT, padx=(0, 8))

        self.auto_hide_var = tk.BooleanVar(value=self.auto_hide_enabled)
        ttk.Checkbutton(ctrl_frame, text="Hide to tray on close", variable=self.auto_hide_var,
                        command=self.toggle_auto_hide).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(ctrl_frame, text="Hide", command=self.hide_window, width=8).pack(side=tk.LEFT)

    def build_record_rows(self):
        """Build input rows for each DNS record."""
        for widget in self.records_container.winfo_children():
            widget.destroy()
        self.record_rows.clear()

        for idx, record in enumerate(self.config.records):
            self.add_record_row(record, idx)

    def add_record_row(self, record: Optional[RecordConfig] = None, idx: Optional[int] = None):
        """Add a record input row."""
        if record is None:
            record = RecordConfig(name="", type="A", proxied=False, comment="")
            self.config.records.append(record)
            idx = len(self.config.records) - 1

        row_frame = ttk.Frame(self.records_container)
        row_frame.pack(fill=tk.X, pady=2)

        # Name
        name_var = tk.StringVar(value=record.name)
        name_entry = ttk.Entry(row_frame, textvariable=name_var, width=14)
        name_entry.pack(side=tk.LEFT, padx=(0, 4))
        name_var.trace_add("write", lambda *_, i=idx: self.update_record_name(i, name_var.get()))

        # Type
        type_var = tk.StringVar(value=record.type)
        type_combo = ttk.Combobox(row_frame, textvariable=type_var, values=["A", "AAAA"], width=6, state="readonly")
        type_combo.pack(side=tk.LEFT, padx=(0, 4))
        type_combo.bind("<<ComboboxSelected>>", lambda e, i=idx: self.update_record_type(i, type_var.get()))

        # Proxy
        proxy_var = tk.BooleanVar(value=record.proxied)
        ttk.Checkbutton(row_frame, variable=proxy_var,
                        command=lambda i=idx: self.update_record_proxy(i, proxy_var.get())).pack(side=tk.LEFT, padx=(0, 4))

        # Comment
        comment_var = tk.StringVar(value=record.comment)
        comment_entry = ttk.Entry(row_frame, textvariable=comment_var, width=24)
        comment_entry.pack(side=tk.LEFT, padx=(0, 4))
        comment_var.trace_add("write", lambda *_, i=idx: self.update_record_comment(i, comment_var.get()))

        # Delete button
        ttk.Button(row_frame, text="✕", width=3,
                   command=lambda i=idx: self.delete_record(i)).pack(side=tk.LEFT)

        self.record_rows.append({
            'frame': row_frame,
            'name_var': name_var,
            'type_var': type_var,
            'proxy_var': proxy_var,
            'comment_var': comment_var
        })

    def update_record_name(self, idx: int, value: str):
        if 0 <= idx < len(self.config.records):
            self.config.records[idx].name = value
            self.on_config_change()

    def update_record_type(self, idx: int, value: str):
        if 0 <= idx < len(self.config.records):
            self.config.records[idx].type = value
            self.on_config_change()

    def update_record_proxy(self, idx: int, value: bool):
        if 0 <= idx < len(self.config.records):
            self.config.records[idx].proxied = value
            self.on_config_change()

    def update_record_comment(self, idx: int, value: str):
        if 0 <= idx < len(self.config.records):
            self.config.records[idx].comment = value
            self.on_config_change()

    def delete_record(self, idx: int):
        if 0 <= idx < len(self.config.records):
            self.config.records.pop(idx)
            self.build_record_rows()
            self.on_config_change()

    def on_config_change(self, *args):
        """Called when any config field changes."""
        if self.config:
            self.config.api_token = self.token_var.get().strip()
            self.config.zone_identifier = self.domain_var.get().strip()
            try:
                self.config.interval_minutes = max(1, int(self.interval_var.get()))
            except ValueError:
                pass
            self.save_config_to_file()
            # Restart scheduler with new interval
            if self.is_running:
                self.restart_scheduler()

    def initialize_app(self):
        """Initialize components and start auto-scheduler."""
        self.init_components()
        self.detect_ip()
        self.refresh_record_status()
        # Auto-start scheduler if interval > 0 and required fields filled
        if self.config.interval_minutes > 0 and self.validate_required_fields(silent=True):
            self.start_scheduler()

    def init_components(self):
        """Initialize Cloudflare client, IP detector, updater."""
        if not self.cf_client and self.config.api_token and self.config.zone_identifier:
            self.cf_client = CloudflareClient(self.config.api_token, self.config.zone_identifier)

        if not self.ip_detector:
            self.ip_detector = IPDetector(
                providers=self.config.ip_detection.providers,
                timeout=self.config.ip_detection.timeout_seconds,
                ipv4_enabled=self.config.ip_detection.ipv4_enabled,
                ipv6_enabled=self.config.ip_detection.ipv6_enabled
            )

        if not self.updater and self.cf_client and self.ip_detector:
            self.updater = DDNSUpdater(self.config, self.cf_client, self.ip_detector, self.logger)

    def validate_required_fields(self, silent=False) -> bool:
        """Validate required fields are filled."""
        if not self.config.api_token.strip():
            if not silent:
                messagebox.showerror("Error", "API Token is required")
            return False
        if not self.config.zone_identifier.strip():
            if not silent:
                messagebox.showerror("Error", "Domain is required")
            return False
        if not self.config.records:
            if not silent:
                messagebox.showerror("Error", "At least one DNS record required")
            return False
        for r in self.config.records:
            if not r.name.strip():
                if not silent:
                    messagebox.showerror("Error", "Record name cannot be empty")
                return False
        return True

    def setup_logging(self):
        """Setup logging to file and GUI queue."""
        self.logger = setup_logging(self.config, self.base_dir)

        # Add queue handler for GUI
        qh = LogHandler(self.log_queue)
        qh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S'))
        self.logger.addHandler(qh)

    def setup_tray(self):
        """Setup system tray icon."""
        self._create_tray_icon()

    def _create_tray_icon(self):
        """Create or recreate the tray icon with menu."""
        try:
            import pystray
            from PIL import Image, ImageDraw

            icon_path = self.base_dir / "icon.ico"
            if icon_path.exists():
                image = Image.open(icon_path)
            else:
                image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
                draw = ImageDraw.Draw(image)
                draw.ellipse([8, 8, 56, 56], fill='#4A90D9')
                draw.text((28, 20), "DDNS", fill='white', anchor="mm")

            menu = pystray.Menu(
                pystray.MenuItem("Show", self.show_window, default=True),
                pystray.MenuItem("Update Now", self.manual_update),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Close App", self.quit_app)
            )

            self.tray_icon = pystray.Icon("cloudflare_ddns", image, "Cloudflare DDNS Updater", menu)
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.warning(f"Tray not available: {e}")
            self.tray_icon = None

    def run_tray(self):
        if self.tray_icon:
            try:
                self.tray_icon.run()
            except Exception:
                pass

    def process_log_queue(self):
        """Process log messages from queue."""
        try:
            while True:
                record = self.log_queue.get_nowait()
                # Could add a small log display here if needed
        except queue.Empty:
            pass
        if not self._shutting_down:
            self.root.after(200, self.process_log_queue)

    def detect_ip(self):
        """Detect public IP addresses."""
        def _detect():
            try:
                if not self.ip_detector:
                    self.init_components()
                ips = self.ip_detector.detect_all()
                self.root.after(0, lambda: self.update_ip_display(ips))
            except Exception as e:
                if hasattr(self, 'logger'):
                    self.logger.error(f"IP detect failed: {e}")

        threading.Thread(target=_detect, daemon=True).start()

    def update_ip_display(self, ips):
        if ips.ipv4:
            self.ipv4_var.set(f"IPv4: {ips.ipv4}")
        else:
            self.ipv4_var.set("IPv4: not detected")

        if ips.ipv6:
            self.ipv6_var.set(f"IPv6: {ips.ipv6}")
        else:
            self.ipv6_var.set("IPv6: not detected (will use IPv4-mapped if AAAA record exists)")

    def _get_aaaa_content(self, ipv4: str, ipv6: Optional[str]) -> str:
        """Get AAAA record content. If no IPv6, use IPv4-mapped IPv6 address."""
        if ipv6:
            return ipv6
        if ipv4:
            return f"::ffff:{ipv4}"
        return ""

    def refresh_record_status(self):
        """Refresh DNS record status from Cloudflare."""
        def _refresh():
            try:
                if not self.cf_client:
                    self.init_components()
                if not self.cf_client:
                    return

                for idx, record in enumerate(self.config.records):
                    existing = self.cf_client.get_dns_record(record.name, record.type)
                    # Could update UI indicator here
            except Exception as e:
                if hasattr(self, 'logger'):
                    self.logger.error(f"Record refresh failed: {e}")

        threading.Thread(target=_refresh, daemon=True).start()

    def manual_update(self):
        """Manual update triggered by button."""
        if not self.validate_required_fields():
            return

        self.update_btn.config(state=tk.DISABLED, text="Updating...")
        self.root.update()

        def _update():
            try:
                self.init_components()
                if self.updater:
                    # Override AAAA content for updater if needed
                    self._prepare_updater_ips()
                    self.updater.run_once()
                self.root.after(0, self.on_update_done)
            except Exception as e:
                if hasattr(self, 'logger'):
                    self.logger.error(f"Update failed: {e}")
                self.root.after(0, lambda: self.on_update_error(str(e)))

        threading.Thread(target=_update, daemon=True).start()

    def _prepare_updater_ips(self):
        """Prepare IP detector to return IPv4-mapped IPv6 for AAAA records when no native IPv6."""
        if not self.ip_detector:
            return

        # Detect IPs first
        ips = self.ip_detector.detect_all()

        # If we have IPv4 but no IPv6, and we have AAAA records, we need to handle this
        # The IPDetector will be called again in updater, so we can't easily override here
        # Instead, we'll modify the cloudflare client to handle this case

    def on_update_done(self):
        self.update_btn.config(state=tk.NORMAL, text="Update Now")
        self.detect_ip()
        self.refresh_record_status()
        if hasattr(self, 'logger'):
            self.logger.info("Manual update completed")

    def on_update_error(self, error: str):
        self.update_btn.config(state=tk.NORMAL, text="Update Now")
        messagebox.showerror("Update Failed", error)

    def start_scheduler(self):
        """Start background scheduler."""
        if self.is_running:
            return

        try:
            self.init_components()
            if not self.updater:
                return

            self.scheduler = Scheduler(self.config.interval_minutes, self.updater)
            self.scheduler_thread = threading.Thread(target=self.scheduler.run, daemon=True)
            self.scheduler_thread.start()

            self.is_running = True
            if hasattr(self, 'logger'):
                self.logger.info(f"Scheduler started (every {self.config.interval_minutes} min)")
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"Scheduler start failed: {e}")

    def restart_scheduler(self):
        """Restart scheduler with new interval."""
        self.stop_scheduler()
        if self.validate_required_fields(silent=True):
            self.start_scheduler()

    def stop_scheduler(self):
        """Stop background scheduler."""
        if self.scheduler:
            self.scheduler.stop()
            # Wait for scheduler thread to finish (with timeout)
            if self.scheduler_thread and self.scheduler_thread.is_alive():
                self.scheduler_thread.join(timeout=2.0)
        self.is_running = False
        if hasattr(self, 'logger'):
            self.logger.info("Scheduler stopped")

    def toggle_auto_start(self):
        self.set_auto_start(self.auto_start_var.get())

    def toggle_auto_hide(self):
        self.auto_hide_enabled = self.auto_hide_var.get()
        self.save_settings()

    def hide_window(self):
        """Hide to system tray."""
        self.root.withdraw()
        # Always recreate tray icon for clean state
        self._create_tray_icon()
        if self.tray_icon and not self._tray_started:
            self._tray_started = True
            threading.Thread(target=self.run_tray, daemon=True).start()

    def show_window(self, icon=None, item=None):
        self.root.after(0, self._do_show)

    def _do_show(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
            self.tray_icon = None
            self._tray_started = False

    def on_close(self):
        """Close button behavior:
        - If 'Hide to tray on close' is checked: hide to tray
        - Otherwise: quit application
        """
        if self.auto_hide_enabled:
            self.hide_window()
        else:
            self.quit_app()

    def quit_app(self, icon=None, item=None):
        """Quit completely."""
        self._shutting_down = True
        if hasattr(self, 'logger'):
            self.logger.info("Shutting down...")
        self.stop_scheduler()
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
            self.tray_icon = None
        # Schedule force exit on main thread
        self.root.after(0, self._force_exit)

    def _force_exit(self):
        """Force exit the application."""
        try:
            self.root.quit()  # Stop mainloop
            self.root.destroy()
        finally:
            import os
            os._exit(0)


def main():
    root = tk.Tk()
    try:
        root.iconbitmap(default="")
    except:
        pass
    app = DDNSGuiApp(root)
    root.mainloop()
    # Ensure clean exit after mainloop
    import os
    os._exit(0)


if __name__ == "__main__":
    main()
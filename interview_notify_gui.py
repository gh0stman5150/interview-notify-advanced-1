#!/usr/bin/env python3

"""
GUI wrapper for interview-notify-advanced
Provides a user-friendly interface for configuring and running the notifier
"""

try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext, filedialog, messagebox
except ImportError as e:
    print("ERROR: tkinter is not available on your system.")
    print()
    print("To fix this:")
    print()
    print("  macOS (Homebrew Python):")
    print("    brew install python-tk@3.13  # or your Python version")
    print()
    print("  macOS (use system Python instead):")
    print("    /usr/bin/python3 interview_notify_gui.py")
    print()
    print("  Linux (Debian/Ubuntu):")
    print("    sudo apt-get install python3-tk")
    print()
    print("  Linux (Fedora/RHEL):")
    print("    sudo dnf install python3-tkinter")
    print()
    print("  Windows:")
    print("    Tkinter should be included - reinstall Python and check 'tcl/tk' option")
    print()
    import sys
    sys.exit(1)

import subprocess
import threading
import json
import os
from pathlib import Path
import sys
import queue

from interview_modes import default_bot_nicks, normalize_mode

VERSION = '1.5.0'
CONFIG_FILE = Path.home() / '.interview-notify-config.json'
SCRIPT_FILE = Path(__file__).resolve().with_name('interview_notify.py')


class InterviewNotifyGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Interview Notify Advanced v{VERSION}")
        self.root.geometry("900x750")
        self.root.minsize(800, 600)

        self.process = None
        self.log_queue = queue.Queue()
        self.log_dirs = []

        self.create_widgets()

        # Load config after widgets are created and rendered
        self.root.after(100, self.load_config)

    def create_widgets(self):
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # === Configuration Section ===
        config_frame = ttk.LabelFrame(main_frame, text="Configuration", padding="10")
        config_frame.pack(fill=tk.X, pady=(0, 10))

        # Topic and Server row
        row1 = ttk.Frame(config_frame)
        row1.pack(fill=tk.X, pady=5)

        ttk.Label(row1, text="ntfy Topic:", width=15).pack(side=tk.LEFT)
        self.topic_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.topic_var, width=25).pack(side=tk.LEFT, padx=5)

        ttk.Label(row1, text="Server:", width=10).pack(side=tk.LEFT, padx=(15, 0))
        self.server_var = tk.StringVar(value="https://ntfy.sh/")
        ttk.Entry(row1, textvariable=self.server_var, width=25).pack(side=tk.LEFT, padx=5)

        # Nick and Bot Nicks row
        row2 = ttk.Frame(config_frame)
        row2.pack(fill=tk.X, pady=5)

        ttk.Label(row2, text="Your Nick:", width=15).pack(side=tk.LEFT)
        self.nick_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.nick_var, width=25).pack(side=tk.LEFT, padx=5)

        ttk.Label(row2, text="Bot Nicks:", width=10).pack(side=tk.LEFT, padx=(15, 0))
        self.bot_nicks_var = tk.StringVar(value="Gatekeeper")
        ttk.Entry(row2, textvariable=self.bot_nicks_var, width=25).pack(side=tk.LEFT, padx=5)

        # Mode and Rate Limit row
        row3 = ttk.Frame(config_frame)
        row3.pack(fill=tk.X, pady=5)

        ttk.Label(row3, text="Mode:", width=15).pack(side=tk.LEFT)
        self.mode_var = tk.StringVar(value="red")
        mode_combo = ttk.Combobox(row3, textvariable=self.mode_var, values=["red", "ops"],
                                  state="readonly", width=22)
        mode_combo.pack(side=tk.LEFT, padx=5)
        mode_combo.bind("<<ComboboxSelected>>", self.on_mode_changed)

        ttk.Label(row3, text="Rate Limit (sec):", width=15).pack(side=tk.LEFT, padx=(15, 0))
        self.rate_limit_var = tk.StringVar(value="60")
        ttk.Entry(row3, textvariable=self.rate_limit_var, width=22).pack(side=tk.LEFT, padx=5)

        # Log Directories
        log_dir_label = ttk.Label(config_frame, text="IRC Log Files or Directories:")
        log_dir_label.pack(anchor=tk.W, pady=(10, 5))

        log_dir_container = ttk.Frame(config_frame)
        log_dir_container.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        self.log_dir_listbox = tk.Listbox(log_dir_container, height=4)
        self.log_dir_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        log_dir_scrollbar = ttk.Scrollbar(log_dir_container, orient=tk.VERTICAL,
                                         command=self.log_dir_listbox.yview)
        log_dir_scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        self.log_dir_listbox.configure(yscrollcommand=log_dir_scrollbar.set)

        log_dir_btn_frame = ttk.Frame(log_dir_container)
        log_dir_btn_frame.pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(log_dir_btn_frame, text="Add Directory",
                  command=self.add_log_dir).pack(pady=2, fill=tk.X)
        ttk.Button(log_dir_btn_frame, text="Add Log File",
                  command=self.add_log_file).pack(pady=2, fill=tk.X)
        ttk.Button(log_dir_btn_frame, text="Remove",
                  command=self.remove_log_dir).pack(pady=2, fill=tk.X)

        # Options
        options_frame = ttk.Frame(config_frame)
        options_frame.pack(fill=tk.X, pady=(10, 0))

        self.check_bot_nicks_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Check bot nicks",
                       variable=self.check_bot_nicks_var).pack(side=tk.LEFT, padx=5)

        self.enable_notif_log_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Enable notification log",
                       variable=self.enable_notif_log_var,
                       command=self.toggle_notif_log).pack(side=tk.LEFT, padx=5)

        self.notif_log_var = tk.StringVar()
        self.notif_log_entry = ttk.Entry(options_frame, textvariable=self.notif_log_var,
                                         width=30, state=tk.DISABLED)
        self.notif_log_entry.pack(side=tk.LEFT, padx=5)

        self.notif_log_button = ttk.Button(options_frame, text="Browse",
                                          command=self.browse_notif_log, state=tk.DISABLED)
        self.notif_log_button.pack(side=tk.LEFT)

        # === Control Section ===
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=10)

        self.start_button = ttk.Button(control_frame, text="▶ Start Monitoring",
                                      command=self.start_monitoring)
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = ttk.Button(control_frame, text="⬛ Stop",
                                     command=self.stop_monitoring, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        ttk.Button(control_frame, text="💾 Save Config",
                  command=self.save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="📂 Load Config",
                  command=self.load_config).pack(side=tk.LEFT, padx=5)

        # Status
        ttk.Label(control_frame, text="Status:").pack(side=tk.LEFT, padx=(20, 5))
        self.status_label = ttk.Label(control_frame, text="⬤ Stopped", foreground="red")
        self.status_label.pack(side=tk.LEFT)

        # === Log Viewer Section ===
        log_frame = ttk.LabelFrame(main_frame, text="Live Logs", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, wrap=tk.WORD,
                                                  state=tk.DISABLED, font="TkFixedFont")
        self.log_text.pack(fill=tk.BOTH, expand=True)

        log_buttons = ttk.Frame(log_frame)
        log_buttons.pack(fill=tk.X, pady=(5, 0))

        ttk.Button(log_buttons, text="Clear Logs", command=self.clear_logs).pack(side=tk.LEFT, padx=5)

        self.auto_scroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(log_buttons, text="Auto-scroll",
                       variable=self.auto_scroll_var).pack(side=tk.LEFT, padx=5)

        # Add initial welcome message
        self.log_message("=" * 60)
        self.log_message(f"Interview Notify Advanced v{VERSION} - GUI")
        self.log_message("=" * 60)
        self.log_message("Configure settings above and click 'Start Monitoring'")
        self.log_message("")

        # Start log update timer
        self.update_logs()

    def toggle_notif_log(self):
        if self.enable_notif_log_var.get():
            self.notif_log_entry.config(state=tk.NORMAL)
            self.notif_log_button.config(state=tk.NORMAL)
        else:
            self.notif_log_entry.config(state=tk.DISABLED)
            self.notif_log_button.config(state=tk.DISABLED)

    def on_mode_changed(self, _event=None):
        """Update an untouched default bot nick when the mode changes."""
        mode = normalize_mode(self.mode_var.get())
        current_bot_nicks = self.bot_nicks_var.get().strip()
        if mode == "ops" and current_bot_nicks in ("", "Gatekeeper"):
            self.bot_nicks_var.set(default_bot_nicks(mode))
        elif mode == "red" and current_bot_nicks in ("", "Hermes"):
            self.bot_nicks_var.set(default_bot_nicks(mode))

    def browse_notif_log(self):
        filename = filedialog.asksaveasfilename(
            title="Select notification log file",
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            self.notif_log_var.set(filename)

    def add_log_dir(self):
        directory = filedialog.askdirectory(title="Select IRC log directory")
        if directory and directory not in self.log_dirs:
            self.log_dirs.append(directory)
            self.log_dir_listbox.insert(tk.END, directory)

    def add_log_file(self):
        filename = filedialog.askopenfilename(
            title="Select IRC log file",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")],
        )
        if filename and filename not in self.log_dirs:
            self.log_dirs.append(filename)
            self.log_dir_listbox.insert(tk.END, filename)

    def remove_log_dir(self):
        selection = self.log_dir_listbox.curselection()
        if selection:
            index = selection[0]
            self.log_dir_listbox.delete(index)
            del self.log_dirs[index]

    def validate_config(self):
        """Validate configuration before starting"""
        if not self.topic_var.get():
            messagebox.showerror("Configuration Error", "ntfy Topic is required")
            return False
        if not self.nick_var.get():
            messagebox.showerror("Configuration Error", "Your Nick is required")
            return False
        if not self.log_dirs:
            messagebox.showerror("Configuration Error", "At least one log file or directory is required")
            return False
        return True

    def start_monitoring(self):
        if not self.validate_config():
            return

        # Build command
        cmd = [sys.executable, str(SCRIPT_FILE)]
        cmd.extend(["--topic", self.topic_var.get()])
        cmd.extend(["--server", self.server_var.get()])
        cmd.extend(["--nick", self.nick_var.get()])
        cmd.extend(["--bot-nicks", self.bot_nicks_var.get()])
        cmd.extend(["--mode", self.mode_var.get()])
        cmd.extend(["--rate-limit", self.rate_limit_var.get()])

        for log_dir in self.log_dirs:
            cmd.extend(["--log-dir", log_dir])

        if not self.check_bot_nicks_var.get():
            cmd.append("--no-check-bot-nicks")

        if self.enable_notif_log_var.get() and self.notif_log_var.get():
            cmd.extend(["--notification-log", self.notif_log_var.get()])

        # Add verbosity
        cmd.extend(["-v", "-v", "-v"])

        try:
            self.log_message("Starting interview-notify with command:")
            self.log_message(" ".join(cmd))
            self.log_message("-" * 60)

            # Start process
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1,
                env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}
            )

            # Start thread to read output
            self.output_thread = threading.Thread(target=self.read_output, daemon=True)
            self.output_thread.start()

            # Update UI
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.status_label.config(text="● Running", foreground="green")

            self.log_message("Monitoring started successfully!")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to start monitoring: {e}")
            self.log_message(f"ERROR: {e}")

    def stop_monitoring(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process = None

            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.status_label.config(text="● Stopped", foreground="red")

            self.log_message("-" * 60)
            self.log_message("Monitoring stopped")

    def read_output(self):
        """Read process output in separate thread"""
        try:
            for line in iter(self.process.stdout.readline, ''):
                if line:
                    self.log_queue.put(line.rstrip())
        except Exception as e:
            self.log_queue.put(f"ERROR reading output: {e}")

    def update_logs(self):
        """Update log display from queue"""
        try:
            while True:
                line = self.log_queue.get_nowait()
                self.log_message(line)
        except queue.Empty:
            pass

        # Check if process died unexpectedly
        if self.process and self.process.poll() is not None:
            self.log_message("Process terminated unexpectedly!")
            self.stop_monitoring()

        # Schedule next update
        self.root.after(100, self.update_logs)

    def log_message(self, message):
        """Add message to log viewer"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        if self.auto_scroll_var.get():
            self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def clear_logs(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)

    def save_config(self):
        """Save configuration to file"""
        config = {
            "topic": self.topic_var.get(),
            "server": self.server_var.get(),
            "nick": self.nick_var.get(),
            "bot_nicks": self.bot_nicks_var.get(),
            "mode": normalize_mode(self.mode_var.get()),
            "rate_limit": self.rate_limit_var.get(),
            "log_dirs": self.log_dirs,
            "check_bot_nicks": self.check_bot_nicks_var.get(),
            "enable_notif_log": self.enable_notif_log_var.get(),
            "notif_log": self.notif_log_var.get()
        }

        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            messagebox.showinfo("Success", f"Configuration saved to {CONFIG_FILE}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save config: {e}")

    def load_config(self):
        """Load configuration from file"""
        if not CONFIG_FILE.exists():
            return

        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)

            self.topic_var.set(config.get("topic", ""))
            self.server_var.set(config.get("server", "https://ntfy.sh/"))
            self.nick_var.set(config.get("nick", ""))
            mode = normalize_mode(config.get("mode", "red"))
            self.mode_var.set(mode)
            self.bot_nicks_var.set(config.get("bot_nicks") or default_bot_nicks(mode))
            self.rate_limit_var.set(config.get("rate_limit", "60"))
            self.check_bot_nicks_var.set(config.get("check_bot_nicks", True))
            self.enable_notif_log_var.set(config.get("enable_notif_log", False))
            self.notif_log_var.set(config.get("notif_log", ""))

            # Load log directories
            self.log_dirs = config.get("log_dirs", [])
            self.log_dir_listbox.delete(0, tk.END)
            for log_dir in self.log_dirs:
                self.log_dir_listbox.insert(tk.END, log_dir)

            self.toggle_notif_log()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load config: {e}")

    def on_closing(self):
        """Handle window closing"""
        if self.process:
            if messagebox.askokcancel("Quit", "Monitoring is running. Stop and quit?"):
                self.stop_monitoring()
                self.root.destroy()
        else:
            self.root.destroy()


def main():
    root = tk.Tk()
    app = InterviewNotifyGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()

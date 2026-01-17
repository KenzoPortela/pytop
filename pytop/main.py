import curses
import psutil
import time
import wmi
import winreg

# Initialize WMI
try:
    wmi_obj = wmi.WMI(namespace="root\\CIMV2")
except:
    wmi_obj = None

def get_gradient_color(index, total_width):
    """Returns the color pair index based on the position in the bar."""
    pos = (index / total_width) * 100
    if pos < 40: return 1   # Green
    if pos < 65: return 5   # Yellow
    if pos < 85: return 6   # Orange
    return 7                # Red

def draw_bar(stdscr, y, x, label, percent, width, extra_info=""):
    """Draws a bar with a green -> yellow -> orange -> red gradient."""
    percent = max(0, min(100, percent))
    filled = int((percent / 100) * width)
    
    try:
        stdscr.addstr(y, x, f"{label}")
        bar_x = x + len(label) + 1
        stdscr.addstr(y, bar_x, "[")
        
        # Draw each pipe character with its specific gradient color
        for i in range(width):
            if i < filled:
                color = get_gradient_color(i, width)
                stdscr.addstr("|", curses.color_pair(color))
            else:
                stdscr.addstr(" ", curses.color_pair(0))
        
        stdscr.addstr("]")
        percent_str = f"{percent:5.1f}%"
        stdscr.addstr(y, bar_x + width + 2, percent_str)
        
        if extra_info:
            stdscr.addstr(f" {extra_info}", curses.color_pair(2))
    except curses.error:
        pass

import winreg

def get_physical_vram_capacity():
    """Tries multiple methods to get the true 64-bit VRAM capacity."""
    # Method 1: Registry check (Best for 4GB+ cards)
    try:
        path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            for i in range(10):
                try:
                    with winreg.OpenKey(key, f"{i:04d}") as subkey:
                        val, _ = winreg.QueryValueEx(subkey, "HardwareInformation.qwMemorySize")
                        if val and int(val) > 0: 
                            return int(val)
                except: continue
    except: pass

    # Method 2: WMI check (Will be negative if >4GB, so we fix the overflow)
    try:
        for controller in wmi_obj.Win32_VideoController():
            if controller.AdapterRAM:
                ram = int(controller.AdapterRAM)
                if ram < 0: # Handle the 32-bit overflow
                    ram += 2**32
                return ram
    except: pass

    # Method 3: Hard Fallback (If you know you have 8GB, we use it as a last resort)
    return 8 * 1024**3 

# Initialize this globally
TOTAL_VRAM_BYTES = get_physical_vram_capacity()

def get_gpu_data():
    gpu_usage = 0
    vram_percent = 0
    used_bytes = 0
    
    if not wmi_obj:
        return 0, 0, "N/A"

    try:
        # GPU Load
        gpu_stats = wmi_obj.query("SELECT UtilizationPercentage FROM Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine WHERE Name LIKE '%engtype_3D%'")
        if gpu_stats:
            gpu_usage = min(sum(int(item.UtilizationPercentage) for item in gpu_stats), 100)

        # Dedicated VRAM Usage
        vram_stats = wmi_obj.query("SELECT DedicatedUsage FROM Win32_PerfRawData_GPUPerformanceCounters_GPUAdapterMemory")
        if vram_stats:
            # We use max() because different 'engines' report usage; the highest is the card total.
            # We use abs() and handle potential 32-bit overflow for used_bytes too.
            raw_used = max(int(item.DedicatedUsage) for item in vram_stats)
            if raw_used < 0: 
                raw_used += 2**32
            used_bytes = raw_used
            
        vram_percent = (used_bytes / TOTAL_VRAM_BYTES) * 100
        vram_info = f"{used_bytes / (1024**3):.2f}/{TOTAL_VRAM_BYTES / (1024**3):.1f}GB"
        
    except Exception as e:
        # If it still fails, return 0s instead of crashing the UI
        return 0, 0, f"Sync Error"
        
    return gpu_usage, vram_percent, vram_info

def main(stdscr):
    curses.curs_set(0) 
    stdscr.nodelay(True) 
    stdscr.keypad(True) 
    
    # Initialize Terminal Colors
    curses.start_color()
    curses.use_default_colors()
    
    # Gradient Pairs (FG, BG)
    curses.init_pair(1, curses.COLOR_GREEN, -1)
    curses.init_pair(2, curses.COLOR_CYAN, -1)
    curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_CYAN) # Selection - white text
    curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_GREEN) # Header - white text
    curses.init_pair(5, curses.COLOR_YELLOW, -1)               # Yellow
    curses.init_pair(6, 208, -1)                               # Orange (Extended color code)
    curses.init_pair(7, curses.COLOR_RED, -1)                  # Red
    curses.init_pair(8, curses.COLOR_BLACK, curses.COLOR_WHITE) # Title bar - black on white

    selected_idx = 0
    start_time = time.time()

    while True:
        try:
            stdscr.erase() 
            h, w = stdscr.getmaxyx()
            
            # Ensure minimum terminal size
            if h < 15 or w < 60:
                stdscr.addstr(0, 0, "Terminal too small! Minimum: 60x15")
                stdscr.refresh()
                time.sleep(0.3)
                continue
            
            # Calculate dynamic dimensions
            bar_width = min(20, max(10, (w - 50) // 4))  # Adaptive bar width
            mid_point = w // 2
            
            # --- TITLE BAR ---
            title = " PYTOP "
            try:
                stdscr.addstr(0, 0, title.center(w)[:w], curses.color_pair(8))
            except:
                stdscr.addstr(0, 0, title.center(w)[:w], curses.color_pair(2))
            
            # --- SYSTEM INFO SECTION ---
            current_y = 2
            
            # Left column - CPU cores
            cpu_percents = psutil.cpu_percent(percpu=True)
            freq = psutil.cpu_freq()
            ghz = freq.current / 1000 if freq else 0.0
            
            cpu_label_width = 5
            for i, cpu in enumerate(cpu_percents):
                if current_y >= h - 2:
                    break
                extra = f"{ghz:.2f}GHz" if i == 0 else ""
                draw_bar(stdscr, current_y, 1, f"CPU{i+1:>2}", cpu, bar_width, extra)
                current_y += 1
            
            # Right column - Memory, GPU, System info
            right_y = 2
            right_x = mid_point
            
            # Memory
            mem = psutil.virtual_memory()
            draw_bar(stdscr, right_y, right_x, "Mem ", mem.percent, bar_width, 
                    f"{mem.used/(1024**3):.2f}/{mem.total/(1024**3):.1f}GB")
            right_y += 1
            
            # GPU
            gpu_load, vram_pct, vram_txt = get_gpu_data()
            draw_bar(stdscr, right_y, right_x, "GPU ", gpu_load, bar_width)
            right_y += 1
            draw_bar(stdscr, right_y, right_x, "VRAM", vram_pct, bar_width, vram_txt)
            right_y += 2
            
            # System stats
            try:
                stdscr.addstr(right_y, right_x, f"Tasks: {len(psutil.pids())}", curses.color_pair(2))
                right_y += 1
                uptime_str = time.strftime('%H:%M:%S', time.gmtime(time.time()-start_time))
                stdscr.addstr(right_y, right_x, f"Uptime: {uptime_str}", curses.color_pair(2))
            except curses.error:
                pass
            
            # --- SEPARATOR LINE ---
            separator_y = max(current_y, right_y) + 2
            if separator_y < h - 3:
                try:
                    stdscr.addstr(separator_y, 0, "-" * w, curses.color_pair(2))
                except curses.error:
                    pass
            
            # --- PROCESS LIST HEADER ---
            header_y = separator_y + 1
            if header_y < h - 2:
                # Dynamic column widths
                pid_width = 8
                user_width = min(15, max(10, (w - 30) // 4))
                cpu_width = 6
                mem_width = 6
                cmd_width = w - pid_width - user_width - cpu_width - mem_width - 4
                
                header = f"{'PID':<{pid_width}} {'USER':<{user_width}} {'CPU%':>{cpu_width}} {'MEM%':>{mem_width}} {'COMMAND'}"
                try:
                    stdscr.addstr(header_y, 0, header[:w].ljust(w), curses.color_pair(4) | curses.A_BOLD)
                except:
                    stdscr.addstr(header_y, 0, header[:w].ljust(w), curses.color_pair(4))
            
            # --- PROCESS LIST ---
            procs = []
            for p in psutil.process_iter(['pid', 'username', 'cpu_percent', 'memory_percent', 'name']):
                try:
                    info = p.info
                    info['username'] = info['username'] if info['username'] else "SYSTEM"
                    procs.append(info)
                except: 
                    continue

            process_start_y = header_y + 1
            visible_rows = h - process_start_y - 1
            visible = sorted(procs, key=lambda x: x['cpu_percent'], reverse=True)[:visible_rows]
            
            for i, info in enumerate(visible):
                y = process_start_y + i
                if y >= h - 1:
                    break
                
                username = str(info['username'])[:user_width-1]
                line = (f"{info['pid']:<{pid_width}} "
                       f"{username:<{user_width}} "
                       f"{info['cpu_percent']:>{cpu_width}.1f} "
                       f"{info['memory_percent']:>{mem_width}.1f} "
                       f"{info['name']}")
                
                try:
                    attr = curses.color_pair(3) | curses.A_BOLD if i == selected_idx else 0
                    stdscr.addstr(y, 0, line[:w].ljust(w), attr)
                except:
                    try:
                        attr = curses.color_pair(3) if i == selected_idx else 0
                        stdscr.addstr(y, 0, line[:w].ljust(w), attr)
                    except curses.error:
                        pass

            # --- FOOTER ---
            footer = " [q] Quit  [k] Kill  [Up/Down] Select "
            try:
                stdscr.addstr(h-1, 0, footer.center(w)[:w], curses.color_pair(8))
            except:
                try:
                    stdscr.addstr(h-1, 0, footer.center(w)[:w], curses.color_pair(2))
                except curses.error:
                    pass
            
            stdscr.refresh()

            key = stdscr.getch()
            if key == ord('q'): 
                break
            elif key == curses.KEY_UP and selected_idx > 0: 
                selected_idx -= 1
            elif key == curses.KEY_DOWN and selected_idx < len(visible)-1: 
                selected_idx += 1
            elif key == ord('k'):
                try: 
                    psutil.Process(visible[selected_idx]['pid']).terminate()
                except: 
                    pass
            
            time.sleep(0.3)
        except (curses.error, KeyboardInterrupt):
            break

def run():
    """Entry point for the pytop command."""
    curses.wrapper(main)

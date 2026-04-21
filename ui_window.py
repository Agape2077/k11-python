import tkinter as tk
from tkinter import ttk, messagebox
HID_MAP = {
    'a': 4, 'b': 5, 'c': 6, 'd': 7, 'e': 8, 'f': 9, 'g': 10, 'h': 11, 'i': 12,
    'j': 13, 'k': 14, 'l': 15, 'm': 16, 'n': 17, 'o': 18, 'p': 19, 'q': 20,
    'r': 21, 's': 22, 't': 23, 'u': 24, 'v': 25, 'w': 26, 'x': 27, 'y': 28, 'z': 29,
    '1': 30, '2': 31, '3': 32, '4': 33, '5': 34, '6': 35, '7': 36, '8': 37, '9': 38, '0': 39,
    'enter': 40, 'esc': 41, 'backspace': 42, 'tab': 43, 'space': 44,
    'f1': 58, 'f2': 59, 'f3': 60, 'f4': 61, 'f5': 62, 'f6': 63, 'f7': 64, 'f8': 65,
}

# 多媒体键对应 Type 48 (0x30)
MEDIA_MAP = {
    "音量 +": 233, "音量 -": 234, "静音": 226, "下一首": 181, "上一首": 182, "播放/暂停": 205
    }

class SettingsWindow:

    def __init__(self, driver_instance):
        self.driver = driver_instance # 接收从 main_tray 传来的硬件驱动
        self.root = tk.Tk()
        self.root.title("K-snake X11 驱动控制台")
        self.root.geometry("600x500")
        self.root.resizable(False, False)
        
        # 拦截右上角的 X，改为隐藏窗口而不是退出
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        
        # --- UI 变量 ---
        self.status_var = tk.StringVar(value="状态: 驱动后台运行中...")
        self.battery_var = tk.StringVar(value="电量: --%")
        
        self.dpi_vars = [tk.IntVar(value=800), tk.IntVar(value=1200), tk.IntVar(value=1600), 
                         tk.IntVar(value=3200), tk.IntVar(value=5000), tk.IntVar(value=12000)]
        self.current_dpi_var = tk.IntVar(value=0)
        self.report_rate_var = tk.IntVar(value=2)
        self.lod_var = tk.IntVar(value=1)
        self.light_mode_var = tk.IntVar(value=2)

        self.setup_ui()
        

    def setup_ui(self):
        # 顶部状态栏
        status_frame = ttk.Frame(self.root, padding=10)
        status_frame.pack(fill=tk.X)
        ttk.Label(status_frame, textvariable=self.status_var, font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        ttk.Label(status_frame, textvariable=self.battery_var, foreground="green", font=("Arial", 10, "bold")).pack(side=tk.RIGHT)

        notebook = ttk.Notebook(self.root)
        notebook.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)

        # 1. 性能设置页
        perf_frame = ttk.Frame(notebook, padding=10)
        notebook.add(perf_frame, text="性能设置")
        self.dpi_colors = ["#FF0000", "#00FF00", "#0000FF", "#FFCC00", "#00FFFF", "#FF00FF"]
        

        ttk.Label(perf_frame, text="DPI 设置 (200 - 12000)", font=("Arial", 10, "bold")).grid(row=0, column=0, columnspan=2, pady=5, sticky=tk.W)
        
        for i in range(6):
            # 添加彩色小方块指示器
            color_box = tk.Label(perf_frame, width=2, bg=self.dpi_colors[i], relief="ridge")
            color_box.grid(row=i+1, column=0, padx=(0, 5), pady=2, sticky=tk.W)
            
            # 调整单选框位置，不要挡住颜色块
            ttk.Radiobutton(perf_frame, text=f"档位 {i+1}", variable=self.current_dpi_var, value=i).grid(row=i+1, column=0, padx=(25, 5), pady=2, sticky=tk.W)
            ttk.Entry(perf_frame, textvariable=self.dpi_vars[i], width=10).grid(row=i+1, column=1, padx=5, pady=2)
        
        ttk.Label(perf_frame, text="DPI 设置 (200 - 12000)", font=("Arial", 10, "bold")).grid(row=0, column=0, columnspan=2, pady=5, sticky=tk.W)

        ttk.Label(perf_frame, text="回报率 (Hz)", font=("Arial", 10, "bold")).grid(row=0, column=2, padx=20, pady=5, sticky=tk.W)
        rates = [("125Hz", 0), ("250Hz", 1), ("500Hz", 2), ("1000Hz", 3)]
        for i, (text, val) in enumerate(rates):
            ttk.Radiobutton(perf_frame, text=text, variable=self.report_rate_var, value=val).grid(row=i+1, column=2, padx=20, sticky=tk.W)

        ttk.Label(perf_frame, text="静默高度 (LOD)", font=("Arial", 10, "bold")).grid(row=5, column=2, padx=20, pady=5, sticky=tk.W)
        ttk.Radiobutton(perf_frame, text="1.0 mm", variable=self.lod_var, value=1).grid(row=6, column=2, padx=20, sticky=tk.W)
        ttk.Radiobutton(perf_frame, text="2.0 mm", variable=self.lod_var, value=2).grid(row=7, column=2, padx=20, sticky=tk.W)
        keys_frame = ttk.Frame(notebook, padding=10)
        notebook.add(keys_frame, text="按键自定义")
        
        self.btn_names = ["左键 (无法修改)", "右键", "中键", "前进侧键", "后退侧键", "DPI 键"]
        self.btn_vars = [] # 存储每个按键选择的功能类型
        self.btn_code_vars = [] # 存储具体的键值
        
        # 定义一些常用选项
        self.opt_map = {
            "默认": {"type": 16, "codes": [1, 2, 4, 16, 8, 85]}, # 这里的 85 是 DPI 的特殊码
            "键盘按键": {"type": 32},
            "禁用": {"type": 0, "code": 0}
        }

        for i in range(6):
            row = ttk.Frame(keys_frame)
            row.pack(fill=tk.X, pady=5)
            
            ttk.Label(row, text=self.btn_names[i], width=15).pack(side=tk.LEFT)
            
            # 功能类型选择
            v = tk.StringVar(value="默认")
            self.btn_vars.append(v)
            cb = ttk.Combobox(row, textvariable=v, values=list(self.opt_map.keys()), state="readonly", width=10)
            cb.pack(side=tk.LEFT, padx=5)
            
            # 如果选键盘，这里填 HID Code (比如 Enter 是 40)
            cv = tk.IntVar(value=0)
            self.btn_code_vars.append(cv)
            ent = ttk.Entry(row, textvariable=cv, width=5)
            ent.pack(side=tk.LEFT, padx=5)
            ttk.Label(row, text="(键盘代码)").pack(side=tk.LEFT)
            
            # 锁定左键防止把自己关在外面
            if i == 0: cb.configure(state="disabled"); ent.configure(state="disabled")

        ttk.Button(keys_frame, text="保存按键配置", command=self.apply_buttons).pack(pady=20)
        # 2. 灯光设置页
        light_frame = ttk.Frame(notebook, padding=10)
        notebook.add(light_frame, text="灯光效果")
        lights = ["常亮模式", "呼吸模式", "霓虹模式", "波浪模式", "闪烁模式", "反应模式", "关闭灯光"]
        for i, text in enumerate(lights):
            ttk.Radiobutton(light_frame, text=text, variable=self.light_mode_var, value=i, command=self.apply_lighting).pack(anchor=tk.W, pady=5)

        # 底部应用按钮
        btn_frame = ttk.Frame(self.root, padding=10)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="应用性能设置并保存到鼠标", command=self.apply_performance).pack(side=tk.RIGHT)
        macro_frame = ttk.Frame(notebook, padding=10)
        notebook.add(macro_frame, text="宏编辑器")
        
        # 左侧列表：展示动作序列
        self.macro_listbox = tk.Listbox(macro_frame, height=15, width=40)
        self.macro_listbox.pack(side=tk.LEFT, padx=5)
        
        # 右侧控制面板
        ctrl_frame = ttk.Frame(macro_frame)
        ctrl_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        ttk.Label(ctrl_frame, text="模拟按键 (HID Code):").pack(pady=2)
        self.key_entry = ttk.Entry(ctrl_frame, width=10)
        self.key_entry.insert(0, "4") # 默认为 'A'
        self.key_entry.pack()
        
        ttk.Button(ctrl_frame, text="添加按下动作", command=lambda: self.add_action(True)).pack(fill=tk.X, pady=2)
        ttk.Button(ctrl_frame, text="添加松开动作", command=lambda: self.add_action(False)).pack(fill=tk.X, pady=2)
        ttk.Button(ctrl_frame, text="清空序列", command=lambda: self.macro_listbox.delete(0, tk.END)).pack(fill=tk.X, pady=10)
        
        # 绑定到按键
        ttk.Label(ctrl_frame, text="绑定至按键:").pack(pady=2)
        self.target_btn_var = tk.IntVar(value=4) # 默认后退侧键
        ttk.OptionMenu(ctrl_frame, self.target_btn_var, 4, 3, 4, 5).pack() # 前进/后退/DPI
        
        ttk.Button(ctrl_frame, text="🚀 烧录宏到鼠标", command=self.save_macro).pack(fill=tk.X, pady=20)
        
        self.macro_data = []

    def sync_ui_from_mouse(self):
        """拉取最新配置刷新UI"""
        config = self.driver.get_mouse_config()
        if config:
            for i in range(6): self.dpi_vars[i].set(config["dpis"][i])
            self.current_dpi_var.set(config["dpi_index"])
            if 0 <= config["report_rate"] <= 3: self.report_rate_var.set(config["report_rate"])
            if config["lod_value"] in [1, 2]: self.lod_var.set(config["lod_value"])
            self.light_mode_var.set(config["light_mode"])

    def apply_lighting(self):
        if self.driver.connected:
            self.driver.set_light_mode(self.light_mode_var.get())

    def apply_performance(self):
        if not self.driver.connected: 
            messagebox.showwarning("警告", "鼠标未连接，无法应用设置！")
            return
        try:
            new_dpis = [var.get() for var in self.dpi_vars]
            idx = self.current_dpi_var.get()
            rate = self.report_rate_var.get()
            lod = self.lod_var.get()
        except:
            messagebox.showerror("錯誤", "請輸入正確的數字")
            return

    # 2. 發送給滑鼠硬體（寫入 Flash）
        self.driver.set_performance_config(new_dpis, idx, rate, lod)

    # 3. 🌟 關鍵：立刻通知後台 Toast 服務更新記憶！
        if hasattr(self, 'app_manager'):
            self.app_manager.update_dpi_config(new_dpis, idx)
    
        messagebox.showinfo("成功", "配置已同步至硬體與後台服務")

    def show_window(self):
        """显示窗口时顺便刷新一下数据"""
        self.root.deiconify()
        self.root.lift()
        self.sync_ui_from_mouse()

    def hide_window(self):
        self.root.withdraw()

    def add_action(self, is_press):
        key = int(self.key_entry.get())
        action = {'type': 2, 'key': key, 'press': is_press, 'delay': 20}
        self.macro_data.append(action)
        txt = f"{'⬇️ 按下' if is_press else '⬆️ 松开'} 键码:{key} (20ms)"
        self.macro_listbox.insert(tk.END, txt)

    def save_macro(self):
        if not self.driver.connected: return
        # 1. 烧录动作数据
        self.driver.send_macro_data(self.macro_data)
        # 2. 绑定按键
        btn_idx = self.target_btn_var.get()
        self.driver.bind_macro_to_button(btn_idx, 0) # 统一存为宏 0
        messagebox.showinfo("成功", f"宏已绑定至鼠标按键 {btn_idx}！")

    def apply_buttons(self):
        configs = []
        # 默认的鼠标键值
        default_mouse_codes = [1, 2, 4, 16, 8, 85]
        
        for i in range(6):
            mode = self.btn_vars[i].get()
            if mode == "默认":
                # 特殊处理：DPI 键的类型是 33
                t = 33 if i == 5 else 16
                c = default_mouse_codes[i]
            elif mode == "键盘按键":
                t = 32
                c = self.btn_code_vars[i].get()
            else: # 禁用
                t = 0
                c = 0
            configs.append({'type': t, 'code': c})
        
        self.driver.set_button_config(configs)
        messagebox.showinfo("成功", "按键配置已下发！部分改动可能需要重新插拔鼠标生效。")

    def setup_button_tab(self, parent):
        self.btn_configs = [] # 存储 6 个按键的详细配置字典
        
        for i in range(6):
            frame = ttk.LabelFrame(parent, text=self.btn_names[i])
            frame.pack(fill=tk.X, padx=10, pady=2)
            
            # 存储该按键的配置
            config = {'type': 16, 'modifier': 0, 'code': 0, 'desc': tk.StringVar(value="默认")}
            self.btn_configs.append(config)
            
            ttk.Label(frame, textvariable=config['desc'], width=25, foreground="blue").pack(side=tk.LEFT, padx=5)
            
            # 录制键盘按钮
            rec_btn = ttk.Button(frame, text="🔴 录制键盘", command=lambda idx=i: self.record_key(idx))
            rec_btn.pack(side=tk.LEFT, padx=2)
            
            # 多媒体下拉
            media_btn = ttk.Button(frame, text="🎵 媒体键", command=lambda idx=i: self.pick_media(idx))
            media_btn.pack(side=tk.LEFT, padx=2)
            
            # 恢复默认
            reset_btn = ttk.Button(frame, text="↺", width=3, command=lambda idx=i: self.reset_btn(idx))
            reset_btn.pack(side=tk.LEFT, padx=2)
    def record_key(self, idx):
        import keyboard
        # 弹出一个简单的无边框窗口提示用户
        overlay = tk.Toplevel(self.root)
        overlay.geometry("300x100+500+400")
        overlay.overrideredirect(True)
        tk.Label(overlay, text="请按下组合键...\n(例如 Ctrl+C)", font=("Arial", 12)).pack(expand=True)
        self.root.update()

        # 阻塞直到捕获按键
        event = keyboard.read_event()
        if event.event_type == keyboard.KEY_DOWN:
            modifier = 0
            if keyboard.is_pressed('ctrl'): modifier |= 0x01
            if keyboard.is_pressed('shift'): modifier |= 0x02
            if keyboard.is_pressed('alt'): modifier |= 0x04
            if keyboard.is_pressed('windows'): modifier |= 0x08
            
            key_name = event.name
            hid_code = HID_MAP.get(key_name.lower(), 0)
            
            # 更新配置
            self.btn_configs[idx]['type'] = 32
            self.btn_configs[idx]['modifier'] = modifier
            self.btn_configs[idx]['code'] = hid_code
            
            # 更新描述显示
            mod_str = ""
            if modifier & 0x01: mod_str += "Ctrl+"
            if modifier & 0x02: mod_str += "Shift+"
            if modifier & 0x04: mod_str += "Alt+"
            if modifier & 0x08: mod_str += "Win+"
            self.btn_configs[idx]['desc'].set(f"键盘: {mod_str}{key_name.upper()}")
            
        overlay.destroy()

    def pick_media(self, idx):
        # 简单起见，弹出一个小菜单
        menu = tk.Menu(self.root, tearoff=0)
        for name, code in MEDIA_MAP.items():
            menu.add_command(label=name, command=lambda n=name, c=code: self.set_media(idx, n, c))
        menu.post(self.root.winfo_pointerx(), self.root.winfo_pointery())

    def set_media(self, idx, name, code):
        self.btn_configs[idx]['type'] = 48
        self.btn_configs[idx]['modifier'] = 0
        self.btn_configs[idx]['code'] = code
        self.btn_configs[idx]['desc'].set(f"媒体: {name}")
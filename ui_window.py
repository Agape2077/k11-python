import tkinter as tk
from tkinter import ttk, messagebox

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
        
        # ⚠️ 这里删除了 monitor_thread！UI 现在只负责展示，不负责轮询硬件。

    def setup_ui(self):
        # 顶部状态栏
        status_frame = ttk.Frame(self.root, padding=10)
        status_frame.pack(fill=tk.X)
        ttk.Label(status_frame, textvariable=self.status_var, font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        ttk.Label(status_frame, textvariable=self.battery_var, foreground="green", font=("Arial", 10, "bold")).pack(side=tk.RIGHT)

        notebook = ttk.Notebook(self.root)
        notebook.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)

        # 1. 性能设置页
       # 1. 性能设置页
        perf_frame = ttk.Frame(notebook, padding=10)
        notebook.add(perf_frame, text="性能设置")
        
        # 定义颜色列表
        self.dpi_colors = ["#FF0000", "#00FF00", "#0000FF", "#FFCC00", "#00FFFF", "#FF00FF"]
        
        ttk.Label(perf_frame, text="DPI 设置 (200 - 12000)", font=("Arial", 10, "bold")).grid(row=0, column=0, columnspan=2, pady=5, sticky=tk.W)
        
        for i in range(6):
            # 添加彩色小方块指示器
            color_box = tk.Label(perf_frame, width=2, bg=self.dpi_colors[i], relief="ridge")
            color_box.grid(row=i+1, column=0, padx=(0, 5), pady=2, sticky=tk.W)
            
            # 调整单选框位置，不要挡住颜色块
            ttk.Radiobutton(perf_frame, text=f"档位 {i+1}", variable=self.current_dpi_var, value=i).grid(row=i+1, column=0, padx=(25, 5), pady=2, sticky=tk.W)
            ttk.Entry(perf_frame, textvariable=self.dpi_vars[i], width=10).grid(row=i+1, column=1, padx=5, pady=2)
        ttk.Label(perf_frame, text="回报率 (Hz)", font=("Arial", 10, "bold")).grid(row=0, column=2, padx=20, pady=5, sticky=tk.W)
        rates = [("125Hz", 0), ("250Hz", 1), ("500Hz", 2), ("1000Hz", 3)]
        for i, (text, val) in enumerate(rates):
            ttk.Radiobutton(perf_frame, text=text, variable=self.report_rate_var, value=val).grid(row=i+1, column=2, padx=20, sticky=tk.W)

        ttk.Label(perf_frame, text="静默高度 (LOD)", font=("Arial", 10, "bold")).grid(row=5, column=2, padx=20, pady=5, sticky=tk.W)
        ttk.Radiobutton(perf_frame, text="1.0 mm", variable=self.lod_var, value=1).grid(row=6, column=2, padx=20, sticky=tk.W)
        ttk.Radiobutton(perf_frame, text="2.0 mm", variable=self.lod_var, value=2).grid(row=7, column=2, padx=20, sticky=tk.W)

        # # 2. 灯光设置页
        # light_frame = ttk.Frame(notebook, padding=10)
        # notebook.add(light_frame, text="灯光效果")
        # lights = ["常亮模式", "呼吸模式", "霓虹模式", "波浪模式", "闪烁模式", "反应模式", "关闭灯光"]
        # for i, text in enumerate(lights):
        #     ttk.Radiobutton(light_frame, text=text, variable=self.light_mode_var, value=i, command=self.apply_lighting).pack(anchor=tk.W, pady=5)

        # 底部应用按钮
        btn_frame = ttk.Frame(self.root, padding=10)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="应用性能设置并保存到鼠标", command=self.apply_performance).pack(side=tk.RIGHT)

    def sync_ui_from_mouse(self):
        """拉取最新配置刷新UI"""
        # 调用核心驱动层的方法获取配置
        config = self.driver.get_mouse_config()
        if config:
            for i in range(6): 
                self.dpi_vars[i].set(config["dpis"][i])
            if hasattr(self, 'app_manager'):
                self.app_manager.update_dpi_list(config["dpis"])
                
            self.current_dpi_var.set(config["dpi_index"])
            
            if 0 <= config["report_rate"] <= 3: 
                self.report_rate_var.set(config["report_rate"])
                
            if config["lod_value"] in [1, 2]: 
                self.lod_var.set(config["lod_value"])
                
            self.light_mode_var.set(config["light_mode"])
            print("🔄 成功从鼠标同步记忆配置！")

    def apply_lighting(self):
        if self.driver.connected:
            self.driver.set_light_mode(self.light_mode_var.get())

    def apply_performance(self):
        if not self.driver.connected:
            messagebox.showwarning("警告", "滑鼠未連線")
            return

    # 1. 從輸入框獲取最新的數值
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
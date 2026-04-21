import time
import threading
import pystray
import sys
from PIL import Image, ImageDraw, ImageFont
from core_driver import MouseDriver
from ui_window import SettingsWindow
from windows_toasts import WindowsToaster, Toast
class AppManager:
    def __init__(self):
        self.driver = MouseDriver()
        self.running = True
        self.toaster = WindowsToaster('K-snake X11 Driver')
        self.ui = None
        
        # 1. 基础变量初始化
        self.dpi_list = [800, 1200, 1600, 3200, 5000, 12000]
        self.notified_20 = False
        self.notified_10 = False
        self.last_dpi_idx = -1
        self._last_battery = 0
        self._last_charge = 0

        # 2. 建立右键选单 (SEPARATOR 没有括号)
        menu = pystray.Menu(
            pystray.MenuItem("打开设置面板", self.open_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出驱动", self.quit_app)
        )
        
        # 3. 初始化托盘图标
        initial_icon = self.create_text_icon("...")
        self.tray_icon = pystray.Icon("KSnake", initial_icon, "K-snake: 正在连接...", menu)
        
        # 4. 启动后台轮询线程
        self.monitor_thread = threading.Thread(target=self.hardware_monitor_loop, daemon=True)
        self.monitor_thread.start()
    def send_toast(self, message, title, tag):
        """发送覆盖式通知，相同的 tag 会互相替换"""
        new_toast = Toast()
        new_toast.text_fields = [title, message]
        # 🌟 关键：设置 Tag 和 Group，让新通知替换旧通知
        new_toast.tag = tag
        new_toast.group = "KSnake"
        # 🌟 关键：设置场景为 'incomingCall' 或 'alarm' 会让它更突出
        # 或者保持默认，但通过 Tag 来控制数量
        self.toaster.show_toast(new_toast)

        

    def update_dpi_list(self, new_list):
        """当 UI 读取到或设置了新 DPI 时，同步给主控"""
        self.dpi_list = new_list
        print(f"🔄 主控已同步最新 DPI 清单: {self.dpi_list}")

    def is_windows_dark_mode(self):
        """侦测 Windows 是否处于暗色模式"""
        if sys.platform != 'win32': return True
        try:
            import winreg
            registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            key_path = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize'
            key = winreg.OpenKey(registry, key_path)
            value, regtype = winreg.QueryValueEx(key, 'SystemUsesLightTheme')
            winreg.CloseKey(key)
            return value == 0
        except:
            return True

    def create_text_icon(self, text):
        """生成适配主题的图标"""
        img_size = 64
        image = Image.new('RGBA', (img_size, img_size), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("msyhbd.ttc", 38)
        except:
            font = ImageFont.load_default()

        is_dark = self.is_windows_dark_mode()
        text_color = "white" if is_dark else "black"

        bbox = draw.textbbox((0, 0), text, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((img_size - w) / 2, (img_size - h) / 2 - 5), text, fill=text_color, font=font)
        return image
    def update_dpi_config(self, new_dpi_list, current_idx=None):

        self.dpi_list = new_dpi_list
        if current_idx is not None:
            self.last_dpi_idx = current_idx
        print(f"🔔 Toast 服務已接收更新！當前數值清單: {self.dpi_list}")

    def hardware_monitor_loop(self):
        last_battery_req = 0
        last_is_dark = self.is_windows_dark_mode()
        
        while self.running:
            try:
                if not self.driver.connected:
                    self.tray_icon.icon = self.create_text_icon("X")
                    if self.driver.connect():
                        print("✅ 硬體已連接，正在同步硬體記憶體中的 DPI 設定...")
                        
                        # 🌟 核心修改：連上後立刻主動讀取一次完整配置
                        config = self.driver.get_mouse_config()
                        if config:
                            # 把滑鼠內部的真實 DPI 數值同步到主控的 dpi_list 裡
                            self.dpi_list = config["dpis"]
                            self.last_dpi_idx = config["dpi_index"] # 同步當前檔位，防止啟動就彈窗
                            print(f"🎯 同步成功！當前硬體 DPI 列表: {self.dpi_list}")
                            
                            # 如果 UI 開著，也通知 UI 更新
                            if self.ui and self.ui.root.winfo_exists():
                                self.ui.root.after(0, self.ui.sync_ui_from_mouse)
                        
                    time.sleep(2)
                    continue
                    
                now = time.time()
                if now - last_battery_req > 5.0:
                    self.driver.request_battery()
                    last_battery_req = now

                packet = self.driver.read_packet()
                
                # 主题切换检测
                current_is_dark = self.is_windows_dark_mode()
                if current_is_dark != last_is_dark:
                    last_is_dark = current_is_dark
                    if hasattr(self, '_last_battery'):
                        display_text = f"{self._last_battery}+" if self._last_charge == 1 else str(self._last_battery)
                        self.tray_icon.icon = self.create_text_icon(display_text)

                if packet:
                    if packet["type"] == "battery":
                        bat, charge = packet["battery"], packet["charge"]
                        self._last_battery, self._last_charge = bat, charge
                        
                        status_emoji = "⚡" if charge == 1 else "🔋"
                        self.tray_icon.title = f"K-snake X11\n电量: {bat}% {status_emoji}"
                        self.tray_icon.icon = self.create_text_icon(f"{bat}+" if charge == 1 else str(bat))

                        # 低电量通知
                        if charge == 0:
                            if bat <= 10 and not self.notified_10:
                                self.send_toast(f"当前电量 {bat}%，请充电！", "🔴 电量极低", "BATTERY")
                                self.notified_10 = True
                            elif bat <= 20 and not self.notified_20:
                                self.send_toast(f"当前电量 {bat}%，建议充电。", "🟡 电量不足", "BATTERY")
                                self.notified_20 = True
                            elif bat > 25:
                                self.notified_10 = self.notified_20 = False
                        else:
                            self.notified_10 = self.notified_20 = False

                        if self.ui and self.ui.root.winfo_exists():
                            self.ui.root.after(0, lambda b=bat, s=status_emoji: self.ui.battery_var.set(f"电量: {b}% {s}"))

                    elif packet["type"] == "dpi_status":
                        idx = packet["dpi_index"]
                        current_dpi_val = self.dpi_list[idx] if idx < len(self.dpi_list) else "未知"
                        
                        if idx != self.last_dpi_idx and self.last_dpi_idx != -1:
                            self.send_toast(f"{current_dpi_val} DPI ", "DPI 变更", "DPI")
                        self.last_dpi_idx = idx
                        if self.ui and self.ui.root.winfo_exists():
                            self.ui.root.after(0, lambda i=idx: self.ui.current_dpi_var.set(i))
                            self.ui.root.after(0, lambda v=current_dpi_val: self.ui.status_var.set(f"状态: 当前 {v} DPI"))

                time.sleep(0.02) 
            except Exception as e:
                print(f"⚠️ 监控线程异常: {e}")
                time.sleep(1)

    def open_settings(self, icon=None, item=None):
        if self.ui and self.ui.root.winfo_exists():
            self.ui.show_window()

    def quit_app(self, icon=None, item=None):
        self.running = False
        self.driver.disconnect()
        if self.tray_icon: self.tray_icon.stop()
        if self.ui and self.ui.root.winfo_exists(): self.ui.root.quit()

    def run(self):
        # 先启动托盘线程
        threading.Thread(target=self.tray_icon.run, daemon=True).start()
        # 初始化 UI 并将主控实例传给 UI
        self.ui = SettingsWindow(self.driver)
        self.ui.app_manager = self 
        self.ui.root.mainloop()

if __name__ == "__main__":
    app = AppManager()
    app.run()
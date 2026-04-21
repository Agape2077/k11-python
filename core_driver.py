import hid
import time

VIDS = [43172, 43173]
PID = 8789
DEBUG_MODE = True

class MouseDriver:
    def __init__(self):
        self.device = None
        self.connected = False
    
    def get_mouse_config(self):
        """读取鼠标当前的完整配置参数"""
        if not self.connected: return None
        
        # 1. 快速排空积压的数据包
        while True:
            if not self.device.read(65, timeout_ms=5):
                break
                
        # 2. 构造查询配置指令 (JS: e[2]=14, e[5]=47)
        command = [0x00] * 65
        command[1], command[2], command[3] = 85, 14, 165  
        command[4], command[5], command[6], command[7] = 11, 47, 1, 1 
        
        try:
            self.device.write(command)
            time.sleep(0.05)
            
            # 3. 捕捉返回的数据包
            for _ in range(15):
                data = self.device.read(65, timeout_ms=50)
                if not data or len(data) < 55:  # 配置包很长，至少需要读到第50多位
                    continue
                    
                # 🎯 特征匹配：返回包的头部对应查询指令 [170, 14, 165]
                if data[0] == 170 and data[1] == 14 and data[2] == 165:
                    
                    # 检查是否是出厂未初始化的空数据 (JS里判断全0或全255)
                    if (data[13] == 0 and data[14] == 0) or (data[13] == 255 and data[14] == 255):
                        return None # 此时可以用UI上的默认值
                        
                    # 💡 核心解析：将高低字节拼装回真实 DPI，并提取其他参数
                    config = {
                        "light_mode": data[9],
                        "report_rate": data[10] - 1,
                        "dpi_index": data[12] - 1,
                        "dpis": [
                            (data[14] << 8) | data[13],  # DPI 1
                            (data[16] << 8) | data[15],  # DPI 2
                            (data[18] << 8) | data[17],  # DPI 3
                            (data[20] << 8) | data[19],  # DPI 4
                            (data[22] << 8) | data[21],  # DPI 5
                            (data[24] << 8) | data[23],  # DPI 6
                        ],
                        "lod_value": data[49]
                    }
                    return config
                    
        except Exception as e:
            print(f"读取配置失败: {e}")
            
        return None
    

    def connect(self):
        try:
            for d in hid.enumerate():
                if d['vendor_id'] in VIDS and d['product_id'] == PID:
                    if d['usage_page'] == 65281: # 专属通讯通道
                        self.device = hid.device()
                        self.device.open_path(d['path'])
                        self.device.set_nonblocking(0) # 阻塞模式保证读取稳定性
                        self.connected = True
                        return True
            return False
        except Exception as e:
            print(f"连接失败: {e}")
            return False

    def disconnect(self):
        if self.device:
            self.device.close()
        self.connected = False

    def request_battery(self):
        """主动向鼠标发送获取电量的指令"""
        if not self.connected: return
        for _ in range(20):
            if not self.device.read(65, timeout_ms=2):
                break
        command = [0x00] * 65
        command[1], command[2], command[3] = 85, 48, 165
        command[4], command[5], command[6], command[7] = 11, 46, 1, 1
        try:
            self.device.write(command)
        except:
            pass

    def read_packet(self):
        """读取并解析一个数据包"""
        if not self.connected: return None
        try:
            data = self.device.read(65, timeout_ms=50)
            if not data or len(data) < 11:
                return None
                
            # 🌟 [加入 Debug 日志] 
            # 为了防止满屏幕都是空包，我们过滤一下，只打印前几位不是 0 的包
            if DEBUG_MODE and data[0] != 0:
                print(f"{data[:15]}")
                
            # 1. 响应我们主动获取电量的返回包
            if data[0] == 170 and data[1] == 48 and data[2] == 165:
                return {"type": "battery", "battery": data[8], "charge": data[9]}
                
            # 2. 鼠标主动广播的状态包
            if data[0] == 170 and data[1] == 250:
                if data[8] == 208:
                    return {"type": "battery", "battery": data[9], "charge": data[10]}
                else:
                    # 解析 DPI 切包
                    return {
                        "type": "dpi_status", 
                        "dpi_index": data[9] - 1, 
                        "report_rate": data[10] - 1
                    }
        except Exception as e:
            if DEBUG_MODE:
                print(f"❌ 读取错误: {e}")
        return None

    def set_light_mode(self, mode_index):
        if not self.connected: return
        command = [0x00] * 65
        command[1], command[2], command[5] = 85, 33, 3
        command[11] = mode_index
        try:
            self.device.write(command)
        except Exception as e:
            print(f"设置灯光失败: {e}")

    def set_performance_config(self, dpis, current_dpi_idx, report_rate, lod_value):
        """下发核心性能配置参数，包含 DPI 档位颜色"""
        if not self.connected: return
        command = [0x00] * 65
        command[1], command[2], command[3] = 85, 15, 174
        command[4], command[5], command[6], command[7] = 10, 47, 1, 1
        
        command[11] = report_rate + 1
        command[12] = 6 
        command[13] = current_dpi_idx + 1 
        
        # 写入 6 档 DPI 数值 (14-25字节)
        for i in range(6):
            dpi_val = dpis[i]
            command[14 + i*2] = dpi_val & 0xFF
            command[15 + i*2] = (dpi_val >> 8) & 0xFF
            
        # 🌟 写入 6 档 DPI 对应的颜色 (26-43字节，每档3字节RGB)
        # 颜色定义：红, 绿, 蓝, 橙黄, 青, 粉紫
        colors_rgb = [
            (255, 0, 0),     # 红
            (0, 255, 0),     # 绿
            (0, 0, 255),     # 蓝
            (255, 204, 0),   # 橙偏黄
            (0, 255, 255),   # 青
            (255, 0, 255)    # 粉紫
        ]
        
        for i in range(6):
            r, g, b = colors_rgb[i]
            command[26 + i*3] = r
            command[27 + i*3] = g
            command[28 + i*3] = b
        
        command[50] = lod_value 
        command[51], command[52], command[53] = 49, 2, 10
        command[55] = 17 
        
        try:
            self.device.write(command)
            print("🌈 DPI 及颜色设置已成功下发至硬件！")
        except Exception as e:
            print(f"设置失败: {e}")
    def send_macro_data(self, macro_actions):
        """将宏动作序列烧录进滑鼠 Flash"""
        if not self.connected: return
        
        # 1. 构建 4096 字节的宏内存镜像
        payload = [0] * 4096
        # 简化版：假设我们将宏存放在索引 0 的位置，数据从 64 字节开始
        payload[0], payload[1] = 64, 0  # 目录：宏0 的偏移量是 64
        
        offset = 64
        for i, action in enumerate(macro_actions):
            # action 格式: {'type': 2, 'key': 4, 'press': True, 'delay': 50}
            flags = 0x02 if action['type'] == 2 else 0x03 # 键盘/滑鼠
            if action['press']: flags |= 0x40 # 按下标记
            if i == len(macro_actions) - 1: flags |= 0x80 # 结束标记
            
            delay = action['delay']
            payload[offset] = delay & 0xFF
            payload[offset+1] = (delay >> 8) & 0xFF
            payload[offset+2] = flags
            payload[offset+3] = action['key']
            offset += 4

        # 2. 切片发送 (每包 56 字节数据)
        for i in range(0, offset, 56):
            chunk = payload[i:i+56]
            cmd = [0x00] * 65
            cmd[1], cmd[2] = 85, 13 # 0x55, 0x0D (写入宏)
            cmd[5] = len(chunk)
            cmd[6], cmd[7] = i & 0xFF, (i >> 8) & 0xFF
            for j, b in enumerate(chunk): cmd[9+j] = b
            self.device.write(cmd)
            time.sleep(0.01)
        print("✅ 宏动作已烧录至滑鼠硬件")

    def bind_macro_to_button(self, btn_idx, macro_idx):
        """将特定按键绑定为触发宏"""
        # 逻辑：发送 0x09 指令，将对应按键的 type 设为 0x70
        cmd = [0x00] * 65
        cmd[1], cmd[2], cmd[3], cmd[4] = 85, 9, 165, 34
        # 这里需要保留其他按键的默认值（简化处理：假设只改一个）
        # 实际开发建议先 read 整个配置，修改后再 write
        cmd[9 + btn_idx*4] = 0x70      # 0x70 代表宏功能
        cmd[10 + btn_idx*4] = macro_idx # 宏的索引
        self.device.write(cmd)
    def set_button_config(self, btn_configs):
        """
        btn_configs 元素格式: 
        键盘: {'type': 32, 'modifier': 1, 'code': 4} (Ctrl+A)
        鼠标: {'type': 16, 'code': 1} (左键)
        媒体: {'type': 48, 'code': 176} (音量+)
        """
        if not self.connected: return
        
        command = [0x00] * 65
        command[1], command[2], command[3], command[4] = 85, 9, 165, 34
        command[5], command[6], command[7], command[8] = 11, 47, 1, 1 
        
        for i in range(6):
            cfg = btn_configs[i]
            base = 9 + (i * 4)
            command[base] = cfg['type']
            # Byte 1: 键盘模式下是修饰键(Ctrl/Shift等)，媒体模式下通常是0
            command[base + 1] = cfg.get('modifier', 0)
            # Byte 2: 键码
            command[base + 2] = cfg['code']
            command[base + 3] = 0
            
        self.device.write(command)
        print("⌨️ 复杂按键映射已同步至硬件！")
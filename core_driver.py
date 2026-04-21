import hid
import time

VIDS = [43172, 43173]
PID = 8789
DEBUG_MODE = True
class MouseDriver:
    def __init__(self):
        self.device = None
        self.connected = False


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
        if not self.connected: return
        
        # 🌟 核心修复：不要无限循环排空，最多排空 20 个包就行了
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
                print(f"📦 [RAW] 收到原始包: {data[:15]}")
                
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
        """下发核心性能配置参数"""
        if not self.connected: return
        command = [0x00] * 65
        command[1], command[2], command[3] = 85, 15, 174
        command[4], command[5], command[6], command[7] = 10, 47, 1, 1
        
        # Report Rate: JS 中是 report_rate + 1 (125Hz=1, 250Hz=2, 500Hz=3, 1000Hz=4)
        command[11] = report_rate + 1
        command[12] = 6 # DPI count (固定6档)
        command[13] = current_dpi_idx + 1 
        
        # 写入 6 档 DPI (拆分为低位和高位)
        for i in range(6):
            dpi_val = dpis[i]
            low_byte = dpi_val & 0xFF
            high_byte = (dpi_val >> 8) & 0xFF
            command[14 + i*2] = low_byte
            command[15 + i*2] = high_byte
            
        command[50] = lod_value # 1 或 2 (1.0mm / 2.0mm)
        
        # 写入其他默认参数保持稳定
        command[51] = 49 # sensor_flag default
        command[52] = 2  # key_respond default
        command[53] = 10 # sleep_light 10mins
        command[55] = 17 # wakeup_flag & move_light_flag
        
        try:
            self.device.write(command)
        except Exception as e:
            print(f"设置性能参数失败: {e}")
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

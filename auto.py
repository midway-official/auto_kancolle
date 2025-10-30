import cv2
import numpy as np
import pyautogui
import time
import os
import random
import sys

# ==== 配置 ====
ICON_DIR = os.path.join(os.path.dirname(__file__), "icon")

# --- 1. 定义可重用的任务序列 (MISSION) ---
MISSIONS = {
    # 示例: 补给任务
    "supply_2": [
        ("wait_click", "supply.png", 20, 20),
        ("wait_click", "2.png"),
        ("wait_click", "supply_all.png", 15, 5),
        ("wait_click", "port.png", 15, 20),
    ],
    # 示例: 远征任务
    "expedition_02": [
        ("wait_click", "attack.png"),
        ("wait_click", "expedition.png", 20, 20),
        ("wait_click", "02.png"),
        ("wait_click", "start.png", 10, 5),  # 自定义偏移: 水平±20, 垂直±5
        ("wait", (2, 3)),
        ("wait_click", "start2.png"),
        ("wait", (5, 6)),
        ("wait_click", "port.png"),
    ],
    "expedition_01": [
        ("wait_click", "attack.png", 40, 40),
        ("wait_click", "expedition.png", 40, 40),
        ("wait_click", "01.png", 20, 10),
        ("wait_click", "start.png", 20, 10),  # 自定义偏移示例
        ("wait", (2, 3)),
        ("wait_click", "start2.png", 20, 10),
        ("wait", (5, 6)),
        ("wait_click", "port.png", 10, 20),
    ],
    "expedition_38": [
        ("wait_click", "attack.png", 40, 40),
        ("wait_click", "expedition.png", 40, 40),
        ("wait_click", "sourth.png", 10, 10),
        ("wait_click", "38.png", 20, 10),
        ("wait_click", "start.png", 20, 10),  # 自定义偏移示例
        ("wait", (2, 3)),
        ("wait_click", "start2.png", 20, 10),
        ("wait", (5, 6)),
        ("wait_click", "port.png", 10, 20),
    ]
}

# --- 2. 任务执行列表 (TASKS) ---
# 列表元素可以是:
# 1. 单个动作元组: ('action', 'icon_name') 或 ('action', 'icon_name', offset_x, offset_y)
# 2. 引用一个 Mission: ('mission', 'mission_name')
# 3. 纯等待: ('wait', seconds)
TASKS = [
    # 远征02
    ("mission", "expedition_02"),

    # 等待950-1100秒之间的随机时间
    ("wait", (950, 1100)),
    
    # 收远征
    ("wait_click", "supply.png", 20, 20),
    ("wait", (3, 5)),
    ("wait_click", "port.png", 10, 10),
    ("wait_click", "over.png", 15, 10),  # 自定义偏移: 水平±15, 垂直±10
    ("wait", (20, 30)),
    
    # 补给
    ("mission", "supply_2"),
    
    # 等待
    ("wait", (10, 20)),
]

THRESHOLD = 0.7       # 图像匹配阈值
WAIT_TIMEOUT = 3600   # wait_click 超时时间（秒）
INTERVAL = 0.8        # 检测间隔
# --- 随机时间配置 ---
IDLE_AFTER_TASK_RANGE = (10, 15)  # 每个任务结束后的等待时间范围（秒）
CLICK_OFFSET_RANGE = (-8, 8)      # 默认点击位置的随机偏移范围（像素）
CLICK_HOLD_RANGE = (0.15, 0.3)     # 鼠标按下的随机持续时间范围（秒）
# --- 交互控制配置 ---
USER_MOVE_THRESHOLD = 300        # 两次任务间隔内，用户手动移动的最大像素距离（欧氏距离）
# --- 循环变量 ---
MAX_TASK_LOOPS = 5    # 整个任务列表的执行次数。-1 为无限循环
START_TASK_INDEX = 7  # 脚本开始执行的任务索引 (0-based)

# ==== 全局状态变量 ====
LAST_MOUSE_POS = pyautogui.position()


# ==== 辅助函数 ====

def find_icon(icon_name):
    """在屏幕上查找目标图标，返回中心坐标或 None"""
    target_path = os.path.join(ICON_DIR, icon_name)
    
    screenshot = pyautogui.screenshot()
    img_rgb = np.array(screenshot)
    img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2GRAY)

    template = cv2.imread(target_path, 0)
    if template is None:
        print(f"[WARN] 图标文件未找到或无法读取: {target_path}")
        return None

    res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)

    if max_val >= THRESHOLD:
        w, h = template.shape[::-1]
        center_x = max_loc[0] + w // 2
        center_y = max_loc[1] + h // 2
        return (center_x, center_y)
    return None


def human_move_to(target_x, target_y):
    """模拟人类操作，平滑、随机地移动鼠标到目标坐标"""
    print(f"[MOVE] 平滑移动到 ({target_x}, {target_y})...")
    x0, y0 = pyautogui.position()
    
    steps = random.randint(25, 45)
    screen_w, screen_h = pyautogui.size()

    for i in range(1, steps + 1):
        t = i / steps
        
        xi = int(x0 + (target_x - x0) * t + random.randint(-4, 4))
        yi = int(y0 + (target_y - y0) * t + random.randint(-4, 4))
        
        xi = max(0, min(screen_w - 1, xi))
        yi = max(0, min(screen_h - 1, yi))

        pyautogui.moveTo(xi, yi, duration=random.uniform(0.005, 0.02))
    
    pyautogui.moveTo(target_x, target_y, duration=random.uniform(0.01, 0.03))


def click_icon(icon_name, wait=False, offset_x_range=None, offset_y_range=None):
    """
    点击图标（可选择等待图标出现），实现随机按压时长和自定义偏移
    
    参数:
        icon_name: 图标文件名
        wait: 是否等待图标出现
        offset_x_range: 水平偏移量，如果为 None 则使用默认值
        offset_y_range: 垂直偏移量，如果为 None 则使用默认值
    """
    global LAST_MOUSE_POS
    
    # 使用自定义偏移或默认偏移
    if offset_x_range is None:
        offset_x_range = CLICK_OFFSET_RANGE
    else:
        offset_x_range = (-offset_x_range, offset_x_range)
    
    if offset_y_range is None:
        offset_y_range = CLICK_OFFSET_RANGE
    else:
        offset_y_range = (-offset_y_range, offset_y_range)
    
    start_time = time.time()
    screen_w, screen_h = pyautogui.size()
    center_x, center_y = screen_w // 2, screen_h // 2

    while True:
        pos = find_icon(icon_name)
        
        if pos:
            offset_x = random.randint(offset_x_range[0], offset_x_range[1])
            offset_y = random.randint(offset_y_range[0], offset_y_range[1])
            click_x = pos[0] + offset_x
            click_y = pos[1] + offset_y
            
            human_move_to(click_x, click_y) 
            
            hold_duration = random.uniform(CLICK_HOLD_RANGE[0], CLICK_HOLD_RANGE[1])
            pyautogui.mouseDown(button='left')
            time.sleep(hold_duration)
            pyautogui.mouseUp(button='left')

            print(f"[INFO] 点击: {icon_name} (原位置: {pos}, 偏移: ({offset_x}, {offset_y}))，按压时长: {hold_duration:.2f}s")
            LAST_MOUSE_POS = pyautogui.position()
            return True

        if not wait:
            print(f"[INFO] 未找到图标: {icon_name}")
            LAST_MOUSE_POS = pyautogui.position()
            return False

        if time.time() - start_time > WAIT_TIMEOUT:
            print(f"[WARN] 等待 {icon_name} 超时 ({WAIT_TIMEOUT}s)")
            LAST_MOUSE_POS = pyautogui.position()
            return False

        current_x, current_y = pyautogui.position()
        print(f"[WAIT] 未找到 {icon_name}，向屏幕中心移动并等待...")
        t = random.uniform(0.1, 0.3)
        next_x = int(current_x + (center_x - current_x) * t + random.randint(-10, 10))
        next_y = int(current_y + (center_y - current_y) * t + random.randint(-10, 10))

        pyautogui.moveTo(next_x, next_y, duration=random.uniform(0.1, 0.3))
        
        LAST_MOUSE_POS = pyautogui.position()
        time.sleep(INTERVAL)


def human_idle(duration):
    """模拟人为操作：连续平滑移动鼠标，带随机轨迹和点击"""
    global LAST_MOUSE_POS 
    screen_w, screen_h = pyautogui.size()
    start_time = time.time()
    print(f"[IDLE] 模拟人为操作 {duration:.2f} 秒中…")

    x0, y0 = pyautogui.position()
    end_x, end_y = screen_w // 2, screen_h // 2

    while time.time() - start_time < duration:
        target_x = end_x + random.randint(-50, 50)
        target_y = end_y + random.randint(-50, 50)

        steps = random.randint(20, 40)
        for i in range(steps):
            t = i / steps
            xi = int(x0 + (target_x - x0) * t + random.randint(-2, 2))
            yi = int(y0 + (target_y - y0) * t + random.randint(-2, 2))
            pyautogui.moveTo(xi, yi, duration=random.uniform(0.01, 0.03)) 

        if random.random() < 0.3:
            pyautogui.mouseDown(button='left')
            time.sleep(random.uniform(0.1, 0.3)) 
            pyautogui.mouseUp(button='left')

        x0, y0 = pyautogui.position()
        time.sleep(random.uniform(0.1, 0.3))
    
    LAST_MOUSE_POS = pyautogui.position()


def pure_wait(wait_time):
    """
    纯等待功能，不执行任何操作，仅等待指定时间
    参数:
        wait_time: 可以是数字(秒)或元组(最小值, 最大值)
    """
    global LAST_MOUSE_POS
    
    # 解析等待时间
    if isinstance(wait_time, tuple) and len(wait_time) == 2:
        actual_wait = random.uniform(wait_time[0], wait_time[1])
        print(f"[WAIT] 纯等待 {actual_wait:.2f} 秒 (范围: {wait_time[0]}-{wait_time[1]}秒)...")
    else:
        actual_wait = float(wait_time)
        print(f"[WAIT] 纯等待 {actual_wait:.2f} 秒...")
    
    time.sleep(actual_wait)
    LAST_MOUSE_POS = pyautogui.position()
    print(f"[WAIT] 等待完成")


def check_user_interference(current_task_index):
    """检查鼠标移动是否过大（判断用户是否接管）"""
    global LAST_MOUSE_POS
    
    current_pos = pyautogui.position()
    
    dist_sq = (current_pos[0] - LAST_MOUSE_POS[0])**2 + (current_pos[1] - LAST_MOUSE_POS[1])**2
    threshold_sq = USER_MOVE_THRESHOLD**2
    
    if dist_sq > threshold_sq:
        print("\n" * 3)
        print("!" * 60)
        print(f"!!! [ALERT] 检测到鼠标大幅度移动 (距离: {dist_sq**0.5:.2f} > {USER_MOVE_THRESHOLD})，可能用户接管。")
        print(f"!!! 当前任务索引: {current_task_index}")
        print("!!!" * 20)
        print("请选择操作:")
        print("  输入 'continue' (不区分大小写) 继续执行此任务。")
        print("  输入其他任意内容，程序将退出。")
        print("-" * 60)
        
        user_input = input(">>> ").strip().lower()
        
        if user_input == 'continue':
            print(">>> 用户选择继续。将重新执行当前任务。")
            LAST_MOUSE_POS = current_pos
            return True
        else:
            print(">>> 用户选择退出。程序终止。")
            return False
    
    LAST_MOUSE_POS = current_pos
    return True


def execute_mission(mission_name, loop_count, main_task_index):
    """执行一个预定义的任务序列 (MISSION)"""
    if mission_name not in MISSIONS:
        print(f"[ERROR] 未知的 MISSION 名称: {mission_name}。跳过。")
        return False

    mission_steps = MISSIONS[mission_name]
    print(f"\n--- [MISSION START] 执行子任务: {mission_name} (共 {len(mission_steps)} 步) ---")
    
    for i, step in enumerate(mission_steps):
        action = step[0]
        
        print(f"[MISSION STEP {i + 1}/{len(mission_steps)}] 动作: {action}")
        
        if action == "click":
            icon_name = step[1]
            # 检查是否有自定义偏移参数
            offset_x = step[2] if len(step) > 2 else None
            offset_y = step[3] if len(step) > 3 else None
            success = click_icon(icon_name, wait=False, offset_x_range=offset_x, offset_y_range=offset_y)
            
        elif action == "wait_click":
            icon_name = step[1]
            # 检查是否有自定义偏移参数
            offset_x = step[2] if len(step) > 2 else None
            offset_y = step[3] if len(step) > 3 else None
            success = click_icon(icon_name, wait=True, offset_x_range=offset_x, offset_y_range=offset_y)
            
        elif action == "wait":
            # 支持 MISSION 中的 wait 动作
            wait_time = step[1]
            pure_wait(wait_time)
        else:
            print(f"[WARN] MISSION 中未知动作: {action}，跳过。")
            continue
            
        time.sleep(random.uniform(0.1, 0.3))

    print(f"--- [MISSION END] 子任务: {mission_name} 执行完毕 ---")
    return True


# ==== 主循环 ====
if __name__ == "__main__":
    if not (0 <= START_TASK_INDEX < len(TASKS)):
        print(f"[ERROR] START_TASK_INDEX ({START_TASK_INDEX}) 超出 TASKS 列表范围 (0 到 {len(TASKS) - 1})。程序退出。")
        sys.exit(1)
        
    print(f"[START] 自动执行脚本启动。目标执行次数: {'无限' if MAX_TASK_LOOPS == -1 else MAX_TASK_LOOPS}。")
    print(f"[INIT] 将从任务索引 {START_TASK_INDEX} 开始执行。按 Ctrl+C 停止。")
    
    current_task_index = START_TASK_INDEX
    loop_count = 0 

    try:
        while MAX_TASK_LOOPS == -1 or loop_count < MAX_TASK_LOOPS:
            
            # 检查用户干扰
            if not check_user_interference(current_task_index):
                sys.exit(0)
            
            # 检查是否完成一个完整的循环
            if current_task_index == 0 and loop_count > 0:
                 print(f"--- [LOOP] 完成第 {loop_count} 轮任务 ---")
            
            # 获取当前任务
            task_element = TASKS[current_task_index]
            action_type = task_element[0]

            print(f"[TASK {loop_count + 1}-{current_task_index + 1}/{len(TASKS)}] 动作类型: {action_type}")

            
            # 执行任务逻辑 (支持自定义偏移参数)
            if action_type in ["click", "wait_click"]:
                # 执行单个点击动作
                icon_name = task_element[1]
                # 检查是否有自定义偏移参数
                offset_x = task_element[2] if len(task_element) > 2 else None
                offset_y = task_element[3] if len(task_element) > 3 else None
                
                print(f"  > 执行动作: {action_type}, 目标: {icon_name}")
                if offset_x is not None or offset_y is not None:
                    print(f"  > 自定义偏移: 水平±{offset_x if offset_x else 'default'}, 垂直±{offset_y if offset_y else 'default'}")
                
                if action_type == "click":
                    click_icon(icon_name, wait=False, offset_x_range=offset_x, offset_y_range=offset_y)
                elif action_type == "wait_click":
                    click_icon(icon_name, wait=True, offset_x_range=offset_x, offset_y_range=offset_y)
                
            elif action_type == "mission":
                # 执行一个 MISSION
                mission_name = task_element[1]
                execute_mission(mission_name, loop_count, current_task_index)
            
            elif action_type == "wait":
                # 执行纯等待
                wait_time = task_element[1]
                pure_wait(wait_time)
                
            else:
                print(f"[WARN] 未知任务类型: {action_type}，跳过。")

            # 随机化每个任务后的 IDLE 时间
            idle_duration = random.uniform(IDLE_AFTER_TASK_RANGE[0], IDLE_AFTER_TASK_RANGE[1])
            human_idle(idle_duration) 

            # 进入下一个任务
            current_task_index = (current_task_index + 1) % len(TASKS)
            
            # 如果回到了列表的开头，增加循环计数
            if current_task_index == 0:
                loop_count += 1
                
            time.sleep(random.uniform(0.1, 0.3))

        print(f"\n[DONE] 已达到设定的执行次数 ({MAX_TASK_LOOPS} 次)。脚本停止。")

    except KeyboardInterrupt:
        print("\n[STOP] 用户终止。")
    except SystemExit:
        print("\n[EXIT] 程序安全退出。")
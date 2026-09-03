from __future__ import annotations

import asyncio
import argparse
from collections.abc import Callable
from collections import deque
import os
import queue
import re
import sys
import locale
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import cv2
from PIL import Image, ImageTk

from .analyzer import SIX_AXES, RealtimeAnalyzer
from .audio import AudioAnalyzer, AudioCapture, list_audio_devices
from . import __version__
from .capture import ScreenCapture, ScreenRegion
from .config import AppConfig, DEFAULT_SIX_AXIS_GAINS, DEFAULT_SIX_AXIS_INVERTS
from .preview import PreviewBridge
from .recorder import MultiAxisFunscriptRecorder
from .sinks import (
    BleSink,
    LogSink,
    SerialSink,
    choose_best_serial_port,
    extract_serial_device,
    list_serial_port_infos,
    scan_ble_devices,
)
from .tcode import MultiAxisSafeOutput


TRACKER_MODE_CHOICES = (
    "混合分析（推荐）",
    "Stroke Phase（内测用）",
    "Motion Center（内测用）",
    "Optical Flow（内测用）",
    "Hybrid Motion（内测用）",
    "Activity Pulse（内测用）",
)

TRACKER_MODE_EN = {
    "混合分析（推荐）": "Hybrid Analysis (Recommended)",
    "Stroke Phase（内测用）": "Stroke Phase (Beta)",
    "Motion Center（内测用）": "Motion Center (Beta)",
    "Optical Flow（内测用）": "Optical Flow (Beta)",
    "Hybrid Motion（内测用）": "Hybrid Motion (Beta)",
    "Activity Pulse（内测用）": "Activity Pulse (Beta)",
}

UI_TEXT_EN = {
    "成年人使用确认": "Adults Only",
    "本软件面向成年人使用，未成年禁止入内。": "This software is intended for adults only. Minors are prohibited.",
    "六轴模式只建议在光线好、主体清晰、框选区域干净时使用。": "Use Six Axis only with good lighting, a clear subject, and a clean selected region.",
    "第一次正式使用前，请先用测量模式保存适合自己的安全上限/下限。": "Before real use, save comfortable safe upper/lower limits in measurement mode.",
    "我已满 18 岁，继续": "I am 18+ and continue",
    "未满 18 岁，退出": "Exit",
    "中文": "Chinese",
    "英文": "English",
    "界面语言": "Interface language",
    "五档预设": "Play Preset",
    "1 慢玩  ·  5 刺激": "1 gentle  ·  5 intense",
    "急停回中": "Emergency Center",
    "全行程": "Full Travel",
    "连接并回中": "Connect + Center",
    "实时输出由下限/上限滑块决定。想要更大更快，点全行程。": "Realtime output follows the lower/upper limit sliders. For larger/faster motion, use Full Travel.",
    "收起更多设置": "Hide More Settings",
    "展开更多设置": "Show More Settings",
    "屏幕区域": "Screen Region",
    "宽": "Width",
    "高": "Height",
    "框选区域": "Select Region",
    "输入来源": "Input Source",
    "来源": "Source",
    "视频": "Video",
    "选择": "Browse",
    "分析视频并保存脚本": "Analyze Video + Save Script",
    "声音监听（PMV）": "Audio Only (PMV)",
    "声音分析": "Audio Analysis",
    "声音设备": "Audio Device",
    "刷新": "Refresh",
    "声音增益": "Audio Gain",
    "声音门槛": "Audio Threshold",
    "声音平滑": "Audio Smoothing",
    "选择 Audio Only 后只监听声音，不读取屏幕画面。系统输出回环适合播放 PMV。": "Audio Only listens to sound without reading the screen. System Output is useful for PMV playback.",
    "高级参数": "Advanced",
    "输出模式": "Output Mode",
    "分析模式": "Analysis Mode",
    "间隔 ms": "Interval ms",
    "启用每帧限速": "Enable Frame Speed Limit",
    "限速值": "Speed Limit",
    "启用平滑曲线": "Enable Smoothing",
    "平滑": "Smoothing",
    "启用死区滤波": "Enable Deadzone",
    "死区": "Deadzone",
    "启用 L0 防抽搐": "Enable L0 Jitter Guard",
    "L0 防抖": "L0 Anti-Jitter",
    "极端位自动复位": "Endpoint Auto Reset",
    "极端停留 ms": "Endpoint Hold ms",
    "端点保护": "Endpoint Guard",
    "端点留白 %": "Endpoint Margin %",
    "启用活动门控": "Enable Activity Gate",
    "活动阈值": "Activity Threshold",
    "增益": "Gain",
    "视觉行程": "Visual Travel",
    "压缩延迟": "Compression / Latency",
    "-5 最准确 / 0 默认 / 5 延迟最低": "-5 most accurate / 0 default / 5 lowest latency",
    "响应曲线": "Response Curve",
    "空闲": "Idle",
    "启用启动渐入": "Enable Startup Ramp",
    "渐入 ms": "Ramp ms",
    "反向": "Invert",
    "一键稳态 L0": "Stable L0 Preset",
    "连接设备": "Device Connection",
    "输出": "Output",
    "串口": "Serial Port",
    "波特率": "Baudrate",
    "自动检测 OSR6": "Auto Detect OSR6",
    "BLE 名称": "BLE Name",
    "扫描": "Scan",
    "BLE 地址": "BLE Address",
    "写入 UUID": "Write UUID",
    "断开": "Disconnect",
    "查询设备轴": "Query Device Axes",
    "实时输出": "Realtime Output",
    "下限": "Lower",
    "上限": "Upper",
    "速度": "Speed",
    "居中": "Center",
    "中等测试": "Medium Test",
    "上下全幅测试": "Full L0 Test",
    "OSR6 六轴轻测": "OSR6 Six-Axis Test",
    "恢复所有默认设置": "Restore Defaults",
    "开始实时输出": "Start Realtime Output",
    "显示预览": "Show Preview",
    "取消预览": "Hide Preview",
    "停止": "Stop",
    "安全预设": "Safe",
    "标准预设": "Standard",
    "混合分析灵敏": "Sensitive Hybrid",
    "开始录制": "Start Recording",
    "保存脚本": "Save Script",
    "六轴独立上下限": "Per-Axis Limits",
    "L0 总行程倍率": "L0 Travel Scale",
    "六轴总行程倍率": "Six-Axis Travel Scale",
    "Pose 倾向": "Pose Bias",
    "Pose 倾向 L0": "Pose Bias for L0",
    "Pose L0 权重": "Pose L0 Weight",
    "Pose 倾向六轴": "Pose Bias for Six Axis",
    "Pose 六轴权重": "Pose Six-Axis Weight",
    "轴": "Axis",
    "实时输出与测试会按每个轴自己的范围映射。滑块交叉时会自动整理。": "Realtime output and tests are mapped through each axis limit. Crossed sliders are fixed automatically.",
    "测量模式": "Measurement Mode",
    "滑动即发送": "Send While Sliding",
    "位置": "Position",
    "发送当前位置": "Send Current Position",
    "保存为下限": "Save as Lower",
    "当前轴回中": "Center Axis",
    "保存为上限": "Save as Upper",
    "用于找机械安全范围：先低档、慢慢滑，确认位置后保存上下限。": "Use this to find your safe mechanical range: start low, slide slowly, then save upper/lower limits.",
    "六轴辅助调节（不影响 L0）": "Six-Axis Tuning (L0 unchanged)",
    "总强度": "Overall Strength",
    "六轴降抖": "Six-Axis Stabilizer",
    "一键稳六轴": "Stable Six-Axis Preset",
    "六轴敏感度": "Six-Axis Sensitivity",
    "反": "Inv",
    "建议先把其它轴限位收窄，再逐个放大强度；L0 主轴不会被这些滑块改变。": "Start with narrower auxiliary limits, then increase strength gradually. These sliders do not change L0.",
    "连接失败": "Connection Failed",
    "正在运行": "Running",
    "请先停止实时输出，再查询设备轴。": "Stop realtime output before querying device axes.",
    "暂不支持": "Not Supported Yet",
    "设备轴查询目前只支持 Serial COM。BLE UART 通常需要通知通道，暂时只做写入。": "Device axis query currently supports Serial COM only. BLE UART usually needs a notify channel, so this app only writes for now.",
    "开始实时输出前确认": "Confirm Realtime Output",
    "请先确认上下限已经调好。六轴模式会同时控制 L0/L1/L2/R0/R1/R2，建议先用较窄范围和低档测试。": "Confirm your upper/lower limits first. Six Axis controls L0/L1/L2/R0/R1/R2 together, so start with narrow ranges and low presets.",
    "框选屏幕区域": "Select Screen Region",
    "分析": "Analysis",
    "L0 Only：只上下": "L0 Only: vertical only",
    "Six Axis：六轴": "Six Axis: all axes",
    "当前范围": "Current Range",
    "取消": "Cancel",
    "确认开始": "Start",
    "确认要恢复所有默认设置吗？": "Restore all default settings?",
    "这会重置屏幕区域、输出方式、串口/BLE 信息、上下限、倍率、五档预设、六轴参数、声音参数和高级参数。": "This resets the screen region, output, serial/BLE info, limits, scales, presets, six-axis tuning, audio, and advanced settings.",
    "当前本地保存的设置会被覆盖。": "Your locally saved settings will be overwritten.",
    "预览启动失败": "Preview Failed",
    "拖拽选择实时读取区域": "Drag to select the realtime screen region",
    "建议只框住主要画面动作，避开弹幕、字幕和播放器控件；Enter 确认，R 重选，Esc 取消": "Select only the main motion area; avoid subtitles and player controls. Enter confirms, R reselects, Esc cancels.",
    "当前区域": "Current region",
    "使用此区域": "Use Region",
    "重新选择": "Reselect",
    "区域太小，请重新拖拽": "Region is too small. Drag again.",
    "拔出": "Out",
    "插入": "In",
    "脚本曲线": "Script Curve",
    "最近12秒 / 实际输出": "Last 12s / Real Output",
    "开始输出后显示曲线": "Curve appears after output starts",
    "设备": "Device",
    "已连接": "Connected",
    "未连接": "Not connected",
    "日志模式": "Log mode",
    "连接失败": "Connection failed",
    "已连接并回中": "Connected and centered",
    "实时输出中": "Realtime output running",
    "已停止": "Stopped",
    "已急停并回中": "Emergency centered",
    "已恢复所有默认设置，并保存到本机": "Defaults restored and saved locally",
    "预览已关闭": "Preview closed",
    "预览已打开：显示限制后的真实输出": "Preview open: showing real limited output",
    "未录制": "Not recording",
    "中段": "Middle",
    "活动": "Activity",
    "声音": "Audio",
    "已应用六轴敏感度": "Applied six-axis sensitivity",
    "档": "level",
    "已应用稳六轴：辅助轴更低敏、更少抖": "Applied stable six-axis preset: auxiliary axes are less sensitive and smoother",
    "未发现串口设备": "No serial device found",
    "已选择": "Selected",
    "BLE 扫描中...": "Scanning BLE...",
    "BLE 扫描失败": "BLE scan failed",
    "选择视频文件": "Choose Video File",
    "选择脚本保存基名": "Choose Script Save Name",
    "视频分析中...": "Analyzing video...",
    "视频分析完成": "Video analysis complete",
    "个脚本": "scripts",
    "视频分析失败": "Video analysis failed",
    "无法打开视频": "Cannot open video",
    "设备轴查询": "Device axis query",
    "设备轴查询失败": "Device axis query failed",
    "无回复：可继续用六轴轻测，或确认固件是否支持 TCode D2 查询。": "No reply: you can still use the six-axis test, or confirm whether the firmware supports TCode D2 query.",
    "请先停止实时输出，再恢复默认设置。": "Stop realtime output before restoring defaults.",
    "请先停止实时输出，再使用测量模式": "Stop realtime output before using measurement mode.",
    "测量模式: 请先连接设备": "Measurement mode: connect a device first",
    "测量发送失败": "Measurement send failed",
    "已保存": "Saved",
    "请先停止实时输出，再做中等测试。": "Stop realtime output before running the medium test.",
    "中等测试完成": "Medium test complete",
    "请先停止实时输出，再做上下全幅测试。": "Stop realtime output before running the full L0 test.",
    "上下全幅测试中": "Full L0 test running",
    "上下全幅测试完成，已回中": "Full L0 test complete, centered",
    "上下全幅测试失败": "Full L0 test failed",
    "请先停止实时输出，再做六轴轻测。": "Stop realtime output before running the six-axis test.",
    "OSR6 六轴轻测中": "OSR6 six-axis test running",
    "OSR6 六轴轻测完成，已回中": "OSR6 six-axis test complete, centered",
    "六轴轻测失败": "Six-axis test failed",
    "已应用安全预设": "Applied safe preset",
    "已应用标准预设": "Applied standard preset",
    "已应用上下全行程高速预设": "Applied full-travel fast preset",
    "已应用混合分析稳态预设": "Applied stable hybrid analysis preset",
    "已应用稳态 L0 + 低敏六轴": "Applied stable L0 + low-sensitivity six-axis",
    "已应用": "Applied",
    "预设": "preset",
    "录制中": "Recording",
    "保存 funscript": "Save funscript",
    "已保存:": "Saved:",
    "点": "points",
    "已选择区域": "Selected region",
    "找到 BLE": "Found BLE",
    "未找到 BLE 设备": "No BLE device found",
    "插入中（去下限）": "Inward (toward lower)",
    "拔出中（去上限）": "Outward (toward upper)",
    "插入端（下限）": "In endpoint (lower)",
    "拔出端（上限）": "Out endpoint (upper)",
}

UI_TEXT_REVERSE_EN = {value: key for key, value in UI_TEXT_EN.items()}


TOOLTIPS = {
    "五档预设": "一键切换整体速度、平滑和幅度；1 更柔，5 更刺激。",
    "1 慢玩  ·  5 刺激": "数字越小越慢越稳，数字越大越快越强。",
    "急停回中": "立即停止实时输出，并把当前启用的轴回到中间位置。",
    "全行程": "把 L0 切到更大更快的全行程测试参数。",
    "连接并回中": "连接当前选择的设备，并发送回中命令。",
    "开始实时输出前确认": "启动设备前最后确认输出模式和上下限。",
    "L0 Only：只上下": "只输出 L0 上下轴，最适合先测试。",
    "Six Axis：六轴": "同时输出 L0/L1/L2/R0/R1/R2。",
    "确认开始": "按当前选择的模式开始实时输出。",
    "取消": "关闭当前确认窗口，不启动输出。",
    "连接设备": "选择 USB 串口或 BLE，并连接 OSR6 控制器。",
    "输出": "选择只看日志、USB 串口或 BLE UART 输出。",
    "串口": "USB 或蓝牙串口号，例如 COMx。",
    "刷新": "重新扫描电脑上的串口或声音设备。",
    "波特率": "串口通信速度；OSR 常见为 115200。",
    "自动检测 OSR6": "从可用串口里猜测最可能的 OSR6 控制口。",
    "BLE 名称": "按蓝牙设备名称过滤扫描结果。",
    "扫描": "扫描附近 BLE UART 设备。",
    "BLE 地址": "BLE 设备地址，扫描后会自动填入。",
    "写入 UUID": "BLE UART 的写入通道 UUID。",
    "断开": "关闭当前设备连接。",
    "查询设备轴": "向串口发送 D2，查看固件开放了哪些 TCode 轴。",
    "实时输出": "屏幕、视频或声音实时转换成 TCode 输出。",
    "下限": "当前轴允许到达的最小 TCode 值。",
    "上限": "当前轴允许到达的最大 TCode 值。",
    "速度": "每帧最多允许变化多少 TCode 数值，越大动作越快。",
    "居中": "发送回中命令。",
    "中等测试": "发送较小幅度的安全测试动作。",
    "上下全幅测试": "只测试 L0 上下轴的完整范围。",
    "OSR6 六轴轻测": "逐个轻微测试 L0/L1/L2/R0/R1/R2。",
    "开始实时输出": "开始读取输入来源并控制设备。",
    "恢复所有默认设置": "把所有参数恢复到新安装时的默认值；点击后会先二次确认。",
    "显示预览": "打开 3D 预览；显示的是已经过上下限、速度和平滑限制后的真实输出。",
    "取消预览": "关闭预览同步；已打开的浏览器页可直接关掉。",
    "停止": "停止实时输出，保持连接。",
    "安全预设": "更慢、更小幅，适合初次测试。",
    "标准预设": "日常推荐的折中参数。",
    "混合分析灵敏": "使用混合分析，并提高跟手程度。",
    "六轴独立上下限": "分别限制每个轴的物理输出范围。",
    "总行程倍率": "围绕中点缩放所有轴行程，不会越过每轴上下限。",
    "L0 总行程倍率": "只缩放 L0 上下轴行程，不改变 L0 的机械上下限。",
    "六轴总行程倍率": "只缩放 L1/L2/R0/R1/R2 辅助轴行程，不影响 L0。",
    "轴": "当前要查看或调整的 TCode 通道。",
    "测量模式": "用滑块手动遥控单个轴，方便保存安全上下限。",
    "滑动即发送": "打开后拖动测量滑块会立刻发送到设备。",
    "位置": "当前手动发送的 TCode 位置值。",
    "发送当前位置": "把测量滑块的位置发送给当前轴。",
    "保存为下限": "把当前测量位置保存为该轴下限。",
    "当前轴回中": "把当前测量轴发送到 5000。",
    "保存为上限": "把当前测量位置保存为该轴上限。",
    "六轴辅助调节（不影响 L0）": "只调整 L1/L2/R0/R1/R2，不改变 L0 主轴。",
    "总强度": "整体放大或缩小非 L0 五个辅助轴。",
    "六轴降抖": "越往右，辅助轴越不敏感、越平滑、越不容易抖。",
    "一键稳六轴": "把辅助轴调成低敏稳态，适合先解决抖动。",
    "六轴敏感度": "只调整非 L0 五个辅助轴；1 最稳，5 为新版默认，6-10 更灵敏。",
    "展开更多设置": "显示输入来源、声音、屏幕坐标和高级参数。",
    "收起更多设置": "隐藏不常用设置，让主界面更清爽。",
    "一键低敏六轴": "切到 Six Axis，并使用低敏但可见的辅助轴参数。",
    "反": "反转这个辅助轴的方向。",
    "L1": "前后 surge 辅助轴。",
    "L2": "左右 sway 辅助轴。",
    "R0": "twist 扭转轴。",
    "R1": "roll 横滚轴。",
    "R2": "pitch 俯仰轴。",
    "输入来源": "选择读取屏幕、读取视频文件或只监听声音。",
    "来源": "实时分析的数据来源。",
    "视频": "待分析的视频文件路径。",
    "选择": "选择本地视频文件。",
    "分析视频并保存脚本": "离线分析视频并导出 funscript。",
    "声音监听（PMV）": "只根据声音强度或节拍输出 L0。",
    "声音分析": "选择音频转动作的方式。",
    "声音设备": "选择系统输出回环或麦克风输入。",
    "声音增益": "放大声音信号，越大越容易触发动作。",
    "声音门槛": "低于这个声音强度时不触发动作。",
    "声音平滑": "声音动作平滑程度，越高越稳但越慢。",
    "极端位自动复位": "卡在上限/下限附近太久时自动松回中段，防止一直顶住不动。",
    "极端停留 ms": "贴近上限/下限超过这个时间后才开始自动复位。",
    "端点保护": "实时输出时给上下极限留出缓冲，避免 L0 一直顶到机械端点。",
    "端点留白 %": "L0 上下两端保留多少行程；越大越不容易顶到底。",
    "屏幕区域": "限定读屏范围，减少无关画面干扰。",
    "X": "屏幕区域左上角横坐标。",
    "Y": "屏幕区域左上角纵坐标。",
    "宽": "读屏区域宽度。",
    "高": "读屏区域高度。",
    "框选区域": "用鼠标直观选择屏幕分析区域。",
    "高级参数": "控制分析、滤波、速度和响应方式。",
    "输出模式": "L0 Only 只输出上下；Six Axis 输出六轴。",
    "分析模式": "选择屏幕运动识别算法。",
    "Pose 倾向 L0": "适合扭腰、舞蹈、PMV 画面；减少 L0 把左右摆动误判成上下到底。",
    "Pose 倾向六轴": "让横摆、扭腰、重复舞蹈更多体现在 L1/L2/R0/R1/R2 上。",
    "Pose L0 权重": "越大越偏向完整人物舞蹈/扭腰横摆理解，L0 越不容易把左右摆动误判成上下。",
    "Pose 六轴权重": "越大越像显示完整人物的舞蹈，横摆、扭腰和身体角度会更多分配给六轴辅助。",
    "框选屏幕区域": "启动前重新选择实时读取范围，减少无关画面干扰。",
    "FPS": "每秒分析帧数，越高越跟手也越吃性能。",
    "间隔 ms": "TCode 命令的 I 时间，通常和输出刷新速度相关。",
    "启用每帧限速": "限制每帧最大变化，减少突然猛动。",
    "限速值": "每帧允许变化的最大 TCode 数值。",
    "启用平滑曲线": "对输出做平滑，减少生硬抖动。",
    "平滑": "越高越稳，越低越跟手。",
    "启用死区滤波": "忽略很小的画面变化。",
    "死区": "小于这个变化量时不更新输出。",
    "启用 L0 防抽搐": "专门压住 L0 小幅反复反转。",
    "L0 防抖": "越高 L0 越稳，但小动作会更钝。",
    "启用活动门控": "画面活动太小时保持当前动作或回中。",
    "活动阈值": "低于这个活动量时视为无有效运动。",
    "增益": "放大视觉运动，越大越敏感。",
    "视觉行程": "控制画面动作映射到 L0 行程的幅度。",
    "压缩延迟": "默认 0 不压缩画面。调到 1..5 会降低分析分辨率以减少延迟；-5..0 保持原始画面，优先准确。",
    "响应曲线": "改变中段和两端的响应手感。",
    "空闲": "无有效运动时保持当前位置或回中。",
    "启用启动渐入": "开始输出时逐渐进入动作，避免突然跳动。",
    "渐入 ms": "启动渐入持续时间。",
    "反向": "反转 L0 上下方向。",
    "一键稳态 L0": "把 L0 调成更稳、更少抽搐的参数。",
    "开始录制": "把实时输出记录为脚本。",
    "保存脚本": "保存当前录制的 funscript 文件。",
}

TOOLTIPS_EN = {
    "五档预设": "Switch overall speed, smoothing, and travel. 1 is gentle; 5 is stronger.",
    "1 慢玩  ·  5 刺激": "Lower numbers are slower and steadier. Higher numbers are faster and stronger.",
    "急停回中": "Stop realtime output immediately and move active axes back to center.",
    "全行程": "Use larger and faster L0 travel for full-range testing.",
    "连接并回中": "Connect the selected device and send a center command.",
    "开始实时输出前确认": "Final check for output mode and limits before starting.",
    "L0 Only：只上下": "Only output the L0 vertical axis. Best for first tests.",
    "Six Axis：六轴": "Output L0/L1/L2/R0/R1/R2 together.",
    "确认开始": "Start realtime output with the selected settings.",
    "取消": "Close this dialog without starting output.",
    "连接设备": "Choose USB serial or BLE, then connect the OSR6 controller.",
    "输出": "Choose log-only, USB serial, or BLE UART output.",
    "串口": "USB or Bluetooth serial port, such as COMx.",
    "刷新": "Scan serial or audio devices again.",
    "波特率": "Serial speed. OSR devices commonly use 115200.",
    "自动检测 OSR6": "Pick the serial port that most likely belongs to OSR6.",
    "BLE 名称": "Filter BLE scan results by device name.",
    "扫描": "Scan nearby BLE UART devices.",
    "BLE 地址": "BLE device address, filled after scanning.",
    "写入 UUID": "BLE UART write characteristic UUID.",
    "断开": "Close the current device connection.",
    "查询设备轴": "Send D2 over serial to see which TCode axes the firmware exposes.",
    "实时输出": "Convert screen, video, or audio motion to realtime TCode output.",
    "下限": "Minimum allowed TCode value for this axis.",
    "上限": "Maximum allowed TCode value for this axis.",
    "速度": "Maximum TCode change per frame. Higher means faster motion.",
    "居中": "Send a center command.",
    "中等测试": "Send a small safe test motion.",
    "上下全幅测试": "Test the full L0 vertical range only.",
    "OSR6 六轴轻测": "Lightly test L0/L1/L2/R0/R1/R2 one by one.",
    "开始实时输出": "Start reading the selected input and controlling the device.",
    "恢复所有默认设置": "Restore factory defaults after a confirmation prompt.",
    "显示预览": "Open the 3D preview. It shows the real output after limits, speed, and smoothing.",
    "取消预览": "Stop preview sync. You can close the browser preview window.",
    "停止": "Stop realtime output while keeping the device connection.",
    "安全预设": "Slower and smaller motion, useful for first tests.",
    "标准预设": "Balanced daily settings.",
    "混合分析灵敏": "Use Hybrid Analysis with more direct response.",
    "六轴独立上下限": "Limit each physical axis separately.",
    "总行程倍率": "Scale all axis travel around center without crossing saved limits.",
    "L0 总行程倍率": "Scale only L0 travel without changing its mechanical limits.",
    "六轴总行程倍率": "Scale L1/L2/R0/R1/R2 travel without affecting L0.",
    "轴": "The TCode channel being viewed or adjusted.",
    "测量模式": "Manually control one axis with a slider and save safe limits.",
    "滑动即发送": "Send commands immediately while dragging the measurement slider.",
    "位置": "Current manual TCode position.",
    "发送当前位置": "Send the measurement slider value to the selected axis.",
    "保存为下限": "Save the current measurement value as this axis lower limit.",
    "当前轴回中": "Move the selected measurement axis to 5000.",
    "保存为上限": "Save the current measurement value as this axis upper limit.",
    "六轴辅助调节（不影响 L0）": "Tune L1/L2/R0/R1/R2 only. L0 is unchanged.",
    "总强度": "Overall strength for the five non-L0 auxiliary axes.",
    "六轴降抖": "Higher values make auxiliary axes less sensitive, smoother, and steadier.",
    "一键稳六轴": "Apply a low-sensitivity six-axis setup to reduce jitter.",
    "六轴敏感度": "Adjust non-L0 axes only. 1 is steadiest, 5 is default, 6-10 are more sensitive.",
    "展开更多设置": "Show input, audio, screen region, and advanced settings.",
    "收起更多设置": "Hide less common settings for a cleaner main view.",
    "一键低敏六轴": "Switch to Six Axis with visible but low-sensitivity auxiliary motion.",
    "反": "Invert this auxiliary axis direction.",
    "L1": "Surge auxiliary axis.",
    "L2": "Sway auxiliary axis.",
    "R0": "Twist axis.",
    "R1": "Roll axis.",
    "R2": "Pitch axis.",
    "输入来源": "Choose screen capture, video file, or audio-only listening.",
    "来源": "The data source for realtime analysis.",
    "视频": "Path to the video file to analyze.",
    "选择": "Choose a local video file.",
    "分析视频并保存脚本": "Analyze a video offline and export funscript files.",
    "声音监听（PMV）": "Output L0 from audio level or rhythm only.",
    "声音分析": "Choose how audio is converted to motion.",
    "声音设备": "Choose system loopback or microphone input.",
    "声音增益": "Boost the audio signal. Higher values trigger motion more easily.",
    "声音门槛": "Audio below this level will not trigger motion.",
    "声音平滑": "Higher values are steadier but respond slower.",
    "极端位自动复位": "If the output stays near an endpoint too long, ease back toward center.",
    "极端停留 ms": "How long the output must stay near an endpoint before auto reset starts.",
    "端点保护": "Leave buffer near mechanical extremes during realtime output.",
    "端点留白 %": "How much L0 travel to reserve at both ends.",
    "屏幕区域": "Limit the screen-reading area to reduce unrelated motion.",
    "X": "Left coordinate of the screen region.",
    "Y": "Top coordinate of the screen region.",
    "宽": "Width of the screen-reading region.",
    "高": "Height of the screen-reading region.",
    "框选区域": "Select the screen analysis region with the mouse.",
    "高级参数": "Control analysis, filtering, speed, and response.",
    "输出模式": "L0 Only controls vertical motion only. Six Axis controls all axes.",
    "分析模式": "Choose the screen motion analysis method.",
    "Pose 倾向 L0": "Useful for dance or full-body motion; prevents L0 from overreacting to side-to-side motion.",
    "Pose 倾向六轴": "Map sway, twist, and body angle more strongly to auxiliary axes.",
    "Pose L0 权重": "Higher values favor full-body dance interpretation and reduce false L0 extremes.",
    "Pose 六轴权重": "Higher values make full-body dance, sway, and angle drive auxiliary axes more.",
    "框选屏幕区域": "Select the realtime capture region before starting.",
    "FPS": "Frames analyzed per second. Higher is more responsive and uses more CPU.",
    "间隔 ms": "The TCode I time, usually related to output refresh speed.",
    "启用每帧限速": "Limit maximum change per frame to reduce sudden moves.",
    "限速值": "Maximum TCode change allowed per frame.",
    "启用平滑曲线": "Smooth the output to reduce harsh jitter.",
    "平滑": "Higher is steadier. Lower follows the picture more directly.",
    "启用死区滤波": "Ignore very small screen changes.",
    "死区": "Ignore updates smaller than this amount.",
    "启用 L0 防抽搐": "Specifically reduce tiny rapid L0 reversals.",
    "L0 防抖": "Higher makes L0 steadier, but small motion becomes softer.",
    "启用活动门控": "When screen activity is too low, hold or center instead of chasing noise.",
    "活动阈值": "Activity below this value is treated as no useful motion.",
    "增益": "Amplify visual motion sensitivity.",
    "视觉行程": "How much visual motion maps to L0 travel.",
    "压缩延迟": "Default 0 keeps the original frame. 1..5 lowers analysis resolution for less latency; -5..0 keeps original detail for accuracy.",
    "响应曲线": "Change response feel around center and endpoints.",
    "空闲": "What to do when there is no useful motion.",
    "启用启动渐入": "Ramp in at start to avoid a sudden jump.",
    "渐入 ms": "Duration of startup ramp.",
    "反向": "Invert L0 vertical direction.",
    "一键稳态 L0": "Set L0 to a steadier, less jittery setup.",
    "开始录制": "Record realtime output as a script.",
    "保存脚本": "Save the current recording as funscript files.",
}


class Tooltip:
    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.window: tk.Toplevel | None = None
        self.after_id: str | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event: tk.Event | None = None) -> None:
        self._cancel()
        self.after_id = self.widget.after(420, self._show)

    def _show(self) -> None:
        if self.window is not None:
            return
        x = self.widget.winfo_pointerx() + 14
        y = self.widget.winfo_pointery() + 14
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.window,
            text=self.text,
            justify="left",
            background="#222831",
            foreground="#f7f7f7",
            relief="solid",
            borderwidth=1,
            padx=8,
            pady=5,
            wraplength=260,
        )
        label.pack()

    def _hide(self, _event: tk.Event | None = None) -> None:
        self._cancel()
        if self.window is not None:
            self.window.destroy()
            self.window = None

    def _cancel(self) -> None:
        if self.after_id is not None:
            try:
                self.widget.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None


class OsrScreenApp(tk.Tk):
    def __init__(
        self,
        auto_connect: bool = False,
        center_on_connect: bool = False,
        enforce_age_gate: bool = True,
        ui_language: str = "auto",
    ) -> None:
        super().__init__()
        self.ui_language = "en"
        self.title(f"OSR6 Realtime Screen TCode v{__version__}")
        self.geometry("1040x700")
        self.minsize(960, 620)
        if enforce_age_gate and not os.environ.get("OSR_SCREEN_TCODE_SKIP_AGE_GATE"):
            self._confirm_adult_use_or_exit()

        self.config_model = AppConfig.load()
        self.ui_language = self._choose_ui_language(ui_language)
        self.config_model.extra["ui_language"] = self.ui_language
        self.frame_queue: queue.Queue[dict[str, object]] = queue.Queue(maxsize=3)
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.sink = LogSink()
        self.connected = False
        self.auto_connect = auto_connect
        self.center_on_connect = center_on_connect
        self._config_save_after_id: str | None = None
        self._config_autosave_suspended = False
        self.preview_image: ImageTk.PhotoImage | None = None
        self.preview_canvas_image: int | None = None
        self.preview_bridge = PreviewBridge()
        self.recorder = MultiAxisFunscriptRecorder()
        self._startup_window_geometry: str | None = None

        self._build_vars()
        self._build_ui()
        self._install_config_autosave()
        if not self.config_model.extra.get("play_preset_initialized_v1"):
            self.apply_play_preset(3, announce=False)
            self.config_model.extra["play_preset_initialized_v1"] = True
        self.refresh_ports()
        self.refresh_audio_devices()
        if self.config_model.serial_port:
            self.serial_port.set(self.config_model.serial_port)
            self.refresh_ports()
        else:
            self.autodetect_device()
        self.after(50, self._poll_worker)
        self.after(400, self._startup_actions)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _resolve_ui_language(self, requested: str = "auto", allow_saved: bool = True) -> str:
        requested = (requested or "auto").lower()
        if requested in {"zh", "cn"}:
            return "zh"
        if requested == "en":
            return "en"
        env_language = os.environ.get("OSR_SCREEN_TCODE_LANG", "").lower()
        if env_language in {"zh", "cn"}:
            return "zh"
        if env_language == "en":
            return "en"

        path_hint = " ".join(
            [
                str(Path(getattr(sys, "executable", ""))),
                str(Path.cwd()),
            ]
        ).lower()
        if "windows-en" in path_hint or "english" in path_hint:
            return "en"
        if "windows-cn" in path_hint or "chinese" in path_hint:
            return "zh"

        if allow_saved and hasattr(self, "config_model"):
            saved_language = str(self.config_model.extra.get("ui_language", "")).lower()
            if saved_language in {"zh", "cn"}:
                return "zh"
            if saved_language == "en":
                return "en"
        locale_name = (locale.getlocale()[0] or "").lower()
        return "zh" if locale_name.startswith("zh") else "en"

    def _confirm_adult_use_or_exit(self) -> None:
        accepted = tk.BooleanVar(value=False)
        dialog = tk.Toplevel(self)
        dialog.title("Adults Only")
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)

        body = tk.Frame(dialog, padx=22, pady=18)
        body.pack(fill="both", expand=True)
        tk.Label(
            body,
            text="ADULTS ONLY",
            font=("TkDefaultFont", 18, "bold"),
            foreground="#8a1f11",
        ).pack(anchor="w")
        tk.Label(
            body,
            text="成年人使用确认 / 未成年禁止入内",
            font=("TkDefaultFont", 11),
            foreground="#8a1f11",
        ).pack(anchor="w", pady=(2, 10))
        tk.Label(
            body,
            text=(
                "This software is intended for adults only. Minors are prohibited.\n"
                "Six-axis mode should only be used with good lighting, a clear subject, "
                "and a clean selected screen region.\n"
                "Before real use, save comfortable safe upper/lower limits in measurement mode.\n\n"
                "本软件仅面向成年人使用。六轴模式只建议在光线好、主体清晰、框选干净时使用。"
                "第一次正式使用前，请先用测量模式保存适合自己的安全上限/下限。"
            ),
            justify="left",
            wraplength=560,
            padx=0,
            pady=14,
        ).pack(anchor="w")
        button_row = tk.Frame(body)
        button_row.pack(fill="x", pady=(8, 0))

        def accept() -> None:
            accepted.set(True)
            dialog.destroy()

        def decline() -> None:
            accepted.set(False)
            dialog.destroy()

        tk.Button(
            button_row,
            text="I am 18+ / 我已成年",
            command=accept,
            width=28,
        ).pack(side="left")
        tk.Button(
            button_row,
            text="Exit / 退出",
            command=decline,
            width=24,
        ).pack(side="right")
        dialog.bind("<Return>", lambda _event: accept())
        dialog.bind("<Escape>", lambda _event: decline())
        dialog.protocol("WM_DELETE_WINDOW", decline)
        dialog.update_idletasks()
        x = self.winfo_screenwidth() // 2 - dialog.winfo_width() // 2
        y = self.winfo_screenheight() // 2 - dialog.winfo_height() // 2
        dialog.geometry(f"+{x}+{y}")
        dialog.lift()
        dialog.focus_force()
        dialog.grab_set()
        self.wait_window(dialog)
        if not accepted.get():
            self.destroy()
            raise SystemExit(0)

    def _choose_ui_language(self, requested: str = "auto") -> str:
        requested = (requested or "auto").lower()
        default_language = self._resolve_ui_language(requested, allow_saved=True)
        if requested in {"zh", "cn", "en"}:
            return default_language

        chosen = tk.StringVar(value=default_language)
        dialog = tk.Toplevel(self)
        dialog.title("Choose Language / 选择语言")
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)

        body = tk.Frame(dialog, padx=24, pady=18)
        body.pack(fill="both", expand=True)
        tk.Label(
            body,
            text="Choose Interface Language",
            font=("TkDefaultFont", 16, "bold"),
        ).pack(anchor="w")
        tk.Label(
            body,
            text="选择界面语言",
            foreground="#555555",
            pady=4,
        ).pack(anchor="w")
        button_row = tk.Frame(body)
        button_row.pack(fill="x", pady=(14, 0))

        def pick(value: str) -> None:
            chosen.set(value)
            dialog.destroy()

        tk.Button(button_row, text="English", command=lambda: pick("en"), width=18).pack(side="left", padx=(0, 10))
        tk.Button(button_row, text="中文", command=lambda: pick("zh"), width=18).pack(side="left")
        dialog.bind("<Return>", lambda _event: pick(default_language))
        dialog.bind("<Escape>", lambda _event: pick(default_language))
        dialog.protocol("WM_DELETE_WINDOW", lambda: pick(default_language))
        dialog.update_idletasks()
        x = self.winfo_screenwidth() // 2 - dialog.winfo_width() // 2
        y = self.winfo_screenheight() // 2 - dialog.winfo_height() // 2
        dialog.geometry(f"+{x}+{y}")
        dialog.lift()
        dialog.focus_force()
        dialog.grab_set()
        self.wait_window(dialog)
        return "zh" if chosen.get() == "zh" else "en"

    def _t(self, text: str) -> str:
        if self.ui_language != "en":
            return UI_TEXT_REVERSE_EN.get(text, text)
        return UI_TEXT_EN.get(text, text)

    def _tracker_choices(self) -> tuple[str, ...]:
        if self.ui_language != "en":
            return TRACKER_MODE_CHOICES
        return tuple(TRACKER_MODE_EN.get(choice, choice) for choice in TRACKER_MODE_CHOICES)

    def _tracker_display(self, value: str) -> str:
        if self.ui_language != "en":
            return value
        return TRACKER_MODE_EN.get(value, value)

    def _tracker_internal(self, value: str) -> str:
        reverse = {display: internal for internal, display in TRACKER_MODE_EN.items()}
        return reverse.get(value, value)

    def _set_tracker_mode(self, value: str) -> None:
        self.tracker_mode.set(self._tracker_display(value))

    def _startup_actions(self) -> None:
        if not self.auto_connect:
            return
        self.sink_type.set("Serial COM")
        if not self.serial_port.get():
            self.autodetect_device()
        self.connect_sink()
        if self.connected and self.center_on_connect:
            self.send_center(interval_ms=600)

    def _build_vars(self) -> None:
        cfg = self.config_model
        self.x = tk.IntVar(value=cfg.x)
        self.y = tk.IntVar(value=cfg.y)
        self.width = tk.IntVar(value=cfg.width)
        self.height = tk.IntVar(value=cfg.height)
        self.fps = tk.IntVar(value=cfg.fps)
        self.source_mode = tk.StringVar(value=cfg.extra.get("source_mode", "Screen"))
        self.video_path = tk.StringVar(value=cfg.extra.get("video_path", ""))
        self.output_mode = tk.StringVar(value=cfg.extra.get("output_mode", "L0 Only"))
        self.audio_mode = tk.StringVar(value=cfg.audio_mode)
        self.audio_gain = tk.DoubleVar(value=cfg.audio_gain)
        self.audio_threshold = tk.DoubleVar(value=cfg.audio_threshold)
        self.audio_smoothing = tk.DoubleVar(value=cfg.audio_smoothing)
        self.audio_device = tk.StringVar(value=cfg.audio_device)
        stored_limits = cfg.axis_limits if isinstance(cfg.axis_limits, dict) else {}
        self.axis_min_vars: dict[str, tk.IntVar] = {}
        self.axis_max_vars: dict[str, tk.IntVar] = {}
        for axis in SIX_AXES:
            raw_limit = stored_limits.get(axis)
            if not isinstance(raw_limit, (list, tuple)) or len(raw_limit) < 2:
                raw_limit = (cfg.min_value, cfg.max_value)
            try:
                low, high = int(float(raw_limit[0])), int(float(raw_limit[1]))
            except (TypeError, ValueError):
                low, high = cfg.min_value, cfg.max_value
            self.axis_min_vars[axis] = tk.IntVar(value=max(0, min(9999, low)))
            self.axis_max_vars[axis] = tk.IntVar(value=max(0, min(9999, high)))
        # Keep the compact L0 controls as aliases for backwards-compatible presets/configs.
        self.min_value = self.axis_min_vars["L0"]
        self.max_value = self.axis_max_vars["L0"]
        self.smoothing = tk.DoubleVar(value=cfg.smoothing)
        self.enable_smoothing = tk.BooleanVar(value=cfg.enable_smoothing)
        self.deadzone = tk.DoubleVar(value=cfg.deadzone)
        self.enable_deadzone = tk.BooleanVar(value=cfg.enable_deadzone)
        self.enable_l0_jitter_guard = tk.BooleanVar(value=bool(cfg.extra.get("enable_l0_jitter_guard", True)))
        self.l0_guard_strength = tk.DoubleVar(value=float(cfg.extra.get("l0_guard_strength", 0.65)))
        self.enable_extreme_reset = tk.BooleanVar(value=bool(cfg.extra.get("enable_extreme_reset", True)))
        self.extreme_hold_ms = tk.IntVar(value=int(cfg.extra.get("extreme_hold_ms", 900)))
        self.enable_endpoint_guard = tk.BooleanVar(value=bool(cfg.extra.get("enable_endpoint_guard", True)))
        self.endpoint_margin_pct = tk.IntVar(value=int(cfg.extra.get("endpoint_margin_pct", 10)))
        legacy_pose = bool(cfg.extra.get("pose_dance_analysis", False))
        self.pose_l0_analysis = tk.BooleanVar(value=bool(cfg.extra.get("pose_l0_analysis", legacy_pose)))
        self.pose_six_axis_analysis = tk.BooleanVar(value=bool(cfg.extra.get("pose_six_axis_analysis", legacy_pose)))
        self.pose_l0_weight = tk.IntVar(value=int(cfg.extra.get("pose_l0_weight", 60)))
        self.pose_six_axis_weight = tk.IntVar(value=int(cfg.extra.get("pose_six_axis_weight", 60)))
        self.tracker_mode = tk.StringVar(value=self._tracker_display(cfg.tracker_mode))
        self.response_curve = tk.StringVar(value=cfg.response_curve)
        self.motion_gain = tk.DoubleVar(value=cfg.motion_gain)
        self.visual_stroke_scale = tk.DoubleVar(value=cfg.visual_stroke_scale)
        self.compression_latency = tk.IntVar(value=max(-5, min(5, int(cfg.extra.get("compression_latency", 0)))))
        self.l0_travel_scale = tk.DoubleVar(value=float(cfg.extra.get("l0_travel_scale", cfg.global_travel_scale)))
        self.global_travel_scale = tk.DoubleVar(value=cfg.global_travel_scale)
        self._travel_slider_syncing = False
        self.l0_travel_slider = tk.DoubleVar(value=self._travel_scale_to_slider(self.l0_travel_scale.get()))
        self.global_travel_slider = tk.DoubleVar(value=self._travel_scale_to_slider(self.global_travel_scale.get()))
        self.l0_travel_text = tk.StringVar(value=self._format_travel_scale(self.l0_travel_scale.get()))
        self.global_travel_text = tk.StringVar(value=self._format_travel_scale(self.global_travel_scale.get()))
        self.play_preset_level = tk.IntVar(value=int(cfg.extra.get("play_preset_level", 3)))
        self.six_axis_intensity = tk.IntVar(value=int(cfg.extra.get("six_axis_intensity", 65)))
        self.six_axis_jitter_reduction = tk.IntVar(value=int(cfg.extra.get("six_axis_jitter_reduction", 55)))
        self.six_axis_sensitivity_level = tk.IntVar(value=int(cfg.extra.get("six_axis_sensitivity_level", 5)))
        self.show_more_settings = tk.BooleanVar(value=bool(cfg.extra.get("show_more_settings", False)))
        stored_gains = cfg.extra.get("six_axis_gains", {})
        stored_inverts = cfg.extra.get("six_axis_inverts", {})
        self.six_axis_gain_vars: dict[str, tk.IntVar] = {}
        self.six_axis_invert_vars: dict[str, tk.BooleanVar] = {}
        for axis in SIX_AXES:
            if axis == "L0":
                continue
            gain = stored_gains.get(axis, DEFAULT_SIX_AXIS_GAINS.get(axis, 60)) if isinstance(stored_gains, dict) else DEFAULT_SIX_AXIS_GAINS.get(axis, 60)
            inverted = stored_inverts.get(axis, DEFAULT_SIX_AXIS_INVERTS.get(axis, False)) if isinstance(stored_inverts, dict) else DEFAULT_SIX_AXIS_INVERTS.get(axis, False)
            self.six_axis_gain_vars[axis] = tk.IntVar(value=max(0, min(200, int(float(gain)))))
            self.six_axis_invert_vars[axis] = tk.BooleanVar(value=bool(inverted))
        self.min_activity = tk.DoubleVar(value=cfg.min_activity)
        self.enable_activity_gate = tk.BooleanVar(value=cfg.enable_activity_gate)
        self.max_step = tk.IntVar(value=cfg.max_step)
        self.enable_speed_limit = tk.BooleanVar(value=cfg.enable_speed_limit)
        self.idle_mode = tk.StringVar(value=cfg.idle_mode)
        self.invert = tk.BooleanVar(value=cfg.invert)
        self.enable_startup_ramp = tk.BooleanVar(value=cfg.enable_startup_ramp)
        self.startup_ramp_ms = tk.IntVar(value=cfg.startup_ramp_ms)
        self.axis = tk.StringVar(value=cfg.axis)
        self.interval_ms = tk.IntVar(value=cfg.output_interval_ms)
        self.sink_type = tk.StringVar(value=cfg.last_sink)
        self.serial_port = tk.StringVar(value=cfg.serial_port)
        self.baudrate = tk.IntVar(value=cfg.baudrate)
        self.ble_name = tk.StringVar(value=cfg.ble_name)
        self.ble_address = tk.StringVar(value=cfg.ble_address)
        self.ble_service_uuid = tk.StringVar(value=cfg.ble_service_uuid)
        self.ble_write_uuid = tk.StringVar(value=cfg.ble_write_uuid)
        self.status = tk.StringVar(value=self._t("未连接"))
        self.device_status = tk.StringVar(value=f"{self._t('设备')}: {self._t('未连接')}")
        self.output_value = tk.StringVar(value="L05000I20")
        self.l0_status = tk.StringVar(value="L0 5000")
        self.stroke_status = tk.StringVar(value=f"{self._t('中段')} 50%")
        self.range_status = tk.StringVar(value=f"L0 {self._t('下限')} 0 / {self._t('上限')} 9999")
        measure_axis = cfg.extra.get("measure_axis", "L0")
        if measure_axis not in SIX_AXES:
            measure_axis = "L0"
        try:
            measure_value = max(0, min(9999, int(float(cfg.extra.get("measure_value", 5000)))))
        except (TypeError, ValueError):
            measure_value = 5000
        self.measure_axis = tk.StringVar(value=measure_axis)
        self.measure_value = tk.IntVar(value=measure_value)
        self.measure_live = tk.BooleanVar(value=bool(cfg.extra.get("measure_live", True)))
        self.activity = tk.StringVar(value=f"{self._t('活动')}: 0.000")
        self.record_status = tk.StringVar(value=self._t("未录制"))
        self._last_axis_values = {axis: 5000 for axis in SIX_AXES}
        self._six_axis_stable_positions = {axis: 0.5 for axis in SIX_AXES}
        self._previous_l0_value = 5000
        self._script_history: deque[tuple[float, dict[str, int]]] = deque(maxlen=900)
        self._last_measure_sent = 0.0
        self.min_value.trace_add("write", lambda *_args: self._refresh_limit_text())
        self.max_value.trace_add("write", lambda *_args: self._refresh_limit_text())
        self.l0_travel_scale.trace_add("write", lambda *_args: self._sync_travel_slider(self.l0_travel_scale, self.l0_travel_slider, self.l0_travel_text))
        self.global_travel_scale.trace_add("write", lambda *_args: self._sync_travel_slider(self.global_travel_scale, self.global_travel_slider, self.global_travel_text))
        self.show_more_settings.trace_add("write", lambda *_args: self._refresh_more_settings())
        for axis in SIX_AXES:
            self.axis_min_vars[axis].trace_add("write", lambda *_args, axis_name=axis: self._refresh_axis_limit_text(axis_name))
            self.axis_max_vars[axis].trace_add("write", lambda *_args, axis_name=axis: self._refresh_axis_limit_text(axis_name))

    def _install_config_autosave(self) -> None:
        for variable in self._config_variables():
            variable.trace_add("write", lambda *_args: self._schedule_config_save())

    def _config_variables(self) -> list[tk.Variable]:
        variables: list[tk.Variable] = [
            self.x,
            self.y,
            self.width,
            self.height,
            self.fps,
            self.source_mode,
            self.video_path,
            self.output_mode,
            self.audio_mode,
            self.audio_gain,
            self.audio_threshold,
            self.audio_smoothing,
            self.audio_device,
            self.smoothing,
            self.enable_smoothing,
            self.deadzone,
            self.enable_deadzone,
            self.enable_l0_jitter_guard,
            self.l0_guard_strength,
            self.enable_extreme_reset,
            self.extreme_hold_ms,
            self.enable_endpoint_guard,
            self.endpoint_margin_pct,
            self.pose_l0_analysis,
            self.pose_six_axis_analysis,
            self.pose_l0_weight,
            self.pose_six_axis_weight,
            self.tracker_mode,
            self.response_curve,
            self.motion_gain,
            self.visual_stroke_scale,
            self.compression_latency,
            self.l0_travel_scale,
            self.global_travel_scale,
            self.play_preset_level,
            self.six_axis_intensity,
            self.six_axis_jitter_reduction,
            self.six_axis_sensitivity_level,
            self.show_more_settings,
            self.min_activity,
            self.enable_activity_gate,
            self.max_step,
            self.enable_speed_limit,
            self.idle_mode,
            self.invert,
            self.enable_startup_ramp,
            self.startup_ramp_ms,
            self.axis,
            self.interval_ms,
            self.sink_type,
            self.serial_port,
            self.baudrate,
            self.ble_name,
            self.ble_address,
            self.ble_service_uuid,
            self.ble_write_uuid,
            self.measure_axis,
            self.measure_value,
            self.measure_live,
        ]
        variables.extend(self.axis_min_vars.values())
        variables.extend(self.axis_max_vars.values())
        variables.extend(self.six_axis_gain_vars.values())
        variables.extend(self.six_axis_invert_vars.values())
        return variables

    def _schedule_config_save(self) -> None:
        if self._config_autosave_suspended:
            return
        if self._config_save_after_id is not None:
            try:
                self.after_cancel(self._config_save_after_id)
            except tk.TclError:
                pass
        self._config_save_after_id = self.after(650, self._autosave_config)

    def _autosave_config(self) -> None:
        self._config_save_after_id = None
        if self._config_autosave_suspended:
            return
        self._save_config()

    def _build_ui(self) -> None:
        self._configure_style()
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        sidebar_shell = ttk.Frame(self)
        sidebar_shell.grid(row=0, column=0, sticky="ns")
        sidebar_shell.rowconfigure(0, weight=1)
        sidebar_shell.columnconfigure(0, weight=1)
        sidebar_canvas = tk.Canvas(sidebar_shell, width=340, highlightthickness=0)
        sidebar_scrollbar = ttk.Scrollbar(sidebar_shell, orient="vertical", command=sidebar_canvas.yview)
        sidebar_canvas.configure(yscrollcommand=sidebar_scrollbar.set)
        sidebar_canvas.grid(row=0, column=0, sticky="ns")
        sidebar_scrollbar.grid(row=0, column=1, sticky="ns")
        sidebar = ttk.Frame(sidebar_canvas, padding=12)
        sidebar_window = sidebar_canvas.create_window((0, 0), window=sidebar, anchor="nw")
        sidebar.columnconfigure(1, weight=1)

        def update_scroll_region(_event: tk.Event) -> None:
            sidebar_canvas.configure(scrollregion=sidebar_canvas.bbox("all"))

        def update_sidebar_width(event: tk.Event) -> None:
            sidebar_canvas.itemconfigure(sidebar_window, width=event.width)

        def on_mousewheel(event: tk.Event) -> None:
            sidebar_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        sidebar.bind("<Configure>", update_scroll_region)
        sidebar_canvas.bind("<Configure>", update_sidebar_width)
        sidebar_canvas.bind("<Enter>", lambda _event: sidebar_canvas.bind_all("<MouseWheel>", on_mousewheel))
        sidebar_canvas.bind("<Leave>", lambda _event: sidebar_canvas.unbind_all("<MouseWheel>"))

        preview = ttk.Frame(self, padding=(0, 12, 12, 12))
        preview.grid(row=0, column=1, sticky="nsew")
        preview.rowconfigure(1, weight=1, minsize=420)
        preview.columnconfigure(0, weight=1, minsize=650)

        monitor = ttk.Frame(preview, padding=10)
        monitor.grid(row=0, column=0, sticky="ew")
        monitor.columnconfigure(0, weight=0)
        monitor.columnconfigure(1, weight=1)
        monitor.columnconfigure(2, weight=0)
        preset_bar = ttk.Frame(monitor)
        preset_bar.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        preset_bar.columnconfigure(6, weight=1)
        ttk.Label(preset_bar, text="五档预设", font=("", 10, "bold")).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.preset_buttons: dict[int, ttk.Button] = {}
        for level in range(1, 6):
            button = ttk.Button(preset_bar, text=str(level), width=4, command=lambda selected=level: self.apply_play_preset(selected))
            button.grid(row=0, column=level, sticky="w", padx=(0, 4))
            self.preset_buttons[level] = button
        ttk.Label(preset_bar, text="1 慢玩  ·  5 刺激", foreground="#555").grid(row=0, column=6, sticky="w", padx=(4, 0))

        self.stroke_canvas = tk.Canvas(monitor, width=72, height=176, highlightthickness=0, background="#f4f4f4")
        self.stroke_canvas.grid(row=1, column=0, rowspan=4, sticky="nsw", padx=(0, 12))
        ttk.Label(monitor, textvariable=self.l0_status, font=("", 30, "bold")).grid(row=1, column=1, sticky="w")
        ttk.Label(monitor, textvariable=self.stroke_status, font=("", 15, "bold"), foreground="#0b6b3a").grid(row=2, column=1, sticky="w")
        ttk.Label(monitor, textvariable=self.range_status, font=("", 12)).grid(row=3, column=1, sticky="w")
        ttk.Label(monitor, textvariable=self.activity, font=("", 12)).grid(row=4, column=1, sticky="w")
        ttk.Button(monitor, text="急停回中", command=self.estop, style="Danger.TButton").grid(row=1, column=2, sticky="ew")
        ttk.Button(monitor, text="全行程", command=self.apply_full_preset, style="Primary.TButton").grid(row=2, column=2, sticky="ew", pady=4)
        ttk.Button(monitor, text="连接并回中", command=self.connect_and_center).grid(row=3, column=2, sticky="ew")
        self.axis_canvas = tk.Canvas(monitor, width=520, height=136, highlightthickness=0, background="#f8f8f8")
        self.axis_canvas.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self.curve_canvas = tk.Canvas(monitor, width=520, height=150, highlightthickness=0, background="#101418")
        self.curve_canvas.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        self.curve_canvas.bind("<Configure>", lambda _event: self._draw_script_curve())

        self.preview_canvas = tk.Canvas(
            preview,
            width=650,
            height=420,
            highlightthickness=0,
            background="#0f1115",
        )
        self.preview_canvas.grid(row=1, column=0, sticky="nsew")
        self.preview_canvas.bind("<Configure>", lambda _event: self._redraw_preview_image())
        stats = ttk.Frame(preview)
        stats.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        stats.columnconfigure((0, 1, 2), weight=1)
        ttk.Label(stats, textvariable=self.device_status).grid(row=0, column=0, sticky="w")
        ttk.Label(stats, textvariable=self.output_value, anchor="center").grid(row=0, column=1, sticky="ew")
        ttk.Label(stats, textvariable=self.record_status, anchor="e").grid(row=0, column=2, sticky="e")
        ttk.Label(preview, textvariable=self.status, foreground="#555").grid(row=3, column=0, sticky="ew", pady=(4, 0))

        row = 0
        row = self._connection_controls(sidebar, row)
        row = self._quick_controls(sidebar, row)
        row = self._axis_limit_controls(sidebar, row)
        row = self._more_settings_controls(sidebar, row)
        ttk.Label(
            sidebar,
            text="实时输出由下限/上限滑块决定。想要更大更快，点全行程。",
            wraplength=300,
            foreground="#555",
        ).grid(row=row, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        self._refresh_limit_text()
        self._refresh_play_preset_buttons()
        self._refresh_six_axis_sensitivity_buttons()
        self._draw_stroke_monitor(5000)
        self._draw_axis_monitor(self._last_axis_values)
        self._draw_script_curve()
        self._install_tooltips(self)
        self._localize_widget_tree(self)

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Primary.TButton", font=("", 10, "bold"))
        style.configure("Danger.TButton", font=("", 10, "bold"))
        style.configure("PresetActive.TButton", font=("", 10, "bold"))

    def _section(self, parent: ttk.Frame, title: str, row: int) -> int:
        ttk.Label(parent, text=title, font=("", 10, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(0 if row == 0 else 14, 6)
        )
        return row + 1

    def _entry(self, parent: ttk.Frame, label: str, var: tk.Variable, row: int, width: int = 8) -> int:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        ttk.Entry(parent, textvariable=var, width=width).grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
        return row + 1

    def _slider(
        self,
        parent: ttk.Frame,
        label: str,
        var: tk.Variable,
        row: int,
        from_: float,
        to: float,
        value_text: tk.StringVar | None = None,
    ) -> int:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        ttk.Scale(parent, from_=from_, to=to, variable=var, command=lambda _value: self._refresh_limit_text()).grid(
            row=row, column=1, sticky="ew", pady=2
        )
        if value_text is not None:
            ttk.Label(parent, textvariable=value_text, width=6, anchor="e").grid(row=row, column=2, sticky="e")
        else:
            ttk.Label(parent, textvariable=var, width=6, anchor="e").grid(row=row, column=2, sticky="e")
        return row + 1

    def _travel_slider(
        self,
        parent: ttk.Frame,
        label: str,
        value_var: tk.DoubleVar,
        slider_var: tk.DoubleVar,
        text_var: tk.StringVar,
        row: int,
    ) -> int:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        ttk.Scale(
            parent,
            from_=0.0,
            to=100.0,
            variable=slider_var,
            command=lambda value, target=value_var, text=text_var: self._on_travel_slider(value, target, text),
        ).grid(row=row, column=1, sticky="ew", pady=2)
        ttk.Label(parent, textvariable=text_var, width=6, anchor="e").grid(row=row, column=2, sticky="e")
        return row + 1

    @staticmethod
    def _travel_slider_to_scale(position: float) -> float:
        position = max(0.0, min(100.0, float(position)))
        if position <= 60.0:
            return position / 60.0
        if position <= 85.0:
            return 1.0 + (position - 60.0) / 25.0 * 0.5
        if position <= 95.0:
            return 1.5 + (position - 85.0) / 10.0 * 0.25
        return 1.75 + (position - 95.0) / 5.0 * 1.25

    @staticmethod
    def _travel_scale_to_slider(scale: float) -> float:
        scale = max(0.0, min(3.0, float(scale)))
        if scale <= 1.0:
            return scale * 60.0
        if scale <= 1.5:
            return 60.0 + (scale - 1.0) / 0.5 * 25.0
        if scale <= 1.75:
            return 85.0 + (scale - 1.5) / 0.25 * 10.0
        return 95.0 + (scale - 1.75) / 1.25 * 5.0

    @staticmethod
    def _format_travel_scale(scale: float) -> str:
        return f"{max(0.0, min(3.0, float(scale))):.2f}x"

    def _on_travel_slider(self, value: str | float, target: tk.DoubleVar, text: tk.StringVar) -> None:
        if self._travel_slider_syncing:
            return
        scale = self._travel_slider_to_scale(float(value))
        target.set(round(scale, 3))
        text.set(self._format_travel_scale(scale))
        self._refresh_limit_text()

    def _sync_travel_slider(self, value_var: tk.DoubleVar, slider_var: tk.DoubleVar, text_var: tk.StringVar) -> None:
        if self._travel_slider_syncing:
            return
        self._travel_slider_syncing = True
        try:
            scale = max(0.0, min(3.0, float(value_var.get())))
            slider_var.set(self._travel_scale_to_slider(scale))
            text_var.set(self._format_travel_scale(scale))
        finally:
            self._travel_slider_syncing = False

    def _more_settings_controls(self, parent: ttk.Frame, row: int) -> int:
        self.more_settings_button = ttk.Button(parent, command=self._toggle_more_settings)
        self.more_settings_button.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        row += 1
        self.more_settings_frame = ttk.Frame(parent)
        self.more_settings_frame.columnconfigure(1, weight=1)
        inner_row = 0
        inner_row = self._source_controls(self.more_settings_frame, inner_row)
        inner_row = self._audio_controls(self.more_settings_frame, inner_row)
        inner_row = self._region_controls(self.more_settings_frame, inner_row)
        inner_row = self._tracking_controls(self.more_settings_frame, inner_row)
        self._refresh_more_settings()
        return row + 1

    def _toggle_more_settings(self) -> None:
        self.show_more_settings.set(not self.show_more_settings.get())
        self._refresh_more_settings()

    def _refresh_more_settings(self) -> None:
        if not hasattr(self, "more_settings_button") or not hasattr(self, "more_settings_frame"):
            return
        expanded = self.show_more_settings.get()
        self.more_settings_button.configure(text=self._t("收起更多设置" if expanded else "展开更多设置"))
        if expanded:
            self.more_settings_frame.grid(row=int(self.more_settings_button.grid_info()["row"]) + 1, column=0, columnspan=3, sticky="ew")
        else:
            self.more_settings_frame.grid_remove()

    def _install_tooltips(self, widget: tk.Widget) -> None:
        try:
            text = str(widget.cget("text")).strip()
        except tk.TclError:
            text = ""
        tooltip_key = UI_TEXT_REVERSE_EN.get(text, text)
        tooltip_text = TOOLTIPS_EN.get(tooltip_key) if self.ui_language == "en" else TOOLTIPS.get(tooltip_key)
        if tooltip_text:
            Tooltip(widget, tooltip_text)
        for child in widget.winfo_children():
            self._install_tooltips(child)

    def _localize_widget_tree(self, widget: tk.Widget) -> None:
        if self.ui_language != "en":
            return
        try:
            text = str(widget.cget("text"))
            translated = self._t(text)
            if translated != text:
                widget.configure(text=translated)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._localize_widget_tree(child)

    def _region_controls(self, parent: ttk.Frame, row: int) -> int:
        row = self._section(parent, "屏幕区域", row)
        row = self._entry(parent, "X", self.x, row)
        row = self._entry(parent, "Y", self.y, row)
        row = self._entry(parent, "宽", self.width, row)
        row = self._entry(parent, "高", self.height, row)
        ttk.Button(parent, text="框选区域", command=self.pick_region).grid(row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        return row + 1

    def _source_controls(self, parent: ttk.Frame, row: int) -> int:
        row = self._section(parent, "输入来源", row)
        ttk.Label(parent, text="来源").grid(row=row, column=0, sticky="w", pady=2)
        ttk.Combobox(
            parent,
            textvariable=self.source_mode,
            values=("Screen", "Video File", "Audio Only"),
            state="readonly",
            width=12,
        ).grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
        row += 1
        ttk.Label(parent, text="视频").grid(row=row, column=0, sticky="w", pady=2)
        ttk.Entry(parent, textvariable=self.video_path, width=18).grid(row=row, column=1, sticky="ew", pady=2)
        ttk.Button(parent, text="选择", command=self.pick_video).grid(row=row, column=2, sticky="ew", padx=(4, 0))
        row += 1
        ttk.Button(parent, text="分析视频并保存脚本", command=self.analyze_video_file).grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0)
        )
        return row + 1

    def _audio_controls(self, parent: ttk.Frame, row: int) -> int:
        row = self._section(parent, "声音监听（PMV）", row)
        ttk.Label(parent, text="声音分析").grid(row=row, column=0, sticky="w", pady=2)
        ttk.Combobox(
            parent,
            textvariable=self.audio_mode,
            values=("Audio Level", "Dynamic Accent", "Beat Pulse"),
            state="readonly",
            width=14,
        ).grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
        row += 1
        ttk.Label(parent, text="声音设备").grid(row=row, column=0, sticky="w", pady=2)
        self.audio_device_combo = ttk.Combobox(parent, textvariable=self.audio_device, values=(), width=14)
        self.audio_device_combo.grid(row=row, column=1, sticky="ew", pady=2)
        ttk.Button(parent, text="刷新", command=self.refresh_audio_devices).grid(row=row, column=2, sticky="ew", padx=(4, 0))
        row += 1
        row = self._slider(parent, "声音增益", self.audio_gain, row, 0.2, 8.0)
        row = self._slider(parent, "声音门槛", self.audio_threshold, row, 0.0, 0.35)
        row = self._slider(parent, "声音平滑", self.audio_smoothing, row, 0.0, 0.95)
        ttk.Label(
            parent,
            text="选择 Audio Only 后只监听声音，不读取屏幕画面。系统输出回环适合播放 PMV。",
            wraplength=300,
            foreground="#555",
        ).grid(row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        return row + 1

    def _tracking_controls(self, parent: ttk.Frame, row: int) -> int:
        row = self._section(parent, "高级参数", row)
        ttk.Label(parent, text="输出模式").grid(row=row, column=0, sticky="w", pady=2)
        ttk.Combobox(
            parent,
            textvariable=self.output_mode,
            values=("L0 Only", "Six Axis"),
            state="readonly",
            width=12,
        ).grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
        row += 1
        ttk.Label(parent, text="分析模式").grid(row=row, column=0, sticky="w", pady=2)
        ttk.Combobox(
            parent,
            textvariable=self.tracker_mode,
            values=self._tracker_choices(),
            state="readonly",
            width=12,
        ).grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
        row += 1
        row = self._entry(parent, "FPS", self.fps, row)
        row = self._entry(parent, "间隔 ms", self.interval_ms, row)
        ttk.Checkbutton(parent, text="启用每帧限速", variable=self.enable_speed_limit).grid(row=row, column=0, columnspan=3, sticky="w", pady=2)
        row += 1
        row = self._entry(parent, "限速值", self.max_step, row)
        ttk.Checkbutton(parent, text="启用平滑曲线", variable=self.enable_smoothing).grid(row=row, column=0, columnspan=3, sticky="w", pady=2)
        row += 1
        ttk.Label(parent, text="平滑").grid(row=row, column=0, sticky="w", pady=2)
        ttk.Scale(parent, from_=0.0, to=0.95, variable=self.smoothing).grid(row=row, column=1, columnspan=2, sticky="ew")
        row += 1
        ttk.Checkbutton(parent, text="启用死区滤波", variable=self.enable_deadzone).grid(row=row, column=0, columnspan=3, sticky="w", pady=2)
        row += 1
        ttk.Label(parent, text="死区").grid(row=row, column=0, sticky="w", pady=2)
        ttk.Scale(parent, from_=0.0, to=0.12, variable=self.deadzone).grid(row=row, column=1, columnspan=2, sticky="ew")
        row += 1
        ttk.Checkbutton(parent, text="启用 L0 防抽搐", variable=self.enable_l0_jitter_guard).grid(row=row, column=0, columnspan=3, sticky="w", pady=2)
        row += 1
        ttk.Label(parent, text="L0 防抖").grid(row=row, column=0, sticky="w", pady=2)
        ttk.Scale(parent, from_=0.0, to=1.0, variable=self.l0_guard_strength).grid(row=row, column=1, columnspan=2, sticky="ew")
        row += 1
        ttk.Checkbutton(parent, text="极端位自动复位", variable=self.enable_extreme_reset).grid(row=row, column=0, columnspan=3, sticky="w", pady=2)
        row += 1
        row = self._entry(parent, "极端停留 ms", self.extreme_hold_ms, row)
        ttk.Checkbutton(parent, text="端点保护", variable=self.enable_endpoint_guard).grid(row=row, column=0, columnspan=3, sticky="w", pady=2)
        row += 1
        row = self._entry(parent, "端点留白 %", self.endpoint_margin_pct, row)
        ttk.Checkbutton(parent, text="启用活动门控", variable=self.enable_activity_gate).grid(row=row, column=0, columnspan=3, sticky="w", pady=2)
        row += 1
        ttk.Label(parent, text="活动阈值").grid(row=row, column=0, sticky="w", pady=2)
        ttk.Scale(parent, from_=0.0, to=0.04, variable=self.min_activity).grid(row=row, column=1, columnspan=2, sticky="ew")
        row += 1
        ttk.Label(parent, text="增益").grid(row=row, column=0, sticky="w", pady=2)
        ttk.Scale(parent, from_=0.2, to=4.0, variable=self.motion_gain).grid(row=row, column=1, columnspan=2, sticky="ew")
        row += 1
        ttk.Label(parent, text="视觉行程").grid(row=row, column=0, sticky="w", pady=2)
        ttk.Scale(parent, from_=0.35, to=1.2, variable=self.visual_stroke_scale).grid(row=row, column=1, columnspan=2, sticky="ew")
        row += 1
        ttk.Label(parent, text="压缩延迟").grid(row=row, column=0, sticky="w", pady=2)
        ttk.Scale(parent, from_=-5, to=5, variable=self.compression_latency).grid(row=row, column=1, sticky="ew", pady=2)
        ttk.Label(parent, textvariable=self.compression_latency, width=6, anchor="e").grid(row=row, column=2, sticky="e")
        row += 1
        ttk.Label(parent, text="-5 最准确 / 0 默认 / 5 延迟最低", wraplength=300, foreground="#555").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(0, 4)
        )
        row += 1
        ttk.Label(parent, text="响应曲线").grid(row=row, column=0, sticky="w", pady=2)
        ttk.Combobox(
            parent,
            textvariable=self.response_curve,
            values=("Linear", "Soft", "Sharp", "Ease In"),
            state="readonly",
            width=10,
        ).grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
        row += 1
        ttk.Label(parent, text="空闲").grid(row=row, column=0, sticky="w", pady=2)
        ttk.Combobox(
            parent,
            textvariable=self.idle_mode,
            values=("Hold", "Center"),
            state="readonly",
            width=10,
        ).grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
        row += 1
        ttk.Checkbutton(parent, text="启用启动渐入", variable=self.enable_startup_ramp).grid(row=row, column=0, columnspan=3, sticky="w", pady=2)
        row += 1
        row = self._entry(parent, "渐入 ms", self.startup_ramp_ms, row)
        ttk.Checkbutton(parent, text="反向", variable=self.invert).grid(row=row, column=0, columnspan=3, sticky="w", pady=2)
        row += 1
        ttk.Button(parent, text="一键稳态 L0", command=self.apply_stable_l0_preset, style="Primary.TButton").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0)
        )
        return row + 1

    def _connection_controls(self, parent: ttk.Frame, row: int) -> int:
        row = self._section(parent, "连接设备", row)
        ttk.Label(parent, textvariable=self.device_status, foreground="#0b6b3a").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(0, 4)
        )
        row += 1
        ttk.Label(parent, text="输出").grid(row=row, column=0, sticky="w", pady=2)
        ttk.Combobox(
            parent,
            textvariable=self.sink_type,
            values=("Log only", "Serial COM", "BLE UART"),
            state="readonly",
            width=14,
        ).grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
        row += 1

        ttk.Label(parent, text="串口").grid(row=row, column=0, sticky="w", pady=2)
        self.port_combo = ttk.Combobox(parent, textvariable=self.serial_port, values=(), width=14)
        self.port_combo.grid(row=row, column=1, sticky="ew", pady=2)
        ttk.Button(parent, text="刷新", command=self.refresh_ports).grid(row=row, column=2, sticky="ew", padx=(4, 0))
        row += 1
        row = self._entry(parent, "波特率", self.baudrate, row)
        ttk.Button(parent, text="自动检测 OSR6", command=self.autodetect_device).grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0)
        )
        row += 1

        ttk.Label(parent, text="BLE 名称").grid(row=row, column=0, sticky="w", pady=2)
        ttk.Entry(parent, textvariable=self.ble_name).grid(row=row, column=1, sticky="ew", pady=2)
        ttk.Button(parent, text="扫描", command=self.scan_ble).grid(row=row, column=2, sticky="ew", padx=(4, 0))
        row += 1
        row = self._entry(parent, "BLE 地址", self.ble_address, row, width=18)
        row = self._entry(parent, "写入 UUID", self.ble_write_uuid, row, width=18)
        ttk.Button(parent, text="连接并回中", command=self.connect_and_center, style="Primary.TButton").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(4, 0)
        )
        ttk.Button(parent, text="断开", command=self.disconnect_sink).grid(row=row, column=2, sticky="ew", padx=(4, 0), pady=(4, 0))
        row += 1
        ttk.Button(parent, text="查询设备轴", command=self.query_device_axes).grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0)
        )
        return row + 1

    def _quick_controls(self, parent: ttk.Frame, row: int) -> int:
        row = self._section(parent, "实时输出", row)
        row = self._slider(parent, "下限", self.min_value, row, 0, 9999)
        row = self._slider(parent, "上限", self.max_value, row, 0, 9999)
        ttk.Label(parent, text="速度").grid(row=row, column=0, sticky="w", pady=2)
        ttk.Scale(parent, from_=100, to=9999, variable=self.max_step).grid(row=row, column=1, sticky="ew", pady=2)
        ttk.Label(parent, textvariable=self.max_step, width=6, anchor="e").grid(row=row, column=2, sticky="e")
        row += 1
        ttk.Button(parent, text="居中", command=self.send_center).grid(row=row, column=0, sticky="ew")
        ttk.Button(parent, text="中等测试", command=self.send_small_test).grid(row=row, column=1, columnspan=2, sticky="ew", padx=(4, 0))
        row += 1
        ttk.Button(parent, text="上下全幅测试", command=self.send_full_l0_test).grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0)
        )
        row += 1
        ttk.Button(parent, text="OSR6 六轴轻测", command=self.send_six_axis_test).grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0)
        )
        row += 1
        ttk.Button(parent, text="恢复所有默认设置", command=self.reset_all_settings).grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0)
        )
        row += 1
        ttk.Button(parent, text="开始实时输出", command=self.start).grid(row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        row += 1
        self.preview_button = ttk.Button(parent, text="显示预览", command=self.toggle_preview)
        self.preview_button.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        row += 1
        ttk.Button(parent, text="停止", command=self.stop).grid(row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        row += 1
        ttk.Button(parent, text="急停回中", command=self.estop, style="Danger.TButton").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0)
        )
        row += 1
        ttk.Button(parent, text="安全预设", command=self.apply_safe_preset).grid(row=row, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(parent, text="标准预设", command=self.apply_normal_preset).grid(row=row, column=1, sticky="ew", padx=(4, 0), pady=(8, 0))
        ttk.Button(parent, text="全行程", command=self.apply_full_preset).grid(row=row, column=2, sticky="ew", padx=(4, 0), pady=(8, 0))
        row += 1
        ttk.Button(parent, text="混合分析灵敏", command=self.apply_hybrid_analysis_preset, style="Primary.TButton").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0)
        )
        row += 1
        ttk.Button(parent, text="开始录制", command=self.start_recording).grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(parent, text="保存脚本", command=self.save_recording).grid(row=row, column=2, sticky="ew", padx=(4, 0), pady=(8, 0))
        return row + 1

    def _axis_limit_controls(self, parent: ttk.Frame, row: int) -> int:
        row = self._section(parent, "六轴独立上下限", row)
        row = self._travel_slider(parent, "L0 总行程倍率", self.l0_travel_scale, self.l0_travel_slider, self.l0_travel_text, row)
        row = self._travel_slider(parent, "六轴总行程倍率", self.global_travel_scale, self.global_travel_slider, self.global_travel_text, row)
        pose_box = ttk.LabelFrame(parent, text="Pose 倾向", padding=8)
        pose_box.columnconfigure(1, weight=1)
        ttk.Checkbutton(pose_box, text="Pose 倾向 L0", variable=self.pose_l0_analysis).grid(row=0, column=0, columnspan=3, sticky="w", pady=2)
        ttk.Label(pose_box, text="Pose L0 权重").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Scale(pose_box, from_=0, to=100, variable=self.pose_l0_weight).grid(row=1, column=1, sticky="ew", pady=2)
        ttk.Label(pose_box, textvariable=self.pose_l0_weight, width=4, anchor="e").grid(row=1, column=2, sticky="e")
        ttk.Checkbutton(pose_box, text="Pose 倾向六轴", variable=self.pose_six_axis_analysis).grid(row=2, column=0, columnspan=3, sticky="w", pady=(5, 2))
        ttk.Label(pose_box, text="Pose 六轴权重").grid(row=3, column=0, sticky="w", pady=2)
        ttk.Scale(pose_box, from_=0, to=100, variable=self.pose_six_axis_weight).grid(row=3, column=1, sticky="ew", pady=2)
        ttk.Label(pose_box, textvariable=self.pose_six_axis_weight, width=4, anchor="e").grid(row=3, column=2, sticky="e")
        pose_box.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        row += 1
        row = self._measurement_controls(parent, row)
        row = self._six_axis_tuning_controls(parent, row)
        ttk.Label(parent, text="轴").grid(row=row, column=0, sticky="w")
        ttk.Label(parent, text="下限").grid(row=row, column=1, sticky="w")
        ttk.Label(parent, text="上限").grid(row=row, column=2, sticky="w")
        row += 1
        for axis in SIX_AXES:
            line = ttk.Frame(parent)
            line.columnconfigure(1, weight=1)
            line.columnconfigure(3, weight=1)
            ttk.Label(line, text=axis, width=4).grid(row=0, column=0, sticky="w")
            ttk.Scale(
                line,
                from_=0,
                to=9999,
                variable=self.axis_min_vars[axis],
                command=lambda _value, axis_name=axis: self._normalize_axis_limit(axis_name),
            ).grid(row=0, column=1, sticky="ew", padx=(2, 3))
            ttk.Label(line, textvariable=self.axis_min_vars[axis], width=5, anchor="e").grid(row=0, column=2, sticky="e")
            ttk.Scale(
                line,
                from_=0,
                to=9999,
                variable=self.axis_max_vars[axis],
                command=lambda _value, axis_name=axis: self._normalize_axis_limit(axis_name),
            ).grid(row=0, column=3, sticky="ew", padx=(8, 3))
            ttk.Label(line, textvariable=self.axis_max_vars[axis], width=5, anchor="e").grid(row=0, column=4, sticky="e")
            line.grid(row=row, column=0, columnspan=3, sticky="ew", pady=1)
            row += 1
        ttk.Label(
            parent,
            text="实时输出与测试会按每个轴自己的范围映射。滑块交叉时会自动整理。",
            wraplength=300,
            foreground="#555",
        ).grid(row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        return row + 1

    def _measurement_controls(self, parent: ttk.Frame, row: int) -> int:
        box = ttk.LabelFrame(parent, text="测量模式", padding=8)
        box.columnconfigure(1, weight=1)
        ttk.Label(box, text="轴").grid(row=0, column=0, sticky="w", pady=2)
        axis_combo = ttk.Combobox(
            box,
            textvariable=self.measure_axis,
            values=SIX_AXES,
            state="readonly",
            width=6,
        )
        axis_combo.grid(row=0, column=1, sticky="ew", pady=2)
        axis_combo.bind("<<ComboboxSelected>>", lambda _event: self._sync_measure_value_from_axis())
        ttk.Checkbutton(box, text="滑动即发送", variable=self.measure_live).grid(row=0, column=2, sticky="e", padx=(6, 0))
        ttk.Label(box, text="位置").grid(row=1, column=0, sticky="w", pady=2)
        measure_scale = ttk.Scale(
            box,
            from_=0,
            to=9999,
            variable=self.measure_value,
            command=lambda _value: self._on_measure_slider(),
        )
        measure_scale.grid(row=1, column=1, sticky="ew", pady=2)
        ttk.Label(box, textvariable=self.measure_value, width=5, anchor="e").grid(row=1, column=2, sticky="e")
        ttk.Button(box, text="发送当前位置", command=self.send_measure_position).grid(row=2, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        button_row = ttk.Frame(box)
        button_row.columnconfigure((0, 1, 2), weight=1)
        ttk.Button(button_row, text="保存为下限", command=lambda: self.save_measure_limit("low")).grid(row=0, column=0, sticky="ew")
        ttk.Button(button_row, text="当前轴回中", command=lambda: self.send_measure_position(5000)).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(button_row, text="保存为上限", command=lambda: self.save_measure_limit("high")).grid(row=0, column=2, sticky="ew")
        button_row.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        ttk.Label(
            box,
            text="用于找机械安全范围：先低档、慢慢滑，确认位置后保存上下限。",
            wraplength=270,
            foreground="#555",
        ).grid(row=4, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        box.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(6, 8))
        return row + 1

    def _six_axis_tuning_controls(self, parent: ttk.Frame, row: int) -> int:
        box = ttk.LabelFrame(parent, text="六轴辅助调节（不影响 L0）", padding=8)
        box.columnconfigure(1, weight=1)
        ttk.Label(box, text="总强度").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Scale(box, from_=0, to=180, variable=self.six_axis_intensity).grid(row=0, column=1, sticky="ew", pady=2)
        ttk.Label(box, textvariable=self.six_axis_intensity, width=4, anchor="e").grid(row=0, column=2, sticky="e")
        row_i = 1
        ttk.Label(box, text="六轴降抖").grid(row=row_i, column=0, sticky="w", pady=2)
        ttk.Scale(box, from_=0, to=100, variable=self.six_axis_jitter_reduction).grid(row=row_i, column=1, sticky="ew", pady=2)
        ttk.Label(box, textvariable=self.six_axis_jitter_reduction, width=4, anchor="e").grid(row=row_i, column=2, sticky="e")
        row_i += 1
        ttk.Button(box, text="一键稳六轴", command=self.apply_stable_six_axis_preset, style="Primary.TButton").grid(
            row=row_i, column=0, columnspan=3, sticky="ew", pady=(2, 5)
        )
        row_i += 1
        ttk.Label(box, text="六轴敏感度").grid(row=row_i, column=0, sticky="w", pady=2)
        sensitivity_row = ttk.Frame(box)
        for column in range(5):
            sensitivity_row.columnconfigure(column, weight=1)
        for level in range(1, 11):
            row_pos = 0 if level <= 5 else 1
            col_pos = (level - 1) % 5
            button = ttk.Button(
                sensitivity_row,
                text=str(level),
                width=3,
                command=lambda selected=level: self.apply_six_axis_sensitivity(selected),
            )
            button.grid(row=row_pos, column=col_pos, sticky="ew", padx=(0 if col_pos == 0 else 3, 0), pady=(0 if row_pos == 0 else 3, 0))
            if not hasattr(self, "six_axis_sensitivity_buttons"):
                self.six_axis_sensitivity_buttons = {}
            self.six_axis_sensitivity_buttons[level] = button
        sensitivity_row.grid(row=row_i, column=1, columnspan=2, sticky="ew", pady=(2, 5))
        row_i += 1
        for axis in ("L1", "L2", "R0", "R1", "R2"):
            ttk.Label(box, text=axis, width=4).grid(row=row_i, column=0, sticky="w", pady=1)
            ttk.Scale(box, from_=0, to=200, variable=self.six_axis_gain_vars[axis]).grid(row=row_i, column=1, sticky="ew", padx=(2, 3), pady=1)
            mini = ttk.Frame(box)
            ttk.Label(mini, textvariable=self.six_axis_gain_vars[axis], width=4, anchor="e").grid(row=0, column=0, sticky="e")
            ttk.Checkbutton(mini, text="反", variable=self.six_axis_invert_vars[axis]).grid(row=0, column=1, sticky="e")
            mini.grid(row=row_i, column=2, sticky="e")
            row_i += 1
        ttk.Label(
            box,
            text="建议先把其它轴限位收窄，再逐个放大强度；L0 主轴不会被这些滑块改变。",
            wraplength=270,
            foreground="#555",
        ).grid(row=row_i, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        box.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        return row + 1

    def apply_soft_six_axis_preset(self) -> None:
        self.apply_six_axis_sensitivity(5)

    def apply_six_axis_sensitivity(self, level: int, announce: bool = True) -> None:
        presets = {
            1: {"intensity": 28, "jitter": 92, "gains": {"L1": 42, "L2": 28, "R0": 28, "R1": 18, "R2": 32}},
            2: {"intensity": 38, "jitter": 84, "gains": {"L1": 55, "L2": 38, "R0": 38, "R1": 24, "R2": 44}},
            3: {"intensity": 55, "jitter": 70, "gains": {"L1": 75, "L2": 52, "R0": 52, "R1": 34, "R2": 62}},
            4: {"intensity": 75, "jitter": 52, "gains": {"L1": 95, "L2": 72, "R0": 72, "R1": 46, "R2": 84}},
            5: {"intensity": 100, "jitter": 32, "gains": {"L1": 120, "L2": 92, "R0": 92, "R1": 62, "R2": 110}},
            6: {"intensity": 115, "jitter": 24, "gains": {"L1": 135, "L2": 108, "R0": 108, "R1": 72, "R2": 125}},
            7: {"intensity": 130, "jitter": 18, "gains": {"L1": 150, "L2": 124, "R0": 124, "R1": 84, "R2": 142}},
            8: {"intensity": 145, "jitter": 12, "gains": {"L1": 166, "L2": 140, "R0": 140, "R1": 96, "R2": 160}},
            9: {"intensity": 160, "jitter": 7, "gains": {"L1": 184, "L2": 162, "R0": 162, "R1": 112, "R2": 182}},
            10: {"intensity": 180, "jitter": 2, "gains": {"L1": 200, "L2": 190, "R0": 190, "R1": 132, "R2": 200}},
        }
        level = max(1, min(10, int(level)))
        preset = presets[level]
        self.output_mode.set("Six Axis")
        self.six_axis_intensity.set(preset["intensity"])
        self.six_axis_jitter_reduction.set(preset["jitter"])
        for axis, value in preset["gains"].items():
            self.six_axis_gain_vars[axis].set(value)
        for axis in ("L1", "L2", "R0", "R1", "R2"):
            self.six_axis_invert_vars[axis].set(False)
        self.six_axis_sensitivity_level.set(level)
        self._six_axis_stable_positions = {axis: 0.5 for axis in SIX_AXES}
        self._refresh_six_axis_sensitivity_buttons()
        if announce:
            self.status.set(f"{self._t('已应用六轴敏感度')} {level} {self._t('档')}")

    def apply_stable_six_axis_preset(self) -> None:
        self.output_mode.set("Six Axis")
        self.six_axis_intensity.set(45)
        self.six_axis_jitter_reduction.set(82)
        values = {"L1": 60, "L2": 42, "R0": 42, "R1": 25, "R2": 48}
        for axis, value in values.items():
            self.six_axis_gain_vars[axis].set(value)
        for axis in ("L1", "L2", "R0", "R1", "R2"):
            self.six_axis_invert_vars[axis].set(False)
        self._six_axis_stable_positions = {axis: 0.5 for axis in SIX_AXES}
        self.six_axis_sensitivity_level.set(1)
        self._refresh_six_axis_sensitivity_buttons()
        self.status.set(self._t("已应用稳六轴：辅助轴更低敏、更少抖"))

    def _refresh_six_axis_sensitivity_buttons(self) -> None:
        if not hasattr(self, "six_axis_sensitivity_buttons"):
            return
        active = self.six_axis_sensitivity_level.get()
        for level, button in self.six_axis_sensitivity_buttons.items():
            button.configure(style="PresetActive.TButton" if level == active else "TButton")

    def refresh_ports(self) -> None:
        infos = list_serial_port_infos()
        ports = [info.display_name for info in infos]
        self.port_combo["values"] = ports
        current_device = extract_serial_device(self.serial_port.get())
        if current_device:
            for item in ports:
                if extract_serial_device(item).upper() == current_device.upper():
                    self.serial_port.set(item)
                    break
        elif ports:
            self.serial_port.set(choose_best_serial_port(infos))

    def refresh_audio_devices(self) -> None:
        devices = list_audio_devices()
        if not hasattr(self, "audio_device_combo"):
            return
        self.audio_device_combo["values"] = devices
        if devices and self.audio_device.get() not in devices:
            self.audio_device.set(devices[0])

    @staticmethod
    def _powershell_ports() -> list[str]:
        return []

    def autodetect_device(self) -> None:
        infos = list_serial_port_infos()
        if not infos:
            self.status.set(self._t("未发现串口设备"))
            return
        selected = choose_best_serial_port(infos)
        self.sink_type.set("Serial COM")
        self.serial_port.set(selected)
        self.status.set(f"{self._t('已选择')}: {selected}")

    def scan_ble(self) -> None:
        self.status.set(self._t("BLE 扫描中..."))

        def worker() -> None:
            try:
                devices = asyncio.run(scan_ble_devices(self.ble_name.get()))
                self.frame_queue.put({"ble_devices": devices})
            except Exception as exc:
                self.frame_queue.put({"error": f"{self._t('BLE 扫描失败')}: {exc}"})

        threading.Thread(target=worker, daemon=True).start()

    def pick_video(self) -> None:
        path = filedialog.askopenfilename(
            title=self._t("选择视频文件"),
            filetypes=(
                ("Video", "*.mp4 *.mkv *.avi *.mov *.webm *.m4v"),
                ("All files", "*.*"),
            ),
        )
        if path:
            self.video_path.set(path)
            self.source_mode.set("Video File")

    def analyze_video_file(self) -> None:
        path = self.video_path.get()
        if not path:
            self.pick_video()
            path = self.video_path.get()
        if not path:
            return
        save_path = filedialog.asksaveasfilename(
            title=self._t("选择脚本保存基名"),
            defaultextension=".funscript",
            initialfile=f"{Path(path).stem}.funscript",
            filetypes=(("Funscript", "*.funscript"), ("All files", "*.*")),
        )
        if not save_path:
            return
        self.status.set(self._t("视频分析中..."))

        def worker() -> None:
            try:
                written = self._analyze_video_worker(Path(path), Path(save_path))
                self.frame_queue.put({"status_text": f"{self._t('视频分析完成')}: {len(written)} {self._t('个脚本')}"})
            except Exception as exc:
                self.frame_queue.put({"error": f"{self._t('视频分析失败')}: {exc}"})

        threading.Thread(target=worker, daemon=True).start()

    def _analyze_video_worker(self, video_path: Path, save_path: Path) -> list[Path]:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"{self._t('无法打开视频')}: {video_path}")
        self._six_axis_stable_positions = {axis: 0.5 for axis in SIX_AXES}
        analyzer = RealtimeAnalyzer(
            self._tracker_internal(self.tracker_mode.get()),
            self.output_mode.get(),
            self.smoothing.get(),
            self.deadzone.get(),
            self.motion_gain.get(),
            self.enable_smoothing.get(),
            self.enable_deadzone.get(),
            self.response_curve.get(),
            self.visual_stroke_scale.get(),
            self.enable_l0_jitter_guard.get(),
            self.l0_guard_strength.get(),
            self.enable_extreme_reset.get(),
            self.enable_endpoint_guard.get(),
            self.endpoint_margin_pct.get() / 200.0,
            False,
            self.pose_l0_analysis.get(),
            self.pose_six_axis_analysis.get(),
            self.pose_l0_weight.get() / 100.0,
            self.pose_six_axis_weight.get() / 100.0,
        )
        recorder = MultiAxisFunscriptRecorder()
        recorder.start()
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        native_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        target_fps = max(1, min(60, self.fps.get()))
        frame_step = max(1, round(native_fps / target_fps))
        index = 0
        last_update = 0.0
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                if index % frame_step != 0:
                    index += 1
                    continue
                result = analyzer.process(frame)
                positions = self._apply_six_axis_tuning(result.positions)
                at = int(cap.get(cv2.CAP_PROP_POS_MSEC))
                if at <= 0:
                    at = round(index / native_fps * 1000)
                recorder.add_at(positions, at)
                now = time.perf_counter()
                if now - last_update > 0.25:
                    progress = f"{index}/{total}" if total else str(index)
                    self._queue_latest(
                        {
                            "preview": result.preview_bgr,
                            "status_text": f"{self._t('视频分析中...')} {progress}",
                            "record_count": recorder.action_count,
                        }
                    )
                    last_update = now
                index += 1
        finally:
            cap.release()
        recorder.stop()
        return recorder.save(save_path)

    def connect_sink(self) -> None:
        self.disconnect_sink()
        kind = self.sink_type.get()
        try:
            if kind in ("USB Serial", "Serial COM"):
                self.sink = SerialSink(extract_serial_device(self.serial_port.get()), self.baudrate.get())
            elif kind == "BLE UART":
                self.sink = BleSink(self.ble_address.get(), self.ble_write_uuid.get())
            else:
                self.sink = LogSink()
            self.sink.open()
            self.connected = True
            self.status.set(f"{self._t('已连接')}: {kind}")
            if kind in ("USB Serial", "Serial COM"):
                self.device_status.set(f"{self._t('设备')}: {self._t('已连接')} {extract_serial_device(self.serial_port.get())}")
            elif kind == "BLE UART":
                self.device_status.set(f"{self._t('设备')}: {self._t('已连接')} BLE {self.ble_address.get()}")
            else:
                self.device_status.set(f"{self._t('设备')}: {self._t('日志模式')}")
            self._save_config()
        except Exception as exc:
            self.sink = LogSink()
            self.connected = False
            self.device_status.set(f"{self._t('设备')}: {self._t('连接失败')}")
            self.status.set(self._t("连接失败"))
            messagebox.showerror(self._t("连接失败"), str(exc))

    def connect_and_center(self) -> None:
        self.connect_sink()
        if self.connected:
            self.send_center(interval_ms=600)
            self.status.set(self._t("已连接并回中"))

    def disconnect_sink(self) -> None:
        try:
            self.sink.close()
        except Exception:
            pass
        self.sink = LogSink()
        self.connected = False
        self.device_status.set(f"{self._t('设备')}: {self._t('未连接')}")
        if not self.worker:
            self.status.set(self._t("未连接"))

    def query_device_axes(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning(self._t("正在运行"), self._t("请先停止实时输出，再查询设备轴。"))
            return
        if not self.connected:
            self.connect_sink()
            if not self.connected:
                return
        if not isinstance(self.sink, SerialSink):
            messagebox.showinfo(self._t("暂不支持"), self._t("设备轴查询目前只支持 Serial COM。BLE UART 通常需要通知通道，暂时只做写入。"))
            return

        def worker() -> None:
            try:
                response = self.sink.query(b"D2\n", wait_s=0.8)
                text = response.decode("utf-8", errors="replace").strip()
                if not text:
                    text = self._t("无回复：可继续用六轴轻测，或确认固件是否支持 TCode D2 查询。")
                self._queue_latest({"status_text": f"{self._t('设备轴查询')}: {text}", "command": f"D2 -> {text}"})
            except Exception as exc:
                self._queue_latest({"error": f"{self._t('设备轴查询失败')}: {exc}"})

        threading.Thread(target=worker, daemon=True).start()

    def start(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        self.update_idletasks()
        self._startup_window_geometry = self.geometry()
        self.source_mode.set("Screen")
        if not self._confirm_realtime_start():
            self._startup_window_geometry = None
            return
        if not self.connected:
            self.connect_sink()
            if not self.connected:
                self._startup_window_geometry = None
                return
        self._normalize_limits()
        self._script_history.clear()
        self._six_axis_stable_positions = {axis: 0.5 for axis in SIX_AXES}
        self._draw_script_curve()
        self.stop_event.clear()
        self.worker = threading.Thread(target=self._run_capture, daemon=True)
        self.worker.start()
        self.status.set(self._t("实时输出中"))
        self._restore_start_geometry_once()
        self.after(180, self._release_start_geometry)

    def _restore_start_geometry_once(self) -> None:
        geometry = self._startup_window_geometry
        if geometry:
            self.geometry(geometry)

    def _release_start_geometry(self) -> None:
        self._startup_window_geometry = None

    def _confirm_realtime_start(self) -> bool:
        dialog = tk.Toplevel(self)
        dialog.title(self._t("开始实时输出前确认"))
        dialog.transient(self)
        dialog.resizable(False, False)
        dialog.grab_set()

        mode = tk.StringVar(value=self.output_mode.get() if self.output_mode.get() in ("L0 Only", "Six Axis") else "L0 Only")
        current_tracker = self._tracker_internal(self.tracker_mode.get())
        if current_tracker not in TRACKER_MODE_CHOICES:
            current_tracker = "混合分析（推荐）"
        tracker = tk.StringVar(value=self._tracker_display(current_tracker))
        pose_l0 = tk.BooleanVar(value=self.pose_l0_analysis.get())
        pose_six = tk.BooleanVar(value=self.pose_six_axis_analysis.get())
        pose_l0_weight = tk.IntVar(value=self.pose_l0_weight.get())
        pose_six_weight = tk.IntVar(value=self.pose_six_axis_weight.get())
        compression_latency = tk.IntVar(value=self.compression_latency.get())
        result = {"ok": False}

        body = ttk.Frame(dialog, padding=14)
        body.grid(row=0, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)

        ttk.Label(body, text="开始实时输出前确认", font=("", 11, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            body,
            text="请先确认上下限已经调好。六轴模式会同时控制 L0/L1/L2/R0/R1/R2，建议先用较窄范围和低档测试。",
            wraplength=360,
            foreground="#555",
        ).grid(row=1, column=0, sticky="ew", pady=(6, 10))

        region_text = tk.StringVar()

        def refresh_region_text() -> None:
            region_text.set(f"{self._t('屏幕区域')}: X {self.x.get()}  Y {self.y.get()}  {self.width.get()} x {self.height.get()}")

        def choose_region() -> None:
            try:
                dialog.grab_release()
            except tk.TclError:
                pass
            dialog.withdraw()

            def restore(_accepted: bool) -> None:
                if not dialog.winfo_exists():
                    return
                refresh_region_text()
                dialog.deiconify()
                dialog.lift()
                dialog.focus_force()
                dialog.grab_set()

            self.pick_region(on_close=restore)

        region_box = ttk.LabelFrame(body, text="屏幕区域", padding=8)
        region_box.grid(row=2, column=0, sticky="ew")
        region_box.columnconfigure(0, weight=1)
        refresh_region_text()
        ttk.Label(region_box, textvariable=region_text, foreground="#333").grid(row=0, column=0, sticky="w")
        ttk.Button(region_box, text="框选屏幕区域", command=choose_region).grid(row=0, column=1, sticky="e", padx=(8, 0))

        choices = ttk.LabelFrame(body, text="输出模式", padding=8)
        choices.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ttk.Radiobutton(choices, text="L0 Only：只上下", variable=mode, value="L0 Only").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Radiobutton(choices, text="Six Axis：六轴", variable=mode, value="Six Axis").grid(row=1, column=0, sticky="w", pady=2)

        analysis = ttk.LabelFrame(body, text="分析", padding=8)
        analysis.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        analysis.columnconfigure(1, weight=1)
        ttk.Combobox(
            analysis,
            textvariable=tracker,
            values=self._tracker_choices(),
            state="readonly",
            width=28,
        ).grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        ttk.Checkbutton(analysis, text="Pose 倾向 L0", variable=pose_l0).grid(row=1, column=0, columnspan=3, sticky="w", pady=2)
        ttk.Label(analysis, text="Pose L0 权重").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Scale(analysis, from_=0, to=100, variable=pose_l0_weight).grid(row=2, column=1, sticky="ew", pady=2)
        ttk.Label(analysis, textvariable=pose_l0_weight, width=4, anchor="e").grid(row=2, column=2, sticky="e")
        ttk.Checkbutton(analysis, text="Pose 倾向六轴", variable=pose_six).grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 2))
        ttk.Label(analysis, text="Pose 六轴权重").grid(row=4, column=0, sticky="w", pady=2)
        ttk.Scale(analysis, from_=0, to=100, variable=pose_six_weight).grid(row=4, column=1, sticky="ew", pady=2)
        ttk.Label(analysis, textvariable=pose_six_weight, width=4, anchor="e").grid(row=4, column=2, sticky="e")
        ttk.Label(analysis, text="压缩延迟").grid(row=5, column=0, sticky="w", pady=(8, 2))
        ttk.Scale(analysis, from_=-5, to=5, variable=compression_latency).grid(row=5, column=1, sticky="ew", pady=(8, 2))
        ttk.Label(analysis, textvariable=compression_latency, width=4, anchor="e").grid(row=5, column=2, sticky="e", pady=(8, 2))
        ttk.Label(analysis, text="-5 最准确 / 0 默认 / 5 延迟最低", wraplength=360, foreground="#555").grid(
            row=6, column=0, columnspan=3, sticky="ew", pady=(0, 2)
        )

        limits_text = tk.StringVar()

        def refresh_limits() -> None:
            if mode.get() == "Six Axis":
                parts = [
                    f"{axis} {self.axis_min_vars[axis].get()}..{self.axis_max_vars[axis].get()}"
                    for axis in SIX_AXES
                ]
                limits_text.set(f"{self._t('当前范围')}: " + " / ".join(parts))
            else:
                limits_text.set(f"{self._t('当前范围')}: L0 {self.min_value.get()}..{self.max_value.get()}")

        mode.trace_add("write", lambda *_args: refresh_limits())
        refresh_limits()
        ttk.Label(body, textvariable=limits_text, wraplength=420, foreground="#333").grid(row=5, column=0, sticky="ew", pady=(10, 0))

        buttons = ttk.Frame(body)
        buttons.grid(row=6, column=0, sticky="ew", pady=(14, 0))
        buttons.columnconfigure((0, 1), weight=1)

        def cancel() -> None:
            dialog.destroy()

        def confirm() -> None:
            self.output_mode.set(mode.get())
            self.tracker_mode.set(tracker.get())
            self.pose_l0_analysis.set(pose_l0.get())
            self.pose_six_axis_analysis.set(pose_six.get())
            self.pose_l0_weight.set(pose_l0_weight.get())
            self.pose_six_axis_weight.set(pose_six_weight.get())
            self.compression_latency.set(max(-5, min(5, int(compression_latency.get()))))
            result["ok"] = True
            dialog.destroy()

        ttk.Button(buttons, text="取消", command=cancel).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(buttons, text="确认开始", command=confirm, style="Primary.TButton").grid(row=0, column=1, sticky="ew", padx=(6, 0))

        dialog.bind("<Escape>", lambda _event: cancel())
        dialog.bind("<Return>", lambda _event: confirm())
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        self._install_tooltips(dialog)
        self._localize_widget_tree(dialog)
        dialog.update_idletasks()
        x = self.winfo_rootx() + max(0, (self.winfo_width() - dialog.winfo_width()) // 2)
        y = self.winfo_rooty() + max(0, (self.winfo_height() - dialog.winfo_height()) // 2)
        dialog.geometry(f"+{x}+{y}")
        self.wait_window(dialog)
        return bool(result["ok"])

    def stop(self) -> None:
        self.stop_event.set()
        if self.worker and self.worker.is_alive():
            self.worker.join(timeout=2)
        self.worker = None
        self._startup_window_geometry = None
        self.status.set(self._t("已停止") if self.connected else self._t("未连接"))

    def estop(self) -> None:
        self.stop()
        self.send_center(interval_ms=600)
        self.status.set(self._t("已急停并回中"))

    def reset_all_settings(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning(self._t("正在运行"), self._t("请先停止实时输出，再恢复默认设置。"))
            return
        confirmed = messagebox.askyesno(
            self._t("恢复所有默认设置"),
            self._t("确认要恢复所有默认设置吗？") + "\n\n"
            + self._t("这会重置屏幕区域、输出方式、串口/BLE 信息、上下限、倍率、五档预设、六轴参数、声音参数和高级参数。")
            + "\n" + self._t("当前本地保存的设置会被覆盖。"),
        )
        if not confirmed:
            return

        self._config_autosave_suspended = True
        if self._config_save_after_id is not None:
            try:
                self.after_cancel(self._config_save_after_id)
            except tk.TclError:
                pass
            self._config_save_after_id = None
        try:
            self.stop()
            self.disconnect_sink()
            self.preview_bridge.stop()
            if hasattr(self, "preview_button"):
                self.preview_button.configure(text=self._t("显示预览"))

            defaults = AppConfig()
            self.config_model = defaults
            self.x.set(defaults.x)
            self.y.set(defaults.y)
            self.width.set(defaults.width)
            self.height.set(defaults.height)
            self.fps.set(defaults.fps)
            self.source_mode.set("Screen")
            self.video_path.set("")
            self.output_mode.set("L0 Only")
            self.audio_mode.set(defaults.audio_mode)
            self.audio_gain.set(defaults.audio_gain)
            self.audio_threshold.set(defaults.audio_threshold)
            self.audio_smoothing.set(defaults.audio_smoothing)
            self.audio_device.set(defaults.audio_device)
            for axis in SIX_AXES:
                self.axis_min_vars[axis].set(defaults.axis_limits[axis][0])
                self.axis_max_vars[axis].set(defaults.axis_limits[axis][1])
            self.smoothing.set(defaults.smoothing)
            self.enable_smoothing.set(defaults.enable_smoothing)
            self.deadzone.set(defaults.deadzone)
            self.enable_deadzone.set(defaults.enable_deadzone)
            self.enable_l0_jitter_guard.set(True)
            self.l0_guard_strength.set(0.70)
            self.enable_extreme_reset.set(True)
            self.extreme_hold_ms.set(900)
            self.enable_endpoint_guard.set(True)
            self.endpoint_margin_pct.set(10)
            self.pose_l0_analysis.set(False)
            self.pose_six_axis_analysis.set(False)
            self.pose_l0_weight.set(60)
            self.pose_six_axis_weight.set(60)
            self._set_tracker_mode(defaults.tracker_mode)
            self.response_curve.set(defaults.response_curve)
            self.motion_gain.set(defaults.motion_gain)
            self.visual_stroke_scale.set(defaults.visual_stroke_scale)
            self.compression_latency.set(0)
            self.l0_travel_scale.set(defaults.global_travel_scale)
            self.global_travel_scale.set(defaults.global_travel_scale)
            self.six_axis_intensity.set(65)
            self.six_axis_jitter_reduction.set(55)
            self.six_axis_sensitivity_level.set(5)
            self.show_more_settings.set(False)
            for axis, gain in DEFAULT_SIX_AXIS_GAINS.items():
                self.six_axis_gain_vars[axis].set(gain)
            for axis, inverted in DEFAULT_SIX_AXIS_INVERTS.items():
                self.six_axis_invert_vars[axis].set(inverted)
            self.min_activity.set(defaults.min_activity)
            self.enable_activity_gate.set(defaults.enable_activity_gate)
            self.max_step.set(defaults.max_step)
            self.enable_speed_limit.set(defaults.enable_speed_limit)
            self.idle_mode.set(defaults.idle_mode)
            self.invert.set(defaults.invert)
            self.enable_startup_ramp.set(defaults.enable_startup_ramp)
            self.startup_ramp_ms.set(defaults.startup_ramp_ms)
            self.axis.set(defaults.axis)
            self.interval_ms.set(defaults.output_interval_ms)
            self.sink_type.set(defaults.last_sink)
            self.serial_port.set(defaults.serial_port)
            self.baudrate.set(defaults.baudrate)
            self.ble_name.set(defaults.ble_name)
            self.ble_address.set(defaults.ble_address)
            self.ble_service_uuid.set(defaults.ble_service_uuid)
            self.ble_write_uuid.set(defaults.ble_write_uuid)
            self.measure_axis.set("L0")
            self.measure_value.set(5000)
            self.measure_live.set(True)
            self.apply_play_preset(3, announce=False)
            self._last_axis_values = {axis: 5000 for axis in SIX_AXES}
            self._six_axis_stable_positions = {axis: 0.5 for axis in SIX_AXES}
            self._previous_l0_value = 5000
            self._script_history.clear()
            self.output_value.set("L05000I20")
            self.l0_status.set("L0 5000")
            self.stroke_status.set(f"{self._t('中段')} 50%")
            self.activity.set(f"{self._t('活动')}: 0.000")
            self.record_status.set(self._t("未录制"))
            self.device_status.set(f"{self._t('设备')}: {self._t('未连接')}")
            self._refresh_limit_text()
            self._draw_axis_monitor(self._last_axis_values)
            self._draw_script_curve()
            self._refresh_play_preset_buttons()
            self.config_model.extra["play_preset_initialized_v1"] = True
        finally:
            self._config_autosave_suspended = False
        self._save_config()
        self.status.set(self._t("已恢复所有默认设置，并保存到本机"))

    def toggle_preview(self) -> None:
        if self.preview_bridge.is_running:
            self.preview_bridge.stop()
            self.preview_button.configure(text=self._t("显示预览"))
            self.status.set(self._t("预览已关闭"))
            return
        try:
            self.preview_bridge.start()
            self.preview_bridge.open_window()
        except Exception as exc:
            self.preview_bridge.stop()
            self.preview_button.configure(text=self._t("显示预览"))
            messagebox.showerror(self._t("预览启动失败"), str(exc))
            return
        self.preview_button.configure(text=self._t("取消预览"))
        if self.output_value.get():
            self.preview_bridge.broadcast_tcode(self.output_value.get())
        self.status.set(self._t("预览已打开：显示限制后的真实输出"))

    def _emit_command(self, command: object) -> str:
        if isinstance(command, str):
            text = command.strip()
            payload = (text + "\n").encode("ascii")
        else:
            payload = command.encode()
            text = payload.decode("ascii").strip()
        self.sink.write(payload)
        self.preview_bridge.broadcast_tcode(text)
        return text

    def send_center(self, interval_ms: int | None = None) -> None:
        if not self.connected:
            self.connect_sink()
            if not self.connected:
                return
        self._normalize_limits()
        output = self._new_output(interval_ms or 500)
        command = output.center_command(interval_ms or 500)
        self.output_value.set(self._emit_command(command))
        self._update_command_monitor(self.output_value.get())

    def _on_measure_slider(self) -> None:
        if not self.measure_live.get():
            return
        if not self.connected:
            self.status.set(self._t("测量模式: 请先连接设备"))
            return
        now = time.perf_counter()
        if now - self._last_measure_sent < 0.045:
            return
        self._last_measure_sent = now
        self.send_measure_position()

    def _sync_measure_value_from_axis(self) -> None:
        axis = self.measure_axis.get() if self.measure_axis.get() in SIX_AXES else "L0"
        self.measure_value.set(max(0, min(9999, int(self._last_axis_values.get(axis, 5000)))))

    def send_measure_position(self, value: int | None = None) -> None:
        if self.worker and self.worker.is_alive():
            self.status.set(self._t("请先停止实时输出，再使用测量模式"))
            return
        if value is not None:
            self.measure_value.set(max(0, min(9999, int(value))))
        if not self.connected:
            self.connect_sink()
            if not self.connected:
                return
        axis = self.measure_axis.get() if self.measure_axis.get() in SIX_AXES else "L0"
        try:
            position = max(0, min(9999, int(float(self.measure_value.get()))))
        except (tk.TclError, ValueError):
            position = 5000
            self.measure_value.set(position)
        interval = max(80, min(900, int(self.interval_ms.get()) if self.interval_ms.get() else 250))
        command = f"{axis}{position:04d}I{interval}"
        try:
            self._emit_command(command)
        except Exception as exc:
            self.status.set(f"{self._t('测量发送失败')}: {exc}")
            return
        self.output_value.set(command)
        self._update_command_monitor(command)
        self.status.set(f"{self._t('测量模式')}: {axis} -> {position:04d}")

    def save_measure_limit(self, which: str) -> None:
        axis = self.measure_axis.get() if self.measure_axis.get() in SIX_AXES else "L0"
        try:
            value = max(0, min(9999, int(float(self.measure_value.get()))))
        except (tk.TclError, ValueError):
            return
        low_var = self.axis_min_vars[axis]
        high_var = self.axis_max_vars[axis]
        if which == "low":
            low_var.set(value)
        else:
            high_var.set(value)
        self._normalize_axis_limit(axis)
        self._refresh_limit_text()
        self._draw_axis_monitor(self._last_axis_values)
        label = self._t("下限" if which == "low" else "上限")
        self.status.set(f"{self._t('已保存')} {axis} {label}: {value:04d}")

    def send_small_test(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning(self._t("正在运行"), self._t("请先停止实时输出，再做中等测试。"))
            return
        if not self.connected:
            self.connect_sink()
            if not self.connected:
                return
        self._normalize_limits()
        axes = self._active_axes()
        output = MultiAxisSafeOutput(
            axes,
            self.min_value.get(),
            self.max_value.get(),
            self.invert.get(),
            480,
            999,
            0.0,
            "Hold",
            axis_limits=self._axis_limits(axes),
            position_scale=self.global_travel_scale.get(),
            axis_position_scales={"L0": self.l0_travel_scale.get()},
            enable_endpoint_guard=self.enable_endpoint_guard.get(),
            endpoint_margin=self.endpoint_margin_pct.get() / 100.0,
        )
        for pos in (0.5, 0.0, 1.0, 0.0, 1.0, 0.5):
            positions = {axis: 0.5 for axis in axes}
            positions["L0"] = pos
            command = output.next_command(positions, 1.0)
            self.output_value.set(self._emit_command(command))
            self._update_command_monitor(self.output_value.get())
            self.update_idletasks()
            time.sleep(0.32)
        self.status.set(self._t("中等测试完成"))

    def send_full_l0_test(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning(self._t("正在运行"), self._t("请先停止实时输出，再做上下全幅测试。"))
            return
        if not self.connected:
            self.connect_sink()
            if not self.connected:
                return
        self._normalize_limits()
        axes = self._active_axes()
        axis_limits = self._axis_limits(axes)
        invert_l0 = self.invert.get()
        min_value = self.min_value.get()
        max_value = self.max_value.get()

        def worker() -> None:
            output = MultiAxisSafeOutput(
                axes,
                min_value,
                max_value,
                invert_l0,
                900,
                9999,
                0.0,
                "Hold",
                axis_limits=axis_limits,
                enable_endpoint_guard=False,
            )
            center = {axis: 0.5 for axis in axes}
            try:
                for pos in (0.5, 0.0, 1.0, 0.0, 1.0, 0.5):
                    positions = center.copy()
                    positions["L0"] = pos
                    command = output.next_command(positions, 1.0)
                    command_text = self._emit_command(command)
                    self._queue_latest(
                        {
                            "command": command_text,
                            "status_text": self._t("上下全幅测试中"),
                        }
                    )
                    time.sleep(0.95)
                center_command = output.center_command(900)
                center_text = self._emit_command(center_command)
                self._queue_latest(
                    {
                        "command": center_text,
                        "status_text": self._t("上下全幅测试完成，已回中"),
                    }
                )
            except Exception as exc:
                self._queue_latest({"error": f"{self._t('上下全幅测试失败')}: {exc}"})

        threading.Thread(target=worker, daemon=True).start()

    def send_six_axis_test(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning(self._t("正在运行"), self._t("请先停止实时输出，再做六轴轻测。"))
            return
        if not self.connected:
            self.connect_sink()
            if not self.connected:
                return
        self._normalize_limits()
        axes = SIX_AXES.copy()
        axis_limits = self._axis_limits(axes)
        min_value = self.min_value.get()
        max_value = self.max_value.get()

        def worker() -> None:
            output = MultiAxisSafeOutput(
                axes,
                min_value,
                max_value,
                False,
                320,
                999,
                0.0,
                "Hold",
                axis_limits=axis_limits,
                position_scale=self.global_travel_scale.get(),
                axis_position_scales={"L0": self.l0_travel_scale.get()},
                enable_endpoint_guard=self.enable_endpoint_guard.get(),
                endpoint_margin=self.endpoint_margin_pct.get() / 100.0,
            )
            center = {axis: 0.5 for axis in axes}
            try:
                command = output.next_command(center, 1.0)
                self._queue_latest({"command": self._emit_command(command), "status_text": self._t("OSR6 六轴轻测中")})
                time.sleep(0.35)
                for axis in axes:
                    for value in (0.35, 0.65, 0.5):
                        positions = center.copy()
                        positions[axis] = value
                        command = output.next_command(positions, 1.0)
                        self._queue_latest({"command": self._emit_command(command)})
                        time.sleep(0.35)
                center_command = output.center_command(600)
                self._queue_latest({"command": self._emit_command(center_command)})
                self._queue_latest({"status_text": self._t("OSR6 六轴轻测完成，已回中")})
            except Exception as exc:
                self._queue_latest({"error": f"{self._t('六轴轻测失败')}: {exc}"})

        threading.Thread(target=worker, daemon=True).start()

    def apply_safe_preset(self) -> None:
        self._set_all_axis_limits(2500, 7500)
        self.max_step.set(900)
        self.min_activity.set(0.006)
        self.smoothing.set(0.45)
        self.enable_l0_jitter_guard.set(True)
        self.l0_guard_strength.set(0.85)
        self.enable_extreme_reset.set(True)
        self.extreme_hold_ms.set(700)
        self.enable_endpoint_guard.set(True)
        self.endpoint_margin_pct.set(14)
        self.motion_gain.set(0.8)
        self.l0_travel_scale.set(0.55)
        self.global_travel_scale.set(0.55)
        self.status.set(self._t("已应用安全预设"))
        self.play_preset_level.set(1)
        self._refresh_play_preset_buttons()

    def apply_normal_preset(self) -> None:
        self._set_all_axis_limits(500, 9500)
        self.max_step.set(1800)
        self.min_activity.set(0.004)
        self.smoothing.set(0.25)
        self.enable_l0_jitter_guard.set(True)
        self.l0_guard_strength.set(0.70)
        self.enable_extreme_reset.set(True)
        self.extreme_hold_ms.set(850)
        self.enable_endpoint_guard.set(True)
        self.endpoint_margin_pct.set(10)
        self.motion_gain.set(1.25)
        self.l0_travel_scale.set(1.0)
        self.global_travel_scale.set(1.0)
        self.status.set(self._t("已应用标准预设"))
        self.play_preset_level.set(3)
        self._refresh_play_preset_buttons()

    def apply_full_preset(self) -> None:
        self.output_mode.set("L0 Only")
        self._set_all_axis_limits(0, 9999)
        self.max_step.set(9999)
        self.min_activity.set(0.003)
        self.smoothing.set(0.12)
        self.enable_l0_jitter_guard.set(True)
        self.l0_guard_strength.set(0.45)
        self.enable_extreme_reset.set(True)
        self.extreme_hold_ms.set(1000)
        self.enable_endpoint_guard.set(True)
        self.endpoint_margin_pct.set(6)
        self.motion_gain.set(1.6)
        self.l0_travel_scale.set(1.30)
        self.global_travel_scale.set(1.0)
        self.status.set(self._t("已应用上下全行程高速预设"))
        self.play_preset_level.set(5)
        self._refresh_play_preset_buttons()

    def apply_hybrid_analysis_preset(self) -> None:
        self._set_tracker_mode("混合分析（推荐）")
        self.enable_smoothing.set(True)
        self.smoothing.set(0.08)
        self.enable_deadzone.set(True)
        self.deadzone.set(0.006)
        self.enable_l0_jitter_guard.set(True)
        self.l0_guard_strength.set(0.70)
        self.enable_extreme_reset.set(True)
        self.extreme_hold_ms.set(850)
        self.enable_endpoint_guard.set(True)
        self.endpoint_margin_pct.set(10)
        self.enable_activity_gate.set(True)
        self.min_activity.set(0.0025)
        self.enable_speed_limit.set(True)
        self.max_step.set(1800)
        self.motion_gain.set(1.55)
        self.visual_stroke_scale.set(0.68)
        self.l0_travel_scale.set(1.0)
        self.global_travel_scale.set(1.0)
        self.response_curve.set("Linear")
        self.idle_mode.set("Hold")
        self.status.set(self._t("已应用混合分析稳态预设"))
        self.play_preset_level.set(3)
        self._refresh_play_preset_buttons()

    def apply_stable_l0_preset(self) -> None:
        self._set_tracker_mode("混合分析（推荐）")
        self.enable_smoothing.set(True)
        self.smoothing.set(0.30)
        self.enable_deadzone.set(True)
        self.deadzone.set(0.010)
        self.enable_l0_jitter_guard.set(True)
        self.l0_guard_strength.set(0.82)
        self.enable_extreme_reset.set(True)
        self.extreme_hold_ms.set(650)
        self.enable_endpoint_guard.set(True)
        self.endpoint_margin_pct.set(14)
        self.enable_activity_gate.set(True)
        self.min_activity.set(0.0045)
        self.enable_speed_limit.set(True)
        self.max_step.set(1300)
        self.motion_gain.set(1.25)
        self.visual_stroke_scale.set(0.62)
        self.l0_travel_scale.set(0.75)
        self.response_curve.set("Linear")
        self.apply_soft_six_axis_preset()
        self.status.set(self._t("已应用稳态 L0 + 低敏六轴"))

    def apply_play_preset(self, level: int, announce: bool = True) -> None:
        presets = {
            1: {"interval": 38, "step": 550, "smooth": 0.42, "deadzone": 0.010, "activity": 0.0060, "gain": 0.90, "visual": 0.50, "travel": 0.55, "edge": 14, "hold": 650},
            2: {"interval": 30, "step": 900, "smooth": 0.34, "deadzone": 0.009, "activity": 0.0045, "gain": 1.10, "visual": 0.58, "travel": 0.75, "edge": 12, "hold": 750},
            3: {"interval": 24, "step": 1300, "smooth": 0.28, "deadzone": 0.008, "activity": 0.0035, "gain": 1.35, "visual": 0.66, "travel": 1.00, "edge": 10, "hold": 850},
            4: {"interval": 20, "step": 2100, "smooth": 0.20, "deadzone": 0.006, "activity": 0.0025, "gain": 1.65, "visual": 0.76, "travel": 1.15, "edge": 8, "hold": 950},
            5: {"interval": 16, "step": 3200, "smooth": 0.14, "deadzone": 0.004, "activity": 0.0018, "gain": 2.00, "visual": 0.90, "travel": 1.30, "edge": 6, "hold": 1100},
        }
        level = max(1, min(5, int(level)))
        preset = presets[level]
        self._set_tracker_mode("混合分析（推荐）")
        self.enable_speed_limit.set(True)
        self.enable_smoothing.set(True)
        self.enable_deadzone.set(True)
        self.enable_l0_jitter_guard.set(True)
        self.l0_guard_strength.set({1: 0.88, 2: 0.80, 3: 0.70, 4: 0.55, 5: 0.42}[level])
        self.enable_extreme_reset.set(True)
        self.extreme_hold_ms.set(preset["hold"])
        self.enable_endpoint_guard.set(True)
        self.endpoint_margin_pct.set(preset["edge"])
        self.enable_activity_gate.set(True)
        self.interval_ms.set(preset["interval"])
        self.max_step.set(preset["step"])
        self.smoothing.set(preset["smooth"])
        self.deadzone.set(preset["deadzone"])
        self.min_activity.set(preset["activity"])
        self.motion_gain.set(preset["gain"])
        self.visual_stroke_scale.set(preset["visual"])
        self.l0_travel_scale.set(preset["travel"])
        self.global_travel_scale.set(preset["travel"])
        self.response_curve.set("Linear")
        self.idle_mode.set("Hold")
        self.play_preset_level.set(level)
        self._refresh_play_preset_buttons()
        if announce:
            self.status.set(f"{self._t('已应用')} {level} {self._t('档')} {self._t('预设')}")

    def _refresh_play_preset_buttons(self) -> None:
        if not hasattr(self, "preset_buttons"):
            return
        active = self.play_preset_level.get()
        for level, button in self.preset_buttons.items():
            button.configure(style="PresetActive.TButton" if level == active else "TButton")

    def start_recording(self) -> None:
        self.recorder.start()
        self.record_status.set(f"{self._t('录制中')}: 0 {self._t('点')}")

    def save_recording(self) -> None:
        if self.recorder.is_recording:
            self.recorder.stop()
        path = filedialog.asksaveasfilename(
            title=self._t("保存 funscript"),
            defaultextension=".funscript",
            filetypes=(("Funscript", "*.funscript"), ("JSON", "*.json"), ("All files", "*.*")),
        )
        if not path:
            return
        self.recorder.save(Path(path))
        self.record_status.set(f"{self._t('已保存:')} {self.recorder.action_count} {self._t('点')}")

    def pick_region(self, on_close: Callable[[bool], None] | None = None) -> None:
        overlay = tk.Toplevel(self)
        overlay.configure(background="black")
        overlay.attributes("-fullscreen", True)
        overlay.attributes("-alpha", 0.36)
        overlay.attributes("-topmost", True)
        overlay.config(cursor="crosshair")
        overlay.grab_set()
        canvas = tk.Canvas(overlay, background="black", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        overlay.update_idletasks()

        root_x = overlay.winfo_rootx()
        root_y = overlay.winfo_rooty()
        state: dict[str, object] = {
            "start": None,
            "region": None,
            "panel": None,
            "closed": False,
        }

        def local_to_screen(x_value: int, y_value: int) -> tuple[int, int]:
            return root_x + x_value, root_y + y_value

        def draw_help() -> None:
            canvas.delete("help")
            canvas.create_rectangle(18, 18, 680, 100, fill="#090909", outline="#58e08a", width=2, tags="help")
            canvas.create_text(
                34,
                34,
                text=self._t("拖拽选择实时读取区域"),
                anchor="nw",
                fill="white",
                font=("", 16, "bold"),
                tags="help",
            )
            canvas.create_text(
                34,
                62,
                text=self._t("建议只框住主要画面动作，避开弹幕、字幕和播放器控件；Enter 确认，R 重选，Esc 取消"),
                anchor="nw",
                fill="#d7d7d7",
                font=("", 11),
                tags="help",
            )

        def draw_current_region() -> None:
            canvas.delete("current_region")
            try:
                x1 = self.x.get() - root_x
                y1 = self.y.get() - root_y
                x2 = x1 + self.width.get()
                y2 = y1 + self.height.get()
            except tk.TclError:
                return
            if self.width.get() <= 0 or self.height.get() <= 0:
                return
            canvas.create_rectangle(x1, y1, x2, y2, outline="#7fb4ff", width=2, dash=(6, 4), tags="current_region")
            for ax, ay, bx, by in (
                (x1, y1, x1 + 28, y1),
                (x1, y1, x1, y1 + 28),
                (x2, y1, x2 - 28, y1),
                (x2, y1, x2, y1 + 28),
                (x1, y2, x1 + 28, y2),
                (x1, y2, x1, y2 - 28),
                (x2, y2, x2 - 28, y2),
                (x2, y2, x2, y2 - 28),
            ):
                canvas.create_line(ax, ay, bx, by, fill="#cfe3ff", width=3, tags="current_region")
            canvas.create_text(
                x1 + 8,
                max(104, y1 + 8),
                text=f"{self._t('当前区域')} {self.width.get()} x {self.height.get()}",
                anchor="nw",
                fill="#cfe3ff",
                font=("", 11, "bold"),
                tags="current_region",
            )

        def clear_panel() -> None:
            panel = state.get("panel")
            if panel is not None:
                try:
                    canvas.delete(panel)
                except tk.TclError:
                    pass
            state["panel"] = None

        def reset_selection(_event: tk.Event | None = None) -> None:
            clear_panel()
            state["region"] = None
            state["start"] = None
            canvas.delete("selection")
            canvas.delete("cursor")
            draw_help()
            draw_current_region()

        def finish(accepted: bool) -> None:
            if state.get("closed"):
                return
            state["closed"] = True
            try:
                overlay.grab_release()
            except tk.TclError:
                pass
            try:
                overlay.destroy()
            except tk.TclError:
                pass
            if on_close is not None:
                self.after(50, lambda: on_close(accepted))

        def confirm(_event: tk.Event | None = None) -> None:
            region = state.get("region")
            if not region:
                return
            x1, y1, width, height = region
            self.x.set(int(x1))
            self.y.set(int(y1))
            self.width.set(int(width))
            self.height.set(int(height))
            self.status.set(f"{self._t('已选择区域')}: {width} x {height}")
            finish(True)

        def cancel(_event: tk.Event | None = None) -> None:
            finish(False)

        def draw_panel(x1: int, y1: int, x2: int, y2: int, width: int, height: int) -> None:
            clear_panel()
            panel = tk.Frame(overlay, background="#101010", padx=10, pady=8, highlightthickness=1, highlightbackground="#2f7d55")
            tk.Label(
                panel,
                text=f"{width} x {height}    X {root_x + x1}  Y {root_y + y1}",
                background="#101010",
                foreground="white",
                font=("", 10, "bold"),
            ).grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 6))
            tk.Button(panel, text=self._t("使用此区域"), command=confirm, width=10).grid(row=1, column=0, padx=(0, 6))
            tk.Button(panel, text=self._t("重新选择"), command=reset_selection, width=10).grid(row=1, column=1, padx=(0, 6))
            tk.Button(panel, text=self._t("取消"), command=cancel, width=8).grid(row=1, column=2)
            px = min(max(24, x1), max(24, canvas.winfo_width() - 310))
            py = y2 + 14 if y2 + 82 < canvas.winfo_height() else max(104, y1 - 82)
            state["panel"] = canvas.create_window(px, py, window=panel, anchor="nw")

        def draw_selection(x1: int, y1: int, x2: int, y2: int) -> None:
            canvas.delete("selection")
            left, right = sorted((x1, x2))
            top, bottom = sorted((y1, y2))
            width = max(0, right - left)
            height = max(0, bottom - top)
            canvas.create_rectangle(left, top, right, bottom, outline="#58e08a", width=3, tags="selection")
            canvas.create_rectangle(left, top, right, bottom, outline="white", width=1, dash=(4, 3), tags="selection")
            mid_x = (left + right) // 2
            mid_y = (top + bottom) // 2
            canvas.create_line(mid_x, top, mid_x, bottom, fill="#58e08a", width=1, dash=(3, 7), tags="selection")
            canvas.create_line(left, mid_y, right, mid_y, fill="#58e08a", width=1, dash=(3, 7), tags="selection")
            corner = min(38, max(16, min(width, height) // 5))
            for ax, ay, bx, by in (
                (left, top, left + corner, top),
                (left, top, left, top + corner),
                (right, top, right - corner, top),
                (right, top, right, top + corner),
                (left, bottom, left + corner, bottom),
                (left, bottom, left, bottom - corner),
                (right, bottom, right - corner, bottom),
                (right, bottom, right, bottom - corner),
            ):
                canvas.create_line(ax, ay, bx, by, fill="#ffffff", width=4, tags="selection")
            label_x = min(left + 10, max(10, canvas.winfo_width() - 210))
            label_y = max(104, top - 30)
            canvas.create_rectangle(label_x - 6, label_y - 5, label_x + 190, label_y + 21, fill="#111111", outline="#58e08a", tags="selection")
            canvas.create_text(
                label_x,
                label_y,
                text=f"{width} x {height}   X {root_x + left}  Y {root_y + top}",
                anchor="nw",
                fill="white",
                font=("", 10, "bold"),
                tags="selection",
            )

        def draw_cursor(event: tk.Event) -> None:
            canvas.delete("cursor")
            if state.get("region"):
                return
            canvas.create_line(event.x, 0, event.x, canvas.winfo_height(), fill="#555555", dash=(2, 8), tags="cursor")
            canvas.create_line(0, event.y, canvas.winfo_width(), event.y, fill="#555555", dash=(2, 8), tags="cursor")

        def down(event: tk.Event) -> None:
            clear_panel()
            state["region"] = None
            state["start"] = (event.x, event.y)
            canvas.delete("selection")
            draw_selection(event.x, event.y, event.x, event.y)

        def move(event: tk.Event) -> None:
            draw_cursor(event)
            start = state.get("start")
            if start is None:
                return
            x1, y1 = start
            draw_selection(int(x1), int(y1), event.x, event.y)

        def up(event: tk.Event) -> None:
            start = state.get("start")
            state["start"] = None
            if start is None:
                return
            sx, sy = start
            left, right = sorted((int(sx), event.x))
            top, bottom = sorted((int(sy), event.y))
            width = right - left
            height = bottom - top
            if width < 24 or height < 24:
                canvas.delete("selection")
                canvas.create_text(
                    event.x + 12,
                    event.y + 12,
                    text=self._t("区域太小，请重新拖拽"),
                    anchor="nw",
                    fill="#ffdddd",
                    font=("", 11, "bold"),
                    tags="selection",
                )
                return
            screen_x, screen_y = local_to_screen(left, top)
            state["region"] = (screen_x, screen_y, width, height)
            draw_selection(left, top, right, bottom)
            draw_panel(left, top, right, bottom, width, height)

        draw_help()
        draw_current_region()
        overlay.bind("<ButtonPress-1>", down)
        overlay.bind("<Motion>", draw_cursor)
        overlay.bind("<B1-Motion>", move)
        overlay.bind("<ButtonRelease-1>", up)
        overlay.bind("<Return>", confirm)
        overlay.bind("<r>", reset_selection)
        overlay.bind("<R>", reset_selection)
        overlay.bind("<Escape>", cancel)
        overlay.focus_force()

    def _run_capture(self) -> None:
        self._normalize_limits()
        fps = max(1, min(120, self.fps.get()))
        period = 1.0 / fps
        try:
            if self.source_mode.get() == "Audio Only":
                self._run_audio(period)
                return
            analyzer = RealtimeAnalyzer(
                self._tracker_internal(self.tracker_mode.get()),
                self.output_mode.get(),
                self.smoothing.get(),
                self.deadzone.get(),
                self.motion_gain.get(),
                self.enable_smoothing.get(),
                self.enable_deadzone.get(),
                self.response_curve.get(),
                self.visual_stroke_scale.get(),
                self.enable_l0_jitter_guard.get(),
                self.l0_guard_strength.get(),
                self.enable_extreme_reset.get(),
            self.enable_endpoint_guard.get(),
            self.endpoint_margin_pct.get() / 200.0,
            False,
            self.pose_l0_analysis.get(),
            self.pose_six_axis_analysis.get(),
            self.pose_l0_weight.get() / 100.0,
            self.pose_six_axis_weight.get() / 100.0,
        )
            output = self._new_output(self.interval_ms.get())
            if self.source_mode.get() == "Video File":
                self._run_video(analyzer, output, period, 0.0)
            else:
                self._run_screen(analyzer, output, period, 0.0)
        except Exception as exc:
            self._queue_latest({"error": str(exc)})

    def _run_screen(
        self,
        analyzer: RealtimeAnalyzer,
        output: MultiAxisSafeOutput,
        period: float,
        last_preview: float,
    ) -> None:
        region = ScreenRegion(self.x.get(), self.y.get(), self.width.get(), self.height.get())
        with ScreenCapture(region) as capture:
            while not self.stop_event.is_set():
                started = time.perf_counter()
                frame = capture.grab_bgr()
                last_preview = self._process_frame(analyzer, output, frame, last_preview)
                sleep_for = period - (time.perf_counter() - started)
                if sleep_for > 0:
                    time.sleep(sleep_for)

    def _run_video(
        self,
        analyzer: RealtimeAnalyzer,
        output: MultiAxisSafeOutput,
        period: float,
        last_preview: float,
    ) -> None:
        path = self.video_path.get()
        if not path:
            raise ValueError("请选择视频文件")
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise ValueError(f"无法打开视频: {path}")
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        if video_fps and video_fps > 1:
            period = 1.0 / min(120.0, video_fps)
        try:
            while not self.stop_event.is_set():
                started = time.perf_counter()
                ok, frame = cap.read()
                if not ok:
                    self._queue_latest({"error": "视频分析完成"})
                    break
                last_preview = self._process_frame(analyzer, output, frame, last_preview)
                sleep_for = period - (time.perf_counter() - started)
                if sleep_for > 0:
                    time.sleep(sleep_for)
        finally:
            cap.release()

    def _run_audio(self, period: float) -> None:
        analyzer = AudioAnalyzer(
            self.audio_mode.get(),
            self.audio_gain.get(),
            self.audio_threshold.get(),
            self.audio_smoothing.get(),
        )
        output = self._new_output(self.interval_ms.get())
        self._queue_latest({"status_text": "声音监听中"})
        last_update = 0.0
        with AudioCapture(self.audio_device.get()) as capture:
            while not self.stop_event.is_set():
                samples, duration = capture.read()
                result = analyzer.process(samples, duration or period)
                positions = self._apply_six_axis_tuning(result.positions)
                command = output.next_command(positions, result.activity)
                command_text = self._emit_command(command)
                self.recorder.add(positions)
                now = time.perf_counter()
                if now - last_update > 0.08:
                    self._queue_latest(
                        {
                            "command": command_text,
                            "activity": result.activity,
                            "audio_level": result.level,
                            "record_count": self.recorder.action_count,
                        }
                    )
                    last_update = now

    def _process_frame(
        self,
        analyzer: RealtimeAnalyzer,
        output: MultiAxisSafeOutput,
        frame: object,
        last_preview: float,
    ) -> float:
        result = analyzer.process(self._prepare_analysis_frame(frame))
        positions = self._apply_six_axis_tuning(result.positions)
        command = output.next_command(positions, result.activity)
        command_text = self._emit_command(command)
        self.recorder.add(positions)
        now = time.perf_counter()
        if now - last_preview > 0.08:
            self._queue_latest(
                {
                    "preview": result.preview_bgr,
                    "command": command_text,
                    "activity": result.activity,
                    "record_count": self.recorder.action_count,
                }
            )
            return now
        return last_preview

    def _prepare_analysis_frame(self, frame: object) -> object:
        scale = self._analysis_frame_scale()
        if scale >= 0.999:
            return frame
        try:
            height, width = frame.shape[:2]
        except AttributeError:
            return frame
        target_width = max(64, int(round(width * scale)))
        target_height = max(64, int(round(height * scale)))
        if target_width == width and target_height == height:
            return frame
        return cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_AREA)

    def _analysis_frame_scale(self) -> float:
        try:
            value = max(-5, min(5, int(round(float(self.compression_latency.get())))))
        except (tk.TclError, ValueError):
            return 1.0
        if value <= 0:
            return 1.0
        return max(0.60, 1.0 - value * 0.08)

    def _active_axes(self) -> list[str]:
        return ["L0"] if self.output_mode.get() != "Six Axis" else SIX_AXES.copy()

    def _apply_six_axis_tuning(self, positions: dict[str, float]) -> dict[str, float]:
        if self.output_mode.get() != "Six Axis":
            return dict(positions)
        tuned = dict(positions)
        global_gain = max(0.0, min(1.8, self.six_axis_intensity.get() / 100.0))
        damping = max(0.0, min(1.0, self.six_axis_jitter_reduction.get() / 100.0))
        sensitivity = 1.0 - damping * 0.62
        filter_strength = 0.18 + damping * 0.66
        micro_deadband = 0.0005 + damping * 0.0028
        for axis in ("L1", "L2", "R0", "R1", "R2"):
            value = max(0.0, min(1.0, float(tuned.get(axis, 0.5))))
            centered = value - 0.5
            axis_gain = max(0.0, min(2.0, self.six_axis_gain_vars[axis].get() / 100.0))
            centered *= global_gain * axis_gain * sensitivity
            if self.six_axis_invert_vars[axis].get():
                centered *= -1.0
            target = max(0.0, min(1.0, 0.5 + centered))
            previous = self._six_axis_stable_positions.get(axis, 0.5)
            if abs(target - previous) < micro_deadband:
                target = previous
            else:
                target = previous * filter_strength + target * (1.0 - filter_strength)
            self._six_axis_stable_positions[axis] = target
            tuned[axis] = target
        return tuned

    def _axis_limits(self, axes: list[str] | None = None) -> dict[str, tuple[int, int]]:
        selected_axes = axes or SIX_AXES
        return {
            axis: (self.axis_min_vars[axis].get(), self.axis_max_vars[axis].get())
            for axis in selected_axes
        }

    def _new_output(self, interval_ms: int) -> MultiAxisSafeOutput:
        self._normalize_limits()
        axes = self._active_axes()
        return MultiAxisSafeOutput(
            axes,
            self.min_value.get(),
            self.max_value.get(),
            self.invert.get(),
            interval_ms,
            self.max_step.get() if self.enable_speed_limit.get() else 9999,
            self.min_activity.get() if self.enable_activity_gate.get() else 0.0,
            self.idle_mode.get(),
            axis_limits=self._axis_limits(axes),
            startup_ramp_ms=self.startup_ramp_ms.get() if self.enable_startup_ramp.get() else 0,
            position_scale=self.global_travel_scale.get(),
            axis_position_scales={"L0": self.l0_travel_scale.get()},
            enable_extreme_reset=self.enable_extreme_reset.get(),
            extreme_hold_ms=self.extreme_hold_ms.get(),
            enable_endpoint_guard=self.enable_endpoint_guard.get(),
            endpoint_margin=self.endpoint_margin_pct.get() / 100.0,
        )

    def _queue_latest(self, item: dict[str, object]) -> None:
        try:
            if self.frame_queue.full():
                self.frame_queue.get_nowait()
            self.frame_queue.put_nowait(item)
        except queue.Full:
            pass

    def _poll_worker(self) -> None:
        try:
            while True:
                item = self.frame_queue.get_nowait()
                if "error" in item:
                    self.status.set(str(item["error"]))
                if "status_text" in item:
                    self.status.set(str(item["status_text"]))
                if "preview" in item:
                    self._update_preview(item["preview"])
                if "command" in item:
                    command = str(item["command"])
                    self.output_value.set(command)
                    self._update_command_monitor(command)
                if "activity" in item:
                    self.activity.set(f"{self._t('活动')}: {float(item['activity']):.3f}")
                if "audio_level" in item:
                    self.activity.set(f"{self._t('声音')}: {float(item['audio_level']):.3f}")
                if "record_count" in item and self.recorder.is_recording:
                    self.record_status.set(f"{self._t('录制中')}: {item['record_count']} {self._t('点')}")
                if "ble_devices" in item:
                    devices = item["ble_devices"]
                    if devices:
                        name, address = devices[0]
                        self.ble_name.set(name)
                        self.ble_address.set(address)
                        self.status.set(f"{self._t('找到 BLE')}: {name}")
                    else:
                        self.status.set(self._t("未找到 BLE 设备"))
        except queue.Empty:
            pass
        self.after(50, self._poll_worker)

    def _update_preview(self, frame_bgr: object) -> None:
        frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame)
        max_w = max(320, self.preview_canvas.winfo_width())
        max_h = max(240, self.preview_canvas.winfo_height())
        img.thumbnail((max_w, max_h))
        self.preview_image = ImageTk.PhotoImage(img)
        self._redraw_preview_image()

    def _redraw_preview_image(self) -> None:
        if not hasattr(self, "preview_canvas") or self.preview_image is None:
            return
        x = max(0, self.preview_canvas.winfo_width() // 2)
        y = max(0, self.preview_canvas.winfo_height() // 2)
        if self.preview_canvas_image is None:
            self.preview_canvas_image = self.preview_canvas.create_image(x, y, image=self.preview_image, anchor="center")
        else:
            self.preview_canvas.itemconfigure(self.preview_canvas_image, image=self.preview_image)
            self.preview_canvas.coords(self.preview_canvas_image, x, y)

    def _normalize_limits(self) -> None:
        for axis in SIX_AXES:
            self._normalize_axis_limit(axis)
        self._refresh_limit_text()

    def _normalize_axis_limit(self, axis: str) -> None:
        try:
            low = max(0, min(9999, int(float(self.axis_min_vars[axis].get()))))
            high = max(0, min(9999, int(float(self.axis_max_vars[axis].get()))))
        except (KeyError, tk.TclError, ValueError):
            return
        if low > high:
            low, high = high, low
        if low != self.axis_min_vars[axis].get():
            self.axis_min_vars[axis].set(low)
        if high != self.axis_max_vars[axis].get():
            self.axis_max_vars[axis].set(high)
        self._refresh_axis_limit_text(axis)

    def _set_all_axis_limits(self, low: int, high: int) -> None:
        for axis in SIX_AXES:
            self.axis_min_vars[axis].set(low)
            self.axis_max_vars[axis].set(high)
        self._normalize_limits()

    def _refresh_axis_limit_text(self, axis: str) -> None:
        if axis == "L0":
            self._refresh_limit_text()

    def _refresh_limit_text(self) -> None:
        try:
            low = int(float(self.min_value.get()))
            high = int(float(self.max_value.get()))
        except (tk.TclError, ValueError):
            return
        self.range_status.set(f"L0 {self._t('下限')} {low} / {self._t('上限')} {high}")
        self._draw_stroke_monitor(self._parse_l0_value(self.output_value.get()) or 5000)

    def _update_command_monitor(self, command: str) -> None:
        values = self._parse_axis_values(command)
        if not values:
            return
        self._last_axis_values.update(values)
        now = time.perf_counter()
        self._script_history.append((now, dict(self._last_axis_values)))
        l0 = values.get("L0")
        if l0 is not None:
            self.l0_status.set(f"L0 {l0:04d}")
            self._update_stroke_status(l0)
            self._draw_stroke_monitor(l0)
            self._previous_l0_value = l0
        self._draw_axis_monitor(self._last_axis_values)
        self._draw_script_curve()

    @staticmethod
    def _parse_l0_value(command: str) -> int | None:
        match = re.search(r"L0(\d{4})", command)
        if match is None:
            return None
        return int(match.group(1))

    @staticmethod
    def _parse_axis_values(command: str) -> dict[str, int]:
        return {
            axis: int(value)
            for axis, value in re.findall(r"([LR][0-2])(\d{4})", command)
        }

    def _update_stroke_status(self, value: int) -> None:
        try:
            low = max(0, min(9999, int(float(self.min_value.get()))))
            high = max(0, min(9999, int(float(self.max_value.get()))))
        except (tk.TclError, ValueError):
            low, high = 0, 9999
        if low > high:
            low, high = high, low
        span = max(1, high - low)
        ratio = max(0.0, min(1.0, (value - low) / span))
        delta = value - self._previous_l0_value
        if delta <= -22:
            label = self._t("插入中（去下限）")
        elif delta >= 22:
            label = self._t("拔出中（去上限）")
        elif ratio <= 0.22:
            label = self._t("插入端（下限）")
        elif ratio >= 0.78:
            label = self._t("拔出端（上限）")
        else:
            label = self._t("中段")
        self.stroke_status.set(f"{label}  {ratio * 100:.0f}%")

    def _draw_stroke_monitor(self, value: int) -> None:
        if not hasattr(self, "stroke_canvas"):
            return
        canvas = self.stroke_canvas
        canvas.delete("all")
        width = int(canvas["width"])
        height = int(canvas["height"])
        pad = 12
        try:
            low = max(0, min(9999, int(float(self.min_value.get()))))
            high = max(0, min(9999, int(float(self.max_value.get()))))
        except (tk.TclError, ValueError):
            low, high = 0, 9999
        if low > high:
            low, high = high, low

        def y_for(v: int) -> float:
            return height - pad - (v / 9999) * (height - 2 * pad)

        x = width // 2
        canvas.create_rectangle(x - 8, pad, x + 8, height - pad, fill="#e7e7e7", outline="#c5c5c5")
        canvas.create_rectangle(x - 14, y_for(high), x + 14, y_for(low), fill="#bfe7cc", outline="#58a873")
        y = y_for(max(0, min(9999, value)))
        canvas.create_oval(x - 19, y - 8, x + 19, y + 8, fill="#176f3f", outline="")
        canvas.create_text(x, pad - 2, text=self._t("拔出"), anchor="s", fill="#555")
        canvas.create_text(x, height - pad + 2, text=self._t("插入"), anchor="n", fill="#555")

    def _draw_axis_monitor(self, values: dict[str, int]) -> None:
        if not hasattr(self, "axis_canvas"):
            return
        canvas = self.axis_canvas
        canvas.delete("all")
        width = max(360, canvas.winfo_width() or int(canvas["width"]))
        height = int(canvas["height"])
        left = 42
        right = width - 52
        row_h = height / 6.0
        active_axes = set(self._active_axes())
        for index, axis in enumerate(SIX_AXES):
            y = int(row_h * index + row_h * 0.5)
            value = max(0, min(9999, int(values.get(axis, 5000))))
            try:
                low = max(0, min(9999, int(float(self.axis_min_vars[axis].get()))))
                high = max(0, min(9999, int(float(self.axis_max_vars[axis].get()))))
            except (tk.TclError, ValueError):
                low, high = 0, 9999
            if low > high:
                low, high = high, low

            def x_for(v: int) -> float:
                return left + (v / 9999) * max(1, right - left)

            muted = axis not in active_axes
            track = "#eeeeee" if muted else "#e3e7ea"
            range_fill = "#d8ecdf" if axis == "L0" else "#dfe8f7"
            marker = "#176f3f" if axis == "L0" else "#335f9f"
            text_fill = "#9a9a9a" if muted else "#222222"
            canvas.create_text(10, y, text=axis, anchor="w", fill=text_fill, font=("", 9, "bold"))
            canvas.create_rectangle(left, y - 4, right, y + 4, fill=track, outline="")
            canvas.create_rectangle(x_for(low), y - 5, x_for(high), y + 5, fill=range_fill, outline="")
            x = x_for(value)
            canvas.create_rectangle(x - 3, y - 9, x + 3, y + 9, fill=marker if not muted else "#bdbdbd", outline="")
            canvas.create_text(width - 8, y, text=f"{value:04d}", anchor="e", fill=text_fill, font=("", 9))

    def _draw_script_curve(self) -> None:
        if not hasattr(self, "curve_canvas"):
            return
        canvas = self.curve_canvas
        canvas.delete("all")
        width = max(360, canvas.winfo_width() or int(canvas["width"]))
        height = int(canvas["height"])
        pad_l = 46
        pad_r = 12
        pad_t = 18
        pad_b = 22
        plot_w = max(1, width - pad_l - pad_r)
        plot_h = max(1, height - pad_t - pad_b)
        canvas.create_rectangle(0, 0, width, height, fill="#101418", outline="")
        canvas.create_text(10, 8, text=self._t("脚本曲线"), anchor="nw", fill="#e9eef2", font=("", 10, "bold"))
        canvas.create_text(width - 10, 8, text=self._t("最近12秒 / 实际输出"), anchor="ne", fill="#95a1aa", font=("", 9))
        for label, value in (("9999", 9999), ("5000", 5000), ("0000", 0)):
            y = pad_t + (1.0 - value / 9999.0) * plot_h
            canvas.create_line(pad_l, y, width - pad_r, y, fill="#27313a", dash=(3, 5) if value != 5000 else ())
            canvas.create_text(pad_l - 8, y, text=label, anchor="e", fill="#8c98a3", font=("", 8))
        canvas.create_rectangle(pad_l, pad_t, width - pad_r, height - pad_b, outline="#2e3942")
        if len(self._script_history) < 2:
            canvas.create_text(
                pad_l + plot_w / 2,
                pad_t + plot_h / 2,
                text=self._t("开始输出后显示曲线"),
                fill="#7f8c96",
                font=("", 11),
            )
            return
        latest = self._script_history[-1][0]
        window_s = 12.0
        points = [(ts, values) for ts, values in self._script_history if latest - ts <= window_s]
        if len(points) < 2:
            return

        def x_for(ts: float) -> float:
            age = max(0.0, min(window_s, latest - ts))
            return pad_l + plot_w * (1.0 - age / window_s)

        def y_for(value: int) -> float:
            return pad_t + (1.0 - max(0, min(9999, value)) / 9999.0) * plot_h

        colors = {
            "L0": "#46d184",
            "L1": "#67a6ff",
            "L2": "#ffcc66",
            "R0": "#ff7f7f",
            "R1": "#b58cff",
            "R2": "#69d2e7",
        }
        active_axes = self._active_axes()
        for axis in active_axes:
            coords: list[float] = []
            for ts, values in points:
                coords.extend((x_for(ts), y_for(int(values.get(axis, 5000)))))
            if len(coords) >= 4:
                canvas.create_line(*coords, fill=colors.get(axis, "#ffffff"), width=3 if axis == "L0" else 2, smooth=True)
        legend_x = pad_l
        for axis in active_axes:
            color = colors.get(axis, "#ffffff")
            canvas.create_rectangle(legend_x, height - 15, legend_x + 10, height - 5, fill=color, outline="")
            canvas.create_text(legend_x + 14, height - 10, text=axis, anchor="w", fill="#d8e0e6", font=("", 8, "bold"))
            legend_x += 44

    def _save_config(self) -> None:
        cfg = self.config_model
        cfg.x = self.x.get()
        cfg.y = self.y.get()
        cfg.width = self.width.get()
        cfg.height = self.height.get()
        cfg.fps = self.fps.get()
        cfg.extra["source_mode"] = self.source_mode.get()
        cfg.extra["video_path"] = self.video_path.get()
        cfg.extra["output_mode"] = self.output_mode.get()
        cfg.extra["play_preset_level"] = self.play_preset_level.get()
        cfg.extra["six_axis_intensity"] = self.six_axis_intensity.get()
        cfg.extra["six_axis_jitter_reduction"] = self.six_axis_jitter_reduction.get()
        cfg.extra["six_axis_sensitivity_level"] = self.six_axis_sensitivity_level.get()
        cfg.extra["show_more_settings"] = self.show_more_settings.get()
        cfg.extra["six_axis_gains"] = {
            axis: self.six_axis_gain_vars[axis].get()
            for axis in ("L1", "L2", "R0", "R1", "R2")
        }
        cfg.extra["six_axis_inverts"] = {
            axis: self.six_axis_invert_vars[axis].get()
            for axis in ("L1", "L2", "R0", "R1", "R2")
        }
        cfg.extra["enable_l0_jitter_guard"] = self.enable_l0_jitter_guard.get()
        cfg.extra["l0_guard_strength"] = self.l0_guard_strength.get()
        cfg.extra["enable_extreme_reset"] = self.enable_extreme_reset.get()
        cfg.extra["extreme_hold_ms"] = self.extreme_hold_ms.get()
        cfg.extra["enable_endpoint_guard"] = self.enable_endpoint_guard.get()
        cfg.extra["endpoint_margin_pct"] = self.endpoint_margin_pct.get()
        cfg.extra["pose_dance_analysis"] = self.pose_l0_analysis.get() or self.pose_six_axis_analysis.get()
        cfg.extra["pose_l0_analysis"] = self.pose_l0_analysis.get()
        cfg.extra["pose_six_axis_analysis"] = self.pose_six_axis_analysis.get()
        cfg.extra["pose_l0_weight"] = self.pose_l0_weight.get()
        cfg.extra["pose_six_axis_weight"] = self.pose_six_axis_weight.get()
        cfg.extra["l0_travel_scale"] = self.l0_travel_scale.get()
        cfg.extra["compression_latency"] = max(-5, min(5, int(self.compression_latency.get())))
        cfg.extra["measure_axis"] = self.measure_axis.get()
        cfg.extra["measure_value"] = self.measure_value.get()
        cfg.extra["measure_live"] = self.measure_live.get()
        cfg.min_value = self.min_value.get()
        cfg.max_value = self.max_value.get()
        cfg.axis_limits = {
            axis: [self.axis_min_vars[axis].get(), self.axis_max_vars[axis].get()]
            for axis in SIX_AXES
        }
        cfg.smoothing = self.smoothing.get()
        cfg.enable_smoothing = self.enable_smoothing.get()
        cfg.deadzone = self.deadzone.get()
        cfg.enable_deadzone = self.enable_deadzone.get()
        cfg.tracker_mode = self._tracker_internal(self.tracker_mode.get())
        cfg.extra["ui_language"] = self.ui_language
        cfg.response_curve = self.response_curve.get()
        cfg.motion_gain = self.motion_gain.get()
        cfg.visual_stroke_scale = self.visual_stroke_scale.get()
        cfg.global_travel_scale = self.global_travel_scale.get()
        cfg.min_activity = self.min_activity.get()
        cfg.enable_activity_gate = self.enable_activity_gate.get()
        cfg.max_step = self.max_step.get()
        cfg.enable_speed_limit = self.enable_speed_limit.get()
        cfg.idle_mode = self.idle_mode.get()
        cfg.invert = self.invert.get()
        cfg.enable_startup_ramp = self.enable_startup_ramp.get()
        cfg.startup_ramp_ms = self.startup_ramp_ms.get()
        cfg.axis = self.axis.get()
        cfg.output_interval_ms = self.interval_ms.get()
        cfg.serial_port = self.serial_port.get()
        cfg.baudrate = self.baudrate.get()
        cfg.ble_name = self.ble_name.get()
        cfg.ble_address = self.ble_address.get()
        cfg.ble_service_uuid = self.ble_service_uuid.get()
        cfg.ble_write_uuid = self.ble_write_uuid.get()
        cfg.last_sink = self.sink_type.get()
        cfg.audio_mode = self.audio_mode.get()
        cfg.audio_gain = self.audio_gain.get()
        cfg.audio_threshold = self.audio_threshold.get()
        cfg.audio_smoothing = self.audio_smoothing.get()
        cfg.audio_device = self.audio_device.get()
        cfg.save()

    def on_close(self) -> None:
        if self._config_save_after_id is not None:
            try:
                self.after_cancel(self._config_save_after_id)
            except tk.TclError:
                pass
            self._config_save_after_id = None
        self._save_config()
        self.stop()
        self.preview_bridge.stop()
        self.disconnect_sink()
        self.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(prog="osr6-realtime", description="OSR6 Realtime Screen TCode GUI")
    parser.add_argument("--auto-connect", action="store_true", help="Connect to the selected serial device at startup")
    parser.add_argument("--center", action="store_true", help="Send center command after auto-connect")
    parser.add_argument("--language", choices=("auto", "zh", "cn", "en"), default="auto", help="Interface language override")
    args = parser.parse_args()
    app = OsrScreenApp(auto_connect=args.auto_connect, center_on_connect=args.center, ui_language=args.language)
    app.mainloop()

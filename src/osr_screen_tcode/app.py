from __future__ import annotations

import asyncio
import argparse
from collections.abc import Callable
from collections import deque
from dataclasses import replace
import ctypes
import os
import queue
import re
import sys
import locale
import threading
import time
import urllib.request
import zipfile
from pathlib import Path


from .screen_geometry import configure_dpi_awareness, physical_cursor_position, place_physical_window, move_physical_window


def _configure_windows_dpi_awareness() -> None:
    configure_dpi_awareness()


_configure_windows_dpi_awareness()

from .gpu_runtime import activate_local_runtime

activate_local_runtime()

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import cv2
import numpy as np
from PIL import Image, ImageTk

from .analyzer import SIX_AXES, RealtimeAnalyzer
from .audio import AudioAnalyzer, AudioCapture, list_audio_devices
from . import APP_NAME, __version__
from .capture import LatestScreenCapture, ScreenCapture, ScreenRegion, capture_fps, validate_region
from .region_selector import ScreenRegionSelector, TEXT as REGION_TEXT
from .pose_output import rtm_rotation_amplitudes, rtm_l0_amplitude
from .output_curve import OutputCurveFilter
from .config import (
    AppConfig,
    DEFAULT_AXIS_OUTPUT_INVERTS,
    DEFAULT_SIX_AXIS_GAINS,
    DEFAULT_SIX_AXIS_INVERTS,
    DEFAULT_SIX_AXIS_TRAVEL_SCALES,
    RTM_POSE_2D_MODE,
    RTM_POSE_3D_MODE,
    RTM_POSE_MODE,
    HYBRID_MODE, HYBRID_V2_MODE, STROKE_CYCLE_MODE, normalize_visual_settings,
)
from .analysis_preferences import AnalysisPreferences, defaults as analysis_defaults, load_profiles
from .integrated_preview import IntegratedPreview
from .preview import PreviewBridge
from .visual_pipeline import LabAnalyzer, VisualFrame, VisualSettings, make_analyzer
from .visual_lab.stabilizer import Options
from .device_controls import DeviceControls
from .gpu_controls import GpuControls
from .ui_widgets import WideCombobox, monitor_workarea
from .recorder import MultiAxisFunscriptRecorder
from .sinks import (
    OutputWriteError,
    BleSink,
    LogSink,
    SerialSink,
    choose_best_serial_port,
    extract_serial_device,
    list_serial_port_infos,
    scan_ble_devices,
)
from .tcode import MultiAxisSafeOutput


RTM_POSE_2D_MODEL_URL = "https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/rtmpose-s_simcc-body7_pt-body7_420e-256x192-acd4a1ef_20230504.zip"
RTM_POSE_2D_MODEL_NAME = "rtmpose-s_simcc-body7_pt-body7_420e-256x192-acd4a1ef_20230504.onnx"


TRACKER_MODE_CHOICES = (
    STROKE_CYCLE_MODE,
    RTM_POSE_2D_MODE,
    HYBRID_V2_MODE,
    HYBRID_MODE,
    "Stroke Phase（内测用）",
    "Motion Center（内测用）",
    "Optical Flow（内测用）",
    "Hybrid Motion（内测用）",
    "Activity Pulse（内测用）",
)

TRACKER_MODE_EN = {
    STROKE_CYCLE_MODE: "Full/Half Travel (Hybrid Analysis)",
    HYBRID_MODE: "Hybrid Analysis (Recommended - Large Planar Motion)",
    RTM_POSE_2D_MODE: "RTM Pose 2D (Recommended - Dance)",
    HYBRID_V2_MODE: "Hybrid Analysis v2 (Recommended - Non-Dance)",
    "Stroke Phase（内测用）": "Stroke Phase (Beta)",
    "Motion Center（内测用）": "Motion Center (Beta)",
    "Optical Flow（内测用）": "Optical Flow (Beta)",
    "Hybrid Motion（内测用）": "Hybrid Motion (Beta)",
    "Activity Pulse（内测用）": "Activity Pulse (Beta)",
}

UI_TEXT_EN = {
    "采集帧率 FPS": "Capture FPS",
    "输出曲线拟合": "Output Curve Smoothing",
    "六轴模式只建议在光线好、主体清晰、框选区域干净时使用。": "Use Six Axis only with good lighting, a clear subject, and a clean selected region.",
    "第一次正式使用前，请先用测量模式保存适合自己的安全上限/下限。": "Before real use, save comfortable safe upper/lower limits in measurement mode.",
    "中文": "Chinese",
    "英文": "English",
    "界面语言": "Interface language",
    "五档预设": "Play Preset",
    "仅调整最终输出幅度": "Final output travel only",
    "急停回中": "Emergency Center",
    "全行程": "Full Travel",
    "连接并回中": "Connect + Center",
    "连接中...": "Connecting...",
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
    "声音监听": "Audio Only",
    "声音分析": "Audio Analysis",
    "声音设备": "Audio Device",
    "刷新": "Refresh",
    "声音增益": "Audio Gain",
    "声音门槛": "Audio Threshold",
    "声音平滑": "Audio Smoothing",
    "选择 Audio Only 后只监听声音，不读取屏幕画面。": "Audio Only listens to sound without reading the screen.",
    "高级参数": "Advanced",
    "输出模式": "Output Mode",
    "分析模式": "Analysis Mode",
    "间隔 ms": "Interval ms",
    "到达时间下限 ms": "Minimum arrival time (ms)",
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
    "反转": "Invert",
    "一键稳态 L0": "Stable L0 Preset",
    "连接设备": "Device Connection",
    "输出": "Output",
    "串口": "Serial Port",
    "波特率": "Baudrate",
    "自动检测 SR6/OSR6": "Auto Detect SR6/OSR6",
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
    "SR6/OSR6 六轴轻测": "SR6/OSR6 Six-Axis Test",
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
    "展开六轴单轴行程倍率": "Show Per-Axis Travel Scale",
    "收起六轴单轴行程倍率": "Hide Per-Axis Travel Scale",
    "L1 行程倍率": "L1 Travel Scale",
    "L2 行程倍率": "L2 Travel Scale",
    "R0 行程倍率": "R0 Travel Scale",
    "R1 行程倍率": "R1 Travel Scale",
    "R2 行程倍率": "R2 Travel Scale",
    "Pose 倾向": "Pose Bias",
    "Pose 倾向 L0": "Pose Bias for L0",
    "Pose L0 权重": "Pose L0 Weight",
    "Pose 倾向六轴": "Pose Bias for Six Axis",
    "Pose 六轴权重": "Pose Six-Axis Weight",
    "基础分析 L0 权重": "Base L0 Weight",
    "基础分析六轴权重": "Base Six-Axis Weight",
    "Pose v2 舞蹈六轴测试": "Pose v2 Dance Six-Axis Test",
    "Pose v2 倾向 L0": "Pose v2 Bias for L0",
    "Pose v2 L0 权重": "Pose v2 L0 Weight",
    "Pose v2 倾向六轴": "Pose v2 Bias for Six Axis",
    "Pose v2 六轴权重": "Pose v2 Six-Axis Weight",
    "基础分析 v2 L0 权重": "Base v2 L0 Weight",
    "基础分析 v2 六轴权重": "Base v2 Six-Axis Weight",
    "RTM Pose 骨架标注": "RTM Pose Skeleton Overlay",
    "RTM Pose 模型": "RTM Pose Model",
    "混合分析 L0 权重": "Hybrid L0 Weight",
    "当前本模型分析权重": "Current Model Analysis Weight",
    "RTM GPU 加速": "RTM GPU Acceleration",
    "RTM GPU 状态：CPU": "RTM GPU Status: CPU",
    "RTM GPU 状态：检测中...": "RTM GPU Status: checking...",
    "RTM GPU 状态：CUDA 可用": "RTM GPU Status: CUDA available",
    "RTM GPU 状态：未检测到 CUDA，自动使用 CPU": "RTM GPU Status: CUDA not detected, using CPU",
    "RTM 光流辅助": "RTM Optical Flow Assist",
    "RTM 卡尔曼融合": "RTM Kalman Fusion",
    "基础分析 RTM 权重": "Base RTM Weight",
    "选择模型": "Choose Model",
    "下载模型": "Download Model",
    "下载/自动检测模型": "Download / Auto Detect Model",
    "下载中...": "Downloading...",
    "自动检测到模型": "Model auto detected",
    "未检测到模型，开始下载...": "No model detected. Downloading...",
    "模型不匹配": "Model Mismatch",
    "请先选择或下载正确的 RTM Pose 模型。": "Choose or download the correct RTM Pose model first.",
    "模型下载中...": "Downloading model...",
    "模型下载完成": "Model downloaded",
    "模型下载失败": "Model download failed",
    "来源：OpenMMLab MMPose / rtmlib，需要本地 ONNX 模型。": "Source: OpenMMLab MMPose / rtmlib. Requires a local ONNX model.",
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
    "六轴辅助调节（仅混合分析推荐）": "Six-Axis Tuning (Hybrid Analysis Only)",
    "展开测量模式和轴上下限": "Show Measurement + Axis Limits",
    "收起测量模式和轴上下限": "Hide Measurement + Axis Limits",
    "展开六轴辅助调节（仅混合分析）": "Show Six-Axis Tuning (Hybrid Only)",
    "收起六轴辅助调节（仅混合分析）": "Hide Six-Axis Tuning (Hybrid Only)",
    "展开 RTM Pose 模型设置": "Show RTM Pose Model Settings",
    "收起 RTM Pose 模型设置": "Hide RTM Pose Model Settings",
    "总强度": "Overall Strength",
    "六轴降抖": "Six-Axis Stabilizer",
    "一键稳六轴": "Stable Six-Axis Preset",
    "六轴敏感度": "Six-Axis Sensitivity",
    "反": "Inv",
    "这组滑块只推荐用于混合分析（推荐-非舞蹈）；RTM Pose 输出不会接入这里。": "Recommended only for Hybrid Analysis (Recommended - Non-Dance). RTM Pose output does not use these sliders.",
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
    "上限方向": "Upper",
    "下限方向": "Lower",
    "脚本曲线": "Script Curve",
    "最近12秒 / 实际输出": "Last 12s / Real Output",
    "开始输出后显示曲线": "Curve appears after output starts",
    "设备": "Device",
    "已连接": "Connected",
    "未连接": "Not connected",
    "日志模式": "Log mode",
    "连接失败": "Connection failed",
    "连接超时": "Connection timed out",
    "已连接并回中": "Connected and centered",
    "回中失败": "Center failed",
    "正在连接，请稍候...": "Connecting, please wait...",
    "正在连接，连接成功后会开始实时输出": "Connecting. Realtime output will start after the device connects.",
    "正在连接，连接成功后请再试一次。": "Connecting. Try again after the connection succeeds.",
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
    "SR6/OSR6 六轴轻测中": "SR6/OSR6 six-axis test running",
    "SR6/OSR6 六轴轻测完成，已回中": "SR6/OSR6 six-axis test complete, centered",
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
    "向下限移动": "Moving toward lower",
    "向上限移动": "Moving toward upper",
    "下限端点": "Lower endpoint",
    "上限端点": "Upper endpoint",
}

UI_TEXT_EN.update(REGION_TEXT)
UI_TEXT_REVERSE_EN = {value: key for key, value in UI_TEXT_EN.items()}


TOOLTIPS = {
    "五档预设": "仅设置最终脚本与实时输出的行程倍率：1–5 档为 0.55 / 0.75 / 1 / 1.15 / 1.30；不改变分析方法、识别参数或骨架处理。",
    "仅调整最终输出幅度": "对录制、导出脚本和实时输出生效；原始分析结果不变，现有输出限位与限速继续有效。",
    "急停回中": "立即停止实时输出，并把当前启用的轴回到中间位置。",
    "全行程": "把 L0 切到更大更快的全行程测试参数。",
    "连接并回中": "连接当前选择的设备，并发送回中命令。",
    "连接中...": "正在连接设备；如果端口异常，窗口也会保持可操作。",
    "开始实时输出前确认": "启动设备前最后确认输出模式和上下限。",
    "L0 Only：只上下": "只输出 L0 上下轴，最适合先测试。",
    "Six Axis：六轴": "同时输出 L0/L1/L2/R0/R1/R2。",
    "确认开始": "按当前选择的模式开始实时输出。",
    "取消": "关闭当前确认窗口，不启动输出。",
    "连接设备": "选择 USB 串口或 BLE，并连接 SR6/OSR6 控制器。",
    "输出": "选择只看日志、USB 串口或 BLE UART 输出。",
    "串口": "USB 或蓝牙串口号，例如 COMx。",
    "刷新": "重新扫描电脑上的串口或声音设备。",
    "波特率": "串口通信速度；OSR 常见为 115200。",
    "自动检测 SR6/OSR6": "从可用串口里猜测最可能的 SR6/OSR6 控制口。",
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
    "SR6/OSR6 六轴轻测": "逐个轻微测试 L0/L1/L2/R0/R1/R2。",
    "开始实时输出": "开始读取输入来源并控制设备。",
    "恢复所有默认设置": "把所有参数恢复到新安装时的默认值；点击后会先二次确认。",
    "显示预览": "打开 3D 模拟器，显示最终输出指令的运动。画面与骨架在分析预览页；模拟器不是硬件反馈。",
    "取消预览": "关闭预览同步；已打开的浏览器页可直接关掉。",
    "停止": "停止实时输出，保持连接。",
    "安全预设": "更慢、更小幅，适合初次测试。",
    "标准预设": "日常推荐的折中参数。",
    "混合分析灵敏": "使用混合分析，并提高跟手程度。",
    "六轴独立上下限": "分别限制每个轴的物理输出范围。",
    "总行程倍率": "围绕中点缩放所有轴行程，不会越过每轴上下限。",
    "L0 总行程倍率": "只缩放 L0 上下轴行程，不改变 L0 的机械上下限。",
    "六轴总行程倍率": "只缩放 L1/L2/R0/R1/R2 辅助轴行程，不影响 L0。",
    "展开六轴单轴行程倍率": "展开后可以分别缩放 L1/L2/R0/R1/R2；最终幅度 = 六轴总行程倍率 × 单轴倍率。",
    "收起六轴单轴行程倍率": "收起 L1/L2/R0/R1/R2 单轴行程倍率。",
    "L1 行程倍率": "L1 前后轴的单独行程倍率，会再乘以六轴总行程倍率。",
    "L2 行程倍率": "L2 左右轴的单独行程倍率，会再乘以六轴总行程倍率。",
    "R0 行程倍率": "R0 扭转轴的单独行程倍率，会再乘以六轴总行程倍率。",
    "R1 行程倍率": "R1 横滚轴的单独行程倍率，会再乘以六轴总行程倍率。直接 Pose 额外随最终 L0 收拢：底部至 2/3 为 1 倍，顶部为 0.5 倍。",
    "R2 行程倍率": "R2 俯仰轴的单独行程倍率，会再乘以六轴总行程倍率。直接 Pose 额外随最终 L0 收拢：底部至 2/3 为 1 倍，顶部为 0.5 倍。",
    "轴": "当前要查看或调整的 TCode 通道。",
    "测量模式": "用滑块手动遥控单个轴，方便保存安全上下限。",
    "滑动即发送": "打开后拖动测量滑块会立刻发送到设备。",
    "位置": "当前手动发送的 TCode 位置值。",
    "发送当前位置": "把测量滑块的位置发送给当前轴。",
    "保存为下限": "把当前测量位置保存为该轴下限。",
    "当前轴回中": "把当前测量轴发送到 5000。",
    "保存为上限": "把当前测量位置保存为该轴上限。",
    "六轴辅助调节（仅混合分析推荐）": "只推荐用于混合分析（推荐-非舞蹈）的 L1/L2/R0/R1/R2 辅助微调；RTM Pose 不接入这里。",
    "展开测量模式和轴上下限": "展开测量模式和每个轴的安全上下限。",
    "收起测量模式和轴上下限": "收起测量模式和每个轴的安全上下限。",
    "展开六轴辅助调节（仅混合分析）": "展开混合分析用的六轴辅助微调。",
    "收起六轴辅助调节（仅混合分析）": "收起混合分析用的六轴辅助微调。",
    "展开 RTM Pose 模型设置": "展开 RTM Pose 的模型路径、模型下载和来源说明。只有选择 RTM Pose 2D 舞蹈模式时才显示。",
    "收起 RTM Pose 模型设置": "收起 RTM Pose 模型设置，保持主界面更清爽。",
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
    "声音监听": "只根据声音强度或节拍输出 L0。",
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
    "Pose 倾向 L0": "根据姿态关键点分析运动，减少横向变化被误判为纵向变化。",
    "Pose 倾向六轴": "让横摆、扭腰、重复舞蹈更多体现在 L1/L2/R0/R1/R2 上。",
    "Pose L0 权重": "越大越偏向完整人物舞蹈/扭腰横摆理解，L0 越不容易把左右摆动误判成上下。",
    "Pose 六轴权重": "越大越像显示完整人物的舞蹈，横摆、扭腰和身体角度会更多分配给六轴辅助。",
    "基础分析 L0 权重": "显示 L0 基础分析方法还占多少。开启 Pose 倾向 L0 时等于 100 - Pose L0 权重；关闭时为 100%。",
    "基础分析六轴权重": "显示六轴基础分析方法还占多少。开启 Pose 倾向六轴时等于 100 - Pose 六轴权重；关闭时为 100%。",
    "Pose v2 舞蹈六轴测试": "测试版功能：在压缩延迟后的分析画面中拟合胯部平行四边形，用它的中心、角度、边长和面积辅助输出六轴。关闭后完全使用原逻辑。",
    "Pose v2 倾向 L0": "启用 Pose v2 对 L0 的辅助权重。开启 V2 时会自动关闭 V1 Pose 倾向。",
    "Pose v2 倾向六轴": "启用 Pose v2 对 L1/L2/R0/R1/R2 的辅助权重。开启 V2 时会自动关闭 V1 Pose 倾向。",
    "Pose v2 L0 权重": "越大越偏向 Pose v2 的胯部上下判断；建议先保持较低或关闭，保护原 L0 稳定手感。",
    "Pose v2 六轴权重": "越大越偏向 Pose v2 的胯部核心区、平行四边形和防卡边判断。",
    "基础分析 v2 L0 权重": "显示 L0 基础分析方法还占多少。开启 Pose v2 倾向 L0 时等于 100 - Pose v2 L0 权重；关闭时为 100%。",
    "基础分析 v2 六轴权重": "显示六轴基础分析方法还占多少。开启 Pose v2 倾向六轴时等于 100 - Pose v2 六轴权重；关闭时为 100%。",
    "RTM Pose 骨架标注": "测试版舞蹈模式：使用 RTM Pose 感知到的人体骨架做标注和输出。只在选择 RTM Pose 2D 舞蹈模式时启用。",
    "RTM Pose 模型": "选择本地 256x192 RTMPose 2D ONNX 模型；没有有效模型时不能开始 RTM 分析。",
    "基础分析 RTM 权重": "RTM Pose 是独立舞蹈模式，不接入混合分析权重。",
    "混合分析 L0 权重": "勾选后才会额外运行混合分析，只把它的 L0 按这个权重混入 RTM；不勾选时 RTM 保持 100% 模型并节省算力。",
    "当前本模型分析权重": "显示当前 RTM 模型在 L0 中占多少；未勾选混合分析时为 100%。",
    "RTM GPU 加速": "默认关闭。CUDA 适用于 NVIDIA，运行库较大；DirectML 支持 DirectX 12 的 AMD/NVIDIA/Intel，运行库较小。两者使用同一模型，准确度需同视频对比，不保证 CUDA 必然更准确。后台检测/安装，失败回退 CPU；安装或切换运行库需重启。",
    "RTM 光流辅助": "默认开启。用上一帧骨架关键点在新画面里做轻量追踪，补足两次模型检测之间的运动。",
    "RTM 卡尔曼融合": "默认开启。用光流作为预测，用 RTM 检测点作为观测进行融合，减少关键点跳动。",
    "反转": "反转这个输出方向；只改变最终轴方向，不改变识别算法。",
    "框选屏幕区域": "启动前重新选择实时读取范围，减少无关画面干扰。",
    "FPS": "每秒分析帧数，越高越跟手也越吃性能。",
    "间隔 ms": "TCode 命令的 I 时间，通常和输出刷新速度相关。",
    "到达时间下限 ms": "TCode 的最短到达时间。运行时还会参考实际更新间隔，接近上下限时可进一步延长；不是发送频率设置。",
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
    "五档预设": "Set final script and live output travel to 0.55 / 0.75 / 1 / 1.15 / 1.30. Analysis mode, recognition settings and pose processing stay unchanged.",
    "仅调整最终输出幅度": "Applies to recording, exported scripts and live output. Raw analysis is unchanged; output limits and speed caps still apply.",
    "急停回中": "Stop realtime output immediately and move active axes back to center.",
    "全行程": "Use larger and faster L0 travel for full-range testing.",
    "连接并回中": "Connect the selected device and send a center command.",
    "连接中...": "Connecting in the background; the window stays usable if the port is bad.",
    "开始实时输出前确认": "Final check for output mode and limits before starting.",
    "L0 Only：只上下": "Only output the L0 vertical axis. Best for first tests.",
    "Six Axis：六轴": "Output L0/L1/L2/R0/R1/R2 together.",
    "确认开始": "Start realtime output with the selected settings.",
    "取消": "Close this dialog without starting output.",
    "连接设备": "Choose USB serial or BLE, then connect the SR6/OSR6 controller.",
    "输出": "Choose log-only, USB serial, or BLE UART output.",
    "串口": "USB or Bluetooth serial port, such as COMx.",
    "刷新": "Scan serial or audio devices again.",
    "波特率": "Serial speed. OSR devices commonly use 115200.",
    "自动检测 SR6/OSR6": "Pick the serial port that most likely belongs to SR6/OSR6.",
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
    "SR6/OSR6 六轴轻测": "Lightly test L0/L1/L2/R0/R1/R2 one by one.",
    "开始实时输出": "Start reading the selected input and controlling the device.",
    "恢复所有默认设置": "Restore factory defaults after a confirmation prompt.",
    "显示预览": "Open the 3D simulator for final output commands. Frames and skeletons are in Analysis Preview; the simulator is not hardware feedback.",
    "取消预览": "Stop preview sync. You can close the browser preview window.",
    "停止": "Stop realtime output while keeping the device connection.",
    "安全预设": "Slower and smaller motion, useful for first tests.",
    "标准预设": "Balanced daily settings.",
    "混合分析灵敏": "Use Hybrid Analysis with more direct response.",
    "六轴独立上下限": "Limit each physical axis separately.",
    "总行程倍率": "Scale all axis travel around center without crossing saved limits.",
    "L0 总行程倍率": "Scale only L0 travel without changing its mechanical limits.",
    "六轴总行程倍率": "Scale L1/L2/R0/R1/R2 travel without affecting L0.",
    "展开六轴单轴行程倍率": "Adjust L1/L2/R0/R1/R2 separately. Final travel = Six-Axis Travel Scale x per-axis scale.",
    "收起六轴单轴行程倍率": "Hide per-axis travel scales for L1/L2/R0/R1/R2.",
    "L1 行程倍率": "Per-axis travel scale for L1 surge, multiplied by the six-axis travel scale.",
    "L2 行程倍率": "Per-axis travel scale for L2 sway, multiplied by the six-axis travel scale.",
    "R0 行程倍率": "Per-axis travel scale for R0 twist, multiplied by the six-axis travel scale.",
    "R1 行程倍率": "Per-axis R1 roll scale, multiplied by six-axis travel. Direct Pose also contracts it with final L0: 1x from bottom through 2/3, then 0.5x at the top.",
    "R2 行程倍率": "Per-axis R2 pitch scale, multiplied by six-axis travel. Direct Pose also contracts it with final L0: 1x from bottom through 2/3, then 0.5x at the top.",
    "轴": "The TCode channel being viewed or adjusted.",
    "测量模式": "Manually control one axis with a slider and save safe limits.",
    "滑动即发送": "Send commands immediately while dragging the measurement slider.",
    "位置": "Current manual TCode position.",
    "发送当前位置": "Send the measurement slider value to the selected axis.",
    "保存为下限": "Save the current measurement value as this axis lower limit.",
    "当前轴回中": "Move the selected measurement axis to 5000.",
    "保存为上限": "Save the current measurement value as this axis upper limit.",
    "六轴辅助调节（仅混合分析推荐）": "Tune L1/L2/R0/R1/R2 for Hybrid Analysis only. RTM Pose does not use these controls.",
    "展开测量模式和轴上下限": "Show measurement mode and per-axis safety limits.",
    "收起测量模式和轴上下限": "Hide measurement mode and per-axis safety limits.",
    "展开六轴辅助调节（仅混合分析）": "Show six-axis helper tuning for Hybrid Analysis.",
    "收起六轴辅助调节（仅混合分析）": "Hide six-axis helper tuning for Hybrid Analysis.",
    "展开 RTM Pose 模型设置": "Show RTM Pose model path, download, and source details. Only visible in RTM Pose 2D dance modes.",
    "收起 RTM Pose 模型设置": "Hide RTM Pose model settings to keep the main controls cleaner.",
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
    "声音监听": "Output L0 from audio level or rhythm only.",
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
    "基础分析 L0 权重": "Shows how much the original L0 analysis still contributes. With Pose L0 enabled, it is 100 minus Pose L0 weight; when disabled, it is 100%.",
    "基础分析六轴权重": "Shows how much the original six-axis analysis still contributes. With Pose Six-Axis enabled, it is 100 minus Pose Six-Axis weight; when disabled, it is 100%.",
    "Pose v2 舞蹈六轴测试": "Test feature: fits a hip-plane parallelogram on the frame after Compression / Latency, then uses its center, angle, edge length, and area to assist six-axis output. Turn it off to use the original logic.",
    "Pose v2 倾向 L0": "Enable Pose v2 assist for L0. Turning on V2 automatically turns off V1 Pose bias.",
    "Pose v2 倾向六轴": "Enable Pose v2 assist for L1/L2/R0/R1/R2. Turning on V2 automatically turns off V1 Pose bias.",
    "Pose v2 L0 权重": "Higher values favor Pose v2 hip vertical tracking. Start low or leave it off to preserve stable L0 behavior.",
    "Pose v2 六轴权重": "Higher values favor Pose v2 hip-core, parallelogram, and anti-stuck side-axis tracking.",
    "基础分析 v2 L0 权重": "Shows how much the original L0 analysis still contributes. With Pose v2 L0 enabled, it is 100 minus Pose v2 L0 weight; when disabled, it is 100%.",
    "基础分析 v2 六轴权重": "Shows how much the original six-axis analysis still contributes. With Pose v2 Six-Axis enabled, it is 100 minus Pose v2 Six-Axis weight; when disabled, it is 100%.",
    "RTM Pose 骨架标注": "Test dance mode: uses the skeleton perceived by RTM Pose for overlay and output. Only active in RTM Pose 2D dance modes.",
    "RTM Pose 模型": "Select a local 256x192 RTMPose 2D ONNX model. RTM analysis requires a valid model.",
    "基础分析 RTM 权重": "RTM Pose is a separate dance mode and does not use Hybrid Analysis weighting.",
    "混合分析 L0 权重": "When checked, Hybrid Analysis runs only for L0 and is mixed into RTM by this weight. When unchecked, RTM stays 100% model-driven and saves CPU.",
    "当前本模型分析权重": "Shows how much RTM model analysis currently contributes to L0. It is 100% when Hybrid L0 is unchecked.",
    "RTM GPU 加速": "Off by default. CUDA (NVIDIA) has larger runtime libraries; DirectML (DirectX 12 AMD/NVIDIA/Intel) has smaller ones. Both use the same model; compare the same video before claiming an accuracy advantage. Background checks/install; CPU fallback on failure. Restart after runtime installation or switching.",
    "RTM 光流辅助": "On by default. Tracks the previous skeleton keypoints in the next frame to fill motion between model detections.",
    "RTM 卡尔曼融合": "On by default. Uses optical flow as prediction and RTM detections as observations to reduce keypoint jitter.",
    "反转": "Invert this output direction. It changes the final axis direction only, not the recognition algorithm.",
    "框选屏幕区域": "Select the realtime capture region before starting.",
    "FPS": "Frames analyzed per second. Higher is more responsive and uses more CPU.",
    "间隔 ms": "The TCode I time, usually related to output refresh speed.",
    "到达时间下限 ms": "Minimum TCode arrival time. Actual update cadence and endpoint slowdown can extend it; this does not set the send frequency.",
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
        x, y = (physical_cursor_position() if sys.platform.startswith("win") else
                (self.widget.winfo_pointerx(), self.widget.winfo_pointery()))
        x, y = x + 14, y + 14
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
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
        self.window.update_idletasks()
        width, height = self.window.winfo_reqwidth(), self.window.winfo_reqheight()
        left, top, right, bottom = monitor_workarea(self.widget)
        place_physical_window(self.window, dict(left=max(left, min(x, right-width)),
            top=max(top, min(y, bottom-height)), width=width, height=height))

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


class OsrScreenApp(DeviceControls, GpuControls, tk.Tk):
    def __init__(
        self,
        auto_connect: bool = False,
        center_on_connect: bool = False,
        enforce_age_gate: bool = True,
        ui_language: str = "auto",
    ) -> None:
        super().__init__()
        self.ui_language = "en"
        self.title(f"{APP_NAME} v{__version__}")
        self.geometry("1040x700")
        self.minsize(960, 620)
        if enforce_age_gate and not os.environ.get("OSR_SCREEN_TCODE_SKIP_AGE_GATE"):
            self._confirm_adult_use_or_exit()

        self.config_model = AppConfig.load()
        self.ui_language = self._choose_ui_language(ui_language)
        self.config_model.extra["ui_language"] = self.ui_language
        self.frame_queue: queue.Queue[dict[str, object]] = queue.Queue(maxsize=3)
        self.control_queue: queue.SimpleQueue[dict[str, object]] = queue.SimpleQueue()
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None
        self._region_selector = None
        self._input_widgets = []
        self._region_busy = None
        self._active_screen_region = None
        self._video_worker: threading.Thread | None = None
        self._video_cancel = threading.Event()
        self.sink = LogSink()
        self.preview_bridge = PreviewBridge()
        self._output_context = threading.local()
        self.connected = False
        self._connecting = False
        self._connect_worker: threading.Thread | None = None
        self._connect_attempt_id = 0
        self._start_after_connect = False
        self.auto_connect = auto_connect
        self.center_on_connect = center_on_connect
        self._config_save_after_id: str | None = None
        self._config_autosave_suspended = False
        self.preview_image: ImageTk.PhotoImage | None = None
        self.preview_canvas_image: int | None = None
        self._visual_generation = 0
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
        elif self.config_model.last_sink in ("Serial COM", "USB Serial"):
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
        dialog.title("Simulation Test / 模拟测试")
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)

        body = tk.Frame(dialog, padx=22, pady=18)
        body.pack(fill="both", expand=True)
        tk.Label(
            body,
            text="SIMULATION TEST",
            font=("TkDefaultFont", 18, "bold"),
            foreground="#8a1f11",
        ).pack(anchor="w")
        tk.Label(
            body,
            text="模拟测试确认 / Simulation test notice",
            font=("TkDefaultFont", 11),
            foreground="#8a1f11",
        ).pack(anchor="w", pady=(2, 10))
        tk.Label(
            body,
            text=(
                "For visual-analysis and robot-arm simulation experiments.\n"
                "Physical robot-arm mapping is unverified. Start with Log only and no hardware. "
                "The preview is not sensor feedback.\n\n"
                "用于视觉分析与机械臂模拟实验。实际机械臂映射尚未验证；"
                "请先使用 Log only，不连接硬件。预览不代表传感器反馈。"
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
            text="Continue / 继续",
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
        left, top, right, bottom = monitor_workarea(self)
        x = left + max(0, (right-left-dialog.winfo_width()) // 2)
        y = top + max(0, (bottom-top-dialog.winfo_height()) // 2)
        move_physical_window(dialog, x, y)
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
        left, top, right, bottom = monitor_workarea(self)
        x = left + max(0, (right-left-dialog.winfo_width()) // 2)
        y = top + max(0, (bottom-top-dialog.winfo_height()) // 2)
        move_physical_window(dialog, x, y)
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
        value = self._normalize_tracker_mode(value)
        if self.ui_language != "en":
            return value
        return TRACKER_MODE_EN.get(value, value)

    def _tracker_internal(self, value: str) -> str:
        reverse = {display: internal for internal, display in TRACKER_MODE_EN.items()}
        return self._normalize_tracker_mode(reverse.get(value, value))

    def _set_tracker_mode(self, value: str) -> None:
        self.tracker_mode.set(self._tracker_display(value))

    def _active_rtm_pose_model_var(self, value: str | None = None) -> tk.StringVar:
        return self.rtm_pose_2d_model_path

    def _refresh_active_rtm_pose_model_path(self) -> None:
        if not hasattr(self, "rtm_pose_model_path"):
            return
        self._rtm_pose_model_path_syncing = True
        try:
            self.rtm_pose_model_path.set(self._active_rtm_pose_model_var().get())
        finally:
            self._rtm_pose_model_path_syncing = False

    def _store_active_rtm_pose_model_path(self) -> None:
        if self._rtm_pose_model_path_syncing or not hasattr(self, "rtm_pose_model_path"):
            return
        self._active_rtm_pose_model_var().set(self.rtm_pose_model_path.get())

    def _rtm_pose_mode_active(self, value: str | None = None) -> bool:
        return self._rtm_pose_2d_mode_active(value)

    def _rtm_pose_2d_mode_active(self, value: str | None = None) -> bool:
        raw_value = self.tracker_mode.get() if value is None else value
        return self._tracker_internal(raw_value) == RTM_POSE_2D_MODE

    def _pose_model_required(self, value=None, output_mode=None, v2_pose=None) -> bool:
        mode = self._tracker_internal(self.tracker_mode.get() if value is None else value)
        six = (self.output_mode.get() if output_mode is None else output_mode) == "Six Axis"
        enabled = self.hybrid_v2_pose_enabled.get() if v2_pose is None else v2_pose
        return mode == RTM_POSE_2D_MODE or (mode in (HYBRID_V2_MODE, STROKE_CYCLE_MODE) and six and enabled)

    def _rtm_pose_3d_mode_active(self, value: str | None = None) -> bool:
        return False  # Shared legacy UI helper; 3D is not an analysis mode.

    def _rtm_pose_model_dir(self) -> Path:
        return Path(__file__).resolve().parents[2] / "models"

    def _rtm_pose_model_spec(self, mode: str) -> tuple[str, str, int, int, str]:
        return (RTM_POSE_2D_MODEL_NAME, RTM_POSE_2D_MODEL_URL, 5_000_000, 2, "RTM Pose 2D")

    def _validate_rtm_pose_model_path(self, path_value: str, mode: str) -> tuple[bool, str]:
        model_name, _url, min_size, expected_outputs, label = self._rtm_pose_model_spec(mode)
        path_text = str(path_value or "").strip().strip('"')
        if not path_text:
            return False, f"{label} 需要先选择或下载模型。"
        path = Path(path_text)
        if not path.exists() or not path.is_file():
            return False, f"模型文件不存在：{path_text}"
        if path.suffix.lower() != ".onnx":
            return False, "请选择 .onnx 模型文件。"
        try:
            stat = path.stat()
        except OSError as exc:
            return False, f"无法读取模型文件：{exc}"
        if stat.st_size < min_size:
            return False, f"模型文件太小，可能下载不完整。当前模式需要 {model_name}。"

        cache = getattr(self, "_rtm_pose_model_validation_cache", None)
        if cache is None:
            cache = {}
            self._rtm_pose_model_validation_cache = cache
        try:
            cache_path = str(path.resolve())
        except OSError:
            cache_path = str(path)
        cache_key = (self._tracker_internal(mode), cache_path, int(stat.st_size), int(stat.st_mtime_ns))
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            import onnxruntime as ort

            session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
            output_count = len(session.get_outputs())
        except Exception as exc:
            result = (False, f"ONNX 模型无法读取：{exc}")
            cache[cache_key] = result
            return result

        if output_count != expected_outputs:
            result = (
                False,
                f"模型类型不匹配：当前文件有 {output_count} 个输出，{label} 需要 {expected_outputs} 个输出。请使用 {model_name}。",
            )
            cache[cache_key] = result
            return result

        result = (True, f"{label} 模型可用：{path.name}")
        cache[cache_key] = result
        return result

    def _find_existing_rtm_pose_model(self, mode: str) -> Path | None:
        model_name, _url, _min_size, _expected_outputs, _label = self._rtm_pose_model_spec(mode)
        model_dir = self._rtm_pose_model_dir()
        candidates = [model_dir / model_name]
        if model_dir.exists():
            candidates.extend(path for path in model_dir.glob("*.onnx") if path.name != model_name)
        for candidate in candidates:
            ok, _message = self._validate_rtm_pose_model_path(str(candidate), mode)
            if ok:
                return candidate
        return None

    def _apply_rtm_pose_model_path(self, path: str, mode: str, target_var: tk.StringVar | None = None) -> None:
        self.rtm_pose_2d_model_path.set(path)
        if target_var is not None:
            target_var.set(path)
        self._refresh_active_rtm_pose_model_path()

    def _ensure_rtm_pose_model_ready(self) -> bool:
        if not self._pose_model_required():
            return True
        mode = self._tracker_internal(self.tracker_mode.get())
        model_var = self._active_rtm_pose_model_var(mode)
        ok, message = self._validate_rtm_pose_model_path(model_var.get(), mode)
        if ok:
            self.rtm_model_download_status_text.set(message)
            return True

        detected = self._find_existing_rtm_pose_model(mode)
        if detected is not None:
            self._apply_rtm_pose_model_path(str(detected), mode)
            text = f"{self._t('自动检测到模型')}: {detected.name}"
            self.status.set(text)
            self.rtm_model_download_status_text.set(text)
            return True

        text = f"{self._t('请先选择或下载正确的 RTM Pose 模型。')}\n{message}"
        self.status.set(text)
        self.rtm_model_download_status_text.set(message)
        messagebox.showwarning(self._t("模型不匹配"), text)
        return False

    def _running_analysis_label(self) -> str:
        mode = self._tracker_display(self._tracker_internal(self.tracker_mode.get()))
        if self.ui_language == "en":
            return f"Running: {mode}"
        return f"正在以：{mode}：分析"

    def _refresh_start_button_text(self) -> None:
        if self.worker and self.worker.is_alive():
            self.start_button_text.set(self._running_analysis_label())
        else:
            self.start_button_text.set(self._t("开始实时输出"))

    def _on_tracker_mode_changed(self) -> None:
        is_rtm = self._rtm_pose_mode_active()
        if (self.worker and self.worker.is_alive()) or self._video_analysis_active():
            self.stop()
        self._analysis_preferences.switch(self._tracker_internal(self.tracker_mode.get()), self._analysis_variables())
        if hasattr(self, "integrated_preview"):
            self.reset_visual_reference()
            self.integrated_preview.refresh_mode()
        self.rtm_pose_3d_enabled.set(self._rtm_pose_3d_mode_active())
        self.rtm_pose_3d_weight.set(100 if is_rtm else 0)
        self._refresh_active_rtm_pose_model_path()
        self._refresh_pose_base_weight_texts()
        self._refresh_rtm_pose_3d_settings()
        self._refresh_hybrid_source()

    def _analysis_variables(self):
        return {name: getattr(self, name) for name in analysis_defaults("dance")}

    @staticmethod
    def _analysis_visibility(mode, blend_enabled, source_label, assist=None, blend_widgets=()):
        dance = mode == RTM_POSE_2D_MODE
        for widget in blend_widgets:
            widget.grid() if dance else widget.grid_remove()
        source_label.grid() if dance and blend_enabled else source_label.grid_remove()
        if assist is not None:
            assist.grid() if mode in (HYBRID_MODE, HYBRID_V2_MODE, STROKE_CYCLE_MODE) else assist.grid_remove()
            assist.configure(state="normal" if mode in (HYBRID_V2_MODE, STROKE_CYCLE_MODE) else "disabled")

    def _refresh_hybrid_source(self, *_args):
        if hasattr(self, "rtm_hybrid_source_label"):
            self._analysis_visibility(self._tracker_internal(self.tracker_mode.get()), self.rtm_hybrid_l0_enabled.get(),
                self.rtm_hybrid_source_label, blend_widgets=self._rtm_blend_widgets)

    @staticmethod
    def _normalize_tracker_mode(value: str) -> str:
        aliases = {
            "混合分析（内测）": HYBRID_MODE,
            "Hybrid Analysis (Internal Test)": HYBRID_MODE,
            "Hybrid Analysis (Recommended - Large Planar Motion)": HYBRID_MODE,
            "混合分析（推荐）": HYBRID_MODE,
            "Hybrid Analysis (Recommended)": HYBRID_MODE,
            "Hybrid Analysis (Recommended - Non-Dance)": HYBRID_MODE,
            "RTM Pose": RTM_POSE_2D_MODE,
            "RTM Pose（推荐-舞蹈）": RTM_POSE_2D_MODE,
            "RTM Pose 2D": RTM_POSE_2D_MODE,
            "RTM Pose 2D（推荐-舞蹈）": RTM_POSE_2D_MODE,
            "RTM Pose 2D (Recommended - Dance)": RTM_POSE_2D_MODE,
            "RTM Pose 3D": RTM_POSE_2D_MODE,
            "RTM Pose 3D（推荐-舞蹈）": RTM_POSE_2D_MODE,
            "RTM Pose 3D（高延迟-舞蹈）": RTM_POSE_2D_MODE,
            "RTM Pose (Recommended - Dance)": RTM_POSE_2D_MODE,
            "RTM Pose 3D (Higher Latency - Dance)": RTM_POSE_2D_MODE,
        }
        aliases.update({"混合分析（推荐-非舞蹈）": HYBRID_MODE, "混合分析 v2（画面运动 v2，仅 L0）": HYBRID_V2_MODE, "Hybrid Analysis v2 (Image Motion v2, L0 only)": HYBRID_V2_MODE, "混合分析v2": HYBRID_V2_MODE, "混合分析 v2": HYBRID_V2_MODE,
                        "Hybrid Analysis v2": HYBRID_V2_MODE})
        return aliases.get(value, value)

    def _startup_actions(self) -> None:
        if not self.auto_connect:
            return
        self.sink_type.set("Serial COM")
        if not self.serial_port.get():
            self.autodetect_device()
        self._start_connection_worker(center_after=self.center_on_connect)

    def _build_vars(self) -> None:
        cfg = self.config_model
        self.x = tk.IntVar(value=cfg.x)
        self.y = tk.IntVar(value=cfg.y)
        self.width = tk.IntVar(value=cfg.width)
        self.height = tk.IntVar(value=cfg.height)
        self._screen_region_snapshot = ScreenRegion(cfg.x, cfg.y, cfg.width, cfg.height)
        self._live_source_mode = cfg.extra.get("source_mode", "Screen")
        self.fps = tk.IntVar(value=cfg.fps)
        self._capture_target_fps = capture_fps(cfg.fps)
        self.fps.trace_add("write", self._capture_fps_changed)
        self.capture_rate_text = tk.StringVar(value="")
        self.output_curve_fitting = tk.BooleanVar(value=bool(cfg.extra.get("output_curve_fitting", True)))
        self.endpoint_slowdown_enabled = tk.BooleanVar(value=bool(cfg.extra.get("endpoint_slowdown_enabled", True)))
        self.endpoint_slowdown_pct = tk.DoubleVar(value=float(cfg.extra.get("endpoint_slowdown_pct", 10)))
        self._endpoint_options_changed()
        self.endpoint_slowdown_enabled.trace_add("write", self._endpoint_options_changed)
        self.endpoint_slowdown_pct.trace_add("write", self._endpoint_options_changed)
        self._output_curve_enabled = self.output_curve_fitting.get()
        self.output_curve_fitting.trace_add("write", self._output_curve_changed)
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
        self.l0_guard_strength = tk.DoubleVar(value=float(cfg.extra.get("l0_guard_strength", 0.70)))
        self.enable_extreme_reset = tk.BooleanVar(value=bool(cfg.extra.get("enable_extreme_reset", True)))
        self.extreme_hold_ms = tk.IntVar(value=int(cfg.extra.get("extreme_hold_ms", 850)))
        self.enable_endpoint_guard = tk.BooleanVar(value=bool(cfg.extra.get("enable_endpoint_guard", True)))
        self.endpoint_margin_pct = tk.IntVar(value=int(cfg.extra.get("endpoint_margin_pct", 10)))
        legacy_pose = bool(cfg.extra.get("pose_dance_analysis", False))
        self.pose_l0_analysis = tk.BooleanVar(value=bool(cfg.extra.get("pose_l0_analysis", legacy_pose)))
        self.pose_six_axis_analysis = tk.BooleanVar(value=bool(cfg.extra.get("pose_six_axis_analysis", legacy_pose)))
        self.pose_l0_weight = tk.IntVar(value=int(cfg.extra.get("pose_l0_weight", 60)))
        self.pose_six_axis_weight = tk.IntVar(value=int(cfg.extra.get("pose_six_axis_weight", 60)))
        self.pose_v2_dance_six_axis = tk.BooleanVar(value=bool(cfg.extra.get("pose_v2_dance_six_axis", False)))
        self.pose_v2_l0_analysis = tk.BooleanVar(value=bool(cfg.extra.get("pose_v2_l0_analysis", False)))
        self.pose_v2_six_axis_analysis = tk.BooleanVar(value=bool(cfg.extra.get("pose_v2_six_axis_analysis", self.pose_v2_dance_six_axis.get())))
        self.pose_v2_l0_weight = tk.IntVar(value=int(cfg.extra.get("pose_v2_l0_weight", 60)))
        self.pose_v2_six_axis_weight = tk.IntVar(value=int(cfg.extra.get("pose_v2_six_axis_weight", 60)))
        if self.pose_v2_dance_six_axis.get() and (self.pose_v2_l0_analysis.get() or self.pose_v2_six_axis_analysis.get()):
            self.pose_l0_analysis.set(False)
            self.pose_six_axis_analysis.set(False)
        elif self.pose_l0_analysis.get() or self.pose_six_axis_analysis.get():
            self.pose_v2_dance_six_axis.set(False)
            self.pose_v2_l0_analysis.set(False)
            self.pose_v2_six_axis_analysis.set(False)
        self.pose_l0_base_weight_text = tk.StringVar()
        self.pose_six_axis_base_weight_text = tk.StringVar()
        self.pose_v2_l0_base_weight_text = tk.StringVar()
        self.pose_v2_six_axis_base_weight_text = tk.StringVar()
        self._pose_mode_syncing = False
        initial_tracker_mode = self._normalize_tracker_mode(cfg.tracker_mode)
        if bool(cfg.extra.get("rtm_pose_3d_enabled", False)):
            initial_tracker_mode = RTM_POSE_2D_MODE
        initial_rtm_pose_mode = initial_tracker_mode in (RTM_POSE_2D_MODE,)
        self.rtm_pose_3d_enabled = tk.BooleanVar(value=initial_tracker_mode == RTM_POSE_3D_MODE)
        self.rtm_pose_2d_model_path = tk.StringVar(value=str(cfg.extra.get("rtm_pose_2d_model_path", "")))
        self.rtm_pose_3d_model_path = tk.StringVar(value="")
        self.rtm_pose_3d_weight = tk.IntVar(value=100 if initial_rtm_pose_mode else 0)
        self.rtm_hybrid_l0_enabled = tk.BooleanVar(value=bool(cfg.extra.get("rtm_hybrid_l0_enabled", False)))
        self.pose_auto_l0_enabled = tk.BooleanVar(value=bool(cfg.extra.get("pose_auto_l0_enabled", True)))
        self.pose_pattern_enabled = tk.BooleanVar(value=bool(cfg.extra.get("pose_pattern_enabled", False)))
        self.pose_fast_v1_enabled = tk.BooleanVar(value=bool(cfg.extra.get("pose_fast_v1_enabled", True)))
        self.rtm_hybrid_l0_weight = tk.IntVar(value=max(1, min(100, int(cfg.extra.get("rtm_hybrid_l0_weight", 30)))))
        self.rtm_model_l0_weight_text = tk.StringVar()
        self.rtm_pose_3d_base_weight_text = tk.StringVar()
        self.rtm_model_download_button_text = tk.StringVar(value=self._t("下载/自动检测模型"))
        self.rtm_model_download_status_text = tk.StringVar(value="")
        self.rtm_pose_gpu_enabled = tk.BooleanVar(value=bool(cfg.extra.get("rtm_pose_gpu_enabled", False)))
        self.rtm_pose_gpu_backend = tk.StringVar(value=cfg.extra.get("rtm_pose_gpu_backend", "cuda"))
        self.rtm_pose_gpu_status_text = tk.StringVar()
        self._build_gpu_state()
        self._analysis_preferences = AnalysisPreferences(load_profiles(cfg.extra, initial_tracker_mode, cfg.fps), initial_tracker_mode)
        normalize_visual_settings(cfg.extra)
        self.rtm_pose_flow_enabled = tk.BooleanVar(value=cfg.extra["rtm_pose_flow_enabled"])
        self.rtm_pose_kalman_enabled = tk.BooleanVar(value=cfg.extra["rtm_pose_kalman_enabled"])
        self.hybrid_v2_pose_enabled = tk.BooleanVar(value=cfg.extra["hybrid_v2_pose_enabled"])
        self.v2_l0_reference = tk.StringVar(value=cfg.extra['v2_l0_reference'])
        self.rtm_pose_reject_enabled = tk.BooleanVar(value=cfg.extra["rtm_pose_reject_enabled"])
        self.rtm_pose_micro_smooth_enabled = tk.BooleanVar(value=cfg.extra["rtm_pose_micro_smooth_enabled"])
        self.visual_processing_edge = tk.IntVar(value=cfg.extra["visual_processing_edge"])
        self.rtm_hybrid_source = tk.StringVar(value=cfg.extra["rtm_hybrid_source"])
        self._rtm_pose_3d_downloading = False
        self._rtm_pose_3d_download_target: tk.StringVar | None = None
        self._rtm_pose_3d_download_mode: str | None = None
        self._rtm_pose_model_path_syncing = False
        self._rtm_pose_model_validation_cache: dict[tuple[str, str, int, int], tuple[bool, str]] = {}
        self.tracker_mode = tk.StringVar(value=self._tracker_display(initial_tracker_mode))
        self.rtm_pose_model_path = tk.StringVar()
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
        self.six_axis_travel_invert = tk.BooleanVar(value=bool(cfg.extra.get("six_axis_travel_invert", False)))
        stored_travel_scales = cfg.extra.get("six_axis_travel_scales", {})
        stored_output_inverts = cfg.extra.get("axis_output_inverts", {})
        if not isinstance(stored_travel_scales, dict):
            stored_travel_scales = {}
        if not isinstance(stored_output_inverts, dict):
            stored_output_inverts = {}
        self.six_axis_travel_scale_vars: dict[str, tk.DoubleVar] = {}
        self.six_axis_travel_slider_vars: dict[str, tk.DoubleVar] = {}
        self.six_axis_travel_text_vars: dict[str, tk.StringVar] = {}
        self.axis_output_invert_vars: dict[str, tk.BooleanVar] = {}
        for axis, default_scale in DEFAULT_SIX_AXIS_TRAVEL_SCALES.items():
            scale = max(0.0, min(3.0, float(stored_travel_scales.get(axis, default_scale))))
            self.six_axis_travel_scale_vars[axis] = tk.DoubleVar(value=scale)
            self.six_axis_travel_slider_vars[axis] = tk.DoubleVar(value=self._travel_scale_to_slider(scale))
            self.six_axis_travel_text_vars[axis] = tk.StringVar(value=self._format_travel_scale(scale))
            self.axis_output_invert_vars[axis] = tk.BooleanVar(
                value=bool(stored_output_inverts.get(axis, DEFAULT_AXIS_OUTPUT_INVERTS.get(axis, False)))
            )
        self.play_preset_level = tk.IntVar(value=int(cfg.extra.get("play_preset_level", 3)))
        self.six_axis_intensity = tk.IntVar(value=int(cfg.extra.get("six_axis_intensity", 65)))
        self.six_axis_jitter_reduction = tk.IntVar(value=int(cfg.extra.get("six_axis_jitter_reduction", 55)))
        self.six_axis_sensitivity_level = tk.IntVar(value=int(cfg.extra.get("six_axis_sensitivity_level", 5)))
        self.start_button_text = tk.StringVar(value=self._t("开始实时输出"))
        self.show_more_settings = tk.BooleanVar(value=bool(cfg.extra.get("show_more_settings", False)))
        self.show_measurement_limits = tk.BooleanVar(value=bool(cfg.extra.get("show_measurement_limits", True)))
        self.show_six_axis_tuning = tk.BooleanVar(value=bool(cfg.extra.get("show_six_axis_tuning", False)))
        self.show_rtm_pose_3d_settings = tk.BooleanVar(value=bool(cfg.extra.get("show_rtm_pose_3d_settings", False)))
        self.show_six_axis_travel_scales = tk.BooleanVar(value=bool(cfg.extra.get("show_six_axis_travel_scales", False)))
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
        self.connect_button_text = tk.StringVar(value=self._t("连接并回中"))
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
        self._live_output_mapping_dirty = True
        self._analysis_preferences.apply(self._analysis_variables())
        self.min_value.trace_add("write", lambda *_args: self._refresh_limit_text())
        self.max_value.trace_add("write", lambda *_args: self._refresh_limit_text())
        self.l0_travel_scale.trace_add("write", lambda *_args: self._sync_travel_slider(self.l0_travel_scale, self.l0_travel_slider, self.l0_travel_text))
        self.global_travel_scale.trace_add("write", lambda *_args: self._sync_travel_slider(self.global_travel_scale, self.global_travel_slider, self.global_travel_text))
        for axis in self.six_axis_travel_scale_vars:
            self.six_axis_travel_scale_vars[axis].trace_add(
                "write",
                lambda *_args, axis_name=axis: self._sync_travel_slider(
                    self.six_axis_travel_scale_vars[axis_name],
                    self.six_axis_travel_slider_vars[axis_name],
                    self.six_axis_travel_text_vars[axis_name],
                ),
            )
        self.show_more_settings.trace_add("write", lambda *_args: self._refresh_more_settings())
        self.show_measurement_limits.trace_add("write", lambda *_args: self._refresh_measurement_limits())
        self.show_six_axis_tuning.trace_add("write", lambda *_args: self._refresh_six_axis_tuning())
        self.show_rtm_pose_3d_settings.trace_add("write", lambda *_args: self._refresh_rtm_pose_3d_settings())
        self.show_six_axis_travel_scales.trace_add("write", lambda *_args: self._refresh_six_axis_travel_scales())
        self.rtm_hybrid_l0_enabled.trace_add("write", self._refresh_hybrid_source)
        self.rtm_pose_gpu_enabled.trace_add("write", lambda *_args: self._schedule_rtm_pose_gpu_status_refresh())
        self.rtm_pose_gpu_backend.trace_add("write", lambda *_args: self._on_gpu_backend_changed())
        self.tracker_mode.trace_add("write", lambda *_args: self._on_tracker_mode_changed())
        self.hybrid_v2_pose_enabled.trace_add("write", lambda *_args: self._on_tracker_mode_changed())
        self.output_mode.trace_add("write", lambda *_args: self._on_tracker_mode_changed())
        self.rtm_pose_model_path.trace_add("write", lambda *_args: self._store_active_rtm_pose_model_path())
        self.sink_type.trace_add("write", self._on_native_output_changed)
        self.pose_l0_analysis.trace_add("write", lambda *_args: self._sync_pose_mode_selection("v1"))
        self.pose_six_axis_analysis.trace_add("write", lambda *_args: self._sync_pose_mode_selection("v1"))
        self.pose_v2_dance_six_axis.trace_add("write", lambda *_args: self._sync_pose_mode_selection("v2_mode"))
        self.pose_v2_l0_analysis.trace_add("write", lambda *_args: self._sync_pose_mode_selection("v2_bias"))
        self.pose_v2_six_axis_analysis.trace_add("write", lambda *_args: self._sync_pose_mode_selection("v2_bias"))
        for variable in (
            self.pose_l0_analysis,
            self.pose_six_axis_analysis,
            self.pose_l0_weight,
            self.pose_six_axis_weight,
            self.pose_v2_dance_six_axis,
            self.pose_v2_l0_analysis,
            self.pose_v2_six_axis_analysis,
            self.pose_v2_l0_weight,
            self.pose_v2_six_axis_weight,
            self.rtm_pose_3d_enabled,
            self.rtm_pose_3d_weight,
            self.rtm_hybrid_l0_enabled,
            self.rtm_hybrid_l0_weight,
        ):
            variable.trace_add("write", lambda *_args: self._refresh_pose_base_weight_texts())
        self._refresh_pose_base_weight_texts()
        self._schedule_rtm_pose_gpu_status_refresh()
        for axis in SIX_AXES:
            self.axis_min_vars[axis].trace_add("write", lambda *_args, axis_name=axis: self._refresh_axis_limit_text(axis_name))
            self.axis_max_vars[axis].trace_add("write", lambda *_args, axis_name=axis: self._refresh_axis_limit_text(axis_name))
        live_mapping_vars: list[tk.Variable] = [
            self.endpoint_slowdown_enabled, self.endpoint_slowdown_pct,
            self.output_mode,
            self.min_value,
            self.max_value,
            self.max_step,
            self.enable_speed_limit,
            self.invert,
            self.l0_travel_scale,
            self.global_travel_scale,
            self.six_axis_travel_invert,
        ]
        live_mapping_vars.extend(self.axis_min_vars.values())
        live_mapping_vars.extend(self.axis_max_vars.values())
        live_mapping_vars.extend(self.six_axis_travel_scale_vars.values())
        live_mapping_vars.extend(self.axis_output_invert_vars.values())
        for variable in live_mapping_vars:
            variable.trace_add("write", lambda *_args: self._mark_live_output_mapping_dirty())
        self._refresh_active_rtm_pose_model_path()
        for variable in (self.rtm_pose_reject_enabled, self.rtm_pose_micro_smooth_enabled,
                         self.rtm_pose_flow_enabled, self.rtm_pose_kalman_enabled, self.visual_processing_edge):
            variable.trace_add("write", self._visual_options_changed)
        self._visual_options_changed()
        self.pose_auto_l0_enabled.trace_add("write", self._pose_auto_l0_changed)
        self.pose_pattern_enabled.trace_add("write", self._pose_auto_l0_changed)
        self.pose_fast_v1_enabled.trace_add("write", self._pose_auto_l0_changed)
        self.v2_l0_reference.trace_add('write', self._pose_auto_l0_changed)
        self.compression_latency.trace_add("write", self._visual_options_changed)
        for variable in (self.x, self.y, self.width, self.height, self.source_mode, self.video_path):
            variable.trace_add("write", self._input_geometry_changed)

    def _read_screen_region(self) -> ScreenRegion:
        # Read the complete tuple without IntVar's float-to-int truncation.
        try:
            region = ScreenRegion(*(self.getvar(str(variable)) for variable in
                                  (self.x, self.y, self.width, self.height))).normalized()
            if region.width < 16 or region.height < 16:
                raise ValueError
            return region
        except (tk.TclError, ValueError, TypeError) as exc:
            raise ValueError(self._dt("坐标必须是整数，区域宽高至少为 16 像素。",
                "Coordinates must be integers; width and height must be at least 16 pixels.")) from exc

    def _input_geometry_changed(self, *_args) -> None:
        # A capture owns an immutable rectangle. Do not show new settings while
        # continuing to emit output from the old source, including script edits.
        if (self.worker and self.worker.is_alive()) or self._video_analysis_active():
            self.stop()
        try:
            self._screen_region_snapshot = self._read_screen_region()
        except ValueError:
            pass  # A temporary blank/minus sign must not replace a complete ROI.
        self._active_screen_region = None
        self.reset_visual_reference()

    def _refresh_region_controls(self) -> None:
        busy = bool((self.worker and self.worker.is_alive()) or self._video_analysis_active())
        if busy == self._region_busy:
            return
        self._region_busy = busy
        for widget, idle_state in self._input_widgets:
            widget.configure(state="disabled" if busy else idle_state)

    def _validate_start_region(self) -> bool:
        try:
            region = validate_region(self._read_screen_region())
        except (ValueError, OSError, RuntimeError) as exc:
            self.status.set(str(exc))
            messagebox.showerror(self._dt("请重新选择屏幕区域", "Select the screen region again"),
                                 str(exc), parent=self)
            return False
        self._screen_region_snapshot = region
        return True

    def _pose_auto_l0_changed(self, *_args):
        self._visual_settings = replace(self._visual_settings, pose_auto_l0=self.pose_auto_l0_enabled.get(),
                                        pose_pattern=self.pose_pattern_enabled.get(),
                                        pose_fast_v1=self.pose_fast_v1_enabled.get(),
                                        v2_l0_reference=self.v2_l0_reference.get())

    def _visual_options_changed(self, *_args):
        self._visual_generation += 1
        self._visual_settings = VisualSettings(int(self.visual_processing_edge.get()),
            Options(self.rtm_pose_reject_enabled.get(), self.rtm_pose_flow_enabled.get(),
                    self.rtm_pose_kalman_enabled.get(), self.rtm_pose_micro_smooth_enabled.get()),
            self._visual_generation, pose_auto_l0=self.pose_auto_l0_enabled.get(),
            pose_pattern=self.pose_pattern_enabled.get(), pose_fast_v1=self.pose_fast_v1_enabled.get(),
            v2_l0_reference=self.v2_l0_reference.get())
        if hasattr(self, "integrated_preview"):
            self.integrated_preview.clear()

    def reset_visual_reference(self):
        self._visual_options_changed()

    def _install_config_autosave(self) -> None:
        for variable in self._config_variables():
            variable.trace_add("write", lambda *_args: self._schedule_config_save())

    def _config_variables(self) -> list[tk.Variable]:
        variables: list[tk.Variable] = [
            self.v2_l0_reference,
            self.pose_auto_l0_enabled,
            self.pose_pattern_enabled,
            self.pose_fast_v1_enabled,
            self.endpoint_slowdown_enabled, self.endpoint_slowdown_pct,
            self.hybrid_v2_pose_enabled, self.visual_processing_edge, self.rtm_pose_reject_enabled,
            self.rtm_pose_micro_smooth_enabled, self.rtm_hybrid_source,
            self.x,
            self.y,
            self.width,
            self.height,
            self.fps,
            self.output_curve_fitting,
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
            self.pose_v2_dance_six_axis,
            self.pose_v2_l0_analysis,
            self.pose_v2_six_axis_analysis,
            self.pose_v2_l0_weight,
            self.pose_v2_six_axis_weight,
            self.rtm_pose_3d_enabled,
            self.rtm_pose_2d_model_path,
            self.rtm_pose_3d_model_path,
            self.rtm_pose_3d_weight,
            self.rtm_hybrid_l0_enabled,
            self.rtm_hybrid_l0_weight,
            self.rtm_pose_gpu_enabled,
            self.rtm_pose_gpu_backend,
            self.rtm_pose_flow_enabled,
            self.rtm_pose_kalman_enabled,
            self.tracker_mode,
            self.response_curve,
            self.motion_gain,
            self.visual_stroke_scale,
            self.compression_latency,
            self.l0_travel_scale,
            self.global_travel_scale,
            self.six_axis_travel_invert,
            self.play_preset_level,
            self.six_axis_intensity,
            self.six_axis_jitter_reduction,
            self.six_axis_sensitivity_level,
            self.show_more_settings,
            self.show_measurement_limits,
            self.show_six_axis_tuning,
            self.show_rtm_pose_3d_settings,
            self.show_six_axis_travel_scales,
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
        variables.extend(self.six_axis_travel_scale_vars.values())
        variables.extend(self.axis_output_invert_vars.values())
        variables.extend(self.six_axis_gain_vars.values())
        variables.extend(self.six_axis_invert_vars.values())
        return variables

    def _clamped_percent(self, value: object, default: int = 0) -> int:
        try:
            return max(0, min(100, int(round(float(value)))))
        except (tk.TclError, TypeError, ValueError):
            return default

    def _pose_base_weight_label(self, enabled: bool, pose_weight: object, label_key: str) -> str:
        pose_value = self._clamped_percent(pose_weight)
        base_value = 100 - pose_value if enabled else 100
        return f"{self._t(label_key)}: {base_value}%"

    def _sync_pose_mode_selection(self, source: str) -> None:
        if self._pose_mode_syncing:
            return
        self._pose_mode_syncing = True
        try:
            if source == "v2_mode":
                if self.pose_v2_dance_six_axis.get():
                    self.pose_l0_analysis.set(False)
                    self.pose_six_axis_analysis.set(False)
                    if not self.pose_v2_l0_analysis.get() and not self.pose_v2_six_axis_analysis.get():
                        self.pose_v2_six_axis_analysis.set(True)
                else:
                    self.pose_v2_l0_analysis.set(False)
                    self.pose_v2_six_axis_analysis.set(False)
            elif source == "v2_bias":
                if self.pose_v2_l0_analysis.get() or self.pose_v2_six_axis_analysis.get():
                    self.pose_v2_dance_six_axis.set(True)
                    self.pose_l0_analysis.set(False)
                    self.pose_six_axis_analysis.set(False)
            elif source == "v1" and (self.pose_l0_analysis.get() or self.pose_six_axis_analysis.get()):
                self.pose_v2_dance_six_axis.set(False)
                self.pose_v2_l0_analysis.set(False)
                self.pose_v2_six_axis_analysis.set(False)
        finally:
            self._pose_mode_syncing = False
        self._refresh_pose_base_weight_texts()

    def _refresh_pose_base_weight_texts(self) -> None:
        if hasattr(self, "pose_l0_base_weight_text"):
            self.pose_l0_base_weight_text.set(
                self._pose_base_weight_label(self.pose_l0_analysis.get(), self.pose_l0_weight.get(), "基础分析 L0 权重")
            )
        if hasattr(self, "pose_six_axis_base_weight_text"):
            self.pose_six_axis_base_weight_text.set(
                self._pose_base_weight_label(
                    self.pose_six_axis_analysis.get(),
                    self.pose_six_axis_weight.get(),
                    "基础分析六轴权重",
                )
            )
        if hasattr(self, "pose_v2_l0_base_weight_text"):
            self.pose_v2_l0_base_weight_text.set(
                self._pose_base_weight_label(self.pose_v2_l0_analysis.get(), self.pose_v2_l0_weight.get(), "基础分析 v2 L0 权重")
            )
        if hasattr(self, "pose_v2_six_axis_base_weight_text"):
            self.pose_v2_six_axis_base_weight_text.set(
                self._pose_base_weight_label(
                    self.pose_v2_six_axis_analysis.get(),
                    self.pose_v2_six_axis_weight.get(),
                    "基础分析 v2 六轴权重",
                )
            )
        if hasattr(self, "rtm_pose_3d_base_weight_text"):
            self.rtm_pose_3d_base_weight_text.set(
                self._pose_base_weight_label(self._rtm_pose_mode_active(), self.rtm_pose_3d_weight.get(), "基础分析 RTM 权重")
            )
        if hasattr(self, "rtm_model_l0_weight_text"):
            model_weight = 100
            if self.rtm_hybrid_l0_enabled.get():
                model_weight = max(0, 100 - self._clamped_percent(self.rtm_hybrid_l0_weight.get(), 30))
            self.rtm_model_l0_weight_text.set(f"{self._t('当前本模型分析权重')}: {model_weight}%")

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
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, padding=(12, 6))
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.columnconfigure(0, weight=1)
        product_label = ttk.Label(header, text=f"{APP_NAME}  v{__version__}", wraplength=900)
        product_label.grid(row=0, column=0, sticky="ew")
        header.bind("<Configure>", lambda event: product_label.configure(wraplength=max(240, event.width - 24)))
        ttk.Label(header, text=self._dt("合作与侵权联系：aivnailedeng@gmail.com", "Cooperation / copyright: aivnailedeng@gmail.com")).grid(row=1, column=0, sticky="w")
        ttk.Label(header, text=self._dt("机械臂模拟测试；实际硬件映射尚未验证。",
                                       "Robot-arm simulation test; physical hardware mapping is unverified.")).grid(row=2, column=0, sticky="w")

        sidebar_shell = ttk.Frame(self)
        sidebar_shell.grid(row=1, column=0, sticky="ns")
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
        preview.grid(row=1, column=1, sticky="nsew")
        preview.rowconfigure(0, weight=1)
        preview.columnconfigure(0, weight=1, minsize=560)
        self.preview_tabs = ttk.Notebook(preview)
        self.preview_tabs.grid(row=0, column=0, sticky="nsew")
        self.analysis_tab = ttk.Frame(self.preview_tabs)
        self.analysis_tab.columnconfigure(0, weight=1)
        self.analysis_tab.rowconfigure(0, weight=1)
        self.output_tab = ttk.Frame(self.preview_tabs)
        self.output_tab.columnconfigure(0, weight=1)
        self.preview_tabs.add(self.analysis_tab, text=self._dt("分析预览", "Analysis Preview"))
        self.preview_tabs.add(self.output_tab, text=self._dt("输出监视", "Output Monitor"))
        self.preview_tabs.select(self.output_tab)

        monitor = ttk.Frame(self.output_tab, padding=10)
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
        ttk.Label(preset_bar, text="仅调整最终输出幅度", foreground="#555").grid(row=0, column=6, sticky="w", padx=(4, 0))

        self.stroke_canvas = tk.Canvas(monitor, width=72, height=176, highlightthickness=0, background="#f4f4f4")
        self.stroke_canvas.grid(row=1, column=0, rowspan=4, sticky="nsw", padx=(0, 12))
        ttk.Label(monitor, textvariable=self.l0_status, font=("", 30, "bold")).grid(row=1, column=1, sticky="w")
        ttk.Label(monitor, textvariable=self.stroke_status, font=("", 15, "bold"), foreground="#0b6b3a").grid(row=2, column=1, sticky="w")
        ttk.Label(monitor, textvariable=self.range_status, font=("", 12)).grid(row=3, column=1, sticky="w")
        ttk.Label(monitor, textvariable=self.activity, font=("", 12)).grid(row=4, column=1, sticky="w")
        ttk.Button(monitor, text="急停回中", command=self.estop, style="Danger.TButton").grid(row=1, column=2, sticky="ew")
        ttk.Button(monitor, text="全行程", command=self.apply_full_preset, style="Primary.TButton").grid(row=2, column=2, sticky="ew", pady=4)
        self.monitor_connect_button = ttk.Button(monitor, textvariable=self.connect_button_text, command=self.connect_and_center)
        self.monitor_connect_button.grid(row=3, column=2, sticky="ew")
        self.axis_canvas = tk.Canvas(monitor, width=520, height=136, highlightthickness=0, background="#f8f8f8")
        self.axis_canvas.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self.curve_canvas = tk.Canvas(monitor, width=520, height=150, highlightthickness=0, background="#101418")
        self.curve_canvas.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        self.curve_canvas.bind("<Configure>", lambda _event: self._draw_script_curve())

        self.integrated_preview = IntegratedPreview(self.analysis_tab, self)
        self.integrated_preview.grid(row=0, column=0, sticky="nsew")
        self.preview_canvas = self.integrated_preview.canvas
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

    def _capture_fps_changed(self, *_args: object) -> None:
        try:
            self._capture_target_fps = capture_fps(self.fps.get())
        except tk.TclError:
            pass

    def _capture_rate_controls(self, parent: ttk.Frame, row: int, variable: tk.IntVar) -> int:
        label = ttk.Label(parent, text="采集帧率 FPS")
        label.grid(row=row, column=0, sticky="w", pady=2)
        slider = ttk.Scale(parent, from_=1, to=120, variable=variable,
                           command=lambda value: variable.set(capture_fps(value)))
        slider.grid(row=row, column=1, sticky="ew", pady=2)
        ttk.Label(parent, textvariable=variable, width=4, anchor="e").grid(row=row, column=2, sticky="e")
        hint = self._dt(
            "屏幕模式的目标截图次数，默认 45，最高 120，实时输出时可调。更高帧率增加负载，不会增加视频原始帧数。分析 FPS 是处理循环速度，不等于模型推理 FPS；输入帧龄仅统计进入分析前的等待，不是总延迟。",
            "Target screen captures/second: default 45, maximum 120, adjustable live. Higher rates use more resources, not extra original video frames. Analysis FPS measures the processing loop, not model inference. Input age excludes analysis and output latency.")
        Tooltip(label, hint)
        Tooltip(slider, hint)
        ttk.Label(parent, textvariable=self.capture_rate_text, foreground="#555", wraplength=300).grid(
            row=row + 1, column=0, columnspan=3, sticky="ew", pady=(0, 2))
        return row + 2

    def _output_curve_changed(self, *_args: object) -> None:
        self._output_curve_enabled = bool(self.output_curve_fitting.get())

    def _endpoint_options_changed(self, *_args):
        self._endpoint_options = (bool(self.endpoint_slowdown_enabled.get()),
                                  max(1., min(50., self.endpoint_slowdown_pct.get()))/100.)

    def _endpoint_controls(self, parent, row, enabled, percent, compact=False):
        box = ttk.Frame(parent)
        box.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(2, 5))
        box.columnconfigure(2 if compact else 1, weight=1)
        check = ttk.Checkbutton(box, text=self._dt("接近上下限时减速", "Slow near upper/lower limits"), variable=enabled)
        check.grid(row=0, column=0, columnspan=1 if compact else 3, sticky="w")
        ttk.Label(box, text=self._dt("减速距离", "Braking distance")).grid(row=0 if compact else 1, column=1 if compact else 0, sticky="w", padx=(8 if compact else 0, 0))
        slider = ttk.Scale(box, from_=1, to=50, variable=percent)
        slider.grid(row=0 if compact else 1, column=2 if compact else 1, sticky="ew", padx=4)
        value = ttk.Label(box, width=5, anchor="e")
        value.grid(row=0 if compact else 1, column=3 if compact else 2)
        def refresh(*_args):
            if box.winfo_exists():
                value.configure(text=f"{percent.get():.0f}%")
                slider.state(["!disabled" if enabled.get() else "disabled"])
        callbacks = [(variable, variable.trace_add("write", refresh)) for variable in (enabled, percent)]
        def dispose(event):
            if event.widget == box:
                for variable, callback in callbacks:
                    variable.trace_remove("write", callback)
        box.bind("<Destroy>", dispose, add="+")
        refresh()
        Tooltip(check, self._dt(
            "默认开启，距离 10%：最终输出只延长接近每个轴上下限的到达时间，目标位置不变；导出脚本可能变长。离开限位正常响应，急停和手动回中不受影响。",
            "On by default, distance 10%: final output only extends arrival time near each axis limit; target positions are unchanged. Exported scripts may run longer. Motion away from limits, emergency stop and manual centering are unchanged."))
        return row+1

    def _output_curve_control(self, parent: ttk.Frame, row: int, variable: tk.BooleanVar) -> int:
        check = ttk.Checkbutton(parent, text="输出曲线拟合", variable=variable)
        check.grid(row=row, column=0, columnspan=3, sticky="w", pady=(2, 5))
        Tooltip(check, self._dt(
            "默认开启：用 One Euro 自适应平滑处理分析输出，慢动作抑抖、快动作减小滞后。Pose 自动 L0 保留已生成的曲线与切换过渡，不再重复平滑。会增加少量跟随延迟，不能保证完全无抖动；急停/手动回中不经过此滤波。",
            "Enabled by default: One Euro adaptive smoothing reduces slow-motion jitter and fast-motion lag. Generated Pose L0 retains its curve and source transition without a second smoothing pass. Adds some lag and cannot remove all jitter; emergency stop/manual centering bypass this filter."))
        return row + 1

    def _pose_auto_l0_control(self, parent, row, variable):
        check = ttk.Checkbutton(parent, text=self._dt("L0 静止／小幅时自动生成", "Generate L0 when still / small"), variable=variable)
        check.grid(row=row, column=0, columnspan=3, sticky="w", pady=(3, 2))
        Tooltip(check, self._dt(
            "默认开启，仅 Pose：L0 静止约 0.65 秒，或 L0 幅度小而旋转明显更大时，依次用 R1、R2 生成 L0，中点对应 1/3、两端对应 2/3；R1/R2 无变化但其他识别轴仍在运动时，才生成 1/4～1/2、峰到峰 1 秒的余弦波。所有识别轴静止或缺失时保持位置，不启动兜底波。L0 恢复足够幅度后平滑交回识别；只在分析运行中生效。",
            "On by default, Pose only: after about 0.65 s of still L0, or small L0 with clearly larger rotation, use R1 then R2 (midpoint to one-third L0; either end to two-thirds). When R1/R2 are still but another observed axis is moving, generate a quarter-to-half cosine with a 1 s peak-to-peak period. If all observed axes are still/missing, hold without starting a wave. Sufficient L0 motion smoothly takes over again. Runs only during analysis."))
        return check

    def _point_l0_control(self, parent, row, variable, tracker=None):
        from .point_l0 import POINT_MODES
        tracker = self.tracker_mode if tracker is None else tracker
        box = ttk.Frame(parent)
        box.columnconfigure(1, weight=1)
        box.grid(row=row, column=0, columnspan=4, sticky='ew', pady=(3, 3))
        ttk.Label(box, text=self._dt('v2 L0 参考', 'v2 L0 reference')).grid(row=0, column=0, sticky='w')
        labels = (self._dt('融合参考（默认）', 'Fused reference (default)'),
                  self._dt('三维运动轴', '3D motion axis'),
                  self._dt('往复中心点', 'Stroke center'),
                  self._dt('交互点候选（实验）', 'Interaction candidate (experimental)'))
        shown = tk.StringVar()
        combo = WideCombobox(box, textvariable=shown, values=labels, state='readonly', width=25)
        combo.grid(row=0, column=1, sticky='ew', padx=6)
        combo.bind('<<ComboboxSelected>>', lambda _event: variable.set(POINT_MODES[labels.index(shown.get())]))
        def refresh(*_args):
            value = variable.get()
            shown.set(labels[POINT_MODES.index(value) if value in POINT_MODES else 0])
            if self._tracker_internal(tracker.get()) in (HYBRID_V2_MODE, STROKE_CYCLE_MODE):
                box.grid()
            else:
                box.grid_remove()
        callbacks = [(v, v.trace_add('write', refresh)) for v in (variable, tracker)]
        def dispose(event):
            if event.widget is box:
                for v, token in callbacks:
                    v.trace_remove('write', token)
        box.bind('<Destroy>', dispose, add='+')
        Tooltip(combo, self._dt(
            '默认融合主轴、往复中心与可靠交互候选。方向确认后远离目标 L0 大、靠近 L0 小；T? 标注目标估计，未确认真实接触。识别不清时仅延续已确认规律，最多 2 秒，最后 0.5 秒减速停住。暂停、切镜头与重设参考停止延续。保留三个单独参考供比较，五档与最终限制仍生效。',
            'Default: align and fuse the motion axis, stroke center and reliable interaction evidence. Once polarity is confirmed, away means larger L0 and toward means smaller L0. T? is an estimated target, not confirmed contact. Unclear tracking continues only a confirmed rhythm for up to 2 s, braking over the final 0.5 s. Pauses, cuts and recalibration stop continuation. Three individual references remain available. Final presets and limits still apply.'))
        refresh()
        return box

    def _pose_pattern_control(self, parent, row, variable):
        check = ttk.Checkbutton(parent, text=self._dt("小幅往复渐放大", "Gradually expand small repeated strokes"), variable=variable)
        check.grid(row=row, column=0, columnspan=3, sticky="w", pady=(3, 2))
        Tooltip(check, self._dt(
            "默认关闭，仅 Pose 的 L0、R0、R1：各轴单独确认约 3 个节奏稳定的小幅往复后，用约 1 秒渐增至最多 2 倍，围绕该动作中点放大。实际幅度变大、节奏中断或观测丢失时各自平滑退出。L1、L2、R2 及自动生成的 L0 不参与检测或放大；后续行程倍率、限位和减速仍生效。",
            "Off by default, Pose L0/R0/R1 only: each axis independently confirms about 3 steady small cycles, then expands around that motion's midpoint up to 2x over about 1 s. Each releases when real motion grows, rhythm breaks or observations are lost. L1/L2/R2 and generated L0 are excluded. Travel gains, limits and slowdown still apply."))
        return check

    def _pose_fast_v1_control(self, parent, row, variable):
        check = ttk.Checkbutton(parent, text=self._dt("快速丢点时用混合 v1", "Use Hybrid v1 on fast Pose loss"), variable=variable)
        check.grid(row=row, column=0, columnspan=3, sticky="w", pady=(3, 2))
        Tooltip(check, self._dt(
            "默认开启，仅 Pose：开启后 v1 持续分析同批画面；近期有效骨架丢失且 v1 测得明显快速运动时，从当前输出位置接续 L0 的后续变化，不跳到 v1 的累计位置；Pose 恢复后平滑交回。持续运行 v1 会增加处理开销。只接管 L0，不乘 Pose 的 10 倍，其他轴保留原丢失处理。未建立 Pose、静止丢点或切镜头不会仅凭缺失启用；v1 无有效运动时退回原有自动／保持策略。",
            "On by default, Pose only: v1 continuously analyzes the same sampled frames. After recent valid Pose loss with fast v1 motion, L0 continues from the current output using subsequent changes, without jumping to v1's accumulated position. Pose recovery returns smoothly. Continuous v1 adds processing cost. L0 only, without Pose's 10x gain; other axes retain loss handling. Missing Pose alone, startup or a cut does not activate it. Without valid v1 motion, normal auto/hold behavior applies."))
        return check

    @staticmethod
    def _generated_l0_axes(analyzer):
        return ("L0",) if (getattr(analyzer, "tracker_mode", "") in (RTM_POSE_2D_MODE, HYBRID_V2_MODE, STROKE_CYCLE_MODE)
                            and getattr(analyzer, "generated_l0", None) is not None) else ()

    def _fit_output_curve(self, positions: dict[str, float], passthrough=()) -> dict[str, float]:
        curve = getattr(self._output_context, "curve", None)
        if curve is None:
            curve = self._output_context.curve = OutputCurveFilter()
        return curve.process(positions, enabled=self._output_curve_enabled, passthrough=passthrough)

    def _travel_slider(
        self,
        parent: ttk.Frame,
        label: str,
        value_var: tk.DoubleVar,
        slider_var: tk.DoubleVar,
        text_var: tk.StringVar,
        row: int,
        invert_var: tk.BooleanVar | None = None,
    ) -> int:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        ttk.Scale(
            parent,
            from_=0.0,
            to=100.0,
            variable=slider_var,
            command=lambda value, target=value_var, text=text_var: self._on_travel_slider(value, target, text),
        ).grid(row=row, column=1, sticky="ew", pady=2)
        value_box = ttk.Frame(parent)
        value_box.grid(row=row, column=2, sticky="e")
        entry = ttk.Entry(value_box, textvariable=text_var, width=7, justify="right")
        entry.grid(row=0, column=0, sticky="e")
        entry.bind("<Return>", lambda _event, target=value_var, slider=slider_var, text=text_var: self._on_travel_entry(target, slider, text))
        entry.bind("<FocusOut>", lambda _event, target=value_var, slider=slider_var, text=text_var: self._on_travel_entry(target, slider, text))
        Tooltip(entry, self._tooltip_text(label))
        if invert_var is not None:
            check = ttk.Checkbutton(value_box, text=self._t("反转"), variable=invert_var)
            check.grid(row=0, column=1, sticky="e", padx=(4, 0))
            Tooltip(check, self._tooltip_text("反转"))
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

    def _on_travel_entry(self, target: tk.DoubleVar, slider: tk.DoubleVar, text: tk.StringVar) -> None:
        if self._travel_slider_syncing:
            return
        raw = text.get().strip().lower().replace("x", "")
        try:
            scale = max(0.0, min(3.0, float(raw)))
        except (tk.TclError, ValueError):
            scale = max(0.0, min(3.0, float(target.get())))
        self._travel_slider_syncing = True
        try:
            target.set(round(scale, 3))
            slider.set(self._travel_scale_to_slider(scale))
            text.set(self._format_travel_scale(scale))
        finally:
            self._travel_slider_syncing = False
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
        inner_row = self._manual_test_controls(self.more_settings_frame, inner_row)
        inner_row = self._preset_controls(self.more_settings_frame, inner_row)
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
            self._refresh_ble_settings()
            self._refresh_measurement_limits()
            self._refresh_six_axis_tuning()
            self._refresh_rtm_pose_3d_settings()
        else:
            self.more_settings_frame.grid_remove()

    def _toggle_measurement_limits(self) -> None:
        self.show_measurement_limits.set(not self.show_measurement_limits.get())
        self._refresh_measurement_limits()

    def _refresh_measurement_limits(self) -> None:
        if not hasattr(self, "measurement_limits_button") or not hasattr(self, "measurement_limits_frame"):
            return
        expanded = self.show_measurement_limits.get()
        self.measurement_limits_button.configure(text=self._t("收起测量模式和轴上下限" if expanded else "展开测量模式和轴上下限"))
        if expanded:
            self.measurement_limits_frame.grid(row=int(self.measurement_limits_button.grid_info()["row"]) + 1, column=0, columnspan=3, sticky="ew")
        else:
            self.measurement_limits_frame.grid_remove()

    def _toggle_six_axis_tuning(self) -> None:
        self.show_six_axis_tuning.set(not self.show_six_axis_tuning.get())
        self._refresh_six_axis_tuning()

    def _refresh_six_axis_tuning(self) -> None:
        if not hasattr(self, "six_axis_tuning_button") or not hasattr(self, "six_axis_tuning_frame"):
            return
        expanded = self.show_six_axis_tuning.get()
        self.six_axis_tuning_button.configure(text=self._t("收起六轴辅助调节（仅混合分析）" if expanded else "展开六轴辅助调节（仅混合分析）"))
        if expanded:
            self.six_axis_tuning_frame.grid(row=int(self.six_axis_tuning_button.grid_info()["row"]) + 1, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        else:
            self.six_axis_tuning_frame.grid_remove()

    def _toggle_rtm_pose_3d_settings(self) -> None:
        self.show_rtm_pose_3d_settings.set(not self.show_rtm_pose_3d_settings.get())
        self._refresh_rtm_pose_3d_settings()

    def _refresh_rtm_pose_3d_settings(self) -> None:
        if not hasattr(self, "rtm_pose_3d_settings_button") or not hasattr(self, "rtm_pose_3d_settings_frame"):
            return
        if not self._pose_model_required():
            self.rtm_pose_3d_settings_button.grid_remove()
            self.rtm_pose_3d_settings_frame.grid_remove()
            return
        self.rtm_pose_3d_settings_button.grid()
        expanded = self.show_rtm_pose_3d_settings.get()
        self.rtm_pose_3d_settings_button.configure(text=self._t("收起 RTM Pose 模型设置" if expanded else "展开 RTM Pose 模型设置"))
        if expanded:
            self.rtm_pose_3d_settings_frame.grid(row=int(self.rtm_pose_3d_settings_button.grid_info()["row"]) + 1, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        else:
            self.rtm_pose_3d_settings_frame.grid_remove()

    def _toggle_six_axis_travel_scales(self) -> None:
        self.show_six_axis_travel_scales.set(not self.show_six_axis_travel_scales.get())
        self._refresh_six_axis_travel_scales()

    def _refresh_six_axis_travel_scales(self) -> None:
        if not hasattr(self, "six_axis_travel_button") or not hasattr(self, "six_axis_travel_frame"):
            return
        expanded = self.show_six_axis_travel_scales.get()
        self.six_axis_travel_button.configure(text=self._t("收起六轴单轴行程倍率" if expanded else "展开六轴单轴行程倍率"))
        if expanded:
            self.six_axis_travel_frame.grid(row=int(self.six_axis_travel_button.grid_info()["row"]) + 1, column=0, columnspan=3, sticky="ew")
        else:
            self.six_axis_travel_frame.grid_remove()

    def _refresh_ble_settings(self) -> None:
        if not hasattr(self, "ble_settings_frame"):
            return
        if self.sink_type.get() == "BLE UART":
            self.ble_settings_frame.grid()
        else:
            self.ble_settings_frame.grid_remove()
        if hasattr(self, "serial_settings_frame"):
            if self.sink_type.get() in ("Serial COM", "USB Serial"):
                self.serial_settings_frame.grid()
            else:
                self.serial_settings_frame.grid_remove()

    def _on_native_output_changed(self, *_args) -> None:
        if not hasattr(self, "native_connection_frame"):
            return
        if self.connected or self._connecting:
            self.stop()
            self.disconnect_sink()
        self._refresh_ble_settings()
        self._refresh_device_controls()

    def _manual_test_controls(self, parent: ttk.Frame, row: int) -> int:
        ttk.Button(parent, text="居中", command=self.send_center).grid(row=row, column=0, sticky="ew")
        ttk.Button(parent, text="中等测试", command=self.send_small_test).grid(row=row, column=1, columnspan=2, sticky="ew", padx=(4, 0))
        row += 1
        ttk.Button(parent, text="上下全幅测试", command=self.send_full_l0_test).grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0)
        )
        row += 1
        ttk.Button(parent, text="SR6/OSR6 六轴轻测", command=self.send_six_axis_test).grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(4, 8)
        )
        return row + 1

    def _preset_controls(self, parent: ttk.Frame, row: int) -> int:
        ttk.Button(parent, text="安全预设", command=self.apply_safe_preset).grid(row=row, column=0, sticky="ew")
        ttk.Button(parent, text="标准预设", command=self.apply_normal_preset).grid(row=row, column=1, sticky="ew", padx=(4, 0))
        ttk.Button(parent, text="全行程", command=self.apply_full_preset).grid(row=row, column=2, sticky="ew", padx=(4, 0))
        row += 1
        ttk.Button(parent, text="混合分析灵敏", command=self.apply_hybrid_analysis_preset, style="Primary.TButton").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(4, 12)
        )
        return row + 1

    def _install_tooltips(self, widget: tk.Widget) -> None:
        try:
            text = str(widget.cget("text")).strip()
        except tk.TclError:
            text = ""
        tooltip_key = UI_TEXT_REVERSE_EN.get(text, text)
        tooltip_text = self._tooltip_text(tooltip_key)
        if tooltip_text:
            Tooltip(widget, tooltip_text)
        for child in widget.winfo_children():
            self._install_tooltips(child)

    def _tooltip_text(self, key: str) -> str:
        return (TOOLTIPS_EN if self.ui_language == "en" else TOOLTIPS).get(key, "")

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
        for label, variable in (("X", self.x), ("Y", self.y), ("宽", self.width), ("高", self.height)):
            ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
            entry = ttk.Entry(parent, textvariable=variable, width=12)
            entry.grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
            self._input_widgets.append((entry, "normal"))
            row += 1
        button = ttk.Button(parent, text="框选区域", command=self.pick_region)
        button.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        self._input_widgets.append((button, "normal"))
        ttk.Label(parent, text=self._dt("物理像素；左侧／上方副屏坐标可为负数。",
            "Physical pixels; displays left/above may have negative coordinates."),
            wraplength=300, foreground="#555").grid(row=row+1, column=0, columnspan=3, sticky="ew", pady=4)
        return row + 2

    def _source_controls(self, parent: ttk.Frame, row: int) -> int:
        row = self._section(parent, "输入来源", row)
        ttk.Label(parent, text="来源").grid(row=row, column=0, sticky="w", pady=2)
        source = WideCombobox(
            parent,
            textvariable=self.source_mode,
            values=("Screen", "Video File", "Audio Only"),
            state="readonly",
            width=12,
        )
        source.grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
        self._input_widgets.append((source, "readonly"))
        row += 1
        ttk.Label(parent, text="视频").grid(row=row, column=0, sticky="w", pady=2)
        entry = ttk.Entry(parent, textvariable=self.video_path, width=18)
        entry.grid(row=row, column=1, sticky="ew", pady=2)
        button = ttk.Button(parent, text="选择", command=self.pick_video)
        button.grid(row=row, column=2, sticky="ew", padx=(4, 0))
        self._input_widgets.extend(((entry, "normal"), (button, "normal")))
        row += 1
        ttk.Button(parent, text="分析视频并保存脚本", command=self.analyze_video_file).grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0)
        )
        return row + 1

    def _audio_controls(self, parent: ttk.Frame, row: int) -> int:
        row = self._section(parent, "声音监听", row)
        ttk.Label(parent, text="声音分析").grid(row=row, column=0, sticky="w", pady=2)
        WideCombobox(
            parent,
            textvariable=self.audio_mode,
            values=("Audio Level", "Dynamic Accent", "Beat Pulse"),
            state="readonly",
            width=14,
        ).grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
        row += 1
        ttk.Label(parent, text="声音设备").grid(row=row, column=0, sticky="w", pady=2)
        self.audio_device_combo = WideCombobox(parent, textvariable=self.audio_device, values=(), width=14)
        self.audio_device_combo.grid(row=row, column=1, sticky="ew", pady=2)
        ttk.Button(parent, text="刷新", command=self.refresh_audio_devices).grid(row=row, column=2, sticky="ew", padx=(4, 0))
        row += 1
        row = self._slider(parent, "声音增益", self.audio_gain, row, 0.2, 8.0)
        row = self._slider(parent, "声音门槛", self.audio_threshold, row, 0.0, 0.35)
        row = self._slider(parent, "声音平滑", self.audio_smoothing, row, 0.0, 0.95)
        ttk.Label(
            parent,
            text="选择 Audio Only 后只监听声音，不读取屏幕画面。",
            wraplength=300,
            foreground="#555",
        ).grid(row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        return row + 1

    def _tracking_controls(self, parent: ttk.Frame, row: int) -> int:
        row = self._section(parent, "高级参数", row)
        ttk.Label(parent, text="输出模式").grid(row=row, column=0, sticky="w", pady=2)
        WideCombobox(
            parent,
            textvariable=self.output_mode,
            values=("L0 Only", "Six Axis"),
            state="readonly",
            width=12,
        ).grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
        row += 1
        ttk.Label(parent, text="分析模式").grid(row=row, column=0, sticky="w", pady=2)
        WideCombobox(
            parent,
            textvariable=self.tracker_mode,
            values=self._tracker_choices(),
            state="readonly",
            width=12,
        ).grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
        row += 1
        row = self._endpoint_controls(parent, row, self.endpoint_slowdown_enabled, self.endpoint_slowdown_pct)
        row = self._capture_rate_controls(parent, row, self.fps)
        row = self._output_curve_control(parent, row, self.output_curve_fitting)
        row = self._entry(parent, "到达时间下限 ms", self.interval_ms, row)
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
        WideCombobox(
            parent,
            textvariable=self.response_curve,
            values=("Linear", "Soft", "Sharp", "Ease In"),
            state="readonly",
            width=10,
        ).grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
        row += 1
        ttk.Label(parent, text="空闲").grid(row=row, column=0, sticky="w", pady=2)
        WideCombobox(
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
        row = self._device_selector_controls(parent, row)
        connection_parent, connection_row = parent, row + 1
        self.native_connection_frame = ttk.Frame(parent)
        self.native_connection_frame.columnconfigure(1, weight=1)
        self.native_connection_frame.grid(row=row, column=0, columnspan=3, sticky="ew")
        parent, row = self.native_connection_frame, 0
        ttk.Label(parent, text="输出").grid(row=row, column=0, sticky="w", pady=2)
        self.native_output_combo = WideCombobox(
            parent,
            textvariable=self.sink_type,
            values=("Log only", "Serial COM", "BLE UART"),
            state="readonly",
            width=14,
        )
        self.native_output_combo.grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
        self.serial_settings_frame = ttk.Frame(parent)
        self.serial_settings_frame.columnconfigure(1, weight=1)
        self.serial_settings_frame.grid(row=1, column=0, columnspan=3, sticky="ew")
        parent, row = self.serial_settings_frame, 0
        ttk.Label(parent, text="串口").grid(row=row, column=0, sticky="w", pady=2)
        self.port_combo = WideCombobox(parent, textvariable=self.serial_port, values=(), width=14)
        self.port_combo.grid(row=row, column=1, sticky="ew", pady=2)
        ttk.Button(parent, text="刷新", command=self.refresh_ports).grid(row=row, column=2, sticky="ew", padx=(4, 0))
        row += 1
        row = self._entry(parent, "波特率", self.baudrate, row)
        ttk.Button(parent, text="自动检测 SR6/OSR6", command=self.autodetect_device).grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0)
        )
        row += 1

        self.ble_settings_frame = ttk.Frame(self.native_connection_frame)
        self.ble_settings_frame.columnconfigure(1, weight=1)
        ble_row = 0
        ttk.Label(self.ble_settings_frame, text="BLE 名称").grid(row=ble_row, column=0, sticky="w", pady=2)
        ttk.Entry(self.ble_settings_frame, textvariable=self.ble_name).grid(row=ble_row, column=1, sticky="ew", pady=2)
        ttk.Button(self.ble_settings_frame, text="扫描", command=self.scan_ble).grid(row=ble_row, column=2, sticky="ew", padx=(4, 0))
        ble_row += 1
        ttk.Label(self.ble_settings_frame, text="BLE 地址").grid(row=ble_row, column=0, sticky="w", pady=2)
        ttk.Entry(self.ble_settings_frame, textvariable=self.ble_address, width=18).grid(row=ble_row, column=1, columnspan=2, sticky="ew", pady=2)
        ble_row += 1
        ttk.Label(self.ble_settings_frame, text="写入 UUID").grid(row=ble_row, column=0, sticky="w", pady=2)
        ttk.Entry(self.ble_settings_frame, textvariable=self.ble_write_uuid, width=18).grid(row=ble_row, column=1, columnspan=2, sticky="ew", pady=2)
        self.ble_settings_frame.grid(row=2, column=0, columnspan=3, sticky="ew")
        parent = connection_parent
        row = connection_row
        self.connect_button = ttk.Button(parent, textvariable=self.connect_button_text, command=self.connect_and_center, style="Primary.TButton")
        self.connect_button.grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(4, 0)
        )
        ttk.Button(parent, text="断开", command=self.disconnect_sink).grid(row=row, column=2, sticky="ew", padx=(4, 0), pady=(4, 0))
        row += 1
        self.query_axes_button = ttk.Button(parent, text="查询设备轴", command=self.query_device_axes)
        self.query_axes_button.grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0)
        )
        self._refresh_ble_settings()
        self._refresh_device_controls()
        return row + 1

    def _quick_controls(self, parent: ttk.Frame, row: int) -> int:
        row = self._section(parent, "实时输出", row)
        row = self._slider(parent, "下限", self.min_value, row, 0, 9999)
        row = self._slider(parent, "上限", self.max_value, row, 0, 9999)
        ttk.Label(parent, text="速度").grid(row=row, column=0, sticky="w", pady=2)
        ttk.Scale(parent, from_=100, to=9999, variable=self.max_step).grid(row=row, column=1, sticky="ew", pady=2)
        ttk.Label(parent, textvariable=self.max_step, width=6, anchor="e").grid(row=row, column=2, sticky="e")
        row += 1
        ttk.Button(parent, text="恢复所有默认设置", command=self.reset_all_settings).grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0)
        )
        row += 1
        self.start_button = ttk.Button(parent, textvariable=self.start_button_text, command=self.start)
        self.start_button.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0))
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
        ttk.Button(parent, text="开始录制", command=self.start_recording).grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(parent, text="保存脚本", command=self.save_recording).grid(row=row, column=2, sticky="ew", padx=(4, 0), pady=(8, 0))
        row += 1
        row = self._travel_slider(parent, "L0 总行程倍率", self.l0_travel_scale, self.l0_travel_slider, self.l0_travel_text, row, self.invert)
        row = self._travel_slider(
            parent,
            "六轴总行程倍率",
            self.global_travel_scale,
            self.global_travel_slider,
            self.global_travel_text,
            row,
            self.six_axis_travel_invert,
        )
        self.six_axis_travel_button = ttk.Button(parent, command=self._toggle_six_axis_travel_scales)
        self.six_axis_travel_button.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(0, 4))
        row += 1
        self.six_axis_travel_frame = ttk.Frame(parent)
        self.six_axis_travel_frame.columnconfigure(1, weight=1)
        inner_row = 0
        for axis in ("L1", "L2", "R0", "R1", "R2"):
            inner_row = self._travel_slider(
                self.six_axis_travel_frame,
                f"{axis} 行程倍率",
                self.six_axis_travel_scale_vars[axis],
                self.six_axis_travel_slider_vars[axis],
                self.six_axis_travel_text_vars[axis],
                inner_row,
                self.axis_output_invert_vars[axis],
            )
        self.six_axis_travel_frame.grid(row=row, column=0, columnspan=3, sticky="ew")
        self._refresh_six_axis_travel_scales()
        row += 1
        return row + 1





    def _axis_limit_controls(self, parent: ttk.Frame, row: int) -> int:
        row = self._section(parent, "六轴独立上下限", row)
        self.measurement_limits_button = ttk.Button(parent, command=self._toggle_measurement_limits)
        self.measurement_limits_button.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(0, 4))
        row += 1
        self.measurement_limits_frame = ttk.Frame(parent)
        self.measurement_limits_frame.columnconfigure(1, weight=1)
        inner_row = 0
        inner_row = self._measurement_controls(self.measurement_limits_frame, inner_row)
        ttk.Label(self.measurement_limits_frame, text="轴").grid(row=inner_row, column=0, sticky="w")
        ttk.Label(self.measurement_limits_frame, text="下限").grid(row=inner_row, column=1, sticky="w")
        ttk.Label(self.measurement_limits_frame, text="上限").grid(row=inner_row, column=2, sticky="w")
        inner_row += 1
        for axis in SIX_AXES:
            line = ttk.Frame(self.measurement_limits_frame)
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
            line.grid(row=inner_row, column=0, columnspan=3, sticky="ew", pady=1)
            inner_row += 1
        ttk.Label(
            self.measurement_limits_frame,
            text="实时输出与测试会按每个轴自己的范围映射。滑块交叉时会自动整理。",
            wraplength=300,
            foreground="#555",
        ).grid(row=inner_row, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        self.measurement_limits_frame.grid(row=row, column=0, columnspan=3, sticky="ew")
        self._refresh_measurement_limits()
        row += 1
        row = self._six_axis_tuning_controls(parent, row)
        row = self._rtm_pose_3d_controls(parent, row)
        return row

    def _rtm_pose_3d_controls(self, parent: ttk.Frame, row: int) -> int:
        self.rtm_pose_3d_settings_button = ttk.Button(parent, command=self._toggle_rtm_pose_3d_settings)
        self.rtm_pose_3d_settings_button.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(4, 4))
        row += 1
        box = ttk.LabelFrame(parent, text="RTM Pose 模型", padding=8)
        self.rtm_pose_3d_settings_frame = box
        box.columnconfigure(1, weight=1)
        rtm_hybrid_check = ttk.Checkbutton(box, text="混合分析 L0 权重", variable=self.rtm_hybrid_l0_enabled)
        rtm_hybrid_check.grid(row=0, column=0, sticky="w", pady=2)
        Tooltip(rtm_hybrid_check, self._tooltip_text("混合分析 L0 权重"))
        blend_scale = ttk.Scale(box, from_=1, to=100, variable=self.rtm_hybrid_l0_weight)
        blend_scale.grid(row=0, column=1, sticky="ew", pady=2)
        blend_value = ttk.Label(box, textvariable=self.rtm_hybrid_l0_weight, width=4, anchor="e")
        blend_value.grid(row=0, column=2, sticky="e")
        rtm_model_weight_label = ttk.Label(box, textvariable=self.rtm_model_l0_weight_text, foreground="#555")
        rtm_model_weight_label.grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 5))
        Tooltip(rtm_model_weight_label, self._tooltip_text("当前本模型分析权重"))
        ttk.Label(box, text="RTM Pose 模型").grid(row=2, column=0, sticky="w", pady=2)
        rtm_model_entry = ttk.Entry(box, textvariable=self.rtm_pose_model_path)
        rtm_model_entry.grid(row=2, column=1, sticky="ew", pady=2)
        Tooltip(rtm_model_entry, self._tooltip_text("RTM Pose 模型"))
        ttk.Button(box, text="选择模型", command=self.pick_rtm_pose_3d_model).grid(row=2, column=2, sticky="ew", padx=(4, 0), pady=2)
        ttk.Button(box, textvariable=self.rtm_model_download_button_text, command=self.download_rtm_pose_3d_model).grid(
            row=3, column=0, columnspan=3, sticky="ew", pady=(4, 2)
        )
        ttk.Label(box, textvariable=self.rtm_model_download_status_text, foreground="#555", wraplength=330).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(0, 2)
        )
        ttk.Label(
            box,
            text="来源：OpenMMLab MMPose / rtmlib，需要本地 ONNX 模型。",
            foreground="#555",
            wraplength=330,
        ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(0, 2))
        rtm_gpu_check = ttk.Checkbutton(box, text="RTM GPU 加速", variable=self.rtm_pose_gpu_enabled)
        rtm_gpu_check.grid(row=6, column=0, columnspan=3, sticky="w", pady=(5, 0))
        Tooltip(rtm_gpu_check, self._tooltip_text("RTM GPU 加速"))
        self._gpu_status_controls(box, 7, self.rtm_pose_gpu_enabled, self.rtm_pose_gpu_status_text)
        rtm_flow_check = ttk.Checkbutton(box, text="RTM 光流辅助", variable=self.rtm_pose_flow_enabled)
        rtm_flow_check.grid(row=8, column=0, columnspan=3, sticky="w", pady=(5, 0))
        Tooltip(rtm_flow_check, self._tooltip_text("RTM 光流辅助"))
        rtm_kalman_check = ttk.Checkbutton(box, text="RTM 卡尔曼融合", variable=self.rtm_pose_kalman_enabled)
        rtm_kalman_check.grid(row=9, column=0, columnspan=3, sticky="w", pady=(2, 0))
        Tooltip(rtm_kalman_check, self._tooltip_text("RTM 卡尔曼融合"))
        ttk.Checkbutton(box, text=self._dt("异常过滤", "Reject outliers"), variable=self.rtm_pose_reject_enabled).grid(row=10, column=0, columnspan=3, sticky="w")
        ttk.Checkbutton(box, text=self._dt("仅微抖平滑", "Micro smoothing"), variable=self.rtm_pose_micro_smooth_enabled).grid(row=11, column=0, columnspan=3, sticky="w")
        self.rtm_hybrid_source_label = ttk.Label(box, text=self._dt("L0 混合来源：混合分析 v2", "L0 blend source: Hybrid v2"))
        self.rtm_hybrid_source_label.grid(row=12, column=0, columnspan=3, sticky="w")
        self.pose_auto_l0_check = self._pose_auto_l0_control(box, 13, self.pose_auto_l0_enabled)
        self.pose_pattern_check = self._pose_pattern_control(box, 14, self.pose_pattern_enabled)
        self.pose_fast_v1_check = self._pose_fast_v1_control(box, 15, self.pose_fast_v1_enabled)
        self._rtm_blend_widgets = (rtm_hybrid_check, blend_scale, blend_value, rtm_model_weight_label, self.pose_auto_l0_check, self.pose_pattern_check, self.pose_fast_v1_check)
        self._refresh_hybrid_source()
        box.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        self._refresh_rtm_pose_3d_settings()
        return row + 1

    def _measurement_controls(self, parent: ttk.Frame, row: int) -> int:
        box = ttk.LabelFrame(parent, text="测量模式", padding=8)
        box.columnconfigure(1, weight=1)
        ttk.Label(box, text="轴").grid(row=0, column=0, sticky="w", pady=2)
        axis_combo = WideCombobox(
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
        self.six_axis_tuning_button = ttk.Button(parent, command=self._toggle_six_axis_tuning)
        self.six_axis_tuning_button.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(4, 4))
        row += 1
        box = ttk.LabelFrame(parent, text="六轴辅助调节（仅混合分析推荐）", padding=8)
        self.six_axis_tuning_frame = box
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
            text="这组滑块只推荐用于混合分析（推荐-非舞蹈）；RTM Pose 输出不会接入这里。",
            wraplength=270,
            foreground="#555",
        ).grid(row=row_i, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        box.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        self._refresh_six_axis_tuning()
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

    def pick_rtm_pose_3d_model(self) -> None:
        self._choose_rtm_pose_3d_model_for_var(self.rtm_pose_model_path)

    def _choose_rtm_pose_3d_model_for_var(self, variable: tk.StringVar, mode: str | None = None) -> None:
        path = filedialog.askopenfilename(
            title=self._t("RTM Pose 模型"),
            filetypes=(("ONNX", "*.onnx"), ("All files", "*.*")),
        )
        if path:
            variable.set(path)
            target_mode = self._tracker_internal(mode or self.tracker_mode.get())
            if target_mode in (RTM_POSE_2D_MODE, HYBRID_V2_MODE):
                ok, message = self._validate_rtm_pose_model_path(path, target_mode)
                self.rtm_model_download_status_text.set(message)
                if not ok:
                    messagebox.showwarning(self._t("模型不匹配"), message)

    def download_rtm_pose_3d_model(self, target_var: tk.StringVar | None = None, mode: str | None = None) -> None:
        if self._rtm_pose_3d_downloading:
            self.status.set(self._t("模型下载中..."))
            self.rtm_model_download_status_text.set(self._t("模型下载中..."))
            return
        target_mode = self._tracker_internal(mode or self.tracker_mode.get())
        if target_mode not in (RTM_POSE_2D_MODE, HYBRID_V2_MODE):
            target_mode = RTM_POSE_2D_MODE
        detected = self._find_existing_rtm_pose_model(target_mode)
        if detected is not None:
            self._apply_rtm_pose_model_path(str(detected), target_mode, target_var)
            text = f"{self._t('自动检测到模型')}: {detected.name}"
            self.status.set(text)
            self.rtm_model_download_status_text.set(text)
            return
        self._rtm_pose_3d_download_target = target_var
        self._rtm_pose_3d_download_mode = target_mode
        self._rtm_pose_3d_downloading = True
        self.rtm_model_download_button_text.set(self._t("下载中..."))
        self.rtm_model_download_status_text.set(self._t("未检测到模型，开始下载..."))
        self.status.set(self._t("未检测到模型，开始下载..."))

        def worker() -> None:
            try:
                model_dir = self._rtm_pose_model_dir()
                model_dir.mkdir(parents=True, exist_ok=True)
                model_name, source_url, _min_size, _expected_outputs, _label = self._rtm_pose_model_spec(target_mode)
                target = model_dir / model_name
                partial = target.with_suffix(target.suffix + ".download")
                ok, _message = self._validate_rtm_pose_model_path(str(target), target_mode)
                if ok:
                    self._queue_latest(
                        {
                            "rtm_model_path": str(target),
                            "rtm_model_mode": target_mode,
                            "status_text": f"{self._t('自动检测到模型')}: {target.name}",
                            "rtm_download_status": f"{self._t('自动检测到模型')}: {target.name}",
                        }
                    )
                    return

                last_percent = -1

                def report(block_count: int, block_size: int, total_size: int) -> None:
                    nonlocal last_percent
                    if total_size <= 0:
                        return
                    downloaded = min(total_size, block_count * block_size)
                    percent = int(downloaded * 100 / total_size)
                    if percent >= last_percent + 5:
                        last_percent = percent
                        text = f"{self._t('模型下载中...')} {percent}%"
                        self._queue_latest({"status_text": text, "rtm_download_status": text})

                urllib.request.urlretrieve(source_url, partial, report)
                zip_path = target.with_suffix(".zip")
                partial.replace(zip_path)
                with zipfile.ZipFile(zip_path) as archive:
                    onnx_members = [name for name in archive.namelist() if name.lower().endswith(".onnx")]
                    if not onnx_members:
                        raise ValueError("ONNX model not found in downloaded zip")
                    with archive.open(onnx_members[0]) as source, target.open("wb") as destination:
                        while True:
                            chunk = source.read(1024 * 1024)
                            if not chunk:
                                break
                            destination.write(chunk)
                try:
                    zip_path.unlink()
                except OSError:
                    pass
                ok, message = self._validate_rtm_pose_model_path(str(target), target_mode)
                if not ok:
                    raise ValueError(message)
                self._queue_latest(
                    {
                        "rtm_model_path": str(target),
                        "rtm_model_mode": target_mode,
                        "status_text": self._t("模型下载完成"),
                        "rtm_download_status": self._t("模型下载完成"),
                    }
                )
            except Exception as exc:
                text = f"{self._t('模型下载失败')}: {exc}"
                self._queue_latest({"error": text, "rtm_download_status": text})
            finally:
                self._queue_latest({"rtm_download_done": True})

        threading.Thread(target=worker, daemon=True).start()

    def analyze_video_file(self) -> None:
        if (self.worker and self.worker.is_alive()) or self._video_analysis_active():
            self.status.set(self._dt("请先停止当前分析，再导出视频脚本。", "Stop the current analysis before exporting a video script."))
            return
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
        self._video_cancel.clear()
        self._active_screen_region = None
        self.reset_visual_reference()

        def worker() -> None:
            try:
                written = self._analyze_video_worker(Path(path), Path(save_path))
                if not self._video_cancel.is_set():
                    self._queue_latest({"export_done": True, "status_text": f"{self._t('视频分析完成')}: {len(written)} {self._t('个脚本')}"})
            except Exception as exc:
                if not self._video_cancel.is_set():
                    self._queue_latest({"error": f"{self._t('视频分析失败')}: {exc}"})

        self._video_worker = threading.Thread(target=worker, daemon=True)
        self._video_worker.start()
        self._refresh_region_controls()

    def _video_analysis_active(self) -> bool:
        return bool(self._video_worker and self._video_worker.is_alive())

    def _analyze_video_worker(self, video_path: Path, save_path: Path) -> list[Path]:
        self._six_axis_stable_positions = {axis: 0.5 for axis in SIX_AXES}
        analyzer = make_analyzer(
            visual_settings=self._visual_settings, hybrid_source=self.rtm_hybrid_source.get(),
            hybrid_v2_pose_enabled=self.hybrid_v2_pose_enabled.get(),
            tracker_mode=self._tracker_internal(self.tracker_mode.get()),
            output_mode=self.output_mode.get(),
            smoothing=self.smoothing.get(),
            deadzone=self.deadzone.get(),
            motion_gain=self.motion_gain.get(),
            enable_smoothing=self.enable_smoothing.get(),
            enable_deadzone=self.enable_deadzone.get(),
            response_curve=self.response_curve.get(),
            visual_stroke_scale=self.visual_stroke_scale.get(),
            l0_jitter_guard=self.enable_l0_jitter_guard.get(),
            l0_guard_strength=self.l0_guard_strength.get(),
            enable_extreme_reset=self.enable_extreme_reset.get(),
            enable_endpoint_guard=self.enable_endpoint_guard.get(),
            endpoint_margin=self.endpoint_margin_pct.get() / 200.0,
            pose_dance_l0=False,
            pose_dance_six_axis=False,
            pose_l0_weight=0.0,
            pose_six_axis_weight=0.0,
            pose_v2_dance_six_axis=False,
            pose_v2_l0_weight=0.0,
            pose_v2_six_axis_weight=0.0,
            rtm_pose_2d_enabled=self._rtm_pose_2d_mode_active(),
            rtm_pose_2d_model_path=self.rtm_pose_2d_model_path.get(),
            rtm_pose_3d_enabled=self._rtm_pose_3d_mode_active(),
            rtm_pose_3d_model_path=self.rtm_pose_3d_model_path.get(),
            rtm_pose_3d_weight=1.0 if self._rtm_pose_mode_active() else 0.0,
            rtm_hybrid_l0_enabled=self._rtm_pose_mode_active() and self.rtm_hybrid_l0_enabled.get(),
            rtm_hybrid_l0_weight=self.rtm_hybrid_l0_weight.get() / 100.0,
            rtm_pose_gpu_enabled=self.rtm_pose_gpu_enabled.get(),
            rtm_pose_gpu_backend=self.rtm_pose_gpu_backend.get(),
            rtm_pose_flow_enabled=self.rtm_pose_flow_enabled.get(),
            rtm_pose_kalman_enabled=self.rtm_pose_kalman_enabled.get(),
            compression_latency=self.compression_latency.get(),
        )
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            cap.release()
            raise ValueError(f"{self._t('无法打开视频')}: {video_path}")
        recorder = MultiAxisFunscriptRecorder()
        curve = OutputCurveFilter()
        recorder.start()
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        native_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        target_fps = max(1, min(60, self.fps.get()))
        frame_step = max(1, round(native_fps / target_fps))
        index = 0
        last_update = 0.0
        try:
            while not self._video_cancel.is_set():
                ok, frame = cap.read()
                if not ok:
                    break
                if index % frame_step != 0:
                    index += 1
                    continue
                at = round(index / native_fps * 1000)
                visual = isinstance(analyzer, LabAnalyzer)
                generation = self._visual_settings.generation
                if visual:
                    analyzer.configure(self._visual_settings)
                else:
                    if getattr(analyzer, "_reference_generation", generation) != generation:
                        analyzer.reset()
                    analyzer._reference_generation = generation
                analysis_frame = frame if visual else self._prepare_analysis_frame(frame)
                result = analyzer.process(analysis_frame, timestamp=index / native_fps) if visual else analyzer.process(analysis_frame)
                if self._video_cancel.is_set():
                    break
                positions = self._visual_output_positions(analyzer, result.positions)
                positions = curve.process(positions, enabled=self._output_curve_enabled, timestamp=at / 1000.0,
                                          passthrough=self._generated_l0_axes(analyzer))
                if visual and analyzer.pose and analyzer.settings.pose_fast_v1:
                    analyzer.pose_fast.remember_output(positions.get('L0'))
                if visual and not analyzer.pose:
                    analyzer.remember_l0_output(positions.get('L0'))
                output_positions = self._positions_with_travel_controls(positions)
                recorder.add_at(output_positions, at, *self._endpoint_options)
                now = time.perf_counter()
                if now - last_update > 0.25:
                    progress = f"{index}/{total}" if total else str(index)
                    self._queue_latest(
                        {
                            "visual_frame": analyzer.visual_frame if visual else VisualFrame(
                                (analysis_frame, result.preview_bgr), None, False, generation,
                                reference=getattr(analyzer, "motion_reference", None)),
                            "status_text": f"{self._t('视频分析中...')} {progress}",
                            "record_count": recorder.action_count,
                        }
                    )
                    last_update = now
                index += 1
        finally:
            cap.release()
        recorder.stop()
        if self._video_cancel.is_set():
            return []
        return recorder.save(save_path)

    def _close_sink_safely(self, sink: object) -> None:
        try:
            sink.close()
        except Exception:
            pass

    def _connection_snapshot(self) -> dict[str, object]:
        kind = self.sink_type.get()
        if kind == "Log only":
            return {"kind": kind}
        return {
            "kind": kind,
            "serial_port": extract_serial_device(self.serial_port.get()),
            "baudrate": self.baudrate.get(),
            "ble_address": self.ble_address.get(),
            "ble_write_uuid": self.ble_write_uuid.get(),
        }

    def _open_sink_from_snapshot(self, snapshot: dict[str, object]) -> object:
        kind = str(snapshot["kind"])
        if kind in ("USB Serial", "Serial COM"):
            return SerialSink(str(snapshot["serial_port"]), int(snapshot["baudrate"]))
        if kind == "BLE UART":
            return BleSink(str(snapshot["ble_address"]), str(snapshot["ble_write_uuid"]))
        if kind == "Log only":
            return LogSink()
        raise ValueError(f"Unsupported output transport: {kind}")

    def _set_connecting(self, active: bool) -> None:
        self._connecting = active
        self.connect_button_text.set(self._t("连接中...") if active else self._t("连接并回中"))
        self._set_device_controls_busy(active or bool(self.worker and self.worker.is_alive()))
        for name in ("connect_button", "monitor_connect_button"):
            button = getattr(self, name, None)
            if button is None:
                continue
            try:
                button.state(["disabled"] if active else ["!disabled"])
            except tk.TclError:
                pass

    def _finish_connection_success(self, item: dict[str, object]) -> None:
        attempt_id = int(item.get("attempt_id", 0))
        sink = item.get("sink")
        if attempt_id != self._connect_attempt_id:
            if sink is not None:
                self._close_sink_safely(sink)
            return
        if sink is None:
            return
        self.sink = sink
        self.connected = True
        self._set_connecting(False)
        kind = str(item.get("kind", self.sink_type.get()))
        self.status.set(f"{self._t('已连接')}: {kind}")
        if kind in ("USB Serial", "Serial COM"):
            self.device_status.set(f"{self._t('设备')}: {self._t('已连接')} {item.get('serial_port', '')}")
        elif kind == "BLE UART":
            self.device_status.set(f"{self._t('设备')}: {self._t('已连接')} BLE {item.get('ble_address', '')}")
        else:
            self.device_status.set(f"{self._t('设备')}: {self._t('日志模式')}")
        self._save_config()
        if bool(item.get("center_after", False)):
            try:
                self.send_center(interval_ms=600)
                self.status.set(self._t("已连接并回中"))
            except Exception as exc:
                self.status.set(f"{self._t('回中失败')}: {exc}")
        if self._start_after_connect and not (self.worker and self.worker.is_alive()):
            self._start_after_connect = False
            self.after(0, self._begin_realtime_output)

    def _finish_connection_error(self, item: dict[str, object]) -> None:
        attempt_id = int(item.get("attempt_id", 0))
        if attempt_id != self._connect_attempt_id:
            return
        self.sink = LogSink()
        self.connected = False
        self._start_after_connect = False
        self._set_connecting(False)
        message = str(item.get("message", self._t("连接失败")))
        self.device_status.set(f"{self._t('设备')}: {self._t('连接失败')}")
        self.status.set(f"{self._t('连接失败')}: {message}")
        messagebox.showerror(self._t("连接失败"), self._dt(
            "未能接入设备。请检查设备连接及串口／蓝牙选择；无设备时请选择 Log only。\n\n具体原因：",
            "Could not connect to the device. Check the connection and selected serial/BLE device; use Log only without hardware.\n\nDetails: ")+message, parent=self)

    def _finish_output_failure(self, item: dict[str, object]) -> None:
        failed_sink = item.get("sink")
        if failed_sink is not self.sink:
            return  # An old worker must not disconnect a replacement connection.
        self.stop()
        self._close_sink_safely(failed_sink)
        self.sink = LogSink()
        self.connected = False
        self._set_connecting(False)
        title = self._dt("设备输出失败", "Device output failed")
        detail = str(item.get("message", ""))
        self.device_status.set(self._dt("设备：连接不可用", "Device: connection unavailable"))
        self.status.set(f"{title}: {detail}")
        messagebox.showerror(title, self._dt(
            "设备输出失败，实时输出已停止。设备可能未接入、连接中断或写入超时。\n\n"
            "请检查后重新连接；无设备时请选择 Log only。\n\n具体原因：",
            "Device output failed; realtime output has stopped. The device may be missing, disconnected or timed out.\n\n"
            "Check and reconnect it; use Log only without hardware.\n\nDetails: ")+detail, parent=self)

    def _connection_watchdog(self, attempt_id: int) -> None:
        if not self._connecting or attempt_id != self._connect_attempt_id:
            return
        self._connect_attempt_id += 1
        self.sink = LogSink()
        self.connected = False
        self._start_after_connect = False
        self._set_connecting(False)
        self.device_status.set(f"{self._t('设备')}: {self._t('连接失败')}")
        self.status.set(self._t("连接超时"))
        messagebox.showerror(self._t("连接超时"), self._dt(
            "未能接入设备。请检查连接后重试；无设备时请选择 Log only。",
            "Could not connect to the device. Check the connection and retry; use Log only without hardware."), parent=self)

    def _start_connection_worker(self, center_after: bool = False) -> None:
        if self._gpu_installing:
            self._start_after_connect = False
            self.status.set(self._dt("请等待 GPU 运行库安装完成。", "Wait for GPU runtime installation to finish."))
            return
        if self._connecting:
            self.status.set(self._t("正在连接，连接成功后请再试一次。"))
            return
        if self.worker and self.worker.is_alive():
            self.status.set(self._dt("请先停止实时输出，再更换连接。", "Stop realtime output before changing connections."))
            return
        try:
            snapshot = self._connection_snapshot()
        except (ValueError, tk.TclError) as exc:
            self._start_after_connect = False
            self.status.set(str(exc))
            return
        kind = str(snapshot["kind"])
        self._connect_attempt_id += 1
        attempt_id = self._connect_attempt_id
        self._close_sink_safely(self.sink)
        self.sink = LogSink()
        self.connected = False
        if kind not in ("USB Serial", "Serial COM", "BLE UART"):
            self.sink.open()
            self.connected = True
            self.status.set(f"{self._t('已连接')}: {kind}")
            self.device_status.set(f"{self._t('设备')}: {self._t('日志模式')}")
            self._save_config()
            if center_after:
                self.send_center(interval_ms=600)
                self.status.set(self._t("已连接并回中"))
            return
        self._set_connecting(True)
        self.status.set(self._t("正在连接，请稍候..."))
        self.device_status.set(f"{self._t('设备')}: {self._t('正在连接，请稍候...')}")

        def worker() -> None:
            sink: object | None = None
            try:
                sink = self._open_sink_from_snapshot(snapshot)
                sink.open()
                payload = dict(snapshot)
                payload.update(
                    {
                        "connection_success": True,
                        "attempt_id": attempt_id,
                        "sink": sink,
                        "kind": kind,
                        "center_after": center_after,
                    }
                )
                self._queue_latest(payload)
            except Exception as exc:
                if sink is not None:
                    self._close_sink_safely(sink)
                self._queue_latest(
                    {
                        "connection_error": True,
                        "attempt_id": attempt_id,
                        "message": str(exc),
                    }
                )

        self._connect_worker = threading.Thread(target=worker, daemon=True)
        self._connect_worker.start()
        self.after(15000, lambda attempt=attempt_id: self._connection_watchdog(attempt))

    def connect_sink(self) -> None:
        self._start_connection_worker(center_after=False)

    def connect_and_center(self) -> None:
        self._start_connection_worker(center_after=True)

    def disconnect_sink(self) -> None:
        if self.worker and self.worker.is_alive():
            self.stop()
        self._connect_attempt_id += 1
        self._start_after_connect = False
        self._set_connecting(False)
        self._close_sink_safely(self.sink)
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
        if self._video_analysis_active():
            self.status.set(self._dt("请先停止视频导出，再开始实时分析。", "Stop video export before starting live analysis."))
            return
        if self.worker and self.worker.is_alive():
            return
        self.update_idletasks()
        self._startup_window_geometry = self.geometry()
        self.source_mode.set("Screen")
        if not self._confirm_realtime_start():
            self._startup_window_geometry = None
            return
        if not self._validate_start_region():
            self._startup_window_geometry = None
            return
        if not self._ensure_rtm_pose_model_ready():
            self._startup_window_geometry = None
            return
        if not self.connected:
            self._start_after_connect = True
            self.connect_sink()
            if not self.connected:
                if self._connecting:
                    self.status.set(self._t("正在连接，连接成功后会开始实时输出"))
                self._startup_window_geometry = None
                return
            self._start_after_connect = False
        self._begin_realtime_output()

    def _begin_realtime_output(self) -> None:
        if self._video_analysis_active():
            self.status.set(self._dt("请先停止视频导出，再开始实时分析。", "Stop video export before starting live analysis."))
            return
        if self._gpu_installing or (self._gpu_restart_required and self.rtm_pose_gpu_enabled.get()):
            self.status.set(self._dt("GPU 运行库安装后请重启软件；也可关闭 GPU 使用 CPU。", "Restart after GPU installation, or disable GPU to use CPU."))
            return
        if self.worker and self.worker.is_alive():
            return
        if not self.connected:
            return
        self._live_source_mode = self.source_mode.get()
        if self._live_source_mode == "Screen" and not self._validate_start_region():
            return
        self._active_screen_region = self._screen_region_snapshot if self._live_source_mode == "Screen" else None
        self._normalize_limits()
        self._script_history.clear()
        self._six_axis_stable_positions = {axis: 0.5 for axis in SIX_AXES}
        self._draw_script_curve()
        self.stop_event.clear()
        self.reset_visual_reference()
        self.capture_rate_text.set("")
        self.worker = threading.Thread(target=self._run_capture, daemon=True)
        self.worker.start()
        self._refresh_region_controls()
        self._set_device_controls_busy(True)
        self._refresh_start_button_text()
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
        dialog.resizable(True, True)
        dialog.grab_set()

        mode = tk.StringVar(value=self.output_mode.get() if self.output_mode.get() in ("L0 Only", "Six Axis") else "L0 Only")
        current_tracker = self._tracker_internal(self.tracker_mode.get())
        if current_tracker not in TRACKER_MODE_CHOICES:
            current_tracker = HYBRID_V2_MODE
        tracker = tk.StringVar(value=self._tracker_display(current_tracker))
        pose_l0 = tk.BooleanVar(value=self.pose_l0_analysis.get())
        pose_six = tk.BooleanVar(value=self.pose_six_axis_analysis.get())
        pose_l0_weight = tk.IntVar(value=self.pose_l0_weight.get())
        pose_six_weight = tk.IntVar(value=self.pose_six_axis_weight.get())
        pose_v2 = tk.BooleanVar(value=self.pose_v2_dance_six_axis.get())
        pose_v2_l0 = tk.BooleanVar(value=self.pose_v2_l0_analysis.get())
        pose_v2_six = tk.BooleanVar(value=self.pose_v2_six_axis_analysis.get())
        pose_v2_l0_weight = tk.IntVar(value=self.pose_v2_l0_weight.get())
        pose_v2_six_weight = tk.IntVar(value=self.pose_v2_six_axis_weight.get())
        rtm_pose_3d = tk.BooleanVar(value=self._rtm_pose_mode_active(current_tracker))
        rtm_pose_2d_model = tk.StringVar(value=self.rtm_pose_2d_model_path.get())
        rtm_pose_3d_model = tk.StringVar(value=self.rtm_pose_3d_model_path.get())
        rtm_popup_model_path = tk.StringVar()
        rtm_pose_3d_weight = tk.IntVar(value=self.rtm_pose_3d_weight.get())
        rtm_hybrid_l0_enabled = tk.BooleanVar(value=self.rtm_hybrid_l0_enabled.get())
        pose_auto_l0_enabled = tk.BooleanVar(value=self.pose_auto_l0_enabled.get())
        pose_pattern_enabled = tk.BooleanVar(value=self.pose_pattern_enabled.get())
        pose_fast_v1_enabled = tk.BooleanVar(value=self.pose_fast_v1_enabled.get())
        rtm_hybrid_l0_weight = tk.IntVar(value=self.rtm_hybrid_l0_weight.get())
        rtm_pose_gpu_enabled = tk.BooleanVar(value=self.rtm_pose_gpu_enabled.get())
        rtm_pose_gpu_status_text = tk.StringVar()
        rtm_pose_flow_enabled = tk.BooleanVar(value=self.rtm_pose_flow_enabled.get())
        rtm_pose_kalman_enabled = tk.BooleanVar(value=self.rtm_pose_kalman_enabled.get())
        rtm_pose_reject_enabled = tk.BooleanVar(value=self.rtm_pose_reject_enabled.get())
        rtm_pose_micro_smooth_enabled = tk.BooleanVar(value=self.rtm_pose_micro_smooth_enabled.get())
        rtm_hybrid_source = tk.StringVar(value=HYBRID_V2_MODE)
        hybrid_v2_pose = tk.BooleanVar(value=self.hybrid_v2_pose_enabled.get())
        v2_l0_reference = tk.StringVar(value=self.v2_l0_reference.get())
        compression_latency = tk.IntVar(value=self.compression_latency.get())
        capture_rate = tk.IntVar(value=self._capture_target_fps)
        curve_fitting = tk.BooleanVar(value=self.output_curve_fitting.get())
        endpoint_enabled = tk.BooleanVar(value=self.endpoint_slowdown_enabled.get())
        endpoint_percent = tk.DoubleVar(value=self.endpoint_slowdown_pct.get())
        self._analysis_preferences.remember(self._analysis_variables())
        popup_preferences = AnalysisPreferences(self._analysis_preferences.profiles, current_tracker)
        popup_variables = {
            "pose_auto_l0_enabled": pose_auto_l0_enabled,
            "pose_pattern_enabled": pose_pattern_enabled,
            "pose_fast_v1_enabled": pose_fast_v1_enabled,
            "fps": capture_rate, "output_curve_fitting": curve_fitting, "compression_latency": compression_latency,
            "rtm_pose_gpu_enabled": rtm_pose_gpu_enabled, "rtm_hybrid_l0_enabled": rtm_hybrid_l0_enabled,
            "rtm_hybrid_l0_weight": rtm_hybrid_l0_weight, "rtm_pose_flow_enabled": rtm_pose_flow_enabled,
            "rtm_pose_kalman_enabled": rtm_pose_kalman_enabled, "rtm_pose_reject_enabled": rtm_pose_reject_enabled,
            "rtm_pose_micro_smooth_enabled": rtm_pose_micro_smooth_enabled,
        }
        pose_l0_base_text = tk.StringVar()
        pose_six_base_text = tk.StringVar()
        pose_v2_l0_base_text = tk.StringVar()
        pose_v2_six_base_text = tk.StringVar()
        rtm_pose_3d_base_text = tk.StringVar()
        rtm_popup_model_l0_text = tk.StringVar()
        result = {"ok": False}
        pose_popup_syncing = False
        rtm_popup_path_syncing = False

        def active_popup_rtm_model_var() -> tk.StringVar:
            return rtm_pose_2d_model

        def refresh_popup_rtm_model_path(*_args: object) -> None:
            nonlocal rtm_popup_path_syncing
            rtm_popup_path_syncing = True
            try:
                rtm_popup_model_path.set(active_popup_rtm_model_var().get())
            finally:
                rtm_popup_path_syncing = False

        def store_popup_rtm_model_path(*_args: object) -> None:
            if rtm_popup_path_syncing:
                return
            active_popup_rtm_model_var().set(rtm_popup_model_path.get())

        def refresh_pose_base_texts(*_args: object) -> None:
            pose_l0_base_text.set(self._pose_base_weight_label(pose_l0.get(), pose_l0_weight.get(), "基础分析 L0 权重"))
            pose_six_base_text.set(self._pose_base_weight_label(pose_six.get(), pose_six_weight.get(), "基础分析六轴权重"))
            pose_v2_l0_base_text.set(self._pose_base_weight_label(pose_v2_l0.get(), pose_v2_l0_weight.get(), "基础分析 v2 L0 权重"))
            pose_v2_six_base_text.set(self._pose_base_weight_label(pose_v2_six.get(), pose_v2_six_weight.get(), "基础分析 v2 六轴权重"))
            rtm_pose_3d_base_text.set(self._pose_base_weight_label(rtm_pose_3d.get(), rtm_pose_3d_weight.get(), "基础分析 RTM 权重"))
            model_weight = 100
            if rtm_hybrid_l0_enabled.get():
                model_weight = max(0, 100 - self._clamped_percent(rtm_hybrid_l0_weight.get(), 30))
            rtm_popup_model_l0_text.set(f"{self._t('当前本模型分析权重')}: {model_weight}%")

        def refresh_popup_gpu_status(*_args: object) -> None:
            self._schedule_rtm_pose_gpu_status_refresh()

        def sync_popup_pose_mode(source: str) -> None:
            nonlocal pose_popup_syncing
            if pose_popup_syncing:
                return
            pose_popup_syncing = True
            try:
                if source == "v2_mode":
                    if pose_v2.get():
                        pose_l0.set(False)
                        pose_six.set(False)
                        if not pose_v2_l0.get() and not pose_v2_six.get():
                            pose_v2_six.set(True)
                    else:
                        pose_v2_l0.set(False)
                        pose_v2_six.set(False)
                elif source == "v2_bias":
                    if pose_v2_l0.get() or pose_v2_six.get():
                        pose_v2.set(True)
                        pose_l0.set(False)
                        pose_six.set(False)
                elif source == "v1" and (pose_l0.get() or pose_six.get()):
                    pose_v2.set(False)
                    pose_v2_l0.set(False)
                    pose_v2_six.set(False)
            finally:
                pose_popup_syncing = False
            refresh_pose_base_texts()

        pose_l0.trace_add("write", lambda *_args: sync_popup_pose_mode("v1"))
        pose_six.trace_add("write", lambda *_args: sync_popup_pose_mode("v1"))
        pose_v2.trace_add("write", lambda *_args: sync_popup_pose_mode("v2_mode"))
        pose_v2_l0.trace_add("write", lambda *_args: sync_popup_pose_mode("v2_bias"))
        pose_v2_six.trace_add("write", lambda *_args: sync_popup_pose_mode("v2_bias"))
        for variable in (
            pose_l0,
            pose_six,
            pose_l0_weight,
            pose_six_weight,
            pose_v2,
            pose_v2_l0,
            pose_v2_six,
            pose_v2_l0_weight,
            pose_v2_six_weight,
            rtm_pose_3d,
            rtm_pose_3d_weight,
            rtm_hybrid_l0_enabled,
            rtm_hybrid_l0_weight,
        ):
            variable.trace_add("write", refresh_pose_base_texts)
        rtm_pose_gpu_enabled.trace_add("write", refresh_popup_gpu_status)
        rtm_popup_model_path.trace_add("write", store_popup_rtm_model_path)
        refresh_pose_base_texts()
        refresh_popup_gpu_status()
        refresh_popup_rtm_model_path()

        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)
        scroll = tk.Canvas(dialog, highlightthickness=0)
        scroll.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=scroll.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        scroll.configure(yscrollcommand=scrollbar.set)
        body = ttk.Frame(scroll, padding=14)
        body_window = scroll.create_window(0, 0, window=body, anchor="nw")
        body.bind("<Configure>", lambda _event: scroll.configure(scrollregion=scroll.bbox("all")))
        scroll.bind("<Configure>", lambda event: scroll.itemconfigure(body_window, width=event.width))
        dialog.bind("<MouseWheel>", lambda event: scroll.yview_scroll(-int(event.delta / 120), "units"))
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
            try:
                region = self._read_screen_region()
                region_text.set(f"{self._t('屏幕区域')}: X {region.x}  Y {region.y}  {region.width} × {region.height} px")
            except ValueError:
                region_text.set(self._dt("区域输入尚未完成，请重新框选。", "Region entry is incomplete; select a region again."))

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
        WideCombobox(
            analysis,
            textvariable=tracker,
            values=self._tracker_choices(),
            state="readonly",
            width=28,
        ).grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        fps_frame = ttk.Frame(analysis)
        fps_frame.columnconfigure(1, weight=1)
        fps_frame.grid(row=1, column=0, columnspan=3, sticky="ew")
        next_row = self._endpoint_controls(fps_frame, 0, endpoint_enabled, endpoint_percent)
        next_row = self._capture_rate_controls(fps_frame, next_row, capture_rate)
        self._output_curve_control(fps_frame, next_row, curve_fitting)
        rtm_popup_frame = ttk.Frame(analysis)
        rtm_popup_frame.columnconfigure(1, weight=1)
        rtm_popup_hybrid_check = ttk.Checkbutton(rtm_popup_frame, text="混合分析 L0 权重", variable=rtm_hybrid_l0_enabled)
        rtm_popup_hybrid_check.grid(row=0, column=0, sticky="w", pady=2)
        Tooltip(rtm_popup_hybrid_check, self._tooltip_text("混合分析 L0 权重"))
        popup_blend_scale = ttk.Scale(rtm_popup_frame, from_=1, to=100, variable=rtm_hybrid_l0_weight)
        popup_blend_scale.grid(row=0, column=1, sticky="ew", pady=2)
        popup_blend_value = ttk.Label(rtm_popup_frame, textvariable=rtm_hybrid_l0_weight, width=4, anchor="e")
        popup_blend_value.grid(row=0, column=2, sticky="e")
        rtm_popup_model_label = ttk.Label(rtm_popup_frame, textvariable=rtm_popup_model_l0_text, foreground="#555")
        rtm_popup_model_label.grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 5))
        Tooltip(rtm_popup_model_label, self._tooltip_text("当前本模型分析权重"))
        ttk.Label(rtm_popup_frame, text="RTM Pose 模型").grid(row=2, column=0, sticky="w", pady=2)
        rtm_popup_entry = ttk.Entry(rtm_popup_frame, textvariable=rtm_popup_model_path)
        rtm_popup_entry.grid(row=2, column=1, sticky="ew", pady=2)
        Tooltip(rtm_popup_entry, self._tooltip_text("RTM Pose 模型"))
        ttk.Button(
            rtm_popup_frame,
            text="选择模型",
            command=lambda: self._choose_rtm_pose_3d_model_for_var(rtm_popup_model_path, self._tracker_internal(tracker.get())),
        ).grid(
            row=2, column=2, sticky="ew", padx=(4, 0), pady=2
        )
        ttk.Button(
            rtm_popup_frame,
            textvariable=self.rtm_model_download_button_text,
            command=lambda: self.download_rtm_pose_3d_model(rtm_popup_model_path, self._tracker_internal(tracker.get())),
        ).grid(
            row=3, column=0, columnspan=3, sticky="ew", pady=(4, 2)
        )
        ttk.Label(rtm_popup_frame, textvariable=self.rtm_model_download_status_text, foreground="#555", wraplength=360).grid(
            row=4, column=0, columnspan=3, sticky="ew", pady=(0, 2)
        )
        ttk.Label(
            rtm_popup_frame,
            text="来源：OpenMMLab MMPose / rtmlib，需要本地 ONNX 模型。",
            wraplength=360,
            foreground="#555",
        ).grid(row=5, column=0, columnspan=3, sticky="ew", pady=(0, 2))
        rtm_popup_gpu_check = ttk.Checkbutton(rtm_popup_frame, text="RTM GPU 加速", variable=rtm_pose_gpu_enabled)
        rtm_popup_gpu_check.grid(row=6, column=0, columnspan=3, sticky="w", pady=(5, 0))
        Tooltip(rtm_popup_gpu_check, self._tooltip_text("RTM GPU 加速"))
        self._gpu_status_controls(rtm_popup_frame, 7, rtm_pose_gpu_enabled, rtm_pose_gpu_status_text)
        rtm_popup_flow_check = ttk.Checkbutton(rtm_popup_frame, text="RTM 光流辅助", variable=rtm_pose_flow_enabled)
        rtm_popup_flow_check.grid(row=8, column=0, columnspan=3, sticky="w", pady=(5, 0))
        Tooltip(rtm_popup_flow_check, self._tooltip_text("RTM 光流辅助"))
        rtm_popup_kalman_check = ttk.Checkbutton(rtm_popup_frame, text="RTM 卡尔曼融合", variable=rtm_pose_kalman_enabled)
        rtm_popup_kalman_check.grid(row=9, column=0, columnspan=3, sticky="w", pady=(2, 0))
        Tooltip(rtm_popup_kalman_check, self._tooltip_text("RTM 卡尔曼融合"))

        ttk.Checkbutton(rtm_popup_frame, text=self._dt("异常过滤", "Reject outliers"), variable=rtm_pose_reject_enabled).grid(row=10, column=0, columnspan=3, sticky="w")
        ttk.Checkbutton(rtm_popup_frame, text=self._dt("仅微抖平滑", "Micro smoothing"), variable=rtm_pose_micro_smooth_enabled).grid(row=11, column=0, columnspan=3, sticky="w")
        popup_source_label = ttk.Label(rtm_popup_frame, text=self._dt("L0 混合来源：混合分析 v2", "L0 blend source: Hybrid v2"))
        popup_source_label.grid(row=12, column=0, columnspan=3, sticky="w")
        popup_auto_l0 = self._pose_auto_l0_control(rtm_popup_frame, 13, pose_auto_l0_enabled)
        popup_pattern = self._pose_pattern_control(rtm_popup_frame, 14, pose_pattern_enabled)
        popup_fast_v1 = self._pose_fast_v1_control(rtm_popup_frame, 15, pose_fast_v1_enabled)
        popup_assist = ttk.Checkbutton(analysis, text=self._dt("v2：启用 RTM 2D 旋转辅助", "v2: RTM 2D rotation assist"), variable=hybrid_v2_pose)
        popup_assist.grid(row=5, column=0, columnspan=3, sticky="w")
        self._point_l0_control(analysis, 6, v2_l0_reference, tracker)

        def refresh_rtm_popup_settings(*_args: object) -> None:
            popup_preferences.switch(self._tracker_internal(tracker.get()), popup_variables)
            self._analysis_visibility(self._tracker_internal(tracker.get()), rtm_hybrid_l0_enabled.get(),
                popup_source_label, popup_assist, (rtm_popup_hybrid_check, popup_blend_scale, popup_blend_value, rtm_popup_model_label, popup_auto_l0, popup_pattern, popup_fast_v1))
            rtm_pose_3d.set(self._rtm_pose_mode_active(tracker.get()))
            refresh_pose_base_texts()
            if self._pose_model_required(tracker.get(), mode.get(), hybrid_v2_pose.get()):
                refresh_popup_rtm_model_path()
                rtm_popup_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, 6))
            else:
                rtm_popup_frame.grid_remove()

        rtm_hybrid_l0_enabled.trace_add("write", refresh_rtm_popup_settings)
        mode.trace_add("write", refresh_rtm_popup_settings)
        hybrid_v2_pose.trace_add("write", refresh_rtm_popup_settings)
        tracker.trace_add("write", refresh_rtm_popup_settings)
        refresh_rtm_popup_settings()

        ttk.Label(analysis, text="压缩延迟").grid(row=3, column=0, sticky="w", pady=(8, 2))
        ttk.Scale(analysis, from_=-5, to=5, variable=compression_latency).grid(row=3, column=1, sticky="ew", pady=(8, 2))
        ttk.Label(analysis, textvariable=compression_latency, width=4, anchor="e").grid(row=3, column=2, sticky="e", pady=(8, 2))
        ttk.Label(analysis, text="-5 最准确 / 0 默认 / 5 延迟最低", wraplength=360, foreground="#555").grid(
            row=4, column=0, columnspan=3, sticky="ew", pady=(0, 2)
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

        buttons = ttk.Frame(dialog, padding=14)
        buttons.grid(row=1, column=0, columnspan=2, sticky="ew")
        buttons.columnconfigure((0, 1), weight=1)

        def cancel() -> None:
            dialog.destroy()

        def confirm() -> None:
            if self._gpu_installing or (self._gpu_restart_required and rtm_pose_gpu_enabled.get()):
                messagebox.showwarning(self._dt("GPU 运行库", "GPU Runtime"), self._dt(
                    "请等待安装结束后重启软件；或关闭 GPU 使用 CPU。", "Wait for installation and restart the app, or disable GPU to use CPU."), parent=dialog)
                return
            self.output_mode.set(mode.get())
            self.tracker_mode.set(tracker.get())
            rtm_mode_selected = self._rtm_pose_mode_active(tracker.get())
            self.pose_l0_analysis.set(False)
            self.pose_six_axis_analysis.set(False)
            self.pose_l0_weight.set(pose_l0_weight.get())
            self.pose_six_axis_weight.set(pose_six_weight.get())
            self.pose_v2_dance_six_axis.set(pose_v2.get())
            self.pose_v2_l0_analysis.set(pose_v2_l0.get())
            self.pose_v2_six_axis_analysis.set(pose_v2_six.get())
            self.pose_v2_l0_weight.set(pose_v2_l0_weight.get())
            self.pose_v2_six_axis_weight.set(pose_v2_six_weight.get())
            self.pose_v2_dance_six_axis.set(False)
            self.pose_v2_l0_analysis.set(False)
            self.pose_v2_six_axis_analysis.set(False)
            self.rtm_pose_3d_enabled.set(self._rtm_pose_3d_mode_active(tracker.get()))
            self.rtm_pose_2d_model_path.set(rtm_pose_2d_model.get())
            self.rtm_pose_3d_model_path.set(rtm_pose_3d_model.get())
            self._refresh_active_rtm_pose_model_path()
            self.rtm_pose_3d_weight.set(100 if rtm_mode_selected else 0)
            self.rtm_hybrid_l0_enabled.set(rtm_hybrid_l0_enabled.get())
            self.pose_auto_l0_enabled.set(pose_auto_l0_enabled.get())
            self.pose_pattern_enabled.set(pose_pattern_enabled.get())
            self.pose_fast_v1_enabled.set(pose_fast_v1_enabled.get())
            self.rtm_hybrid_l0_weight.set(max(1, min(100, int(rtm_hybrid_l0_weight.get()))))
            self.rtm_pose_gpu_enabled.set(rtm_pose_gpu_enabled.get())
            self.rtm_pose_flow_enabled.set(rtm_pose_flow_enabled.get())
            self.rtm_pose_kalman_enabled.set(rtm_pose_kalman_enabled.get())
            self.rtm_pose_reject_enabled.set(rtm_pose_reject_enabled.get())
            self.rtm_pose_micro_smooth_enabled.set(rtm_pose_micro_smooth_enabled.get())
            self.rtm_hybrid_source.set(rtm_hybrid_source.get())
            self.hybrid_v2_pose_enabled.set(hybrid_v2_pose.get())
            self.v2_l0_reference.set(v2_l0_reference.get())
            self.compression_latency.set(max(-5, min(5, int(compression_latency.get()))))
            self.fps.set(capture_fps(capture_rate.get()))
            self.output_curve_fitting.set(curve_fitting.get())
            self.endpoint_slowdown_enabled.set(endpoint_enabled.get())
            self.endpoint_slowdown_pct.set(endpoint_percent.get())
            popup_preferences.remember(popup_variables)
            self._analysis_preferences = popup_preferences
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
        left, top, right, bottom = monitor_workarea(self)
        width = min(max(560, body.winfo_reqwidth() + 24), right - left - 40)
        height = min(body.winfo_reqheight() + buttons.winfo_reqheight(), bottom - top - 80)
        x = max(left, min(self.winfo_rootx() + (self.winfo_width() - width) // 2, right - width))
        y = max(top, min(self.winfo_rooty() + (self.winfo_height() - height) // 2, bottom - height - 40))
        dialog.geometry(f"{width}x{height}")
        dialog.update_idletasks()
        move_physical_window(dialog, x, y)
        self.wait_window(dialog)
        return bool(result["ok"])

    def stop(self) -> None:
        self._video_cancel.set()
        self.capture_rate_text.set("")
        self._start_after_connect = False
        self.stop_event.set()
        # Let Tk service outstanding variable reads while the worker observes stop_event.
        # A new worker cannot start until this one exits.
        if not self.worker or not self.worker.is_alive():
            self.worker = None
        self._set_device_controls_busy(self._connecting or bool(self.worker))
        self._refresh_region_controls()
        self._startup_window_geometry = None
        self._refresh_start_button_text()
        self.status.set(self._t("已停止") if self.connected else self._t("未连接"))

    def estop(self) -> None:
        self.stop()
        self.send_center(interval_ms=600)
        self.status.set(self._t("已急停并回中"))

    def reset_all_settings(self) -> None:
        if (self.worker and self.worker.is_alive()) or self._video_analysis_active():
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
            if hasattr(self, "preview_button"):
                self.preview_button.configure(text=self._t("显示预览"))

            defaults = AppConfig()
            self.config_model = defaults
            self.x.set(defaults.x)
            self.y.set(defaults.y)
            self.width.set(defaults.width)
            self.height.set(defaults.height)
            self.fps.set(defaults.fps)
            self.output_curve_fitting.set(True)
            self.endpoint_slowdown_enabled.set(True)
            self.endpoint_slowdown_pct.set(10)
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
            self.extreme_hold_ms.set(850)
            self.enable_endpoint_guard.set(True)
            self.endpoint_margin_pct.set(10)
            self.pose_l0_analysis.set(False)
            self.pose_six_axis_analysis.set(False)
            self.pose_l0_weight.set(60)
            self.pose_six_axis_weight.set(60)
            self.pose_v2_dance_six_axis.set(False)
            self.pose_v2_l0_analysis.set(False)
            self.pose_v2_six_axis_analysis.set(False)
            self.pose_v2_l0_weight.set(60)
            self.pose_v2_six_axis_weight.set(60)
            self.rtm_pose_3d_enabled.set(False)
            self.rtm_pose_2d_model_path.set("")
            self.rtm_pose_3d_model_path.set("")
            self.rtm_pose_3d_weight.set(100)
            self.rtm_hybrid_l0_enabled.set(False)
            self.pose_auto_l0_enabled.set(True)
            self.pose_pattern_enabled.set(False)
            self.pose_fast_v1_enabled.set(True)
            self.rtm_hybrid_l0_weight.set(30)
            self.rtm_pose_gpu_enabled.set(False)
            self.rtm_pose_gpu_backend.set("cuda")
            self.rtm_pose_flow_enabled.set(False)
            self.rtm_pose_kalman_enabled.set(False)
            self.hybrid_v2_pose_enabled.set(False)
            self.v2_l0_reference.set('fusion')
            self.rtm_pose_reject_enabled.set(False)
            self.rtm_pose_micro_smooth_enabled.set(False)
            self.visual_processing_edge.set(640)
            self.rtm_hybrid_source.set(HYBRID_V2_MODE)
            self._set_tracker_mode(defaults.tracker_mode)
            self.response_curve.set(defaults.response_curve)
            self.motion_gain.set(defaults.motion_gain)
            self.visual_stroke_scale.set(defaults.visual_stroke_scale)
            self.compression_latency.set(0)
            self.l0_travel_scale.set(defaults.global_travel_scale)
            self.global_travel_scale.set(defaults.global_travel_scale)
            self.six_axis_travel_invert.set(False)
            for axis, value in DEFAULT_SIX_AXIS_TRAVEL_SCALES.items():
                self.six_axis_travel_scale_vars[axis].set(value)
            for axis, inverted in DEFAULT_AXIS_OUTPUT_INVERTS.items():
                self.axis_output_invert_vars[axis].set(inverted)
            self.six_axis_intensity.set(65)
            self.six_axis_jitter_reduction.set(55)
            self.six_axis_sensitivity_level.set(5)
            self.show_more_settings.set(False)
            self.show_measurement_limits.set(True)
            self.show_six_axis_tuning.set(False)
            self.show_rtm_pose_3d_settings.set(False)
            self.show_six_axis_travel_scales.set(False)
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
            self._analysis_preferences = AnalysisPreferences({key: analysis_defaults(key) for key in ("hybrid", "dance")}, defaults.tracker_mode)
            self._analysis_preferences.apply(self._analysis_variables())
            self.preview_tabs.select(self.output_tab)
        finally:
            self._config_autosave_suspended = False
        self._save_config()
        self.status.set(self._t("已恢复所有默认设置，并保存到本机"))

    def toggle_preview(self) -> None:
        try:
            self.preview_bridge.set_device_context("SR6/OSR6", False, self.ui_language)
            self.preview_bridge.start()
            self.preview_bridge.open_window()
            self.status.set(self._dt("3D 模拟器已打开，显示最终输出指令", "3D simulator opened; showing final output commands"))
        except Exception as exc:
            self.status.set(self._dt("无法打开 3D 模拟器：", "Cannot open 3D simulator: ") + str(exc))

    def _emit_command(self, command: object) -> str:
        if isinstance(command, str):
            text = command.strip()
            payload = (text + "\n").encode("ascii")
        else:
            payload = command.encode()
            text = payload.decode("ascii").strip()
        sink = self.sink
        if getattr(self._output_context, "sink", sink) is not sink:
            return text
        if threading.current_thread() is self.worker and self.stop_event.is_set():
            return text
        try:
            sink.write(payload)
        except Exception as exc:
            self._queue_latest({"output_failed": True, "sink": sink,
                                "message": f"{type(exc).__name__}: {exc}"})
            raise OutputWriteError(f"{type(exc).__name__}: {exc}") from exc
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
            axis_position_scales=self._axis_position_scales(),
            axis_position_inverts=self._axis_position_inverts(),
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
        axis_position_inverts = self._axis_position_inverts()
        min_value = self.min_value.get()
        max_value = self.max_value.get()

        def worker() -> None:
            self._output_context.sink = test_sink
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
                axis_position_inverts=axis_position_inverts,
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

        test_sink = self.sink
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
        axis_position_scales = self._axis_position_scales()
        axis_position_inverts = self._axis_position_inverts()
        global_position_scale = self.global_travel_scale.get()
        invert_l0 = self.invert.get()
        endpoint_guard = self.enable_endpoint_guard.get()
        endpoint_margin = self.endpoint_margin_pct.get() / 100.0
        min_value = self.min_value.get()
        max_value = self.max_value.get()

        def worker() -> None:
            self._output_context.sink = test_sink
            output = MultiAxisSafeOutput(
                axes,
                min_value,
                max_value,
                invert_l0,
                320,
                999,
                0.0,
                "Hold",
                axis_limits=axis_limits,
                position_scale=global_position_scale,
                axis_position_scales=axis_position_scales,
                axis_position_inverts=axis_position_inverts,
                enable_endpoint_guard=endpoint_guard,
                endpoint_margin=endpoint_margin,
            )
            center = {axis: 0.5 for axis in axes}
            try:
                command = output.next_command(center, 1.0)
                self._queue_latest({"command": self._emit_command(command), "status_text": self._t("SR6/OSR6 六轴轻测中")})
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
                self._queue_latest({"status_text": self._t("SR6/OSR6 六轴轻测完成，已回中")})
            except Exception as exc:
                self._queue_latest({"error": f"{self._t('六轴轻测失败')}: {exc}"})

        test_sink = self.sink
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
        self._set_tracker_mode(HYBRID_MODE)
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
        self._set_tracker_mode(HYBRID_MODE)
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
        level = max(1, min(5, int(level)))
        travel = {1: 0.55, 2: 0.75, 3: 1.0, 4: 1.15, 5: 1.30}[level]
        # These scales are consumed only by script mapping and final TCode output.
        # Keep the selected analyzer and its running state intact.
        self.l0_travel_scale.set(travel)
        self.global_travel_scale.set(travel)
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
        if (self.worker and self.worker.is_alive()) or self._video_analysis_active():
            messagebox.showwarning(self._dt("先停止分析", "Stop analysis first"),
                self._dt("请先停止当前分析，再更改采集区域。", "Stop the current analysis before changing the capture region."), parent=self)
            if on_close:
                on_close(False)
            return
        if self._region_selector is not None and not self._region_selector.closed:
            self._region_selector.window.lift()
            return
        try:
            current = self._read_screen_region()
        except ValueError:
            current = None
        previous_state = self.state()

        def restore():
            if previous_state == "withdrawn":
                return
            self.deiconify()
            if previous_state in ("zoomed", "iconic"):
                self.state(previous_state)
            else:
                self.lift()

        def complete(region):
            self._region_selector = None
            restore()
            if region is not None:
                for variable, value in zip((self.x, self.y, self.width, self.height),
                                           (region.x, region.y, region.width, region.height)):
                    variable.set(value)
                self.status.set(self._dt("已选择物理像素区域", "Physical pixel region selected") +
                    f": X {region.x} · Y {region.y} · {region.width} × {region.height} px")
            if on_close:
                on_close(region is not None)

        # The single in-memory snapshot is taken after hiding our own window.
        self.withdraw()
        self.update_idletasks()
        try:
            self._region_selector = ScreenRegionSelector(self, current=current, on_done=complete, translate=self._t)
        except Exception as exc:
            self._region_selector = None
            restore()
            messagebox.showerror(self._dt("无法框选区域", "Could not select a region"), str(exc), parent=self)
            if on_close:
                on_close(False)

    def _run_capture(self) -> None:
        self._output_context.sink = self.sink
        try:
            self._output_context.curve = OutputCurveFilter()
            self._normalize_limits()
            fps = max(1, min(120, self.fps.get()))
            period = 1.0 / fps
            if self._live_source_mode == "Audio Only":
                self._run_audio(period)
                return
            analyzer = make_analyzer(
                visual_settings=self._visual_settings, hybrid_source=self.rtm_hybrid_source.get(),
                hybrid_v2_pose_enabled=self.hybrid_v2_pose_enabled.get(),
                tracker_mode=self._tracker_internal(self.tracker_mode.get()),
                output_mode=self.output_mode.get(),
                smoothing=self.smoothing.get(),
                deadzone=self.deadzone.get(),
                motion_gain=self.motion_gain.get(),
                enable_smoothing=self.enable_smoothing.get(),
                enable_deadzone=self.enable_deadzone.get(),
                response_curve=self.response_curve.get(),
                visual_stroke_scale=self.visual_stroke_scale.get(),
                l0_jitter_guard=self.enable_l0_jitter_guard.get(),
                l0_guard_strength=self.l0_guard_strength.get(),
                enable_extreme_reset=self.enable_extreme_reset.get(),
                enable_endpoint_guard=self.enable_endpoint_guard.get(),
                endpoint_margin=self.endpoint_margin_pct.get() / 200.0,
                pose_dance_l0=False,
                pose_dance_six_axis=False,
                pose_l0_weight=0.0,
                pose_six_axis_weight=0.0,
                pose_v2_dance_six_axis=False,
                pose_v2_l0_weight=0.0,
                pose_v2_six_axis_weight=0.0,
                rtm_pose_2d_enabled=self._rtm_pose_2d_mode_active(),
                rtm_pose_2d_model_path=self.rtm_pose_2d_model_path.get(),
                rtm_pose_3d_enabled=self._rtm_pose_3d_mode_active(),
                rtm_pose_3d_model_path=self.rtm_pose_3d_model_path.get(),
                rtm_pose_3d_weight=1.0 if self._rtm_pose_mode_active() else 0.0,
                rtm_hybrid_l0_enabled=self._rtm_pose_mode_active() and self.rtm_hybrid_l0_enabled.get(),
                rtm_hybrid_l0_weight=self.rtm_hybrid_l0_weight.get() / 100.0,
                rtm_pose_gpu_enabled=self.rtm_pose_gpu_enabled.get(),
                rtm_pose_gpu_backend=self.rtm_pose_gpu_backend.get(),
                rtm_pose_flow_enabled=self.rtm_pose_flow_enabled.get(),
                rtm_pose_kalman_enabled=self.rtm_pose_kalman_enabled.get(),
                compression_latency=self.compression_latency.get(),
            )
            output = self._new_output(self.interval_ms.get())
            if self._live_source_mode == "Video File":
                self._run_video(analyzer, output, period, 0.0)
            else:
                self._run_screen(analyzer, output, period, 0.0)
        except OutputWriteError as exc:
            pass  # _emit_command already queued one failure for the GUI thread.
        except Exception as exc:
            self._queue_latest({"error": f"{type(exc).__name__}: {exc}"})
        finally:
            self._queue_latest({"capture_stopped": True})

    def _run_screen(
        self,
        analyzer: RealtimeAnalyzer,
        output: MultiAxisSafeOutput,
        period: float,
        last_preview: float,
    ) -> None:
        region = self._screen_region_snapshot
        sequence = 0
        measured_at = time.perf_counter()
        processed = 0
        processing_fps = 0.0
        with LatestScreenCapture(region, lambda: self._capture_target_fps, capture_factory=ScreenCapture) as capture:
            while not self.stop_event.is_set():
                sample = capture.next_frame(sequence)
                if sample is None or self.stop_event.is_set():
                    continue
                sequence = sample.sequence
                now = time.perf_counter()
                if now - measured_at >= 0.5:
                    processing_fps = processed / (now - measured_at)
                    measured_at, processed = now, 0
                stats = (sample.fps, processing_fps, max(0.0, now - sample.captured_at) * 1000.0)
                last_preview = self._process_frame(analyzer, output, sample.bgr, last_preview, capture_stats=stats, timestamp=sample.captured_at)
                processed += 1

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
        visual = isinstance(analyzer, LabAnalyzer)
        native_fps = video_fps if np.isfinite(video_fps) and video_fps > 0 else 30.0
        playback_start = time.perf_counter()
        index = 0
        try:
            while not self.stop_event.is_set():
                started = time.perf_counter()
                if visual:
                    target = int((started - playback_start) * native_fps)
                    while index < target and not self.stop_event.is_set():
                        if not cap.grab():
                            break
                        index += 1
                        analyzer.skipped += 1
                ok, frame = cap.read()
                if not ok:
                    self._queue_latest({"error": "视频分析完成"})
                    break
                last_preview = self._process_frame(analyzer, output, frame, last_preview, timestamp=index / native_fps)
                index += 1
                sleep_for = (playback_start + index / native_fps - time.perf_counter()) if visual else period - (time.perf_counter() - started)
                if sleep_for > 0:
                    self.stop_event.wait(sleep_for)
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
                positions = self._fit_output_curve(positions)
                self._refresh_live_output_mapping(output)
                command = output.next_command(positions, result.activity)
                command_text = self._emit_command(command)
                if self.recorder.is_recording:
                    self.recorder.add(self._positions_with_travel_controls(positions), *self._endpoint_options)
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
        capture_stats: tuple[float, float, float] | None = None,
        timestamp: float | None = None,
    ) -> float:
        visual = isinstance(analyzer, LabAnalyzer)
        analysis_frame = frame if visual else self._prepare_analysis_frame(frame)
        self._refresh_live_output_mapping(output)
        if visual:
            analyzer.configure(self._visual_settings)
            if analyzer.pose and analyzer.settings.pose_fast_v1:
                analyzer.pose_fast.remember_output(output.input_position('L0'))
            elif not analyzer.pose:
                analyzer.remember_l0_output(output.input_position('L0'))
            result = analyzer.process(analysis_frame, timestamp=timestamp)
            if analyzer.settings != self._visual_settings or self.stop_event.is_set():
                return last_preview
        else:
            generation = self._visual_settings.generation
            if getattr(analyzer, "_reference_generation", generation) != generation:
                analyzer.reset()
            analyzer._reference_generation = generation
            result = analyzer.process(analysis_frame)
            if generation != self._visual_settings.generation or self.stop_event.is_set():
                return last_preview
        positions = self._visual_output_positions(analyzer, result.positions)
        generated_axes = self._generated_l0_axes(analyzer)
        positions = self._fit_output_curve(positions, passthrough=generated_axes)
        command = output.next_command(positions, 1.0 if generated_axes else result.activity)
        command_text = self._emit_command(command)
        if self.recorder.is_recording:
            self.recorder.add(self._positions_with_travel_controls(positions), *self._endpoint_options)
        now = time.perf_counter()
        if now - last_preview >= 1.0 / min(60, self._capture_target_fps):
            self._queue_latest(
                {
                    "visual_frame": analyzer.visual_frame if visual else VisualFrame(
                        (analysis_frame, result.preview_bgr), None, False, self._visual_settings.generation,
                        reference=getattr(analyzer, "motion_reference", None)),
                    "command": command_text,
                    "activity": result.activity,
                    "record_count": self.recorder.action_count,
                    "capture_stats": capture_stats,
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
        # Preserve the complete ROI and its aspect ratio, including thin strips.
        scale = max(scale, min(1.0, 64.0 / max(1, min(width, height))))
        target_width = max(1, int(round(width * scale)))
        target_height = max(1, int(round(height * scale)))
        if target_width == width and target_height == height:
            return frame
        return cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_AREA)

    def _capture_preview_for_display(self, capture_frame: object, analysis_frame: object, analysis_preview: object) -> object:
        try:
            capture_height, capture_width = capture_frame.shape[:2]
            analysis_height, analysis_width = analysis_frame.shape[:2]
            preview_height, preview_width = analysis_preview.shape[:2]
        except AttributeError:
            return analysis_preview
        display = analysis_preview
        if self._rtm_pose_mode_active() and preview_height == analysis_height and preview_width > analysis_width:
            overlay = analysis_preview[:, :analysis_width].copy()
            panel = analysis_preview[:, analysis_width:].copy()
            overlay_display = cv2.resize(overlay, (capture_width, capture_height), interpolation=cv2.INTER_NEAREST)
            panel_width = max(1, int(round(panel.shape[1] * capture_height / max(1, analysis_height))))
            panel_display = cv2.resize(panel, (panel_width, capture_height), interpolation=cv2.INTER_NEAREST)
            return np.concatenate((overlay_display, panel_display), axis=1)
        if preview_height == analysis_height and preview_width >= analysis_width:
            display = analysis_preview[:, :analysis_width].copy()
        try:
            display_height, display_width = display.shape[:2]
        except AttributeError:
            return analysis_preview
        if display_width == capture_width and display_height == capture_height:
            return display
        return cv2.resize(display, (capture_width, capture_height), interpolation=cv2.INTER_NEAREST)

    def _analysis_frame_scale(self) -> float:
        try:
            value = max(-5, min(5, int(round(float(self.compression_latency.get())))))
        except (tk.TclError, ValueError):
            return 1.0
        if value <= 0:
            return 1.0
        return max(0.60, 1.0 - value * 0.08)

    def _active_axes(self) -> list[str]:
        hybrid_only = self.source_mode.get() != "Audio Only" and self._tracker_internal(self.tracker_mode.get()) == HYBRID_MODE
        return ["L0"] if hybrid_only or self.output_mode.get() != "Six Axis" else SIX_AXES.copy()

    def _visual_output_positions(self, analyzer: RealtimeAnalyzer, positions: dict[str, float]) -> dict[str, float]:
        if getattr(analyzer, "tracker_mode", "") == HYBRID_MODE:
            return {"L0": positions["L0"]}
        if getattr(analyzer, "tracker_mode", "") == RTM_POSE_2D_MODE:
            positions = rtm_l0_amplitude(positions)
            if getattr(analyzer, "pose_l0_output", None) is not None:
                positions['L0'] = analyzer.pose_l0_output
            if self._generated_l0_axes(analyzer):
                positions["L0"] = analyzer.generated_l0
        if analyzer._rtm_pose_enabled() and analyzer.output_mode == "Six Axis":
            positions = rtm_rotation_amplitudes(positions)
        if (isinstance(analyzer, LabAnalyzer) and analyzer.pose and analyzer.settings.pose_pattern):
            excluded = ('L0',) if analyzer.pose_recovery.transition_at is not None else self._generated_l0_axes(analyzer)
            positions = analyzer.pose_pattern.apply(positions, excluded=excluded)
        return dict(positions) if isinstance(analyzer, LabAnalyzer) else self._apply_six_axis_tuning(positions)

    def _apply_six_axis_tuning(self, positions: dict[str, float]) -> dict[str, float]:
        if self.output_mode.get() != "Six Axis":
            return dict(positions)
        tracker_mode = self._tracker_internal(self.tracker_mode.get())
        if not RealtimeAnalyzer._is_hybrid_analysis_mode(tracker_mode) or self._rtm_pose_mode_active():
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

    def _axis_position_scales(self) -> dict[str, float]:
        scales = {"L0": max(0.0, min(3.0, float(self.l0_travel_scale.get())))}
        six_axis_scale = max(0.0, min(3.0, float(self.global_travel_scale.get())))
        for axis in ("L1", "L2", "R0", "R1", "R2"):
            axis_scale = max(0.0, min(3.0, float(self.six_axis_travel_scale_vars[axis].get())))
            scales[axis] = max(0.0, min(3.0, six_axis_scale * axis_scale))
        return scales

    def _axis_position_inverts(self) -> dict[str, bool]:
        global_invert = bool(self.six_axis_travel_invert.get())
        return {
            axis: global_invert ^ bool(self.axis_output_invert_vars[axis].get())
            for axis in ("L1", "L2", "R0", "R1", "R2")
        }

    def _positions_with_travel_controls(self, positions: dict[str, float]) -> dict[str, float]:
        scales = self._axis_position_scales()
        inverts = self._axis_position_inverts()
        mapped: dict[str, float] = {}
        for axis, raw_value in positions.items():
            try:
                value = max(0.0, min(1.0, float(raw_value)))
            except (TypeError, ValueError):
                value = 0.5
            scale = scales.get(axis, 1.0)
            value = max(0.0, min(1.0, 0.5 + (value - 0.5) * scale))
            if (axis == "L0" and self.invert.get()) or (axis != "L0" and inverts.get(axis, False)):
                value = 1.0 - value
            mapped[axis] = value
        return mapped

    def _mark_live_output_mapping_dirty(self) -> None:
        self._live_output_mapping_dirty = True

    def _refresh_live_output_mapping(self, output: MultiAxisSafeOutput) -> None:
        if not self._live_output_mapping_dirty:
            return
        self._live_output_mapping_dirty = False
        axes = self._active_axes()
        output.axes = axes
        output.update_mapping(
            min_value=self.min_value.get(),
            max_value=self.max_value.get(),
            invert_l0=self.invert.get(),
            axis_limits=self._axis_limits(axes),
            position_scale=self.global_travel_scale.get(),
            axis_position_scales=self._axis_position_scales(),
            axis_position_inverts=self._axis_position_inverts(),
            max_step=self.max_step.get() if self.enable_speed_limit.get() else 9999,
            endpoint_slowdown=self._endpoint_options[0],
            slowdown_margin=self._endpoint_options[1],
        )

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
            axis_position_scales=self._axis_position_scales(),
            axis_position_inverts=self._axis_position_inverts(),
            enable_extreme_reset=self.enable_extreme_reset.get(),
            extreme_hold_ms=self.extreme_hold_ms.get(),
            enable_endpoint_guard=self.enable_endpoint_guard.get(),
            endpoint_margin=self.endpoint_margin_pct.get() / 100.0,
            couple_l0_translation=self.source_mode.get() != "Audio Only" and self._tracker_internal(self.tracker_mode.get()) in (RTM_POSE_2D_MODE, HYBRID_V2_MODE) and self.output_mode.get() == "Six Axis",
            coupling_endpoint_gain=0.5 if self._tracker_internal(self.tracker_mode.get()) == RTM_POSE_2D_MODE else 1.0,
            coupling_middle_gain=3.5 if self._tracker_internal(self.tracker_mode.get()) == RTM_POSE_2D_MODE else 2.5,
            coupling_peak_position=2/3 if self._tracker_internal(self.tracker_mode.get()) == RTM_POSE_2D_MODE else .5,
            coupling_lower_knot=(1/3, 1.0) if self._tracker_internal(self.tracker_mode.get()) == RTM_POSE_2D_MODE else None,
            couple_l0_rotation=self.source_mode.get() != 'Audio Only' and self._tracker_internal(self.tracker_mode.get()) == RTM_POSE_2D_MODE and self.output_mode.get() == 'Six Axis',
            sync_timing=True,
            endpoint_slowdown=self._endpoint_options[0],
            slowdown_margin=self._endpoint_options[1],
        )

    def _queue_latest(self, item: dict[str, object]) -> None:
        if any(key in item for key in ("connection_success", "connection_error", "output_failed", "device_scan", "gpu_event", "capture_stopped", "export_done", "error")):
            self.control_queue.put(item)
            return
        try:
            if self.frame_queue.full():
                self.frame_queue.get_nowait()
            self.frame_queue.put_nowait(item)
        except queue.Full:
            pass

    def _poll_worker(self) -> None:
        self._refresh_region_controls()
        latest_preview = None
        latest_visual = None
        if self.worker is not None and not self.worker.is_alive():
            self.worker = None
            self._set_device_controls_busy(self._connecting)
            self._refresh_start_button_text()
        try:
            while True:
                try:
                    item = self.control_queue.get_nowait()
                except queue.Empty:
                    item = self.frame_queue.get_nowait()
                if "gpu_event" in item:
                    self._finish_gpu_event(item)
                if "connection_success" in item:
                    self._finish_connection_success(item)
                if "connection_error" in item:
                    self._finish_connection_error(item)
                if "output_failed" in item:
                    self._finish_output_failure(item)
                if "error" in item:
                    self.status.set(str(item["error"]))
                if "status_text" in item:
                    self.status.set(str(item["status_text"]))
                if "preview" in item:
                    latest_preview = item["preview"]
                if "visual_frame" in item:
                    latest_visual = item["visual_frame"]
                if item.get("capture_stats") is not None and not self.stop_event.is_set():
                    sampled, analyzed, age_ms = item["capture_stats"]
                    self.capture_rate_text.set(self._dt(
                        f"采集 {sampled:.0f} / 分析 {analyzed:.0f} FPS · 输入帧龄 {age_ms:.0f} ms",
                        f"Capture {sampled:.0f} / Analysis {analyzed:.0f} FPS · Input age {age_ms:.0f} ms"))
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
                if "rtm_model_path" in item:
                    model_path = str(item["rtm_model_path"])
                    self.rtm_pose_2d_model_path.set(model_path)
                    if self._rtm_pose_3d_download_target is not None:
                        self._rtm_pose_3d_download_target.set(model_path)
                    self._refresh_active_rtm_pose_model_path()
                if "rtm_download_status" in item:
                    self.rtm_model_download_status_text.set(str(item["rtm_download_status"]))
                if "rtm_download_done" in item:
                    self._rtm_pose_3d_downloading = False
                    self._rtm_pose_3d_download_target = None
                    self._rtm_pose_3d_download_mode = None
                    self.rtm_model_download_button_text.set(self._t("下载/自动检测模型"))
                if "capture_stopped" in item:
                    if self.worker and not self.worker.is_alive():
                        self.worker = None
                        self._set_device_controls_busy(False)
                    self._refresh_start_button_text()
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
        if latest_visual is not None:
            self.integrated_preview.display(latest_visual)
        elif latest_preview is not None:
            self._update_preview(latest_preview)
        self.after(16 if self.worker is not None else 50, self._poll_worker)

    def _update_preview(self, frame_bgr: object) -> None:
        self.integrated_preview.display(VisualFrame((frame_bgr, frame_bgr), None, False, self._visual_settings.generation))

    def _redraw_preview_image(self) -> None:
        self.integrated_preview.render()

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
            label = self._t("向下限移动")
        elif delta >= 22:
            label = self._t("向上限移动")
        elif ratio <= 0.22:
            label = self._t("下限端点")
        elif ratio >= 0.78:
            label = self._t("上限端点")
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
        pad = 24
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
        canvas.create_text(x, pad - 2, text=self._t("上限方向"), anchor="s", fill="#555")
        canvas.create_text(x, height - pad + 2, text=self._t("下限方向"), anchor="n", fill="#555")

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
        pad_t = 34
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
        self._analysis_preferences.remember(self._analysis_variables())
        self.config_model.extra["analysis_profiles"] = {key: dict(value) for key, value in self._analysis_preferences.profiles.items()}
        cfg = self.config_model
        try:
            region = self._read_screen_region()
        except ValueError:
            pass  # Keep the last complete rectangle while an entry is unfinished.
        else:
            cfg.x, cfg.y, cfg.width, cfg.height = region.x, region.y, region.width, region.height
        cfg.fps = capture_fps(self.fps.get())
        cfg.extra["output_curve_fitting"] = bool(self.output_curve_fitting.get())
        cfg.extra["endpoint_slowdown_enabled"] = self._endpoint_options[0]
        cfg.extra["endpoint_slowdown_pct"] = round(self._endpoint_options[1]*100)
        cfg.extra["source_mode"] = self.source_mode.get()
        cfg.extra["video_path"] = self.video_path.get()
        cfg.extra["output_mode"] = self.output_mode.get()
        cfg.extra["play_preset_level"] = self.play_preset_level.get()
        cfg.extra["six_axis_intensity"] = self.six_axis_intensity.get()
        cfg.extra["six_axis_jitter_reduction"] = self.six_axis_jitter_reduction.get()
        cfg.extra["six_axis_sensitivity_level"] = self.six_axis_sensitivity_level.get()
        cfg.extra["show_more_settings"] = self.show_more_settings.get()
        cfg.extra["show_measurement_limits"] = self.show_measurement_limits.get()
        cfg.extra["show_six_axis_tuning"] = self.show_six_axis_tuning.get()
        cfg.extra["show_rtm_pose_3d_settings"] = self.show_rtm_pose_3d_settings.get()
        cfg.extra["show_six_axis_travel_scales"] = self.show_six_axis_travel_scales.get()
        cfg.extra["six_axis_travel_scales"] = {
            axis: self.six_axis_travel_scale_vars[axis].get()
            for axis in ("L1", "L2", "R0", "R1", "R2")
        }
        cfg.extra["six_axis_travel_invert"] = self.six_axis_travel_invert.get()
        cfg.extra["axis_output_inverts"] = {
            axis: self.axis_output_invert_vars[axis].get()
            for axis in ("L1", "L2", "R0", "R1", "R2")
        }
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
        cfg.extra["pose_v2_dance_six_axis"] = self.pose_v2_dance_six_axis.get()
        cfg.extra["pose_v2_l0_analysis"] = self.pose_v2_l0_analysis.get()
        cfg.extra["pose_v2_six_axis_analysis"] = self.pose_v2_six_axis_analysis.get()
        cfg.extra["pose_v2_l0_weight"] = self.pose_v2_l0_weight.get()
        cfg.extra["pose_v2_six_axis_weight"] = self.pose_v2_six_axis_weight.get()
        cfg.extra["rtm_pose_2d_model_path"] = self.rtm_pose_2d_model_path.get()
        for key in ("rtm_pose_3d_enabled", "rtm_pose_3d_model_path", "rtm_pose_3d_weight"):
            cfg.extra.pop(key, None)
        cfg.extra["visual_processing_edge"] = self.visual_processing_edge.get()
        cfg.extra["hybrid_v2_pose_enabled"] = self.hybrid_v2_pose_enabled.get()
        cfg.extra['v2_l0_reference'] = self.v2_l0_reference.get()
        cfg.extra["rtm_pose_reject_enabled"] = self.rtm_pose_reject_enabled.get()
        cfg.extra["rtm_pose_micro_smooth_enabled"] = self.rtm_pose_micro_smooth_enabled.get()
        cfg.extra["rtm_hybrid_source"] = HYBRID_V2_MODE
        cfg.extra["rtm_hybrid_l0_enabled"] = self.rtm_hybrid_l0_enabled.get()
        cfg.extra["pose_auto_l0_enabled"] = self.pose_auto_l0_enabled.get()
        cfg.extra["pose_pattern_enabled"] = self.pose_pattern_enabled.get()
        cfg.extra["pose_fast_v1_enabled"] = self.pose_fast_v1_enabled.get()
        cfg.extra["rtm_hybrid_l0_weight"] = max(1, min(100, int(self.rtm_hybrid_l0_weight.get())))
        cfg.extra["rtm_pose_gpu_enabled"] = self.rtm_pose_gpu_enabled.get()
        cfg.extra["rtm_pose_gpu_backend"] = self.rtm_pose_gpu_backend.get()
        cfg.extra["rtm_pose_flow_enabled"] = self.rtm_pose_flow_enabled.get()
        cfg.extra["rtm_pose_kalman_enabled"] = self.rtm_pose_kalman_enabled.get()
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
        self._cancel_gpu_tasks()
        if self._config_save_after_id is not None:
            try:
                self.after_cancel(self._config_save_after_id)
            except tk.TclError:
                pass
            self._config_save_after_id = None
        self._save_config()
        self.stop()
        self.disconnect_sink()
        self.preview_bridge.stop()
        self.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(prog="osr6-realtime", description=f"{APP_NAME} GUI")
    parser.add_argument("--auto-connect", action="store_true", help="Connect to the selected serial device at startup")
    parser.add_argument("--center", action="store_true", help="Send center command after auto-connect")
    parser.add_argument("--language", choices=("auto", "zh", "cn", "en"), default="auto", help="Interface language override")
    parser.add_argument("--smoke", action="store_true", help="Check UI startup with temporary Log-only settings")
    args = parser.parse_args()
    if args.smoke:
        from unittest.mock import patch
        with patch.object(AppConfig, "load", side_effect=lambda: AppConfig(last_sink="Log only")), patch.object(AppConfig, "save"):
            app = OsrScreenApp(enforce_age_gate=False, ui_language="en" if args.language == "auto" else args.language)
            errors = []
            app.report_callback_exception = lambda *details: errors.append(details)
            app.after(1500, app.on_close)
            app.mainloop()
            if errors:
                raise RuntimeError(f"UI callback failed: {errors}")
    else:
        app = OsrScreenApp(auto_connect=args.auto_connect, center_on_connect=args.center, ui_language=args.language)
        app.mainloop()

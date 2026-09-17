# SL25 状态灯 PCB，Rev A

这是一块面向个人原型的 25 × 25 mm 双层 USB 状态灯 PCB，可用于正面宽、高均不超过 30 mm 的外壳。当前完成硬件设计和软件规则检查，尚未制作、焊接或实测。固件、Windows 状态采集程序和外壳工程不包含在本次交付中。

## 打开工程

使用 KiCad 10 打开 `sl25.kicad_pro`，分别进入原理图和 PCB 编辑器。符号、封装和所用 STEP 模型均随工程提供。KiCad 三维查看器可查看装配效果。

| 文件 | 内容 |
| --- | --- |
| `sl25.kicad_sch` | 单页原理图 |
| `sl25.kicad_pcb` | 已布线、铺铜的 PCB |
| `BOM.csv` | 逐项材料表，含准确型号与安装面 |
| `MATERIALS.md` | 中文采购及装配说明 |
| `checks/erc.rpt`、`checks/drc.rpt` | 最终规则检查报告 |
| `fabrication/` | Gerber、独立 PTH/NPTH 钻孔、贴装坐标 |
| `mechanical/sl25.step` | 含元件的装配 STEP，供外壳设计参考 |
| `mechanical/interface.json` | 板框、安装孔和接口位置 |
| `preview/` | 原理图 SVG 及 PCB 正反面、立体预览 |

本文件夹中的材料表替代之前讨论的 Pico 开发板和洞洞板采购方案。USB-C 插座必须匹配指定封装，不能仅凭“16 脚 Type-C”购买替代件。

## 电路

- USB-C 仅使用 USB 2.0 数据与 5 V 供电，CC1、CC2 各自用 5.1 kΩ 电阻接地。没有 USB PD 升压、电池或外部电源接口。
- CH552G 使用 SOP-16 窄体封装、内部振荡器和内部 USB 上拉。VCC 接 USB 5 V；V33 仅接 100 nF 去耦，不能短接到 5 V。
- USBLC6-2SC6 在背面保护 D+、D-；C4 是其电源去耦。插座金属壳直接接 GND，壳体焊脚直接接地铜皮。
- 单颗共阴 RGB 灯的每个阳极分别串 1 kΩ，限流后由 MCU GPIO 驱动。以 5.25 V 和 1% 电阻下限估算，即使忽略 LED 压降，单路电流也不超过 5.31 mA。
- JP1 平时保持断开；通过 10 kΩ 将 D+ 临时拉到 5 V，在上电时请求兼容工厂 USB ISP 的下载模式。购买带工厂 USB ISP 的 CH552G。TP3–TP6 保留专用编程器信号，不能当作通用 SPI 外设接口。
- R7 将高有效 RESET 下拉到 GND。固件仍应采用上电复位和看门狗。

| 功能 | CH552G 物理脚 | GPIO | 备注 |
| --- | --- | --- | --- |
| 红灯 | 3 | P1.5 | PWM1；高电平亮 |
| 绿灯 | 11 | P3.4 | PWM2；高电平亮 |
| 蓝灯 | 9 | P1.1 | 普通 GPIO，默认关闭 |
| USB D+ | 12 | P3.6 | USB 功能 |
| USB D- | 13 | P3.7 | USB 功能 |
| RESET | 6 | RST | 高有效 |

红加绿形成黄色。PWM 占空比需在样板和最终灯罩上调整，不能保证两路相同占空比就得到视觉上均匀的黄色。

## 固件与电脑端约定

建议后续固件使用 USB HID 接收颜色、亮度和灯效命令，Windows 程序通过 HID 库发送，无需增加 USB 转串口芯片。未配置、USB 挂起和主机命令超时应关闭 LED；初始化时先将三路输出置低，再使能输出，红绿用硬件 PWM，蓝色默认不用。

USB VID/PID 和描述符在固件阶段确定，不能未经授权用于发布产品。USB 功耗描述和挂起电流必须与实测匹配。当前电路未验证 USB 枚举、信号质量、EMC 或 ESD 性能；放置保护器件不等于通过系统级认证。

Windows 桌面版 Codex 的实时状态来源仍需单独验证。PCB 本身只接收灯光命令，不会自动读取 Codex。

## 制板与机械

建议首批 5 块样板：双层 FR-4、1.6 mm、1 oz 铜、绿色阻焊、白色丝印；优先选择平整表面处理，USB-C 手焊可选沉金。没有阻抗控制声明。

布线宽度 0.20 mm，设计最小铜间距 0.15 mm；过孔 0.60 / 0.30 mm。安装孔 2.20 mm，LED 孔 0.90 mm；PTH 和 NPTH 分开导出。USB4105 厂家推荐焊盘到定位孔的最近距离约 0.194 mm，本项目孔到铜间距规则设为 0.18 mm；下单时需要工厂支持这一要求。没有通过忽略 DRC 错误来放行设计。

板框圆角半径 1 mm。以 PCB 左上角为平面坐标原点，X 向右、Y 向下：

| 项目 | 位置或尺寸，mm |
| --- | --- |
| PCB 外形 | 25 × 25 × 1.6 |
| H1、H2 安装孔 | (2.7, 2.7)、(22.3, 2.7)，孔径 2.2 |
| D1 光学中心 | (12.5, 3.5)，靠近板上边，不在板中心 |
| USB 插座封装原点 | (12.5, 21.15)，插拔方向朝下边 |
| USB 插座本体 | 厂家宽 8.94、长 7.35、高 3.31 |
| LED 引脚孔 | X=9.2615 / 11.4205 / 13.5795 / 15.7385；Y=3.5 |

建议外壳先按 30 × 30 × 25 mm 预留，厚度尚未与用户锁定。壁厚与装配间隙需在外壳建模时分配，底面需留出 U2、C4 和焊点空间。两个 M2 安装柱配合底部承托或导轨固定 PCB，避免 USB 插拔力只作用在焊脚上。

LED 需用工具夹住靠近封装的一段引脚，再将外侧引脚整形成 2.159 mm 间距，封装底面离板约 3 mm，不要紧贴树脂根部弯折。灯珠顶面及焊接公差在外壳内至少按板上方 12.5 mm 预留，再留混光距离。STEP 中 LED 为通用 KiCad 模型，蓝色外观只是模型材质；实际指定灯珠为透明 RGB。该模型不能替代实物高度和透光测试。

STEP 使用 PCB 左上角 `(100,100)` 作为导出原点；CAD 的 Y 轴可能与上述 PCB 屏幕坐标相反，导入后以安装孔和 USB 方向识别朝向。

## 验证状态

2026-09-05 使用 KiCad 10.0.6：ERC 为 0 错误、0 警告；DRC 为 0 违规、0 未连接、0 原理图一致性问题。检查了厂家引脚图、封装尺寸图和正反面三维预览。

这些是设计文件检查，不能替代打样验证。未执行固件烧录、供电测量、USB 插头正反插、亮度混色、热稳定、休眠恢复及外壳装配测试。USB 数据布线为短距离原型布线，未做阻抗提取或信号完整性仿真。

## 设计依据与库许可

- WCH CH552/CH551 数据手册 V1G，第 3–4、19、31–33、70 页；`../reference/CH552.pdf` 为 WCH 原文的 Adafruit 镜像。厂家入口：https://www.wch-ic.com/downloads/CH552DS1_PDF.html
- Kingbright WP154A4SUREQBFZGC，第 1–2 页：https://www.kingbrightusa.com/images/catalog/spec/WP154A4SUREQBFZGC.pdf
- GCT USB4105 厂家图纸：https://gct.co/files/drawings/usb4105.pdf
- ST USBLC6-2SC6：https://www.st.com/resource/en/datasheet/usblc6-2.pdf
- ch55xduino 工程及 USB ISP 上电方式：https://github.com/DeqingSun/ch55xduino
- 随附封装、STEP 模型来自 KiCad 官方库，适用 KiCad 库许可及其例外：https://www.kicad.org/libraries/license/ 。通用芯片模型只表示封装，并不代表芯片品牌或实物标识。

## 重新生成

已交付文件可以直接在 KiCad 中编辑。只有需要重新生成初始设计时才执行以下脚本；重新生成会覆盖手工改板结果，先保留自己的修改。

在项目根目录运行 KiCad 自带 Python：依次执行 `hardware/generate_board.py`、`hardware/route_board.py`、`hardware/finish_board.py`。默认工具路径是本机的 `E:/Kicard`，其他电脑可调整 `KICAD_FOOTPRINT_DIR`、`KICAD_3DMODEL_DIR`。渲染需要 KiCad 用户缓存目录可写，否则可能只显示裸板。

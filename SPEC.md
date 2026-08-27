# CSRForge v0.1 Specification

## 1. 项目定位

CSRForge 是一个面向数字 IC 设计流程的轻量级 CSR 自动生成与验证工具。

v0.1 的目标不是实现一个功能完备的寄存器生成框架，而是建立一条最小但完整、可执行、可验证的链路：

```text
CSV Register Spec
        ↓
Parser
        ↓
Semantic Checker
        ↓
Canonical IR
        ↓
APB3 CSR RTL Generator
        ↓
Self-checking Verification
        ↓
Icarus Verilog Simulation
        ↓
PASS / FAIL
```

同时可从同一份 CSR 规格生成：

* SystemVerilog CSR RTL
* C Header
* Markdown Register Documentation

项目核心卖点为：

> **Spec-to-Simulation，而不仅是 Spec-to-RTL。**

CSRForge 的运行不依赖任何大语言模型。

AI Coding Agent（Codex）仅用于项目开发过程中的需求分解、代码实现、测试、调试和重构，不属于 CSRForge v0.1 的运行时依赖。

---

# 2. v0.1 范围

## 2.1 支持功能

CSRForge v0.1 固定支持：

| 项目                  | v0.1 定义                     |
| --------------------- | ----------------------------- |
| RTL Language          | SystemVerilog                 |
| Bus Protocol          | APB3 Slave                    |
| Data Width            | 32 bit                        |
| Address Width         | 32 bit                        |
| Address Type          | Local byte offset             |
| Register Alignment    | 4 Byte                        |
| Access Type           | RW / RO / W1C                 |
| Reset                 | Active-low asynchronous reset |
| APB Wait State        | 不支持                        |
| `PREADY`              | 恒为 `1'b1`                   |
| Reserved Bits         | Read 0 / Write Ignore         |
| Base Address          | 不进入 CSR RTL                |
| Functional Simulation | Icarus Verilog                |
| Static RTL Check      | Verilator                     |
| Input Format          | CSV only                      |

---

## 2.2 v0.1 明确不支持

以下功能不属于 v0.1 范围：

* AXI4-Lite
* AHB / AHB-Lite
* APB wait state
* `PSTRB` / byte enable
* UVM
* UVM RAL
* GUI
* Excel
* YAML
* JSON 直接作为用户输入
* RC
* RS
* W1S
* W0C
* WO
* Functional Coverage Closure
* CDC 自动处理
* 自动 RTL 修复
* Runtime LLM / Agent
* 自然语言修改寄存器规格
* SoC Base Address Decode

除非用户明确修改本 SPEC，否则开发过程中不得自动增加以上功能。

---

# 3. 开发原则

CSRForge v0.1 遵循以下正确性验证顺序：

```text
Stage 0
冻结行为规格

Stage 1
Golden RTL
+
Golden TB
        ↓
Icarus PASS

Stage 2
CSV Parser
+
IR
+
Checker

Stage 3
Generated RTL
+
Golden TB
        ↓
Icarus PASS

Stage 4
Generated RTL
+
Generated TB
        ↓
Icarus PASS

Stage 5
C Header
+
Markdown
+
CLI
+
README

Stage 6
Verilator Integration
+
GitHub Actions
```

其中：

> **Stage 3 是项目最重要的正确性里程碑。**

Generated RTL 必须首先通过人工编写、独立维护的 Golden TB。

Golden TB 在后续阶段不得删除。

---

# 4. 输入 CSR 规格

## 4.1 CSV 格式

v0.1 首先支持 CSV。

推荐字段：

```text
Register,Offset,Field,Bits,Access,Reset
```

示例：

```csv
Register,Offset,Field,Bits,Access,Reset
CTRL,0x00,EN,0,RW,0
CTRL,0x00,MODE,2:1,RW,0
STATUS,0x04,BUSY,0,RO,0
IRQ_STATUS,0x08,DONE,0,W1C,0
```

---

## 4.2 字段定义

### Register

寄存器名称。

要求：

* 非空
* 使用可移植 identifier：`[A-Za-z_][A-Za-z0-9_]*`
* 同一个 Register 可以出现多行，用于描述多个 Field

---

### Offset

寄存器相对于 CSR block 起始地址的 byte offset。

例如：

```text
0x00
0x04
0x08
0x0C
```

要求：

```text
0 <= offset <= 0xFFFF_FFFF
offset % 4 == 0
```

CSRForge RTL 不处理 SoC global base address。

例如：

```text
SoC Base Address = 0x4000_0000
CSR Offset       = 0x08
```

RTL 只负责：

```text
0x08
```

外层 interconnect 负责：

```text
0x4000_0000
```

到 CSR local address 的转换。

---

### Field

寄存器字段名称。

要求：

* 非空
* 使用可移植 identifier：`[A-Za-z_][A-Za-z0-9_]*`
* 同一寄存器内 Field 名称不得重复

---

### Bits

允许格式：

```text
0
7
3:0
15:8
31:16
```

要求：

```text
0 <= lsb <= msb <= 31
```

---

### Access

v0.1 仅允许：

```text
RW
RO
W1C
```

其他类型必须报错。

---

### Reset

字段复位值。

允许十进制或标准整数格式。

必须满足：

```text
0 <= reset < 2^(field_width)
```

---

# 5. Parser 与 Canonical IR

## 5.1 Parser 职责

Parser 只负责：

```text
CSV
      ↓
标准化数据
      ↓
Canonical IR
```

Parser 不负责 RTL 生成。

Parser 不负责验证逻辑。

Parser 不负责 APB 行为实现。

---

## 5.2 Python 内部数据模型

程序内部优先使用 Python `dataclass`。

例如：

```python
@dataclass
class Field:
    name: str
    msb: int
    lsb: int
    access: AccessType
    reset: int


@dataclass
class Register:
    name: str
    offset: int
    fields: list[Field]
```

JSON 是 Canonical IR 的序列化表示，而不是程序内部主要操作的数据结构。

---

## 5.3 IR 原则

以下模块必须基于同一个 IR 工作：

```text
RTL Generator
C Header Generator
Markdown Generator
Verification Generator
```

但：

> RTL Generator 与 Verification Generator 不得共享寄存器访问语义的具体实现逻辑。

例如 W1C 的 RTL 实现和测试期望模型必须分别实现，以降低 DUT 和测试“错得一致”的风险。

---

# 6. Semantic Checker

Checker 必须至少检测以下错误。

## 6.1 地址未对齐

例如：

```text
CTRL,0x02,...
```

必须报错。

---

## 6.2 不同寄存器使用同一 Offset

以下情况非法：

```text
CTRL    0x00
STATUS  0x00
```

以下情况合法：

```text
CTRL    0x00 EN
CTRL    0x00 MODE
```

即：

```text
Same Register + Same Offset
→ Allowed

Different Register + Same Offset
→ Error
```

---

## 6.3 同一 Register 对应不同 Offset

例如：

```text
CTRL 0x00 EN
CTRL 0x04 MODE
```

必须报错。

---

## 6.4 Field Bit Overlap

例如：

```text
FIELD_A 3:1
FIELD_B 2:0
```

存在 bit overlap，必须报错。

---

## 6.5 Bit Range 非法

例如：

```text
32
40:20
1:3
```

必须报错。

---

## 6.6 Reset 超出 Field Width

例如：

```text
Bits  = 1:0
Reset = 4
```

字段只有 2 bit，Reset 最大只能为 `3`。

必须报错。

---

## 6.7 Access Type 非法

例如：

```text
Access = RWCUSTOM
```

必须报错。

---

## 6.8 Reserved Bits

Field 没有覆盖的 bit 自动视为 Reserved Bits。

例如：

```text
CTRL
bit 0   EN
bit 2:1 MODE
```

则：

```text
31:3
```

为 reserved。

Reserved Bits：

```text
Read  → 0
Write → ignored
```

Field 不需要从 bit 0 到 bit 31 连续覆盖。

---

# 7. APB3 接口规范

Generated CSR RTL 使用如下基础接口：

```systemverilog
module csr_regs (
    input  logic        PCLK,
    input  logic        PRESETn,

    input  logic        PSEL,
    input  logic        PENABLE,
    input  logic        PWRITE,
    input  logic [31:0] PADDR,
    input  logic [31:0] PWDATA,

    output logic [31:0] PRDATA,
    output logic        PREADY,
    output logic        PSLVERR,

    ...
);
```

硬件侧 Field 端口使用确定性命名规则，Register 和 Field 名称均转换为小写：

```text
RW  → {register}_{field}_o
RO  → {register}_{field}_i
W1C → {register}_{field}_set_i
```

例如 `IRQ_STATUS.DONE` 的 W1C hardware set input 固定为：

```systemverilog
irq_status_done_set_i
```

---

## 7.1 APB Transfer 定义

统一定义：

```systemverilog
apb_access = PSEL && PENABLE && PREADY;
apb_write  = apb_access && PWRITE;
apb_read   = apb_access && !PWRITE;
```

v0.1：

```systemverilog
assign PREADY = 1'b1;
```

不实现 wait state。

v0.1 固定以下采样与输出行为：

* APB write 在有效 ACCESS phase 完成的 `PCLK` 上升沿更新 CSR 状态
* W1C hardware set input 在 `PCLK` 上升沿采样
* RO field 在 APB read ACCESS phase 反映当前 hardware input
* `PRDATA` 使用组合读数据路径
* `PSLVERR` 使用组合输出，但仅允许在有效 ACCESS phase 拉高
* APB master 必须在 SETUP 到 ACCESS 期间保持地址、方向和写数据稳定

---

## 7.2 APB 时序

每次 transaction 必须遵循：

```text
SETUP
PSEL    = 1
PENABLE = 0

        ↓

ACCESS
PSEL    = 1
PENABLE = 1
```

当：

```text
PREADY = 1
```

时 ACCESS phase 完成。

背靠背 transaction 仍必须符合 APB 的 SETUP / ACCESS 规则。

不得简单地让 `PENABLE` 长时间保持为 1。

---

# 8. 地址行为

## 8.1 地址对齐

32-bit CSR 采用 4-byte alignment。

定义：

```systemverilog
addr_misaligned = (PADDR[1:0] != 2'b00);
```

---

## 8.2 地址未映射

如果访问的 local offset 不对应任何 Register：

```text
addr_unmapped = 1
```

---

## 8.3 PSLVERR

v0.1 定义：

```systemverilog
PSLVERR =
    PSEL &&
    PENABLE &&
    PREADY &&
    (addr_misaligned || addr_unmapped);
```

`PSLVERR` 仅在有效 APB ACCESS phase 有意义。

---

## 8.4 Unmapped Read

读取未映射或非法地址：

```text
PRDATA  = 32'b0
PSLVERR = 1
```

---

## 8.5 Unmapped Write

写入未映射或非法地址：

```text
PSLVERR = 1
```

且：

> 不允许修改任何 CSR 状态。

---

# 9. Reset 规范

复位：

```text
Active-low
Asynchronous
```

即：

```systemverilog
always_ff @(posedge PCLK or negedge PRESETn)
```

当：

```text
PRESETn == 0
```

时：

* RW 字段恢复指定 Reset value
* W1C 字段恢复指定 Reset value
* 内部 CSR 状态恢复指定 Reset value

RO 字段由外部硬件输入提供，不要求 CSRForge 对外部信号本身进行复位。

优先级：

```text
Reset
>
All Other Operations
```

---

# 10. RW Field 语义

RW = Read / Write。

软件写入 RW Field：

```systemverilog
rw_field <= PWDATA[msb:lsb];
```

软件读取：

```text
PRDATA[field_bits] = current rw_field value
```

硬件侧暴露当前值，例如：

```systemverilog
output logic       ctrl_en_o;
output logic [1:0] ctrl_mode_o;
```

外部 RTL 可直接使用这些信号。

RW hardware output 的位宽必须与对应 Field width 一致。

v0.1 不支持 hardware-side overwrite RW field。

---

# 11. RO Field 语义

RO = Read Only。

RO 字段值由外部硬件输入：

```systemverilog
input logic status_busy_i;
```

软件读：

```text
PRDATA[field_bits] = status_busy_i
```

软件写：

```text
ignored
```

不得改变 RO 值。

RO hardware input 的位宽必须与对应 Field width 一致。

v0.1 规定：

> 所有 RO hardware inputs 均假定已经与 `PCLK` 同步。

CSRForge v0.1 不负责：

* CDC synchronization
* pulse synchronization
* metastability handling

---

# 12. W1C Field 语义

W1C = Write One to Clear。

典型用途：

```text
Interrupt Status
Event Status
Error Status
```

---

## 12.1 Hardware Set Interface

每个 W1C field 生成 hardware set input。

hardware set input 的位宽必须与对应 Field width 一致。多 bit W1C field
使用逐 bit set mask；每个为 `1` 的 input bit 置位对应的 W1C state bit。

例如：

```systemverilog
input logic irq_status_done_set_i;
```

当：

```text
irq_status_done_set_i = 1
```

时，对应状态位被置位。

---

## 12.2 Software Clear

当软件对 W1C field 写入：

```text
1
```

对应 bit 清零。

写：

```text
0
```

保持原值。

---

## 12.3 W1C Next-State Equation

推荐统一实现：

```text
w1c_next =
    (w1c_current & ~software_clear_mask)
    | hardware_set
```

---

## 12.4 冲突优先级

v0.1 固定：

```text
Reset
>
Hardware Set
>
Software Clear
```

如果 hardware set 与 software clear 在同一周期发生：

```text
next_value = 1
```

新硬件事件不能因为软件清除旧事件而丢失。

---

# 13. Mixed-Access Register

v0.1 必须支持同一个 32-bit Register 中同时包含：

```text
RW
RO
W1C
Reserved
```

例如：

```text
MIXED @ 0x0C

bit 0    ENABLE     RW
bit 1    BUSY       RO
bit 2    DONE       W1C
31:3     Reserved
```

Mixed-access 的含义不只是各 Field “互不影响”。同一次合法 APB write
transaction 必须同时作用于目标 Register 内的所有 Field，而每个 Field
分别依据自己的 access semantic 响应该事务：

* RW Field 捕获对应的 `PWDATA` bits
* RO Field 忽略对应的 `PWDATA` bits
* W1C Field 仅清除对应 `PWDATA` bit 为 `1` 的状态位
* Reserved Bits 忽略写入

因此，各 Field 独立解释同一次写事务，但写事务在 Register 级别只完成一次。

禁止使用类似：

```systemverilog
register <= PWDATA;
```

的整寄存器覆盖式实现处理 mixed-access register。

---

# 14. Golden Design

Stage 1 手工实现一份 Golden CSR。

固定规格：

| Register   | Offset | Field | Bits | Access | Reset |
| ---------- | -----: | ----- | ---- | ------ | ----: |
| CTRL       |   0x00 | EN    | 0    | RW     |     0 |
| CTRL       |   0x00 | MODE  | 2:1  | RW     |     0 |
| STATUS     |   0x04 | BUSY  | 0    | RO     |     0 |
| IRQ_STATUS |   0x08 | DONE  | 0    | W1C    |     0 |
| MIXED      |   0x0C | ENABLE | 0    | RW     |     0 |
| MIXED      |   0x0C | BUSY   | 1    | RO     |     0 |
| MIXED      |   0x0C | DONE   | 2    | W1C    |     0 |

硬件侧接口：

```systemverilog
output logic       ctrl_en_o;
output logic [1:0] ctrl_mode_o;

input  logic       status_busy_i;

input  logic       irq_status_done_set_i;

output logic       mixed_enable_o;
input  logic       mixed_busy_i;
input  logic       mixed_done_set_i;
```

Golden RTL 必须人工编写。

不得由 Generator 自动生成。

Golden RTL 固定使用模块名 `csr_regs`。Golden RTL 与 Stage 3 Generated RTL
必须保持相同的 module name、端口名、端口宽度和外部可观察行为，使 Golden TB
可以在不修改 DUT 实例和期望值的情况下直接替换两者。

Golden RTL 应保持显式、简单、易于人工审核：

* 直接表达地址译码、Field 更新和读数据拼接
* 不为 Future Work 预建通用化框架
* 不使用会隐藏 RW / RO / W1C 行为的复杂宏、元编程或过度抽象
* 允许少量重复代码，以换取寄存器语义和优先级清晰可见

Golden module interface 固定为：

```systemverilog
module csr_regs (
    input  logic        PCLK,
    input  logic        PRESETn,

    input  logic        PSEL,
    input  logic        PENABLE,
    input  logic        PWRITE,
    input  logic [31:0] PADDR,
    input  logic [31:0] PWDATA,

    output logic [31:0] PRDATA,
    output logic        PREADY,
    output logic        PSLVERR,

    output logic        ctrl_en_o,
    output logic [1:0]  ctrl_mode_o,
    input  logic        status_busy_i,
    input  logic        irq_status_done_set_i,
    output logic        mixed_enable_o,
    input  logic        mixed_busy_i,
    input  logic        mixed_done_set_i
);
```

---

# 15. Golden Testbench

Golden TB 必须人工编写。

至少提供：

```systemverilog
task reset_dut;
task apb_write;
task apb_read;
task check_equal;
```

不使用 UVM。

---

## 15.1 必测场景

Golden TB 至少覆盖：

### Reset

* RW Reset value 正确
* W1C Reset value 正确
* Reserved bits 读 0

### RW

* 写 1
* 读回
* 再写 0
* 再读回
* 修改一个 RW Field 不破坏同 Register 其他 Field

### RO

* RO 能反映 hardware input
* 软件 write RO 无效

### W1C

* hardware set 可以置位
* software write 0 不清除
* software write 1 清除
* hardware set 与 software clear 同周期发生时，hardware set 获胜

### Reserved Bits

* 读取 Reserved bit 返回 0
* 写 Reserved bit 无效

### Mixed-Access Register

* 同一次 write transaction 中，RW Field 捕获对应 `PWDATA` bit
* 同一次 write transaction 中，RO Field 忽略对应 `PWDATA` bit
* 同一次 write transaction 中，W1C Field 按对应 `PWDATA` bit 执行 clear/hold
* 同一次 write transaction 中，Reserved Bits 忽略写入
* mixed-access write 后，各 Field 的结果同时符合各自 access semantic

### Error Access

* unmapped read：

  * `PSLVERR = 1`
  * `PRDATA = 0`

* unmapped write：

  * `PSLVERR = 1`
  * CSR 状态不改变

* misaligned read/write：

  * `PSLVERR = 1`
  * CSR 状态不改变

### APB Transaction

至少测试：

* 单次 read
* 单次 write
* back-to-back transaction

---

# 16. Generated RTL Verification

Stage 3：

```text
CSV
 ↓
IR
 ↓
Generated RTL
 +
Golden TB
 ↓
Icarus
```

Generated RTL 必须通过 Golden TB。

此阶段通过后，才允许进入 Generated TB 开发。

---

# 17. Generated Verification

Stage 4 根据 IR 自动构造基础 CSR 验证场景。

Generated Test 至少支持：

```text
Reset check
RW write/read check
RO write-ignore check
W1C set/hold/clear check
Unmapped address check
Misaligned address check
```

Verification Generator 可以读取同一个 Canonical IR，但不得调用 RTL Generator 的具体 access semantic implementation。

---

# 18. Simulator

## 18.1 Functional Simulation

默认：

```text
Icarus Verilog
```

推荐流程：

```bash
iverilog ...
vvp ...
```

测试成功示例：

```text
[PASS] RESET
[PASS] CTRL.EN RW
[PASS] CTRL.MODE RW
[PASS] STATUS.BUSY RO
[PASS] IRQ_STATUS.DONE W1C
[PASS] UNMAPPED ADDRESS
[PASS] MISALIGNED ADDRESS

ALL TESTS PASSED
```

失败必须返回非零退出码。

---

# 19. Verilator

开发过程中允许直接使用：

```bash
verilator --lint-only --Wall rtl/csr_regs.sv
```

用于发现：

* width mismatch
* truncation
* latch
* multiple driver
* incomplete assignment
* suspicious signed/unsigned behavior
* unused signal

Stage 1 对 Verilator 的硬要求为：

```text
0 error
```

warning 按功能相关性处理：

* 可能影响功能、位宽、时序意图或综合结果的 warning 必须修复
* 已确认无害且不影响 Stage 1 正确性的 warning 可以记录后继续开发
* 不要求为了消除无害 warning 延误 MVP
* 不允许通过全局关闭关键 warning 来掩盖真实设计问题

v0.1 后期再将 Verilator 正式集成到 CLI / CI。

---

# 20. C Header Generator

根据相同 IR 生成 C Header。

示例：

```c
#define CSR_CTRL_OFFSET          0x00000000
#define CSR_CTRL_EN_MASK         0x00000001
#define CSR_CTRL_MODE_MASK       0x00000006
#define CSR_CTRL_MODE_SHIFT      1

#define CSR_STATUS_OFFSET        0x00000004
#define CSR_STATUS_BUSY_MASK     0x00000001

#define CSR_IRQ_STATUS_OFFSET    0x00000008
#define CSR_IRQ_STATUS_DONE_MASK 0x00000001
```

v0.1 不处理 SoC absolute base address。

---

# 21. Markdown Generator

根据 IR 生成寄存器文档。

示例：

```text
## CTRL — 0x00

| Field | Bits | Access | Reset |
| ----- | ---- | ------ | ----- |
| EN    | 0    | RW     | 0     |
| MODE  | 2:1  | RW     | 0     |
```

生成内容必须与 RTL 使用同一 Canonical IR。

---

# 22. CLI

v0.1 最终期望提供：

```bash
csrforge check demo.csv
csrforge generate demo.csv -o build/
csrforge verify demo.csv
```

可选：

```bash
csrforge dump-ir demo.csv
```

CLI 不属于前期开发重点。

Stage 1～4 可以先直接使用 Python script。

---

# 23. 生成可复现性

对于相同输入：

```text
Input Spec
+
CSRForge Version
```

生成物应保持确定性。

v0.1 不应在 Generated RTL / Header / Markdown 中加入会导致 diff 每次变化的动态时间戳。

---

# 24. 推荐仓库结构

```text
CSRForge/
│
├── SPEC.md
├── README.md
│
├── csrforge/
│   ├── model.py
│   ├── parser_csv.py
│   ├── checker.py
│   ├── generator_rtl.py
│   ├── generator_test.py
│   ├── generator_header.py
│   └── generator_doc.py
│
├── templates/
│
├── verification/
│   ├── golden/
│   │   ├── golden_csr.sv
│   │   └── golden_csr_tb.sv
│   └── generated/
│
├── examples/
│   ├── basic.csv
│   ├── mixed_access.csv
│   ├── interrupt.csv
│   └── cache_csr.csv
│
├── tests/
│
└── build/
```

仓库结构可根据实际实现调整，但不得因此扩大项目功能范围。

---

# 25. v0.1 验收标准

## Stage 1 — Golden Design

* [x] Golden CSR RTL 可被 Icarus 编译
* [x] Golden TB 可运行
* [x] Reset PASS
* [x] RW PASS
* [x] RO PASS
* [x] W1C PASS
* [x] W1C HW/SW conflict PASS
* [x] Mixed-access single-write semantics PASS
* [x] Reserved bits PASS
* [x] Unmapped address PASS
* [x] Misaligned address PASS
* [x] Back-to-back APB PASS
* [x] Verilator 0 error
* [x] 功能相关 warning 已修复；确认无害的 warning 已记录

Stage 1 于 2026-08-27 完成：Icarus 运行 55 项检查全部 PASS，Verilator
报告 0 error。保留一个 `UNUSEDSIGNAL` warning：`PWDATA[31:3]` 只对应
明确规定为 Write Ignore 的 Reserved Bits，不影响功能正确性。

---

## Stage 2 — Parser / IR / Checker

* [x] CSV 可解析
* [x] Register / Field 正确映射到 dataclass IR
* [x] IR 可序列化为 JSON
* [x] Misaligned offset 可检测
* [x] Duplicate register address 可检测
* [x] Register-offset inconsistency 可检测
* [x] Field overlap 可检测
* [x] Invalid bit range 可检测
* [x] Reset overflow 可检测
* [x] Unsupported access type 可检测

Stage 2 于 2026-08-27 完成：Parser / IR / Checker 共 23 项 Python
测试全部 PASS；完整回归同时保持 Golden HDL 55 项检查 PASS、Verilator
0 error。Checker 不修改输入 IR，并在一次 validation pass 中汇总所有问题。

---

## Stage 3 — RTL Generator

* [x] IR 可生成 SystemVerilog
* [x] Generated RTL 可被 Icarus 编译
* [x] Generated RTL 可通过 Golden TB
* [x] Generated RTL 可通过 Verilator lint

Stage 3 于 2026-08-27 完成：Golden CSV 经 Parser、Checker 和 RTL Generator
产生确定性 SystemVerilog；Generated RTL 通过独立 Golden TB 的 55 项检查，
并通过 Verilator lint（0 error）。Generator 单元测试覆盖接口契约、逐 Field
读路径、W1C bitwise priority、Reserved Bits 和生成可复现性。

达到此阶段：

> CSRForge 已完成最核心技术目标。

---

## Stage 4 — Generated Verification

* [x] 根据 IR 自动产生验证场景
* [x] Generated TB 可编译
* [x] Generated RTL + Generated TB PASS
* [x] 故意破坏 RW RTL 时测试能够 FAIL
* [x] 故意破坏 W1C RTL 时测试能够 FAIL
* [x] 故意交换 HW Set / SW Clear 优先级时测试能够 FAIL

Stage 4 于 2026-08-27 完成：Generated TB 对 Golden CSV 自动构造 37 项
自检场景并全部 PASS。Verification Generator 不导入或调用 RTL Generator。
三种定向 mutation（RW stuck-at-zero、W1C clear removed、software clear
错误优先于 hardware set）均被 Generated TB 检出并返回非零退出码。

---

## Stage 5 — Tool Output

* [x] C Header 可生成
* [x] Markdown 可生成
* [x] CLI 可运行
* [x] README 包含 Quick Start
* [x] 至少三个 Example

Stage 5 于 2026-08-27 完成：CLI 的 `check`、`dump-ir`、`generate` 和
`verify` 均可运行；每份 spec 可确定性生成 RTL、Self-checking TB、C Header、
Markdown 和 JSON。`basic`、`mixed_access`、`interrupt` 三个公开示例均通过
Icarus 端到端验证。

---

## Stage 6 — Engineering

* [x] Verilator lint 集成
* [x] GitHub Actions 执行 Parser Test
* [x] GitHub Actions 执行 RTL Simulation
* [x] GitHub Actions 执行 Verilator lint

Stage 6 的本地工程化配置于 2026-08-27 完成：`Makefile` 已将 Golden RTL
与 Generated RTL 的 Verilator lint 纳入完整回归，`.github/workflows/ci.yml`
已配置 Python 测试、Golden 仿真、生成链路、mutation test 与公开 examples。
上述三项 GitHub Actions 验收项须在仓库推送后由 GitHub-hosted runner 实际
运行成功才能勾选，不以本地配置文件代替远端执行结果。

Stage 6 于 2026-08-27 完成：GitHub Actions 首次远端完整回归为绿色，Parser /
IR / Checker / Generator 测试、Golden 与 Generated RTL 仿真、Verilator lint、
mutation test 及三个公开 examples 均通过。CSRForge v0.1 至此达到完成定义。

---

# 26. v0.1 完成定义

CSRForge v0.1 的最低完整版本定义为：

```text
CSV Spec
   ↓
Semantic Check
   ↓
Canonical IR
   ↓
APB3 CSR RTL
   ↓
Self-checking Verification
   ↓
Icarus PASS / FAIL
```

并支持：

```text
RW
RO
W1C
32-bit APB3
C Header
Markdown
```

达到此标准后：

> 项目视为完成。

不得因为 Roadmap 功能尚未实现而延迟发布 v0.1。

---

# 27. Future Work

以下内容仅作为未来扩展方向：

* Excel input
* W1S
* RC
* WO
* W0C
* APB `PSTRB`
* APB wait state
* AXI4-Lite
* AHB-Lite
* UVM RAL
* Functional Coverage
* Verilator simulation backend
* Vivado XSIM backend
* JSON verification report
* Cache CSR integration
* Automatic generated-file freshness check
* AI-assisted failure analysis

以上内容不属于当前 v0.1 验收范围。

---

# 28. AI Coding Agent 开发约束

Codex 可以辅助：

* 解释 APB3 / CSR 相关知识
* 实现 Python boilerplate
* 编写或修改 RTL
* 编写测试
* 调用 Icarus
* 调用 Verilator
* 解析错误
* 重构代码
* 完善文档

但必须遵守：

1. 不得未经确认扩大 v0.1 scope。
2. 不得在 Stage 1 完成前开发 generator。
3. 每个阶段完成后必须实际运行对应测试。
4. 修改 RTL 时必须说明修改原因。
5. Generated RTL 与 Generated Test 的访问语义实现必须保持独立。
6. 不得为了让测试通过而同时静默修改 DUT 和期望值。
7. 遇到规格未定义行为时，应首先询问，不得自行假设。
8. 优先实现最简单、确定、可验证的方案。
9. 不为 Future Work 提前建立复杂抽象。
10. 项目目标是完成一个可靠的 v0.1，而不是构建通用 EDA Framework。

---

# 29. 第一阶段立即执行任务

在开始任何 Python Generator 开发前，只完成以下任务：

```text
1. 阅读并理解本 SPEC
2. 学习 APB3 SETUP / ACCESS 基本时序
3. 手写 Golden CSR RTL
4. 手写 Golden SystemVerilog TB
5. 使用 Icarus 完成仿真
6. 使用 Verilator 执行 lint
7. 所有 Golden 测试 PASS
```

只有在 Stage 1 验收全部通过后，才能进入：

```text
CSV Parser
+
Canonical IR
+
Semantic Checker
```

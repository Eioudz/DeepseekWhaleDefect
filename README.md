# 蓝色大肥鱼替换故障机器人 · 工程脚本

《杀戮尖塔 2》Mod **DeepseekWhaleDefect**（Steam 创意工坊 ID `3810578000`）的**素材处理与打包脚本**仓库。

把游戏中的「故障机器人」整体替换为一只蓝色大肥鱼（Q 版女仆造型），包含战斗/商店/篝火立绘、HUD 头像、卡牌插图与遗物图标。

> 本仓库只放**自制脚本、Mod 元数据和成品 pck**。游戏本体资源与第三方二进制一律不入库，见下方「不包含的内容」。

---

## 不包含的内容

以下内容从《杀戮尖塔 2》游戏本体提取或反编译得到，**版权归 Mega Crit 所有，不随本仓库分发**（已写入 `.gitignore`）：

| 目录 / 文件 | 说明 |
|---|---|
| `_allcs/` `_decomp/` | 反编译的游戏 C# 代码，用于查清 Mod 加载与动画切换逻辑 |
| `base_zhs/` | 游戏本地化文本 |
| `investigate/` | 游戏原始 `.spskel` / `.ctex` / atlas 导出 |
| `_ref_*.cpp` | 引擎运行时参考源码 |
| `orig_from_zip.pck` 等 | 与游戏原版同源的 pck |
| `mod_uploader/` | 第三方上传工具（内含 Valve `steam_api64.dll`，不可再分发） |

同理，仓库里也**不含**任何从游戏提取的中间产物（原始 ctex、atlas 文本、临时骨架 dump）与体积较大的预览截图——它们都能由脚本重新生成。

运行本仓库的脚本需要你**自备正版游戏**，脚本会从游戏的 `SlayTheSpire2.pck` 中读取所需的头部模板。

---

## 目录结构

```
.
├── pcktool.py                   # Godot PCK v3 读写（打包器）
├── make_skel.py                 # 生成 31 骨骼人物骨架（头/身/四肢/发/尾独立）
├── parse_skel.py / parse_skel2.py
├── add_attack_head.py           # 各姿态头部贴图
├── add_expression_head.py
├── replace_low_head.py          # 残血表情贴图
├── reuse_head_for_process.py
├── extract_base_zhs.py          # 导出游戏本地化（用于改角色名等文本）
├── fix_loc_pck.py
├── make_preview.py
├── DeepseekWhaleDefect.json     # Mod 清单
├── whale_workspace/             # 上传工作区
│   ├── mod_id.txt               # 创意工坊 ID
│   ├── workshop.json            # 标题/简介/更新说明（title、description 为 null 表示不改线上）
│   ├── image.png                # 工坊封面
│   └── content/                 # 成品 json + pck
└── defendskin_work/             # 素材处理脚本（主要工作区）
    ├── build_whale.py           # 主构建流程
    ├── add_card_to_whale.py     # 卡牌插图替换（通用多卡版）
    ├── add_cookie_relic.py      # 遗物图标替换（美味饼干）
    ├── cut_cookie.py            # 遗物图抠图 + 白色剪影描边
    ├── rest_pose.py / restsite_defect_rice.skel
    ├── install_*.py             # 安装到游戏 mods 目录 + 校验
    └── ...
```

---

## 工具链要点

**PCK v3**
- 索引偏移写在 `0x20`（u64），必须写绝对偏移；写 0 会让 Godot 从文件头解析索引而卡死。
- 条目格式：`[len u32][name][off u64][size u64][md5 16B][flags u32]`，数据 16 字节对齐。

**ctex（GST2 头，共 56 字节）**
- `0x08/0x0c` = 宽 / 高　`0x24` = 数据格式（2 = WebP）　`0x28` = u16 宽 + u16 高
- `0x30` = `Image::Format`（4 = RGB8，5 = RGBA8）　`0x34` = WebP 长度　`0x38` 起为 WebP

**贴图处理**
- 卡图/立绘一律**等比放大 + 居中裁剪**（cover）铺满画布，绝不拉伸变形。
- 头部贴图先按 alpha 裁到内容边界再等比缩放，保证受击/施法/攻击各姿态对齐。
- 抠图用 alpha 阈值 + 最大连通域重建轮廓 + 填洞，再做 **alpha-bleed**（边缘色向透明区渗出）避免缩放采样出白圈。
- 注意：`PIL.Image.paste(..., mask)` 会造成 alpha 侵蚀（α → α²/255），目标区域已清空时应直接 paste。

**重挂前缀**
替换第三方皮肤 Mod 的资源时，把 `DefectSkin/` 整体改为 `DeepseekWhaleDefect/`，并同步替换 blob 内的 `res://` 路径，避免两个 Mod 冲突。打包后逐字节校验未被改动的条目，防止损坏。

---

## 使用

1. 安装 Python 3 + Pillow。
2. 确认游戏安装路径（脚本内 `BASE_PCK` 常量）。
3. 按需运行 `defendskin_work/` 下的脚本，产物默认输出为 `DeepseekWhaleDefect.pck.new`，再用 `install_*.py` 安装到游戏的 `mods/` 目录。
4. 重启游戏生效。

上传创意工坊使用 `ModUploader.exe`（需自备，见 Steamworks 文档）。

---

## 版权

Mod 的美术与脚本为本项目作者所有。游戏本体相关素材版权归 Mega Crit, Inc. 所有，本仓库不再分发。
"""Canonical, documented BDA Rosetta parameter surface. Build generated files with build.py."""

MODES = {
    "score_jd2": "单点评分：对输入结构评分，不进行 Relax，不等于界面结合能。",
    "relax": "FastRelax：侧链重排与局部最小化；不是纳秒分子动力学。",
    "InterfaceAnalyzer": "蛋白–蛋白界面分析：已有复合物的界面能、埋藏面积和氢键等。",
    "relax_interface": "先用 relax 优化并保存坐标，再对每个优化后的复合物运行 InterfaceAnalyzer。",
    "docking_protocol": "RosettaDock：蛋白–蛋白刚体/侧链采样；需要已有组装与明确伙伴链。",
    "cartesian_ddg": "Cartesian ΔΔG：匹配 WT/突变体的折叠稳定性分数差；不是结合 ΔΔG。",
    "rosetta_scripts": "使用上传的 XML 协议；XML 的 mover/filter 参数与输出由该协议定义。",
}
SCORE = "https://docs.rosettacommons.org/docs/latest/application_documentation/analysis/score-commands"
RELAX = "https://docs.rosettacommons.org/docs/latest/application_documentation/structure_prediction/relax"
IA = "https://docs.rosettacommons.org/docs/latest/application_documentation/analysis/interface-analyzer"
DOCK = "https://docs.rosettacommons.org/docs/latest/application_documentation/docking/docking-protocol"
DDG = "https://docs.rosettacommons.org/docs/latest/cartesian-ddG"
XML = "https://docs.rosettacommons.org/docs/latest/scripting_documentation/RosettaScripts/RosettaScripts"
OPTIONS = "https://docs.rosettacommons.org/docs/latest/full-options-list"
PROPERTIES = {}


def option(
    key,
    kind,
    default,
    title,
    description,
    flag="",
    modes=None,
    unit="无量纲",
    source=OPTIONS,
    **kw,
):
    row = {
        "type": kind,
        "default": default,
        "title": title,
        "description": description,
        "x-bda-unit": unit,
        "x-bda-flag": flag or "BDA 控制参数，不直接作为 Rosetta flag",
        "x-bda-source": source,
        **kw,
    }
    if modes:
        row["x-bda-modes"] = modes
    PROPERTIES[key] = row


option(
    "application",
    "string",
    "score_jd2",
    "功能模式",
    "选择计算阶段；不同模式的分数不能混作同一种结合自由能。",
    enum=list(MODES),
)
option(
    "nstruct",
    "integer",
    1,
    "每输入生成数",
    "每个输入、每个独立重复生成的 decoy 数；cartesian_ddg 使用 ddg_iterations，不使用本参数。",
    "-nstruct",
    modes=[m for m in MODES if m != "cartesian_ddg"],
    minimum=1,
    maximum=10000,
    unit="个",
)
option(
    "replicates",
    "integer",
    1,
    "独立重复数",
    "分别启动进程并使用不同随机种子；各重复保留原始结果，不只保存最优值。",
    minimum=1,
    maximum=100,
    unit="次",
)
option(
    "seed",
    "integer",
    111111,
    "起始随机种子",
    "启用 constant_seed；每个输入/重复的种子递增。固定种子利于复现，不证明采样收敛。",
    "-run:constant_seed / -run:jran",
    minimum=1,
    maximum=2000000000,
)
option(
    "score_weights",
    "string",
    "ref2015",
    "评分函数",
    "所有比较对象使用同一权重。Cartesian 模式必须选择 *_cart；REU 不能直接当 kcal/mol。",
    "-score:weights",
    enum=["ref2015", "ref2015_cart", "beta_nov16", "beta_nov16_cart"],
    source=RELAX,
    unit="Rosetta 权重集",
)
option(
    "out_scorefile",
    "string",
    "score.sc",
    "评分文件名",
    "各输入/重复独立目录内的 .sc 文件名；不接受目录或路径穿越。",
    "-out:file:scorefile",
    pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*\.sc$",
)
option(
    "ex1",
    "boolean",
    False,
    "额外 χ1 旋转异构体",
    "扩大侧链 χ1 rotamer 采样；增加打包计算量，不是独立结构重复。",
    "-ex1",
)
option(
    "ex2",
    "boolean",
    False,
    "额外 χ2 旋转异构体",
    "扩大侧链 χ2 rotamer 采样；仅在协议实际执行 packing 时影响采样。",
    "-ex2",
)
option(
    "use_input_sc",
    "boolean",
    True,
    "保留输入侧链候选",
    "将输入侧链构象纳入 packing rotamer 候选集合。",
    "-use_input_sc",
)
option(
    "ignore_unrecognized_res",
    "boolean",
    False,
    "忽略无法识别的残基",
    "默认关闭。开启可能删除糖基、配体或特殊残基，改变体系；须检查运行日志和保存结构。",
    "-ignore_unrecognized_res",
)
option(
    "extra_res_fa",
    "string",
    "",
    "全原子残基参数文件",
    "aux 端口下的 .params 相对文件名；为非标准残基提供全原子参数，不自动生成小分子参数。",
    "-in:file:extra_res_fa",
    unit="文件",
)
option(
    "extra_res_cen",
    "string",
    "",
    "Centroid 残基参数文件",
    "aux 端口下的 .params 文件；对接低分辨率阶段使用非标准残基时需匹配 centroid 参数。",
    "-in:file:extra_res_cen",
    modes=["docking_protocol", "rosetta_scripts"],
    unit="文件",
)
option(
    "constraints_file",
    "string",
    "",
    "约束文件",
    "aux 端口下的 Rosetta .cst 文件；其中残基编号须对应输入 pose。约束能改变评分，不能与无约束能量混排。",
    "-constraints:cst_fa_file",
    modes=[
        "score_jd2",
        "relax",
        "relax_interface",
        "docking_protocol",
        "rosetta_scripts",
    ],
    unit="文件",
)
option(
    "constraint_weight",
    "number",
    1.0,
    "文件约束权重",
    "仅在提供 constraints_file 时传入；不等同于 Relax 自动坐标约束权重。",
    "-constraints:cst_fa_weight",
    modes=[
        "score_jd2",
        "relax",
        "relax_interface",
        "docking_protocol",
        "rosetta_scripts",
    ],
    minimum=0,
    maximum=1000,
    unit="权重",
)
for key, default, title, desc, flag in [
    (
        "pack_input",
        False,
        "先重排输入界面",
        "分析前是否对输入界面进行侧链 packing；这是评分内部分支，不会覆盖保存的 Relax 坐标。",
        "-pack_input",
    ),
    (
        "pack_separated",
        True,
        "分离后重排界面",
        "计算 dG_separated 时，是否重排分離伙伴暴露界面的侧链。与 pack_input 分开控制。",
        "-pack_separated",
    ),
    (
        "compute_packstat",
        False,
        "计算界面堆积统计",
        "启用有随机成分的 packstat；大界面可能较慢。",
        "-compute_packstat",
    ),
]:
    option(
        key,
        "boolean",
        default,
        title,
        desc,
        flag,
        modes=["InterfaceAnalyzer", "relax_interface"],
        source=IA,
    )
option(
    "interface",
    "string",
    "",
    "界面链分组",
    "必填，例如 AB_C 表示受体 A/B 与蛋白 C；天然双链配体可为 AB_CD。使用输入文件实际链标识，不能混淆 mmCIF label/auth ID。",
    "-interface",
    modes=["InterfaceAnalyzer", "relax_interface"],
    source=IA,
    pattern=r"^$|^[A-Za-z0-9]+_[A-Za-z0-9]+$",
)
option(
    "packstat_oversample",
    "integer",
    100,
    "Packstat 过采样",
    "仅 compute_packstat=true 时生效；增加采样以降低随机波动。",
    "-packstat:oversample",
    modes=["InterfaceAnalyzer", "relax_interface"],
    minimum=1,
    maximum=1000,
    source=IA,
    unit="倍",
)
option(
    "relax_repeats",
    "integer",
    5,
    "Relax 内部循环",
    "一个 FastRelax 轨迹内的打包/最小化循环；不同于 nstruct 和独立重复。",
    "-relax:default_repeats",
    modes=["relax", "relax_interface"],
    minimum=1,
    maximum=50,
    source=RELAX,
    unit="次",
)
option(
    "relax_cartesian",
    "boolean",
    False,
    "Cartesian Relax",
    "使用笛卡尔坐标最小化；必须选 ref2015_cart 或 beta_nov16_cart。",
    "-relax:cartesian",
    modes=["relax", "relax_interface"],
    source=RELAX,
)
option(
    "constrain_start",
    "boolean",
    True,
    "约束到输入坐标",
    "由 relax 可执行文件建立起始坐标约束，减少大幅漂移；不作为 XML FastRelax 的通用开关。",
    "-relax:constrain_relax_to_start_coords",
    modes=["relax", "relax_interface"],
    source=RELAX,
)
option(
    "ramp_constraints",
    "boolean",
    False,
    "渐弱坐标约束",
    "配合 constrain_start。false 显式传给 Rosetta，在优化中保留约束；true 渐弱。",
    "-relax:ramp_constraints",
    modes=["relax", "relax_interface"],
    source=RELAX,
)
option(
    "movemap_file",
    "string",
    "",
    "Relax 自由度文件",
    "aux 端口下的 MoveMap 文件，控制骨架/侧链/jump 可动性。默认未提供时沿用该 relax 构建的自由度；不是受体自动固定。",
    "-in:file:movemap",
    modes=["relax", "relax_interface"],
    unit="文件",
    source=RELAX,
)
option(
    "relax_script",
    "string",
    "",
    "自定义 Relax 循环脚本",
    "aux 端口下的 Relax script；覆盖内部优化流程，需与 repeats/约束策略一起审阅。",
    "-relax:script",
    modes=["relax", "relax_interface"],
    unit="文件",
    source=RELAX,
)
option(
    "dock_partners",
    "string",
    "",
    "对接伙伴链",
    "必填，例如 AB_C。对接分组与界面分析分组语法类似，但这是 docking:partners。",
    "-docking:partners",
    modes=["docking_protocol"],
    pattern=r"^$|^[A-Za-z0-9]+_[A-Za-z0-9]+$",
    source=DOCK,
)
option(
    "dock_search",
    "string",
    "local",
    "对接搜索范围",
    "local 从现有姿态附近扰动；global 随机化两个伙伴取向，须充分采样；都不是物理 MD。",
    modes=["docking_protocol"],
    enum=["local", "global"],
    source=DOCK,
)
option(
    "dock_translation",
    "number",
    3.0,
    "初始平移扰动",
    "local 模式 dock_pert 的平移幅度；不能据此推导结合距离或动力学。",
    "-docking:dock_pert [translation rotation]",
    modes=["docking_protocol"],
    minimum=0,
    maximum=100,
    unit="Å",
    source=DOCK,
)
option(
    "dock_rotation",
    "number",
    8.0,
    "初始旋转扰动",
    "local 模式 dock_pert 的旋转幅度。",
    "-docking:dock_pert [translation rotation]",
    modes=["docking_protocol"],
    minimum=0,
    maximum=180,
    unit="度",
    source=DOCK,
)
option(
    "dock_local_refine",
    "boolean",
    False,
    "仅高分辨率对接精修",
    "跳过低分辨率搜索，用于已有可信近邻姿态；不能与 global 搜索组合。",
    "-docking:docking_local_refine",
    modes=["docking_protocol"],
    source=DOCK,
)
option(
    "native_file",
    "string",
    "",
    "参考复合物",
    "aux 中用于对接 RMSD 的参考结构，不自动作为位置约束；必须具有匹配的链/残基映射。",
    "-in:file:native",
    modes=["docking_protocol"],
    unit="文件",
    source=DOCK,
)
option(
    "ddg_mut_file",
    "string",
    "",
    "突变定义文件",
    "cartesian_ddg 必填的 aux mut_file。使用 Rosetta pose 编号；需要 WT 与突变定义校验，不能用 PDB 编号直接替代。",
    "-ddg:mut_file",
    modes=["cartesian_ddg"],
    unit="文件",
    source=DDG,
)
option(
    "ddg_iterations",
    "integer",
    3,
    "WT/突变采样迭代",
    "每个突变定义的采样次数，不是 nstruct；输出的是协议相关折叠稳定性差分。",
    "-ddg:iterations",
    modes=["cartesian_ddg"],
    minimum=1,
    maximum=100,
    unit="次",
    source=DDG,
)
option(
    "ddg_cartesian",
    "boolean",
    True,
    "DDG Cartesian 优化",
    "本插件只支持 Cartesian 协议，必须保持 true。",
    "-ddg:cartesian",
    modes=["cartesian_ddg"],
    enum=[True],
    source=DDG,
)
option(
    "ddg_bb_neighbors",
    "integer",
    1,
    "骨架邻居范围",
    "围绕突变位置允许处理的序列邻居范围；不是空间半径。",
    "-ddg:bbnbrs",
    modes=["cartesian_ddg"],
    minimum=0,
    maximum=10,
    unit="残基数",
    source=DDG,
)
option(
    "ddg_dump_pdbs",
    "boolean",
    True,
    "保存 DDG 结构",
    "保存 WT/突变模型供原子级核查；关闭则仅保存原始分数与日志。",
    "-ddg:dump_pdbs",
    modes=["cartesian_ddg"],
    source=DDG,
)
option(
    "fa_max_dis",
    "number",
    9.0,
    "全原子作用距离截断",
    "Cartesian DDG 推荐协议的相互作用截断；须与 WT 预先 Cartesian Relax 的设置一致。",
    "-fa_max_dis",
    modes=["relax", "relax_interface", "InterfaceAnalyzer", "cartesian_ddg"],
    minimum=3,
    maximum=20,
    unit="Å",
    source=DDG,
)
option(
    "parser_protocol",
    "string",
    "",
    "RosettaScripts XML",
    "rosetta_scripts 必填，aux 下的 XML 文件。平台不会猜测 XML 的科学阶段；生成时验证 XML 可解析，完整 schema 由实际 Rosetta 构建验证。",
    "-parser:protocol",
    modes=["rosetta_scripts"],
    unit="文件",
    source=XML,
)
option(
    "parser_script_vars",
    "string",
    "",
    "XML 变量",
    "空白分隔的 name=value；作为独立 argv 值传入，不运行 shell。所有变量名必须在 XML 的 %%name%% 中出现，所有占位符必须有值。",
    "-parser:script_vars",
    modes=["rosetta_scripts"],
    source=XML,
)
option(
    "xml_expected_output",
    "string",
    "score",
    "XML 最低输出契约",
    "score 要求至少 nstruct 个有效 SCORE 行；structure 还要求对应数量 PDB。自定义协议的完整科学输出仍由协议作者解释。",
    modes=["rosetta_scripts"],
    enum=["score", "structure"],
    source=XML,
)
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": PROPERTIES,
    "description": "BDA Rosetta 显式参数表；默认值是本插件默认，非所有 Rosetta 构建的默认。",
    "allOf": [
        {
            "if": {
                "properties": {
                    "application": {"enum": ["InterfaceAnalyzer", "relax_interface"]}
                },
                "required": ["application"],
            },
            "then": {
                "required": ["interface"],
                "properties": {"interface": {"minLength": 3}},
            },
        },
        {
            "if": {
                "properties": {"application": {"const": "cartesian_ddg"}},
                "required": ["application"],
            },
            "then": {
                "required": ["ddg_mut_file", "score_weights"],
                "properties": {
                    "ddg_mut_file": {"minLength": 1},
                    "score_weights": {"enum": ["ref2015_cart", "beta_nov16_cart"]},
                },
            },
        },
        {
            "if": {
                "properties": {"application": {"const": "docking_protocol"}},
                "required": ["application"],
            },
            "then": {
                "required": ["dock_partners"],
                "properties": {"dock_partners": {"minLength": 3}},
            },
        },
        {
            "if": {
                "properties": {"application": {"const": "rosetta_scripts"}},
                "required": ["application"],
            },
            "then": {
                "required": ["parser_protocol"],
                "properties": {"parser_protocol": {"minLength": 1}},
            },
        },
    ],
}
SPEC = {
    "schema_version": 1,
    "plugin_version": "2024.09-bda.1",
    "modes": MODES,
    "schema": SCHEMA,
}

# Geometry is a selectable post-processing stage of the two interface modes.
_GEOMETRY_MODES = ["InterfaceAnalyzer", "relax_interface"]
option(
    "geometry_contacts",
    "boolean",
    True,
    "计算界面原子距离",
    "从同一被评分的复合物坐标提取重原子接触和逐残基对最短距离；内部 packing 的临时姿态不在此几何文件中。",
    modes=_GEOMETRY_MODES,
)
option(
    "contact_cutoff",
    "number",
    4.5,
    "接触距离阈值",
    "输出此半径内的全部跨界面重原子对及其距离；没有接触不等于证明不结合。",
    modes=_GEOMETRY_MODES,
    minimum=2,
    maximum=10,
    unit="Å",
)
option(
    "receptor_axis",
    "string",
    "",
    "受体角度锚点",
    "可选，两枚 CA 的 chain:residue 标识，逗号分隔，如 A:10,A:100；方向从第一个指向第二个。须与 binder_axis 一起提供。",
    modes=_GEOMETRY_MODES,
    unit="PDB链:残基编号",
)
option(
    "binder_axis",
    "string",
    "",
    "配体蛋白角度锚点",
    "可选，两枚 CA 标识，如 C:1,C:50。报告此有向轴与受体轴的夹角；不是未经定义的“整体结合角”。",
    modes=_GEOMETRY_MODES,
    unit="PDB链:残基编号",
)
option(
    "geometry_reference_file",
    "string",
    "",
    "天然参考复合物",
    "可选，aux 下同链分组的参考 PDB；计算其接触、质心距离与相同锚点定义夹角供比较。参考应记录是实验复合物还是对接假说；不同支架的接触编号不能直接当同源位点。",
    modes=_GEOMETRY_MODES,
    unit="文件",
)

for _name in ["geometry_contacts", "contact_cutoff", "geometry_reference_file"]:
    PROPERTIES[_name]["x-bda-source"] = (
        "https://docs.python.org/3/library/math.html#math.dist"
    )
for _name in ["receptor_axis", "binder_axis"]:
    PROPERTIES[_name]["x-bda-source"] = (
        "https://docs.python.org/3/library/math.html#math.acos"
    )

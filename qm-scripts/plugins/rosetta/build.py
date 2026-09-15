"""Generate the native BDA manifest and complete parameter guide from spec.py + runner.py."""

from pathlib import Path
import argparse
import ast
import hashlib
import importlib.util
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def build():
    loader = importlib.util.spec_from_file_location("rosetta_spec", HERE / "spec.py")
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    spec = module.SPEC
    schema = spec["schema"]
    source = (HERE / "runner.py").read_text()
    spec_node = next(
        node for node in ast.parse(source).body if isinstance(node, ast.If)
    )
    source_lines = source.splitlines(keepends=True)
    injected = (
        "".join(source_lines[: spec_node.lineno - 1])
        + "SPEC = json.loads("
        + repr(json.dumps(spec, ensure_ascii=False))
        + ")\n"
        + "".join(source_lines[spec_node.end_lineno :])
    )
    assert injected != source
    command = (
        "python3 - run <<'BDA_ROSETTA_PLUGIN'\n" + injected + "\nBDA_ROSETTA_PLUGIN"
    )
    manifest = {
        "schema_version": "1.0",
        "manifest_id": "org.bda.rosetta",
        "plugin_key": "Rosetta",
        "plugin_version": spec["plugin_version"],
        "display_name": "Rosetta · 多模式参数工作台",
        "command_template": command,
        "parameter_schema": schema,
        "output_schema": {
            "type": "object",
            "description": "Raw score/structure/log/config artifacts. No inferred Kd. Scientific validation remains separate.",
        },
        "inputs": [
            {
                "name": "s",
                "kind": "protein_structure",
                "accepts": [
                    "backbone_set",
                    "candidate_structure",
                    "complex_structure",
                    "relaxed_structure",
                    "target_structure",
                ],
                "required": True,
                "multiple": True,
            },
            {
                "name": "aux",
                "kind": "params",
                "required": False,
                "multiple": True,
                "description": "XML, mut_file, native PDB, constraints, MoveMap or residue params; paths are relative to this port.",
            },
        ],
        "outputs": [
            {
                "name": "structures",
                "kind": "protein_structure",
                "artifact_type": "candidate_structure",
                "filename_glob": "runs/**/*.pdb",
            },
            {
                "name": "score_table",
                "kind": "tabular",
                "artifact_type": "score_table",
                "filename_glob": "*.csv",
            },
            {
                "name": "raw_score_table",
                "kind": "tabular",
                "artifact_type": "score_table",
                "filename_glob": "runs/**/*.sc",
            },
            {
                "name": "raw_ddg",
                "kind": "opaque",
                "artifact_type": "data",
                "filename_glob": "runs/**/*.ddg",
            },
            {
                "name": "run_evidence",
                "kind": "opaque",
                "artifact_type": "data",
                "filename_glob": "*.json",
            },
            {
                "name": "parameter_guide",
                "kind": "opaque",
                "artifact_type": "data",
                "filename_glob": "parameter-explanations.md",
            },
            {
                "name": "run_logs",
                "kind": "opaque",
                "artifact_type": "data",
                "filename_glob": "runs/**/*.log",
            },
            {
                "name": "command_preview",
                "kind": "opaque",
                "artifact_type": "data",
                "filename_glob": "commands.sh",
            },
        ],
        "resources": {"cpus": 1, "gpu": False, "memory_gb": 4, "walltime_minutes": 240},
        "runtime": {
            "mode": "module",
            "reference": "site://rosetta/2024.09",
            "image_digest": None,
            "setup": [],
        },
        "output_parser": None,
        "input_adapter": None,
    }
    canonical = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    manifest["checksum_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    lines = [
        "# BDA Rosetta：全部可生成参数",
        "",
        "本表由 `qm-scripts/plugins/rosetta/spec.py` 自动生成。覆盖本插件显式开放的全部参数，默认值为 BDA 插件默认，不是所有 Rosetta 版本的默认。",
        "",
        f"版本：`{spec['plugin_version']}`；模式：{len(spec['modes'])}；参数：{len(schema['properties'])}。",
        "",
        "自定义 XML 的 mover/filter 属性由上传协议决定，不能预先声称覆盖 Rosetta 所有模块。插件会额外导出该 XML 的实际属性与变量清单；它们的语义需匹配实际 Rosetta 构建的 XSD。",
        "",
        "## 模式",
        "",
    ]
    for name, desc in spec["modes"].items():
        lines.append(f"- `{name}`：{desc}")
    lines += ["", "## 参数", ""]
    for k, s in schema["properties"].items():
        lines += [
            f"### {k} — {s['title']}",
            "",
            "- 类型：`"
            + s["type"]
            + "`；默认：`"
            + json.dumps(s["default"], ensure_ascii=False)
            + "`。",
            "- 单位："
            + s["x-bda-unit"]
            + "；适用模式："
            + ", ".join(s.get("x-bda-modes", list(spec["modes"])))
            + "。",
            "- 生成映射：`" + s["x-bda-flag"] + "`。",
        ]
        if "enum" in s:
            lines.append(
                "- 可选值：`" + json.dumps(s["enum"], ensure_ascii=False) + "`。"
            )
        if "minimum" in s:
            lines.append(f"- 范围：{s['minimum']}–{s.get('maximum', '不限')}。")
        if "pattern" in s:
            lines.append("- 格式：`" + s["pattern"] + "`。")
        lines += ["", s["description"], "", f"[官方依据]({s['x-bda-source']})", ""]
    lines += [
        "## 固定生成参数与输出解释",
        "",
        "这些设置不在表单中编辑，但同样纳入执行计划：",
        "",
        "- `-in:file:s`：逐个暂存 PDB 输入的绝对路径；本版只接受单模型 PDB，mmCIF 须预先转换并保留链映射。",
        "- `-out:path:all` / `-out:file:scorefile`：每输入、每重复、每阶段的独立输出目录与评分文件；不覆盖已有输出。",
        "- `-run:constant_seed true` / `-run:jran`：显式可追溯种子；不是采样充分性的证明。",
        "- `-add_regular_scores_to_scorefile true`：IA 同时填充常规能量项，避免未计算的占位零值。关闭的 packstat 仍不能把其 0 解释为实际堆积评分。",
        "- `-tracer_data_print false`：InterfaceAnalyzer 写结构/scorefile；避免只有终端文本。",
        "- `-in:file:fullatom true`：RosettaDock 从全原子输入读入，完整协议仍可能包含低分辨率阶段。",
        "- `-docking:randomize1 true` / `-docking:randomize2 true`：global 模式随机化两个伙伴；local 使用 dock_pert。",
        "- `-ddg:legacy false`：显式选择现代 Cartesian DDG 路线，不依赖构建的 legacy 默认值。",
        "- `relax_interface` 的第二阶段固定 `-nstruct 1`，逐一分析第一阶段的全部 Relax PDB，实际命令另存 execution.json。",
        "",
        "## 输出参数口径",
        "",
        "| 输出 | 解释 |",
        "|---|---|",
        "| total_score / score及各能量项 | 特定权重下的 Rosetta 分数，REU；不可直接换成 kcal/mol |",
        "| dG_separated | 结合/分离伙伴的界面分数差，注明 packing 设置；不是相对 WT 的突变 ΔΔG |",
        "| dSASA_int | 接口埋藏溶剂可及面积，Å² |",
        "| dG_separated/dSASAx100 | 按埋藏面积归一化并乘 100 的界面分数 |",
        "| hbonds_int / delta_unsatHbonds | 接口氢键和埋藏未满足氢键统计，依赖协议及氢键判定 |",
        "| sc_value / packstat | 形状互补与堆积指标；packstat仅启用时有意义 |",
        "| docking RMSD / interface RMSD | 仅有匹配 native 参考时能解释为对参考偏差，单位 Å |",
        "| *.ddg | 原始 WT/突变能量记录，保留协议/迭代；物理稳定性或结合结论须另验证 |",
        "| 其他 SCORE 列 | 全部原名保留，不猜测语义；自定义 XML 新字段须附协议作者定义 |",
        "",
        "## 覆盖边界",
        "",
        "本插件不会从 Rosetta 输出虚构 pLDDT、ipTM、MSA 深度或 Kd；这些必须来自对应预测/序列分析/实验。不自动参数化小分子、不提供膜 MD；InterfaceAnalyzer 仅用于蛋白–蛋白界面。",
        "",
        "详细模式和科学限制见 [SCIENTIFIC_MODES.md](SCIENTIFIC_MODES.md)。",
    ]
    lines[1:1] = ['', '状态：活跃', '', '最后核验：2026-09-16（整合验证）', '', '权威范围：插件配置、参数解释与已记录的验证边界。', '', '数据来源：版本化插件声明、参数定义及本文列出的来源。', '', '替代关系：补充插件接口文档；配置覆盖不代表真实运行通过。']
    return {
        HERE / "options.json": json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
        ROOT / "backend_v2/plugin_manifests/rosetta-2024.09-bda.1.json": json.dumps(
            manifest, ensure_ascii=False, indent=2
        )
        + "\n",
        ROOT / "docs/rosetta/PARAMETERS.md": "\n".join(lines) + "\n",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    for path, value in build().items():
        if args.check:
            if not path.is_file() or path.read_text() != value:
                raise SystemExit("Generated file drift: " + str(path))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value)
    print(
        "Rosetta manifest, schema and complete parameter guide: "
        + ("verified" if args.check else "generated")
    )


if __name__ == "__main__":
    main()

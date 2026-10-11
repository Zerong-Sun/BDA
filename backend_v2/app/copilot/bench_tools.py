"""Scalar bench calculations shared with the direct laboratory tools.

Stored sequences remain unavailable to the model. Sequence-based calculations
stay in the standalone UI; this adapter accepts numeric inputs only.
"""
import json
import re
from typing import Annotated, Any

from pydantic import Field, TypeAdapter, ValidationError, model_validator

from ..core.problem import DomainError
from ..wetlab.bench import calculate
from ..wetlab.bench_schemas import (
    BenchCalculationResult,
    CentrifugeInput,
    ConcentrationInput,
    ConcentrationUnit,
    CopyNumberInput,
    DilutionInput,
    DNARatioInput,
    NucleicA260Input,
    Positive,
    ProteinA280Input,
    SerialDilutionInput,
    SolutionInput,
)


class ChatDilutionInput(DilutionInput):
    """Normalize independently stated stock/target units before feasibility checks."""

    target_concentration_unit: ConcentrationUnit | None = Field(
        default=None, description="Unit of target_concentration; omit only when it is already in concentration_unit (the stock unit).")
    molecular_weight_g_mol: Positive | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_target(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        stock_unit, target_unit = value.get("concentration_unit"), value.get("target_concentration_unit")
        if not stock_unit or not target_unit or stock_unit == target_unit:
            return value
        conversion = ConcentrationInput.model_validate({"kind": "concentration", "value": value.get("target_concentration"),
                                                       "from_unit": target_unit, "to_unit": stock_unit,
                                                       "molecular_weight_g_mol": value.get("molecular_weight_g_mol")})
        converted = calculate(conversion).values[0].value
        return {**value, "target_concentration": converted, "target_concentration_unit": stock_unit}


ScalarInput = Annotated[
    ProteinA280Input | NucleicA260Input | ConcentrationInput | CopyNumberInput
    | ChatDilutionInput | DNARatioInput | CentrifugeInput | SerialDilutionInput | SolutionInput,
    Field(discriminator="kind"),
]
SCALAR_INPUT: TypeAdapter[ScalarInput] = TypeAdapter(ScalarInput)
EXPLICIT_ABSORBANCE_FIELDS = ("blank_absorbance", "path_length_cm", "dilution_factor", "absorbance_basis")
# The dedicated surface uses one calculator contract; legacy numeric tools remain
# available to other clients. Library metadata can supply a construct's constants.
DELIVERY_TOOLS = frozenset({"calculate_bench", "list_proteins"})

DELIVERY_INSTRUCTION = """This is a calculation-only delivery surface. Continue calling tools for ALL remaining
requested calculations, including dependent steps; a successful calculation does not finish the request.
The server renders calculated values, formulas, assumptions and sources verbatim. Your final response must
be a JSON object with complete (boolean) and remaining_questions (array of short strings in the user's
language). This is a machine-readable control envelope, not scientific prose: do not prefix a synthetic
label, citation instructions, or explanatory text. Server rendering handles those presentation concerns.
Set complete=false if any requested work is unresolved, and ask only for missing inputs or the
next necessary action. Do not include calculated values or scientific interpretations in these questions.
When all requested calculations are complete, return {"complete":true,"remaining_questions":[]}.
"""


def parameters() -> dict[str, Any]:
    schema = SCALAR_INPUT.json_schema()
    definitions = schema.pop("$defs", {})
    for name in ("ProteinA280Input", "NucleicA260Input"):
        definition = definitions[name]
        definition["required"] = list(dict.fromkeys([*definition["required"], *EXPLICIT_ABSORBANCE_FIELDS]))
        for field in EXPLICIT_ABSORBANCE_FIELDS:
            definition["properties"][field].pop("default", None)
    # Local references resolve from the tool's root, not its nested property.
    return {"type": "object", "$defs": definitions, "properties": {"calculation": schema},
            "required": ["calculation"], "additionalProperties": False}


def run(_context: Any, arguments: dict[str, Any]) -> dict:
    calculation = arguments.get("calculation")
    if isinstance(calculation, dict) and calculation.get("kind") in {"protein-a280", "nucleic-a260"}:
        if any(field not in calculation for field in EXPLICIT_ABSORBANCE_FIELDS):
            raise DomainError("bench_inputs_missing", "Supply the blank, path length, dilution factor and absorbance basis explicitly.", status_code=422)
    try:
        request = SCALAR_INPUT.validate_python(calculation)
    except ValidationError as exc:
        # Do not echo raw argument values through validation feedback.
        raise DomainError("bench_inputs_inconsistent",
                          "Check the supplied sample type, units, positive values, concentration order, and absorbance path basis; normalized readings require 1 cm.",
                          status_code=422) from exc
    result = calculate(request)
    if isinstance(request, ChatDilutionInput) and isinstance(calculation, dict):
        target_unit = calculation.get("target_concentration_unit")
        if target_unit and target_unit != request.concentration_unit:
            result.assumptions.append(f"Target concentration was converted from {target_unit} to the stock unit {request.concentration_unit} before calculating dilution volumes.")
            result.assumptions_zh.append(f"目标浓度先由 {target_unit} 换算为原液单位 {request.concentration_unit}，再计算稀释体积。")
    return result.model_dump(mode="json")


def render_result(result: dict, *, language: str) -> str:
    """Render trusted scalar results without a second model rewriting units or assumptions."""
    value = BenchCalculationResult.model_validate(result)
    zh = language == "zh"
    lines = ["**计算结果**" if zh else "**Calculation result**", ""]
    lines += [f"- {row.label_zh if zh else row.label}：**{row.value:.8g} {row.unit}**" for row in value.values]
    lines += ["", "**公式**" if zh else "**Formula**", value.formula, "",
              "**适用条件**" if zh else "**Assumptions**"]
    lines += [f"- {item}" for item in (value.assumptions_zh if zh else value.assumptions)]
    warnings = value.warnings_zh if zh else value.warnings
    if warnings:
        lines += ["", "**局限**" if zh else "**Limitations**", *[f"- {item}" for item in warnings]]
    if value.steps:
        lines += ["", "| 管号 | µM | 取样 µL | 稀释液 µL | 总体积 µL |" if zh else "| Tube | µM | From source µL | Buffer µL | Total µL |",
                  "| --- | --- | --- | --- | --- |"]
        lines += [f"| {step.step} | {step.conc_uM:.8g} | {step.stock_vol_uL:.8g} | {step.buffer_vol_uL:.8g} | {step.total_vol_uL:.8g} |" for step in value.steps]
    lines += ["", ("方法来源：" if zh else "Method sources: ")
              + " · ".join(f"[{ref.title}]({ref.url})" for ref in value.references), "",
              "这是基于所填参数的计算，不是新的实验测量；未保存实验记录。" if zh else
              "Calculated from the supplied inputs, not a new measurement; no experiment record was saved."]
    return "\n".join(lines)


def completion_status(final_content: str) -> tuple[bool, list[str]]:
    """Only the bounded delivery contract can assert that all steps are done."""
    try:
        fenced = re.fullmatch(r"\s*```(?:json)?\s*\n(.*?)\n```\s*", final_content, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            final_content = fenced.group(1)
        status = json.loads(final_content)
        if not isinstance(status, dict) or type(status.get("complete")) is not bool:
            raise ValueError("invalid_completion")
        questions = status.get("remaining_questions")
        if not isinstance(questions, list) or len(questions) > 8 or any(
            not isinstance(question, str) or not question.strip() or len(question) > 1000 for question in questions
        ):
            raise ValueError("invalid_questions")
        if set(status) != {"complete", "remaining_questions"}:
            raise ValueError("unexpected_delivery_fields")
        return status["complete"] and not questions, questions
    except (TypeError, ValueError):
        return False, []


def _table_text(value: Any) -> str:
    # Library names are user data, not Markdown links or HTML.
    return re.sub(r"([\\`*_{}\[\]<>()|#!])", r"\\\1", str(value if value is not None else "—")).replace("\n", " ").replace("\r", " ")


def render_delivery(results: list[dict], final_content: str, *, language: str, exhausted: bool = False,
                    libraries: list[list[dict]] | None = None, interrupted: bool = False) -> str:
    """Keep every successful read result and model clarification separate."""
    sections = [render_result(result, language=language) for result in results]
    zh = language == "zh"
    for library in libraries or []:
        sections.append("**本次查询返回的蛋白条目**" if zh else "**Protein entries returned by this query**")
        if not library:
            sections.append("本次查询未返回条目。" if zh else "This query returned no entries.")
            continue
        sections.append(("| 名称 | ID | 长度 (aa) | 分子量 (g/mol) |" if zh else
                         "| Name | ID | Length (aa) | Molecular weight (g/mol) |") + "\n| --- | --- | --- | --- |\n" +
                        "\n".join("| " + " | ".join(_table_text(row.get(key)) for key in ("name", "id", "length", "molecular_weight")) + " |" for row in library))
    complete, questions = completion_status(final_content)
    if exhausted or interrupted or not complete:
        sections += ["**尚未完成全部请求**" if zh else "**Request remains incomplete**",
                     "以上保留了已完成的工具结果；其余范围仍需确认。" if zh else
                     "Completed tool results are preserved above; the remaining scope still needs confirmation."]
        if exhausted:
            sections.append("工具调用额度已用完，仍有步骤未执行。" if zh else "The tool-call budget was reached; some steps did not run.")
        if interrupted:
            sections.append("有工具或最终回复失败，请核对尚未完成的部分。" if zh else "A tool or final response failed; check the remaining work.")
        if questions:
            sections.append("\n".join(f"- {question}" for question in questions))
    return "\n\n".join(sections)

"""Scalar bench calculations shared with the direct laboratory tools.

Stored sequences remain unavailable to the model. Sequence-based calculations
stay in the standalone UI; this adapter accepts numeric inputs only.
"""
import json
from typing import Annotated, Any

from pydantic import Field, TypeAdapter, ValidationError

from ..core.problem import DomainError
from ..wetlab.bench import calculate
from ..wetlab.bench_schemas import (
    BenchCalculationResult,
    CentrifugeInput,
    ConcentrationInput,
    CopyNumberInput,
    DilutionInput,
    DNARatioInput,
    NucleicA260Input,
    ProteinA280Input,
    SerialDilutionInput,
    SolutionInput,
)

ScalarInput = Annotated[
    ProteinA280Input | NucleicA260Input | ConcentrationInput | CopyNumberInput
    | DilutionInput | DNARatioInput | CentrifugeInput | SerialDilutionInput | SolutionInput,
    Field(discriminator="kind"),
]
SCALAR_INPUT: TypeAdapter[ScalarInput] = TypeAdapter(ScalarInput)

DELIVERY_INSTRUCTION = """This is a calculation-only delivery surface. Continue calling tools for ALL remaining
requested calculations, including dependent steps; a successful calculation does not finish the request.
The server renders calculated values, formulas, assumptions and sources verbatim. Your final response must
be a JSON object with complete (boolean) and remaining_questions (array of short strings in the user's
language). Set complete=false if any requested work is unresolved, and ask only for missing inputs or the
next necessary action. Do not include calculated values or scientific interpretations in these questions.
When all requested calculations are complete, return {"complete":true,"remaining_questions":[]}.
"""


def parameters() -> dict[str, Any]:
    schema = SCALAR_INPUT.json_schema()
    definitions = schema.pop("$defs", {})
    # Local references resolve from the tool's root, not its nested property.
    return {"type": "object", "$defs": definitions, "properties": {"calculation": schema},
            "required": ["calculation"], "additionalProperties": False}


def run(_context: Any, arguments: dict[str, Any]) -> dict:
    try:
        request = SCALAR_INPUT.validate_python(arguments["calculation"])
    except ValidationError as exc:
        # Do not echo raw argument values through validation feedback.
        raise DomainError("bench_inputs_inconsistent",
                          "Check the supplied sample type, units, positive values, concentration order, and absorbance path basis; normalized readings require 1 cm.",
                          status_code=422) from exc
    return calculate(request).model_dump(mode="json")


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
        lines += ["", "| Tube | µM | From source µL | Buffer µL | Total µL |",
                  "| --- | --- | --- | --- | --- |"]
        lines += [f"| {step.step} | {step.conc_uM:.8g} | {step.stock_vol_uL:.8g} | {step.buffer_vol_uL:.8g} | {step.total_vol_uL:.8g} |" for step in value.steps]
    lines += ["", ("方法来源：" if zh else "Method sources: ")
              + " · ".join(f"[{ref.title}]({ref.url})" for ref in value.references), "",
              "这是基于所填参数的计算，不是新的实验测量；未保存实验记录。" if zh else
              "Calculated from the supplied inputs, not a new measurement; no experiment record was saved."]
    return "\n".join(lines)


def render_delivery(results: list[dict], final_content: str, *, language: str, exhausted: bool = False) -> str:
    """Keep model completion/clarification separate from the calculator's facts."""
    sections = [render_result(result, language=language) for result in results]
    zh = language == "zh"
    try:
        status = json.loads(final_content)
        if not isinstance(status, dict) or type(status.get("complete")) is not bool:
            raise ValueError("invalid_completion")
        questions = status.get("remaining_questions")
        if not isinstance(questions, list) or len(questions) > 8 or any(
            not isinstance(question, str) or not question.strip() or len(question) > 1000 for question in questions
        ):
            raise ValueError("invalid_questions")
        incomplete = not status["complete"] or bool(questions)
    except (TypeError, ValueError):
        questions = []
        incomplete = True
    if exhausted or incomplete:
        sections += ["**尚未完成全部请求**" if zh else "**Request remains incomplete**",
                     "以上仅为已完成的计算；其余范围仍需确认。" if zh else
                     "Only completed calculations are shown above; the remaining scope still needs confirmation."]
        if questions:
            sections.append("\n".join(f"- {question}" for question in questions))
    return "\n\n".join(sections)

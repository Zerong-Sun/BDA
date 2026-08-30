"""Design routes the route planner proposes, and the defaults it recommends.

The routes and their parameter values come from the project methods document
that Research renders under "Methods and Reproducibility": zeroed diffusion
noise, 50 denoising steps, 60-80 residue binders, near-argmax ProteinMPNN with
the soluble weights, AF2 initial-guess as the calibrated filter.

A recommendation is only ever applied when the *registered* plugin declares that
parameter and accepts the value. The operator's ``parameter_schema`` is the
authority, not this table: workflow submission validates node parameters against
it (``workflows.preflight.parameter_blockers``), so a confidently-guessed key the
schema rejects would turn a helpful default into a submission blocker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from jsonschema.exceptions import _Error as _JsonSchemaError


@dataclass(frozen=True)
class ParameterRecommendation:
    """One knob from the methods document.

    ``names`` lists the property names the knob is known by across plugin
    packagings, most canonical first; the first one the schema declares wins.
    """

    names: tuple[str, ...]
    value: Any
    reason: str


@dataclass(frozen=True)
class RouteStep:
    plugin_key: str
    purpose: str
    recommendations: tuple[ParameterRecommendation, ...] = ()


@dataclass(frozen=True)
class DesignRoute:
    route_id: str
    label: str
    summary: str
    requires_structure: bool
    steps: tuple[RouteStep, ...]
    rationale: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    constraints: dict[str, Any] = field(default_factory=dict)


_ZERO_NOISE = (
    ParameterRecommendation(
        names=("noise_scale_ca",),
        value=0,
        reason="Zeroing diffusion noise trades structural diversity for a materially higher wet-lab hit rate on interface design.",
    ),
    ParameterRecommendation(
        names=("noise_scale_frame",),
        value=0,
        reason="Frame noise is zeroed alongside Ca noise; the two are set together.",
    ),
)

_DENOISING_STEPS = ParameterRecommendation(
    names=("diffuser_t", "timesteps", "num_timesteps"),
    value=50,
    reason="50 steps is standard for binder design and 4x cheaper than the default 200 with no meaningful quality loss.",
)

_BINDER_LENGTH = ParameterRecommendation(
    names=("binder_length", "length", "design_length"),
    value=70,
    reason="60-75 aa keeps every design inside a single oligo-pool member (~230-250 nt of coding sequence).",
)

_MPNN_TEMPERATURE = ParameterRecommendation(
    names=("sampling_temp", "temperature", "sampling_temperature"),
    value=0.0001,
    reason="Near-argmax sampling is the binder-design default; raise it only to build library diversity for display.",
)

_MPNN_SEQUENCES = ParameterRecommendation(
    names=("seqs_per_struct", "num_seq_per_target", "sequences_per_backbone"),
    value=8,
    reason="8 sequences per backbone is the cost/benefit point; 32 improves best-of yield marginally and quadruples AF2 cost.",
)

_MPNN_SOLUBLE = ParameterRecommendation(
    names=("use_soluble_model", "soluble_model", "soluble"),
    value=True,
    reason="The default weights are trained including membrane proteins and place hydrophobics on the binder surface.",
)

_AF2_INITIAL_GUESS = ParameterRecommendation(
    names=("initial_guess", "use_initial_guess"),
    value=True,
    reason="AF2 initial-guess is the best-calibrated single filter for designed binders; pae_interaction comes from this run.",
)

_ROSETTA_SCORE_FUNCTION = ParameterRecommendation(
    names=("score_function", "scorefxn"),
    value="beta_nov16",
    reason="REU values shift between score functions, so the ddG thresholds only mean anything if the function is pinned.",
)

_ROSETTA_RELAX_REPEATS = ParameterRecommendation(
    names=("relax_repeats", "nstruct"),
    value=3,
    reason="Three relax repeats is the usual point where interface energies stop moving.",
)

_BINDCRAFT_FINAL_DESIGNS = ParameterRecommendation(
    names=("number_of_final_designs", "num_final_designs"),
    value=100,
    reason="BindCraft costs 10-40 GPU-minutes per accepted design; size the focused arm accordingly.",
)

_BINDCRAFT_MIN_LENGTH = ParameterRecommendation(
    names=("min_binder_length",),
    value=60,
    reason="Lower bound of the length regime with the best-characterised folding behaviour.",
)

_BINDCRAFT_MAX_LENGTH = ParameterRecommendation(
    names=("max_binder_length",),
    value=90,
    reason="The focused arm is not oligo-pool encoded, so it may exceed the 75-80 aa pooled ceiling.",
)

ROUTE_CATALOG: tuple[DesignRoute, ...] = (
    DesignRoute(
        route_id="structure-acquisition",
        label="Structure acquisition",
        summary="Establish trustworthy coordinates for the target surface before any binder is generated.",
        requires_structure=False,
        steps=(
            RouteStep(
                plugin_key="AlphaFold2",
                purpose="Predict the target and build a seed ensemble for the design surface.",
            ),
        ),
        rationale=(
            "The project has no confirmed structure artifact, and design quality is set by the epitope, not the model.",
            "Predicted extracellular loops are the least reliable output of any predictor; treat them as an ensemble, not a coordinate set.",
        ),
        risks=(
            "Designing against a single predicted loop conformation is the most common silent failure in this class of project.",
        ),
        constraints={"ensemble_predictions": 20, "max_loop_ca_rmsd_angstrom": 3.0},
    ),
    DesignRoute(
        route_id="de-novo-binder-pooled",
        label="De novo binder, pooled",
        summary="High-volume generation sized for a pooled screen: diffuse backbones, design sequences, filter on predicted interface confidence.",
        requires_structure=True,
        steps=(
            RouteStep(
                plugin_key="RFdiffusion",
                purpose="Generate binder backbones against the selected hotspot set.",
                recommendations=(*_ZERO_NOISE, _DENOISING_STEPS, _BINDER_LENGTH),
            ),
            RouteStep(
                plugin_key="ProteinMPNN",
                purpose="Design sequences on each backbone with the soluble weights.",
                recommendations=(_MPNN_TEMPERATURE, _MPNN_SEQUENCES, _MPNN_SOLUBLE),
            ),
            RouteStep(
                plugin_key="AlphaFold2",
                purpose="Score every design with initial-guess prediction; pae_interaction gates the library.",
                recommendations=(_AF2_INITIAL_GUESS,),
            ),
            RouteStep(
                plugin_key="Rosetta",
                purpose="Interface energetics, shape complementarity, and aggregation propensity on the survivors.",
                recommendations=(_ROSETTA_SCORE_FUNCTION, _ROSETTA_RELAX_REPEATS),
            ),
        ),
        rationale=(
            "Hotspot choice is the highest-variance decision: run several sets at 10^3-10^4 designs each before scaling the winners.",
            "With pooled screening capacity a false negative costs a molecule and a false positive costs nothing, so gate the library on Tier A, not Tier B.",
            "Keep every score for every member; the metric-versus-outcome regression outlives the campaign.",
        ),
        risks=(
            "Thresholds are a starting guess until a known-answer control target has been run end to end through this same route.",
        ),
        constraints={
            "tier_a": {
                "pae_interaction": "< 15",
                "binder_plddt": "> 70",
                "binder_ca_rmsd_angstrom": "< 3.0",
                "rosetta_ddg_reu": "< -20",
            },
            "tier_b": {
                "pae_interaction": "< 7",
                "binder_plddt": "> 85",
                "binder_ca_rmsd_angstrom": "< 1.5",
                "rosetta_ddg_reu": "< -40",
            },
        },
    ),
    DesignRoute(
        route_id="de-novo-binder-focused",
        label="De novo binder, focused",
        summary="Low-volume, high-quality arm for the two or three best epitopes, where each accepted design is worth GPU-minutes.",
        requires_structure=True,
        steps=(
            RouteStep(
                plugin_key="BindCraft",
                purpose="Hallucinate, redesign, and filter binders in one pipeline for a single high-value epitope.",
                recommendations=(
                    _BINDCRAFT_FINAL_DESIGNS,
                    _BINDCRAFT_MIN_LENGTH,
                    _BINDCRAFT_MAX_LENGTH,
                ),
            ),
            RouteStep(
                plugin_key="Rosetta",
                purpose="Independent interface and developability scoring outside the design loop.",
                recommendations=(_ROSETTA_SCORE_FUNCTION,),
            ),
        ),
        rationale=(
            "BindCraft is a scalpel, not a firehose: budget roughly 10-40 GPU-minutes per accepted design.",
            "Run it in parallel with the pooled arm rather than instead of it; the two fail in different ways.",
        ),
        risks=(
            "Filtering inside the design loop means its accepted designs are not an independent test of those same filters.",
        ),
        constraints={"binder_length_range": [60, 90]},
    ),
)


def _schema_properties(schema: Any) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {}
    properties = schema.get("properties")
    return properties if isinstance(properties, dict) else {}


def _accepts(schema: Any, property_name: str, value: Any) -> bool:
    """Whether the plugin's schema declares the property and accepts the value."""
    properties = _schema_properties(schema)
    if property_name not in properties:
        return False
    subschema = properties[property_name]
    if not isinstance(subschema, dict):
        return False
    try:
        Draft202012Validator.check_schema(subschema)
        return not list(Draft202012Validator(subschema).iter_errors(value))
    except (SchemaError, _JsonSchemaError):
        # A malformed plugin schema is the plugin's defect; do not guess past it.
        return False


def recommended_parameters(
    step: RouteStep,
    parameter_schema: Any,
) -> tuple[dict[str, Any], list[str]]:
    """Resolve a step's recommendations against one plugin's parameter schema.

    Returns the parameters to apply and a note per recommendation that was
    dropped, so the plan can say what it could not set rather than silently
    shipping a thinner default set than the methods document prescribes.
    """
    parameters: dict[str, Any] = {}
    dropped: list[str] = []
    for recommendation in step.recommendations:
        name = next(
            (
                candidate
                for candidate in recommendation.names
                if _accepts(parameter_schema, candidate, recommendation.value)
            ),
            None,
        )
        if name is None:
            dropped.append(
                f"{step.plugin_key}: no registered parameter for "
                f"{recommendation.names[0]}={recommendation.value!r}; set it on the node by hand."
            )
            continue
        parameters[name] = recommendation.value
    return parameters, dropped


def routes_for(*, has_structure: bool) -> tuple[DesignRoute, ...]:
    """Routes worth proposing, most recommended first.

    Without a confirmed structure only structure acquisition is honest: the
    binder routes would be designing against coordinates nobody has checked.
    """
    if not has_structure:
        return tuple(route for route in ROUTE_CATALOG if not route.requires_structure)
    return tuple(route for route in ROUTE_CATALOG if route.requires_structure)

"""Provider endpoints — model discovery and deployment model/effort config.

Model discovery + deployment model default land here from issue #55; the
deployment reasoning-effort default (``/v1/effort``) mirrors the model surface
from issue #60. Effort has no discovery endpoint — it is an opaque
pass-through string, not enumerated per provider.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from mad.core.orchestration.use_cases.deployment_effort_config import (
    ClearDeploymentEffortUseCase,
    DeploymentEffortOutput,
    GetDeploymentEffortUseCase,
    SetDeploymentEffortInput,
    SetDeploymentEffortUseCase,
)
from mad.core.orchestration.use_cases.deployment_model_config import (
    ClearDeploymentModelUseCase,
    DeploymentModelOutput,
    GetDeploymentModelUseCase,
    SetDeploymentModelInput,
    SetDeploymentModelUseCase,
)
from mad.core.orchestration.use_cases.list_provider_models import ListProviderModelsUseCase

router = APIRouter(tags=["providers"])


class ProviderModelsResponse(BaseModel):
    providers: dict[str, list[str]] = Field(
        ..., description="Provider name -> list of model identifiers available from that provider."
    )


class DeploymentModelResponse(BaseModel):
    """Current deployment-wide model default.

    ``model`` is ``null`` when no deployment model has been set — sessions
    with no override will use the provider's machine-configured default.
    """

    model: str | None = None


class SetDeploymentModelRequest(BaseModel):
    model: str = Field(..., description="Model identifier to set as the deployment-wide default.")


class DeploymentEffortResponse(BaseModel):
    """Current deployment-wide reasoning-effort default.

    ``effort`` is ``null`` when no deployment effort has been set — sessions
    with no override will use the provider's machine-configured default (no
    ``--effort`` / ``--variant`` flag is passed).
    """

    effort: str | None = None


class SetDeploymentEffortRequest(BaseModel):
    effort: str = Field(
        ...,
        description=(
            "Reasoning-effort level to set as the deployment-wide default. Opaque "
            "pass-through string forwarded verbatim to the provider CLI (claude "
            "``--effort``, opencode ``--variant``); not validated by Mad."
        ),
    )


def _catalog(request: Request):
    return request.app.state.model_catalog


def _deployment_model_config(request: Request):
    return request.app.state.deployment_model_config


def _deployment_effort_config(request: Request):
    return request.app.state.deployment_effort_config


def _emitter(request: Request):
    return request.app.state.event_emitter


@router.get("/v1/providers/models", response_model=ProviderModelsResponse)
async def list_provider_models(request: Request) -> ProviderModelsResponse:
    use_case = ListProviderModelsUseCase(catalog=_catalog(request))
    output = await use_case.execute()
    return ProviderModelsResponse(providers=output.catalog)


@router.get("/v1/model", response_model=DeploymentModelResponse)
async def get_deployment_model(request: Request) -> DeploymentModelResponse:
    """Read the deployment-wide default model.

    Returns ``null`` for ``model`` when no default has been set — the provider
    uses its own machine-configured default in that case.
    """
    use_case = GetDeploymentModelUseCase(config=_deployment_model_config(request))
    output = use_case.execute()
    return DeploymentModelResponse(model=output.model)


@router.put("/v1/model", response_model=DeploymentModelResponse)
async def set_deployment_model(
    payload: SetDeploymentModelRequest,
    request: Request,
) -> DeploymentModelResponse:
    """Set the deployment-wide default model.

    Every session that has no per-session ``model`` override will use this
    default on the next launcher invocation (live inheritance — no restart
    required). Emits ``model.default.updated`` so the setting survives a
    restart via JSONL replay (hard rule 6).
    """
    use_case = SetDeploymentModelUseCase(
        config=_deployment_model_config(request),
        emitter=_emitter(request),
    )
    output: DeploymentModelOutput = await use_case.execute(
        SetDeploymentModelInput(model=payload.model)
    )
    return DeploymentModelResponse(model=output.model)


@router.delete("/v1/model", response_model=DeploymentModelResponse)
async def clear_deployment_model(request: Request) -> DeploymentModelResponse:
    """Clear the deployment-wide model default.

    After clearing, sessions with no per-session override will use the
    provider's own machine-configured default (i.e. no ``--model`` flag is
    passed). Idempotent: clearing when already unset is a no-op success.
    """
    use_case = ClearDeploymentModelUseCase(
        config=_deployment_model_config(request),
        emitter=_emitter(request),
    )
    output: DeploymentModelOutput = await use_case.execute()
    return DeploymentModelResponse(model=output.model)


@router.get("/v1/effort", response_model=DeploymentEffortResponse)
async def get_deployment_effort(request: Request) -> DeploymentEffortResponse:
    """Read the deployment-wide default reasoning effort.

    Returns ``null`` for ``effort`` when no default has been set — the provider
    uses its own machine-configured default in that case.
    """
    use_case = GetDeploymentEffortUseCase(config=_deployment_effort_config(request))
    output = use_case.execute()
    return DeploymentEffortResponse(effort=output.effort)


@router.put("/v1/effort", response_model=DeploymentEffortResponse)
async def set_deployment_effort(
    payload: SetDeploymentEffortRequest,
    request: Request,
) -> DeploymentEffortResponse:
    """Set the deployment-wide default reasoning effort.

    Every session that has no per-session ``effort`` override will use this
    default on the next launcher invocation (live inheritance — no restart
    required). Emits ``effort.default.updated`` so the setting survives a
    restart via JSONL replay (hard rule 6). The value is opaque — Mad does
    not validate it against any provider's effort levels.
    """
    use_case = SetDeploymentEffortUseCase(
        config=_deployment_effort_config(request),
        emitter=_emitter(request),
    )
    output: DeploymentEffortOutput = await use_case.execute(
        SetDeploymentEffortInput(effort=payload.effort)
    )
    return DeploymentEffortResponse(effort=output.effort)


@router.delete("/v1/effort", response_model=DeploymentEffortResponse)
async def clear_deployment_effort(request: Request) -> DeploymentEffortResponse:
    """Clear the deployment-wide reasoning-effort default.

    After clearing, sessions with no per-session override will use the
    provider's own machine-configured default (i.e. no ``--effort`` /
    ``--variant`` flag is passed). Idempotent: clearing when already unset is
    a no-op success.
    """
    use_case = ClearDeploymentEffortUseCase(
        config=_deployment_effort_config(request),
        emitter=_emitter(request),
    )
    output: DeploymentEffortOutput = await use_case.execute()
    return DeploymentEffortResponse(effort=output.effort)

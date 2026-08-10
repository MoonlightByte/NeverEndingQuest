"""Single production owner for hidden module build workspaces.

The low-level ``ModuleBuilder`` remains concerned only with writing an explicit
directory.  This service serializes allocation across processes, runs the
builder under a hidden UUID-owned workspace, gives callers one preparation
hook before the manifest is frozen, and either returns an immutable READY
handle or atomically promotes a toolkit build.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Generic, Optional, TypeVar, Union

from core.ai.module_creation_contract import ModuleCreationRecoveryRequiredError
from utils.module_lifecycle import (
    ActiveCandidate,
    LifecycleBusyError,
    LifecycleKind,
    LifecycleStatus,
    ModuleLifecycleStore,
    RecoveryStatus,
    RegistryPreparation,
)
from utils.module_refresh_lock import module_refresh_lock


PayloadT = TypeVar("PayloadT")
BuildCandidate = Callable[[Path, str], PayloadT]
PrepareCandidate = Callable[[Path, str], Optional[RegistryPreparation]]


@dataclass(frozen=True)
class ManagedBuildResult(Generic[PayloadT]):
    """Exact result of one managed hidden build."""

    build_id: str
    token: str
    kind: LifecycleKind
    module_name: str
    status: LifecycleStatus
    manifest_digest: str
    candidate_path: Optional[Path]
    final_path: Path
    payload: PayloadT
    active_candidate: Optional[ActiveCandidate] = None


class ManagedModuleBuilder:
    """Allocate, build, freeze, and optionally promote one exact candidate."""

    def __init__(
        self,
        modules_dir: Union[Path, str] = "modules",
        *,
        lock_timeout_seconds: float = 5.0,
    ):
        self.store = ModuleLifecycleStore(modules_dir)
        self.lock_timeout_seconds = lock_timeout_seconds

    def run(
        self,
        *,
        requested_name: str,
        kind: LifecycleKind,
        build_candidate: BuildCandidate[PayloadT],
        prepare_candidate: Optional[PrepareCandidate] = None,
        defer_promotion: bool = False,
        retain_story_first_failure: bool = False,
    ) -> ManagedBuildResult[PayloadT]:
        """Run one build under the cross-process module-refresh boundary.

        ``prepare_candidate`` runs after low-level generation and before the
        tree is synchronized or manifested.  It may normalize files in place
        and may return exact prior/candidate registry bytes; those bytes are
        durably attached while the transaction is still staging.

        Action callers use ``defer_promotion=True`` and hand the returned
        immutable ``active_candidate`` to publication.  Toolkit callers use
        the default and receive an exact public ``GENERATED`` result.
        """
        if not isinstance(kind, LifecycleKind):
            raise ValueError("Managed build kind must be explicit")
        if not callable(build_candidate):
            raise TypeError("build_candidate must be callable")
        if prepare_candidate is not None and not callable(prepare_candidate):
            raise TypeError("prepare_candidate must be callable")
        if kind is LifecycleKind.TOOLKIT and defer_promotion:
            raise ValueError("TOOLKIT builds must complete GENERATED promotion")
        if kind is not LifecycleKind.TOOLKIT and not defer_promotion:
            raise ValueError(
                "ACTION/DISCOVERY builds must remain hidden for publication"
            )
        if type(retain_story_first_failure) is not bool:
            raise TypeError("retain_story_first_failure must be boolean")

        with module_refresh_lock(
            max_wait_seconds=self.lock_timeout_seconds
        ) as acquired:
            if not acquired:
                raise LifecycleBusyError("Module lifecycle is busy")

            recovery = self.store.recover()
            if recovery.status is RecoveryStatus.INDETERMINATE:
                raise ModuleCreationRecoveryRequiredError(
                    "Module lifecycle recovery is required before retrying."
                )

            workspace = (
                self.store.claim_story_first_resume(requested_name, kind)
                if retain_story_first_failure
                else None
            )
            resumed = workspace is not None
            if workspace is None:
                final_name = self.store.allocate_final_name(requested_name)
                workspace = self.store.begin_build(
                    requested_name,
                    kind,
                    final_name=final_name,
                )
            else:
                final_name = workspace.final_name
            activated = False
            try:
                payload = build_candidate(workspace.candidate_path, final_name)
                if resumed:
                    self.store.finish_story_first_resume(workspace)
                if prepare_candidate is not None:
                    preparation = prepare_candidate(
                        workspace.candidate_path,
                        final_name,
                    )
                    if preparation is not None:
                        if type(preparation) is not RegistryPreparation:
                            raise TypeError(
                                "prepare_candidate must return RegistryPreparation or None"
                            )
                        self.store.stage_registry_preparation(
                            workspace,
                            preparation,
                        )

                active = self.store.activate_ready(workspace)
                activated = True
                if defer_promotion:
                    return ManagedBuildResult(
                        active.build_id,
                        active.token,
                        active.kind,
                        active.final_name,
                        LifecycleStatus.READY,
                        active.manifest_digest,
                        active.candidate_path,
                        active.final_path,
                        payload,
                        active,
                    )

                generated = self.store.promote_generated(active)
                return ManagedBuildResult(
                    generated.build_id,
                    generated.token,
                    generated.kind,
                    generated.module_name,
                    generated.status,
                    generated.manifest_digest,
                    None,
                    generated.final_path,
                    payload,
                    None,
                )
            except BaseException as build_error:
                if not activated:
                    try:
                        if retain_story_first_failure:
                            from core.generators.story_first.pipeline import (
                                StoryFirstPipelineError,
                            )

                            if isinstance(build_error, StoryFirstPipelineError):
                                self.store.stage_story_first_resume(
                                    workspace,
                                    stage=build_error.stage,
                                    failure_class=build_error.failure_class,
                                    issues=build_error.diagnostics,
                                    retries_remaining=0 if resumed else 1,
                                )
                        self.store.abort_build(
                            workspace,
                            reason_code="BUILD_FAILED",
                        )
                    except Exception:
                        raise ModuleCreationRecoveryRequiredError(
                            "Module generation cleanup could not be confirmed; "
                            "recovery is required before retrying."
                        ) from None
                    raise build_error
                # Once active, evidence remains intact for exact recovery, but
                # the caller must not treat an uncertain promotion as an
                # ordinary generation failure.
                if isinstance(build_error, (KeyboardInterrupt, SystemExit)):
                    raise build_error
                raise ModuleCreationRecoveryRequiredError(
                    "Module promotion could not be confirmed; recovery is "
                    "required before retrying."
                ) from None


def get_ready_managed_candidate(
    module_name: str,
    *,
    modules_dir: Union[Path, str] = "modules",
) -> Optional[ActiveCandidate]:
    """Publication integration seam for a game/action READY candidate."""
    return ModuleLifecycleStore(modules_dir).find_ready_candidate(
        module_name=module_name
    )

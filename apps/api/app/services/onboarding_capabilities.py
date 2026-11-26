"""Prepare and commit create-only starter selections for a confirmed Site."""
from typing import Annotated, Literal
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import String, column, func, select, values

from app.authorization import forbidden, require_scope
from app.models import BusinessFunction, CriticalityLevel, OnboardingCapabilitySubmission, Service, ServiceType
from app.routes.business_functions import add_business_function
from app.routes.crud_helpers import commit, flush
from app.routes.services import add_business_function_link, add_service
from app.schemas import BusinessFunctionCreate, ServiceBusinessFunctionCreate, ServiceCreate
from app.services import onboarding
from app.services.data_sources import lock_customer_manual_inventory
from app.services.homelab_catalogue import (
    DEFAULT_CRITICALITY_KEY, FUNCTION_COUNT, SERVICE_COUNT, SERVICE_TYPE_KEYS,
    AssociationID, CatalogueID, ContentVersion, FunctionID, ServiceID, load_catalogue,
)


STARTER_CHANGED = "The starter catalogue changed. Review the available version before continuing."
ReferenceKey = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,99}$")]


class SelectionItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=20000)

    @field_validator("name", "description")
    @classmethod
    def database_text(cls, value):
        if value is not None and ("\x00" in value or any(0xD800 <= ord(char) <= 0xDFFF for char in value)):
            raise ValueError("Unsupported character in text")
        return value


class FunctionSelection(SelectionItem):
    id: FunctionID


class ServiceSelection(SelectionItem):
    id: ServiceID
    service_type_key: ReferenceKey | None = None
    criticality_key: ReferenceKey | None = None


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    catalogue_id: CatalogueID
    schema_version: int = Field(ge=1, le=2147483647)
    content_version: ContentVersion
    functions: list[FunctionSelection] = Field(max_length=FUNCTION_COUNT)
    services: list[ServiceSelection] = Field(max_length=SERVICE_COUNT)
    associations: list[AssociationID] = Field(max_length=SERVICE_COUNT)


class CreationCounts(BaseModel):
    functions: int
    services: int
    associations: int


class ApplyOutcome(BaseModel):
    submission_id: UUID
    version: int
    current_stage: str
    created: CreationCounts


class NameWarning(BaseModel):
    definition_id: str
    code: Literal["existing_name"] = "existing_name"


def stale(payload: dict, catalogue) -> bool:
    return any(payload.get(key) != value for key, value in catalogue.versions.items())


def capabilities(principal, site) -> dict[str, bool]:
    return {
        "can_manage": principal.can(onboarding.MANAGE, site.customer_id, site.id),
        "can_view_service_types": principal.can_anywhere("service_types.view"),
        "can_view_criticality_levels": principal.can_anywhere("criticality_levels.view"),
        "can_create_functions": principal.can("business_functions.manage", site.customer_id),
        "can_create_services": principal.can("services.create", site.customer_id),
        "can_create_associations": all(principal.can(permission, site.customer_id) for permission in (
            "business_functions.manage", "business_functions.view",
        )),
    }


def require_confirmed(state, *, homelab=False):
    if state is None:
        raise HTTPException(404, "Record not found")
    if state.stage_decisions.get("environment") != "completed" or state.environment_profile not in {"homelab", "blank"}:
        raise HTTPException(409, "Confirm Environment before opening Capabilities.")
    if homelab and state.environment_profile != "homelab":
        raise HTTPException(409, "The starter catalogue requires the Homelab profile.")


def require_version(state, version, *, active=False):
    if state.version != version:
        raise HTTPException(409, onboarding.CONFLICT)
    if active and state.status == "saved":
        raise HTTPException(409, "Resume setup before applying Capabilities.")


def initial_selection(catalogue, state):
    use_defaults = "capabilities" not in state.stage_decisions
    functions = [{"id": item.id} for item in catalogue.functions if use_defaults and item.preselected]
    services = [{"id": item.id} for function in catalogue.functions for item in function.services
                if use_defaults and item.preselected]
    function_ids = {item["id"] for item in functions}
    service_ids = {item["id"] for item in services}
    return Selection(
        **catalogue.versions, functions=functions, services=services,
        associations=[link.id for link in catalogue.associations
                      if link.business_function_id in function_ids and link.service_id in service_ids],
    )


def read(state, principal, site):
    require_confirmed(state)
    permissions = capabilities(principal, site)
    result = {
        "version": state.version, "profile": state.environment_profile,
        "permissions": permissions, "catalogue": None, "defaults": None,
        "draft": None, "draft_stale": False, "default_service_type_keys": {},
        "default_criticality_key": None,
    }
    if state.environment_profile == "homelab":
        catalogue = load_catalogue()
        draft = state.capabilities_draft if permissions["can_manage"] else None
        result.update(
            catalogue=catalogue, defaults=initial_selection(catalogue, state),
            draft=draft, draft_stale=draft is not None and stale(draft, catalogue),
            default_service_type_keys=SERVICE_TYPE_KEYS, default_criticality_key=DEFAULT_CRITICALITY_KEY,
        )
    return result


def require_creation_grants(principal, customer_id, counts):
    if counts.functions or counts.associations:
        require_scope(principal, "business_functions.manage", customer_id)
    if counts.services:
        require_scope(principal, "services.create", customer_id)
    if counts.associations:
        require_scope(principal, "business_functions.view", customer_id, hide_existence=True)


def indexed(items, allowed, label):
    chosen = {item.id: item for item in items}
    if len(chosen) != len(items) or not chosen.keys() <= allowed:
        raise HTTPException(422, f"Invalid or repeated {label} definition ID.")
    return chosen


def selection_error(definition_id, message):
    return HTTPException(422, {"code": "invalid_selection", "definition_id": definition_id, "message": message})


def build_payload(schema, definition, item, **fields):
    overrides = item.model_dump(exclude_unset=True, exclude={"id", "service_type_key", "criticality_key"})
    payload = {"name": definition.name, "description": definition.description, **overrides, **fields}
    try:
        return schema.model_validate(payload)
    except ValidationError as exc:
        error = exc.errors(include_url=False, include_context=False, include_input=False)[0]
        raise selection_error(item.id, f"{error['loc'][0]}: {error['msg']}") from None


def active_references(db, model, keys, *, lock):
    query = select(model).where(model.active.is_(True), model.key.in_(keys)).order_by(model.key)
    if lock:
        # Block deactivation/renaming through commit. Order the shared locks.
        query = query.with_for_update(read=True).execution_options(populate_existing=True)
    return {row.key: row.id for row in db.scalars(query)} if keys else {}


def require_reference_grants(services, principal, catalogue):
    # Only callers allowed to list reference data can probe alternate keys.
    if principal.can_anywhere("service_types.view") and principal.can_anywhere("criticality_levels.view"):
        return
    defaults = {service.id: SERVICE_TYPE_KEYS[service.service_type_name]
                for group in catalogue.functions for service in group.services}
    if (not principal.can_anywhere("service_types.view") and any(
        item.service_type_key not in {None, defaults[item.id]} for item in services
    )) or (not principal.can_anywhere("criticality_levels.view") and any(
        item.criticality_key not in {None, DEFAULT_CRITICALITY_KEY} for item in services
    )):
        raise forbidden()


def prepare_selection(db, selection, customer_id, principal, *, lock_references=False):
    catalogue = load_catalogue()
    if stale(selection.model_dump(), catalogue):
        raise HTTPException(409, STARTER_CHANGED)
    function_defs = {item.id: item for item in catalogue.functions}
    service_defs = {item.id: item for group in catalogue.functions for item in group.services}
    function_items = indexed(selection.functions, function_defs.keys(), "Business Function")
    service_items = indexed(selection.services, service_defs.keys(), "Service")
    link_ids = set(selection.associations)
    if len(link_ids) != len(selection.associations):
        raise HTTPException(422, "Association definition IDs must be unique.")
    links = [link for link in catalogue.associations if link.id in link_ids]
    if len(links) != len(link_ids) or any(
        link.business_function_id not in function_items or link.service_id not in service_items for link in links
    ):
        raise HTTPException(422, "Each association must be approved and both endpoints selected.")

    reference_keys = {}
    for identifier, item in service_items.items():
        if ("service_type_key" in item.model_fields_set and item.service_type_key is None
                or "criticality_key" in item.model_fields_set and item.criticality_key is None):
            raise selection_error(identifier, "Choose an active Service Type and criticality.")
        reference_keys[identifier] = (
            item.service_type_key or SERVICE_TYPE_KEYS[service_defs[identifier].service_type_name],
            item.criticality_key or DEFAULT_CRITICALITY_KEY,
        )
    require_reference_grants(service_items.values(), principal, catalogue)
    types = active_references(db, ServiceType, {key for key, _ in reference_keys.values()}, lock=lock_references)
    levels = active_references(db, CriticalityLevel, {key for _, key in reference_keys.values()}, lock=lock_references)

    functions = {
        identifier: build_payload(BusinessFunctionCreate, definition, function_items[identifier],
                                  customer_id=customer_id)
        for identifier, definition in function_defs.items() if identifier in function_items
    }
    services = {}
    for identifier, definition in service_defs.items():
        if identifier not in service_items:
            continue
        type_key, level_key = reference_keys[identifier]
        if type_key not in types or level_key not in levels:
            label = "Service Type" if type_key not in types else "Criticality level"
            raise selection_error(identifier, f"{label} is not active or does not exist. Choose an active value.")
        services[identifier] = build_payload(
            ServiceCreate, definition, service_items[identifier], customer_id=customer_id,
            service_type_id=types[type_key], criticality_level_id=levels[level_key],
        )
    return functions, services, links


def name_warnings(db, principal, customer_id, functions, services):
    warnings = []
    for model, permission, candidates in (
        (BusinessFunction, "business_functions.view", functions), (Service, "services.view", services),
    ):
        if not candidates or not principal.can(permission, customer_id):
            continue
        proposed = values(column("definition_id", String), column("name", String), name="proposed").data(
            [(identifier, item.name) for identifier, item in candidates.items()],
        )
        query = select(proposed.c.definition_id).select_from(proposed).join(
            model, func.lower(model.name) == func.lower(proposed.c.name),
        ).where(model.customer_id == customer_id, model.site_id.is_(None), model.deleted_at.is_(None))
        if model is Service:
            query = query.where(Service.archived_at.is_(None))
        warnings.extend(NameWarning(definition_id=identifier) for identifier in sorted(set(db.scalars(query))))
    return warnings


def save_draft(db, customer, site, principal, request, state, payload):
    require_version(state, payload.version)
    if (state.capabilities_draft is not None and stale(state.capabilities_draft, load_catalogue())
            and not payload.replace_stale_draft):
        raise HTTPException(409, STARTER_CHANGED)
    prepare_selection(db, payload.selection, customer.id, principal)
    state.capabilities_draft = payload.selection.model_dump(mode="json", exclude_unset=True)
    if payload.save_and_exit and state.status == "in_progress":
        state.status = "saved"
    onboarding.record_progress(db, customer, site, principal, request, state, "capabilities_draft_saved")
    commit(db, "Capabilities draft")


def advance(state, decision):
    state.capabilities_draft = None
    state.stage_decisions = {**state.stage_decisions, "capabilities": decision}
    if state.current_stage == "capabilities":
        state.current_stage = "integrations"


def skip(db, customer, site, principal, request, state, version):
    require_version(state, version, active=True)
    if state.current_stage != "capabilities":
        raise HTTPException(409, "Capabilities has already been decided.")
    advance(state, "skipped")
    onboarding.record_progress(db, customer, site, principal, request, state, "capabilities_skipped")
    commit(db, "Capabilities progress")


def apply(db, customer, site, principal, request, state, payload):
    # The version binds this logical command to an immutable snapshot of the
    # shared draft. A globally unique submission key must not cross Sites.
    db.execute(select(func.pg_advisory_xact_lock(
        func.hashtextextended(f"atlas-onboarding-submission:{payload.submission_id}", 0),
    )))
    principal = onboarding.refreshed_access(db, principal, site, manage=True)
    receipt = db.get(OnboardingCapabilitySubmission, payload.submission_id)
    if receipt is not None:
        if receipt.onboarding_id != state.id:
            raise HTTPException(404, "Record not found")
        outcome = ApplyOutcome.model_validate(receipt.outcome)
        require_creation_grants(principal, customer.id, outcome.created)
        if receipt.requested_version != payload.version:
            raise HTTPException(409, "This submission ID was used with a different Apply request.")
        return outcome

    require_version(state, payload.version, active=True)
    if state.capabilities_draft is None:
        raise HTTPException(409, "Save the selection before applying Capabilities.")
    if stale(state.capabilities_draft, load_catalogue()):
        raise HTTPException(409, STARTER_CHANGED)

    selection = Selection.model_validate(state.capabilities_draft)
    counts = CreationCounts(functions=len(selection.functions), services=len(selection.services),
                            associations=len(selection.associations))
    if not counts.functions and not counts.services:
        raise HTTPException(422, "Select a Business Function or Service, or skip Capabilities.")
    require_creation_grants(principal, customer.id, counts)
    functions, services, links = prepare_selection(
        db, selection, customer.id, principal, lock_references=True,
    )
    # Reference maintenance can lock existing Services. Take the Customer lock
    # after reference locks and before the batch claims any unique keys.
    lock_customer_manual_inventory(db, customer.id)
    principal = onboarding.refreshed_access(db, principal, site, manage=True)
    require_creation_grants(principal, customer.id, counts)
    require_reference_grants(selection.services, principal, load_catalogue())

    try:
        new_functions = {key: add_business_function(db, item, principal, request) for key, item in functions.items()}
        new_services = {key: add_service(db, item, principal, request) for key, item in services.items()}
    except HTTPException as exc:
        cause = getattr(exc.__cause__, "orig", None)
        constraint = getattr(getattr(cause, "diag", None), "constraint_name", None)
        if constraint in {
            "uq_business_functions_customer_name_without_site", "uq_services_customer_name_without_site",
            "uq_services_customer_slug_without_site",
        }:
            raise HTTPException(409, "A selected name or generated Service identifier is unavailable. Edit the selected names and try again.") from None
        raise
    for link in links:
        add_business_function_link(
            db, new_services[link.service_id].id,
            ServiceBusinessFunctionCreate(business_function_id=new_functions[link.business_function_id].id),
            principal, request,
        )

    advance(state, "completed")
    onboarding.record_progress(db, customer, site, principal, request, state, "capabilities_applied")
    outcome = ApplyOutcome(submission_id=payload.submission_id, version=state.version,
                           current_stage=state.current_stage, created=counts)
    db.add(OnboardingCapabilitySubmission(
        id=payload.submission_id, onboarding_id=state.id, requested_version=payload.version,
        outcome=outcome.model_dump(mode="json"),
    ))
    flush(db, "Capabilities Apply")
    # A database constraint or shared canonical write may have made us wait.
    principal = onboarding.refreshed_access(db, principal, site, manage=True)
    require_creation_grants(principal, customer.id, counts)
    require_reference_grants(selection.services, principal, load_catalogue())
    commit(db, "Capabilities Apply")
    return outcome

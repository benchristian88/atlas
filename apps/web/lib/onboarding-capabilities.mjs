const versionFields = ["catalogue_id", "schema_version", "content_version"];
const functionFields = ["name", "description"];
const serviceFields = [...functionFields, "service_type_key", "criticality_key"];
const permissions = [
  "can_manage", "can_create_functions", "can_create_services", "can_create_associations",
  "can_view_service_types", "can_view_criticality_levels",
];

export function validateCapabilities(data, profile) {
  const invalid = () => { throw new Error("Atlas returned an invalid Capabilities response. Reload saved progress to try again."); };
  if (data?.profile !== profile || !Number.isInteger(data.version) || data.version < 1
    || permissions.some((key) => typeof data.permissions?.[key] !== "boolean")
    || typeof data.draft_stale !== "boolean") invalid();
  const { catalogue, defaults, draft, draft_stale: stale } = data;
  if (profile === "blank") {
    if (catalogue !== null || defaults !== null || draft !== null || stale) invalid();
    return data;
  }
  const validVersion = (selection) => versionFields.every((key) => selection?.[key] === catalogue[key]);
  const validSelection = (selection) => validVersion(selection) && ["functions", "services", "associations"]
    .every((field) => Array.isArray(selection[field]));
  const definition = (item) => typeof item?.id === "string" && typeof item.name === "string"
    && typeof item.description === "string" && typeof item.preselected === "boolean"
    && Number.isInteger(item.sort_order);
  if (catalogue?.schema_version !== 1 || catalogue.profile !== profile
    || typeof catalogue.catalogue_id !== "string" || typeof catalogue.content_version !== "string"
    || !Array.isArray(catalogue.functions) || !catalogue.functions.length || !Array.isArray(catalogue.associations)
    || !catalogue.functions.every((item) => definition(item) && Array.isArray(item.services)
      && item.services.every((service) => definition(service) && service.business_function_id === item.id
        && ["standard", "extended"].includes(service.selection_tier)
        && typeof data.default_service_type_keys?.[service.service_type_name] === "string"))
    || typeof data.default_criticality_key !== "string" || !validSelection(defaults)
    || (draft !== null && !stale && !validSelection(draft))) invalid();

  const functions = new Set(catalogue.functions.map(({ id }) => id));
  const services = new Map(catalogue.functions.flatMap(({ services }) => services.map((item) => [item.id, item])));
  const links = new Set(catalogue.associations.map((link) => link?.id));
  if (functions.size !== catalogue.functions.length
    || services.size !== catalogue.functions.reduce((total, item) => total + item.services.length, 0)
    || links.size !== catalogue.associations.length
    || !catalogue.associations.every((link) => typeof link?.id === "string" && functions.has(link.business_function_id)
      && services.get(link.service_id)?.business_function_id === link.business_function_id)) invalid();
  return data;
}

export function orderedDefinitions(definitions) {
  return [...definitions].sort((a, b) => a.sort_order - b.sort_order || a.id.localeCompare(b.id));
}

export function entryDefaults(data, definition) {
  const base = { name: definition.name, description: definition.description };
  return definition.business_function_id ? {
    ...base,
    service_type_key: data.default_service_type_keys[definition.service_type_name],
    criticality_key: data.default_criticality_key,
  } : base;
}

function allowedOverrides(definition, values) {
  const fields = definition.business_function_id ? serviceFields : functionFields;
  return Object.fromEntries(fields.filter((key) => Object.hasOwn(values, key))
    .map((key) => [key, values[key]]));
}

export function hasCustomisations(data, definition, overrides = {}) {
  const defaults = entryDefaults(data, definition);
  return Object.entries(overrides).some(([key, value]) => value !== defaults[key]);
}

export function selectionState(data, source = data.draft_stale ? data.defaults : data.draft ?? data.defaults) {
  const state = {
    functions: new Set(), services: new Set(), associations: new Set(), overrides: new Map(), remembered: new Map(),
  };
  if (!data.catalogue) return state;
  const { functions, associations } = data.catalogue;
  for (const [field, definitions] of [["functions", functions], ["services", functions.flatMap((group) => group.services)]]) {
    const byId = new Map(definitions.map((definition) => [definition.id, definition]));
    for (const entry of source[field]) {
      const definition = byId.get(entry?.id);
      if (!definition) continue;
      state[field].add(definition.id);
      const overrides = allowedOverrides(definition, entry);
      if (Object.keys(overrides).length) state.overrides.set(definition.id, overrides);
    }
  }
  const eligibleLinks = new Set(associations.filter(({ business_function_id, service_id }) =>
    state.functions.has(business_function_id) && state.services.has(service_id)).map(({ id }) => id));
  state.associations = new Set(source.associations.filter((id) => eligibleLinks.has(id)));
  return state;
}

export function recommendedState(data) {
  const functions = data.catalogue.functions.filter((item) => item.preselected).map(({ id }) => ({ id }));
  const services = data.catalogue.functions.flatMap((group) => group.services)
    .filter((item) => item.preselected).map(({ id }) => ({ id }));
  return selectionState(data, {
    functions,
    services,
    associations: data.catalogue.associations.map(({ id }) => id),
  });
}

export function changeSelection(state, catalogue, group, { service, selected, all = false, canSelectService = true }) {
  const functions = new Set(state.functions);
  const services = new Set(state.services);
  const associations = new Set(state.associations);
  const remembered = new Map(state.remembered);
  const links = catalogue.associations.filter((link) => link.business_function_id === group.id);

  function selectService(serviceId) {
    services.add(serviceId);
    for (const link of links) {
      if (link.service_id === serviceId) associations.add(link.id);
    }
  }

  if (service) {
    if (selected) {
      functions.add(group.id);
      selectService(service.id);
    } else {
      services.delete(service.id);
      for (const link of links) {
        if (link.service_id === service.id) associations.delete(link.id);
      }
    }
  } else if (selected) {
    functions.add(group.id);
    const previous = remembered.get(group.id);
    if (canSelectService && all) {
      for (const item of group.services) {
        if (!services.has(item.id)) selectService(item.id);
      }
    } else if (canSelectService && previous) {
      for (const id of previous.services) services.add(id);
      for (const id of previous.associations) associations.add(id);
    }
    remembered.delete(group.id);
  } else {
    remembered.set(group.id, {
      services: group.services.filter(({ id }) => services.has(id)).map(({ id }) => id),
      associations: links.filter(({ id }) => associations.has(id)).map(({ id }) => id),
    });
    for (const { id } of links) associations.delete(id);
    for (const { id } of group.services) services.delete(id);
    functions.delete(group.id);
  }
  return { ...state, functions, services, associations, remembered };
}

export function editEntry(state, data, definition, values) {
  const overrides = new Map(state.overrides);
  const defaults = entryDefaults(data, definition);
  const previous = overrides.get(definition.id) ?? {};
  const override = Object.fromEntries(Object.entries(allowedOverrides(definition, values)).filter(([key, value]) =>
    value !== defaults[key] || (Object.hasOwn(previous, key) && value === previous[key])));
  if (Object.keys(override).length) overrides.set(definition.id, override);
  else overrides.delete(definition.id);
  return { ...state, overrides };
}

export function selectionPayload(data, state) {
  const { catalogue } = data;
  const entry = (id) => ({ id, ...state.overrides.get(id) });
  return {
    ...Object.fromEntries(versionFields.map((key) => [key, catalogue[key]])),
    functions: [...state.functions].map(entry),
    services: [...state.services].map(entry),
    associations: [...state.associations],
  };
}

export function creationAllowed(permissions, selection) {
  return Boolean(selection && permissions.can_manage
    && (!selection.functions.length || permissions.can_create_functions)
    && (!selection.services.length || permissions.can_create_services)
    && (!selection.associations.length || permissions.can_create_associations));
}

export function restrictedClassifications(data, selection) {
  const restricted = new Set();
  if (!selection) return restricted;
  const { catalogue, permissions, default_service_type_keys, default_criticality_key } = data;
  if (permissions.can_view_service_types && permissions.can_view_criticality_levels) return restricted;
  const services = new Map(catalogue.functions.flatMap((group) => group.services).map((item) => [item.id, item]));
  for (const item of selection.services) {
    const typeKey = default_service_type_keys[services.get(item.id).service_type_name];
    if ((!permissions.can_view_service_types && Object.hasOwn(item, "service_type_key") && item.service_type_key !== typeKey)
      || (!permissions.can_view_criticality_levels && Object.hasOwn(item, "criticality_key")
        && item.criticality_key !== default_criticality_key)) restricted.add(item.id);
  }
  return restricted;
}

export function readPendingApply(key) {
  try {
    const entry = JSON.parse(window.sessionStorage.getItem(key));
    if (Number.isInteger(entry?.version) && entry.version > 0
      && /^[\da-f]{8}-[\da-f]{4}-4[\da-f]{3}-[89ab][\da-f]{3}-[\da-f]{12}$/i.test(entry.submission_id)) {
      return { version: entry.version, submission_id: entry.submission_id };
    }
  } catch {
    // The read-only workflow remains usable if browser storage is blocked.
  }
  return null;
}

export function pendingApplyKey(userId, path) {
  return `atlas:onboarding-apply:${userId}:${path}`;
}

export function beginPendingApply(key, version) {
  const existing = readPendingApply(key);
  if (existing) return existing;
  // getRandomValues is also available on Atlas installations served over HTTP.
  const bytes = window.crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  const submission_id = [hex.slice(0, 8), hex.slice(8, 12), hex.slice(12, 16), hex.slice(16, 20), hex.slice(20)].join("-");
  const entry = { version, submission_id };
  // Persist before sending the operation so a reload can repeat the same command.
  window.sessionStorage.setItem(key, JSON.stringify(entry));
  return entry;
}

export function clearPendingApply(key) {
  window.sessionStorage.removeItem(key);
}

export function validApplyOutcome(result, pending) {
  return result?.submission_id === pending.submission_id && result.version === pending.version + 1
    && typeof result.current_stage === "string" && ["functions", "services", "associations"]
      .every((key) => Number.isInteger(result.created?.[key]) && result.created[key] >= 0);
}

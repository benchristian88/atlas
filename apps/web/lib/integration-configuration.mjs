export function visibleField(field, config) {
  return !field.visible_when || config[field.visible_when.field] === field.visible_when.equals;
}

export function initialConfig(form, record = {}) {
  return Object.fromEntries(form.connection_fields.filter(field => !field.secret).flatMap(field => {
    const value = Object.hasOwn(record, field.key) ? record[field.key] : field.default ?? (field.type === "boolean" && field.required ? false : undefined);
    return value === undefined ? [] : [[field.key, value]];
  }));
}

export function configurationPayload(form, config, credentials = {}) {
  const safe = {}, writeOnly = {};
  for (const field of form.connection_fields) {
    if (!visibleField(field, config)) continue;
    const value = (field.secret ? credentials : config)[field.key];
    if (value !== undefined && value !== "") (field.secret ? writeOnly : safe)[field.key] = value;
  }
  return { config: safe, credentials: writeOnly };
}

export const TEST_MESSAGES = Object.freeze({
  connected: "Connection authenticated successfully.",
  authentication_failed: "The API token was rejected. Check the token identity and replace the credential.",
  permission_limited: "The token has limited permissions for the connection probe. Review the dedicated token's permissions.",
  tls_trust_required: "Certificate trust could not be verified. Check the certificate or establish a trusted fingerprint.",
  runtime_unavailable: "The local runtime is unavailable. Check its service and try again.",
  package_unavailable: "The exact verified Connector package is unavailable. Ask a global administrator to check it.",
  unsafe_endpoint: "This endpoint is not allowed. Use an HTTPS infrastructure address without embedded credentials.",
  redirect_rejected: "The endpoint redirected the request. Use the source's direct HTTPS address.",
  timeout: "The connection probe timed out. Check connectivity and try again.",
  source_incompatible: "This source version is known to be incompatible with the Connector. Update the Connector before use.",
});

export function testMessage(result) {
  return TEST_MESSAGES[result?.category] || "The connection probe could not complete. Check the endpoint and configuration.";
}

// Same bounded generic schema as the API: reject an entire malformed list.
export function capabilityDiagnostics(value) {
  const fields = new Set(["capability", "state", "privilege", "path_category"]);
  const states = new Set(["ready", "permission_limited", "unproven", "source_unavailable"]);
  const paths = new Set(["root", "inventory", "topology", "authorization"]);
  const identifier = /^[A-Za-z][A-Za-z0-9_.-]{0,63}$/;
  if (!Array.isArray(value) || value.length > 16) return [];
  if (value.some(row => !row || Array.isArray(row) || typeof row !== "object"
    || Object.keys(row).some(key => !fields.has(key))
    || Object.values(row).some(item => typeof item !== "string")
    || !identifier.test(row.capability || "") || !states.has(row.state) || !paths.has(row.path_category)
    || (Object.hasOwn(row, "privilege") && !identifier.test(row.privilege)))) return [];
  return value;
}

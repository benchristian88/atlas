// Editing a customer-wide record must not adopt the shell's Site viewpoint.
// The API still authorizes the record, requested context, and mutation.
export function recordContextOptions(customerId, siteId) {
  if (!customerId) throw new Error("A record Customer is required.");
  return { omitContext: true, headers: {
    "X-Atlas-Customer-ID": customerId,
    ...(siteId ? { "X-Atlas-Site-ID": siteId } : {}),
  } };
}

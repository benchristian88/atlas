export function loginResult(result) {
  if (result?.mfa_required === true && result?.user == null) return { mfa_required: true };
  if (result?.mfa_required === true) throw new Error("An MFA challenge cannot contain an authenticated user.");
  if (typeof result?.user?.email !== "string" || typeof result?.user?.display_name !== "string") {
    throw new Error("Atlas API returned an unexpected login response.");
  }
  return result.user;
}

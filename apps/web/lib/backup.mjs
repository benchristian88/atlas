export const MAX_BACKUP_BYTES = 2 * 1024 ** 3;

export function backupValidation(passphrase, confirmation) {
  if (passphrase.length < 12 || passphrase.length > 1024) return "Use a passphrase of 12–1024 characters.";
  if (passphrase !== confirmation) return "Passphrases do not match.";
  return "";
}

export function restoreFileValidation(file) {
  if (!file || file.size === 0) return "Choose an Atlas backup file.";
  if (file.size > MAX_BACKUP_BYTES) return "Choose a backup no larger than 2 GiB.";
  return "";
}

export function canManageBackups(user) {
  return Boolean(!user?.force_password_change && user?.assignments?.some(assignment =>
    assignment.scope_type === "global" && assignment.role_name === "Master Administrator"
    && assignment.permissions?.includes("system_settings.manage")));
}

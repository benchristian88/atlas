export class ApiError extends Error {
  constructor(message, { status = null, kind = "api", details = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.kind = kind;
    this.details = details;
  }
}

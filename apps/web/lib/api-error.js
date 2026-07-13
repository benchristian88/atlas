export class ApiError extends Error {
  constructor(message, { status = null, kind = "api" } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.kind = kind;
  }
}

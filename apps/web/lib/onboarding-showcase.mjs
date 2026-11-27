import { graphHref } from "./operations-experience.mjs";

export function showcaseDestinations(summary, can) {
  const graph = ["assets.view", "services.view", "business_functions.view"].some(can);
  const focus = summary?.analysis_focus;
  return {
    graph: graph ? graphHref() : null,
    topology: can("assets.view") ? "/topology" : null,
    analysis: graph && focus ? graphHref({ focus, analysis: true }) : null,
  };
}

export async function finishSetup({ version, complete, read, signal }) {
  if (signal.aborted) return {};
  try {
    return { progress: await complete() };
  } catch (error) {
    if (signal.aborted) return {};
    if ([400, 401, 403, 404, 409, 422].includes(error.status)) throw error;

    // A transport or proxy error can arrive after PostgreSQL committed.
    // Observe the shared state before offering another explicit action.
    let latest;
    try {
      latest = await read();
    } catch (readError) {
      if (signal.aborted) return {};
      if (readError.status === 401) throw readError;
      throw Object.assign(new Error("Could not verify whether setup was completed. Reload progress before trying again."), { status: 409 });
    }
    if (signal.aborted) return {};
    if (latest?.status === "completed") return { latest };
    if (latest?.progress?.version !== version || !latest.can_manage) {
      throw Object.assign(new Error("Setup progress changed. Reload progress before trying again."), { status: 409 });
    }
    throw new Error("Setup is still in progress. You can try Finish setup again.");
  }
}

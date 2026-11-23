export interface PiRunPolicy {
  readonly tools?: "default" | "none";
  readonly webSearch?: "default" | "enabled" | "disabled";
  readonly webFetch?: "default" | "enabled" | "disabled";
  readonly subagent?: "default" | "disabled";
  readonly mcp?: "default" | "disabled";
  readonly skills?: "default" | "disabled";
}

/** Native Pi calls the returned factory once for each activation. */
export function definePiExtension<Api, Result>(activate: (pi: Api, policy: PiRunPolicy) => Result) {
  return (pi: Api): Result => {
    const input: unknown = JSON.parse(process.env.PI_BUNDLE_RUN_POLICY ?? "{}");
    if (typeof input !== "object" || input === null || Array.isArray(input)) {
      throw new TypeError("PI_BUNDLE_RUN_POLICY must be a JSON object");
    }
    const modes: Record<keyof PiRunPolicy, readonly string[]> = {
      tools: ["default", "none"], webSearch: ["default", "enabled", "disabled"],
      webFetch: ["default", "enabled", "disabled"], subagent: ["default", "disabled"],
      mcp: ["default", "disabled"], skills: ["default", "disabled"],
    };
    for (const [key, value] of Object.entries(input)) {
      if (!Object.hasOwn(modes, key) || !modes[key as keyof PiRunPolicy].includes(value)) {
        throw new TypeError(`Invalid PI_BUNDLE_RUN_POLICY field ${key}`);
      }
    }
    const policy = input as PiRunPolicy;
    return activate(pi, Object.freeze(policy.tools === "none"
      ? { ...policy, webSearch: "disabled", webFetch: "disabled" } : policy));
  };
}

declare namespace JSX {
  interface IntrinsicElements {
    [elemName: string]: any;
  }
}

export type HermesSDK = {
  React: {
    createElement: (...args: any[]) => any;
    Fragment: unknown;
  };
  hooks: {
    useState: <T>(initial: T) => [T, (value: T | ((current: T) => T)) => void];
    useEffect: (effect: () => void | (() => void), deps?: unknown[]) => void;
  };
  components: Record<string, (props: Record<string, unknown>) => any>;
  fetchJSON: (url: string, init?: RequestInit) => Promise<any>;
};

export type OnboardingView = {
  status?: string;
  required_remaining?: number | null;
  optional_remaining?: number | null;
  required_steps?: string[];
  optional_steps?: string[];
  error?: string | null;
};

export type LangfuseView = {
  status?: string;
  reason?: string | null;
  keys_set?: boolean;
  host_set?: boolean;
  base_url?: string | null;
  environment?: string | null;
  source?: string | null;
};

export type ToolItem = {
  name?: string;
  kind?: string;
  enabled?: boolean;
  present?: boolean;
  source?: string;
  desired?: string;
  can_install?: boolean;
  can_uninstall?: boolean;
  note?: string;
  scope?: string;
};

export type LangfuseForm = {
  open: boolean;
  publicKey: string;
  secretKey: string;
  baseUrl: string;
};

const root = window as unknown as {
  __HERMES_PLUGIN_SDK__: HermesSDK;
};

export const SDK = root.__HERMES_PLUGIN_SDK__;
export const React = SDK.React;
export const useState = SDK.hooks.useState;
export const useEffect = SDK.hooks.useEffect;
export const Card = SDK.components.Card;
export const CardHeader = SDK.components.CardHeader;
export const CardTitle = SDK.components.CardTitle;
export const CardContent = SDK.components.CardContent;
export const Button = SDK.components.Button;
export const Badge = SDK.components.Badge;
export const Input = SDK.components.Input;
export const Label = SDK.components.Label;

export const EMPTY_FORM: LangfuseForm = {
  open: false,
  publicKey: "",
  secretKey: "",
  baseUrl: "https://cloud.langfuse.com",
};

export const CHIP_ROW = {
  display: "flex",
  flexWrap: "wrap" as const,
  gap: "0.5rem",
  alignItems: "center",
};

export const STATUS_GRID = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(14rem, 1fr))",
  gap: "1rem",
};

export function badgeVariant(status?: string | null) {
  if (
    status === "healthy" ||
    status === "complete" ||
    status === "enabled" ||
    status === "installed" ||
    status === "running"
  ) {
    return "default";
  }
  if (
    status === "stopped" ||
    status === "missing" ||
    status === "unavailable" ||
    status === "disabled" ||
    status === "not installed"
  ) {
    return "secondary";
  }
  return "outline";
}

export function formatNumber(value: number | null | undefined, suffix: string) {
  if (value === null || value === undefined) {
    return "unavailable";
  }
  return `${value}${suffix}`;
}

export function formatSteps(steps: string[]) {
  return steps
    .map(function (step) {
      return step.replace(/_/g, " ");
    })
    .join(", ");
}

export function remainingCopy(view?: OnboardingView) {
  if (!view || view.error) {
    return "";
  }
  const parts: string[] = [];
  const requiredSteps = Array.isArray(view.required_steps)
    ? view.required_steps.filter(Boolean)
    : [];
  const optionalSteps = Array.isArray(view.optional_steps)
    ? view.optional_steps.filter(Boolean)
    : [];
  if (requiredSteps.length > 0) {
    parts.push("Required remaining: " + formatSteps(requiredSteps));
  } else if (typeof view.required_remaining === "number" && view.required_remaining > 0) {
    parts.push(`${view.required_remaining} required remaining`);
  }
  if (optionalSteps.length > 0) {
    parts.push("Optional remaining: " + formatSteps(optionalSteps));
  } else if (typeof view.optional_remaining === "number" && view.optional_remaining > 0) {
    parts.push(`${view.optional_remaining} optional remaining`);
  }
  return parts.join(". ");
}

export function findTool(tools: ToolItem[] | undefined, name: string) {
  return (tools || []).find(function (item) {
    return item.name === name;
  });
}

export function opencodeStatus(tools?: ToolItem[]) {
  const item = findTool(tools, "opencode");
  if (!item) {
    return "unknown";
  }
  if (!item.present) {
    return "not installed";
  }
  if (item.desired === "absent") {
    return "disabled";
  }
  return "installed";
}

export function extraPluginNames(tools: ToolItem[] | undefined, selfName: string) {
  const labels: Record<string, string> = {
    "aidee-overview": "Fleet overview",
    "aidee-onboarding": "Onboarding",
    "aidee-assistant-home": "Overview",
    "aidee-fleet": "Fleet",
  };
  return (tools || [])
    .filter(function (item) {
      return (
        item.kind === "plugin" &&
        item.name &&
        item.name !== "observability/langfuse" &&
        item.name !== selfName
      );
    })
    .map(function (item) {
      const name = item.name || "";
      if (labels[name]) {
        return labels[name];
      }
      const raw = name.split("/").pop() || "";
      return raw.replace(/-/g, " ");
    });
}

export function langfuseLabel(status?: string) {
  if (status === "enabled") {
    return "Langfuse on";
  }
  if (status === "disabled") {
    return "Langfuse off";
  }
  return "Langfuse unknown";
}

export function opencodeLabel(status?: string) {
  if (status === "installed") {
    return "OpenCode installed";
  }
  if (status === "disabled") {
    return "OpenCode off";
  }
  return "OpenCode missing";
}

export function langfuseCopy(view?: LangfuseView) {
  const status = (view && view.status) || "unknown";
  const environment = view && view.environment;
  const envCopy = environment ? ` Environment ${environment}.` : "";
  if (status === "enabled") {
    return `Tracing is on${view && view.base_url ? ` at ${view.base_url}` : ""}.${envCopy} Values live on the Hermes Keys page.`;
  }
  return (view && view.reason) || "Tracing is off until you add keys on the controller.";
}

export function langfuseInheritCopy(view?: LangfuseView) {
  const status = (view && view.status) || "unknown";
  const environment = view && view.environment;
  const envCopy = environment ? ` Environment ${environment}.` : "";
  if (status === "enabled") {
    return `Tracing is on${view && view.base_url ? ` at ${view.base_url}` : ""}.${envCopy} Values were set on the controller.`;
  }
  if (status === "unknown") {
    return (view && view.reason) || "Tracing status is unknown. Values are set on the controller.";
  }
  return `Tracing is off.${envCopy} Values are set on the controller.`;
}

export function StatusChip(props: { label: string; status?: string | null }) {
  return <Badge variant={badgeVariant(props.status)}>{props.label}</Badge>;
}

export function LangfusePanel(props: {
  title: string;
  view?: LangfuseView;
  form: LangfuseForm;
  busy: boolean;
  hostCopy?: string;
  onToggle: () => void;
  onChange: (patch: Partial<LangfuseForm>) => void;
  onSave: () => void;
  onDisable: () => void;
}) {
  const view = props.view || {};
  const status = view.status || "unknown";
  const needsSetup = status === "disabled" || status === "unknown";
  const showForm = props.form.open || needsSetup;
  const keysStay = props.hostCopy || "Values live on the Hermes Keys page.";
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="font-medium">{props.title}</div>
          <p className="text-sm text-muted-foreground">
            {status === "enabled"
              ? `Tracing is on${view.base_url ? ` at ${view.base_url}` : ""}.${view.environment ? ` Environment ${view.environment}.` : ""} ${keysStay}`
              : view.reason || "Tracing is off until you add keys. One Langfuse project covers this Aidee install."}
          </p>
        </div>
        <StatusChip label={langfuseLabel(status)} status={status} />
      </div>
      {status === "enabled" && !props.form.open ? (
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" onClick={props.onToggle} disabled={props.busy}>
            Change keys
          </Button>
          <Button type="button" variant="outline" onClick={props.onDisable} disabled={props.busy}>
            {props.busy ? "Saving" : "Turn off"}
          </Button>
        </div>
      ) : null}
      {showForm ? (
        <div className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor={`${props.title}-public`}>Public key</Label>
            <Input
              id={`${props.title}-public`}
              value={props.form.publicKey}
              autoComplete="off"
              placeholder={view.keys_set ? "Key is set. Enter a new key to replace it." : "Public key"}
              onChange={function (event: { target: { value: string } }) {
                props.onChange({ publicKey: event.target.value });
              }}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor={`${props.title}-secret`}>Secret key</Label>
            <Input
              id={`${props.title}-secret`}
              type="password"
              value={props.form.secretKey}
              autoComplete="new-password"
              placeholder={view.keys_set ? "Key is set. Enter a new key to replace it." : "Secret key"}
              onChange={function (event: { target: { value: string } }) {
                props.onChange({ secretKey: event.target.value });
              }}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor={`${props.title}-url`}>Langfuse URL</Label>
            <Input
              id={`${props.title}-url`}
              value={props.form.baseUrl}
              autoComplete="off"
              placeholder="https://cloud.langfuse.com"
              onChange={function (event: { target: { value: string } }) {
                props.onChange({ baseUrl: event.target.value });
              }}
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="button" onClick={props.onSave} disabled={props.busy}>
              {props.busy ? "Saving" : "Save and enable"}
            </Button>
            {status === "enabled" ? (
              <Button type="button" variant="outline" onClick={props.onToggle} disabled={props.busy}>
                Cancel
              </Button>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function LangfuseStatus(props: {
  title: string;
  view?: LangfuseView;
}) {
  const view = props.view || {};
  const status = view.status || "unknown";
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="font-medium">{props.title}</div>
          <p className="text-sm text-muted-foreground">{langfuseInheritCopy(view)}</p>
        </div>
        <StatusChip label={langfuseLabel(status)} status={status} />
      </div>
    </div>
  );
}

export function OpencodePanel(props: {
  tools?: ToolItem[];
  busy: boolean;
  onInstall: () => void;
  onUninstall: () => void;
}) {
  const item = findTool(props.tools, "opencode");
  const status = opencodeStatus(props.tools);
  const note =
    (item && item.note) ||
    (status === "installed"
      ? "Hermes plans and investigates, then delegates coding to OpenCode."
      : "OpenCode is not installed.");
  const imageScope = item && item.scope === "image";
  const enableLabel = imageScope || status === "disabled" ? "Enable OpenCode" : "Install OpenCode";
  const disableLabel = imageScope ? "Disable OpenCode" : "Uninstall";
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="font-medium">OpenCode</div>
          <p className="text-sm text-muted-foreground">{note}</p>
        </div>
        <StatusChip label={opencodeLabel(status)} status={status} />
      </div>
      <div className="flex flex-wrap gap-2">
        {item && item.can_install ? (
          <Button type="button" onClick={props.onInstall} disabled={props.busy}>
            {props.busy ? "Working" : enableLabel}
          </Button>
        ) : null}
        {item && item.can_uninstall ? (
          <Button type="button" variant="outline" onClick={props.onUninstall} disabled={props.busy}>
            {props.busy ? "Working" : disableLabel}
          </Button>
        ) : null}
      </div>
    </div>
  );
}

import {
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CHIP_ROW,
  EMPTY_FORM,
  extraPluginNames,
  formatNumber,
  LangfuseForm,
  LangfusePanel,
  langfuseLabel,
  OpencodePanel,
  opencodeLabel,
  opencodeStatus,
  React,
  remainingCopy,
  SDK,
  STATUS_GRID,
  StatusChip,
  ToolItem,
  useEffect,
  useState,
} from "../../../shared/dashboard-ui";

type AssistantCard = {
  id: string;
  name?: string;
  kind?: string;
  registry_status?: string;
  dashboard_url?: string | null;
  health?: {
    status?: string;
    running?: boolean;
    error?: string | null;
  };
  resources?: {
    limits?: {
      cpu_limit?: number | null;
      memory_mb?: number | null;
      pids_limit?: number | null;
    };
    usage?: {
      cpu_percent?: number | null;
      memory_mb?: number | null;
      error?: string | null;
    };
  };
  image?: {
    desired_version?: string | null;
    installed_version?: string | null;
  };
  onboarding?: {
    status?: string;
    required_remaining?: number | null;
    optional_remaining?: number | null;
    required_steps?: string[];
    optional_steps?: string[];
    error?: string | null;
  };
  langfuse?: {
    status?: string;
    reason?: string | null;
    keys_set?: boolean;
    host_set?: boolean;
    base_url?: string | null;
    environment?: string | null;
    source?: string | null;
  };
  tools?: ToolItem[];
};

type OverviewResponse = {
  host?: {
    memory?: {
      total_mb?: number;
      available_mb?: number | null;
      error?: string;
    };
    disk?: {
      total_gb?: number;
      available_gb?: number;
      path?: string;
      error?: string;
    };
    cpu_count?: number | null;
    error?: string;
  };
  release?: {
    installed?: string | null;
    desired?: string | null;
    image_version?: string | null;
    error?: string | null;
  };
  controller?: {
    onboarding?: AssistantCard["onboarding"];
    langfuse?: AssistantCard["langfuse"];
    tools?: ToolItem[];
  };
  assistants?: AssistantCard[];
  warnings?: string[];
};

const root = window as unknown as {
  __HERMES_PLUGINS__: { register: (name: string, page: unknown) => void };
};

function OverviewPage() {
  const [data, setData] = useState<OverviewResponse | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [form, setForm] = useState<LangfuseForm>(EMPTY_FORM);

  function load() {
    setError("");
    setLoading(true);
    SDK.fetchJSON("/api/plugins/aidee-overview/overview")
      .then(function (payload) {
        setData(payload || {});
      })
      .catch(function (err) {
        setError(err.message || "Could not load the fleet overview.");
      })
      .finally(function () {
        setLoading(false);
      });
  }

  useEffect(function () {
    load();
  }, []);

  function postJSON(url: string, body: Record<string, unknown>, key: string) {
    setBusy(key);
    setError("");
    setNotice("");
    return SDK.fetchJSON(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
      .then(function (result) {
        if (result && result.next_action) {
          setNotice(result.next_action);
        } else if (result && result.note) {
          setNotice(result.note);
        } else {
          setNotice("Saved.");
        }
        setForm(Object.assign({}, EMPTY_FORM, { baseUrl: form.baseUrl }));
        load();
      })
      .catch(function (err) {
        setError(err.message || "Could not save settings.");
      })
      .finally(function () {
        setBusy("");
      });
  }

  function saveLangfuse() {
    const keysSet = controller.langfuse && controller.langfuse.keys_set;
    if ((!form.publicKey || !form.secretKey) && !keysSet) {
      setError("Enter the public key and secret key before enabling Langfuse.");
      return;
    }
    const body: Record<string, unknown> = {
      enabled: true,
      base_url: form.baseUrl || "https://cloud.langfuse.com",
    };
    if (form.publicKey && form.secretKey) {
      body.public_key = form.publicKey;
      body.secret_key = form.secretKey;
    }
    postJSON("/api/plugins/aidee-overview/langfuse", body, "langfuse:controller");
  }

  function disableLangfuse() {
    postJSON("/api/plugins/aidee-overview/langfuse", { enabled: false }, "langfuse:controller");
  }

  function changeOpencode(action: "install" | "uninstall") {
    if (action === "uninstall") {
      const confirmed = window.confirm(
        "Uninstall OpenCode from the controller host and remove the coding-delegation instruction?"
      );
      if (!confirmed) {
        return;
      }
    }
    postJSON("/api/plugins/aidee-overview/opencode", { action }, "opencode:controller");
  }

  const hasData = data !== null;
  const initialLoading = loading && !hasData;
  const refreshing = loading && hasData;
  const assistants = (data && data.assistants) || [];
  const warnings = (data && data.warnings) || [];
  const host = (data && data.host) || {};
  const release = (data && data.release) || {};
  const controller = (data && data.controller) || {};
  const controllerOnboarding = controller.onboarding;
  const controllerRemaining = remainingCopy(controllerOnboarding);
  const controllerPlugins = extraPluginNames(controller.tools, "aidee-overview");
  const healthyCount = assistants.filter(function (item) {
    return item.health && (item.health.status === "healthy" || item.health.status === "running");
  }).length;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight">Fleet</h1>
          <p className="text-sm text-muted-foreground">
            Host capacity, controller health, and every assistant. Assistant settings open on that assistant's dashboard. Logins stay on the Fleet tab.
          </p>
          {hasData ? (
            <div style={CHIP_ROW}>
              <StatusChip
                label={`${assistants.length} assistant${assistants.length === 1 ? "" : "s"}`}
                status={assistants.length > 0 ? "healthy" : "missing"}
              />
              <StatusChip
                label={
                  assistants.length === 0
                    ? "No assistants"
                    : `${healthyCount} running`
                }
                status={healthyCount > 0 ? "healthy" : assistants.length > 0 ? "stopped" : "missing"}
              />
              <StatusChip
                label={
                  controller.langfuse && controller.langfuse.status === "enabled"
                    ? "Controller Langfuse on"
                    : "Controller Langfuse off"
                }
                status={(controller.langfuse && controller.langfuse.status) || "disabled"}
              />
              <StatusChip
                label={
                  opencodeStatus(controller.tools) === "installed"
                    ? "Controller OpenCode installed"
                    : "Controller OpenCode missing"
                }
                status={opencodeStatus(controller.tools)}
              />
            </div>
          ) : null}
        </div>
        <Button type="button" variant="outline" onClick={load} disabled={loading}>
          {refreshing ? "Refreshing" : "Refresh"}
        </Button>
      </div>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {notice ? <p className="text-sm text-muted-foreground">{notice}</p> : null}
      {warnings.map(function (warning) {
        return (
          <p key={warning} className="text-sm text-destructive">
            {warning}
          </p>
        );
      })}
      {initialLoading ? (
        <p className="text-sm text-muted-foreground">Loading fleet overview.</p>
      ) : null}

      {hasData ? (
        <div style={STATUS_GRID}>
          <Card>
            <CardHeader>
              <CardTitle>Host</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div>
                Memory{" "}
                {host.memory && host.memory.error
                  ? host.memory.error
                  : `${formatNumber(host.memory && host.memory.available_mb, " MB free")} of ${formatNumber(host.memory && host.memory.total_mb, " MB")}`}
              </div>
              <div>
                Disk{" "}
                {host.disk && host.disk.error
                  ? host.disk.error
                  : `${formatNumber(host.disk && host.disk.available_gb, " GB free")} of ${formatNumber(host.disk && host.disk.total_gb, " GB")}`}
              </div>
              <div>CPU {formatNumber(host.cpu_count, "")}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Release</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {release.error ? <p className="text-destructive">{release.error}</p> : null}
              <div>Installed {release.installed || "unavailable"}</div>
              <div>Desired {release.desired || "unavailable"}</div>
              <div>Image {release.image_version || "unavailable"}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <CardTitle>Controller onboarding</CardTitle>
              <StatusChip
                label={(controllerOnboarding && controllerOnboarding.status) || "unavailable"}
                status={controllerOnboarding && controllerOnboarding.status}
              />
            </CardHeader>
            <CardContent className="text-sm">
              {controllerOnboarding && controllerOnboarding.error ? (
                <p className="text-destructive">{controllerOnboarding.error}</p>
              ) : controllerRemaining ? (
                controllerRemaining
              ) : (
                <span className="text-muted-foreground">No remaining steps.</span>
              )}
            </CardContent>
          </Card>
        </div>
      ) : null}

      {hasData ? (
        <Card>
          <CardHeader>
            <CardTitle>Controller</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6 text-sm">
            {controllerPlugins.length > 0 ? (
              <p className="text-muted-foreground">
                Also enabled: {controllerPlugins.join(", ")}
              </p>
            ) : null}
            <LangfusePanel
              title="Aidee agent tracing"
              view={controller.langfuse}
              form={form}
              busy={busy === "langfuse:controller"}
              hostCopy="One Langfuse project for this install. Controller traces use environment controller. Assistants inherit the same keys with their own environment names. Values live on the Hermes Keys page."
              onToggle={function () {
                setForm(
                  Object.assign({}, form, {
                    open: !form.open,
                    baseUrl:
                      form.baseUrl ||
                      (controller.langfuse && controller.langfuse.base_url) ||
                      "https://cloud.langfuse.com",
                  })
                );
              }}
              onChange={function (patch) {
                setForm(Object.assign({}, form, patch));
              }}
              onSave={saveLangfuse}
              onDisable={disableLangfuse}
            />
            <OpencodePanel
              tools={controller.tools}
              busy={busy === "opencode:controller"}
              onInstall={function () {
                changeOpencode("install");
              }}
              onUninstall={function () {
                changeOpencode("uninstall");
              }}
            />
          </CardContent>
        </Card>
      ) : null}

      {hasData && assistants.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Assistants</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            No assistants are registered yet. Create one from Telegram after controller onboarding.
          </CardContent>
        </Card>
      ) : null}

      {hasData && assistants.length > 0 ? (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold tracking-tight">Assistants</h2>
          {assistants.map(function (assistant) {
            const health = assistant.health || {};
            const limits = (assistant.resources && assistant.resources.limits) || {};
            const usage = (assistant.resources && assistant.resources.usage) || {};
            const image = assistant.image || {};
            const plugins = extraPluginNames(assistant.tools, "aidee-overview");
            const langfuse = assistant.langfuse || {};
            const codeStatus = opencodeStatus(assistant.tools);
            return (
              <Card key={assistant.id}>
                <CardHeader className="flex flex-row items-center justify-between space-y-0">
                  <div>
                    <CardTitle>{assistant.name || assistant.id}</CardTitle>
                    <p className="text-sm text-muted-foreground">
                      {assistant.kind || "assistant"} · {assistant.id}
                    </p>
                  </div>
                  <div style={CHIP_ROW}>
                    <StatusChip label={health.status || "unknown"} status={health.status} />
                    <StatusChip
                      label={
                        langfuse.environment
                          ? `${langfuseLabel(langfuse.status)} (${langfuse.environment})`
                          : langfuseLabel(langfuse.status)
                      }
                      status={langfuse.status || "disabled"}
                    />
                    <StatusChip label={opencodeLabel(codeStatus)} status={codeStatus} />
                  </div>
                </CardHeader>
                <CardContent className="space-y-4 text-sm">
                  {health.error ? <p className="text-destructive">{health.error}</p> : null}
                  <div className="grid gap-2 md:grid-cols-3">
                    <div>
                      CPU {formatNumber(usage.cpu_percent, "%")} of{" "}
                      {formatNumber(limits.cpu_limit, " CPUs")}
                    </div>
                    <div>
                      Memory {formatNumber(usage.memory_mb, " MB")} of{" "}
                      {formatNumber(limits.memory_mb, " MB")}
                    </div>
                    <div>
                      Image {image.installed_version || "unavailable"}
                      {image.desired_version &&
                      image.desired_version !== image.installed_version
                        ? ` (desired ${image.desired_version})`
                        : ""}
                    </div>
                  </div>
                  {usage.error ? <p className="text-muted-foreground">{usage.error}</p> : null}
                  <div>
                    Onboarding{" "}
                    {(assistant.onboarding && assistant.onboarding.error) ||
                      remainingCopy(assistant.onboarding) ||
                      (assistant.onboarding && assistant.onboarding.status) ||
                      "unavailable"}
                  </div>
                  {plugins.length > 0 ? (
                    <p className="text-muted-foreground">Also enabled: {plugins.join(", ")}</p>
                  ) : null}
                  {assistant.dashboard_url ? (
                    <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-4">
                      <div>
                        <div className="font-medium">Dashboard</div>
                        <p className="text-sm text-muted-foreground">
                          Open this assistant's dashboard to change its settings.
                        </p>
                      </div>
                      <Button
                        type="button"
                        onClick={function () {
                          window.open(
                            assistant.dashboard_url as string,
                            "_blank",
                            "noopener,noreferrer"
                          );
                        }}
                      >
                        Open dashboard
                      </Button>
                    </div>
                  ) : (
                    <p className="text-muted-foreground">No dashboard URL is recorded.</p>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

root.__HERMES_PLUGINS__.register("aidee-overview", OverviewPage);

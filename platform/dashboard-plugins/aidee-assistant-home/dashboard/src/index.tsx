import {
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CHIP_ROW,
  extraPluginNames,
  LangfuseStatus,
  LangfuseView,
  OnboardingView,
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

type MemoryFile = {
  present?: boolean;
  content?: string;
  truncated?: boolean;
};

type HomeResponse = {
  profile?: {
    id?: string;
    name?: string;
    kind?: string;
    purpose?: string;
    projects?: Array<{
      id?: string;
      repositories?: Array<{ url?: string }>;
    }>;
    capabilities?: string[];
  } | null;
  profile_error?: string | null;
  user_md?: MemoryFile;
  memory_md?: MemoryFile;
  onboarding?: OnboardingView;
  langfuse?: LangfuseView;
  tools?: ToolItem[];
};

const root = window as unknown as {
  __HERMES_PLUGINS__: { register: (name: string, page: unknown) => void };
};

function MemorySection(props: { title: string; file?: MemoryFile }) {
  const file = props.file || {};
  let body = "This file is not present yet.";
  if (file.present) {
    body = file.content || "";
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>{props.title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {file.truncated ? (
          <p className="text-muted-foreground">Showing the first 64 KB only.</p>
        ) : null}
        <pre className="whitespace-pre-wrap break-words rounded-md bg-muted p-3">
          {body}
        </pre>
      </CardContent>
    </Card>
  );
}

function AssistantOverviewPage() {
  const [data, setData] = useState<HomeResponse | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");

  function load() {
    setError("");
    setLoading(true);
    SDK.fetchJSON("/api/plugins/aidee-assistant-home/home")
      .then(function (payload) {
        setData(payload || {});
      })
      .catch(function (err) {
        setError(err.message || "Could not load the assistant overview.");
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
        load();
      })
      .catch(function (err) {
        setError(err.message || "Could not save settings.");
      })
      .finally(function () {
        setBusy("");
      });
  }

  function changeOpencode(action: "install" | "uninstall") {
    if (action === "uninstall") {
      if (
        !window.confirm(
          "Turn off OpenCode for this assistant? The CLI stays in the image. Hermes will stop delegating coding to it."
        )
      ) {
        return;
      }
    }
    postJSON("/api/plugins/aidee-assistant-home/opencode", { action }, "opencode");
  }

  const hasData = data !== null;
  const initialLoading = loading && !hasData;
  const refreshing = loading && hasData;
  const profile = (data && data.profile) || null;
  const projects = (profile && profile.projects) || [];
  const capabilities = (profile && profile.capabilities) || [];
  const langfuse = (data && data.langfuse) || {};
  const langfuseStatus = langfuse.status || "unknown";
  const tools = (data && data.tools) || [];
  const codeStatus = opencodeStatus(tools);
  const plugins = extraPluginNames(tools, "aidee-assistant-home");
  const onboarding = (data && data.onboarding) || undefined;
  const onboardingRemaining = remainingCopy(onboarding);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight">
            {(profile && profile.name) || "Overview"}
          </h1>
          <p className="text-sm text-muted-foreground">
            Status, tracing, OpenCode, identity, and memories for this assistant.
            Dashboard logins stay on the controller Fleet tab.
          </p>
          {hasData ? (
            <div style={CHIP_ROW}>
              {profile && profile.kind ? (
                <StatusChip label={profile.kind} status="enabled" />
              ) : null}
              <StatusChip
                label={langfuseStatus === "enabled" ? "Langfuse on" : "Langfuse off"}
                status={langfuseStatus}
              />
              <StatusChip label={opencodeLabel(codeStatus)} status={codeStatus} />
              <StatusChip
                label={(onboarding && onboarding.status) || "onboarding unknown"}
                status={onboarding && onboarding.status}
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
      {initialLoading ? (
        <p className="text-sm text-muted-foreground">Loading assistant overview.</p>
      ) : null}

      {hasData ? (
        <div style={STATUS_GRID}>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <CardTitle>Onboarding</CardTitle>
              <StatusChip
                label={(onboarding && onboarding.status) || "unavailable"}
                status={onboarding && onboarding.status}
              />
            </CardHeader>
            <CardContent className="text-sm">
              {onboarding && onboarding.error ? (
                <p className="text-destructive">{onboarding.error}</p>
              ) : onboardingRemaining ? (
                onboardingRemaining
              ) : (
                <span className="text-muted-foreground">No remaining steps.</span>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Plugins</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              {plugins.length > 0
                ? `Also enabled: ${plugins.join(", ")}`
                : "No extra plugins are enabled."}
            </CardContent>
          </Card>
        </div>
      ) : null}

      {hasData ? (
        <Card>
          <CardHeader>
            <CardTitle>Identity</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {data && data.profile_error ? (
              <p className="text-destructive">{data.profile_error}</p>
            ) : null}
            <div>ID: {(profile && profile.id) || "unavailable"}</div>
            <div>Purpose: {(profile && profile.purpose) || "unavailable"}</div>
            <div>
              Capabilities:{" "}
              {capabilities.length > 0 ? capabilities.join(", ") : "none configured"}
            </div>
            <div>
              Projects:{" "}
              {projects.length > 0
                ? projects
                    .map(function (project) {
                      return project.id || "unnamed";
                    })
                    .join(", ")
                : "none configured"}
            </div>
            {projects.map(function (project) {
              const repositories = project.repositories || [];
              if (repositories.length === 0) {
                return null;
              }
              return (
                <div key={project.id || "project"}>
                  {project.id}:{" "}
                  {repositories
                    .map(function (repository) {
                      return repository.url;
                    })
                    .filter(Boolean)
                    .join(", ")}
                </div>
              );
            })}
          </CardContent>
        </Card>
      ) : null}

      {hasData ? (
        <Card>
          <CardHeader>
            <CardTitle>Settings</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6 text-sm">
            <LangfuseStatus title="Aidee agent tracing" view={langfuse} />
            <OpencodePanel
              tools={tools}
              busy={busy === "opencode"}
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

      {hasData ? <MemorySection title="USER.md" file={data && data.user_md} /> : null}
      {hasData ? <MemorySection title="MEMORY.md" file={data && data.memory_md} /> : null}
    </div>
  );
}

root.__HERMES_PLUGINS__.register("aidee-assistant-home", AssistantOverviewPage);

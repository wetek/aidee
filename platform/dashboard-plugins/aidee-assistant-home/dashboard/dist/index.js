(() => {
  // platform/dashboard-plugins/shared/dashboard-ui.tsx
  var root = window;
  var SDK = root.__HERMES_PLUGIN_SDK__;
  var React = SDK.React;
  var useState = SDK.hooks.useState;
  var useEffect = SDK.hooks.useEffect;
  var Card = SDK.components.Card;
  var CardHeader = SDK.components.CardHeader;
  var CardTitle = SDK.components.CardTitle;
  var CardContent = SDK.components.CardContent;
  var Button = SDK.components.Button;
  var Badge = SDK.components.Badge;
  var Input = SDK.components.Input;
  var Label = SDK.components.Label;
  var CHIP_ROW = {
    display: "flex",
    flexWrap: "wrap",
    gap: "0.5rem",
    alignItems: "center"
  };
  var STATUS_GRID = {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(14rem, 1fr))",
    gap: "1rem"
  };
  function badgeVariant(status) {
    if (status === "healthy" || status === "complete" || status === "enabled" || status === "installed" || status === "running") {
      return "default";
    }
    if (status === "stopped" || status === "missing" || status === "unavailable" || status === "disabled" || status === "not installed") {
      return "secondary";
    }
    return "outline";
  }
  function formatSteps(steps) {
    return steps.map(function(step) {
      return step.replace(/_/g, " ");
    }).join(", ");
  }
  function remainingCopy(view) {
    if (!view || view.error) {
      return "";
    }
    const parts = [];
    const requiredSteps = Array.isArray(view.required_steps) ? view.required_steps.filter(Boolean) : [];
    const optionalSteps = Array.isArray(view.optional_steps) ? view.optional_steps.filter(Boolean) : [];
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
  function findTool(tools, name) {
    return (tools || []).find(function(item) {
      return item.name === name;
    });
  }
  function opencodeStatus(tools) {
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
  function extraPluginNames(tools, selfName) {
    const labels = {
      "aidee-overview": "Fleet overview",
      "aidee-onboarding": "Onboarding",
      "aidee-assistant-home": "Overview",
      "aidee-fleet": "Fleet"
    };
    return (tools || []).filter(function(item) {
      return item.kind === "plugin" && item.name && item.name !== "observability/langfuse" && item.name !== selfName;
    }).map(function(item) {
      const name = item.name || "";
      if (labels[name]) {
        return labels[name];
      }
      const raw = name.split("/").pop() || "";
      return raw.replace(/-/g, " ");
    });
  }
  function langfuseLabel(status) {
    if (status === "enabled") {
      return "Langfuse on";
    }
    if (status === "disabled") {
      return "Langfuse off";
    }
    return "Langfuse unknown";
  }
  function opencodeLabel(status) {
    if (status === "installed") {
      return "OpenCode installed";
    }
    if (status === "disabled") {
      return "OpenCode off";
    }
    return "OpenCode missing";
  }
  function langfuseInheritCopy(view) {
    const status = view && view.status || "unknown";
    const environment = view && view.environment;
    const envCopy = environment ? ` Environment ${environment}.` : "";
    if (status === "enabled") {
      return `Tracing is on${view && view.base_url ? ` at ${view.base_url}` : ""}.${envCopy} Values were set on the controller.`;
    }
    if (status === "unknown") {
      return view && view.reason || "Tracing status is unknown. Values are set on the controller.";
    }
    return `Tracing is off.${envCopy} Values are set on the controller.`;
  }
  function StatusChip(props) {
    return /* @__PURE__ */ React.createElement(Badge, { variant: badgeVariant(props.status) }, props.label);
  }
  function LangfuseStatus(props) {
    const view = props.view || {};
    const status = view.status || "unknown";
    return /* @__PURE__ */ React.createElement("div", { className: "space-y-3" }, /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap items-center justify-between gap-2" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("div", { className: "font-medium" }, props.title), /* @__PURE__ */ React.createElement("p", { className: "text-sm text-muted-foreground" }, langfuseInheritCopy(view))), /* @__PURE__ */ React.createElement(StatusChip, { label: langfuseLabel(status), status })));
  }
  function OpencodePanel(props) {
    const item = findTool(props.tools, "opencode");
    const status = opencodeStatus(props.tools);
    const note = item && item.note || (status === "installed" ? "Hermes plans and investigates, then delegates coding to OpenCode." : "OpenCode is not installed.");
    const imageScope = item && item.scope === "image";
    const enableLabel = imageScope || status === "disabled" ? "Enable OpenCode" : "Install OpenCode";
    const disableLabel = imageScope ? "Disable OpenCode" : "Uninstall";
    return /* @__PURE__ */ React.createElement("div", { className: "space-y-3" }, /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap items-center justify-between gap-2" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("div", { className: "font-medium" }, "OpenCode"), /* @__PURE__ */ React.createElement("p", { className: "text-sm text-muted-foreground" }, note)), /* @__PURE__ */ React.createElement(StatusChip, { label: opencodeLabel(status), status })), /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-2" }, item && item.can_install ? /* @__PURE__ */ React.createElement(Button, { type: "button", onClick: props.onInstall, disabled: props.busy }, props.busy ? "Working" : enableLabel) : null, item && item.can_uninstall ? /* @__PURE__ */ React.createElement(Button, { type: "button", variant: "outline", onClick: props.onUninstall, disabled: props.busy }, props.busy ? "Working" : disableLabel) : null));
  }

  // platform/dashboard-plugins/aidee-assistant-home/dashboard/src/index.tsx
  var root2 = window;
  function MemorySection(props) {
    const file = props.file || {};
    let body = "This file is not present yet.";
    if (file.present) {
      body = file.content || "";
    }
    return /* @__PURE__ */ React.createElement(Card, null, /* @__PURE__ */ React.createElement(CardHeader, null, /* @__PURE__ */ React.createElement(CardTitle, null, props.title)), /* @__PURE__ */ React.createElement(CardContent, { className: "space-y-2 text-sm" }, file.truncated ? /* @__PURE__ */ React.createElement("p", { className: "text-muted-foreground" }, "Showing the first 64 KB only.") : null, /* @__PURE__ */ React.createElement("pre", { className: "whitespace-pre-wrap break-words rounded-md bg-muted p-3" }, body)));
  }
  function AssistantOverviewPage() {
    const [data, setData] = useState(null);
    const [error, setError] = useState("");
    const [notice, setNotice] = useState("");
    const [loading, setLoading] = useState(true);
    const [busy, setBusy] = useState("");
    function load() {
      setError("");
      setLoading(true);
      SDK.fetchJSON("/api/plugins/aidee-assistant-home/home").then(function(payload) {
        setData(payload || {});
      }).catch(function(err) {
        setError(err.message || "Could not load the assistant overview.");
      }).finally(function() {
        setLoading(false);
      });
    }
    useEffect(function() {
      load();
    }, []);
    function postJSON(url, body, key) {
      setBusy(key);
      setError("");
      setNotice("");
      return SDK.fetchJSON(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      }).then(function(result) {
        if (result && result.next_action) {
          setNotice(result.next_action);
        } else if (result && result.note) {
          setNotice(result.note);
        } else {
          setNotice("Saved.");
        }
        load();
      }).catch(function(err) {
        setError(err.message || "Could not save settings.");
      }).finally(function() {
        setBusy("");
      });
    }
    function changeOpencode(action) {
      if (action === "uninstall") {
        if (!window.confirm(
          "Turn off OpenCode for this assistant? The CLI stays in the image. Hermes will stop delegating coding to it."
        )) {
          return;
        }
      }
      postJSON("/api/plugins/aidee-assistant-home/opencode", { action }, "opencode");
    }
    const hasData = data !== null;
    const initialLoading = loading && !hasData;
    const refreshing = loading && hasData;
    const profile = data && data.profile || null;
    const projects = profile && profile.projects || [];
    const capabilities = profile && profile.capabilities || [];
    const langfuse = data && data.langfuse || {};
    const langfuseStatus = langfuse.status || "unknown";
    const tools = data && data.tools || [];
    const codeStatus = opencodeStatus(tools);
    const plugins = extraPluginNames(tools, "aidee-assistant-home");
    const onboarding = data && data.onboarding || void 0;
    const onboardingRemaining = remainingCopy(onboarding);
    return /* @__PURE__ */ React.createElement("div", { className: "space-y-6" }, /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap items-start justify-between gap-4" }, /* @__PURE__ */ React.createElement("div", { className: "space-y-2" }, /* @__PURE__ */ React.createElement("h1", { className: "text-2xl font-semibold tracking-tight" }, profile && profile.name || "Overview"), /* @__PURE__ */ React.createElement("p", { className: "text-sm text-muted-foreground" }, "Status, tracing, OpenCode, identity, and memories for this assistant. Dashboard logins stay on the controller Fleet tab."), hasData ? /* @__PURE__ */ React.createElement("div", { style: CHIP_ROW }, profile && profile.kind ? /* @__PURE__ */ React.createElement(StatusChip, { label: profile.kind, status: "enabled" }) : null, /* @__PURE__ */ React.createElement(
      StatusChip,
      {
        label: langfuseStatus === "enabled" ? "Langfuse on" : "Langfuse off",
        status: langfuseStatus
      }
    ), /* @__PURE__ */ React.createElement(StatusChip, { label: opencodeLabel(codeStatus), status: codeStatus }), /* @__PURE__ */ React.createElement(
      StatusChip,
      {
        label: onboarding && onboarding.status || "onboarding unknown",
        status: onboarding && onboarding.status
      }
    )) : null), /* @__PURE__ */ React.createElement(Button, { type: "button", variant: "outline", onClick: load, disabled: loading }, refreshing ? "Refreshing" : "Refresh")), error ? /* @__PURE__ */ React.createElement("p", { className: "text-sm text-destructive" }, error) : null, notice ? /* @__PURE__ */ React.createElement("p", { className: "text-sm text-muted-foreground" }, notice) : null, initialLoading ? /* @__PURE__ */ React.createElement("p", { className: "text-sm text-muted-foreground" }, "Loading assistant overview.") : null, hasData ? /* @__PURE__ */ React.createElement("div", { style: STATUS_GRID }, /* @__PURE__ */ React.createElement(Card, null, /* @__PURE__ */ React.createElement(CardHeader, { className: "flex flex-row items-center justify-between space-y-0" }, /* @__PURE__ */ React.createElement(CardTitle, null, "Onboarding"), /* @__PURE__ */ React.createElement(
      StatusChip,
      {
        label: onboarding && onboarding.status || "unavailable",
        status: onboarding && onboarding.status
      }
    )), /* @__PURE__ */ React.createElement(CardContent, { className: "text-sm" }, onboarding && onboarding.error ? /* @__PURE__ */ React.createElement("p", { className: "text-destructive" }, onboarding.error) : onboardingRemaining ? onboardingRemaining : /* @__PURE__ */ React.createElement("span", { className: "text-muted-foreground" }, "No remaining steps."))), /* @__PURE__ */ React.createElement(Card, null, /* @__PURE__ */ React.createElement(CardHeader, null, /* @__PURE__ */ React.createElement(CardTitle, null, "Plugins")), /* @__PURE__ */ React.createElement(CardContent, { className: "text-sm text-muted-foreground" }, plugins.length > 0 ? `Also enabled: ${plugins.join(", ")}` : "No extra plugins are enabled."))) : null, hasData ? /* @__PURE__ */ React.createElement(Card, null, /* @__PURE__ */ React.createElement(CardHeader, null, /* @__PURE__ */ React.createElement(CardTitle, null, "Identity")), /* @__PURE__ */ React.createElement(CardContent, { className: "space-y-2 text-sm" }, data && data.profile_error ? /* @__PURE__ */ React.createElement("p", { className: "text-destructive" }, data.profile_error) : null, /* @__PURE__ */ React.createElement("div", null, "ID: ", profile && profile.id || "unavailable"), /* @__PURE__ */ React.createElement("div", null, "Purpose: ", profile && profile.purpose || "unavailable"), /* @__PURE__ */ React.createElement("div", null, "Capabilities:", " ", capabilities.length > 0 ? capabilities.join(", ") : "none configured"), /* @__PURE__ */ React.createElement("div", null, "Projects:", " ", projects.length > 0 ? projects.map(function(project) {
      return project.id || "unnamed";
    }).join(", ") : "none configured"), projects.map(function(project) {
      const repositories = project.repositories || [];
      if (repositories.length === 0) {
        return null;
      }
      return /* @__PURE__ */ React.createElement("div", { key: project.id || "project" }, project.id, ":", " ", repositories.map(function(repository) {
        return repository.url;
      }).filter(Boolean).join(", "));
    }))) : null, hasData ? /* @__PURE__ */ React.createElement(Card, null, /* @__PURE__ */ React.createElement(CardHeader, null, /* @__PURE__ */ React.createElement(CardTitle, null, "Settings")), /* @__PURE__ */ React.createElement(CardContent, { className: "space-y-6 text-sm" }, /* @__PURE__ */ React.createElement(LangfuseStatus, { title: "Aidee agent tracing", view: langfuse }), /* @__PURE__ */ React.createElement(
      OpencodePanel,
      {
        tools,
        busy: busy === "opencode",
        onInstall: function() {
          changeOpencode("install");
        },
        onUninstall: function() {
          changeOpencode("uninstall");
        }
      }
    ))) : null, hasData ? /* @__PURE__ */ React.createElement(MemorySection, { title: "USER.md", file: data && data.user_md }) : null, hasData ? /* @__PURE__ */ React.createElement(MemorySection, { title: "MEMORY.md", file: data && data.memory_md }) : null);
  }
  root2.__HERMES_PLUGINS__.register("aidee-assistant-home", AssistantOverviewPage);
})();

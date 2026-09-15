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
  var EMPTY_FORM = {
    open: false,
    publicKey: "",
    secretKey: "",
    baseUrl: "https://cloud.langfuse.com"
  };
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
  function formatNumber(value, suffix) {
    if (value === null || value === void 0) {
      return "unavailable";
    }
    return `${value}${suffix}`;
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
  function StatusChip(props) {
    return /* @__PURE__ */ React.createElement(Badge, { variant: badgeVariant(props.status) }, props.label);
  }
  function LangfusePanel(props) {
    const view = props.view || {};
    const status = view.status || "unknown";
    const needsSetup = status === "disabled" || status === "unknown";
    const showForm = props.form.open || needsSetup;
    const keysStay = props.hostCopy || "Values live on the Hermes Keys page.";
    return /* @__PURE__ */ React.createElement("div", { className: "space-y-3" }, /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap items-center justify-between gap-2" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("div", { className: "font-medium" }, props.title), /* @__PURE__ */ React.createElement("p", { className: "text-sm text-muted-foreground" }, status === "enabled" ? `Tracing is on${view.base_url ? ` at ${view.base_url}` : ""}.${view.environment ? ` Environment ${view.environment}.` : ""} ${keysStay}` : view.reason || "Tracing is off until you add keys. One Langfuse project covers this Aidee install.")), /* @__PURE__ */ React.createElement(StatusChip, { label: langfuseLabel(status), status })), status === "enabled" && !props.form.open ? /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-2" }, /* @__PURE__ */ React.createElement(Button, { type: "button", variant: "outline", onClick: props.onToggle, disabled: props.busy }, "Change keys"), /* @__PURE__ */ React.createElement(Button, { type: "button", variant: "outline", onClick: props.onDisable, disabled: props.busy }, props.busy ? "Saving" : "Turn off")) : null, showForm ? /* @__PURE__ */ React.createElement("div", { className: "space-y-3" }, /* @__PURE__ */ React.createElement("div", { className: "space-y-1" }, /* @__PURE__ */ React.createElement(Label, { htmlFor: `${props.title}-public` }, "Public key"), /* @__PURE__ */ React.createElement(
      Input,
      {
        id: `${props.title}-public`,
        value: props.form.publicKey,
        autoComplete: "off",
        placeholder: view.keys_set ? "Key is set. Enter a new key to replace it." : "Public key",
        onChange: function(event) {
          props.onChange({ publicKey: event.target.value });
        }
      }
    )), /* @__PURE__ */ React.createElement("div", { className: "space-y-1" }, /* @__PURE__ */ React.createElement(Label, { htmlFor: `${props.title}-secret` }, "Secret key"), /* @__PURE__ */ React.createElement(
      Input,
      {
        id: `${props.title}-secret`,
        type: "password",
        value: props.form.secretKey,
        autoComplete: "new-password",
        placeholder: view.keys_set ? "Key is set. Enter a new key to replace it." : "Secret key",
        onChange: function(event) {
          props.onChange({ secretKey: event.target.value });
        }
      }
    )), /* @__PURE__ */ React.createElement("div", { className: "space-y-1" }, /* @__PURE__ */ React.createElement(Label, { htmlFor: `${props.title}-url` }, "Langfuse URL"), /* @__PURE__ */ React.createElement(
      Input,
      {
        id: `${props.title}-url`,
        value: props.form.baseUrl,
        autoComplete: "off",
        placeholder: "https://cloud.langfuse.com",
        onChange: function(event) {
          props.onChange({ baseUrl: event.target.value });
        }
      }
    )), /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-2" }, /* @__PURE__ */ React.createElement(Button, { type: "button", onClick: props.onSave, disabled: props.busy }, props.busy ? "Saving" : "Save and enable"), status === "enabled" ? /* @__PURE__ */ React.createElement(Button, { type: "button", variant: "outline", onClick: props.onToggle, disabled: props.busy }, "Cancel") : null)) : null);
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

  // platform/dashboard-plugins/aidee-overview/dashboard/src/index.tsx
  var root2 = window;
  function OverviewPage() {
    const [data, setData] = useState(null);
    const [error, setError] = useState("");
    const [notice, setNotice] = useState("");
    const [loading, setLoading] = useState(true);
    const [busy, setBusy] = useState("");
    const [form, setForm] = useState(EMPTY_FORM);
    function load() {
      setError("");
      setLoading(true);
      SDK.fetchJSON("/api/plugins/aidee-overview/overview").then(function(payload) {
        setData(payload || {});
      }).catch(function(err) {
        setError(err.message || "Could not load the fleet overview.");
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
        setForm(Object.assign({}, EMPTY_FORM, { baseUrl: form.baseUrl }));
        load();
      }).catch(function(err) {
        setError(err.message || "Could not save settings.");
      }).finally(function() {
        setBusy("");
      });
    }
    function saveLangfuse() {
      const keysSet = controller.langfuse && controller.langfuse.keys_set;
      if ((!form.publicKey || !form.secretKey) && !keysSet) {
        setError("Enter the public key and secret key before enabling Langfuse.");
        return;
      }
      const body = {
        enabled: true,
        base_url: form.baseUrl || "https://cloud.langfuse.com"
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
    function changeOpencode(action) {
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
    const assistants = data && data.assistants || [];
    const warnings = data && data.warnings || [];
    const host = data && data.host || {};
    const release = data && data.release || {};
    const controller = data && data.controller || {};
    const controllerOnboarding = controller.onboarding;
    const controllerRemaining = remainingCopy(controllerOnboarding);
    const controllerPlugins = extraPluginNames(controller.tools, "aidee-overview");
    const healthyCount = assistants.filter(function(item) {
      return item.health && (item.health.status === "healthy" || item.health.status === "running");
    }).length;
    return /* @__PURE__ */ React.createElement("div", { className: "space-y-6" }, /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap items-start justify-between gap-4" }, /* @__PURE__ */ React.createElement("div", { className: "space-y-2" }, /* @__PURE__ */ React.createElement("h1", { className: "text-2xl font-semibold tracking-tight" }, "Fleet"), /* @__PURE__ */ React.createElement("p", { className: "text-sm text-muted-foreground" }, "Host capacity, controller health, and every assistant. Assistant settings open on that assistant's dashboard. Logins stay on the Fleet tab."), hasData ? /* @__PURE__ */ React.createElement("div", { style: CHIP_ROW }, /* @__PURE__ */ React.createElement(
      StatusChip,
      {
        label: `${assistants.length} assistant${assistants.length === 1 ? "" : "s"}`,
        status: assistants.length > 0 ? "healthy" : "missing"
      }
    ), /* @__PURE__ */ React.createElement(
      StatusChip,
      {
        label: assistants.length === 0 ? "No assistants" : `${healthyCount} running`,
        status: healthyCount > 0 ? "healthy" : assistants.length > 0 ? "stopped" : "missing"
      }
    ), /* @__PURE__ */ React.createElement(
      StatusChip,
      {
        label: controller.langfuse && controller.langfuse.status === "enabled" ? "Controller Langfuse on" : "Controller Langfuse off",
        status: controller.langfuse && controller.langfuse.status || "disabled"
      }
    ), /* @__PURE__ */ React.createElement(
      StatusChip,
      {
        label: opencodeStatus(controller.tools) === "installed" ? "Controller OpenCode installed" : "Controller OpenCode missing",
        status: opencodeStatus(controller.tools)
      }
    )) : null), /* @__PURE__ */ React.createElement(Button, { type: "button", variant: "outline", onClick: load, disabled: loading }, refreshing ? "Refreshing" : "Refresh")), error ? /* @__PURE__ */ React.createElement("p", { className: "text-sm text-destructive" }, error) : null, notice ? /* @__PURE__ */ React.createElement("p", { className: "text-sm text-muted-foreground" }, notice) : null, warnings.map(function(warning) {
      return /* @__PURE__ */ React.createElement("p", { key: warning, className: "text-sm text-destructive" }, warning);
    }), initialLoading ? /* @__PURE__ */ React.createElement("p", { className: "text-sm text-muted-foreground" }, "Loading fleet overview.") : null, hasData ? /* @__PURE__ */ React.createElement("div", { style: STATUS_GRID }, /* @__PURE__ */ React.createElement(Card, null, /* @__PURE__ */ React.createElement(CardHeader, null, /* @__PURE__ */ React.createElement(CardTitle, null, "Host")), /* @__PURE__ */ React.createElement(CardContent, { className: "space-y-2 text-sm" }, /* @__PURE__ */ React.createElement("div", null, "Memory", " ", host.memory && host.memory.error ? host.memory.error : `${formatNumber(host.memory && host.memory.available_mb, " MB free")} of ${formatNumber(host.memory && host.memory.total_mb, " MB")}`), /* @__PURE__ */ React.createElement("div", null, "Disk", " ", host.disk && host.disk.error ? host.disk.error : `${formatNumber(host.disk && host.disk.available_gb, " GB free")} of ${formatNumber(host.disk && host.disk.total_gb, " GB")}`), /* @__PURE__ */ React.createElement("div", null, "CPU ", formatNumber(host.cpu_count, "")))), /* @__PURE__ */ React.createElement(Card, null, /* @__PURE__ */ React.createElement(CardHeader, null, /* @__PURE__ */ React.createElement(CardTitle, null, "Release")), /* @__PURE__ */ React.createElement(CardContent, { className: "space-y-2 text-sm" }, release.error ? /* @__PURE__ */ React.createElement("p", { className: "text-destructive" }, release.error) : null, /* @__PURE__ */ React.createElement("div", null, "Installed ", release.installed || "unavailable"), /* @__PURE__ */ React.createElement("div", null, "Desired ", release.desired || "unavailable"), /* @__PURE__ */ React.createElement("div", null, "Image ", release.image_version || "unavailable"))), /* @__PURE__ */ React.createElement(Card, null, /* @__PURE__ */ React.createElement(CardHeader, { className: "flex flex-row items-center justify-between space-y-0" }, /* @__PURE__ */ React.createElement(CardTitle, null, "Controller onboarding"), /* @__PURE__ */ React.createElement(
      StatusChip,
      {
        label: controllerOnboarding && controllerOnboarding.status || "unavailable",
        status: controllerOnboarding && controllerOnboarding.status
      }
    )), /* @__PURE__ */ React.createElement(CardContent, { className: "text-sm" }, controllerOnboarding && controllerOnboarding.error ? /* @__PURE__ */ React.createElement("p", { className: "text-destructive" }, controllerOnboarding.error) : controllerRemaining ? controllerRemaining : /* @__PURE__ */ React.createElement("span", { className: "text-muted-foreground" }, "No remaining steps.")))) : null, hasData ? /* @__PURE__ */ React.createElement(Card, null, /* @__PURE__ */ React.createElement(CardHeader, null, /* @__PURE__ */ React.createElement(CardTitle, null, "Controller")), /* @__PURE__ */ React.createElement(CardContent, { className: "space-y-6 text-sm" }, controllerPlugins.length > 0 ? /* @__PURE__ */ React.createElement("p", { className: "text-muted-foreground" }, "Also enabled: ", controllerPlugins.join(", ")) : null, /* @__PURE__ */ React.createElement(
      LangfusePanel,
      {
        title: "Aidee agent tracing",
        view: controller.langfuse,
        form,
        busy: busy === "langfuse:controller",
        hostCopy: "One Langfuse project for this install. Controller traces use environment controller. Assistants inherit the same keys with their own environment names. Values live on the Hermes Keys page.",
        onToggle: function() {
          setForm(
            Object.assign({}, form, {
              open: !form.open,
              baseUrl: form.baseUrl || controller.langfuse && controller.langfuse.base_url || "https://cloud.langfuse.com"
            })
          );
        },
        onChange: function(patch) {
          setForm(Object.assign({}, form, patch));
        },
        onSave: saveLangfuse,
        onDisable: disableLangfuse
      }
    ), /* @__PURE__ */ React.createElement(
      OpencodePanel,
      {
        tools: controller.tools,
        busy: busy === "opencode:controller",
        onInstall: function() {
          changeOpencode("install");
        },
        onUninstall: function() {
          changeOpencode("uninstall");
        }
      }
    ))) : null, hasData && assistants.length === 0 ? /* @__PURE__ */ React.createElement(Card, null, /* @__PURE__ */ React.createElement(CardHeader, null, /* @__PURE__ */ React.createElement(CardTitle, null, "Assistants")), /* @__PURE__ */ React.createElement(CardContent, { className: "text-sm text-muted-foreground" }, "No assistants are registered yet. Create one from Telegram after controller onboarding.")) : null, hasData && assistants.length > 0 ? /* @__PURE__ */ React.createElement("div", { className: "space-y-3" }, /* @__PURE__ */ React.createElement("h2", { className: "text-lg font-semibold tracking-tight" }, "Assistants"), assistants.map(function(assistant) {
      const health = assistant.health || {};
      const limits = assistant.resources && assistant.resources.limits || {};
      const usage = assistant.resources && assistant.resources.usage || {};
      const image = assistant.image || {};
      const plugins = extraPluginNames(assistant.tools, "aidee-overview");
      const langfuse = assistant.langfuse || {};
      const codeStatus = opencodeStatus(assistant.tools);
      return /* @__PURE__ */ React.createElement(Card, { key: assistant.id }, /* @__PURE__ */ React.createElement(CardHeader, { className: "flex flex-row items-center justify-between space-y-0" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement(CardTitle, null, assistant.name || assistant.id), /* @__PURE__ */ React.createElement("p", { className: "text-sm text-muted-foreground" }, assistant.kind || "assistant", " \xB7 ", assistant.id)), /* @__PURE__ */ React.createElement("div", { style: CHIP_ROW }, /* @__PURE__ */ React.createElement(StatusChip, { label: health.status || "unknown", status: health.status }), /* @__PURE__ */ React.createElement(
        StatusChip,
        {
          label: langfuse.environment ? `${langfuseLabel(langfuse.status)} (${langfuse.environment})` : langfuseLabel(langfuse.status),
          status: langfuse.status || "disabled"
        }
      ), /* @__PURE__ */ React.createElement(StatusChip, { label: opencodeLabel(codeStatus), status: codeStatus }))), /* @__PURE__ */ React.createElement(CardContent, { className: "space-y-4 text-sm" }, health.error ? /* @__PURE__ */ React.createElement("p", { className: "text-destructive" }, health.error) : null, /* @__PURE__ */ React.createElement("div", { className: "grid gap-2 md:grid-cols-3" }, /* @__PURE__ */ React.createElement("div", null, "CPU ", formatNumber(usage.cpu_percent, "%"), " of", " ", formatNumber(limits.cpu_limit, " CPUs")), /* @__PURE__ */ React.createElement("div", null, "Memory ", formatNumber(usage.memory_mb, " MB"), " of", " ", formatNumber(limits.memory_mb, " MB")), /* @__PURE__ */ React.createElement("div", null, "Image ", image.installed_version || "unavailable", image.desired_version && image.desired_version !== image.installed_version ? ` (desired ${image.desired_version})` : "")), usage.error ? /* @__PURE__ */ React.createElement("p", { className: "text-muted-foreground" }, usage.error) : null, /* @__PURE__ */ React.createElement("div", null, "Onboarding", " ", assistant.onboarding && assistant.onboarding.error || remainingCopy(assistant.onboarding) || assistant.onboarding && assistant.onboarding.status || "unavailable"), plugins.length > 0 ? /* @__PURE__ */ React.createElement("p", { className: "text-muted-foreground" }, "Also enabled: ", plugins.join(", ")) : null, assistant.dashboard_url ? /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap items-center justify-between gap-3 border-t pt-4" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("div", { className: "font-medium" }, "Dashboard"), /* @__PURE__ */ React.createElement("p", { className: "text-sm text-muted-foreground" }, "Open this assistant's dashboard to change its settings.")), /* @__PURE__ */ React.createElement(
        Button,
        {
          type: "button",
          onClick: function() {
            window.open(
              assistant.dashboard_url,
              "_blank",
              "noopener,noreferrer"
            );
          }
        },
        "Open dashboard"
      )) : /* @__PURE__ */ React.createElement("p", { className: "text-muted-foreground" }, "No dashboard URL is recorded.")));
    })) : null);
  }
  root2.__HERMES_PLUGINS__.register("aidee-overview", OverviewPage);
})();

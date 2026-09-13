(function () {
  const SDK = window.__HERMES_PLUGIN_SDK__;
  const React = SDK.React;
  const useState = SDK.hooks.useState;
  const useEffect = SDK.hooks.useEffect;
  const Card = SDK.components.Card;
  const CardHeader = SDK.components.CardHeader;
  const CardTitle = SDK.components.CardTitle;
  const CardContent = SDK.components.CardContent;
  const Button = SDK.components.Button;
  const Badge = SDK.components.Badge;
  const Input = SDK.components.Input;
  const Label = SDK.components.Label;

  function FleetPage() {
    const [assistants, setAssistants] = useState([]);
    const [error, setError] = useState("");
    const [busy, setBusy] = useState("");
    const [edits, setEdits] = useState({});

    function editFor(assistant) {
      return (
        edits[assistant.id] || {
          username: assistant.dashboard_username || "aidee",
          password: "",
        }
      );
    }

    function changeEdit(assistantId, patch) {
      setEdits(function (current) {
        const next = Object.assign({}, current);
        next[assistantId] = Object.assign(
          { username: "", password: "" },
          current[assistantId],
          patch
        );
        return next;
      });
    }

    function load() {
      setError("");
      SDK.fetchJSON("/api/plugins/aidee-fleet/assistants")
        .then(function (data) {
          const list = data.assistants || [];
          setAssistants(list);
          setEdits(function (current) {
            const next = Object.assign({}, current);
            list.forEach(function (assistant) {
              if (!next[assistant.id]) {
                next[assistant.id] = {
                  username: assistant.dashboard_username || "aidee",
                  password: "",
                };
              }
            });
            return next;
          });
        })
        .catch(function (err) {
          setError(err.message || "Could not load assistants.");
        });
    }

    useEffect(function () {
      load();
    }, []);

    function showPassword(assistantId) {
      setBusy("reveal:" + assistantId);
      setError("");
      SDK.fetchJSON("/api/plugins/aidee-fleet/reveal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ assistant_id: assistantId }),
      })
        .then(function (data) {
          changeEdit(assistantId, {
            username: data.dashboard_username,
            password: data.dashboard_password,
          });
        })
        .catch(function (err) {
          setError(err.message || "Could not reveal the password.");
        })
        .finally(function () {
          setBusy("");
        });
    }

    function resetPassword(assistantId) {
      if (
        !window.confirm(
          "Generate a new password for " +
            assistantId +
            "? The assistant dashboard will restart."
        )
      ) {
        return;
      }
      setBusy("reset:" + assistantId);
      setError("");
      SDK.fetchJSON("/api/plugins/aidee-fleet/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ assistant_id: assistantId }),
      })
        .then(function (data) {
          changeEdit(assistantId, {
            username: data.dashboard_username,
            password: data.dashboard_password,
          });
        })
        .catch(function (err) {
          setError(err.message || "Could not reset the password.");
        })
        .finally(function () {
          setBusy("");
        });
    }

    function saveLogin(assistantId) {
      const edit = edits[assistantId] || {};
      if (!edit.username || !edit.password) {
        setError("Enter a username and password before saving.");
        return;
      }
      if (
        !window.confirm(
          "Save this dashboard login for " +
            assistantId +
            "? The assistant dashboard will restart."
        )
      ) {
        return;
      }
      setBusy("set:" + assistantId);
      setError("");
      SDK.fetchJSON("/api/plugins/aidee-fleet/set", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          assistant_id: assistantId,
          dashboard_username: edit.username,
          dashboard_password: edit.password,
        }),
      })
        .then(function (data) {
          changeEdit(assistantId, {
            username: data.dashboard_username,
            password: data.dashboard_password,
          });
          load();
        })
        .catch(function (err) {
          setError(err.message || "Could not save the login.");
        })
        .finally(function () {
          setBusy("");
        });
    }

    return React.createElement(
      "div",
      { className: "space-y-4" },
      React.createElement(
        Card,
        null,
        React.createElement(
          CardHeader,
          null,
          React.createElement(CardTitle, null, "Fleet")
        ),
        React.createElement(
          CardContent,
          { className: "space-y-3 text-sm" },
          React.createElement(
            "p",
            { className: "text-muted-foreground" },
            "Reveal, set, or reset an assistant dashboard login here. Do not paste these passwords into Telegram."
          ),
          error
            ? React.createElement("p", { className: "text-destructive" }, error)
            : null,
          React.createElement(
            Button,
            { type: "button", variant: "outline", onClick: load },
            "Refresh"
          )
        )
      ),
      assistants.length === 0
        ? React.createElement(
            Card,
            null,
            React.createElement(
              CardContent,
              { className: "text-sm text-muted-foreground" },
              "No assistants are registered yet."
            )
          )
        : assistants.map(function (assistant) {
            const edit = editFor(assistant);
            return React.createElement(
              Card,
              { key: assistant.id },
              React.createElement(
                CardHeader,
                { className: "flex flex-row items-center justify-between space-y-0" },
                React.createElement(CardTitle, null, assistant.name || assistant.id),
                React.createElement(
                  Badge,
                  { variant: assistant.running ? "default" : "secondary" },
                  assistant.status || assistant.registry_status || "unknown"
                )
              ),
              React.createElement(
                CardContent,
                { className: "space-y-3 text-sm" },
                React.createElement("div", null, "ID: ", assistant.id),
                assistant.dashboard_url
                  ? React.createElement(
                      "a",
                      {
                        className: "text-primary underline",
                        href: assistant.dashboard_url,
                        target: "_blank",
                        rel: "noreferrer",
                      },
                      assistant.dashboard_url
                    )
                  : null,
                React.createElement(
                  "div",
                  { className: "space-y-1" },
                  React.createElement(Label, { htmlFor: "user-" + assistant.id }, "Username"),
                  React.createElement(Input, {
                    id: "user-" + assistant.id,
                    value: edit.username,
                    autoComplete: "off",
                    onChange: function (event) {
                      changeEdit(assistant.id, { username: event.target.value });
                    },
                  })
                ),
                React.createElement(
                  "div",
                  { className: "space-y-1" },
                  React.createElement(Label, { htmlFor: "pass-" + assistant.id }, "Password"),
                  React.createElement(Input, {
                    id: "pass-" + assistant.id,
                    type: "password",
                    value: edit.password,
                    autoComplete: "new-password",
                    placeholder: "Show, reset, or type a new password",
                    onChange: function (event) {
                      changeEdit(assistant.id, { password: event.target.value });
                    },
                  })
                ),
                React.createElement(
                  "div",
                  { className: "flex flex-wrap gap-2" },
                  React.createElement(
                    Button,
                    {
                      type: "button",
                      disabled: busy !== "",
                      onClick: function () {
                        saveLogin(assistant.id);
                      },
                    },
                    busy === "set:" + assistant.id ? "Saving..." : "Save login"
                  ),
                  React.createElement(
                    Button,
                    {
                      type: "button",
                      variant: "outline",
                      disabled: busy !== "",
                      onClick: function () {
                        showPassword(assistant.id);
                      },
                    },
                    busy === "reveal:" + assistant.id
                      ? "Showing..."
                      : "Show password"
                  ),
                  React.createElement(
                    Button,
                    {
                      type: "button",
                      variant: "outline",
                      disabled: busy !== "",
                      onClick: function () {
                        resetPassword(assistant.id);
                      },
                    },
                    busy === "reset:" + assistant.id ? "Resetting..." : "Reset password"
                  )
                )
              )
            );
          })
    );
  }

  window.__HERMES_PLUGINS__.register("aidee-fleet", FleetPage);
})();

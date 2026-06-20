# LSP-gh-actions

GitHub Actions workflows language server provided through [`@actions/languageserver`](https://github.com/actions/languageservices/tree/main/languageserver).

### Installation

* Install [LSP](https://packagecontrol.io/packages/LSP) and `LSP-gh-actions` from Package Control.
* Install [YamlPipelines](https://packagecontrol.io/packages/YamlPipelines) package. It provides dedicated syntaxes for GitHub workflows that this server depends on by targeting views with `source.yaml.pipeline.github-actions` scope.
* Restart Sublime.

> [!NOTE]
> Package expects the [`gh` CLI utility](https://cli.github.com/) to be available on the `PATH` to get a GitHub token from. Without it some functionality won't work.

### Configuration

If you have `LSP-yaml` installed, you don't want it running for GitHub workflows if you are using `LSP-gh-actions`. To achieve that, open `Preferences: LSP-yaml Settings` from the _Command Palette_ and modify the selector to exclude `source.yaml.pipeline.github-actions` scope. For example:

```diff
@@ -61 +61 @@
-       "selector": "(source.yml | source.yaml) - (source.yaml.go | source.yaml.helm | source.yaml.esphome)",
+       "selector": "(source.yml | source.yaml) - (source.yaml.go | source.yaml.helm | source.yaml.esphome | source.yaml.pipeline.github-actions)",
```

Open configuration file using command palette with `Preferences: LSP-gh-actions Settings` command or opening it from the Sublime menu (`Preferences > Package Settings > LSP > Servers > LSP-gh-actions`).

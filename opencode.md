# OpenCode + Azure Foundry (Anthropic Opus 4.6)

The launcher script lives at `C:\dev\opencode_foundry.ps1` so it can be
invoked from any VS Code project directory:

```powershell
pwsh -File C:\dev\opencode_foundry.ps1
```

Defaults in the script:
- Model: `azure/claude-opus-4-6`
- Resource: `bowties-dev-resource`
- Key file: `C:\dev\api.key`
- Anthropic compatibility API version: `2024-02-29-preview`

For Claude models, the script also sets:
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_BASE_URL`

This avoids the error:
`Anthropic API key is missing. Pass it using the 'apiKey' parameter or the ANTHROPIC_API_KEY environment variable.`

Optional overrides:

```powershell
pwsh -File C:\dev\opencode_foundry.ps1 -Model azure/claude-opus-4-6 -ResourceName bowties-dev-resource
```

If needed, override Anthropic compatibility API version:

```powershell
pwsh -File C:\dev\opencode_foundry.ps1 -Model azure/claude-opus-4-6 -AnthropicApiVersion 2024-02-29-preview
```




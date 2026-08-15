<!-- mcp-name: io.github.CSOAI-ORG/ai-bom-mcp -->
[![MCP Scorecard: 84/100](https://img.shields.io/badge/proofof.ai-84%2F100-5b21b6)](https://proofof.ai/scorecard/ai-bom-mcp.html)

# Ai Bom MCP

[![MEOK AI Labs](https://img.shields.io/badge/MEOK-AI%20Labs-667eea)](https://meok.ai)
[![EU AI Act](https://img.shields.io/badge/EU%20AI%20Act-Compliant-22c55e)](https://councilof.ai)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![PyPI](https://img.shields.io/badge/PyPI-Install-3775a9)](https://pypi.org/project/ai_bom_mcp/)

> AI Bill of Materials MCP in CycloneDX + SPDX format

AI Bill of Materials MCP in CycloneDX + SPDX format. Required by EU AI Act Article 11. MIT

---

## 🚀 Quick Start

```bash
# Install via pip
pip install ai_bom_mcp

# Or install via Smithery
npx -y @smithery/cli@latest install ai-bom-mcp --client claude
```

## ✨ Features

- MCP protocol compliant
- Easy installation
- Well-documented API
- Production-ready
- Active maintenance

## 📖 Documentation

- [Full Documentation](https://docs.meok.ai/ai-bom-mcp)
- [API Reference](https://meok-attestation-api.vercel.app)
- [EU AI Act Compliance Guide](https://councilof.ai)

## 🛡️ Compliance

This MCP server is built with **EU AI Act compliance** built-in:

- ✅ Article 9 — Risk Management System
- ✅ Article 13 — Transparency & Instructions for Use
- ✅ Article 15 — Bias Detection & Testing
- ✅ Article 26 — FRIA Support (where applicable)
- ✅ Article 50 — AI Content Watermarking (where applicable)

Need help getting compliant? **[Book a free 15-min diagnostic →](mailto:nicholas@meok.ai?subject=Compliance%20diagnostic)**

## 🏢 Enterprise

Need custom development, SLA guarantees, or white-label deployment?

- **Pro:** £79/mo — Full MCP suite + EU AI Act tracking
- **Enterprise:** £499/mo — Custom dev + SLA + Dedicated support

[View Pricing →](https://councilof.ai/payg) | [Contact Sales →](mailto:sales@meok.ai)

## 🤝 Part of the MEOK Ecosystem

This server is part of the **[MEOK AI Labs](https://meok.ai)** ecosystem — a governed MCP fleet · ~16,300 monthly installs.

| Domain | Purpose |
|--------|---------|
| [councilof.ai](https://councilof.ai) | EU AI Act compliance marketplace |
| [safetyof.ai](https://safetyof.ai) | AI safety & monitoring |
| [meok.ai](https://meok.ai) | Sovereign AI platform |
| [cobolbridge.ai](https://cobolbridge.ai) | Legacy modernization |

## 📜 License

MIT © [CSOAI-ORG](https://github.com/CSOAI-ORG)

---

<p align="center">
  <sub>Built with 💜 by <a href="https://meok.ai">MEOK AI Labs</a> · UK Companies House 16939677</sub>
</p>


## Configuration

Add to your `claude_desktop_config.json` (Claude Desktop) or your MCP client config:

```json
{
  "mcpServers": {
    "ai-bom-mcp": {
      "command": "uvx",
      "args": ["ai-bom-mcp"]
    }
  }
}
```

Or: `pip install ai-bom-mcp` then run the `ai-bom-mcp` command (stdio transport).

## Examples

Once configured, ask your assistant, for example:
- "Use `generate_ai_bom` to …"
- "Use `audit_ai_bom_completeness` to …"
- "Use `map_to_regulation` to …"

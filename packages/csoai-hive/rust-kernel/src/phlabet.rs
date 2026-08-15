//! Phlabet — 256 primal symbols that compress infinite knowledge.
//!
//! Per memory: "Phlabet: Symbolic Compression — 256 primal symbols."
//! Per memory: "Natural language is bloated. Phlabet: [Scales(255) → Web(200) → Eye(180) → Lock(150)]
//!   = 4 glyphs, 1KB, captures the entire concept. The GNN spine operates on glyphs, not words.
//!   1000x faster reasoning."

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

/// The 256 primal phonemes — the alphabet of the sovereign mind.
#[repr(u8)]
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Phoneme {
    // G-Axis (Governance) 0x00-0x0F
    Scales = 0x00,      // ⚖️ governance, balance, justice, regulation, compliance
    Crown = 0x01,       // 👑 authority, decision, finality, sovereign, mandate
    Web = 0x02,         // 🕸️ network, connection, protocol, harness, agent
    Scroll = 0x03,      // 📜 law, regulation, codified, article, provision, act
    Bridge = 0x04,      // 🌉 cross-jurisdiction, equivalence, interoperability
    Parliament = 0x05,  // 🏛️ council, assembly, vote, deliberation
    Chain = 0x06,       // ⛓️ blockchain, hash, verification, tamper-evidence
    Oracle = 0x07,      // 🔮 prediction, forecast, simulation, dream
    Charter = 0x08,     // 📋 constitution, principles, immutable rules
    Verdict = 0x09,     // ⚖️ judgment, outcome, pass/fail, compliance

    // S-Axis (Security) 0x10-0x1F
    Shield = 0x10,      // 🛡️ defense, protection, encryption, security
    Eye = 0x11,         // 👁️ surveillance, detection, audit, monitoring
    Serpent = 0x12,     // 🐍 threat, vulnerability, poison, attack
    Wall = 0x13,        // 🧱 boundary, firewall, perimeter, guard
    Key = 0x14,         // 🔑 access, authentication, authorization, credential
    Fortress = 0x15,    // 🏰 castle, stronghold, defense-in-depth
    Radar = 0x16,       // 📡 detection, signal, WiFi CSI, perception
    Sentinel = 0x17,    // 🗿 watchdog, guardian, always-on observer
    Trap = 0x18,        // 🪤 honeypot, decoy, adversarial lure
    Vault = 0x19,       // 🏦 secure storage, cold wallet, deep archive

    // P-Axis (Privacy) 0x20-0x2F
    Lock = 0x20,        // 🔒 privacy, secret, encryption, sovereignty, private
    Mask = 0x21,        // 🎭 anonymity, identity, persona, obfuscation
    Veil = 0x22,        // 🌫️ obfuscation, zero-knowledge, hidden
    Mirror = 0x23,      // 🪞 reflection, self-audit, introspection, review
    Seed = 0x24,        // 🌱 genesis, origin, root, trust, foundation
    Shadow = 0x25,      // 👤 unknown, untracked, dark matter
    Whisper = 0x26,     // 🤫 quiet, private, encrypted channel
    Fog = 0x27,         // 🌁 ambiguity, uncertainty, incomplete data
    Pearl = 0x28,       // 🦪 hidden value, inner beauty, compressed knowledge
    Cocoon = 0x29,      // 🐛 transformation, metamorphosis, growth phase

    // C-Axis (Commerce) 0x30-0x3F
    Coin = 0x30,        // 🪙 value, transaction, exchange, commerce, revenue
    Horn = 0x31,        // 📯 growth, abundance, harvest, market, expand
    Flame = 0x32,       // 🔥 energy, compute, burn, training, inference
    Wheel = 0x33,       // ⚙️ mechanism, process, workflow, pipeline, system
    Market = 0x34,      // 🏪 marketplace, supply, demand, economy
    Ship = 0x35,        // 🚢 transport, delivery, logistics, movement
    Hammer = 0x36,      // 🔨 build, create, construct, manufacture
    Scale = 0x37,       // ⚖️ measurement, metrics, KPI, benchmark
    River = 0x38,       // 🌊 flow, stream, data pipeline, continuous
    Beacon = 0x39,      // 🗼 signal, visibility, brand, awareness

    // Meta 0xF0-0xFF
    Dragon = 0xF0,      // 🐉 SOV itself, the unified mind
    Atom = 0xF1,        // ⚛️ indivisible, truth, quantum, state
    Void = 0xF2,        // 🌑 potential, unformed, genesis, begin
    Spine = 0xF3,       // 🦴 structure, reasoning, core, GNN, brain
    Honey = 0xF4,       // 🍯 knowledge, output, training, data, create
    Dream = 0xF5,       // 💭 simulation, imagination, prediction
    Drum = 0xF6,        // 🥁 heartbeat, rhythm, continuous cycle
    Rainbow = 0xF7,     // 🌈 multi-spectrum, 7-layer security
    Fractal = 0xF8,     // 🌀 self-similar, recursive, infinite zoom
    Hive = 0xF9,        // 🐝 collective, swarm, emergent behavior
    CrownJewel = 0xFA,  // 💎 crown jewel, most valuable asset
    BlackSwan = 0xFB,   // 🦢 unknown risk, tail event, paradigm shift
    Phoenix = 0xFC,     // 🔥 rebirth, recovery, resilience
    Compass = 0xFD,     // 🧭 direction, orientation, GSPC axes
    Infinity = 0xFE,    // ♾️ unbounded, infinite, fractal
    Genesis = 0xFF,     // 🌅 origin, start, the beginning
}

/// A single Phlabet glyph — 326 bytes (2 header + 64×f32 vector + 64 provenance pad + f32 confidence).
#[derive(Debug, Clone)]
pub struct Glyph {
    pub phoneme: u8,
    pub intensity: u8,           // 0-255, how strong
    pub vector: [f32; 64],       // 64-dim semantic embedding
    pub provenance: String,      // Which epoch/agent created this
    pub confidence: f32,         // 0.0-1.0, certainty
}

// Manual Serialize/Deserialize — serde 1.0 has limited [T; N] support for large N
impl serde::Serialize for Glyph {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where S: serde::Serializer {
        use serde::ser::SerializeStruct;
        let mut state = serializer.serialize_struct("Glyph", 5)?;
        state.serialize_field("phoneme", &self.phoneme)?;
        state.serialize_field("intensity", &self.intensity)?;
        state.serialize_field("vector", &self.vector.to_vec())?;
        state.serialize_field("provenance", &self.provenance)?;
        state.serialize_field("confidence", &self.confidence)?;
        state.end()
    }
}

impl<'de> serde::Deserialize<'de> for Glyph {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where D: serde::Deserializer<'de> {
        use serde::de::{self, MapAccess, Visitor};
        use std::fmt;

        struct GlyphVisitor;
        impl<'de> Visitor<'de> for GlyphVisitor {
            type Value = Glyph;
            fn expecting(&self, f: &mut fmt::Formatter) -> fmt::Result {
                f.write_str("Glyph")
            }
            fn visit_map<M>(self, mut map: M) -> Result<Glyph, M::Error>
            where M: MapAccess<'de> {
                let mut phoneme = 0u8;
                let mut intensity = 0u8;
                let mut vector = [0.0f32; 64];
                let mut provenance = String::new();
                let mut confidence = 1.0f32;
                while let Some(key) = map.next_key::<String>()? {
                    match key.as_str() {
                        "phoneme" => { phoneme = map.next_value()?; }
                        "intensity" => { intensity = map.next_value()?; }
                        "vector" => {
                            let v: Vec<f32> = map.next_value()?;
                            for (i, val) in v.into_iter().enumerate() {
                                if i < 64 { vector[i] = val; }
                            }
                        }
                        "provenance" => { provenance = map.next_value()?; }
                        "confidence" => { confidence = map.next_value()?; }
                        _ => { let _: de::IgnoredAny = map.next_value()?; }
                    }
                }
                Ok(Glyph { phoneme, intensity, vector, provenance, confidence })
            }
        }
        deserializer.deserialize_map(GlyphVisitor)
    }
}

impl std::fmt::Display for Glyph {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let name = match self.phoneme {
            0x00 => "⚖️ scales",
            0x01 => "👑 crown",
            0x02 => "🕸️ web",
            0x03 => "📜 scroll",
            0x04 => "🌉 bridge",
            0x10 => "🛡️ shield",
            0x11 => "👁️ eye",
            0x12 => "🐍 serpent",
            0x20 => "🔒 lock",
            0x21 => "🎭 mask",
            0x30 => "🪙 coin",
            0x31 => "📯 horn",
            0x32 => "🔥 flame",
            0x33 => "⚙️ wheel",
            0xF0 => "🐉 dragon",
            0xF3 => "🦴 spine",
            0xF4 => "🍯 honey",
            0xF5 => "💭 dream",
            0xF7 => "🌈 rainbow",
            0xF8 => "🌀 fractal",
            0xF9 => "🐝 hive",
            _ => "? unknown",
        };
        write!(f, "{} i={}", name, self.intensity)
    }
}

impl Glyph {
    pub fn new(phoneme: u8, intensity: u8, provenance: &str, confidence: f32) -> Self {
        Self {
            phoneme,
            intensity,
            vector: [0.0; 64],
            provenance: provenance.to_string(),
            confidence,
        }
    }

    /// Compact to 326 bytes.
    pub fn to_bytes(&self) -> Vec<u8> {
        let mut buf = Vec::with_capacity(273);
        buf.push(self.phoneme);
        buf.push(self.intensity);
        for &v in &self.vector {
            buf.extend_from_slice(&v.to_le_bytes());
        }
        let prov_bytes = self.provenance.as_bytes();
        let mut prov_padded = [0u8; 64];
        let copy_len = prov_bytes.len().min(64);
        prov_padded[..copy_len].copy_from_slice(&prov_bytes[..copy_len]);
        buf.extend_from_slice(&prov_padded);
        buf.extend_from_slice(&self.confidence.to_le_bytes());
        buf
    }

    pub fn from_bytes(data: &[u8]) -> Self {
        let phoneme = data[0];
        let intensity = data[1];
        let mut vector = [0.0f32; 64];
        for i in 0..64 {
            let offset = 2 + i * 4;
            vector[i] = f32::from_le_bytes([
                data[offset], data[offset+1], data[offset+2], data[offset+3],
            ]);
        }
        let prov_bytes = &data[258..322];
        let provenance = String::from_utf8_lossy(prov_bytes).trim_end_matches('\0').to_string();
        let confidence = f32::from_le_bytes([data[322], data[323], data[324], data[325]]);
        Self { phoneme, intensity, vector, provenance, confidence }
    }

    /// SHA256 hash of the glyph.
    pub fn hash(&self) -> [u8; 32] {
        let mut hasher = Sha256::new();
        hasher.update(&self.to_bytes());
        hasher.finalize().into()
    }
}

/// Compress natural language into Phlabet glyphs.
pub fn compress_to_phlabet(text: &str, provenance: &str) -> Vec<Glyph> {
    let words: Vec<&str> = text.split_whitespace().collect();
    let mut matched: Vec<u8> = Vec::new();

    let phoneme_keywords: Vec<(u8, Vec<&str>)> = vec![
        (0x00, vec!["governance", "balance", "justice", "regulation", "compliance"]),
        (0x01, vec!["authority", "decision", "sovereign", "mandate"]),
        (0x02, vec!["network", "connection", "protocol", "harness", "agent"]),
        (0x03, vec!["law", "regulation", "article", "provision", "act"]),
        (0x04, vec!["cross-jurisdiction", "equivalence", "interop"]),
        (0x10, vec!["defense", "protection", "encryption", "security"]),
        (0x11, vec!["surveillance", "detection", "audit", "monitoring"]),
        (0x12, vec!["threat", "vulnerability", "attack"]),
        (0x13, vec!["boundary", "firewall", "perimeter"]),
        (0x14, vec!["access", "authentication", "credential"]),
        (0x16, vec!["detection", "signal", "wifi", "perception"]),
        (0x17, vec!["watchdog", "guardian", "observer"]),
        (0x20, vec!["privacy", "secret", "encryption", "private"]),
        (0x21, vec!["anonymity", "identity", "persona"]),
        (0x22, vec!["zero-knowledge", "hidden"]),
        (0x24, vec!["genesis", "origin", "root", "trust", "foundation"]),
        (0x30, vec!["value", "transaction", "commerce", "revenue"]),
        (0x31, vec!["growth", "abundance", "harvest", "market"]),
        (0x32, vec!["energy", "compute", "burn", "training", "inference"]),
        (0x33, vec!["mechanism", "process", "workflow", "pipeline"]),
        (0xF0, vec!["sov", "sovereign", "mind", "unified"]),
        (0xF3, vec!["structure", "reasoning", "core", "gnn", "brain"]),
        (0xF4, vec!["knowledge", "output", "training", "data", "create"]),
        (0xF5, vec!["simulation", "imagination", "prediction", "dream"]),
        (0xF7, vec!["multi-spectrum", "rainbow", "defense"]),
        (0xF8, vec!["self-similar", "recursive", "fractal"]),
        (0xF9, vec!["collective", "swarm", "hive"]),
    ];

    for word in &words {
        let w = word.to_lowercase();
        for (phoneme, keywords) in &phoneme_keywords {
            for kw in keywords {
                if w.contains(kw) || kw.contains(&*w) {
                    matched.push(*phoneme);
                    break;
                }
            }
        }
    }

    matched.sort();
    matched.dedup();

    if matched.is_empty() {
        matched.push(0xF2); // Void
    }

    matched.into_iter().map(|p| {
        Glyph::new(p, 200, provenance, 1.0)
    }).collect()
}

/// Decode glyphs back to readable text.
pub fn glyphs_to_text(glyphs: &[Glyph]) -> String {
    let names: Vec<&str> = glyphs.iter().map(|g| match g.phoneme {
        0x00 => "⚖️ scales",
        0x01 => "👑 crown",
        0x02 => "🕸️ web",
        0x03 => "📜 scroll",
        0x04 => "🌉 bridge",
        0x10 => "🛡️ shield",
        0x11 => "👁️ eye",
        0x12 => "🐍 serpent",
        0x20 => "🔒 lock",
        0x21 => "🎭 mask",
        0x30 => "🪙 coin",
        0x31 => "📯 horn",
        0x32 => "🔥 flame",
        0x33 => "⚙️ wheel",
        0xF0 => "🐉 dragon",
        0xF3 => "🦴 spine",
        0xF4 => "🍯 honey",
        0xF5 => "💭 dream",
        0xF7 => "🌈 rainbow",
        0xF8 => "🌀 fractal",
        0xF9 => "🐝 hive",
        _ => "? unknown",
    }).collect();
    names.join(" → ")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_glyph_roundtrip() {
        let g = Glyph::new(0x00, 200, "test_prov", 0.95);
        let bytes = g.to_bytes();
        assert_eq!(bytes.len(), 326);
        let g2 = Glyph::from_bytes(&bytes);
        assert_eq!(g2.phoneme, 0x00);
        assert_eq!(g2.intensity, 200);
    }

    #[test]
    fn test_compress() {
        let glyphs = compress_to_phlabet(
            "EU AI Act Article 50 requires governance compliance audit",
            "test"
        );
        assert!(!glyphs.is_empty());
        assert!(glyphs.iter().any(|g| g.phoneme != 0xF2)); // not all void
    }

    #[test]
    fn test_glyphs_to_text() {
        let glyphs = vec![Glyph::new(0x00, 200, "", 1.0), Glyph::new(0x03, 200, "", 1.0)];
        let text = glyphs_to_text(&glyphs);
        assert!(text.contains("scales"));
        assert!(text.contains("scroll"));
    }
}

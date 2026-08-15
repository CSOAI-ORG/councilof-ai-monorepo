//! J-Space Cards — Symbolic knowledge tarot.
//!
//! Per memory: "J-Space Cards = symbolic knowledge tarot — archetype compression (your Phlabet)."
//! Per memory: "Layer-2 = J-SPACE (honey-signed decisions, orange ring with denser dots)."
//!
//! Each card is a compressed archetype that triggers reasoning patterns in the Spine.
//! 4 suits × 13 ranks = 52 base cards + 4 GSPC axis cards + 4 meta cards = 60 total.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

/// The 4 GSPC suits.
#[repr(u8)]
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum JSuit {
    Scales = 0,  // G — Governance, law, regulation
    Shield = 1,  // S — Security, defense, audit
    Lock = 2,    // P — Privacy, encryption, sovereignty
    Horn = 3,    // C — Commerce, growth, abundance
}

impl JSuit {
    pub fn color(&self) -> (u8, u8, u8, u8) {
        match self {
            JSuit::Scales => (47, 129, 247, 255),   // Blue
            JSuit::Shield => (248, 81, 73, 255),     // Red
            JSuit::Lock => (52, 199, 89, 255),       // Green
            JSuit::Horn => (255, 199, 44, 255),      // Gold
        }
    }

    pub fn axis_name(&self) -> &str {
        match self {
            JSuit::Scales => "Governance",
            JSuit::Shield => "Security",
            JSuit::Lock => "Privacy",
            JSuit::Horn => "Commerce",
        }
    }
}

/// Ranks: Ace through King (1-13), plus special cards.
#[repr(u8)]
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum JRank {
    Ace = 1,
    Two = 2,
    Three = 3,
    Four = 4,
    Five = 5,
    Six = 6,
    Seven = 7,
    Eight = 8,
    Nine = 9,
    Ten = 10,
    Jack = 11,    // Agent / Worker
    Queen = 12,   // Governance / Policy
    King = 13,    // Sovereign / Final authority
}

/// A J-Space Card — the symbolic knowledge tarot.
#[derive(Debug, Clone)]
pub struct JSpaceCard {
    pub id: u64,
    pub suit: JSuit,
    pub rank: u8,                // 1-13
    pub name: String,            // e.g. "Ace of Scales — The First Law"
    pub glyph: [u8; 64],        // 64-byte Phlabet embedding
    pub description: String,     // What this card means
    pub activation: CardEffect,  // What happens when drawn
    pub provenance: String,      // Who/what created this card
    pub confidence: f32,         // 0.0-1.0
}

// Manual Serialize/Deserialize — serde 1.0 has limited [T; N] support for large N
impl serde::Serialize for JSpaceCard {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where S: serde::Serializer {
        use serde::ser::SerializeStruct;
        let mut state = serializer.serialize_struct("JSpaceCard", 8)?;
        state.serialize_field("id", &self.id)?;
        state.serialize_field("suit", &self.suit)?;
        state.serialize_field("rank", &self.rank)?;
        state.serialize_field("name", &self.name)?;
        state.serialize_field("glyph", &self.glyph.to_vec())?;
        state.serialize_field("description", &self.description)?;
        state.serialize_field("activation", &self.activation)?;
        state.serialize_field("provenance", &self.provenance)?;
        state.serialize_field("confidence", &self.confidence)?;
        state.end()
    }
}

impl<'de> serde::Deserialize<'de> for JSpaceCard {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where D: serde::Deserializer<'de> {
        use serde::de::{self, MapAccess, Visitor};
        use std::fmt;

        struct JSpaceCardVisitor;
        impl<'de> Visitor<'de> for JSpaceCardVisitor {
            type Value = JSpaceCard;
            fn expecting(&self, f: &mut fmt::Formatter) -> fmt::Result {
                f.write_str("JSpaceCard")
            }
            fn visit_map<M>(self, mut map: M) -> Result<JSpaceCard, M::Error>
            where M: MapAccess<'de> {
                let mut id = 0u64;
                let mut suit = JSuit::Scales;
                let mut rank = 0u8;
                let mut name = String::new();
                let mut glyph = [0u8; 64];
                let mut description = String::new();
                let mut activation = CardEffect::None;
                let mut provenance = String::new();
                let mut confidence = 1.0f32;
                while let Some(key) = map.next_key::<String>()? {
                    match key.as_str() {
                        "id" => { id = map.next_value()?; }
                        "suit" => { suit = map.next_value()?; }
                        "rank" => { rank = map.next_value()?; }
                        "name" => { name = map.next_value()?; }
                        "glyph" => {
                            let v: Vec<u8> = map.next_value()?;
                            for (i, val) in v.into_iter().enumerate() {
                                if i < 64 { glyph[i] = val; }
                            }
                        }
                        "description" => { description = map.next_value()?; }
                        "activation" => { activation = map.next_value()?; }
                        "provenance" => { provenance = map.next_value()?; }
                        "confidence" => { confidence = map.next_value()?; }
                        _ => { let _: de::IgnoredAny = map.next_value()?; }
                    }
                }
                Ok(JSpaceCard { id, suit, rank, name, glyph, description, activation, provenance, confidence })
            }
        }
        deserializer.deserialize_map(JSpaceCardVisitor)
    }
}

impl Default for JSpaceCard {
    fn default() -> Self {
        Self {
            id: 0, suit: JSuit::Scales, rank: 0, name: String::new(),
            glyph: [0u8; 64], description: String::new(), activation: CardEffect::None,
            provenance: String::new(), confidence: 1.0,
        }
    }
}

/// What a card does when activated.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CardEffect {
    /// Redirect reasoning to a specific axis
    AxisFocus { axis: JSuit, weight: f32 },
    /// Trigger a governance check
    GovernanceCheck { policy_id: String },
    /// Initiate a security scan
    SecurityScan { target: String },
    /// Generate new honey (training data)
    HoneyGenerate { task_type: String },
    /// Dream: simulate a scenario
    Dream { scenario: String },
    /// Meta-cognition: select best model for task
    MetaRoute { task_type: String },
    /// No effect (placeholder)
    None,
}

impl JSpaceCard {
    /// Create a new card.
    pub fn new(suit: JSuit, rank: u8, name: &str, description: &str, effect: CardEffect) -> Self {
        let mut hasher = Sha256::new();
        hasher.update(&[suit as u8, rank]);
        hasher.update(name.as_bytes());
        let hash: [u8; 32] = hasher.finalize().into();
        let id = u64::from_le_bytes(hash[0..8].try_into().unwrap());

        let mut glyph = [0u8; 64];
        glyph[0] = suit as u8;
        glyph[1] = rank;

        Self {
            id,
            suit,
            rank,
            name: name.to_string(),
            glyph,
            description: description.to_string(),
            activation: effect,
            provenance: String::new(),
            confidence: 1.0,
        }
    }

    /// SHA256 hash of the card.
    pub fn hash(&self) -> [u8; 32] {
        let mut hasher = Sha256::new();
        hasher.update(&self.id.to_le_bytes());
        hasher.update(&[self.suit as u8, self.rank]);
        hasher.update(self.name.as_bytes());
        hasher.finalize().into()
    }

    /// Is this a face card (Jack, Queen, King)?
    pub fn is_face(&self) -> bool {
        self.rank >= 11
    }
}

/// The full deck: 52 base + 4 axis + 4 meta = 60 cards.
pub fn create_deck() -> Vec<JSpaceCard> {
    let mut deck = Vec::with_capacity(60);

    let suits = [JSuit::Scales, JSuit::Shield, JSuit::Lock, JSuit::Horn];
    let rank_names: Vec<(&str, &str)> = vec![
        ("Ace", "The First Principle"),
        ("Two", "The Pair"),
        ("Three", "The Triad"),
        ("Four", "The Foundation"),
        ("Five", "The Test"),
        ("Six", "The Harmony"),
        ("Seven", "The Challenge"),
        ("Eight", "The Cycle"),
        ("Nine", "The Threshold"),
        ("Ten", "The Completion"),
        ("Jack", "The Agent"),
        ("Queen", "The Guardian"),
        ("King", "The Sovereign"),
    ];

    // 52 base cards
    for suit in &suits {
        for (rank_idx, (rank_name, suffix)) in rank_names.iter().enumerate() {
            let rank = (rank_idx + 1) as u8;
            let name = format!("{} of {}s — {}", rank_name, suit.axis_name(), suffix);
            let desc = format!("{}: {} of the {} axis.", rank_name, suffix, suit.axis_name());
            let effect = match rank {
                1 => CardEffect::AxisFocus { axis: *suit, weight: 2.0 },
                11 => CardEffect::MetaRoute { task_type: suit.axis_name().to_lowercase() },
                12 => CardEffect::GovernanceCheck { policy_id: format!("{}-Q", suit.axis_name()) },
                13 => CardEffect::HoneyGenerate { task_type: suit.axis_name().to_lowercase() },
                _ => CardEffect::None,
            };
            deck.push(JSpaceCard::new(*suit, rank, &name, &desc, effect));
        }
    }

    // 4 GSPC axis cards (special)
    deck.push(JSpaceCard::new(JSuit::Scales, 0, "The GSPC Compass — Governance",
        "The north axis. All compliance flows from here.",
        CardEffect::AxisFocus { axis: JSuit::Scales, weight: 5.0 }));
    deck.push(JSpaceCard::new(JSuit::Shield, 0, "The GSPC Compass — Security",
        "The east axis. Defense-in-depth.",
        CardEffect::SecurityScan { target: "all".to_string() }));
    deck.push(JSpaceCard::new(JSuit::Lock, 0, "The GSPC Compass — Privacy",
        "The south axis. Sovereignty of data.",
        CardEffect::AxisFocus { axis: JSuit::Lock, weight: 5.0 }));
    deck.push(JSpaceCard::new(JSuit::Horn, 0, "The GSPC Compass — Commerce",
        "The west axis. Value creation.",
        CardEffect::AxisFocus { axis: JSuit::Horn, weight: 5.0 }));

    // 4 meta cards
    deck.push(JSpaceCard::new(JSuit::Scales, 14, "The Dragon",
        "SOV itself. The unified mind.",
        CardEffect::Dream { scenario: "full_ecosystem".to_string() }));
    deck.push(JSpaceCard::new(JSuit::Shield, 14, "The Black Swan",
        "Unknown risk. The tail event that changes everything.",
        CardEffect::SecurityScan { target: "unknown".to_string() }));
    deck.push(JSpaceCard::new(JSuit::Lock, 14, "The Phoenix",
        "Rebirth from failure. Learning from refutations.",
        CardEffect::HoneyGenerate { task_type: "refutation".to_string() }));
    deck.push(JSpaceCard::new(JSuit::Horn, 14, "The Genesis",
        "The beginning. Where all honey starts.",
        CardEffect::HoneyGenerate { task_type: "genesis".to_string() }));

    deck
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_deck_size() {
        let deck = create_deck();
        assert_eq!(deck.len(), 60);
    }

    #[test]
    fn test_card_hash() {
        let card = JSpaceCard::new(JSuit::Scales, 1, "Test", "Test card", CardEffect::None);
        let hash = card.hash();
        assert_eq!(hash.len(), 32);
    }

    #[test]
    fn test_suit_colors() {
        assert_eq!(JSuit::Scales.color(), (47, 129, 247, 255));
        assert_eq!(JSuit::Shield.color(), (248, 81, 73, 255));
    }
}

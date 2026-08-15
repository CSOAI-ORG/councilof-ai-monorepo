//! SOVOS Fractal Monotric Hive
//!
//! Ring-0 AI governance kernel. Every node is a fractal cell — same structure
//! at every scale: token, agent, clan, cluster, ecosystem.
//!
//! Architecture:
//!   Phlabet (256 symbols) → Spine (GNN reasoning) → Honey Generator → IWM → VWM
//!
//! Per memory: "Ring 0 = Layer 0 = The Monad = The One."
//! Per memory: "Fractal Hive Node: recursive self-similar governance."

pub mod phlabet;
pub mod spine;
pub mod hive;
pub mod jcard;
pub mod drum;
pub mod rainbow;
pub mod iwm;
pub mod meta;
pub mod honey;

pub use hive::HiveNode;
pub use hive::NodeKind;
pub use hive::NodeStatus;
pub use hive::Query;
pub use hive::Response;
pub use hive::{SCALE_TOKEN, SCALE_AGENT, SCALE_CLAN, SCALE_CLUSTER, SCALE_ECOSYSTEM};
pub use jcard::{JSpaceCard, JSuit, CardEffect};
pub use jcard::create_deck;
pub use phlabet::{Phoneme, Glyph, compress_to_phlabet, glyphs_to_text};
pub use iwm::IwmAddress;
pub use iwm::{W_GOVERNANCE, W_SECURITY, W_PRIVACY, W_COMMERCE};
pub use drum::{Drum, Scenario, AttackVector, ComplianceFramework, SimulationResult};
pub use rainbow::{RainbowSecurity, SecurityLayer, Operation, SecurityViolation};
pub use meta::{ExpertiseMap, TaskType, PrivacyLevel, ModelCapability};
pub use honey::{HoneyGenerator, Honey, ModelOutput, TrainingExample};

//! HiveNode — The fractal monotric cell.
//!
//! Per memory: "A HiveNode is a fractal cell. It can be an individual agent, a clan,
//! a cluster, or the entire ecosystem. Same structure at every scale."
//!
//! Per memory: "Fractal Hive Node: recursive self-similar governance — every cell
//! contains the whole pattern. J-Space Cards = symbolic knowledge tarot."
//!
//! Per memory: "Ring 0 = Layer 0 = The Monad = The One."

use std::sync::Arc;
use tokio::sync::RwLock;
use serde::{Deserialize, Serialize};

use crate::jcard::{JSpaceCard, JSuit, CardEffect};
use crate::phlabet::{Glyph, compress_to_phlabet, glyphs_to_text};
use crate::spine::Spine;
use crate::iwm::{IwmAddress, W_GOVERNANCE, W_SECURITY, W_PRIVACY, W_COMMERCE};

/// The scale constants — same node, different zoom levels.
pub const SCALE_TOKEN: u8 = 0;      // Single token / embedding
pub const SCALE_AGENT: u8 = 8;      // Individual AI agent
pub const SCALE_CLAN: u8 = 16;      // Framework clan (Mastra, LangGraph, etc.)
pub const SCALE_CLUSTER: u8 = 24;   // OWEM cluster (CSOAI, MEOK, DEFONEOS)
pub const SCALE_ECOSYSTEM: u8 = 32; // Entire SOV ecosystem

/// Node state — what the hive cell knows about itself.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeState {
    pub energy: f32,             // Cognitive activity (0.0-1.0)
    pub gspc_axes: [f32; 4],    // G-S-P-C scores (0.0-1.0)
    pub kind: NodeKind,
    pub is_dreaming: bool,
    pub last_action: String,
    pub memory: Vec<Glyph>,     // Short-term glyph memory
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum NodeKind {
    Token,
    Agent { model_id: String },
    Clan { framework: String },
    Cluster { name: String },
    Ecosystem,
}

/// A HiveNode — the fractal monotric cell.
///
/// Same structure at every scale. An agent contains sub-agents.
/// A clan contains agents. A cluster contains clans.
/// The ecosystem contains everything.
#[derive(Debug, Clone)]
pub struct HiveNode {
    pub id: u64,
    pub epoch: u64,
    pub scale: u8,
    pub axes: [f32; 4],                    // G-S-P-C scores
    pub state: Arc<RwLock<NodeState>>,
    pub children: Vec<Arc<RwLock<HiveNode>>>,
    pub parent: Option<u64>,               // Parent ID (weak ref)
    pub j_cards: Vec<JSpaceCard>,           // Symbolic knowledge
    pub spine: Spine,                       // GNN reasoning core
    pub iwm_address: IwmAddress,            // Fractal address in IWM
}

/// A query to the hive.
#[derive(Debug, Clone)]
pub struct Query {
    pub text: String,
    pub task_type: String,
    pub priority: f32,
}

/// A response from the hive.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Response {
    pub glyphs: Vec<Glyph>,
    pub text: String,
    pub confidence: f32,
    pub actions: Vec<String>,
    pub model_plan: Vec<String>,
    pub honey_id: Option<String>,
}

impl HiveNode {
    /// Create a new hive node.
    pub fn new(id: u64, scale: u8, axes: [f32; 4], kind: NodeKind) -> Self {
        let epoch = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        let w = if axes[0] >= axes[1] && axes[0] >= axes[2] && axes[0] >= axes[3] {
            W_GOVERNANCE
        } else if axes[1] >= axes[0] && axes[1] >= axes[2] && axes[1] >= axes[3] {
            W_SECURITY
        } else if axes[2] >= axes[0] && axes[2] >= axes[1] && axes[2] >= axes[3] {
            W_PRIVACY
        } else {
            W_COMMERCE
        };

        Self {
            id,
            epoch,
            scale,
            axes,
            state: Arc::new(RwLock::new(NodeState {
                energy: 0.5,
                gspc_axes: axes,
                kind,
                is_dreaming: false,
                last_action: String::new(),
                memory: Vec::new(),
            })),
            children: Vec::new(),
            parent: None,
            j_cards: Vec::new(),
            spine: Spine::new(10),
            iwm_address: IwmAddress::new(epoch as u32, scale as u16, 0, 0, 0, w),
        }
    }

    /// Think: propagate reasoning up and down the fractal.
    pub async fn think(self: std::sync::Arc<Self>, query: &Query) -> Response {
        // 1. Compress query to Phlabet
        let glyphs = compress_to_phlabet(&query.text, &format!("node-{}", self.id));

        // 2. Process through spine
        let actions = self.spine.think(&glyphs);

        // 3. Select model plan based on task type
        let model_plan = self.select_models(&query.task_type).await;

        // 4. Check confidence — if low, escalate to children or parent
        let confidence = self.calculate_confidence(&glyphs, &actions);

        if confidence < 0.95 && !self.children.is_empty() {
            // Delegate to children (boxed recursion to avoid infinite future size)
            // Children are Arc<RwLock<HiveNode>>; clone the inner node into a new Arc for the recursive call
            let mut child_responses = Vec::new();
            for child_lock in &self.children {
                let child_node = child_lock.read().await.clone();
                let child_arc = std::sync::Arc::new(child_node);
                let resp = Box::pin(async move {
                    child_arc.think(query).await
                }).await;
                child_responses.push(resp);
            }
            return self.synthesize(child_responses);
        }

        // 5. Draw J-Space cards if relevant
        let drawn_cards = self.draw_cards(&query.task_type);
        let mut card_effects = Vec::new();
        for card in &drawn_cards {
            match &card.activation {
                CardEffect::AxisFocus { axis, weight } => {
                    card_effects.push(format!("Axis {} weighted {}", axis.axis_name(), weight));
                }
                CardEffect::GovernanceCheck { policy_id } => {
                    card_effects.push(format!("Governance check: {}", policy_id));
                }
                CardEffect::SecurityScan { target } => {
                    card_effects.push(format!("Security scan: {}", target));
                }
                CardEffect::HoneyGenerate { task_type } => {
                    card_effects.push(format!("Honey generate: {}", task_type));
                }
                CardEffect::Dream { scenario } => {
                    card_effects.push(format!("Dream: {}", scenario));
                }
                CardEffect::MetaRoute { task_type } => {
                    card_effects.push(format!("Meta route: {}", task_type));
                }
                CardEffect::None => {}
            }
        }

        Response {
            glyphs: actions.clone(),
            text: glyphs_to_text(&actions),
            confidence,
            actions: card_effects,
            model_plan,
            honey_id: None,
        }
    }

    /// Dream: simulate scenarios while idle.
    pub async fn dream(&mut self) {
        {
            let mut state = self.state.write().await;
            state.is_dreaming = true;
        }

        // Generate adversarial scenarios
        let scenarios = vec![
            "governance_compliance_breach",
            "security_intrusion_attempt",
            "privacy_data_leak",
            "commerce_fraud_detection",
        ];

        for scenario in scenarios {
            let glyphs = compress_to_phlabet(scenario, &format!("dream-{}", self.id));
            self.spine.learn(&glyphs, 0.5);
        }

        {
            let mut state = self.state.write().await;
            state.is_dreaming = false;
        }
    }

    /// Add a child node.
    pub async fn add_child(&mut self, child: Arc<RwLock<HiveNode>>) {
        {
            let mut child_node = child.write().await;
            child_node.parent = Some(self.id);
        }
        self.children.push(child);
    }

    /// Select best models for a task type.
    async fn select_models(&self, task_type: &str) -> Vec<String> {
        match task_type {
            "governance" => vec!["kimi-k3".to_string(), "claude-opus-5".to_string()],
            "security" => vec!["claude-opus-5".to_string(), "deepseek-v4-pro".to_string()],
            "privacy" => vec!["sov3-local".to_string()],
            "commerce" => vec!["deepseek-v4-pro".to_string(), "groq-llama-3.3".to_string()],
            _ => vec!["kimi-k3".to_string()],
        }
    }

    /// Calculate confidence based on glyph matches.
    fn calculate_confidence(&self, input: &[Glyph], output: &[Glyph]) -> f32 {
        if input.is_empty() || output.is_empty() {
            return 0.0;
        }
        let match_count = input.iter().zip(output.iter())
            .filter(|(a, b)| a.phoneme == b.phoneme)
            .count();
        match_count as f32 / input.len().max(output.len()) as f32
    }

    /// Draw J-Space cards relevant to a task type.
    fn draw_cards(&self, task_type: &str) -> Vec<&JSpaceCard> {
        self.j_cards.iter().filter(|card| {
            match task_type {
                "governance" => card.suit == JSuit::Scales,
                "security" => card.suit == JSuit::Shield,
                "privacy" => card.suit == JSuit::Lock,
                "commerce" => card.suit == JSuit::Horn,
                _ => true,
            }
        }).take(3).collect()
    }

    /// Synthesize multiple child responses into one.
    fn synthesize(&self, responses: Vec<Response>) -> Response {
        let mut all_glyphs = Vec::new();
        let mut all_actions = Vec::new();
        let mut all_models = Vec::new();
        let mut total_confidence = 0.0;

        for resp in &responses {
            all_glyphs.extend(resp.glyphs.clone());
            all_actions.extend(resp.actions.clone());
            all_models.extend(resp.model_plan.clone());
            total_confidence += resp.confidence;
        }

        let confidence = if responses.is_empty() { 0.0 } else { total_confidence / responses.len() as f32 };

        Response {
            glyphs: all_glyphs,
            text: format!("Synthesized from {} children", responses.len()),
            confidence,
            actions: all_actions,
            model_plan: all_models,
            honey_id: None,
        }
    }

    /// Current state of the node.
    pub async fn status(&self) -> NodeStatus {
        let state = self.state.read().await;
        NodeStatus {
            id: self.id,
            scale: self.scale,
            energy: state.energy,
            gspc_axes: state.gspc_axes,
            children_count: self.children.len(),
            j_cards_count: self.j_cards.len(),
            spine_layers: self.spine.layers.len(),
            is_dreaming: state.is_dreaming,
        }
    }
}

/// Serializable node status.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeStatus {
    pub id: u64,
    pub scale: u8,
    pub energy: f32,
    pub gspc_axes: [f32; 4],
    pub children_count: usize,
    pub j_cards_count: usize,
    pub spine_layers: usize,
    pub is_dreaming: bool,
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::jcard::create_deck;

    #[tokio::test]
    async fn test_hive_node_think() {
        let mut node = HiveNode::new(1, SCALE_AGENT, [0.8, 0.6, 0.4, 0.2], NodeKind::Agent {
            model_id: "kimi-k3".to_string(),
        });
        node.j_cards = create_deck();

        let query = Query {
            text: "EU AI Act governance compliance audit".to_string(),
            task_type: "governance".to_string(),
            priority: 1.0,
        };

        let node = std::sync::Arc::new(node);
        let response = node.think(&query).await;
        assert!(!response.glyphs.is_empty());
        assert!(response.confidence >= 0.0);
    }

    #[tokio::test]
    async fn test_hive_node_dream() {
        let mut node = HiveNode::new(1, SCALE_AGENT, [0.8, 0.6, 0.4, 0.2], NodeKind::Agent {
            model_id: "kimi-k3".to_string(),
        });
        node.dream().await;
        let status = node.status().await;
        assert!(!status.is_dreaming);
    }
}

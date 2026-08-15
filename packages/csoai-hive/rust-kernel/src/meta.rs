//! Meta — Meta-cognition: which AI family for what.
//!
//! Per memory: "Meta-Cognition: The AI family expertise graph."
//! Per memory: "SOV doesn't randomly route. It knows."

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TaskType {
    Reasoning,
    Coding,
    Math,
    Creative,
    Governance,
    Security,
    Privacy,
    Commerce,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelCapability {
    pub model_id: String,
    pub task_type: TaskType,
    pub score: f32,             // 0.0-1.0, measured performance
    pub cost_per_1k: f32,       // $/1K tokens
    pub latency_ms: u32,
    pub privacy_level: PrivacyLevel,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum PrivacyLevel {
    Local,        // On-device only
    Encrypted,    // Encrypted in transit
    Cloud,        // Standard cloud (acceptable for non-sensitive)
}

#[derive(Debug, Clone)]
pub struct ExpertiseMap {
    pub capabilities: Vec<ModelCapability>,
}

impl ExpertiseMap {
    pub fn new() -> Self {
        // Per July 2026 bleeding-edge briefing
        let capabilities = vec![
            // Reasoning
            ModelCapability { model_id: "kimi-k3".to_string(), task_type: TaskType::Reasoning, score: 0.95, cost_per_1k: 0.015, latency_ms: 1500, privacy_level: PrivacyLevel::Encrypted },
            ModelCapability { model_id: "claude-opus-5".to_string(), task_type: TaskType::Reasoning, score: 0.98, cost_per_1k: 0.025, latency_ms: 2000, privacy_level: PrivacyLevel::Cloud },
            // Coding
            ModelCapability { model_id: "claude-fable-5".to_string(), task_type: TaskType::Coding, score: 0.98, cost_per_1k: 0.050, latency_ms: 2500, privacy_level: PrivacyLevel::Cloud },
            ModelCapability { model_id: "gpt-5.6-sol".to_string(), task_type: TaskType::Coding, score: 0.92, cost_per_1k: 0.030, latency_ms: 1800, privacy_level: PrivacyLevel::Cloud },
            // Math
            ModelCapability { model_id: "deepseek-v4-pro".to_string(), task_type: TaskType::Math, score: 0.85, cost_per_1k: 0.0009, latency_ms: 800, privacy_level: PrivacyLevel::Cloud },
            // Governance
            ModelCapability { model_id: "kimi-k3".to_string(), task_type: TaskType::Governance, score: 0.95, cost_per_1k: 0.015, latency_ms: 1500, privacy_level: PrivacyLevel::Encrypted },
            ModelCapability { model_id: "sov3-local".to_string(), task_type: TaskType::Governance, score: 0.85, cost_per_1k: 0.0, latency_ms: 100, privacy_level: PrivacyLevel::Local },
            // Privacy-sensitive
            ModelCapability { model_id: "sov3-local".to_string(), task_type: TaskType::Privacy, score: 0.90, cost_per_1k: 0.0, latency_ms: 100, privacy_level: PrivacyLevel::Local },
            // Commerce
            ModelCapability { model_id: "deepseek-v4-flash".to_string(), task_type: TaskType::Commerce, score: 0.80, cost_per_1k: 0.0003, latency_ms: 400, privacy_level: PrivacyLevel::Cloud },
        ];
        Self { capabilities }
    }

    /// Select best models for a task type, with privacy/cost constraints.
    pub fn select(&self, task_type: &TaskType, privacy_req: Option<&PrivacyLevel>, max_cost_per_1k: Option<f32>) -> Vec<&ModelCapability> {
        let mut candidates: Vec<&ModelCapability> = self.capabilities.iter()
            .filter(|c| std::mem::discriminant(&c.task_type) == std::mem::discriminant(task_type))
            .collect();

        if let Some(p) = privacy_req {
            candidates.retain(|c| privacy_level_rank(&c.privacy_level) >= privacy_level_rank(p));
        }
        if let Some(max) = max_cost_per_1k {
            candidates.retain(|c| c.cost_per_1k <= max);
        }

        // Sort by score desc, then by cost asc
        candidates.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap_or(std::cmp::Ordering::Equal)
            .then(a.cost_per_1k.partial_cmp(&b.cost_per_1k).unwrap_or(std::cmp::Ordering::Equal)));

        candidates
    }
}

fn privacy_level_rank(level: &PrivacyLevel) -> u8 {
    match level {
        PrivacyLevel::Cloud => 1,
        PrivacyLevel::Encrypted => 2,
        PrivacyLevel::Local => 3,
    }
}

impl Default for ExpertiseMap {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_expertise_selection() {
        let map = ExpertiseMap::new();
        let selected = map.select(&TaskType::Governance, Some(&PrivacyLevel::Local), None);
        assert!(!selected.is_empty());
    }
}
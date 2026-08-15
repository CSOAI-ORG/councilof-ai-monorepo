//! Honey — Knowledge creation engine.
//!
//! Per memory: "Honey Generator: Self-generated knowledge that feeds back into training."
//! Per memory: "Every time SOV routes to Kimi + Claude + DeepSeek, it learns from all three."

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::phlabet::{Glyph, compress_to_phlabet};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelOutput {
    pub model_id: String,
    pub text: String,
    pub confidence: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Honey {
    pub id: String,
    pub task: String,
    pub glyphs: Vec<Glyph>,
    pub examples: Vec<TrainingExample>,
    pub provenance: Vec<String>,
    pub quality: f32,
    pub timestamp: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrainingExample {
    pub input: String,
    pub output: String,
    pub model_id: String,
}

#[derive(Debug, Clone)]
pub struct HoneyGenerator {
    pub quality_threshold: f32,
}

impl HoneyGenerator {
    pub fn new() -> Self {
        Self { quality_threshold: 0.7 }
    }

    /// Generate honey from multiple model outputs.
    pub fn synthesize(&self, outputs: &[ModelOutput], task: &str) -> Honey {
        // 1. Compress each output to Phlabet
        let mut all_glyphs: Vec<Glyph> = Vec::new();
        let mut examples: Vec<TrainingExample> = Vec::new();
        let mut provenances: Vec<String> = Vec::new();

        for out in outputs {
            let glyphs = compress_to_phlabet(&out.text, &format!("honey-{}", out.model_id));
            all_glyphs.extend(glyphs);
            examples.push(TrainingExample {
                input: task.to_string(),
                output: out.text.clone(),
                model_id: out.model_id.clone(),
            });
            provenances.push(out.model_id.clone());
        }

        // 2. Calculate quality (average confidence)
        let quality = if outputs.is_empty() {
            0.0
        } else {
            outputs.iter().map(|o| o.confidence).sum::<f32>() / outputs.len() as f32
        };

        // 3. Generate ID from task hash
        let mut hasher = Sha256::new();
        hasher.update(task.as_bytes());
        let hash: [u8; 32] = hasher.finalize().into();
        let id = hash[..8].iter().map(|b| format!("{:02x}", b)).collect::<String>();

        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        Honey {
            id,
            task: task.to_string(),
            glyphs: all_glyphs,
            examples,
            provenance: provenances,
            quality,
            timestamp,
        }
    }
}

impl Default for HoneyGenerator {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_honey_generation() {
        let gen = HoneyGenerator::new();
        let outputs = vec![
            ModelOutput { model_id: "kimi-k3".to_string(), text: "governance requires compliance".to_string(), confidence: 0.95 },
            ModelOutput { model_id: "claude-opus-5".to_string(), text: "regulation must be followed".to_string(), confidence: 0.92 },
        ];
        let honey = gen.synthesize(&outputs, "EU AI Act compliance");
        assert!(!honey.glyphs.is_empty());
        assert_eq!(honey.examples.len(), 2);
        assert!(honey.quality > 0.9);
    }
}
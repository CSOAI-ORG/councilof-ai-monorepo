//! Spine — GNN-like message passing over Phlabet graphs.
//!
//! Per memory: "The Spine: Message Passing Neural Network over Phlabet graphs."
//! Per memory: "10 layers, ~2ms on M4."
//!
//! The spine runs on your M4 Mac at 2ms per reasoning step. It doesn't need cloud GPU.
//! It's a small, fast, local brain that orchestrates the big cloud models.

use crate::phlabet::Glyph;

/// One layer of the GNN — message passing + aggregation.
#[derive(Debug, Clone)]
pub struct SpineLayer {
    pub weights: Vec<f32>,
    pub dim: usize,
}

impl SpineLayer {
    pub fn new(dim: usize) -> Self {
        Self {
            weights: vec![1.0 / dim as f32; dim],
            dim,
        }
    }

    /// Message passing: each glyph's vector aggregates neighbor information.
    pub fn propagate(&self, glyphs: &[Glyph]) -> Vec<Vec<f32>> {
        if glyphs.is_empty() {
            return Vec::new();
        }

        // Mean aggregation (GNN-style)
        let mut aggregated = vec![0.0f32; 64];
        for g in glyphs {
            for (i, &v) in g.vector.iter().enumerate() {
                aggregated[i] += v;
            }
        }
        let n = glyphs.len() as f32;
        for v in &mut aggregated {
            *v /= n;
        }

        // Apply weights
        let mut output = Vec::with_capacity(glyphs.len());
        for g in glyphs {
            let mut result = vec![0.0f32; 64];
            for i in 0..64 {
                result[i] = g.vector[i] * self.weights[i] + aggregated[i] * (1.0 - self.weights[i]);
            }
            output.push(result);
        }
        output
    }

    /// Update weights based on reward signal.
    pub fn update(&mut self, reward: f32, learning_rate: f32) {
        for w in &mut self.weights {
            *w += reward * learning_rate;
            *w = w.clamp(0.0, 1.0);
        }
    }
}

/// The Spine: 10-layer GNN reasoning core.
#[derive(Debug, Clone)]
pub struct Spine {
    pub layers: Vec<SpineLayer>,
    pub memory: Vec<Glyph>,       // Short-term reasoning memory
    pub expertise: Vec<(String, f32)>, // (task_type, score) — learned routing
}

impl Spine {
    pub fn new(n_layers: usize) -> Self {
        let layers = (0..n_layers).map(|_| SpineLayer::new(64)).collect();
        Self {
            layers,
            memory: Vec::new(),
            expertise: Vec::new(),
        }
    }

    /// Think: propagate reasoning through all layers.
    pub fn think(&self, glyphs: &[Glyph]) -> Vec<Glyph> {
        if glyphs.is_empty() {
            return Vec::new();
        }

        let mut current: Vec<Glyph> = glyphs.to_vec();

        for layer in &self.layers {
            let vectors = layer.propagate(&current);
            for (i, vec) in vectors.into_iter().enumerate() {
                if i < current.len() {
                    let mut new_vector = [0.0f32; 64];
                    for (idx, &v) in vec.iter().enumerate() {
                        if idx < 64 {
                            new_vector[idx] = v;
                        }
                    }
                    current[i].vector = new_vector;
                }
            }
        }

        current
    }

    /// Learn: update weights from experience.
    pub fn learn(&mut self, glyphs: &[Glyph], reward: f32) {
        let lr = 0.01;
        for layer in &mut self.layers {
            layer.update(reward, lr);
        }
        self.memory.extend_from_slice(glyphs);
    }

    /// Get expertise map.
    pub fn expertise_map(&self) -> &[(String, f32)] {
        &self.expertise
    }

    /// Update expertise for a task type.
    pub fn update_expertise(&mut self, task_type: &str, score: f32) {
        if let Some((_, s)) = self.expertise.iter_mut().find(|(t, _)| t == task_type) {
            *s = (*s * 0.9 + score * 0.1).clamp(0.0, 1.0); // EMA
        } else {
            self.expertise.push((task_type.to_string(), score));
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::phlabet::Glyph;

    #[test]
    fn test_spine_think() {
        let spine = Spine::new(10);
        let glyphs = vec![
            Glyph::new(0x00, 200, "test", 1.0),
            Glyph::new(0x03, 200, "test", 1.0),
        ];
        let result = spine.think(&glyphs);
        assert_eq!(result.len(), 2);
    }

    #[test]
    fn test_spine_learn() {
        let mut spine = Spine::new(10);
        let glyphs = vec![Glyph::new(0x00, 200, "test", 1.0)];
        spine.learn(&glyphs, 0.8);
        assert_eq!(spine.memory.len(), 1);
    }
}

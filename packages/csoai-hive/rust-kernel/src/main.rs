//! sov-hive CLI — interactive demo of the SOVOS Fractal Monotric Hive.

use sov_hive::{
    HiveNode, NodeKind, JSpaceCard,
    IwmAddress, W_GOVERNANCE,
    Drum, RainbowSecurity, Operation, ExpertiseMap, TaskType, PrivacyLevel,
    HoneyGenerator, ModelOutput,
    hive::{SCALE_AGENT, SCALE_CLAN, SCALE_CLUSTER, SCALE_ECOSYSTEM},
    jcard::create_deck,
    phlabet::compress_to_phlabet, phlabet::glyphs_to_text,
};

#[tokio::main]
async fn main() {
    println!("╔═══════════════════════════════════════════════════════════════╗");
    println!("║  SOVOS Fractal Monotric Hive — Ring-0 AI Governance Kernel   ║");
    println!("║  Every node is a fractal cell. Every cell contains the whole. ║");
    println!("╚═══════════════════════════════════════════════════════════════╝");
    println!();

    println!("═══ Phase 1: Phlabet (256 primal symbols) ═══");
    let glyphs = compress_to_phlabet(
        "EU AI Act Article 50 requires governance compliance audit",
        "demo"
    );
    println!("  Compressed text: {} glyphs", glyphs.len());
    for g in &glyphs {
        println!("    {} i={}", g, g.intensity);
    }
    println!("  Decoded: {}", glyphs_to_text(&glyphs));
    println!();

    println!("═══ Phase 2: J-Space Cards (60 cards) ═══");
    let deck = create_deck();
    println!("  Deck size: {}", deck.len());
    let kings: Vec<&JSpaceCard> = deck.iter().filter(|c| c.rank == 13).collect();
    println!("  King cards:");
    for k in &kings {
        println!("    {} — {}", k.name, k.description);
    }
    println!();

    println!("═══ Phase 3: IWM Fractal Address ═══");
    let addr = IwmAddress::new(1000, 8, 100, 200, 300, W_GOVERNANCE);
    let bytes = addr.to_bytes();
    println!("  Address: epoch={} scale={} x={} y={} z={} w={} (Governance)",
        addr.epoch, addr.scale, addr.x, addr.y, addr.z, addr.w);
    println!("  Packed: {} bytes", bytes.len());
    println!("  Parent (zoom out): scale={}", addr.parent().scale);
    println!("  Children (zoom in): {} cells", addr.children().len());
    println!();

    println!("═══ Phase 4: Build the Hive (fractal recursion) ═══");
    let root = std::sync::Arc::new(tokio::sync::RwLock::new(
        HiveNode::new(1, SCALE_ECOSYSTEM, [0.9, 0.85, 0.80, 0.75], NodeKind::Ecosystem)
    ));

    let cluster = std::sync::Arc::new(tokio::sync::RwLock::new(
        HiveNode::new(2, SCALE_CLUSTER, [0.88, 0.82, 0.78, 0.72], NodeKind::Cluster {
            name: "CSOAI-Governance".to_string(),
        })
    ));

    let clan = std::sync::Arc::new(tokio::sync::RwLock::new(
        HiveNode::new(3, SCALE_CLAN, [0.85, 0.80, 0.75, 0.70], NodeKind::Clan {
            framework: "Mastra".to_string(),
        })
    ));

    let agent = std::sync::Arc::new(tokio::sync::RwLock::new(
        HiveNode::new(4, SCALE_AGENT, [0.82, 0.78, 0.72, 0.68], NodeKind::Agent {
            model_id: "kimi-k3".to_string(),
        })
    ));

    // Wire the fractal: ecosystem → cluster → clan → agent
    {
        let mut r = root.write().await;
        r.add_child(cluster.clone()).await;
    }
    {
        let mut c = cluster.write().await;
        c.add_child(clan.clone()).await;
    }
    {
        let mut cl = clan.write().await;
        cl.add_child(agent.clone()).await;
    }
    println!("  Ecosystem (1) → Cluster (2) → Clan (3) → Agent (4)");
    println!();

    println!("═══ Phase 5: Honey Generation (knowledge creation) ═══");
    let gen = HoneyGenerator::new();
    let outputs = vec![
        ModelOutput { model_id: "kimi-k3".to_string(), text: "EU AI Act requires governance compliance for high-risk systems".to_string(), confidence: 0.95 },
        ModelOutput { model_id: "claude-opus-5".to_string(), text: "Article 50 mandates audit trails and machine-readable provenance".to_string(), confidence: 0.92 },
        ModelOutput { model_id: "deepseek-v4-pro".to_string(), text: "Compliance requires governance, security, privacy, commerce axes".to_string(), confidence: 0.88 },
    ];
    let honey = gen.synthesize(&outputs, "EU AI Act compliance governance");
    println!("  Honey ID: {}", honey.id);
    println!("  Glyphs synthesized: {}", honey.glyphs.len());
    println!("  Training examples: {}", honey.examples.len());
    println!("  Provenance: {:?}", honey.provenance);
    println!("  Quality: {:.2}", honey.quality);
    println!();

    println!("═══ Phase 6: Meta-Cognition (which model for what) ═══");
    let map = ExpertiseMap::new();
    let gov = map.select(&TaskType::Governance, Some(&PrivacyLevel::Local), None);
    println!("  Governance task (Local privacy): {} candidates", gov.len());
    for m in &gov {
        println!("    {} — score={:.2} cost=${}/1K latency={}ms",
            m.model_id, m.score, m.cost_per_1k, m.latency_ms);
    }
    println!();

    println!("═══ Phase 7: Rainbow Security (7 layers) ═══");
    let rainbow = RainbowSecurity::new();
    println!("  Layers: {}", rainbow.layers.len());
    for l in &rainbow.layers {
        println!("    {}", l.name());
    }
    let op = Operation {
        name: "demo_op".to_string(),
        requires_hardware: false,
        hardware_attested: true,
        network_access: true,
        encrypted: true,
        behavioral_anomaly_score: 0.1,
        temporal_violation: false,
        requires_glyph_auth: true,
        glyph_verified: true,
        prompt_injection_score: 0.1,
    };
    println!("  Validation: {:?}", rainbow.validate(&op).is_ok());
    println!();

    println!("═══ Phase 8: Drum (continuous simulation) ═══");
    let drum = Drum::new(60);
    println!("  Tempo: {} Hz ({}ms per beat)", drum.tempo_hz, drum.tempo_ms());
    println!("  Scenarios: {}", drum.scenarios.len());
    println!();

    println!("═══ Phase 9: Think (reasoning pipeline) ═══");
    let query = sov_hive::hive::Query {
        text: "EU AI Act Article 50 requires governance compliance audit".to_string(),
        task_type: "governance".to_string(),
        priority: 1.0,
    };

    {
        let mut r = root.write().await;
        r.j_cards = create_deck();
    }

    let response = {
        // Extract the HiveNode out of the RwLock, wrap in Arc for the recursive call
        let node = root.read().await.clone();
        let node_arc = std::sync::Arc::new(node);
        node_arc.think(&query).await
    };

    println!("  Query: {}", query.text);
    println!("  Response glyphs: {}", response.glyphs.len());
    println!("  Confidence: {:.2}", response.confidence);
    println!("  Model plan: {:?}", response.model_plan);
    println!("  Card actions:");
    for action in &response.actions {
        println!("    → {}", action);
    }
    println!();

    println!("═══ Phase 10: Hive Status ═══");
    let r = root.read().await;
    let status = r.status().await;
    println!("  Root status: {:?}", status);
    println!();

    println!("╔═══════════════════════════════════════════════════════════════╗");
    println!("║  Hive is alive. Mind is online. Ring 0 touches the silicon.   ║");
    println!("║  SOVOS is sovereign. Every cell contains the whole.          ║");
    println!("╚═══════════════════════════════════════════════════════════════╝");
}
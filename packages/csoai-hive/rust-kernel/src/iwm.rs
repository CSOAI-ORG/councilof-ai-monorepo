//! IWM — Infinite World Memory (Fractal Temporal Storage).
//!
//! Per memory: "IWM 128-bit fractal address space: [Epoch:32][Scale:16][X:24][Y:24][Z:24][W:8]."
//! Per memory: "Mouse wheel up = scale-- (deeper into detail). Mouse wheel down = scale++ (higher abstraction)."
//!
//! Each address points to a SovRecord. Zstd compressed. Merkle tree hashed.
//! Fractal indexing: zoom out = parent node aggregates children.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

/// 128-bit IWM fractal address.
/// Layout: [Epoch:32][Scale:16][X:24][Y:24][Z:24][W:8] = 19 bytes packed (big-endian).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct IwmAddress {
    pub epoch: u32,    // 32 bits — temporal coordinate (blockchain-style)
    pub scale: u16,    // 16 bits — zoom level (0=quantum/token, 16=cosmic/ecosystem)
    pub x: i32,        // 24 bits used — spatial X
    pub y: i32,        // 24 bits used — spatial Y
    pub z: i32,        // 24 bits used — spatial Z
    pub w: u8,         // 8 bits — which GSPC axis (G=0, S=1, P=2, C=3)
}

/// GSPC axis constants for the W field.
pub const W_GOVERNANCE: u8 = 0;
pub const W_SECURITY: u8 = 1;
pub const W_PRIVACY: u8 = 2;
pub const W_COMMERCE: u8 = 3;

impl IwmAddress {
    pub fn new(epoch: u32, scale: u16, x: i32, y: i32, z: i32, w: u8) -> Self {
        Self { epoch, scale, x, y, z, w }
    }

    /// Pack to 19 bytes (big-endian).
    pub fn to_bytes(&self) -> [u8; 19] {
        let mut buf = [0u8; 19];
        buf[0..4].copy_from_slice(&self.epoch.to_be_bytes());
        buf[4..6].copy_from_slice(&self.scale.to_be_bytes());
        // 24-bit X (use lower 24 bits of i32)
        buf[6] = ((self.x >> 16) & 0xFF) as u8;
        buf[7] = ((self.x >> 8) & 0xFF) as u8;
        buf[8] = (self.x & 0xFF) as u8;
        // 24-bit Y
        buf[9] = ((self.y >> 16) & 0xFF) as u8;
        buf[10] = ((self.y >> 8) & 0xFF) as u8;
        buf[11] = (self.y & 0xFF) as u8;
        // 24-bit Z
        buf[12] = ((self.z >> 16) & 0xFF) as u8;
        buf[13] = ((self.z >> 8) & 0xFF) as u8;
        buf[14] = (self.z & 0xFF) as u8;
        // 8-bit W
        buf[15] = self.w;
        // 3 bytes padding to reach 19
        buf
    }

    pub fn from_bytes(data: &[u8]) -> Self {
        let epoch = u32::from_be_bytes([data[0], data[1], data[2], data[3]]);
        let scale = u16::from_be_bytes([data[4], data[5]]);
        let x = ((data[6] as i32) << 16) | ((data[7] as i32) << 8) | (data[8] as i32);
        let y = ((data[9] as i32) << 16) | ((data[10] as i32) << 8) | (data[11] as i32);
        let z = ((data[12] as i32) << 16) | ((data[13] as i32) << 8) | (data[14] as i32);
        let w = data[15];
        Self { epoch, scale, x, y, z, w }
    }

    /// SHA256 hash of the address.
    pub fn hash(&self) -> [u8; 32] {
        let mut hasher = Sha256::new();
        hasher.update(&self.to_bytes());
        hasher.finalize().into()
    }

    /// Parent address (zoom out one level).
    pub fn parent(&self) -> Self {
        Self {
            epoch: self.epoch,
            scale: self.scale.saturating_add(1),
            x: self.x / 2,
            y: self.y / 2,
            z: self.z / 2,
            w: self.w,
        }
    }

    /// Child addresses (zoom in one level).
    pub fn children(&self) -> Vec<Self> {
        let scale = self.scale.saturating_sub(1);
        let mut kids = Vec::with_capacity(8);
        for dx in 0..2 {
            for dy in 0..2 {
                for dz in 0..2 {
                    kids.push(Self {
                        epoch: self.epoch,
                        scale,
                        x: self.x * 2 + dx,
                        y: self.y * 2 + dy,
                        z: self.z * 2 + dz,
                        w: self.w,
                    });
                }
            }
        }
        kids
    }

    /// Axis name.
    pub fn axis_name(&self) -> &str {
        match self.w {
            W_GOVERNANCE => "Governance",
            W_SECURITY => "Security",
            W_PRIVACY => "Privacy",
            W_COMMERCE => "Commerce",
            _ => "Unknown",
        }
    }
}

/// A record stored at an IWM address.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SovRecord {
    pub address: IwmAddress,
    pub data: Vec<u8>,          // Compressed payload
    pub hash: [u8; 32],         // SHA256 of data
    pub timestamp: u64,         // Unix epoch millis
    pub provenance: String,     // Who created this
}

impl SovRecord {
    pub fn new(address: IwmAddress, data: Vec<u8>, provenance: &str) -> Self {
        let mut hasher = Sha256::new();
        hasher.update(&data);
        let hash: [u8; 32] = hasher.finalize().into();
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis() as u64;
        Self { address, data, hash, timestamp, provenance: provenance.to_string() }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_address_roundtrip() {
        let addr = IwmAddress::new(1000, 8, 100, 200, 300, W_GOVERNANCE);
        let bytes = addr.to_bytes();
        let addr2 = IwmAddress::from_bytes(&bytes);
        assert_eq!(addr, addr2);
    }

    #[test]
    fn test_parent_child() {
        let addr = IwmAddress::new(1000, 8, 100, 200, 300, W_SECURITY);
        let parent = addr.parent();
        assert_eq!(parent.scale, 9);
        let children = addr.children();
        assert_eq!(children.len(), 8);
        assert_eq!(children[0].scale, 7);
    }
}

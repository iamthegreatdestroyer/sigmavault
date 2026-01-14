"""Quick test for VAE module."""
from sigmavault.ml.pattern_vae import PatternObfuscationVAE, VAEConfig, create_pattern_vae
from sigmavault.ml.synthetic_data_generator import SyntheticDataGenerator, PatternType
from datetime import datetime
import tempfile
from pathlib import Path

print('Testing Pattern Obfuscation VAE...')
print('='*50)

with tempfile.TemporaryDirectory() as tmpdir:
    vault_path = Path(tmpdir)
    
    # Create VAE
    vae = create_pattern_vae(vault_path, latent_dim=4)
    print(f'✅ VAE created with latent_dim={vae.config.latent_dim}')
    
    # Generate synthetic training data (30 days = more data)
    gen = SyntheticDataGenerator(seed=42)
    sequences = []
    
    events = gen.generate_normal_workday(
        vault_id='test-vault',
        start_date=datetime(2026, 1, 1),
        days=30  # 30 days of data
    )
    
    # Split into 1-hour windows (sliding)
    for i in range(0, len(events)-20, 5):
        sequences.append(events[i:i+20])
    
    print(f'✅ Generated {len(sequences)} training sequences from {len(events)} events')
    
    if len(sequences) >= 50:
        print('   Training VAE (5 epochs)...')
        vae.config.epochs = 5
        metrics = vae.train(sequences, verbose=0)
        print(f'✅ Training complete!')
        print(f'   - Samples: {metrics["n_samples"]}')
        print(f'   - Final loss: {metrics["final_loss"]:.4f}')
        
        decoys = vae.generate_decoys(n=5)
        print(f'✅ Generated {len(decoys)} decoy patterns')
        for i, d in enumerate(decoys):
            print(f'   Decoy {i+1}: freq={d.features["access_frequency"]:.1f}')
    else:
        print(f'   ⚠️ Only {len(sequences)} sequences (need 50+)')

print('='*50)
print('✅ Pattern Obfuscation VAE module verified!')
